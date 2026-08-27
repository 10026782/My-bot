"""Audit #3 Finding #1: LeadMemory is post-write enrichment only."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.lead_service import LeadPayload, _run_post_write_enrichment
from lead_memory import LeadMemory


def _flush_with_patches(*, record_id="", lookup="", **kwargs):
    memory = LeadMemory(save_every=1)
    memory.update(
        "tenant/lead@example.com", record_id=record_id,
        score=kwargs.pop("score", 42), domain="import", channel="whatsapp",
        contact_name="Dana", summary="qualified", **kwargs,
    )
    updated = Mock(return_value={"ok": True})
    added = Mock(side_effect=AssertionError("LeadMemory must not create Leads"))
    records = [{"id": lookup.split()[-1]}] if lookup.startswith("existing ") else []
    with patch("tools.airtable_tools.airtable_get_records", return_value=records) as get, \
         patch("tools.airtable_tools.airtable_update", updated), \
         patch("tools.airtable_tools.airtable_add", added):
        result = memory.flush("tenant/lead@example.com")
    return result, memory, get, updated, added


def test_record_id_updates_existing_lead_without_lookup_or_create():
    result, memory, get, updated, added = _flush_with_patches(record_id="recKNOWN123")

    assert result is True
    get.assert_not_called()
    added.assert_not_called()
    updated.assert_called_once()
    assert updated.call_args.args[1] == "recKNOWN123"
    fields = updated.call_args.args[2]
    assert fields["memory_key"] == "tenant/lead@example.com"
    assert fields["Score"] == 42
    assert fields["domain"] == "import"
    assert fields["channel"] == "whatsapp"
    assert "status" not in fields
    assert "Owner" not in fields
    assert memory.get("tenant/lead@example.com").record_id == "recKNOWN123"


def test_memory_key_match_updates_existing_lead_without_create():
    result, memory, get, updated, added = _flush_with_patches(lookup="existing recMATCH456")

    assert result is True
    get.assert_called_once()
    added.assert_not_called()
    assert updated.call_args.args[1] == "recMATCH456"
    assert memory.get("tenant/lead@example.com").record_id == "recMATCH456"


def test_missing_memory_key_match_is_bounded_noop_and_never_creates():
    result, memory, get, updated, added = _flush_with_patches(lookup="no-match")

    assert result is False
    get.assert_called_once()
    updated.assert_not_called()
    added.assert_not_called()
    assert memory.get("tenant/lead@example.com").record_id == ""


def test_lead_memory_source_has_no_airtable_create_path():
    source = open("lead_memory.py", encoding="utf-8").read()
    assert "airtable_add" not in source
    assert "airtable_create" not in source


def test_lead_service_passes_canonical_record_id_to_memory():
    payload = LeadPayload(
        name="Dana", phone="0501234567", domain="import",
        channel="whatsapp", summary="qualified", tenant_id="boss_hq",
    )
    update = Mock()
    identity = SimpleNamespace(user_id="owner-1")
    with patch("feature_flags.is_enabled", side_effect=lambda flag: flag == "LEAD_MEMORY"), \
         patch("lead_memory.lead_memory.update", update):
        _run_post_write_enrichment(identity, payload, "recPOST789", "created", write_event=False)

    assert update.call_args.kwargs["record_id"] == "recPOST789"
