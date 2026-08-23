"""Focused regression tests for Track F #15 Finding A."""

from unittest.mock import patch

import drive_adapter
import media_handler
from guards.idempotency import IdempotencyStore
from media_gateway import MediaLookupResult


def _missing_drive() -> drive_adapter.DriveFile:
    return drive_adapter.DriveFile(
        error=drive_adapter.MediaError("DRIVE_NOT_FOUND", "", False)
    )


def _upload_kwargs() -> tuple:
    return (b"payload", "test.pdf", "application/pdf", "document", "file-1", "user-1", "general")


def test_active_duplicate_is_blocked_and_success_remains_suppressed():
    store = IdempotencyStore()

    assert store.is_duplicate("media", "key-1", "") is False
    assert store.is_duplicate("media", "key-1", "") is True

    successful = IdempotencyStore()
    assert successful.is_duplicate("media", "key-2", "") is False
    assert successful.is_duplicate("media", "key-2", "") is True


def test_drive_failure_releases_reservation_for_immediate_retry():
    store = IdempotencyStore()
    failed = drive_adapter.DriveFile(
        error=drive_adapter.MediaError("UPLOAD_FAILED", "temporary", True)
    )
    uploaded = drive_adapter.DriveFile(
        file_id="drive-1", web_url="https://drive.test/1", name="test.pdf"
    )

    with patch.object(media_handler, "_idem_store", store), \
         patch.object(media_handler, "_resolve_drive_folder", return_value=("folder", None)), \
         patch.object(media_handler, "find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")), \
         patch.object(media_handler.drive_adapter, "find_existing_by_logical_media_key", return_value=_missing_drive()), \
         patch.object(media_handler, "save_asset", return_value="asset-1"), \
         patch.object(media_handler, "update_asset_persistence", return_value=True), \
         patch.object(media_handler.drive_adapter, "upload_file", side_effect=[failed, uploaded]):
        first = media_handler.handle_file_upload(*_upload_kwargs())
        second = media_handler.handle_file_upload(*_upload_kwargs())

    assert not first.ok and first.error.error_code == "UPLOAD_FAILED"
    assert second.ok and second.asset_id == "asset-1"


def test_asset_persistence_failure_releases_reservation_for_immediate_retry():
    store = IdempotencyStore()
    uploaded = drive_adapter.DriveFile(
        file_id="drive-1", web_url="https://drive.test/1", name="test.pdf"
    )

    with patch.object(media_handler, "_idem_store", store), \
         patch.object(media_handler, "_resolve_drive_folder", return_value=("folder", None)), \
         patch.object(media_handler, "find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")), \
         patch.object(media_handler.drive_adapter, "find_existing_by_logical_media_key", return_value=_missing_drive()), \
         patch.object(media_handler, "save_asset", return_value="asset-1"), \
         patch.object(media_handler, "update_asset_persistence", side_effect=[True, False, True, True, True]), \
         patch.object(media_handler.drive_adapter, "upload_file", side_effect=[uploaded, uploaded]):
        first = media_handler.handle_file_upload(*_upload_kwargs())
        second = media_handler.handle_file_upload(*_upload_kwargs())

    assert not first.ok and first.error.error_code == "MEDIA_FILES_PARTIAL"
    assert second.ok and second.asset_id == "asset-1"
