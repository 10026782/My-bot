#!/usr/bin/env python3
# test_c05c07_finding3_single_write_path.py
#
# C05-C07 audit Finding #3 (DUPLICATE_APPROVAL_PATH) remediation.
#
# DECISION — SINGLE BUSINESS WRITE PATH: all meaningful business mutations
# enter through ActionGateway. Owner does not require manual approval for
# their own permitted action, but must not bypass ActionGateway with a
# direct business-data write — Owner policy is auto-approval INSIDE the
# gateway pipeline, not a separate direct-write branch. Manager keeps the
# existing manual approval policy, on the identical pipeline.
#
# Implemented for: tma_api.py::patch_lead / set_lead_outcome / create_lead_task
# via tma_api._queue_or_owner_execute() — both roles call
# _queue_tma_write_approval() (proposes a "tma_write" ActionContract exactly
# as before); Owner alone is then driven through
# _claim_and_execute_approval(), the same claim -> approve -> execute helper
# the manual /api/approvals/<id> click endpoint uses, so Owner never sees a
# manual "approve your own action" step.
#
# Run: python3 test_c05c07_finding3_single_write_path.py
# Pass condition: exit code 0, all assertions green.

from __future__ import annotations

import sys

from flask import Flask

from identity import Role
from airtable_schema import Tables
import tma_api

_passed = 0
_failed = 0


