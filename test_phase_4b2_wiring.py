#!/usr/bin/env python3
"""
test_phase_4b2_wiring.py — Phase 4B-2 wiring stage: Approvals becomes a
non-authoritative projection of ActionContracts; execution is reachable
only through core.action_gateway.action_gateway (approve()/reject() ->
_execute_contract(), which owns the PostgreSQL atomic claim).

Covers the 9 scenarios required for this wiring stage:
  1. Raw-payload tampering in Approvals.CONTEXT_DATA is ignored — execution
     is driven entirely by the canonical ActionContract, never deserialized
     JSON from the projection row.
  2. Legacy refusal — a row with no action_contract_id / legacy_read_only
     is refused before any contract lookup, for both approve and reject.
  3. Projection-failure retry — the canonical ActionContract survives a
     failed projection write; a retry with the same payload self-heals the
     missing projection instead of creating a duplicate contract.
  4. Duplicate projection is harmless — two Approvals rows referencing the
     same action_contract_id cannot cause a double execution, because the
     second approve() sees the contract already resolved.
  5. Concurrent approval → exactly one execution (two threads racing the
     same Approvals row).
  6. Identity preservation — the original requester's identity is frozen
     onto the proposed contract; the approver's identity (not the
     requester's) is what action_gateway.approve() receives.
  7. outcome_unknown is never collapsed into failed — distinct HTTP/ok
     semantics and a distinct projected_lifecycle_status.
  8. Bulk path — bulk_approve() calls the exact same single-item helper as
     the single-approval endpoint (no parallel implementation).
  9. Flags-off refusal — with either FEATURE_ACTION_CONTRACT_PERSISTENCE or
     FEATURE_ATOMIC_CLAIMS unavailable, _queue_tma_write_approval() refuses
     before creating any ActionContract or Approvals row (no RAM-only /
     direct-execution fallback), and _claim_and_execute_approval() refuses
     the same way even if a contract already exists.
"""

from __future__ import annotations

import os
import sys
import threading
import types
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ── Minimal stubs so tma_api can be imported without full env ──────
os.environ.setdefault("TELEGRAM_TOKEN", "123:stub_token_for_tests")
os.environ.setdefault("AIRTABLE_API_KEY", "stub")
os.environ.setdefault("AIRTABLE_BASE_ID", "stub")
os.environ.setdefault("ANTHROPIC_API_KEY", "stub")

for mod_name in ["telebot", "anthropic", "httpx"]:
    sys.modules.setdefault(mod_name, MagicMock())

_sv = types.ModuleType("startup_validator")
_sv.validate_startup = lambda: None
_sv.format_startup_message = lambda: ""
sys.modules["startup_validator"] = _sv

import tma_api as _tma
from airtable_schema import ApprovalsFields, ApprovalStatus

from flask import Flask as _Flask
_app = _Flask(__name__)
_app.register_blueprint(_tma.tma_api)

_act_raw = _tma.act_on_approval.__wrapped__
_bulk_raw = _tma.bulk_approve.__wrapped__

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id="owner_1", role="owner", tenant_id="boss_hq") -> SimpleNamespace:
    ns = SimpleNamespace(
        is_owner=(role == "owner"),
        user_id=user_id,
        display_name=user_id,
        role=role,
        tenant_id=tenant_id,
        domain_id="general",
        allowed_domains=[],
        channel="telegram",
        external_id=f"tg_{user_id}",
    )
    ns.memory_key = f"{tenant_id}:{user_id}"
    return ns


# ── Fake ActionGateway: propose_action + approve/reject + find_contract ──

class _FakeContract:
    def __init__(self, contract_id: str, status: str = "pending", requester_identity=None):
        self.contract_id = contract_id
        self.status = status
        self.requester_identity = requester_identity


class _GatewayResult:
    def __init__(self, ok, contract_id=None, reason="", user_message=None, failure_code=None):
        self.ok = ok
        self.contract_id = contract_id
        self.reason = reason
        self.user_message = user_message
        self.failure_code = failure_code


class _FakeRepository:
    """Non-None sentinel — presence alone signals durable persistence available."""


class _FakeLedger:
    def __init__(self):
        self._repository = _FakeRepository()


