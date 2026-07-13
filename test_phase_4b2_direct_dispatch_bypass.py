#!/usr/bin/env python3
"""
test_phase_4b2_direct_dispatch_bypass.py — Phase 4B-2 follow-up: proves the
direct-dispatch bypass is actually closed, and that receipt identity
(approved_by) is never derived from the frozen requester identity.

Before this follow-up, dispatch_tool("tma_write", inputs, identity=...,
trusted_source=...) would execute the write immediately for ANY caller —
nothing checked that the call came from ActionGateway._execute_contract()
after a real approve(). tools/approval_actions.py::tma_write() now refuses
unless trusted_source=="tma_api" AND an execution_context dict (supplied
only by core/action_gateway.py::_make_dispatch_executor()) carries both a
contract_id and an approved_by.

These tests call the REAL dispatch_tool() / tma_write() — only the Airtable
I/O boundary (tools.airtable_gateway.airtable_create/airtable_patch) is
mocked, so tool_registry.enforce(), action_validator.validate_action(), and
tma_write()'s own gate all run for real.

Tests:
  1. dispatch_tool("tma_write", ...) with no execution_context at all
     performs zero provider writes (refused before touching Airtable).
  2. dispatch_tool("tma_write", ...) with trusted_source="agent" (the
     default/least-trusted value — what a rogue Agent tool_use call would
     carry) is refused even if an execution_context is somehow supplied.
  3. execution_context missing approved_by (contract_id present) is refused.
  4. execution_context missing contract_id (approved_by present) is refused.
  5. The legitimate shape — trusted_source="tma_api" + full
     execution_context — succeeds and performs exactly one write.
  6. Receipt's approved_by comes from execution_context, not from the
     `identity` parameter (which is always the frozen requester, per
     core/action_gateway.py's BUG-C89-APPROVAL-IDENTITY design) — proven by
     using a requester identity whose ref is deliberately different from
     execution_context["approved_by"].
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from tools.dispatcher import dispatch_tool
import tools.approval_actions as approval_actions

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _manager_identity() -> SimpleNamespace:
    return SimpleNamespace(
        user_id="manager_1", role="manager", display_name="Manager One",
        tenant_id="boss_hq", domain_id="general", allowed_domains=[],
        channel="telegram", external_id="tg_manager_1",
    )


_VALID_INPUTS = {
    "op": "post",
    "table": "Leads",
    "action": "tma_create_lead_task",
    "requested_by": "requester_ref",
    "fields": {"phone": "0501234567"},
    "audit_action": "lead_task_created",
    "audit_details": "test",
}


def _mock_airtable_create(*args, **kwargs):
    return {"id": "recCREATED123456", "fields": kwargs.get("fields", {})}


def _run_dispatch(trusted_source, execution_context):
    create_calls: list = []
    patch_calls: list = []

    def _tracking_create(table, fields, source="unknown"):
        create_calls.append({"table": table, "fields": fields})
        if table == "Leads":
            return {"id": "recCREATED123456", "fields": fields}
        return {"id": "recAUDIT123456789", "fields": fields}  # audit/receipt writes

    def _tracking_patch(table, record_id, fields, source="unknown"):
        patch_calls.append({"table": table, "record_id": record_id, "fields": fields})
        return True

    with patch("tools.airtable_gateway.airtable_create", side_effect=_tracking_create):
        with patch("tools.airtable_gateway.airtable_patch", side_effect=_tracking_patch):
            result = dispatch_tool(
                "tma_write", dict(_VALID_INPUTS),
                identity=_manager_identity(), trusted_source=trusted_source,
                execution_context=execution_context,
            )
    return result, create_calls, patch_calls


# ══════════════════════════════════════════════════════════════════
# 1. No execution_context at all — zero provider writes
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: no execution_context — refused, zero writes ────────")

result1, creates1, patches1 = _run_dispatch(trusted_source="tma_api", execution_context=None)

chk("Test1: result reports failure", isinstance(result1, dict) and result1.get("ok") is False)
chk("Test1: zero airtable_create calls (no Leads write, no audit, no receipt)", creates1 == [])
chk("Test1: zero airtable_patch calls", patches1 == [])


# ══════════════════════════════════════════════════════════════════
# 2. trusted_source="agent" (rogue Agent tool_use call shape) — refused
#    even with a full execution_context
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: trusted_source='agent' — refused despite full context ─")

result2, creates2, patches2 = _run_dispatch(
    trusted_source="agent",
    execution_context={"contract_id": "c-legit", "approved_by": "boss_hq:owner_1"},
)

chk("Test2: result reports failure", isinstance(result2, dict) and result2.get("ok") is False)
chk("Test2: zero provider writes", creates2 == [] and patches2 == [])


# ══════════════════════════════════════════════════════════════════
# 3. execution_context missing approved_by — refused
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: execution_context missing approved_by — refused ────")

result3, creates3, patches3 = _run_dispatch(
    trusted_source="tma_api",
    execution_context={"contract_id": "c-legit"},
)

chk("Test3: result reports failure", isinstance(result3, dict) and result3.get("ok") is False)
chk("Test3: zero provider writes", creates3 == [] and patches3 == [])


# ══════════════════════════════════════════════════════════════════
# 4. execution_context missing contract_id — refused
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: execution_context missing contract_id — refused ────")

result4, creates4, patches4 = _run_dispatch(
    trusted_source="tma_api",
    execution_context={"approved_by": "boss_hq:owner_1"},
)

chk("Test4: result reports failure", isinstance(result4, dict) and result4.get("ok") is False)
chk("Test4: zero provider writes", creates4 == [] and patches4 == [])


# ══════════════════════════════════════════════════════════════════
# 5. Legitimate shape — succeeds, exactly one business-table write
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: legitimate execution_context — succeeds ────────────")

result5, creates5, patches5 = _run_dispatch(
    trusted_source="tma_api",
    execution_context={"contract_id": "c-legit", "approved_by": "boss_hq:owner_1"},
)

chk("Test5: result reports success", isinstance(result5, dict) and result5.get("ok") is True)
business_writes = [c for c in creates5 if c["table"] == "Leads"]
chk("Test5: exactly one write to the actual business table (Leads)", len(business_writes) == 1)


# ══════════════════════════════════════════════════════════════════
# 6. Receipt approved_by comes from execution_context, never from the
#    frozen requester identity
# ══════════════════════════════════════════════════════════════════
print("\n── Test 6: receipt approved_by is the approver, not the requester ─")

# The `identity` parameter always represents the frozen REQUESTER (per
# core/action_gateway.py's BUG-C89-APPROVAL-IDENTITY design) — here that's
# _manager_identity() ("manager_1"). The APPROVER is a different person
# entirely, threaded in only via execution_context.
_, creates6, _ = _run_dispatch(
    trusted_source="tma_api",
    execution_context={"contract_id": "c-legit", "approved_by": "boss_hq:owner_1"},
)

# Find the receipt write (Interaction Log "[TMA receipt] ..." create call).
receipt_calls = [c for c in creates6 if c["table"] != "Leads"]
chk("Test6: a receipt write occurred", len(receipt_calls) >= 1)
if receipt_calls:
    import json as _json
    receipt_summary_calls = [c for c in receipt_calls if "SUMMARY" in str(c["fields"].keys()) or any(
        isinstance(v, str) and '"approved_by"' in v for v in c["fields"].values()
    )]
    found_approved_by = None
    for c in receipt_calls:
        for v in c["fields"].values():
            if isinstance(v, str) and '"approved_by"' in v:
                try:
                    parsed = _json.loads(v)
                    found_approved_by = parsed.get("approved_by")
                except (TypeError, ValueError):
                    pass
    chk("Test6: receipt approved_by == execution_context's approver (owner_1)",
        found_approved_by == "boss_hq:owner_1")
    chk("Test6: receipt approved_by is NOT the frozen requester (manager_1)",
        found_approved_by != "manager_1" and found_approved_by != "boss_hq:manager_1")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Phase 4B-2 direct-dispatch-bypass tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
