#!/usr/bin/env python3
"""
test_approval_concurrency.py — Regression tests for act_on_approval's
Phase 4B-2 claim flow: Approvals row -> canonical ActionContract ->
action_gateway.approve()/reject() -> re-read -> projection sync.

Phase 4B-2 replaced the old 3-state Airtable-PATCH claim (ממתין -> מעבד ->
אושר/נכשל, driven by a raw CONTEXT_DATA payload deserialized and executed
directly from tma_api.py) with: Approvals is a non-authoritative projection
of ActionContracts; execution is driven entirely by
core.action_gateway.action_gateway.approve()/reject(), which themselves
acquire the PostgreSQL atomic claim before any dispatch (see
core/action_gateway.py::_execute_contract). The per-approval_id
threading.Lock here only closes a same-process race window around the
claim-check-then-approve sequence; it is not the execution-ownership
primitive.

Tests:
  1. Normal approve: canonical contract pending -> completed via approve();
     projection fields (not CONTEXT_DATA) get synced.
  2. Normal reject: canonical contract pending -> rejected via reject();
     single projection sync, no execution attempted.
  3. Execution failure: approve() drives the contract to "failed"; response
     is 500, projection reflects failed — never marked approved.
  4. Double-approve concurrency: two concurrent requests for the same
     Approvals row — exactly one succeeds (200), the other sees the
     contract already resolved (409); action_gateway.approve() is called
     at most twice but only the first actually transitions the contract.
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

# ── Import module under test ───────────────────────────────────────
import tma_api as _tma
from tma_api import _APPROVAL_LOCKS
from airtable_schema import ApprovalsFields, ApprovalStatus

# Get the raw function, bypassing @require_tma_auth and @tma_api.route decorators.
# @wraps preserves __wrapped__ pointing to the original.
_act_raw = _tma.act_on_approval.__wrapped__


def _act(approval_id: str, identity) -> tuple:
    """Normalize Flask view return to always be (response, code)."""
    result = _act_raw(approval_id, identity=identity)
    if isinstance(result, tuple):
        return result
    return result, 200

# Minimal Flask app for request context
from flask import Flask as _Flask
_app = _Flask(__name__)
_app.register_blueprint(_tma.tma_api)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _owner() -> SimpleNamespace:
    return SimpleNamespace(
        is_owner=True,
        user_id="owner_1",
        display_name="Owner",
        role="owner",
    )


def _approval_rec(contract_id: str = "c1", legacy: bool = False) -> dict:
    return {
        "id": "recTEST123",
        "fields": {
            ApprovalsFields.STATUS:              ApprovalStatus.PENDING,
            ApprovalsFields.ACTION:               "test_action",
            ApprovalsFields.CONTEXT_ID:            "ctx_1",
            ApprovalsFields.CONTEXT_DATA:          "",  # Phase 4B-2: always empty for contract-linked rows
            ApprovalsFields.ACTION_CONTRACT_ID:    "" if legacy else contract_id,
            ApprovalsFields.LEGACY_READ_ONLY:      legacy,
        },
    }


# ── Fake ActionGateway: full control over contract lifecycle, no Airtable ──

class _FakeContract:
    def __init__(self, contract_id: str, status: str = "pending"):
        self.contract_id = contract_id
        self.status = status
        # Phase 4B-2 follow-up: _is_canonical_tma_contract() reads these
        # directly — defaults match this file's tma_write happy path and
        # _owner()'s identity, which has no tenant_id attribute at all
        # (getattr(..., "tenant_id", None) is None), so tenant_id here is
        # None too rather than a real tenant string.
        self.approval_policy = "approval"
        self.tool_name = "tma_write"
        self.trusted_source = "tma_api"
        self.origin_channel = "tma"
        self.tenant_id = None


class _FakeRepository:
    """Non-None sentinel — presence alone signals durable persistence available."""


class _FakeLedger:
    def __init__(self):
        self._repository = _FakeRepository()


class _FakeGateway:
    """Deterministic stand-in for core.action_gateway.action_gateway.

    approve_outcome / reject_outcome control what state approve()/reject()
    drive the contract to, so each test can force completed/failed/
    outcome_unknown without touching real dispatch/Airtable/PostgreSQL.
    """
    def __init__(self):
        self._ledger = _FakeLedger()
        self.contracts: dict[str, _FakeContract] = {}
        self.approve_calls: list[str] = []
        self.reject_calls: list[str] = []
        self.approve_outcome = "completed"   # or "failed" / "outcome_unknown"
        self._lock = threading.Lock()

    def find_contract(self, contract_id):
        return self.contracts.get(contract_id)

    def approve(self, contract_id, approver, approver_role=""):
        with self._lock:
            self.approve_calls.append(contract_id)
            c = self.contracts.get(contract_id)
            if c is None:
                return "⚠️ פעולה לא נמצאה."
            if c.status != "pending":
                return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
            c.status = self.approve_outcome
        if self.approve_outcome in ("completed", "executed"):
            return "✅ בוצע: test_action"
        if self.approve_outcome == "outcome_unknown":
            return "⚠️ תוצאת הפעולה אינה ידועה. אין לנסות שוב אוטומטית."
        return "❌ ביצוע נכשל: simulated failure"

    def reject(self, contract_id, rejected_by=""):
        with self._lock:
            self.reject_calls.append(contract_id)
            c = self.contracts.get(contract_id)
            if c is None:
                return "⚠️ פעולה לא נמצאה."
            if c.status != "pending":
                return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
            c.status = "rejected"
        return "🚫 הפעולה בוטלה."


def _patched(gateway: _FakeGateway, at_get_record, at_patch, extra=()) -> ExitStack:
    """Standard patch set, entered: fake gateway + durable/atomic-claims
    available + Airtable record fetch/patch. Returns an entered ExitStack —
    caller is responsible for using it as a context manager."""
    stack = ExitStack()
    for cm in (
        patch("core.action_gateway.action_gateway", gateway),
        patch("core.database.get_pool", return_value=object()),
        patch("feature_flags.is_enabled", return_value=True),
        patch("tma_api._at_get_record", side_effect=at_get_record),
        patch("tma_api._at_patch", side_effect=at_patch),
        patch("tma_api._try_bus_action", return_value=False),
        patch("tma_api._audit"),
        patch("tma_api._notify_owner"),
        *extra,
    ):
        stack.enter_context(cm)
    return stack


# ══════════════════════════════════════════════════════════════════
# 1. Normal approve — canonical contract pending -> completed
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: Normal approve ───────────────────────────────────")

patches_recorded: list[dict] = []


def _record_patch(table, rec_id, fields):
    patches_recorded.append(dict(fields))
    return True


gw1 = _FakeGateway()
gw1.contracts["c1"] = _FakeContract("c1")
gw1.approve_outcome = "completed"

with _app.test_request_context(
    "/api/approvals/recTEST123", method="POST", json={"action": "approve"},
):
    with _patched(gw1, lambda t, rid: _approval_rec("c1"), _record_patch):
        patches_recorded.clear()
        resp, code = _act("recTEST123", identity=_owner())

chk("Test1: HTTP 200", code == 200)
chk("Test1: action_gateway.approve() called exactly once", gw1.approve_calls == ["c1"])
chk("Test1: contract ended completed", gw1.contracts["c1"].status == "completed")
chk("Test1: projected_lifecycle_status synced to completed",
    any(p.get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS) == "completed" for p in patches_recorded))
chk("Test1: legacy STATUS synced to אושר",
    any(p.get(ApprovalsFields.STATUS) == ApprovalStatus.APPROVED for p in patches_recorded))
chk("Test1: CONTEXT_DATA never written by the sync",
    not any(ApprovalsFields.CONTEXT_DATA in p for p in patches_recorded))


# ══════════════════════════════════════════════════════════════════
# 2. Normal reject — single sync, no execution
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: Normal reject ────────────────────────────────────")

gw2 = _FakeGateway()
gw2.contracts["c2"] = _FakeContract("c2")

with _app.test_request_context(
    "/api/approvals/recTEST123", method="POST", json={"action": "reject", "note": "not needed"},
):
    with _patched(gw2, lambda t, rid: _approval_rec("c2"), _record_patch):
        patches_recorded.clear()
        resp, code = _act("recTEST123", identity=_owner())

chk("Test2: HTTP 200", code == 200)
chk("Test2: action_gateway.reject() called, approve() never called",
    gw2.reject_calls == ["c2"] and gw2.approve_calls == [])
chk("Test2: contract ended rejected", gw2.contracts["c2"].status == "rejected")
chk("Test2: legacy STATUS synced to נדחה",
    any(p.get(ApprovalsFields.STATUS) == ApprovalStatus.REJECTED for p in patches_recorded))


# ══════════════════════════════════════════════════════════════════
# 3. Execution failure -> נכשל, never אושר
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: Execution failure → נכשל ─────────────────────────")

gw3 = _FakeGateway()
gw3.contracts["c3"] = _FakeContract("c3")
gw3.approve_outcome = "failed"

with _app.test_request_context(
    "/api/approvals/recTEST123", method="POST", json={"action": "approve"},
):
    with _patched(gw3, lambda t, rid: _approval_rec("c3"), _record_patch):
        patches_recorded.clear()
        resp, code = _act("recTEST123", identity=_owner())

chk("Test3: HTTP 500 on failure", code == 500)
chk("Test3: contract ended failed", gw3.contracts["c3"].status == "failed")
chk("Test3: projected_lifecycle_status synced to failed",
    any(p.get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS) == "failed" for p in patches_recorded))
chk("Test3: legacy STATUS synced to נכשל, never אושר",
    any(p.get(ApprovalsFields.STATUS) == ApprovalStatus.FAILED for p in patches_recorded)
    and not any(p.get(ApprovalsFields.STATUS) == ApprovalStatus.APPROVED for p in patches_recorded))


# ══════════════════════════════════════════════════════════════════
# 4. Double-approve concurrency — executes exactly once
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: Double-approve → executes once ───────────────────")

gw4 = _FakeGateway()
gw4.contracts["c4"] = _FakeContract("c4")
gw4.approve_outcome = "completed"

_APPROVAL_LOCKS.pop("recTEST456", None)
result_codes: list[int] = []


def _run_approve():
    with _app.test_request_context(
        "/api/approvals/recTEST456", method="POST", json={"action": "approve"},
    ):
        with _patched(gw4, lambda t, rid: _approval_rec("c4"), _record_patch):
            _, code = _act("recTEST456", identity=_owner())
            result_codes.append(code)


t1 = threading.Thread(target=_run_approve)
t2 = threading.Thread(target=_run_approve)
t1.start(); t2.start()
t1.join();  t2.join()

chk("Test4: exactly one 200 (approved)", result_codes.count(200) == 1)
chk("Test4: the other sees already-resolved (409)", result_codes.count(409) == 1)
chk("Test4: contract executed exactly once (completed, not double-run)",
    gw4.contracts["c4"].status == "completed")
chk("Test4: action_gateway.approve() called at most twice, contract only transitions once",
    len(gw4.approve_calls) <= 2)


# ══════════════════════════════════════════════════════════════════
# 5. Legacy row (no action_contract_id) — refused, never touches the gateway
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: Legacy row is refused, not executed ──────────────")

gw5 = _FakeGateway()

with _app.test_request_context(
    "/api/approvals/recLEGACY", method="POST", json={"action": "approve"},
):
    with _patched(gw5, lambda t, rid: _approval_rec(legacy=True), _record_patch):
        resp, code = _act("recLEGACY", identity=_owner())

chk("Test5: HTTP 409 for legacy row", code == 409)
chk("Test5: action_gateway.approve() never called for a legacy row", gw5.approve_calls == [])


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Approval tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
