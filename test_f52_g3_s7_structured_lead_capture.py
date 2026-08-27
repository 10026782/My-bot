from types import SimpleNamespace
from unittest.mock import patch

from core.lead_service import LeadCreateResult


def _identity():
    return SimpleNamespace(
        display_name="Lead", external_id="+972500000000", channel="whatsapp",
        memory_key="boss_hq:+972500000000", domain_id="general",
    )


def test_structured_record_id_is_authoritative():
    import lead_capture

    with patch.object(lead_capture, "is_enabled", return_value=True), \
         patch("tools.airtable_read_adapter.list_records", return_value=[
             {"id": "recSTRUCTURED", "fields": {"Name": "✅ no record here"}},
         ]), \
         patch.object(lead_capture, "create_lead") as create:
        result = lead_capture.capture_inbound_lead(_identity(), "need a quote", write_event=False)

    assert result.business_success
    assert result.record_id == "recSTRUCTURED"
    assert not create.called


def test_display_text_change_does_not_change_business_outcome():
    import lead_capture

    with patch.object(lead_capture, "is_enabled", return_value=True), \
         patch("tools.airtable_read_adapter.list_records", return_value=[
             {"id": "recKNOWN", "fields": {"Name": "changed display"}},
         ]):
        result = lead_capture.capture_inbound_lead(_identity(), "hello", write_event=False)

    assert result.business_success
    assert result.record_id == "recKNOWN"


def test_misleading_success_text_cannot_create_false_success():
    import lead_capture

    with patch.object(lead_capture, "is_enabled", return_value=True), \
         patch("tools.airtable_read_adapter.list_records", return_value=[
             {"fields": {"Name": "✅ saved"}},
         ]), \
         patch.object(lead_capture, "create_lead") as create:
        result = lead_capture.capture_inbound_lead(_identity(), "hello", write_event=False)

    assert not result.business_success
    assert result.fatal_error == "missing_structured_record_id"
    assert not create.called


def test_missing_structured_lookup_fails_safely():
    import lead_capture

    with patch.object(lead_capture, "is_enabled", return_value=True), \
         patch("tools.airtable_read_adapter.list_records", return_value=None), \
         patch.object(lead_capture, "create_lead") as create:
        result = lead_capture.capture_inbound_lead(_identity(), "hello", write_event=False)

    assert not result.business_success
    assert result.fatal_error == "malformed_structured_lookup"
    assert not create.called


def test_new_lead_behavior_remains_unchanged():
    import lead_capture

    created = LeadCreateResult(ok=True, action="created", record_id="recNEW", domain="general")
    with patch.object(lead_capture, "is_enabled", return_value=True), \
         patch("tools.airtable_read_adapter.list_records", return_value=[]), \
         patch.object(lead_capture, "create_lead", return_value=created) as create:
        result = lead_capture.capture_inbound_lead(_identity(), "need a quote", write_event=False)

    assert result.business_success
    assert result.record_id == "recNEW"
    create.assert_called_once()
