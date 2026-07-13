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
     same Approvals row) — WIRING-ONLY, see the WIRING-ONLY note below.
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
 10. Two different approval IDs, same contract, concurrent — WIRING-ONLY,
     see the WIRING-ONLY note below.

WIRING-ONLY NOTE (Tests 5 and 10 — concurrency): every test in this file
replaces core.action_gateway.action_gateway with _FakeGateway, whose
approve()/reject() serialize under their OWN threading.Lock
(_claim_lock). That proves this file's wiring layer (tma_api.py's
_claim_and_execute_approval/_claim_and_reject_approval) correctly treats
action_gateway.approve() as the single choke point for execution — it
correctly handles whatever approve() returns, regardless of which
approval_id/process-local lock reached it first, and never performs a
second dispatch itself. It does NOT exercise, and must never be read as
proof of, PostgreSQL's own atomic coordination — _FakeGateway._claim_lock
is a Python-level substitute chosen by this test file, not
core.atomic_claim_repository's real INSERT ... ON CONFLICT DO NOTHING. The
authoritative proof that concurrent approvals produce exactly one
dispatcher/provider call through the REAL PostgreSQL claim lives in
test_phase_4b0_1b_concurrency.py (claim_contract_execution() race
semantics, including real-PostgreSQL cases against a staging DB) and
test_phase_4b0_1c_concurrent_approvals.py (concurrent approval requests via
the real ActionGateway + execute_with_atomic_claim path) — see those files,
not this one, for that guarantee.
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
    def __init__(self, contract_id: str, status: str = "pending", requester_identity=None,
                 approval_policy: str = "approval"):
        self.contract_id = contract_id
        self.status = status
        self.requester_identity = requester_identity
        # "approval" (APPROVAL_POLICY_APPROVAL) is the default/strict policy —
        # matches real propose_action() behavior for tma_write, which is
        # never classified as self_confirm (see classify_approval_policy()).
        self.approval_policy = approval_policy


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
        # Test-only substitute for whatever ultimately gives approve() a
        # single-winner guarantee (in production: PostgreSQL's atomic
        # claim). The check-then-transition below is atomic under this
        # lock regardless of which (possibly different) approval_id/
        # process-local lock the caller used to get here — this proves the
        # WIRING layer's response to a single-winner outcome is correct, not
        # that PostgreSQL itself provides one (see the WIRING-ONLY note at
        # the top of this file).
        self._claim_lock = threading.Lock()
        # Incremented only by the caller that actually wins the
        # check-then-transition race — i.e. only once per contract, no
        # matter how many callers reach approve()/reject(). Distinct from
        # approve_calls/reject_calls, which count invocations (both a
        # winner and a loser show up there).
        self.execution_count = 0
        # Optional threading.Barrier: when set, approve()/reject() wait on
        # it before acquiring _claim_lock, so a concurrency test can force
        # every caller to actually reach the race window at the same time
        # instead of depending on OS thread-scheduling luck.
        self._entry_barrier: threading.Barrier | None = None

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
        if self._entry_barrier is not None:
            self._entry_barrier.wait()
        with self._claim_lock:
            c = self.contracts.get(contract_id)
            if c is None:
                return "⚠️ פעולה לא נמצאה."
            if c.status != "pending":
                return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
            outcome = self.outcomes.get(contract_id, "completed")
            c.status = outcome
            self.execution_count += 1
        if outcome in ("completed", "executed"):
            return "✅ בוצע: test"
        if outcome == "outcome_unknown":
            return "⚠️ תוצאת הפעולה אינה ידועה. אין לנסות שוב אוטומטית."
        return "❌ ביצוע נכשל: simulated failure"

    def reject(self, contract_id, rejected_by=""):
        self.reject_calls.append({"contract_id": contract_id, "rejected_by": rejected_by})
        with self._claim_lock:
            c = self.contracts.get(contract_id)
            if c is None:
                return "⚠️ פעולה לא נמצאה."
            if c.status != "pending":
                return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
            c.status = "rejected"
            self.execution_count += 1
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
chk("Test3: response reports pending_approval_projection_missing, not a hard error",
    body.get("status") == "pending_approval_projection_missing" and body.get("contract_id") == first_contract_id)
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
# 5. WIRING-ONLY: same approval_id, concurrent requests -> the wiring layer
#    routes both through action_gateway.approve() and correctly surfaces
#    exactly one success. This exercises _FakeGateway._claim_lock, a test
#    substitute — NOT PostgreSQL's real atomic claim. See the WIRING-ONLY
#    note at the top of this file; the real proof lives in
#    test_phase_4b0_1b_concurrency.py / test_phase_4b0_1c_concurrent_approvals.py.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5 (wiring-only): concurrent approval, same approval_id ─")

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
chk("Test5 (wiring-only): exactly one thread succeeded through the wiring layer",
    ok_count == 1)
