#!/usr/bin/env python3
"""
test_pr0c0_tma_approval_truthfulness.py — Regression tests for PR-0C0
(BUG-TMA-APPROVAL-TRUTHFULNESS), updated for Phase 4B-2.

TMA must never report or persist "approved" unless the underlying action
executed successfully. Phase 4B-2 moved that guarantee from a raw
CONTEXT_DATA payload deserialized and dispatched directly out of tma_api.py
into core.action_gateway.action_gateway.approve() -> _execute_contract(),
which is itself covered by extensive dedicated tests (test_action_gateway.py,
test_stage_b_full_suite.py, etc.). What remains specific to tma_api.py, and
what this file covers:

  1. _try_bus_action: real sync -> True; "miss" strings (not found / no
     subscriber / restart-lost in-memory item) -> False, never raises.
  2. _try_bus_action: unexpected exception from event_bus -> False, not raised.
  3. bulk_approve: low-risk, contract-linked record is actually routed
     through action_gateway.approve() before being counted as approved.
  4. bulk_approve: a contract that ends up "failed" keeps the record out of
     "approved" and puts it in "failed" — never a bare status flip with no
     execution (the original PR-0C0 bug).
  5. bulk_approve: never touches high/medium risk records (hard rule),
     and never touches legacy (no action_contract_id) records either
     (Phase 4B-2 audit §8).
  6. _claim_and_execute_approval: an orphaned projection (action_contract_id
     set but no matching canonical contract) is refused, not silently
     treated as success.
  7. Phase 4B-2 follow-up: act_on_approval's approve/reject responses never
     call event_bus at all through the ActionContract-backed flow —
     bus_synced is always False, and _try_bus_action is never invoked, even
     if it would have returned True (Approvals.CONTEXT_ID is projection
     data, not a live event_bus action_id).
"""

from __future__ import annotations

import os
import sys
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
from airtable_schema import ApprovalsFields, ApprovalStatus

_bulk_raw = _tma.bulk_approve.__wrapped__

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
    return SimpleNamespace(is_owner=True, user_id="owner_1", display_name="Owner", role="owner")


def _bulk(identity) -> dict:
    with _app.test_request_context("/api/approvals/bulk", method="POST"):
        result = _bulk_raw(identity=identity)
        resp = result[0] if isinstance(result, tuple) else result
        return resp.json


# ── Fake ActionGateway (same pattern as test_approval_concurrency.py) ──

class _FakeContract:
    def __init__(self, contract_id: str, status: str = "pending"):
        self.contract_id = contract_id
        self.status = status


class _FakeRepository:
    """Non-None sentinel — presence alone signals durable persistence available."""


class _FakeLedger:
    def __init__(self):
        self._repository = _FakeRepository()


class _FakeGateway:
    def __init__(self):
        self._ledger = _FakeLedger()
        self.contracts: dict[str, _FakeContract] = {}
        self.approve_calls: list[str] = []
        # per-contract_id outcome override; default "completed"
        self.outcomes: dict[str, str] = {}

    def find_contract(self, contract_id):
        return self.contracts.get(contract_id)

    def approve(self, contract_id, approver, approver_role=""):
        self.approve_calls.append(contract_id)
        c = self.contracts.get(contract_id)
        if c is None:
            return "⚠️ פעולה לא נמצאה."
        if c.status != "pending":
            return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
        outcome = self.outcomes.get(contract_id, "completed")
        c.status = outcome
        if outcome in ("completed", "executed"):
            return "✅ בוצע: test"
        return "❌ ביצוע נכשל: simulated failure"

    def reject(self, contract_id, rejected_by=""):
        c = self.contracts.get(contract_id)
        if c is None:
            return "⚠️ פעולה לא נמצאה."
        if c.status != "pending":
            return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
        c.status = "rejected"
        return "🚫 הפעולה בוטלה."


def _patched(gateway, at_list=None, at_get_record=None, at_patch=None, extra=()) -> ExitStack:
    stack = ExitStack()
    cms = [
        patch("core.action_gateway.action_gateway", gateway),
        patch("core.database.get_pool", return_value=object()),
        patch("feature_flags.is_enabled", return_value=True),
        patch("tma_api._try_bus_action", return_value=False),
        patch("tma_api._audit"),
        patch("tma_api._notify_owner"),
        *extra,
    ]
    if at_list is not None:
        cms.append(patch("tma_api._at_list", return_value=at_list))
    if at_get_record is not None:
        cms.append(patch("tma_api._at_get_record", side_effect=at_get_record))
    if at_patch is not None:
        cms.append(patch("tma_api._at_patch", side_effect=at_patch))
    for cm in cms:
        stack.enter_context(cm)
    return stack


