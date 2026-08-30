"""F16-M3 regression: mark_partial() must leave a durable trace even when no
reservation record_id exists, instead of silently no-op'ing.

Prior bug: mark_partial(record_id="") did nothing when both save_asset()
attempts failed, leaving a real Drive artifact with zero Airtable trace
(BUG_AUDIT_LOG.md "F16 Media — Decision Gate", F16-M3). This test exercises
the actual mark_partial() code path inside handle_file_upload() — it mocks
only the external boundaries (Airtable via save_asset/find_asset_by_logical_
media_key, Drive via drive_adapter), not mark_partial() itself.
"""

from unittest.mock import patch

import drive_adapter
import media_handler
from media_gateway import MediaLookupResult
from airtable_schema import MediaPersistenceState


def _upload_kwargs(file_id: str) -> dict:
    return dict(
        file_bytes=b"x" * 1024,
        filename="x.pdf",
        mime_type="application/pdf",
        file_type="document",
        file_id=file_id,
        user_id="u1",
        domain="general",
    )


def test_reservation_id_present_keeps_update_behavior_unchanged():
    """When an 'incomplete' record already exists, mark_partial() must still
    UPDATE it, not create a second one — existing reservation-id behavior is
    preserved."""
    existing_record = {"id": "recEXIST1", "fields": {}}
    with patch.object(media_handler, "find_asset_by_logical_media_key",
                       return_value=MediaLookupResult("incomplete", record=existing_record)), \
         patch.object(media_handler, "record_id", return_value="recEXIST1"), \
         patch.object(media_handler, "record_fields", return_value={}), \
         patch.object(drive_adapter, "_get_upload_folder", return_value="folder123"), \
         patch.object(drive_adapter, "find_existing_by_logical_media_key",
                       return_value=drive_adapter.DriveFile(
                           error=drive_adapter.MediaError("DRIVE_NOT_FOUND", "no Drive object found", False)
                       )), \
         patch.object(drive_adapter, "upload_file") as mock_upload, \
         patch.object(media_handler, "save_asset") as mock_save, \
         patch.object(media_handler, "update_asset_persistence", return_value=False) as mock_update:
        mock_upload.return_value = drive_adapter.DriveFile(
            file_id="driveF1", web_url="https://drive/x", name="x.pdf", size_bytes=1024
        )
        result = media_handler.handle_file_upload(**_upload_kwargs("f-m3-reservation"))

    assert not result.ok and result.error.error_code == "MEDIA_FILES_PARTIAL"
    # DRIVE_UPLOADED write fails first, then mark_partial() corrects the same
    # record to PARTIAL — both are updates against the existing record_id.
    assert mock_update.call_count == 2
    for call in mock_update.call_args_list:
        assert call.args[0] == "recEXIST1"
    assert mock_update.call_args_list[-1].kwargs["state"] == MediaPersistenceState.PARTIAL
    mock_save.assert_not_called()
    print("✅ reservation id present → mark_partial() updates the existing record, never creates a new one")


def test_no_reservation_id_fresh_upload_creates_durable_trace():
    """Path: no prior record, no reusable Drive object, Drive upload
    succeeds, both save_asset() attempts fail → mark_partial(record_id="")
    must now CREATE a durable PARTIAL record instead of losing the evidence."""
    with patch.object(media_handler, "find_asset_by_logical_media_key",
                       return_value=MediaLookupResult("not_found")), \
         patch.object(drive_adapter, "_get_upload_folder", return_value="folder123"), \
         patch.object(drive_adapter, "find_existing_by_logical_media_key",
                       return_value=drive_adapter.DriveFile(
                           error=drive_adapter.MediaError("DRIVE_NOT_FOUND", "no Drive object found", False)
                       )), \
         patch.object(drive_adapter, "upload_file") as mock_upload, \
         patch.object(media_handler, "save_asset", side_effect=[None, None, "recNEWTRACE"]) as mock_save:
        mock_upload.return_value = drive_adapter.DriveFile(
            file_id="driveF2", web_url="https://drive/y", name="x.pdf", size_bytes=1024
        )
        result = media_handler.handle_file_upload(**_upload_kwargs("f-m3-fresh"))

    assert not result.ok and result.error.error_code == "MEDIA_FILES_PARTIAL"
    assert mock_save.call_count == 3, "expected: initial PENDING save, DRIVE_UPLOADED save, then mark_partial's durable-trace save"
    trace_record = mock_save.call_args_list[2].args[0]
    assert trace_record.persistence_state == MediaPersistenceState.PARTIAL
    assert trace_record.drive_file_id == "driveF2"
    assert trace_record.drive_url == "https://drive/y"
    assert trace_record.last_error_code == "MEDIA_FILES_PARTIAL"
    assert trace_record.logical_media_key == media_handler.logical_media_key("telegram", "f-m3-fresh")
    print("✅ no reservation id, fresh Drive upload, both saves fail → durable PARTIAL trace created (logical_media_key recoverable)")