def chk(label: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS: {label}")
    else:
        _failed += 1
        print(f"  FAIL: {label}")


class _FakeIdentity:
    def __init__(self, role):
        self.role = role
        self.display_name = "Test Identity"
        self.user_id = "1"

    @property
    def is_owner(self):
        return self.role == Role.OWNER


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    return app.test_client()


_HDR = {"X-Telegram-Init-Data": "x"}

# ── shared gateway-seam fakes ────────────────────────────────────────────
# _queue_tma_write_approval() and _claim_and_execute_approval() are each
# already covered by their own extensive existing test suites (Phase 4B-2
# wiring, TTL, truthfulness) and are UNCHANGED by this fix — only a new
# caller (_queue_or_owner_execute) composes them. Mocking exactly at that
# seam isolates what actually changed: which endpoints call which of these
# two functions, for which role, and how the result is translated.
_queued_calls: list[tuple[str, dict]] = []
_exec_should_fail = {"value": False}
_direct_patch_tables: list[str] = []
_direct_post_tables: list[str] = []


def _fake_queue(action, payload, identity, label):
    _queued_calls.append((action, dict(payload)))
    return "fake_approval_1", {
        "status": "pending_approval",
        "approval_id": "fake_approval_1",
        "contract_id": "fake_contract_1",
    }, 202


def _fake_claim_execute(approval_id, identity):
    if _exec_should_fail["value"]:
        return {
            "ok": False, "status_code": 500, "error": "execution failed",
            "action_label": "x", "ctx_id": "",
        }
    return {
        "ok": True, "status_code": 200, "new_status": "approved",
        "action_label": "x", "ctx_id": "", "bus_synced": False,
        "execution_result": {"message": "✅", "contract_status": "executed"},
    }


def _tracking_at_patch(table, record_id, fields):
    _direct_patch_tables.append(table)
    return True


def _tracking_at_post(table, fields):
    _direct_post_tables.append(table)
    return {"id": "recAudit"}


_orig_validate = tma_api._validate_initdata
_orig_resolve = tma_api.resolve_identity
_orig_at_patch = tma_api._at_patch
_orig_at_post = tma_api._at_post
_orig_at_get_record = tma_api._at_get_record
_orig_at_list = tma_api._at_list
_orig_queue = tma_api._queue_tma_write_approval
_orig_claim_execute = tma_api._claim_and_execute_approval

client = _make_client()
tma_api._validate_initdata = lambda s: {"id": "1"}
tma_api._at_patch = _tracking_at_patch
tma_api._at_post = _tracking_at_post
tma_api._at_get_record = lambda table, rid: {"id": rid, "fields": {}}
tma_api._at_list = lambda *a, **kw: []
tma_api._queue_tma_write_approval = _fake_queue
tma_api._claim_and_execute_approval = _fake_claim_execute

_OWNER_ENDPOINTS = [
    ("patch_lead",       lambda: client.patch("/api/leads/recLEAD001", json={"status": "active"}, headers=_HDR),
     "tma_patch_lead", "Leads"),
    ("set_lead_outcome", lambda: client.post("/api/leads/recLEAD001/outcome", json={"outcome": "converted"}, headers=_HDR),
     "tma_set_lead_outcome", "Leads"),
    ("create_lead_task", lambda: client.post("/api/leads/recLEAD001/task", json={"title": "call back"}, headers=_HDR),
     "tma_create_lead_task", Tables.TASKS),
]

try:
    print("\n[1+3+4] Owner: canonical ActionGateway path, no manual approval, no direct bypass")
    for name, call, expected_action, expected_table in _OWNER_ENDPOINTS:
        tma_api.resolve_identity = lambda ch, tid: _FakeIdentity(Role.OWNER)
        _queued_calls.clear()
        _direct_patch_tables.clear()
        _direct_post_tables.clear()
        _exec_should_fail["value"] = False

        r = call()
        body = r.get_json() or {}

        chk(f"{name}: owner request succeeds with no pending/manual-approval step",
            r.status_code == 200 and body.get("ok") is True)
        chk(f"{name}: exactly one contract proposed through the canonical ActionGateway pipeline",
            len(_queued_calls) == 1 and _queued_calls[0][0] == expected_action)
        chk(f"{name}: proposed payload targets the expected table",
            _queued_calls[0][1].get("table") == expected_table)
        chk(f"{name}: execution result carries the gateway's evidence/receipt contract",
            "contract_status" in body and body.get("approval_id") == "fake_approval_1")
        chk(f"{name}: never falls back to a direct tma_api._at_patch business write",
            expected_table not in _direct_patch_tables)
        chk(f"{name}: never falls back to a direct tma_api._at_post business write",
            expected_table not in _direct_post_tables)

    print("\n[2] Manager: still requires the existing (unchanged) approval flow")
    for name, call, expected_action, expected_table in _OWNER_ENDPOINTS:
        tma_api.resolve_identity = lambda ch, tid: _FakeIdentity(Role.MANAGER)
        _queued_calls.clear()
        _exec_should_fail["value"] = False

        r = call()
        body = r.get_json() or {}

        chk(f"{name}: manager request is queued (202), never auto-executed",
            r.status_code == 202 and body.get("status") == "pending_approval")
        chk(f"{name}: manager request proposes the same canonical action/table as owner",
            len(_queued_calls) == 1
            and _queued_calls[0][0] == expected_action
            and _queued_calls[0][1].get("table") == expected_table)

    print("\n[5] Unauthorized/insufficient role: remains fail-closed")
    for name, call, _, _ in _OWNER_ENDPOINTS:
        tma_api.resolve_identity = lambda ch, tid: _FakeIdentity(Role.LEAD)
        _queued_calls.clear()

        r = call()
        chk(f"{name}: insufficient role -> 403 forbidden", r.status_code == 403)
        chk(f"{name}: insufficient role -> gateway never reached", len(_queued_calls) == 0)

    print("\n[6] Failure inside execution must never produce a false success")
    for name, call, _, _ in _OWNER_ENDPOINTS:
        tma_api.resolve_identity = lambda ch, tid: _FakeIdentity(Role.OWNER)
        _queued_calls.clear()
        _exec_should_fail["value"] = True

        r = call()
        body = r.get_json() or {}
        chk(f"{name}: execution failure -> response never claims ok=True", body.get("ok") is not True)
        chk(f"{name}: execution failure -> non-2xx status code", r.status_code >= 400)
        _exec_should_fail["value"] = False
finally:
    tma_api._validate_initdata = _orig_validate
    tma_api.resolve_identity = _orig_resolve
    tma_api._at_patch = _orig_at_patch
    tma_api._at_post = _orig_at_post
    tma_api._at_get_record = _orig_at_get_record
    tma_api._at_list = _orig_at_list
    tma_api._queue_tma_write_approval = _orig_queue
    tma_api._claim_and_execute_approval = _orig_claim_execute


print(f"\n{'=' * 60}")
print(f"C05-C07 Finding #3 (single write path): {_passed}/{_passed + _failed} passed")
if _failed:
    print(f"FAILED: {_failed} check(s)")
sys.exit(0 if _failed == 0 else 1)