def _rec(rec_id: str, contract_id: str = "", risk: str = "low", legacy: bool = False) -> dict:
    return {
        "id": rec_id,
        "fields": {
            ApprovalsFields.STATUS:              ApprovalStatus.PENDING,
            ApprovalsFields.ACTION:                "add lead",
            ApprovalsFields.RISK_LEVEL:            risk,
            ApprovalsFields.CONTEXT_ID:            f"ctx_{rec_id}",
            ApprovalsFields.CONTEXT_DATA:          "",
            ApprovalsFields.ACTION_CONTRACT_ID:    "" if legacy else (contract_id or f"c_{rec_id}"),
            ApprovalsFields.LEGACY_READ_ONLY:      legacy,
        },
    }


# ══════════════════════════════════════════════════════════════════
# 1. _try_bus_action: miss strings → False, never raises
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: _try_bus_action miss strings ─────────────────────")

_fake_bus = MagicMock()

for miss_msg in [
    "⚠️ הפעולה פגה או לא נמצאה.",          # confirm(): not found (e.g. restart lost in-memory item)
    "⚠️ אין handler לפעולה זו — הפעולה לא בוצעה.",  # confirm(): no .confirmed subscriber
]:
    _fake_bus.confirm = MagicMock(return_value=miss_msg)
    with patch.dict(sys.modules, {"event_bus": types.SimpleNamespace(bus=_fake_bus)}):
        result = _tma._try_bus_action("ctx_missing", "approve")
    chk(f"Test1: miss '{miss_msg[:20]}...' → False", result is False)

_fake_bus.reject = MagicMock(return_value="⚠️ הפעולה כבר לא קיימת.")
with patch.dict(sys.modules, {"event_bus": types.SimpleNamespace(bus=_fake_bus)}):
    result = _tma._try_bus_action("ctx_missing", "reject")
chk("Test1: reject-miss → False", result is False)

chk("Test1: empty context_id → False without calling bus", _tma._try_bus_action("", "approve") is False)


# ══════════════════════════════════════════════════════════════════
# 2. _try_bus_action: real sync → True; exception → False, not raised
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: _try_bus_action real sync / exception safety ─────")

_fake_bus.confirm = MagicMock(return_value="✅ בוצע בהצלחה")
with patch.dict(sys.modules, {"event_bus": types.SimpleNamespace(bus=_fake_bus)}):
    result = _tma._try_bus_action("ctx_real", "approve")
chk("Test2: real event_bus result → True", result is True)

_fake_bus.confirm = MagicMock(side_effect=RuntimeError("boom"))
with patch.dict(sys.modules, {"event_bus": types.SimpleNamespace(bus=_fake_bus)}):
    try:
        result = _tma._try_bus_action("ctx_err", "approve")
        raised = False
    except Exception:
        raised = True
        result = None
chk("Test2: exception from event_bus does not propagate", raised is False)
chk("Test2: exception from event_bus → False", result is False)


# ══════════════════════════════════════════════════════════════════
# 3. bulk_approve: low-risk, contract-linked record is actually routed
#    through action_gateway.approve() before being counted as approved
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: bulk_approve routes through action_gateway.approve() ──")

gw3 = _FakeGateway()
gw3.contracts["c_recA"] = _FakeContract("c_recA")
gw3.outcomes["c_recA"] = "completed"

with _patched(gw3, at_list=[_rec("recA")], at_get_record=lambda t, rid: _rec("recA"),
              at_patch=lambda t, rid, fields: True):
    resp = _bulk(_owner())

chk("Test3: action_gateway.approve() was actually called", gw3.approve_calls == ["c_recA"])
chk("Test3: contract ended completed", gw3.contracts["c_recA"].status == "completed")
chk("Test3: approved count is 1", resp.get("approved") == 1)
chk("Test3: response has failed/skipped keys", "failed" in resp and "skipped" in resp)


