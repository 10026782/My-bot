"""Focused record-envelope checks for Provider Portability #1D."""

from pathlib import Path

from tma_api import record_fields, record_id


TARGETS = (
    "daily_digest.py",
    "scheduler.py",
    "decision_pipeline.py",
    "decision_matching.py",
    "core/lead_events.py",
    "core/memory_retrieval.py",
    "media_handler.py",
    "ad_attribution.py",
)


def test_scope_has_no_raw_provider_envelope_access():
    markers = ('["id"]', "['id']", '["fields"]', "['fields']", '.get("id"',
               ".get('id'", '.get("fields"', ".get('fields'")
    for path in TARGETS:
        source = Path(path).read_text(encoding="utf-8")
        assert not any(marker in source for marker in markers), path


def test_existing_record_helpers_preserve_envelope_compatibility():
    record = {"id": "rec-1", "fields": {"Status": "Open"}}
    assert record_id(record, required=True) == "rec-1"
    assert record_fields(record) == {"Status": "Open"}
    assert record_fields({}) == {}
    assert record_id({}) is None