chk("Test5 (wiring-only): _FakeGateway's own lock resolved the contract to completed "
    "(not proof of PostgreSQL atomicity — see test_phase_4b0_1b/1c)",
    gw5.contracts["c5"].status == "completed")


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
# 10. WIRING-ONLY: two DIFFERENT approval IDs referencing the SAME contract,
#     concurrently. Proves the wiring layer's per-approval_id
#     threading.Lock (_get_approval_lock) does NOT — and is not relied on
#     to — serialize these two rows (different approval_ids -> different
#     locks), and that both requests correctly funnel through the single
#     action_gateway.approve() choke point regardless. The single-winner
#     outcome here comes from _FakeGateway._claim_lock, a test substitute —
#     see the WIRING-ONLY note at the top of this file. It is NOT proof of
#     PostgreSQL's real atomic claim; that is test_phase_4b0_1b_concurrency.py
#     / test_phase_4b0_1c_concurrent_approvals.py's job, not this file's.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 10 (wiring-only): two different approval IDs, same contract ─")

gw10 = _FakeGateway()
gw10.contracts["c_shared"] = _FakeContract("c_shared")
# Force both threads to actually reach approve() together before either can
# acquire the claim lock — proves the race is won/lost inside approve()
# itself, not just an artifact of whichever thread the OS scheduler happened
# to run first.
gw10._entry_barrier = threading.Barrier(2)
_tma._APPROVAL_LOCKS.pop("recDupC", None)
_tma._APPROVAL_LOCKS.pop("recDupD", None)

rows10 = {
    "recDupC": _projection_rec("recDupC", "c_shared"),
    "recDupD": _projection_rec("recDupD", "c_shared"),
}

results10: list[dict] = []
results10_lock = threading.Lock()


def _run10(approval_id):
    with _gateway_patches(gw10):
        with patch("tma_api._at_get_record", side_effect=lambda t, rid: rows10[rid]):
            with patch("tma_api._at_patch", return_value=True):
                outcome = _tma._claim_and_execute_approval(approval_id, _identity())
    with results10_lock:
        results10.append(outcome)


t_c = threading.Thread(target=_run10, args=("recDupC",))
t_d = threading.Thread(target=_run10, args=("recDupD",))
t_c.start(); t_d.start()
t_c.join(); t_d.join()

chk("Test10 (wiring-only): both different-approval_id requests reached "
    "action_gateway.approve() — confirms their process-local locks do NOT "
    "serialize each other (different approval_ids); the wiring layer relies "
    "on approve() itself, not _get_approval_lock, for correctness here",
    len(gw10.approve_calls) == 2)
chk("Test10 (wiring-only): the contract was resolved exactly once by "
    "_FakeGateway's own lock — a test substitute for PostgreSQL's atomic "
    "claim, not the claim itself (see test_phase_4b0_1b/1c for that proof)",
    gw10.execution_count == 1)
chk("Test10 (wiring-only): contract ends completed, not double-run",
    gw10.contracts["c_shared"].status == "completed")


# ══════════════════════════════════════════════════════════════════
# 11. CONTEXT_ID tampering cannot invoke event_bus, even when it collides
#     with a real pending event_bus action.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 11: tampered CONTEXT_ID cannot reach event_bus ────────────")

gw11 = _FakeGateway()
gw11.contracts["c11"] = _FakeContract("c11")