# ══════════════════════════════════════════════════════════════════
# 4. bulk_approve: contract ends failed → failed bucket, not approved
#    (the original PR-0C0 bug: a bare status flip with no real execution)
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: bulk_approve failure → failed bucket, never approved ─")

gw4 = _FakeGateway()
gw4.contracts["c_recB"] = _FakeContract("c_recB")
gw4.outcomes["c_recB"] = "failed"

patches_recorded: list[dict] = []


def _record_patch(table, rec_id, fields):
    patches_recorded.append(dict(fields))
    return True


with _patched(gw4, at_list=[_rec("recB")], at_get_record=lambda t, rid: _rec("recB"),
              at_patch=_record_patch):
    patches_recorded.clear()
    resp = _bulk(_owner())

statuses = [p.get(ApprovalsFields.STATUS) for p in patches_recorded if ApprovalsFields.STATUS in p]
chk("Test4: approved count is 0", resp.get("approved") == 0)
chk("Test4: failed count is 1", resp.get("failed") == 1)
chk("Test4: record ends at נכשל, never אושר",
    ApprovalStatus.FAILED in statuses and ApprovalStatus.APPROVED not in statuses)


# ══════════════════════════════════════════════════════════════════
# 5. bulk_approve: never touches high/medium risk or legacy records
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: bulk_approve skips high-risk and legacy rows ─────")

gw5 = _FakeGateway()
gw5.contracts["c_recC"] = _FakeContract("c_recC")   # high risk — must never be reached
# recD is contract-linked but legacy_read_only would never be set alongside
# a real contract_id in practice; here we simulate the no-contract-id case.

recs = [
    _rec("recC", risk="high"),
    _rec("recD", legacy=True),   # no action_contract_id — must be skipped
]

with _patched(gw5, at_list=recs, at_get_record=lambda t, rid: None, at_patch=lambda t, rid, f: True):
    resp = _bulk(_owner())

chk("Test5: no contract ever approved", gw5.approve_calls == [])
chk("Test5: both records skipped", resp.get("skipped") == 2)
chk("Test5: approved count is 0", resp.get("approved") == 0)


# ══════════════════════════════════════════════════════════════════
# 6. _claim_and_execute_approval: orphaned projection (contract_id set,
#    no matching canonical contract) is refused, not silently "succeeded"
# ══════════════════════════════════════════════════════════════════
print("\n── Test 6: orphaned projection is refused ────────────────────")

gw6 = _FakeGateway()  # no contracts registered — find_contract() always misses

with _patched(gw6, at_get_record=lambda t, rid: _rec("recE", contract_id="c_missing"),
              at_patch=lambda t, rid, f: True):
    outcome = _tma._claim_and_execute_approval("recE", _owner())

chk("Test6: outcome is not ok", outcome.get("ok") is False)
chk("Test6: status_code is 404 (orphaned reference)", outcome.get("status_code") == 404)
chk("Test6: action_gateway.approve() never called for an orphaned contract", gw6.approve_calls == [])


# ══════════════════════════════════════════════════════════════════
# 7. Phase 4B-2 follow-up: event_bus is never touched by the
#    ActionContract-backed reject flow — bus_synced is always False, even
#    when _try_bus_action is mocked to return True.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 7: event_bus never invoked; bus_synced always False ──")

_act_raw = _tma.act_on_approval.__wrapped__

gw7 = _FakeGateway()
gw7.contracts["c_recE"] = _FakeContract("c_recE")


def _reject_rec() -> dict:
    return _rec("recE", contract_id="c_recE")


# _try_bus_action mocked to return True — if the reject path still called
# it, bus_synced would come back True. It must not.
bus_mock = MagicMock(return_value=True)
with _app.test_request_context("/api/approvals/recE", method="POST", json={"action": "reject"}):
    with _patched(gw7, at_get_record=lambda t, rid: _reject_rec(), at_patch=lambda t, rid, f: True,
                  extra=[patch("tma_api._try_bus_action", bus_mock)]):
        result = _act_raw("recE", identity=_owner())
        resp, code = result if isinstance(result, tuple) else (result, 200)

chk("Test7: bus_synced is False even though _try_bus_action would have returned True",
    resp.json.get("bus_synced") is False)
chk("Test7: _try_bus_action was never called by the reject flow", bus_mock.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PR-0C0 tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
