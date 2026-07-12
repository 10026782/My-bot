#!/usr/bin/env python3
"""
test_approval_concurrency.py — Regression tests for act_on_approval 3-state flow.

Tests:
  1. Normal approve: ממתין → מעבד → אושר
  2. Normal reject: ממתין → נדחה (single PATCH, no execution)
  3. Execution failure: ממתין → מעבד → נכשל (status set to נכשל, 500 returned)
  4. Double-approve concurrency: second request sees מעבד → 409, action executes once
"""

from __future__ import annotations

import json
import os
import sys
import threading
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
from tma_api import _get_approval_lock, _APPROVAL_LOCKS
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


def _approval_rec(status: str, context_data: str = "") -> dict:
    return {
        "id": "recTEST123",
        "fields": {
            ApprovalsFields.STATUS:       status,
            ApprovalsFields.ACTION:       "test_action",
            ApprovalsFields.CONTEXT_ID:   "ctx_1",
            ApprovalsFields.CONTEXT_DATA: context_data,
        },
    }


# ══════════════════════════════════════════════════════════════════
# 1. Normal approve — no tma_write payload
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: Normal approve ───────────────────────────────────")

patches_recorded: list[dict] = []

def _record_patch(table, rec_id, fields):
    patches_recorded.append(dict(fields))
    return True

with _app.test_request_context(
    "/api/approvals/recTEST123",
    method="POST",
    json={"action": "approve"},
):
    with (
        patch("tma_api._at_get_record", return_value=_approval_rec(ApprovalStatus.PENDING)),
        patch("tma_api._at_patch", side_effect=_record_patch),
        patch("tma_api._try_bus_action", return_value=False),
        patch("tma_api._audit"),
        patch("tma_api._notify_owner"),
    ):
        patches_recorded.clear()
        resp, code = _act("recTEST123", identity=_owner())

statuses = [p.get(ApprovalsFields.STATUS) for p in patches_recorded]
chk("Test1: HTTP 200", code == 200)
chk("Test1: first PATCH is מעבד (claim)",  statuses[0] == ApprovalStatus.PROCESSING)
chk("Test1: second PATCH is אושר (finalize)", statuses[-1] == ApprovalStatus.APPROVED)
chk("Test1: exactly 2 PATCHes",           len(patches_recorded) == 2)


# ══════════════════════════════════════════════════════════════════
# 2. Normal reject — single PATCH, no execution
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: Normal reject ────────────────────────────────────")

with _app.test_request_context(
    "/api/approvals/recTEST123",
    method="POST",
    json={"action": "reject", "note": "not needed"},
):
    with (
        patch("tma_api._at_get_record", return_value=_approval_rec(ApprovalStatus.PENDING)),
        patch("tma_api._at_patch", side_effect=_record_patch),
        patch("tma_api._try_bus_action", return_value=False),
        patch("tma_api._audit"),
        patch("tma_api._notify_owner"),
    ):
        patches_recorded.clear()
        resp, code = _act("recTEST123", identity=_owner())

statuses = [p.get(ApprovalsFields.STATUS) for p in patches_recorded]
chk("Test2: HTTP 200",          code == 200)
chk("Test2: exactly 1 PATCH",  len(patches_recorded) == 1)
chk("Test2: PATCH is נדחה",    statuses[0] == ApprovalStatus.REJECTED)


# ══════════════════════════════════════════════════════════════════
# 3. Execution failure → status becomes נכשל, not אושר
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: Execution failure → נכשל ─────────────────────────")

tma_write_payload = json.dumps({
    "type": "tma_write", "action": "add",
    "table": "Leads", "op": "post", "fields": {},
})

with _app.test_request_context(
    "/api/approvals/recTEST123",
    method="POST",
    json={"action": "approve"},
):
    with (
        patch("tma_api._at_get_record",   return_value=_approval_rec(ApprovalStatus.PENDING, tma_write_payload)),
        patch("tma_api._at_patch",        side_effect=_record_patch),
        patch("tma_api._execute_tma_write", return_value={"ok": False, "error": "timeout"}),
        patch("tma_api._try_bus_action", return_value=False),
        patch("tma_api._audit"),
        patch("tma_api._notify_owner"),
    ):
        patches_recorded.clear()
        resp, code = _act("recTEST123", identity=_owner())

statuses = [p.get(ApprovalsFields.STATUS) for p in patches_recorded]
chk("Test3: HTTP 500 on failure",               code == 500)
chk("Test3: first PATCH is מעבד (claim)",        statuses[0]  == ApprovalStatus.PROCESSING)
chk("Test3: last PATCH is נכשל, not אושר",      statuses[-1] == ApprovalStatus.FAILED)
chk("Test3: אושר never written",                ApprovalStatus.APPROVED not in statuses)


# ══════════════════════════════════════════════════════════════════
# 4. Double-approve concurrency — executes exactly once
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: Double-approve → executes once ───────────────────")

# Simulated Airtable: first claim transitions PENDING → PROCESSING;
# second concurrent re-read sees PROCESSING → returns 409.
_at_state: dict[str, str] = {"status": ApprovalStatus.PENDING}
_claim_lock = threading.Lock()   # guard _at_state transitions in this test

def _stateful_get(table, rec_id):
    with _claim_lock:
        return {
            "id": rec_id,
            "fields": {
                ApprovalsFields.STATUS:       _at_state["status"],
                ApprovalsFields.ACTION:       "test_action",
                ApprovalsFields.CONTEXT_ID:   "ctx_1",
                ApprovalsFields.CONTEXT_DATA: "",
            },
        }

def _stateful_patch(table, rec_id, fields):
    new_status = fields.get(ApprovalsFields.STATUS)
    if new_status:
        with _claim_lock:
            _at_state["status"] = new_status
    return True

result_codes: list[int] = []

def _run_approve():
    with _app.test_request_context(
        "/api/approvals/recTEST456",
        method="POST",
        json={"action": "approve"},
    ):
        with (
            patch("tma_api._at_get_record", side_effect=_stateful_get),
            patch("tma_api._at_patch",      side_effect=_stateful_patch),
            patch("tma_api._try_bus_action", return_value=False),
            patch("tma_api._audit"),
            patch("tma_api._notify_owner"),
        ):
            _, code = _act("recTEST456", identity=_owner())
            result_codes.append(code)

# Reset state
_at_state["status"] = ApprovalStatus.PENDING
_APPROVAL_LOCKS.pop("recTEST456", None)

t1 = threading.Thread(target=_run_approve)
t2 = threading.Thread(target=_run_approve)
t1.start(); t2.start()
t1.join();  t2.join()

chk("Test4: exactly one 200 (approved)",          result_codes.count(200) == 1)
chk("Test4: exactly one 409 (double-claim blocked)", result_codes.count(409) == 1)
chk("Test4: final Airtable status is אושר",       _at_state["status"] == ApprovalStatus.APPROVED)


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Approval tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