tampered_row = _projection_rec("rec11", "c11")
tampered_row["fields"][ApprovalsFields.CONTEXT_ID] = "some_unrelated_live_event_bus_action_id"

bus_mock_11 = MagicMock(return_value=True)  # would "succeed" if ever called
with _gateway_patches(gw11):
    with patch("tma_api._at_get_record", return_value=tampered_row):
        with patch("tma_api._at_patch", return_value=True):
            with patch("tma_api._try_bus_action", bus_mock_11):
                outcome11 = _tma._claim_and_execute_approval("rec11", _identity())

chk("Test11: approval still executes correctly", outcome11.get("ok") is True)
chk("Test11: bus_synced is False regardless of CONTEXT_ID content", outcome11.get("bus_synced") is False)
chk("Test11: _try_bus_action is never called — CONTEXT_ID is never used to reach event_bus",
    bus_mock_11.call_count == 0)


# ══════════════════════════════════════════════════════════════════
# 12. Projection lookup failure does not create a duplicate row
# ══════════════════════════════════════════════════════════════════
print("\n── Test 12: projection lookup failure never falls through to POST ─")

post_calls_12: list[dict] = []


def _tracking_post_12(table, fields):
    post_calls_12.append(fields)
    return {"id": "should-not-exist", "fields": fields}


with patch("tma_api._at_list", side_effect=_tma.AirtableError("Approvals", 500, "boom")):
    with patch("tma_api._at_post", side_effect=_tracking_post_12):
        result12 = _tma._ensure_approval_projection("c12", "tma_create_project", "label", "Low", _identity())

chk("Test12: _ensure_approval_projection returns None on lookup failure (visibility failure)",
    result12 is None)
chk("Test12: no POST was ever attempted after a failed lookup — no duplicate risk",
    post_calls_12 == [])


# ══════════════════════════════════════════════════════════════════
# 13. A malformed existing projection is repaired, not returned untouched
# ══════════════════════════════════════════════════════════════════
print("\n── Test 13: malformed existing projection is repaired ─────────────")

malformed_row = {
    "id": "recMalformed",
    "fields": {
        ApprovalsFields.ACTION: "add lead",
        # action_contract_id present but legacy_read_only was left True by
        # a prior inconsistent write — must be corrected, not trusted as-is.
        ApprovalsFields.ACTION_CONTRACT_ID: "c13",
        ApprovalsFields.LEGACY_READ_ONLY: True,
        ApprovalsFields.PROJECTED_LIFECYCLE_STATUS: "failed",  # stale/wrong
    },
}

patch_calls_13: list[dict] = []


def _tracking_patch_13(table, rec_id, fields):
    patch_calls_13.append({"rec_id": rec_id, **fields})
    return True


with patch("tma_api._at_list", return_value=[malformed_row]):
    with patch("tma_api._at_patch", side_effect=_tracking_patch_13):
        result13 = _tma._ensure_approval_projection("c13", "tma_create_project", "label", "Low", _identity())

chk("Test13: repair PATCH was issued against the existing row", len(patch_calls_13) == 1
    and patch_calls_13[0]["rec_id"] == "recMalformed")
chk("Test13: legacy_read_only corrected to False",
    patch_calls_13[0][ApprovalsFields.LEGACY_READ_ONLY] is False)
chk("Test13: projected_lifecycle_status corrected to pending",
    patch_calls_13[0][ApprovalsFields.PROJECTED_LIFECYCLE_STATUS] == "pending")
chk("Test13: CONTEXT_DATA re-blanked during repair", patch_calls_13[0][ApprovalsFields.CONTEXT_DATA] == "")
chk("Test13: returned record reflects the repaired fields, not the stale ones",
    result13 is not None
    and result13["fields"][ApprovalsFields.LEGACY_READ_ONLY] is False
    and result13["fields"][ApprovalsFields.PROJECTED_LIFECYCLE_STATUS] == "pending")


# ══════════════════════════════════════════════════════════════════
# 14. Projection sync failure surfaces projection_sync_pending, canonical
#     outcome preserved
# ══════════════════════════════════════════════════════════════════
print("\n── Test 14: projection sync failure surfaces projection_sync_pending ─")