class _FakeGateway:
    def __init__(self):
        self._ledger = _FakeLedger()
        self.contracts: dict[str, _FakeContract] = {}
        self.propose_calls: list[dict] = []
        self.approve_calls: list[dict] = []
        self.reject_calls: list[dict] = []
        self._next_id = 0
        self.propose_fail_persistence = False
        self.outcomes: dict[str, str] = {}   # contract_id -> forced approve() outcome

    def _new_id(self) -> str:
        self._next_id += 1
        return f"contract-{self._next_id}"

    def propose_action(self, *, tenant_id, canonical_user_id, tool_name, tool_inputs,
                        origin_channel, origin_chat_id, requires_approval, identity=None,
                        trusted_source="agent"):
        self.propose_calls.append({
            "tenant_id": tenant_id, "canonical_user_id": canonical_user_id,
            "tool_name": tool_name, "tool_inputs": tool_inputs,
            "origin_channel": origin_channel, "origin_chat_id": origin_chat_id,
            "identity": identity, "trusted_source": trusted_source,
        })
        if self.propose_fail_persistence:
            return _GatewayResult(ok=False, failure_code="persistence_failed", reason="db down")
        # Fingerprint-free fake dedup: same canonical_user_id + tool_inputs → same contract.
        for c in self.contracts.values():
            if getattr(c, "_fingerprint", None) == (canonical_user_id, str(tool_inputs)) and c.status == "pending":
                return _GatewayResult(ok=False, contract_id=c.contract_id,
                                       reason="already pending", user_message="⏳ כבר יש בקשת אישור פתוחה")
        cid = self._new_id()
        c = _FakeContract(cid, status="pending", requester_identity=identity)
        c._fingerprint = (canonical_user_id, str(tool_inputs))
        self.contracts[cid] = c
        return _GatewayResult(ok=True, contract_id=cid)

    def find_contract(self, contract_id):
        return self.contracts.get(contract_id)

    def approve(self, contract_id, approver, approver_role=""):
        self.approve_calls.append({"contract_id": contract_id, "approver": approver, "approver_role": approver_role})
        c = self.contracts.get(contract_id)
        if c is None:
            return "⚠️ פעולה לא נמצאה."
        if c.status != "pending":
            return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
        outcome = self.outcomes.get(contract_id, "completed")
        c.status = outcome
        if outcome in ("completed", "executed"):
            return "✅ בוצע: test"
        if outcome == "outcome_unknown":
            return "⚠️ תוצאת הפעולה אינה ידועה. אין לנסות שוב אוטומטית."
        return "❌ ביצוע נכשל: simulated failure"

    def reject(self, contract_id, rejected_by=""):
        self.reject_calls.append({"contract_id": contract_id, "rejected_by": rejected_by})
        c = self.contracts.get(contract_id)
        if c is None:
            return "⚠️ פעולה לא נמצאה."
        if c.status != "pending":
            return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
        c.status = "rejected"
        return "🚫 הפעולה בוטלה."


def _gateway_patches(gateway, durable=True, atomic=True) -> ExitStack:
    stack = ExitStack()
    for cm in (
        patch("core.action_gateway.action_gateway", gateway),
        patch("core.database.get_pool", return_value=(object() if atomic else None)),
        patch("feature_flags.is_enabled", side_effect=lambda name: {
            "FEATURE_ACTION_CONTRACT_PERSISTENCE": durable,
            "FEATURE_ATOMIC_CLAIMS": atomic,
        }.get(name, False)),
    ):
        stack.enter_context(cm)
    return stack


def _flags_patch(durable_flag: bool, atomic_flag: bool, pool_present: bool) -> ExitStack:
    """Precise control over the two independent axes for scenario 9."""
    stack = ExitStack()
    for cm in (
        patch("core.database.get_pool", return_value=(object() if pool_present else None)),
        patch("feature_flags.is_enabled", side_effect=lambda name: {
            "FEATURE_ACTION_CONTRACT_PERSISTENCE": durable_flag,
            "FEATURE_ATOMIC_CLAIMS": atomic_flag,
        }.get(name, False)),
    ):
        stack.enter_context(cm)
    return stack


def _projection_rec(rec_id: str, contract_id: str | None = None, legacy: bool = False,
                     context_data: str = "") -> dict:
    """contract_id=None means "auto-generate a default id"; pass "" explicitly
    to test the empty/missing-id case without triggering the default."""
    if contract_id is None:
        contract_id = f"c_{rec_id}"
    return {
        "id": rec_id,
        "fields": {
            ApprovalsFields.STATUS:              ApprovalStatus.PENDING,
            ApprovalsFields.ACTION:                "add lead",
            ApprovalsFields.RISK_LEVEL:            "low",
            ApprovalsFields.CONTEXT_ID:            f"ctx_{rec_id}",
            ApprovalsFields.CONTEXT_DATA:          context_data,
            ApprovalsFields.ACTION_CONTRACT_ID:    "" if legacy else contract_id,
            ApprovalsFields.LEGACY_READ_ONLY:      legacy,
        },
    }


