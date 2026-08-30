from unittest.mock import patch

import drive_adapter
import media_handler
from airtable_schema import MediaFileFields, MediaPersistenceState
from media_gateway import MediaLookupResult


def _missing_drive():
    return drive_adapter.DriveFile(
        error=drive_adapter.MediaError("DRIVE_NOT_FOUND", "", False)
    )


def _drive():
    return drive_adapter.DriveFile(
        file_id="drive1", web_url="https://drive/x", name="x.pdf"
    )


def _base_patches():
    return (
        patch("media_handler._idem_store.is_duplicate", return_value=False),
        patch("media_handler._resolve_drive_folder", return_value=("folder", None)),
        patch("media_handler.find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")),
        patch("media_handler.drive_adapter.find_existing_by_logical_media_key", return_value=_missing_drive()),
    )


def _upload_kwargs():
    return (b"data", "x.pdf", "application/pdf", "document", "f1", "u1", "general")


def test_fresh_ingestion_writes_pending_drive_uploaded_then_persisted():
    patches = _base_patches()
    with patches[0], patches[1], patches[2], patches[3], patch(
        "media_handler.save_asset", return_value="rec1"
    ) as save, patch(
        "media_handler.drive_adapter.upload_file", return_value=_drive()
    ), patch(
        "media_handler.update_asset_persistence", return_value=True
    ) as update:
        result = media_handler.handle_file_upload(*_upload_kwargs())

    assert result.ok
    assert save.call_args_list[0].args[0].persistence_state == MediaPersistenceState.PENDING
    assert [call.kwargs["state"] for call in update.call_args_list] == [
        MediaPersistenceState.DRIVE_UPLOADED,
        MediaPersistenceState.ASSET_PERSISTED,
    ]


def test_final_persistence_failure_returns_partial_and_retry_reconciles_without_upload():
    patches = _base_patches()
    with patches[0], patches[1], patches[2], patches[3], patch(
        "media_handler.save_asset", return_value="rec1"
    ), patch(
        "media_handler.drive_adapter.upload_file", return_value=_drive()
    ) as upload, patch(
        "media_handler.update_asset_persistence", side_effect=[True, False, True]
    ):
        first = media_handler.handle_file_upload(*_upload_kwargs())

    assert not first.ok
    assert first.error.error_code == "MEDIA_FILES_PARTIAL"
    upload.assert_called_once()

    incomplete = {
        "id": "rec1",
        "fields": {
            MediaFileFields.LOGICAL_MEDIA_KEY: "telegram:f1",
            MediaFileFields.PERSISTENCE_STATE: MediaPersistenceState.DRIVE_UPLOADED,
            MediaFileFields.DRIVE_FILE_ID: "drive1",
        },
    }
    with patch("media_handler._idem_store.is_duplicate", return_value=False), patch(
        "media_handler._resolve_drive_folder", return_value=("folder", None)
    ), patch(
        "media_handler.find_asset_by_logical_media_key",
        return_value=MediaLookupResult("incomplete", record=incomplete),
    ), patch(
        "media_handler.drive_adapter.find_existing_by_logical_media_key", return_value=_drive()
    ), patch(
        "media_handler.drive_adapter.upload_file"
    ) as retry_upload, patch(
        "media_handler.update_asset_persistence", return_value=True
    ) as reconcile:
        retry = media_handler.handle_file_upload(*_upload_kwargs())

    assert retry.ok and retry.asset_id == "rec1"
    retry_upload.assert_not_called()
    assert reconcile.call_args.kwargs["state"] == MediaPersistenceState.ASSET_PERSISTED


def test_drive_app_property_match_creates_and_completes_media_record_without_upload():
    with patch("media_handler._idem_store.is_duplicate", return_value=False), patch(
        "media_handler._resolve_drive_folder", return_value=("folder", None)
    ), patch(
        "media_handler.find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")
    ), patch(
        "media_handler.drive_adapter.find_existing_by_logical_media_key", return_value=_drive()
    ), patch(
        "media_handler.save_asset", return_value="rec1"
    ) as save, patch(
        "media_handler.update_asset_persistence", return_value=True
    ) as update, patch(
        "media_handler.drive_adapter.upload_file"
    ) as upload:
        result = media_handler.handle_file_upload(*_upload_kwargs())

    assert result.ok and result.asset_id == "rec1"
    upload.assert_not_called()
    assert save.call_args.args[0].persistence_state == MediaPersistenceState.DRIVE_UPLOADED
    assert update.call_args.kwargs["state"] == MediaPersistenceState.ASSET_PERSISTED


def test_multiple_drive_matches_fail_closed_without_upload():
    duplicate = drive_adapter.DriveFile(
        error=drive_adapter.MediaError("DRIVE_DUPLICATE_KEY", "duplicate", False)
    )
    with patch("media_handler._idem_store.is_duplicate", return_value=False), patch(
        "media_handler._resolve_drive_folder", return_value=("folder", None)
    ), patch(
        "media_handler.find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")
    ), patch(
        "media_handler.drive_adapter.find_existing_by_logical_media_key", return_value=duplicate
    ), patch("media_handler.drive_adapter.upload_file") as upload:
        result = media_handler.handle_file_upload(*_upload_kwargs())

    assert not result.ok
    assert result.error.error_code == "DRIVE_DUPLICATE_KEY"
    upload.assert_not_called()


def test_pending_creation_failure_recovers_tagged_drive_on_retry():
    drive = _drive()
    with patch("media_handler._idem_store.is_duplicate", return_value=False), patch(
        "media_handler._resolve_drive_folder", return_value=("folder", None)
    ), patch(
        "media_handler.find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")
    ), patch(
        "media_handler.drive_adapter.find_existing_by_logical_media_key", return_value=_missing_drive()
    ), patch(
        "media_handler.save_asset", side_effect=[None, None, "recPARTIAL"]
    ) as first_save, patch(
        "media_handler.drive_adapter.upload_file", return_value=drive
    ) as first_upload:
        first = media_handler.handle_file_upload(*_upload_kwargs())

    assert not first.ok
    # PENDING save fails, DRIVE_UPLOADED save fails, then mark_partial()
    # (F16-M3) creates a durable PARTIAL trace record instead of losing the
    # failure evidence — this 3rd call is the fix, not a regression.
    assert first_save.call_count == 3
    assert first_save.call_args_list[2].args[0].persistence_state == MediaPersistenceState.PARTIAL
    assert first_upload.call_args.kwargs["logical_media_key"] == "telegram:f1"

    with patch("media_handler._idem_store.is_duplicate", return_value=False), patch(
        "media_handler._resolve_drive_folder", return_value=("folder", None)
    ), patch(
        "media_handler.find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")
    ), patch(
        "media_handler.drive_adapter.find_existing_by_logical_media_key", return_value=drive
    ), patch(
        "media_handler.save_asset", return_value="rec1"
    ) as retry_save, patch(
        "media_handler.update_asset_persistence", return_value=True
    ) as retry_update, patch(
        "media_handler.drive_adapter.upload_file"
    ) as retry_upload:
        retry = media_handler.handle_file_upload(*_upload_kwargs())

    assert retry.ok and retry.asset_id == "rec1"
    retry_save.assert_called_once()
    assert retry_save.call_args.args[0].persistence_state == MediaPersistenceState.DRIVE_UPLOADED
    assert retry_update.call_args.kwargs["state"] == MediaPersistenceState.ASSET_PERSISTED
    retry_upload.assert_not_called()
