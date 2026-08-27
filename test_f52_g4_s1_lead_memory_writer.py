from unittest.mock import patch

from core.action_gateway import APPROVAL_POLICY_SELF_CONFIRM, classify_approval_policy
from core.lead_service import LeadCreateResult
from lead_memory import LeadMemory


def test_scheduler_writer_uses_explicit_system_identity_and_structured_result():
    memory = LeadMemory(save_every=1)
    memory.update("tenant-a:lead-1", record_id="recLEAD1", score=42, domain="import")
    result = LeadCreateResult(
        ok=True, action="updated", record_id="recLEAD1",
        evidence={"contract_id": "contract-1", "mutation_executed": True},
    )
    with patch("core.lead_service.update_lead_fields", return_value=result) as update:
        assert memory.flush("tenant-a:lead-1") is True

    identity, record_id, fields = update.call_args.args
    assert identity.user_id == "lead_memory_scheduler"
    assert identity.role == "manager"
    assert identity.tenant_id == "tenant-a"
    assert identity.channel == "scheduler"
    assert record_id == "recLEAD1"
    assert fields["Score"] == 42
    assert update.call_args.kwargs["source_module"] == "lead_memory_scheduler"


def test_scheduler_policy_is_exact_and_structured_failure_stays_failed():
    inputs = {
        "table": "Leads", "record_id": "recLEAD2",
        "fields": {"memory_key": "tenant-a:lead-2", "Score": 1},
    }
    assert classify_approval_policy(
        "airtable_update", inputs, "lead_memory_scheduler"
    ) == APPROVAL_POLICY_SELF_CONFIRM

    memory = LeadMemory(save_every=1)
    memory.update("tenant-a:lead-2", record_id="recLEAD2", score=1)
    failure = LeadCreateResult(
        ok=False, action="write_failed", record_id="recLEAD2",
        evidence={"mutation_executed": False},
    )
    with patch("core.lead_service.update_lead_fields", return_value=failure) as update:
        assert memory.flush("tenant-a:lead-2") is False
        assert memory.get("tenant-a:lead-2").dirty is True
        update.assert_called_once()


def test_successful_flush_clears_dirty_state_and_does_not_repeat():
    memory = LeadMemory(save_every=1)
    memory.update("tenant-a:lead-3", record_id="recLEAD3", score=3)
    result = LeadCreateResult(ok=True, action="updated", record_id="recLEAD3")
    with patch("core.lead_service.update_lead_fields", return_value=result) as update:
        assert memory.flush("tenant-a:lead-3") is True
        assert memory.save("tenant-a:lead-3") is True
    update.assert_called_once()