# ══════════════════════════════════════════════════════════════════
# 1. Raw-payload tampering in CONTEXT_DATA is ignored
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: raw-payload tampering ignored ─────────────────────")

gw1 = _FakeGateway()
gw1.contracts["c1"] = _FakeContract("c1")

# Deliberately malformed/tampered CONTEXT_DATA — the old code would have
# json.loads()'d and executed this; the new code must never even look at it.
tampered = '{"type": "tma_write", "op": "post", "table": "Approvals", "fields": {"HACKED": true}'  # invalid JSON on purpose

with _gateway_patches(gw1):
    with patch("tma_api._at_get_record", return_value=_projection_rec("rec1", "c1", context_data=tampered)):
        with patch("tma_api._at_patch", return_value=True):
            with patch("tma_api._try_bus_action", return_value=False):
                outcome = _tma._claim_and_execute_approval("rec1", _identity())

chk("Test1: approval still succeeds despite malformed CONTEXT_DATA", outcome.get("ok") is True)
chk("Test1: contract executed via canonical contract, not the tampered payload",
    gw1.contracts["c1"].status == "completed")
chk("Test1: exactly one approve() call, no payload/table ever read from CONTEXT_DATA",
    len(gw1.approve_calls) == 1)


# ══════════════════════════════════════════════════════════════════
# 2. Legacy refusal — approve AND reject
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: legacy refusal (approve + reject) ─────────────────")

gw2 = _FakeGateway()

with _gateway_patches(gw2):
    with patch("tma_api._at_get_record", return_value=_projection_rec("rec2", legacy=True)):
        approve_outcome = _tma._claim_and_execute_approval("rec2", _identity())
        reject_outcome = _tma._claim_and_reject_approval("rec2", _identity())

chk("Test2: legacy approve refused (409)", approve_outcome.get("status_code") == 409 and not approve_outcome["ok"])
chk("Test2: legacy reject refused (409)", reject_outcome.get("status_code") == 409 and not reject_outcome["ok"])
chk("Test2: gateway never touched for either", gw2.approve_calls == [] and gw2.reject_calls == [])

# Also: a row with an empty action_contract_id but legacy_read_only=False
# (malformed/never-created-by-4B-2) must be refused the same way.
with _gateway_patches(gw2):
    with patch("tma_api._at_get_record", return_value=_projection_rec("rec2b", contract_id="", legacy=False)):
        no_id_outcome = _tma._claim_and_execute_approval("rec2b", _identity())
chk("Test2: empty action_contract_id (no legacy flag) is also refused",
    no_id_outcome.get("status_code") == 409 and not no_id_outcome["ok"])


# ══════════════════════════════════════════════════════════════════
# 3. Projection-failure retry — contract survives, retry self-heals
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: projection-failure retry self-heals ───────────────")

gw3 = _FakeGateway()
req_identity = _identity(user_id="owner_1")

with _gateway_patches(gw3):
    with patch("tma_api._at_list", return_value=[]):          # no existing projection row
        with patch("tma_api._at_post", return_value=None):    # projection write fails
            approval_id, body, status = _tma._queue_tma_write_approval(
                "tma_create_project",
                {"op": "post", "table": "ProjectsHub", "fields": {"name": "X"}},
                req_identity, "Create project: X",
            )

chk("Test3: canonical contract WAS created despite projection failure", len(gw3.contracts) == 1)
first_contract_id = next(iter(gw3.contracts))
chk("Test3: contract remains valid (pending), not deleted", gw3.contracts[first_contract_id].status == "pending")
chk("Test3: response reports approved_pending_projection, not a hard error",
    body.get("status") == "approved_pending_projection" and body.get("contract_id") == first_contract_id)
chk("Test3: no second/duplicate contract was created", len(gw3.propose_calls) == 1)

# Retry: same payload → propose_action recovers the SAME pending contract;
# this time the projection write succeeds → self-heals exactly one row.
created_rows: list[dict] = []


def _post_success(table, fields):
    row = {"id": f"approval-{len(created_rows)+1}", "fields": fields}
    created_rows.append(row)
    return row


with _gateway_patches(gw3):
    with patch("tma_api._at_list", return_value=[]):          # still no projection row exists yet
        with patch("tma_api._at_post", side_effect=_post_success):
            approval_id2, body2, status2 = _tma._queue_tma_write_approval(
                "tma_create_project",
                {"op": "post", "table": "ProjectsHub", "fields": {"name": "X"}},
                req_identity, "Create project: X",
            )

