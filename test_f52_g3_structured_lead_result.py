"""F52-G3-S1: LeadMemory decisions use structured Airtable results only."""

from unittest.mock import Mock, patch

from lead_memory import LeadMemory, _write_success


def test_success_uses_structured_ok_not_display_text():
    assert _write_success({"ok": True, "user_message": "saved"}) is True


def test_success_marker_cannot_override_structured_failure():
    assert _write_success({"ok": False, "user_message": "✅ saved"}) is False


def test_write_uses_structured_record_id_not_rendered_text():
    memory = LeadMemory(save_every=1)
    memory.update("lead-1", record_id="", score=42)
    with patch(
        "tools.airtable_tools.airtable_get_records",
        return_value=[{"id": "recSTRUCTURED", "fields": {}}],
    ) as get, patch(
        "tools.airtable_gateway.airtable_patch",
        return_value={"ok": True, "external_id": "recSTRUCTURED", "user_message": "updated"},
    ) as update:
        assert memory.flush("lead-1") is True
    get.assert_called_once()
    assert update.call_args.args[1] == "recSTRUCTURED"


def test_missing_structured_result_fails_safely():
    assert _write_success({"user_message": "✅ saved"}) is False
    assert _write_success("✅ saved") is False


def test_existing_successful_flush_behavior_is_preserved():
    memory = LeadMemory(save_every=1)
    memory.update("lead-1", record_id="recKNOWN", score=42)
    update = Mock(return_value={"ok": True, "user_message": "changed wording"})
    with patch("tools.airtable_gateway.airtable_patch", update):
        assert memory.flush("lead-1") is True
    assert memory.get("lead-1").dirty is False
