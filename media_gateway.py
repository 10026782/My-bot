# media_gateway.py — F16 Media Layer: Airtable metadata persistence
#
# Thin wrapper over tools/airtable_gateway.airtable_create() for the
# "Media Files" table. All writes go through the gateway — never call
# httpx directly here.

from __future__ import annotations

import logging
from dataclasses import dataclass

from airtable_schema import MediaFileFields, MediaPersistenceState, Tables
from tools.airtable_gateway import (
    AirtableLookupError,
    escape_formula_value,
    at_list_by_formula,
    airtable_create,
    airtable_patch,
)

logger = logging.getLogger(__name__)


@dataclass
class AssetRecord:
    name: str
    file_type: str          # image / document / audio / video
    mime_type: str
    drive_url: str
    drive_file_id: str
    domain: str
    source: str              # telegram / tma / whatsapp
    size_bytes: int
    created_by: str
    telegram_file_id: str = ""
    linked_lead_id: str = ""
    raw_transcript: str = ""
    normalized_transcript: str = ""
    logical_media_key: str = ""
    persistence_state: str = ""
    last_error_code: str = ""


@dataclass(frozen=True)
class MediaLookupResult:
    status: str  # not_found | incomplete | reusable | duplicate | error
    record: dict | None = None
    error: str = ""


def _asset_to_fields(asset: AssetRecord) -> dict:
    fields: dict = {
        MediaFileFields.NAME: asset.name,
        MediaFileFields.FILE_TYPE: asset.file_type,
        MediaFileFields.MIME_TYPE: asset.mime_type,
        MediaFileFields.DRIVE_URL: asset.drive_url,
        MediaFileFields.DRIVE_FILE_ID: asset.drive_file_id,
        MediaFileFields.DOMAIN: asset.domain,
        MediaFileFields.SOURCE: asset.source,
        MediaFileFields.SIZE_BYTES: asset.size_bytes,
        MediaFileFields.CREATED_BY: asset.created_by,
    }
    if asset.telegram_file_id:
        fields[MediaFileFields.TELEGRAM_FILE_ID] = asset.telegram_file_id
    if asset.linked_lead_id:
        fields[MediaFileFields.LINKED_LEAD] = [asset.linked_lead_id]
    if asset.raw_transcript:
        fields[MediaFileFields.RAW_TRANSCRIPT] = asset.raw_transcript
    if asset.normalized_transcript:
        fields[MediaFileFields.NORMALIZED_TRANSCRIPT] = asset.normalized_transcript
    if asset.logical_media_key:
        fields[MediaFileFields.LOGICAL_MEDIA_KEY] = asset.logical_media_key
    if asset.persistence_state:
        fields[MediaFileFields.PERSISTENCE_STATE] = asset.persistence_state
    if asset.last_error_code:
        fields[MediaFileFields.LAST_ERROR_CODE] = asset.last_error_code
    return fields


def find_asset_by_logical_media_key(logical_media_key: str) -> MediaLookupResult:
    """Read exact-key Media Files matches; never infer identity from names."""
    if not logical_media_key:
        return MediaLookupResult("not_found")
    formula = (
        f"{{{MediaFileFields.LOGICAL_MEDIA_KEY}}}="
        f"'{escape_formula_value(logical_media_key)}'"
    )
    try:
        records = at_list_by_formula(Tables.MEDIA_FILES, formula, max_records=100)
    except AirtableLookupError as exc:
        return MediaLookupResult("error", error=str(exc))
    if len(records) > 1:
        return MediaLookupResult("duplicate", error="duplicate logical media key")
    if not records:
        return MediaLookupResult("not_found")
    fields = records[0].get("fields", {})
    if not fields.get(MediaFileFields.DRIVE_FILE_ID):
        return MediaLookupResult("incomplete", record=records[0])
    if fields.get(MediaFileFields.PERSISTENCE_STATE) and fields.get(
        MediaFileFields.PERSISTENCE_STATE
    ) != MediaPersistenceState.ASSET_PERSISTED:
        return MediaLookupResult("incomplete", record=records[0])
    return MediaLookupResult("reusable", record=records[0])


def save_asset(asset: AssetRecord) -> str | None:
    """
    Persists an AssetRecord to the "Media Files" table via the single
    Airtable write gateway. Returns the new record id, or None on failure.
    """
    fields = _asset_to_fields(asset)
    record = airtable_create(Tables.MEDIA_FILES, fields, source="media_gateway")
    if not record:
        logger.warning("[media_gateway] save_asset failed for name=%s", asset.name)
        return None
    return record.get("id")


def update_asset_persistence(
    record_id: str,
    *,
    state: str,
    drive_file_id: str = "",
    drive_url: str = "",
    last_error_code: str = "",
) -> bool:
    """Advance one Media Files record through the durable persistence lifecycle."""
    fields = {
        MediaFileFields.PERSISTENCE_STATE: state,
        MediaFileFields.LAST_ERROR_CODE: last_error_code,
    }
    if drive_file_id:
        fields[MediaFileFields.DRIVE_FILE_ID] = drive_file_id
    if drive_url:
        fields[MediaFileFields.DRIVE_URL] = drive_url
    return airtable_patch(Tables.MEDIA_FILES, record_id, fields, source="media_gateway")


if __name__ == "__main__":
    sample = AssetRecord(
        name="test.mp3",
        file_type="audio",
        mime_type="audio/mpeg",
        drive_url="https://drive.google.com/uc?id=abc",
        drive_file_id="abc",
        domain="general",
        source="telegram",
        size_bytes=1234,
        created_by="tester",
    )
    fields = _asset_to_fields(sample)
    assert fields[MediaFileFields.NAME] == "test.mp3"
    assert MediaFileFields.LINKED_LEAD not in fields
    assert MediaFileFields.RAW_TRANSCRIPT not in fields

    sample_with_lead = AssetRecord(
        name="voice.ogg",
        file_type="audio",
        mime_type="audio/ogg",
        drive_url="https://drive.google.com/uc?id=def",
        drive_file_id="def",
        domain="real_estate",
        source="telegram",
        size_bytes=4321,
        created_by="tester",
        linked_lead_id="recABC123",
        raw_transcript="שָׁלוֹם",
        normalized_transcript="שלום",
    )
    fields2 = _asset_to_fields(sample_with_lead)
    assert fields2[MediaFileFields.LINKED_LEAD] == ["recABC123"]
    assert fields2[MediaFileFields.RAW_TRANSCRIPT] == "שָׁלוֹם"
    assert fields2[MediaFileFields.NORMALIZED_TRANSCRIPT] == "שלום"

    print("media_gateway.py self-test OK")