chk("Test3: retry recovers the SAME contract_id (no duplicate contract)",
    body2.get("contract_id") == first_contract_id)
chk("Test3: retry created exactly one projection row now", len(created_rows) == 1)
chk("Test3: still only one canonical contract in existence", len(gw3.contracts) == 1)


# ══════════════════════════════════════════════════════════════════
# 4. Duplicate projection rows are harmless — no double execution
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: duplicate projection rows cannot double-execute ───")

gw4 = _FakeGateway()
gw4.contracts["c_dup"] = _FakeContract("c_dup")

row_a = _projection_rec("recDupA", "c_dup")
row_b = _projection_rec("recDupB", "c_dup")   # same action_contract_id — duplicate

rows_by_id = {"recDupA": row_a, "recDupB": row_b}

with _gateway_patches(gw4):
    with patch("tma_api._at_get_record", side_effect=lambda t, rid: rows_by_id[rid]):
        with patch("tma_api._at_patch", return_value=True):
            with patch("tma_api._try_bus_action", return_value=False):
                first = _tma._claim_and_execute_approval("recDupA", _identity())
                second = _tma._claim_and_execute_approval("recDupB", _identity())

chk("Test4: first duplicate row executes successfully", first.get("ok") is True)
chk("Test4: second duplicate row is refused — contract already resolved",
    second.get("ok") is False and second.get("status_code") == 409)
chk("Test4: second call never reaches action_gateway.approve() at all — "
    "the contract-status check catches it first, before any claim/dispatch attempt",
    len(gw4.approve_calls) == 1 and gw4.contracts["c_dup"].status == "completed")


# ══════════════════════════════════════════════════════════════════
# 5. Concurrent approval → exactly one execution
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: concurrent approval → exactly one execution ───────")

gw5 = _FakeGateway()
gw5.contracts["c5"] = _FakeContract("c5")
_tma._APPROVAL_LOCKS.pop("rec5", None)

results: list[dict] = []
results_lock = threading.Lock()


def _run():
    with _gateway_patches(gw5):
        with patch("tma_api._at_get_record", return_value=_projection_rec("rec5", "c5")):
            with patch("tma_api._at_patch", return_value=True):
                with patch("tma_api._try_bus_action", return_value=False):
                    outcome = _tma._claim_and_execute_approval("rec5", _identity())
    with results_lock:
        results.append(outcome)


threads = [threading.Thread(target=_run) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

ok_count = sum(1 for r in results if r.get("ok"))
chk("Test5: exactly one thread succeeded", ok_count == 1)
chk("Test5: contract executed exactly once", gw5.contracts["c5"].status == "completed")


# ══════════════════════════════════════════════════════════════════
# 6. Identity preservation
# ══════════════════════════════════════════════════════════════════
print("\n── Test 6: identity preservation (requester vs approver) ─────")

gw6 = _FakeGateway()
requester = _identity(user_id="manager_1", role="manager")
approver = _identity(user_id="owner_1", role="owner")

with _gateway_patches(gw6):
    with patch("tma_api._at_list", return_value=[]):
        with patch("tma_api._at_post", side_effect=lambda t, f: {"id": "recX", "fields": f}):
            _tma._queue_tma_write_approval(
                "tma_update_lead_status",
                {"op": "patch", "table": "Leads", "record_id": "recLead1", "fields": {"status": "active"}},
                requester, "Update lead status",
            )

chk("Test6: propose_action received the REQUESTER's identity",
    gw6.propose_calls[0]["identity"] is requester)
chk("Test6: canonical_user_id uses the requester's memory_key",
    gw6.propose_calls[0]["canonical_user_id"] == requester.memory_key)

contract_id = gw6.propose_calls[0]["identity"] and next(iter(gw6.contracts))
with _gateway_patches(gw6):
    with patch("tma_api._at_get_record", return_value=_projection_rec("recX2", contract_id)):
        with patch("tma_api._at_patch", return_value=True):
            with patch("tma_api._try_bus_action", return_value=False):
                _tma._claim_and_execute_approval("recX2", approver)

chk("Test6: action_gateway.approve() received the APPROVER's ref, not the requester's",
    gw6.approve_calls[0]["approver"] == _tma._identity_ref(approver))
chk("Test6: approver_role reflects the approver's own role",
    gw6.approve_calls[0]["approver_role"] == "owner")


# ══════════════════════════════════════════════════════════════════
# 7. outcome_unknown is never collapsed into failed
# ══════════════════════════════════════════════════════════════════
print("\n── Test 7: outcome_unknown distinct from failed ──────────────")

gw7 = _FakeGateway()
gw7.contracts["c7"] = _FakeContract("c7")
gw7.outcomes["c7"] = "outcome_unknown"

patches_recorded: list[dict] = []


def _record_patch(table, rec_id, fields):
    patches_recorded.append(dict(fields))
    return True


with _gateway_patches(gw7):
    with patch("tma_api._at_get_record", return_value=_projection_rec("rec7", "c7")):
        with patch("tma_api._at_patch", side_effect=_record_patch):
            with patch("tma_api._try_bus_action", return_value=False):
                patches_recorded.clear()
                outcome = _tma._claim_and_execute_approval("rec7", _identity())

chk("Test7: HTTP 202 (distinct from 500 failure)", outcome.get("status_code") == 202)
chk("Test7: ok=False but not a hard failure error text",
    outcome.get("ok") is False and "outcome unknown" in outcome.get("error", ""))
chk("Test7: projected_lifecycle_status = outcome_unknown, not failed",
    any(p.get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS) == "outcome_unknown" for p in patches_recorded))
