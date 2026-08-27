from types import SimpleNamespace
from unittest.mock import patch

import core.lead_buffer as lead_buffer


def _identity():
    return SimpleNamespace(memory_key="email:sender@example.com")


def test_recovery_uses_structured_record_id():
    lead_buffer.clear_buffer()
    lead_buffer.save_blocked_payload({"Name": "Dana"})
    with patch("tools.airtable_read_adapter.list_records", return_value=[{"id": "recSTRUCT", "fields": {}}]), \
         patch("tools.airtable_tools.airtable_get", side_effect=AssertionError("display lookup")), \
         patch("tools.airtable_gateway.airtable_patch") as patch_lead:
        assert lead_buffer.recover_blocked_lead_payload(_identity()) is True
    assert patch_lead.call_args.args[1] == "recSTRUCT"


def test_recovery_display_text_cannot_create_false_match():
    lead_buffer.clear_buffer()
    lead_buffer.save_blocked_payload({"Name": "Dana"})
    with patch("tools.airtable_read_adapter.list_records", return_value=[]), \
         patch("tools.airtable_tools.airtable_get", return_value="✅ נמצא | ID: recFAKE"):
        assert lead_buffer.recover_blocked_lead_payload(_identity()) is False


def test_recovery_missing_structured_identity_fails_closed():
    lead_buffer.clear_buffer()
    lead_buffer.save_blocked_payload({"Name": "Dana"})
    with patch("tools.airtable_read_adapter.list_records", return_value=[{"fields": {}}]), \
         patch("tools.airtable_tools.airtable_get", side_effect=AssertionError("display fallback")):
        assert lead_buffer.recover_blocked_lead_payload(_identity()) is False


def test_recovery_normal_missing_lead_behavior_remains_false():
    lead_buffer.clear_buffer()
    assert lead_buffer.recover_blocked_lead_payload(_identity()) is False
