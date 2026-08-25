"""Focused Audit #3 I3 regressions for provider-specific media IDs."""

from unittest.mock import patch

import drive_adapter
import media_handler
from airtable_schema import MediaFileFields
from media_gateway import AssetRecord, MediaLookupResult, _asset_to_fields


def test_telegram_keeps_compatibility_id_and_logical_key():
    fields = _asset_to_fields(AssetRecord(
        name="x.jpg", file_type="image", mime_type="image/jpeg",
        drive_url="https://drive/x", drive_file_id="drive-x", domain="general",
        source="telegram", size_bytes=1, created_by="u",
        provider_media_id="telegram-file-1", logical_media_key="telegram:telegram-file-1",
    ))

    assert fields[MediaFileFields.TELEGRAM_FILE_ID] == "telegram-file-1"
    assert fields[MediaFileFields.LOGICAL_MEDIA_KEY] == "telegram:telegram-file-1"


def test_non_telegram_ids_are_logical_only_at_gateway_boundary():
    for source, provider_id, logical_key in (
        ("whatsapp", "twilio-message-1", "twilio:twilio-message-1"),
        ("whatsapp_meta", "meta-media-1", "meta:meta-media-1"),
        ("tma", "ignored", "tma:sha256:key"),
    ):
        fields = _asset_to_fields(AssetRecord(
            name="x.jpg", file_type="image", mime_type="image/jpeg",
            drive_url="https://drive/x", drive_file_id="drive-x", domain="general",
            source=source, size_bytes=1, created_by="u",
            provider_media_id=provider_id, logical_media_key=logical_key,
        ))

        assert fields[MediaFileFields.LOGICAL_MEDIA_KEY] == logical_key
        assert MediaFileFields.TELEGRAM_FILE_ID not in fields


def test_handler_passes_provider_neutral_id_and_does_not_dual_write():
    saved_assets = []
    drive = drive_adapter.DriveFile(
        file_id="drive-1", web_url="https://drive/x", name="x.jpg"
    )

    def capture_save(asset):
        saved_assets.append(asset)
        return "rec-1"

    with patch("media_handler._idem_store.is_duplicate", return_value=False), \
         patch("media_handler._resolve_drive_folder", return_value=("folder", None)), \
         patch("media_handler.find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")), \
         patch("media_handler.drive_adapter.find_existing_by_logical_media_key", return_value=drive_adapter.DriveFile(
             error=drive_adapter.MediaError("DRIVE_NOT_FOUND", "", False)
         )), \
         patch("media_handler.drive_adapter.upload_file", return_value=drive), \
         patch("media_handler.save_asset", side_effect=capture_save), \
         patch("media_handler.update_asset_persistence", return_value=True):
        result = media_handler.handle_file_upload(
            b"data", "x.jpg", "image/jpeg", "image", "twilio-message-1",
            "u", "general", source="whatsapp",
        )

    assert result.ok
    assert len(saved_assets) == 1
    assert saved_assets[0].provider_media_id == "twilio-message-1"
    assert saved_assets[0].logical_media_key == "twilio:twilio-message-1"
    persisted = _asset_to_fields(saved_assets[0])
    assert MediaFileFields.TELEGRAM_FILE_ID not in persisted
    assert persisted[MediaFileFields.LOGICAL_MEDIA_KEY] == "twilio:twilio-message-1"
