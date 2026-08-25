"""Focused checks for provider-neutral record access in Cluster #1."""

import pytest
from pathlib import Path

from action_validator import ActionAllowed, validate_action
from tma_api import record_fields, record_id


def test_record_view_preserves_id_and_fields():
    raw = {"id": "provider-42", "fields": {"Name": "Dana"}}
    assert record_id(raw, required=True) == "provider-42"
    assert record_fields(raw) == {"Name": "Dana"}


def test_record_view_preserves_missing_field_and_id_behavior():
    raw = {"id": "provider-42"}
    assert record_fields(raw) == {}
    assert record_id(raw) == "provider-42"
    with pytest.raises(KeyError):
        record_id({}, required=True)


def test_record_id_is_not_provider_prefix_validated():
    result = validate_action(
        "airtable_update",
        {"table": "Leads", "record_id": "provider-42", "fields": {"Name": "Dana"}},
    )
    assert isinstance(result, ActionAllowed)


def test_record_id_round_trips_without_rewriting():
    raw = {"id": "recExisting123", "fields": {"Status": "Open"}}
    assert record_id(raw, required=True) == "recExisting123"


@pytest.mark.parametrize("module", ("cmd_decision.py", "crm.py", "core/lead_service.py"))
def test_target_business_modules_do_not_parse_provider_envelopes(module):
    source = Path(module).read_text(encoding="utf-8")
    for marker in ('["id"]', "['id']", '["fields"]', "['fields']", '.get("fields"', ".get('fields'"):
        assert marker not in source, f"{module} still contains raw envelope access: {marker}"
