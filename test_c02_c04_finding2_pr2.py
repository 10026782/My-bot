import hashlib
from unittest.mock import patch

import drive_adapter
import media_handler
from airtable_schema import MediaFileFields
from media_gateway import MediaLookupResult, find_asset_by_logical_media_key


def test_logical_keys_are_provider_scoped_and_deterministic():
    assert media_handler.logical_media_key("telegram", "f1") == "telegram:f1"
    assert media_handler.logical_media_key("telegram", "f1") == media_handler.logical_media_key("telegram", "f1")
    assert media_handler.logical_media_key("whatsapp", "m1") == "twilio:m1"
    assert media_handler.logical_media_key("whatsapp_meta", "m1") == "meta:m1"
    assert media_handler.logical_media_key("whatsapp", "m1") != media_handler.logical_media_key("whatsapp_meta", "m1")


def test_tma_key_hashes_full_file():
    first = b"a" * 1024 + b"one"
    second = b"a" * 1024 + b"two"
    assert media_handler.logical_media_key("tma", "ignored", first) == (
        "tma:sha256:" + hashlib.sha256(first).hexdigest()
    )
    assert media_handler.logical_media_key("tma", "ignored", first) != media_handler.logical_media_key(
        "tma", "ignored", second
    )


def test_media_lookup_reuses_one_exact_record():
    record = {"id": "rec1", "fields": {MediaFileFields.DRIVE_FILE_ID: "drive1"}}
    with patch("media_gateway.at_list_by_formula", return_value=[record]) as lookup:
        result = find_asset_by_logical_media_key("telegram:f1")
    assert result == MediaLookupResult("reusable", record=record)
    assert "Logical Media Key" in lookup.call_args.args[1]


def test_media_lookup_fails_closed_on_duplicates_and_ignores_legacy_rows():
    with patch("media_gateway.at_list_by_formula", return_value=[{"id": "a"}, {"id": "b"}]):
        assert find_asset_by_logical_media_key("telegram:f1").status == "duplicate"
    with patch("media_gateway.at_list_by_formula", return_value=[]):
        assert find_asset_by_logical_media_key("telegram:f1").status == "not_found"


def test_handler_reuses_media_record_without_drive_upload():
    record = {"id": "rec1", "fields": {"Drive File ID": "drive1", "Drive URL": "https://drive/x"}}
    with patch("media_handler._idem_store.is_duplicate", return_value=False), patch(
        "media_handler._resolve_drive_folder", return_value=("folder", None)), patch(
        "media_handler.find_asset_by_logical_media_key",
        return_value=MediaLookupResult("reusable", record=record),
    ), patch("media_handler.drive_adapter.upload_file") as upload:
        result = media_handler.handle_file_upload(
            b"data", "renamed.pdf", "application/pdf", "document", "f1", "u1", "general"
        )
    assert result.ok and result.asset_id == "rec1"
    upload.assert_not_called()


def test_handler_miss_falls_through_to_new_upload():
    drive = drive_adapter.DriveFile(file_id="drive1", web_url="https://drive/x", name="x.pdf")
    with patch("media_handler._idem_store.is_duplicate", return_value=False), patch(
        "media_handler._resolve_drive_folder", return_value=("folder", None)), patch(
        "media_handler.find_asset_by_logical_media_key", return_value=MediaLookupResult("not_found")
    ), patch("media_handler.drive_adapter.find_existing_by_logical_media_key", return_value=drive_adapter.DriveFile(
        error=drive_adapter.MediaError("DRIVE_NOT_FOUND", "", False)
    )), patch("media_handler.drive_adapter.upload_file", return_value=drive) as upload, patch(
        "media_handler.save_asset", return_value="rec1"
    ), patch(
        "media_handler.update_asset_persistence", return_value=True
    ):
        result = media_handler.handle_file_upload(
            b"data", "x.pdf", "application/pdf", "document", "f1", "u1", "general"
        )
    assert result.ok
    upload.assert_called_once()
    assert upload.call_args.kwargs["logical_media_key"] == "telegram:f1"


def test_filename_never_defines_logical_identity():
    assert media_handler.logical_media_key("telegram", "f1") == "telegram:f1"
    assert media_handler.logical_media_key("telegram", "f1") != media_handler.logical_media_key("telegram", "f2")


def test_drive_lookup_reuses_tagged_object_without_upload():
    response = type("Response", (), {
        "status_code": 200,
        "json": lambda self: {"files": [{
            "id": "drive1", "name": "x.pdf", "parents": ["folder"],
            "webViewLink": "https://drive/x",
            "appProperties": {"logical_media_key": "telegram:f1"},
        }]},
    })()
    with patch("drive_adapter.get_google_token", return_value="token"), patch(
        "drive_adapter.httpx.get", return_value=response
    ), patch("drive_adapter.upload_file") as upload:
        found = drive_adapter.find_existing_by_logical_media_key("telegram:f1", "folder")
    assert found.ok and found.file_id == "drive1"
    upload.assert_not_called()


def test_drive_lookup_miss_allows_upload_and_writes_app_property():
    response = type("Response", (), {"status_code": 200, "json": lambda self: {"files": []}})()
    with patch("drive_adapter.get_google_token", return_value="token"), patch(
        "drive_adapter.httpx.get", return_value=response
    ), patch("drive_adapter._upload_to_drive", return_value=drive_adapter.DriveFile(file_id="new")) as upload:
        result = drive_adapter.upload_file(b"data", "x.pdf", "application/pdf", "folder", "telegram:f1")
    assert result.ok
    upload.assert_called_once()
    assert upload.call_args.args[-1] == "telegram:f1"