gw14 = _FakeGateway()
gw14.contracts["c14"] = _FakeContract("c14")

with _gateway_patches(gw14):
    with patch("tma_api._at_get_record", return_value=_projection_rec("rec14", "c14")):
        with patch("tma_api._at_patch", return_value=False):   # projection sync PATCH fails
            with patch("tma_api._try_bus_action", return_value=False):
                outcome14 = _tma._claim_and_execute_approval("rec14", _identity())

chk("Test14: canonical execution still succeeded (approve() itself unaffected)",
    gw14.contracts["c14"].status == "completed")
chk("Test14: response still reports ok=True — canonical outcome is authoritative",
    outcome14.get("ok") is True)
chk("Test14: projection_sync_pending=True surfaces the display lag",
    outcome14.get("projection_sync_pending") is True)


# ══════════════════════════════════════════════════════════════════
# 15. GET /api/approvals: legacy rows are actionable=false, action_contract_id
#     / legacy_read_only / projected_lifecycle_status are all exposed
# ══════════════════════════════════════════════════════════════════
print("\n── Test 15: GET /api/approvals exposes projection fields, legacy=non-actionable ─")

gw15 = _FakeGateway()
gw15.contracts["c15"] = _FakeContract("c15")   # pending, real contract

legacy_row_15 = _projection_rec("recLegacy15", legacy=True)
linked_row_15 = _projection_rec("recLinked15", "c15")

with patch("core.action_gateway.action_gateway", gw15):
    with patch("feature_flags.is_enabled", return_value=True):
        legacy_fmt = _tma._fmt_approval(legacy_row_15)
        linked_fmt = _tma._fmt_approval(linked_row_15)

chk("Test15: legacy row exposes action_contract_id (empty)",
    legacy_fmt["action_contract_id"] == "")
chk("Test15: legacy row exposes legacy_read_only=True", legacy_fmt["legacy_read_only"] is True)
chk("Test15: legacy row is actionable=False", legacy_fmt["actionable"] is False)
chk("Test15: contract-linked pending row is actionable=True",
    linked_fmt["action_contract_id"] == "c15"
    and linked_fmt["legacy_read_only"] is False
    and linked_fmt["actionable"] is True)
chk("Test15: projected_lifecycle_status is exposed in the read model",
    "projected_lifecycle_status" in linked_fmt)

# Full GET /api/approvals endpoint, end to end.
_get_approvals_raw = _tma.get_approvals.__wrapped__
with patch("core.action_gateway.action_gateway", gw15):
    with patch("feature_flags.is_enabled", return_value=True):
        with patch("tma_api._at_list", return_value=[legacy_row_15, linked_row_15]):
            with _app.test_request_context("/api/approvals", method="GET"):
                resp = _get_approvals_raw(identity=_identity())

approvals_list = resp.json["approvals"]
by_id = {a["id"]: a for a in approvals_list}
chk("Test15: GET /api/approvals surfaces actionable=false for the legacy row",
    by_id["recLegacy15"]["actionable"] is False)
chk("Test15: GET /api/approvals surfaces actionable=true for the contract-linked row",
    by_id["recLinked15"]["actionable"] is True)


# ══════════════════════════════════════════════════════════════════
# 16. projection_sync_pending propagates through the actual HTTP boundary —
#     approve success, approve failure/outcome_unknown, reject success, and
#     bulk_approve's count/list. Endpoint-level (full Flask route), not just
#     the internal helper dicts already covered by Test 14.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 16: projection_sync_pending propagates through HTTP ──────")

_act_raw_16 = _tma.act_on_approval.__wrapped__
_bulk_raw_16 = _tma.bulk_approve.__wrapped__

# 16a. approve success, sync fails -> HTTP 200 body carries projection_sync_pending.
gw16a = _FakeGateway()
gw16a.contracts["c16a"] = _FakeContract("c16a")

with _app.test_request_context("/api/approvals/rec16a", method="POST", json={"action": "approve"}):
    with _gateway_patches(gw16a):
        with patch("tma_api._at_get_record", return_value=_projection_rec("rec16a", "c16a")):
            with patch("tma_api._at_patch", return_value=False):  # projection sync fails
                with patch("tma_api._audit"), patch("tma_api._notify_owner"):
                    result16a = _act_raw_16("rec16a", identity=_identity())
                    resp16a, code16a = result16a if isinstance(result16a, tuple) else (result16a, 200)

