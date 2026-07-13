#!/usr/bin/env python3
"""
test_pr0c0_tma_approval_truthfulness.py — Regression tests for PR-0C0
(BUG-TMA-APPROVAL-TRUTHFULNESS).

TMA must never report or persist "approved" unless the underlying action
executed successfully. Covers what test_approval_concurrency.py does not:

  1. _try_bus_action: real sync → True; "miss" strings (not found / no
     subscriber / restart-lost in-memory item) → False, never raises.
  2. _try_bus_action: unexpected exception from event_bus → False, not raised.
  3. bulk_approve: low-risk record with a real tma_write payload is actually
     executed via _execute_tma_write before being counted as approved.
  4. bulk_approve: execution failure keeps the record out of "approved" and
     puts it in "failed", instead of the old bug (direct PATCH to אושר with
     no execution at all).
  5. bulk_approve: never touches high/medium risk records (hard rule).
  6. _claim_and_execute_approval: unexpected exception after claim reverts
     the record from מעבד back to ממתין instead of leaving it stuck.
  7. Consistency: act_on_approval's approve/reject responses surface
     bus_synced truthfully (True only on a real event_bus sync).
"""

from __future__ import annotations

import json
import os
import sys
import types
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
# 3. bulk_approve: low-risk record actually executes before "approved"
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: bulk_approve executes tma_write before counting ──")

tma_write_payload = json.dumps({
    "type": "tma_write", "action": "add", "table": "Leads", "op": "post", "fields": {},
})

def _low_risk_rec(rec_id: str, ctx_data: str = "") -> dict:
    return {
        "id": rec_id,
        "fields": {
            ApprovalsFields.STATUS: ApprovalStatus.PENDING,
            ApprovalsFields.ACTION: "add lead",
            "רמת סיכון": "low",
            ApprovalsFields.CONTEXT_ID: f"ctx_{rec_id}",
            ApprovalsFields.CONTEXT_DATA: ctx_data,
        },
    }

execute_calls: list[dict] = []

def _record_execute(payload, identity):
    execute_calls.append(payload)
    return {"ok": True, "record_id": "recNEW1"}

patches_recorded: list[dict] = []

def _record_patch(table, rec_id, fields):
    patches_recorded.append({"rec_id": rec_id, **fields})
    return True

with (
    patch("tma_api._at_list", return_value=[_low_risk_rec("recA", tma_write_payload)]),
    patch("tma_api._at_get_record", side_effect=lambda t, rid: _low_risk_rec("recA", tma_write_payload)),
    patch("tma_api._at_patch", side_effect=_record_patch),
    patch("tma_api._execute_tma_write", side_effect=_record_execute),
    patch("tma_api._try_bus_action", return_value=False),
    patch("tma_api._audit"),
    patch("tma_api._notify_owner"),
):
    execute_calls.clear()
    patches_recorded.clear()
    resp = _bulk(_owner())

chk("Test3: _execute_tma_write was actually called", len(execute_calls) == 1)
chk("Test3: approved count is 1", resp.get("approved") == 1)
chk("Test3: response has failed/skipped keys", "failed" in resp and "skipped" in resp)


# ══════════════════════════════════════════════════════════════════
# 4. bulk_approve: execution failure → failed, not approved (old bug)
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: bulk_approve execution failure → failed bucket ───")

def _failing_execute(payload, identity):
    return {"ok": False, "error": "airtable 422"}

with (
    patch("tma_api._at_list", return_value=[_low_risk_rec("recB", tma_write_payload)]),
    patch("tma_api._at_get_record", side_effect=lambda t, rid: _low_risk_rec("recB", tma_write_payload)),
    patch("tma_api._at_patch", side_effect=_record_patch),
    patch("tma_api._execute_tma_write", side_effect=_failing_execute),
    patch("tma_api._try_bus_action", return_value=False),
    patch("tma_api._audit"),
    patch("tma_api._notify_owner"),
):
    patches_recorded.clear()
    resp = _bulk(_owner())

statuses = [p.get(ApprovalsFields.STATUS) for p in patches_recorded]
chk("Test4: approved count is 0", resp.get("approved") == 0)
chk("Test4: failed count is 1", resp.get("failed") == 1)
chk("Test4: record ends at נכשל, never אושר", ApprovalStatus.APPROVED not in statuses)
chk("Test4: record was claimed (מעבד) before failing", ApprovalStatus.PROCESSING in statuses)


