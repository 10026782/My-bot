# media_gateway.py — F16 Media Layer: Airtable metadata persistence
#
# Thin wrapper over tools/airtable_gateway.airtable_create() for the
# "Media Files" table. All writes go through the gateway — never call
# httpx directly here.

from __future__ import annotations

import logging
from dataclasses import dataclass

from airtable_schema import MediaFileFields, Tables
from tools.airtable_gateway import airtable_create

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
    return fields


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
