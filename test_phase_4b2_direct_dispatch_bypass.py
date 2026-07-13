#!/usr/bin/env python3
"""
test_phase_4b2_direct_dispatch_bypass.py — Phase 4B-2 follow-up: proves the
direct-dispatch bypass is actually closed, and that receipt identity
(approved_by) is never derived from the frozen requester identity.

Before this follow-up, dispatch_tool("tma_write", inputs, identity=...,
trusted_source=...) would execute the write immediately for ANY caller —
nothing checked that the call came from ActionGateway._execute_contract()
after a real approve(). A first fix required trusted_source=="tma_api" AND
an execution_context dict carrying a contract_id + approved_by — but that
dict is caller-constructible: ANY in-process code that can call
dispatch_tool() can also fabricate {"contract_id": "...", "approved_by":
"..."} and pass trusted_source="tma_api" directly, with no real approval
ever having happened. That gap is what this file's Test 6 used to prove
"succeeds" — a bug in the test, not a feature: it demonstrated the exact
forgery this phase closes.

tools/approval_actions.py::tma_write() now additionally requires
execution_context["claim_execution_id"], and verifies it via
_verify_active_execution_claim() against a REAL row in PostgreSQL's
action_execution_claims table (core.atomic_claim_repository.get_claim()) —
the sole execution-ownership primitive. That row can only exist because
execute_with_atomic_claim() won a real claim_contract_execution() race and
threaded its execution_id through core/action_gateway.py's
_make_dispatch_executor() closure. A caller-constructed dict — no matter
how plausible its shape — cannot produce a matching PostgreSQL row, so it
is refused before touching Airtable.

These tests call the REAL dispatch_tool() / tma_write() — only the Airtable
I/O boundary (tools.airtable_gateway.airtable_create/airtable_patch) and
the PostgreSQL claim lookup (core.atomic_claim_repository.get_claim) are
mocked, so tool_registry.enforce(), action_validator.validate_action(), and
tma_write()'s own gate (including _verify_active_execution_claim()) all run
for real.

Tests:
  1. No execution_context at all — refused, zero provider writes.
  2. trusted_source="agent" (rogue Agent tool_use call shape) is refused
     even when execution_context matches a real, currently-EXECUTING
     PostgreSQL claim — trusted_source is checked independently.
  3. execution_context missing approved_by (contract_id + claim_execution_id
     present) — refused.
  4. execution_context missing contract_id (approved_by + claim_execution_id
     present) — refused.
  5. execution_context missing claim_execution_id entirely (only contract_id
     + approved_by present — the exact shape the OLD, insufficient gate
     accepted) — refused, zero writes.
  6. Forged execution_context: contract_id + approved_by + a plausible-
     looking claim_execution_id, but no matching claim exists in
     PostgreSQL at all (get_claim() returns None) — refused, zero writes.
     THIS IS THE DIRECT REPLACEMENT for the old Test 5, which incorrectly
     asserted this exact shape succeeds.
  6b. A real claim exists for the contract, but the supplied
      claim_execution_id does not match it (copied/guessed from elsewhere)
      — refused.
  6c. A real claim exists and the execution_id matches, but its status is
      no longer "executing" (already completed) — a finished claim's id
      cannot be replayed to authorize a second write — refused.
  6d. A real, currently-EXECUTING claim exists and the execution_id
      matches, but the claim's actual claimant_id differs from the
      approved_by the caller is asserting (attempted receipt-identity
      forgery riding on someone else's real claim) — refused.
  7. The legitimate shape — trusted_source="tma_api" + execution_context
     whose claim_execution_id verifies against a real, currently-EXECUTING
     PostgreSQL claim owned by the asserted approved_by — succeeds and
     performs exactly one write to the actual business table.
  8. Receipt's approved_by comes from execution_context (the verified
     claimant), not from the `identity` parameter (which is always the
     frozen requester, per core/action_gateway.py's BUG-C89-APPROVAL-
     IDENTITY design) — proven with a genuine claim whose claimant differs
     from the requester identity.
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
from core.atomic_claim_repository import AtomicExecutionClaim, STATUS_EXECUTING, STATUS_COMPLETED

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

_REAL_CONTRACT_ID = "c-legit"
_REAL_EXECUTION_ID = "exec-legit-1234"
_REAL_APPROVER = "boss_hq:owner_1"


def _real_claim(status: str = STATUS_EXECUTING, claimant_id: str = _REAL_APPROVER,
                 execution_id: str = _REAL_EXECUTION_ID) -> AtomicExecutionClaim:
    """A live PostgreSQL claim row — what get_claim() returns when a real
    claim_contract_execution() actually won the race for this contract."""
    claim = AtomicExecutionClaim(
        contract_id=_REAL_CONTRACT_ID, claimant_id=claimant_id,
        execution_id=execution_id, claimed_at=1234567890.0,
    )
    claim.status = status
    return claim


def _run_dispatch(trusted_source, execution_context, claim=None):
    """claim=None simulates no PostgreSQL row existing for the contract at
    all (get_claim() returns None) — the realistic state for any caller
    that never went through claim_contract_execution(). Pass a real
    AtomicExecutionClaim to simulate one actually existing."""
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
            with patch("core.atomic_claim_repository.get_claim", return_value=claim):
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
# 2. trusted_source="agent" — refused even against a REAL, matching claim
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: trusted_source='agent' — refused despite a real claim ─")

result2, creates2, patches2 = _run_dispatch(
    trusted_source="agent",
    execution_context={
        "contract_id": _REAL_CONTRACT_ID, "approved_by": _REAL_APPROVER,
        "claim_execution_id": _REAL_EXECUTION_ID,
    },
    claim=_real_claim(),
)

chk("Test2: result reports failure", isinstance(result2, dict) and result2.get("ok") is False)
chk("Test2: zero provider writes", creates2 == [] and patches2 == [])


# ══════════════════════════════════════════════════════════════════
# 3. execution_context missing approved_by — refused
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: execution_context missing approved_by — refused ────")

result3, creates3, patches3 = _run_dispatch(
    trusted_source="tma_api",
    execution_context={"contract_id": _REAL_CONTRACT_ID, "claim_execution_id": _REAL_EXECUTION_ID},
    claim=_real_claim(),
)

chk("Test3: result reports failure", isinstance(result3, dict) and result3.get("ok") is False)
chk("Test3: zero provider writes", creates3 == [] and patches3 == [])


# ══════════════════════════════════════════════════════════════════
# 4. execution_context missing contract_id — refused
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: execution_context missing contract_id — refused ────")

result4, creates4, patches4 = _run_dispatch(
    trusted_source="tma_api",
    execution_context={"approved_by": _REAL_APPROVER, "claim_execution_id": _REAL_EXECUTION_ID},
    claim=_real_claim(),
)

chk("Test4: result reports failure", isinstance(result4, dict) and result4.get("ok") is False)
chk("Test4: zero provider writes", creates4 == [] and patches4 == [])


# ══════════════════════════════════════════════════════════════════
# 5. execution_context missing claim_execution_id — the exact shape the
#    OLD (insufficient) gate accepted as sufficient proof — refused
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: no claim_execution_id — refused (old gate's blind spot) ─")

result5, creates5, patches5 = _run_dispatch(
    trusted_source="tma_api",
    execution_context={"contract_id": _REAL_CONTRACT_ID, "approved_by": _REAL_APPROVER},
    claim=_real_claim(),  # a real claim exists, but the caller never supplied its id
)

chk("Test5: result reports failure", isinstance(result5, dict) and result5.get("ok") is False)
chk("Test5: zero provider writes", creates5 == [] and patches5 == [])


# ══════════════════════════════════════════════════════════════════
# 6. Forged execution_context: contract_id + approved_by + a plausible
#    claim_execution_id, but NO matching PostgreSQL claim exists at all.
#    DIRECT REPLACEMENT for the old (incorrect) Test 5, which asserted this
#    exact caller-constructed-dict shape succeeds.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 6: forged execution_context, no real PG claim — refused ─")

result6, creates6, patches6 = _run_dispatch(
    trusted_source="tma_api",
    execution_context={
        "contract_id": _REAL_CONTRACT_ID, "approved_by": _REAL_APPROVER,
        "claim_execution_id": "forged-execution-id-never-acquired",
    },
    claim=None,  # get_claim() finds nothing — no claim_contract_execution() ever ran
)

chk("Test6: result reports failure", isinstance(result6, dict) and result6.get("ok") is False)
chk("Test6: a hand-built dict alone performs ZERO provider writes",
    creates6 == [] and patches6 == [])


# ── 6b. Real claim exists, but supplied claim_execution_id doesn't match ──
print("── Test 6b: claim_execution_id mismatch — refused ──────────────")

result6b, creates6b, patches6b = _run_dispatch(
    trusted_source="tma_api",
    execution_context={
        "contract_id": _REAL_CONTRACT_ID, "approved_by": _REAL_APPROVER,
        "claim_execution_id": "some-other-execution-id",
    },
    claim=_real_claim(execution_id=_REAL_EXECUTION_ID),
)

chk("Test6b: result reports failure", isinstance(result6b, dict) and result6b.get("ok") is False)
chk("Test6b: zero provider writes", creates6b == [] and patches6b == [])


# ── 6c. Real claim exists and id matches, but it's no longer EXECUTING ──
print("── Test 6c: claim already completed (stale id) — refused ───────")

result6c, creates6c, patches6c = _run_dispatch(
    trusted_source="tma_api",
    execution_context={
        "contract_id": _REAL_CONTRACT_ID, "approved_by": _REAL_APPROVER,
        "claim_execution_id": _REAL_EXECUTION_ID,
    },
    claim=_real_claim(status=STATUS_COMPLETED),
)

chk("Test6c: result reports failure", isinstance(result6c, dict) and result6c.get("ok") is False)
chk("Test6c: zero provider writes", creates6c == [] and patches6c == [])


# ── 6d. Real EXECUTING claim, id matches, but claimant != asserted approved_by ──
print("── Test 6d: claimant_id mismatch (receipt-forgery attempt) — refused ─")

result6d, creates6d, patches6d = _run_dispatch(
    trusted_source="tma_api",
    execution_context={
        "contract_id": _REAL_CONTRACT_ID, "approved_by": "boss_hq:someone_else",
        "claim_execution_id": _REAL_EXECUTION_ID,
    },
    claim=_real_claim(claimant_id=_REAL_APPROVER),  # real claimant is owner_1, not someone_else
)

chk("Test6d: result reports failure", isinstance(result6d, dict) and result6d.get("ok") is False)
chk("Test6d: zero provider writes", creates6d == [] and patches6d == [])


# ══════════════════════════════════════════════════════════════════
# 7. Legitimate shape — real, currently-EXECUTING PostgreSQL claim —
#    succeeds, exactly one business-table write
# ══════════════════════════════════════════════════════════════════
print("\n── Test 7: genuine PostgreSQL claim — succeeds ─────────────────")

result7, creates7, patches7 = _run_dispatch(
    trusted_source="tma_api",
    execution_context={
        "contract_id": _REAL_CONTRACT_ID, "approved_by": _REAL_APPROVER,
        "claim_execution_id": _REAL_EXECUTION_ID,
    },
    claim=_real_claim(),
)

chk("Test7: result reports success", isinstance(result7, dict) and result7.get("ok") is True)
business_writes = [c for c in creates7 if c["table"] == "Leads"]
chk("Test7: exactly one write to the actual business table (Leads)", len(business_writes) == 1)


# ══════════════════════════════════════════════════════════════════
# 8. Receipt approved_by comes from the verified claim's claimant, never
#    from the frozen requester identity
# ══════════════════════════════════════════════════════════════════
print("\n── Test 8: receipt approved_by is the approver, not the requester ─")

# The `identity` parameter always represents the frozen REQUESTER (per
# core/action_gateway.py's BUG-C89-APPROVAL-IDENTITY design) — here that's
# _manager_identity() ("manager_1"). The APPROVER is a different person
# entirely, proven only via a real PostgreSQL claim.
_, creates8, _ = _run_dispatch(
    trusted_source="tma_api",
    execution_context={
        "contract_id": _REAL_CONTRACT_ID, "approved_by": _REAL_APPROVER,
        "claim_execution_id": _REAL_EXECUTION_ID,
    },
    claim=_real_claim(),
)

# Find the receipt write (Interaction Log "[TMA receipt] ..." create call).
receipt_calls = [c for c in creates8 if c["table"] != "Leads"]
chk("Test8: a receipt write occurred", len(receipt_calls) >= 1)
if receipt_calls:
    import json as _json
    found_approved_by = None
    for c in receipt_calls:
        for v in c["fields"].values():
            if isinstance(v, str) and '"approved_by"' in v:
                try:
                    parsed = _json.loads(v)
                    found_approved_by = parsed.get("approved_by")
                except (TypeError, ValueError):
                    pass
    chk("Test8: receipt approved_by == the verified claim's claimant (owner_1)",
        found_approved_by == _REAL_APPROVER)
    chk("Test8: receipt approved_by is NOT the frozen requester (manager_1)",
        found_approved_by != "manager_1" and found_approved_by != "boss_hq:manager_1")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Phase 4B-2 direct-dispatch-bypass tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