def test_no_reservation_id_reused_drive_object_creates_durable_trace():
    """Path: no prior record, an existing Drive object IS found (reused),
    but the reconciling save_asset() call fails → mark_partial(record_id=None)
    must create a durable trace instead of losing it."""
    with patch.object(media_handler, "find_asset_by_logical_media_key",
                       return_value=MediaLookupResult("not_found")), \
         patch.object(drive_adapter, "_get_upload_folder", return_value="folder123"), \
         patch.object(drive_adapter, "find_existing_by_logical_media_key",
                       return_value=drive_adapter.DriveFile(
                           file_id="driveF3", web_url="https://drive/z", name="x.pdf", size_bytes=1024
                       )), \
         patch.object(media_handler, "save_asset", side_effect=[None, "recTRACE2"]) as mock_save:
        result = media_handler.handle_file_upload(**_upload_kwargs("f-m3-reused"))

    assert not result.ok and result.error.error_code == "MEDIA_FILES_RECONCILIATION_FAILED"
    assert mock_save.call_count == 2, "expected: failed reconciliation save, then mark_partial's durable-trace save"
    trace_record = mock_save.call_args_list[1].args[0]
    assert trace_record.persistence_state == MediaPersistenceState.PARTIAL
    assert trace_record.drive_file_id == "driveF3"
    assert trace_record.drive_url == "https://drive/z"
    print("✅ no reservation id, reused Drive object, reconciliation save fails → durable PARTIAL trace created")


def test_retry_reconciles_against_durable_trace_without_duplicating():
    """A retry after test_no_reservation_id_fresh_upload_creates_durable_trace
    must find the durable trace via find_asset_by_logical_media_key() and
    reconcile (update) it — never call save_asset() to create a second
    record for the same logical_media_key."""
    key = media_handler.logical_media_key("telegram", "f-m3-retry", None)
    traced_record = {"id": "recNEWTRACE", "fields": {"Logical Media Key": key}}
    with patch.object(media_handler, "find_asset_by_logical_media_key",
                       return_value=MediaLookupResult("incomplete", record=traced_record)), \
         patch.object(media_handler, "record_id", return_value="recNEWTRACE"), \
         patch.object(media_handler, "record_fields", return_value=traced_record["fields"]), \
         patch.object(drive_adapter, "_get_upload_folder", return_value="folder123"), \
         patch.object(drive_adapter, "find_existing_by_logical_media_key",
                       return_value=drive_adapter.DriveFile(
                           file_id="driveF2", web_url="https://drive/y", name="x.pdf", size_bytes=1024
                       )), \
         patch.object(media_handler, "save_asset") as mock_save, \
         patch.object(media_handler, "update_asset_persistence", return_value=True) as mock_update:
        result = media_handler.handle_file_upload(**_upload_kwargs("f-m3-retry"))

    assert result.ok and result.asset_id == "recNEWTRACE"
    mock_update.assert_called_once()
    assert mock_update.call_args.args[0] == "recNEWTRACE"
    assert mock_update.call_args.kwargs["state"] == MediaPersistenceState.ASSET_PERSISTED
    mock_save.assert_not_called()
    print("✅ retry finds the durable trace by logical_media_key and reconciles it — no duplicate record created")


if __name__ == "__main__":
    test_reservation_id_present_keeps_update_behavior_unchanged()
    test_no_reservation_id_fresh_upload_creates_durable_trace()
    test_no_reservation_id_reused_drive_object_creates_durable_trace()
    test_retry_reconciles_against_durable_trace_without_duplicating()
    print("test_f16_m3_durable_trace.py self-test OK")
