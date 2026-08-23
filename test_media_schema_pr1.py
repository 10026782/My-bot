#!/usr/bin/env python3
"""PR1 foundation checks: constants only, with no runtime adoption."""

from airtable_schema import MediaFileFields, MediaPersistenceState
from media_gateway import AssetRecord, _asset_to_fields


def test_media_schema_constants_are_canonical_and_unique():
    expected_fields = {
        "LOGICAL_MEDIA_KEY": "Logical Media Key",
        "PERSISTENCE_STATE": "Persistence State",
        "LAST_ERROR_CODE": "Last Error Code",
    }
    for name, value in expected_fields.items():
        assert getattr(MediaFileFields, name) == value
        assert sum(v == value for v in vars(MediaFileFields).values()) == 1

    assert MediaPersistenceState.ALL == (
        "PENDING",
        "DRIVE_UPLOADED",
        "ASSET_PERSISTED",
        "PARTIAL",
        "FAILED",
    )
    assert set(MediaPersistenceState.ALL) == {
        MediaPersistenceState.PENDING,
        MediaPersistenceState.DRIVE_UPLOADED,
        MediaPersistenceState.ASSET_PERSISTED,
        MediaPersistenceState.PARTIAL,
        MediaPersistenceState.FAILED,
    }


def test_pr1_does_not_change_legacy_media_mapping():
    asset = AssetRecord(
        name="legacy.pdf",
        file_type="document",
        mime_type="application/pdf",
        drive_url="https://drive.google.com/uc?id=legacy",
        drive_file_id="legacy",
        domain="general",
        source="telegram",
        size_bytes=10,
        created_by="tester",
    )
    fields = _asset_to_fields(asset)
    assert MediaFileFields.DRIVE_FILE_ID in fields
    assert MediaFileFields.LOGICAL_MEDIA_KEY not in fields
    assert MediaFileFields.PERSISTENCE_STATE not in fields
    assert MediaFileFields.LAST_ERROR_CODE not in fields


if __name__ == "__main__":
    test_media_schema_constants_are_canonical_and_unique()
    test_pr1_does_not_change_legacy_media_mapping()
    print("media schema PR1 self-test OK")