chk("Test16a: HTTP 200 despite sync failure (canonical outcome succeeded)", code16a == 200)
chk("Test16a: JSON body carries projection_sync_pending=true",
    resp16a.json.get("projection_sync_pending") is True)

# 16b. approve outcome_unknown, sync ALSO fails -> HTTP 202 body still carries it.
gw16b = _FakeGateway()
gw16b.contracts["c16b"] = _FakeContract("c16b")
gw16b.outcomes["c16b"] = "outcome_unknown"

with _app.test_request_context("/api/approvals/rec16b", method="POST", json={"action": "approve"}):
    with _gateway_patches(gw16b):
        with patch("tma_api._at_get_record", return_value=_projection_rec("rec16b", "c16b")):
            with patch("tma_api._at_patch", return_value=False):
                result16b = _act_raw_16("rec16b", identity=_identity())
                resp16b, code16b = result16b if isinstance(result16b, tuple) else (result16b, 200)

chk("Test16b: HTTP 202 for outcome_unknown", code16b == 202)
chk("Test16b: JSON error body ALSO carries projection_sync_pending=true "
    "(display lag surfaced even on a non-2xx response)",
    resp16b.json.get("projection_sync_pending") is True)

# 16c. reject success, sync fails -> HTTP 200 body carries projection_sync_pending.
gw16c = _FakeGateway()
gw16c.contracts["c16c"] = _FakeContract("c16c")

with _app.test_request_context("/api/approvals/rec16c", method="POST", json={"action": "reject"}):
    with _gateway_patches(gw16c):
        with patch("tma_api._at_get_record", return_value=_projection_rec("rec16c", "c16c")):
            with patch("tma_api._at_patch", return_value=False):
                with patch("tma_api._audit"), patch("tma_api._notify_owner"):
                    result16c = _act_raw_16("rec16c", identity=_identity())
                    resp16c, code16c = result16c if isinstance(result16c, tuple) else (result16c, 200)

chk("Test16c: HTTP 200 on reject despite sync failure", code16c == 200)
chk("Test16c: JSON body carries projection_sync_pending=true on reject",
    resp16c.json.get("projection_sync_pending") is True)

# 16d. bulk_approve: one of two rows has a sync failure -> count + id list surfaced.
gw16d = _FakeGateway()
gw16d.contracts["c16d1"] = _FakeContract("c16d1")
gw16d.contracts["c16d2"] = _FakeContract("c16d2")

rows16d = {
    "rec16d1": _projection_rec("rec16d1", "c16d1"),
    "rec16d2": _projection_rec("rec16d2", "c16d2"),
}
patch_call_count_16d = {"n": 0}


def _patch_16d(table, rec_id, fields):
    # First projection-sync PATCH (for rec16d1) fails; everything else succeeds.
    patch_call_count_16d["n"] += 1
    return patch_call_count_16d["n"] != 1


with _gateway_patches(gw16d):
    with patch("tma_api._at_list", return_value=[rows16d["rec16d1"], rows16d["rec16d2"]]):
        with patch("tma_api._at_get_record", side_effect=lambda t, rid: rows16d[rid]):
            with patch("tma_api._at_patch", side_effect=_patch_16d):
                with patch("tma_api._audit"), patch("tma_api._notify_owner"):
                    with _app.test_request_context("/api/approvals/bulk", method="POST"):
                        result16d = _bulk_raw_16(identity=_identity())
                        resp16d = result16d[0] if isinstance(result16d, tuple) else result16d

chk("Test16d: both rows still approved (sync failure doesn't block canonical outcome)",
    resp16d.json.get("approved") == 2)
chk("Test16d: bulk response carries projection_sync_pending count",
    resp16d.json.get("projection_sync_pending") == 1)
chk("Test16d: bulk response carries the specific projection_sync_pending_ids list",
    resp16d.json.get("projection_sync_pending_ids") == ["rec16d1"])


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Phase 4B-2 wiring tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