# ══════════════════════════════════════════════════════════════════
# 5. bulk_approve: never touches high/medium risk records
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: bulk_approve skips high/medium risk ──────────────")

def _high_risk_rec(rec_id: str) -> dict:
    return {
        "id": rec_id,
        "fields": {
            ApprovalsFields.STATUS: ApprovalStatus.PENDING,
            ApprovalsFields.ACTION: "delete everything",
            "רמת סיכון": "high",
            ApprovalsFields.CONTEXT_ID: "ctx_high",
            ApprovalsFields.CONTEXT_DATA: "",
        },
    }

claim_calls: list[str] = []

def _tracking_claim(approval_id, identity):
    claim_calls.append(approval_id)
    return {"ok": True, "status_code": 200, "new_status": ApprovalStatus.APPROVED,
            "action_label": "x", "ctx_id": "", "bus_synced": False, "execution_result": None}

with (
    patch("tma_api._at_list", return_value=[_high_risk_rec("recC")]),
    patch("tma_api._claim_and_execute_approval", side_effect=_tracking_claim),
    patch("tma_api._audit"),
    patch("tma_api._notify_owner"),
):
    claim_calls.clear()
    resp = _bulk(_owner())

chk("Test5: high-risk record never claimed/executed", len(claim_calls) == 0)
chk("Test5: high-risk record is skipped", resp.get("skipped") == 1)
chk("Test5: approved count is 0", resp.get("approved") == 0)


# ══════════════════════════════════════════════════════════════════
# 6. _claim_and_execute_approval: exception after claim reverts to ממתין
# ══════════════════════════════════════════════════════════════════
print("\n── Test 6: stuck-PROCESSING recovery on unexpected exception ─")

def _explode_execute(payload, identity):
    raise RuntimeError("network blew up mid-execution")

with (
    patch("tma_api._at_get_record", return_value=_low_risk_rec("recD", tma_write_payload)),
    patch("tma_api._at_patch", side_effect=_record_patch),
    patch("tma_api._execute_tma_write", side_effect=_explode_execute),
):
    patches_recorded.clear()
    outcome = _tma._claim_and_execute_approval("recD", _owner())

statuses = [p.get(ApprovalsFields.STATUS) for p in patches_recorded]
chk("Test6: outcome is not ok", outcome.get("ok") is False)
chk("Test6: claimed (מעבד) then reverted to ממתין, never stuck",
    statuses == [ApprovalStatus.PROCESSING, ApprovalStatus.PENDING])
chk("Test6: never reached אושר", ApprovalStatus.APPROVED not in statuses)


# ══════════════════════════════════════════════════════════════════
# 7. Consistency: act_on_approval surfaces bus_synced truthfully
# ══════════════════════════════════════════════════════════════════
print("\n── Test 7: bus_synced surfaced truthfully on reject ──────────")

_act_raw = _tma.act_on_approval.__wrapped__

def _reject_rec() -> dict:
    return {
        "id": "recE",
        "fields": {
            ApprovalsFields.STATUS: ApprovalStatus.PENDING,
            ApprovalsFields.ACTION: "test",
            ApprovalsFields.CONTEXT_ID: "ctx_e",
            ApprovalsFields.CONTEXT_DATA: "",
        },
    }

with _app.test_request_context("/api/approvals/recE", method="POST", json={"action": "reject"}):
    with (
        patch("tma_api._at_get_record", return_value=_reject_rec()),
        patch("tma_api._at_patch", return_value=True),
        patch("tma_api._try_bus_action", return_value=True),
        patch("tma_api._audit"),
        patch("tma_api._notify_owner"),
    ):
        result = _act_raw("recE", identity=_owner())
        resp, code = result if isinstance(result, tuple) else (result, 200)

chk("Test7: bus_synced True is surfaced in response", resp.json.get("bus_synced") is True)

with _app.test_request_context("/api/approvals/recE", method="POST", json={"action": "reject"}):
    with (
        patch("tma_api._at_get_record", return_value=_reject_rec()),
        patch("tma_api._at_patch", return_value=True),
        patch("tma_api._try_bus_action", return_value=False),
        patch("tma_api._audit"),
        patch("tma_api._notify_owner"),
    ):
        result = _act_raw("recE", identity=_owner())
        resp, code = result if isinstance(result, tuple) else (result, 200)

chk("Test7: bus_synced False is surfaced (not hidden as True)", resp.json.get("bus_synced") is False)


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PR-0C0 tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
