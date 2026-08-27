"""N18 Phase 3 Slice 1: approved Telegram Lead previews use create_lead()."""

from dataclasses import dataclass
from unittest.mock import patch

import core.lead_candidate_handler as lch
from core.action_gateway import ActionGateway, ExecutionLedger, _make_dispatch_executor
from core.lead_service import LeadCreateResult


@dataclass
class Identity:
    user_id: str = "owner_1"
    role: str = "owner"
    tenant_id: str = "boss_hq"
    domain_id: str = "general"
    external_id: str = "tg_owner_1"

    @property
    def memory_key(self):
        return f"{self.tenant_id}:{self.user_id}"

    @property
    def is_internal(self):
        return True


def _gateway():
    ledger = ExecutionLedger()
    return ActionGateway(ledger=ledger, tool_executor=_make_dispatch_executor(ledger))


def _result(ok=True, action="created", record_id="recXOW7FBZQZcNdw1", reason=""):
    return LeadCreateResult(
        ok=ok, action=action, record_id=record_id if ok else "", reason=reason,
        domain="recruitment", owner_user_id="owner_1",
    )


def _propose(gw, identity):
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("tma_api._resolve_profile_record_id", return_value="recOwner1"), \
         patch("feature_flags.is_enabled", return_value=False), \
         patch("core.action_gateway.action_gateway", gw):
        lch.handle_lead_candidate(
            identity, "משה כהן 0501234567", "n18-chat", "telegram",
            domain="recruitment",
        )
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 1
    return live[0]


def test_approved_preview_calls_canonical_writer_once_and_never_dispatches_leads():
    identity = Identity()
    gw = _gateway()
    calls = []
    with patch("core.lead_service.create_lead", side_effect=lambda *a, **kw: calls.append((a, kw)) or _result()), \
         patch("tools.dispatcher.dispatch_tool", side_effect=AssertionError("legacy Leads dispatcher reached")), \
         patch("tools.airtable_gateway.airtable_create", side_effect=AssertionError("direct create reached")), \
         patch("tools.airtable_gateway.airtable_patch", side_effect=AssertionError("direct patch reached")):
        contract = _propose(gw, identity)
        reply = gw.route_confirmation_word(identity.memory_key, approver_role=identity.role)

    assert "הפעולה הושלמה" in reply
    assert len(calls) == 1
    assert calls[0][1]["manage_action_contract"] is False
    assert contract.status == "executed"


def test_canonical_failure_marks_outer_contract_failed_without_fallback():
    identity = Identity()
    gw = _gateway()
    with patch("core.lead_service.create_lead", return_value=_result(False, action="invalid", reason="owner failure")), \
         patch("tools.dispatcher.dispatch_tool", side_effect=AssertionError("legacy fallback reached")):
        contract = _propose(gw, identity)
        reply = gw.route_confirmation_word(identity.memory_key, approver_role=identity.role)

    assert "לא הושלמה" in reply or "נכשל" in reply
    assert contract.status == "failed"


def test_duplicate_approval_executes_canonical_writer_once():
    identity = Identity()
    gw = _gateway()
    calls = []
    with patch("core.lead_service.create_lead", side_effect=lambda *a, **kw: calls.append(1) or _result()), \
         patch("tools.dispatcher.dispatch_tool", side_effect=AssertionError("legacy Leads dispatcher reached")):
        _propose(gw, identity)
        gw.route_confirmation_word(identity.memory_key, approver_role=identity.role)
        gw.route_confirmation_word(identity.memory_key, approver_role=identity.role)

    assert calls == [1]


def test_existing_preview_uses_canonical_update_with_one_write():
    identity = Identity()
    gw = _gateway()
    seen = []
    with patch.object(lch, "_at_find_lead", return_value="recExisting123456"), \
         patch("tma_api._resolve_profile_record_id", return_value="recOwner1"), \
         patch("feature_flags.is_enabled", return_value=False), \
         patch("tools.airtable_gateway.at_list_by_formula", return_value=[{"fields": {"Name": "משה כהן"}}]), \
         patch("core.lead_service.create_lead", side_effect=lambda ident, payload, **kw: seen.append((payload, kw)) or _result(action="updated")), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("tools.dispatcher.dispatch_tool", side_effect=AssertionError("legacy Leads dispatcher reached")):
        lch._propose_lead_write(identity, "משה כהן", "0501234567", "עודכן", "telegram", "recruitment")
        contract = gw.find_live_contracts(identity.memory_key)
        assert len(contract) == 1
        gw.route_confirmation_word(identity.memory_key, approver_role=identity.role)

    assert len(seen) == 1
    assert seen[0][0].name == "משה כהן"
    assert seen[0][1]["existing_id"] == "recExisting123456"
    assert seen[0][1]["manage_action_contract"] is False


def test_preview_preserves_explicit_domain_and_owner_failure():
    identity = Identity()
    gw = _gateway()
    seen = []
    with patch("core.lead_service.create_lead", side_effect=lambda ident, payload, **kw: seen.append(payload) or _result()), \
         patch("tools.dispatcher.dispatch_tool", side_effect=AssertionError("legacy Leads dispatcher reached")):
        contract = _propose(gw, identity)
        gw.route_confirmation_word(identity.memory_key, approver_role=identity.role)

    assert seen[0].domain == "recruitment"
    assert seen[0].name == "משה כהן"

    gw2 = _gateway()
    with patch("core.lead_service.create_lead", return_value=_result(False, action="invalid", reason="owner_user_id missing")), \
         patch("tools.dispatcher.dispatch_tool", side_effect=AssertionError("legacy fallback reached")):
        contract2 = _propose(gw2, identity)
        gw2.route_confirmation_word(identity.memory_key, approver_role=identity.role)

    assert contract2.status == "failed"


def test_owner_failure_is_canonical_and_does_not_persist():
    identity = Identity()
    gw = _gateway()
    with patch("tma_api._resolve_profile_record_id", return_value=None), \
         patch("core.lead_service.find_existing_lead", return_value=None), \
         patch("feature_flags.is_enabled", return_value=False), \
         patch("tools.dispatcher.dispatch_tool", side_effect=AssertionError("legacy fallback reached")), \
         patch("tools.airtable_gateway.airtable_create", side_effect=AssertionError("direct create reached")), \
         patch("tools.airtable_gateway.airtable_patch", side_effect=AssertionError("direct patch reached")):
        contract = _propose(gw, identity)
        gw.route_confirmation_word(identity.memory_key, approver_role=identity.role)

    assert contract.status == "failed"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