chk("Test7: legacy STATUS is not נכשל (not collapsed into failed)",
    not any(p.get(ApprovalsFields.STATUS) == ApprovalStatus.FAILED for p in patches_recorded))


# ══════════════════════════════════════════════════════════════════
# 8. Bulk path calls the exact same single-item helper
# ══════════════════════════════════════════════════════════════════
print("\n── Test 8: bulk_approve reuses the single-item helper ────────")

call_log: list[str] = []


def _tracking_single(approval_id, identity):
    call_log.append(approval_id)
    return {"ok": True, "status_code": 200, "new_status": ApprovalStatus.APPROVED,
            "action_label": "x", "ctx_id": "", "bus_synced": False, "execution_result": None}


recs8 = [_projection_rec("recB1"), _projection_rec("recB2")]

with patch("tma_api._at_list", return_value=recs8):
    with patch("tma_api._claim_and_execute_approval", side_effect=_tracking_single):
        with patch("tma_api._audit"):
            with patch("tma_api._notify_owner"):
                with _app.test_request_context("/api/approvals/bulk", method="POST"):
                    result = _bulk_raw(identity=_identity())
                    resp = result[0] if isinstance(result, tuple) else result

chk("Test8: bulk_approve called the single-item helper once per eligible row",
    sorted(call_log) == ["recB1", "recB2"])
chk("Test8: bulk response reports 2 approved", resp.json.get("approved") == 2)


# ══════════════════════════════════════════════════════════════════
# 9. Flags-off refusal — propose path and execute path
# ══════════════════════════════════════════════════════════════════
print("\n── Test 9: flags-off refusal, no fallback ─────────────────────")

gw9 = _FakeGateway()

for durable, atomic, label in [
    (False, True,  "durable persistence off"),
    (True,  False, "atomic claims off (no pool)"),
    (False, False, "both off"),
]:
    with patch("core.action_gateway.action_gateway", gw9):
        with _flags_patch(durable_flag=durable, atomic_flag=True, pool_present=atomic):
            gw9.propose_calls.clear()
            _, body, status = _tma._queue_tma_write_approval(
                "tma_create_project",
                {"op": "post", "table": "ProjectsHub", "fields": {"name": "Y"}},
                _identity(), "Create project: Y",
            )
    chk(f"Test9 propose ({label}): HTTP 503", status == 503)
    chk(f"Test9 propose ({label}): propose_action never called — no RAM-only fallback",
        gw9.propose_calls == [])

# Execute-path re-check: a contract that WAS created while flags were on
# must still refuse execution if flags are off by the time it's approved.
gw9b = _FakeGateway()
gw9b.contracts["c9"] = _FakeContract("c9")

with patch("core.action_gateway.action_gateway", gw9b):
    with _flags_patch(durable_flag=False, atomic_flag=True, pool_present=True):
        with patch("tma_api._at_get_record", return_value=_projection_rec("rec9", "c9")):
            outcome9 = _tma._claim_and_execute_approval("rec9", _identity())

chk("Test9 execute: refused when durable persistence unavailable at execution time",
    outcome9.get("ok") is False and outcome9.get("status_code") == 503)
chk("Test9 execute: approve() never called — no direct-execution fallback",
    gw9b.approve_calls == [])
chk("Test9 execute: contract remains pending, untouched", gw9b.contracts["c9"].status == "pending")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Phase 4B-2 wiring tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
