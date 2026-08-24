#!/usr/bin/env python3
# test_bug104_tma_lead_event_bridge.py
# BUG-104 — TMA Lead Event Bridge
#
# Run: python3 test_bug104_tma_lead_event_bridge.py
# Pass condition: exit code 0, all assertions green.
#
# Covers core/lead_event_writer.py and its two wiring points:
#   - tma_api.py::patch_lead / set_lead_outcome (owner-immediate path)
#   - tools/approval_actions.py::tma_write() (Manager-approved path, also
#     covers update_lead_status which always goes through approval)
#
# Explicitly OUT of scope (per owner decision — no code here touches these):
# Airtable schema changes, domain slug mapping, backfill of historical
# records, Phase 2A, Core Reasoning engine changes, new feature flags,
# response-contract changes.

from __future__ import annotations

import json
import os
import sys

_passed = 0
_failed = 0


def check(label: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ✅ {label}")
    else:
        _failed += 1
        print(f"  ❌ {label}")


# ═════════════════════════════════════════════════════════════════
# 1. core.lead_event_writer.write_tma_lead_event — direct unit tests
# ═════════════════════════════════════════════════════════════════
print("\n[1] write_tma_lead_event — direct unit tests")

import tools.airtable_gateway as airtable_gateway
import tools.airtable_read_adapter as airtable_read_adapter
from core.lead_event_writer import write_tma_lead_event
from airtable_schema import LeadEventFields, LeadEventType, Tables, LeadFields

_orig_create = airtable_gateway.airtable_create
_orig_get_record_fields = airtable_read_adapter.get_record_fields

_created: list[dict] = []
_create_should_fail = {"value": False}
_create_should_raise = {"value": False}
_domain_lookup_calls = {"n": 0}
_domain_lookup_return = {"value": {LeadFields.DOMAIN: "recruitment"}}


def _fake_create(table, fields, source="unknown"):
    if _create_should_raise["value"]:
        raise RuntimeError("boom")
    if table != Tables.LEAD_EVENTS:
        return {"id": "recOTHER", "fields": fields}
    if _create_should_fail["value"]:
        return None
    _created.append({"table": table, "fields": fields, "source": source})
    return {"id": f"recEV{len(_created)}", "fields": fields}


def _fake_get_record_fields(table, record_id, **kwargs):
    _domain_lookup_calls["n"] += 1
    if table == "Leads":
        return _domain_lookup_return["value"]
    return {}


airtable_gateway.airtable_create = _fake_create
airtable_read_adapter.get_record_fields = _fake_get_record_fields

try:
    # -- success path, domain read via one extra Airtable call --
    _created.clear()
    _domain_lookup_calls["n"] = 0
    ok = write_tma_lead_event("recLEAD001", "lead_patch", {"status": "active"})
    check("success path returns True", ok is True)
    check("exactly one Lead Events record created", len(_created) == 1)
    check("Lead link = [lead_id]", _created[0]["fields"][LeadEventFields.LEAD_LINK] == ["recLEAD001"])
    check("Channel is literal 'tma'", _created[0]["fields"][LeadEventFields.CHANNEL] == "tma")
    check("Event Type is 'other'", _created[0]["fields"][LeadEventFields.EVENT_TYPE] == LeadEventType.OTHER)
    check("domain resolved via exactly one extra read when not supplied", _domain_lookup_calls["n"] == 1)
    check("domain 'recruitment' passed through as-is", _created[0]["fields"][LeadEventFields.DOMAIN] == "recruitment")

    # -- domain passthrough: real_estate --
    _created.clear()
    _domain_lookup_return["value"] = {LeadFields.DOMAIN: "real_estate"}
    write_tma_lead_event("recL2", "lead_patch", {"status": "active"})
    check("domain 'real_estate' passes through unchanged", _created[0]["fields"][LeadEventFields.DOMAIN] == "real_estate")

    # -- domain passthrough: saas --
    _created.clear()
    _domain_lookup_return["value"] = {LeadFields.DOMAIN: "saas"}
    write_tma_lead_event("recL3", "lead_patch", {"status": "active"})
    check("domain 'saas' passes through unchanged", _created[0]["fields"][LeadEventFields.DOMAIN] == "saas")

    # -- domain passthrough: import --
    _created.clear()
    _domain_lookup_return["value"] = {LeadFields.DOMAIN: "import"}
    write_tma_lead_event("recL4", "lead_patch", {"status": "active"})
    check("domain 'import' passes through unchanged", _created[0]["fields"][LeadEventFields.DOMAIN] == "import")

    # -- missing domain field entirely -> general --
    _created.clear()
    _domain_lookup_return["value"] = {}
    write_tma_lead_event("recL5", "lead_patch", {"status": "active"})
    check("missing domain -> general fallback", _created[0]["fields"][LeadEventFields.DOMAIN] == "general")

    # -- unrecognized raw domain (e.g. a project_slug value) -> general, no invented option --
    _created.clear()
    _domain_lookup_return["value"] = {LeadFields.DOMAIN: "blueview"}
    write_tma_lead_event("recL6", "lead_patch", {"status": "active"})
    check("unrecognized domain value ('blueview') -> general fallback, not invented",
          _created[0]["fields"][LeadEventFields.DOMAIN] == "general")

    # -- explicit lead_domain supplied -> no extra read, normalized (strip/lower) --
    _created.clear()
    _domain_lookup_calls["n"] = 0
    write_tma_lead_event("recL7", "lead_patch", {"status": "active"}, lead_domain="  SAAS  ")
    check("explicit lead_domain normalized via strip().lower()", _created[0]["fields"][LeadEventFields.DOMAIN] == "saas")
    check("explicit lead_domain -> zero extra Airtable reads", _domain_lookup_calls["n"] == 0)

    # -- deterministic applied_fields serialization (sorted keys) --
    _created.clear()
    _domain_lookup_return["value"] = {LeadFields.DOMAIN: "general"}
    write_tma_lead_event("recL8", "lead_patch", {"z_field": 1, "a_field": "x"})
    msg1 = _created[0]["fields"][LeadEventFields.MESSAGE]
    _created.clear()
    write_tma_lead_event("recL8", "lead_patch", {"a_field": "x", "z_field": 1})
    msg2 = _created[0]["fields"][LeadEventFields.MESSAGE]
    check("applied_fields serialization is order-independent (sorted keys)", msg1 == msg2)
    check("serialized message contains both field names", "a_field" in msg1 and "z_field" in msg1)
    check("message does not claim an old->new transition (no '->' token)", "->" not in msg1)

    # -- create() failure -> False, never raises --
    _created.clear()
    _create_should_fail["value"] = True
    ok_fail = write_tma_lead_event("recL9", "lead_patch", {"status": "active"})
    check("Airtable create failure -> returns False", ok_fail is False)
    _create_should_fail["value"] = False

    # -- create() raising -> False, never propagates --
    _create_should_raise["value"] = True
    raised = False
    try:
        ok_exc = write_tma_lead_event("recL10", "lead_patch", {"status": "active"})
    except Exception:
        raised = True
        ok_exc = None
    check("writer never raises even when the Airtable call raises", raised is False)
    check("exception path returns False", ok_exc is False)
    _create_should_raise["value"] = False

    # -- LEAD_CAPTURE independence --
    import feature_flags
    os.environ["LEAD_CAPTURE"] = ""  # ensure disabled/unset
    _created.clear()
    _domain_lookup_return["value"] = {LeadFields.DOMAIN: "general"}
    ok_no_flag = write_tma_lead_event("recL11", "lead_patch", {"status": "active"})
    check("LEAD_CAPTURE disabled/unset -> writer still succeeds (no dependency)",
          ok_no_flag is True and len(_created) == 1)
    _writer_src = open("core/lead_event_writer.py", encoding="utf-8").read()
    check("write_tma_lead_event never imports lead_capture",
          "import lead_capture" not in _writer_src and "from lead_capture" not in _writer_src)
    check("write_tma_lead_event never gates on is_enabled(\"LEAD_CAPTURE\")",
          'is_enabled("LEAD_CAPTURE")' not in _writer_src and "is_enabled('LEAD_CAPTURE')" not in _writer_src)
finally:
    airtable_gateway.airtable_create = _orig_create
    airtable_read_adapter.get_record_fields = _orig_get_record_fields


# ═════════════════════════════════════════════════════════════════
# 2. tma_api.py — Owner ActionGateway path (C05-C07 Finding #3 remediation)
#
# Owner used to call tma_api._at_patch/_at_post directly ("owner-immediate
# path"), with write_tma_lead_event() called by hand right after. That
# direct-write branch is exactly what Finding #3 flagged
# (DUPLICATE_APPROVAL_PATH) and has been removed: Owner and Manager now both
# enter _queue_or_owner_execute() -> _queue_tma_write_approval() (identical
# for every role) and, for Owner only, _claim_and_execute_approval() — the
# same claim -> approve -> execute helper the manual /api/approvals/<id>
# click endpoint uses. The Lead Event bridge for a Leads patch is therefore
# no longer tma_api.py's concern at all — it lives entirely inside
# tools/approval_actions.py::tma_write(), exercised identically for both
# roles in section [3] below (same audit_action="lead_patch"/"lead_outcome"
# payload shape sent by section 2's endpoints). This section instead proves
# the tma_api.py-level HTTP contract: Owner gets an immediate result with no
# manual approval step, Manager still gets queued, an execution failure
# never reports success, and — the regression this fix specifically
# guards — Owner writes never reach tma_api._at_patch/_at_post directly.
# ═════════════════════════════════════════════════════════════════
print("\n[2] tma_api Owner ActionGateway path (Finding #3)")

from flask import Flask
from identity import Role
import tma_api


class _FakeIdentity:
    def __init__(self, role):
        self.role = role
        self.display_name = "Test Owner"
        self.user_id = "1"

    @property
    def is_owner(self):
        return self.role == Role.OWNER


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    return app.test_client()


_client = _make_client()
_HDR = {"X-Telegram-Init-Data": "x"}

_orig_validate = tma_api._validate_initdata
_orig_resolve = tma_api.resolve_identity
_orig_at_patch = tma_api._at_patch
_orig_at_post = tma_api._at_post
_orig_at_get_record = tma_api._at_get_record
_orig_queue = tma_api._queue_tma_write_approval
_orig_claim_execute = tma_api._claim_and_execute_approval
_orig_at_list = tma_api._at_list

_exec_should_fail = {"value": False}
_queued_calls = []          # (action, payload) captured from every propose
_direct_patch_tables = []   # any table tma_api._at_patch was called with
_direct_post_tables = []    # any table tma_api._at_post was called with (Interaction Log audit excluded below)


def _tracking_at_patch(table, record_id, fields):
    _direct_patch_tables.append(table)
    return True


def _tracking_at_post(table, fields):
    _direct_post_tables.append(table)
    return {"id": "recAudit"}


def _fake_queue(action, payload, identity, label):
    _queued_calls.append((action, dict(payload)))
    return "fake_approval_1", {
        "status": "pending_approval", "approval_id": "fake_approval_1", "contract_id": "fake_contract_1",
    }, 202


def _fake_claim_execute(approval_id, identity):
    if _exec_should_fail["value"]:
        return {"ok": False, "status_code": 500, "error": "execution failed", "action_label": "x", "ctx_id": ""}
    return {
        "ok": True, "status_code": 200, "new_status": "approved",
        "action_label": "x", "ctx_id": "", "bus_synced": False,
        "execution_result": {"message": "✅", "contract_status": "executed"},
    }


tma_api._validate_initdata = lambda s: {"id": "1"}
tma_api.resolve_identity = lambda ch, tid: _FakeIdentity(Role.OWNER)
tma_api._at_patch = _tracking_at_patch
tma_api._at_post = _tracking_at_post
tma_api._queue_tma_write_approval = _fake_queue
tma_api._claim_and_execute_approval = _fake_claim_execute
tma_api._at_list = lambda *a, **kw: []

try:
    # -- 1. Owner patch_lead: canonical ActionGateway path, no manual approval --
    _queued_calls.clear()
    _direct_patch_tables.clear()
    _exec_should_fail["value"] = False
    r = _client.patch("/api/leads/recLEAD001", json={"status": "active"}, headers=_HDR)
    check("owner patch_lead -> 200, no manual approval step", r.status_code == 200)
    check("owner patch_lead -> exactly one contract proposed through the gateway", len(_queued_calls) == 1)
    check("owner patch_lead -> canonical tma_patch_lead action, Leads table, audit_action carried through",
          _queued_calls[0][0] == "tma_patch_lead"
          and _queued_calls[0][1]["table"] == "Leads"
          and _queued_calls[0][1]["audit_action"] == "lead_patch")
    check("owner patch_lead -> never reaches tma_api._at_patch directly (Leads)",
          "Leads" not in _direct_patch_tables)

    # -- 6. Failure inside execution must never produce a false success --
    _queued_calls.clear()
    _exec_should_fail["value"] = True
    r = _client.patch("/api/leads/recLEAD001", json={"status": "active"}, headers=_HDR)
    check("owner patch_lead execution failure -> response never claims ok=True",
          (r.get_json() or {}).get("ok") is not True)
    check("owner patch_lead execution failure -> non-2xx status", r.status_code >= 400)
    _exec_should_fail["value"] = False

    # -- 3. Owner set_lead_outcome: same canonical path, no direct Airtable bypass --
    _queued_calls.clear()
    _direct_patch_tables.clear()
    r = _client.post("/api/leads/recLEAD001/outcome", json={"outcome": "converted"}, headers=_HDR)
    check("owner set_lead_outcome -> 200, no manual approval step", r.status_code == 200)
    check("owner set_lead_outcome -> canonical tma_set_lead_outcome action, audit_action carried through",
          _queued_calls[0][0] == "tma_set_lead_outcome"
          and _queued_calls[0][1]["audit_action"] == "lead_outcome")
    check("owner set_lead_outcome -> never reaches tma_api._at_patch directly (Leads)",
          "Leads" not in _direct_patch_tables)

    _queued_calls.clear()
    _exec_should_fail["value"] = True
    r = _client.post("/api/leads/recLEAD001/outcome", json={"outcome": "converted"}, headers=_HDR)
    check("owner set_lead_outcome execution failure -> response never claims ok=True",
          (r.get_json() or {}).get("ok") is not True)
    check("owner set_lead_outcome execution failure -> non-2xx status", r.status_code >= 400)
    _exec_should_fail["value"] = False

    # -- GET lead -> unaffected by this change (read path, no gateway involvement) --
    tma_api._at_get_record = lambda table, rid: {"id": rid, "fields": {"Name": "x"}}
    _queued_calls.clear()
    r = _client.get("/api/leads/recLEAD001", headers=_HDR)
    check("GET lead -> no contract proposed on the read path", len(_queued_calls) == 0)

    # -- 4. Owner create_lead_task: same canonical path, no direct Airtable bypass --
    tma_api._at_get_record = lambda table, rid: {"id": rid, "fields": {}}
    _queued_calls.clear()
    _direct_post_tables.clear()
    r = _client.post("/api/leads/recLEAD001/task", json={"title": "call back"}, headers=_HDR)
    check("owner create_lead_task -> 200, no manual approval step", r.status_code == 200)
    check("owner create_lead_task -> canonical tma_create_lead_task action, Tasks table",
          _queued_calls[0][0] == "tma_create_lead_task"
          and _queued_calls[0][1]["table"] == Tables.TASKS)
    check("owner create_lead_task -> never reaches tma_api._at_post directly (Tasks)",
          Tables.TASKS not in _direct_post_tables)

    # -- create_followup: unrelated endpoint, always queued (unchanged) --
    _queued_calls.clear()
    r = _client.post("/api/followup", json={"lead_id": "recLEAD001", "note": "x"}, headers=_HDR)
    check("create_followup -> still queued for approval (out of Finding #3's scope)",
          r.status_code == 202)

    # -- 2. Manager patch_lead: still requires the existing approval flow --
    tma_api.resolve_identity = lambda ch, tid: _FakeIdentity(Role.MANAGER)
    _queued_calls.clear()
    r = _client.patch("/api/leads/recLEAD001", json={"status": "active"}, headers=_HDR)
    check("manager patch_lead -> still 202 pending_approval (unchanged)", r.status_code == 202)
    check("manager patch_lead -> response is the pending_approval shape, not executed",
          (r.get_json() or {}).get("status") == "pending_approval")

    # -- 5. Insufficient role -> fail closed, gateway never reached --
    tma_api.resolve_identity = lambda ch, tid: _FakeIdentity(Role.LEAD)
    _queued_calls.clear()
    r = _client.patch("/api/leads/recLEAD001", json={"status": "active"}, headers=_HDR)
    check("insufficient role -> 403 forbidden", r.status_code == 403)
    check("insufficient role -> gateway never reached", len(_queued_calls) == 0)
finally:
    tma_api._validate_initdata = _orig_validate
    tma_api.resolve_identity = _orig_resolve
    tma_api._at_patch = _orig_at_patch
    tma_api._at_post = _orig_at_post
    tma_api._at_get_record = _orig_at_get_record
    tma_api._queue_tma_write_approval = _orig_queue
    tma_api._claim_and_execute_approval = _orig_claim_execute
    tma_api._at_list = _orig_at_list


# ═════════════════════════════════════════════════════════════════
# 3. tools/approval_actions.py::tma_write() — Manager-approved path
# ═════════════════════════════════════════════════════════════════
print("\n[3] tma_write() — approved-write path")

import tools.approval_actions as approval_actions

_orig_verify_claim = approval_actions._verify_active_execution_claim
approval_actions._verify_active_execution_claim = lambda *a, **kw: True

_patch_ok = {"value": True}
_events_created = []


def _fake_gw_patch(table, record_id, fields, source="unknown"):
    return _patch_ok["value"]


def _counting_create(table, fields, source="unknown"):
    if table == Tables.LEAD_EVENTS:
        _events_created.append({"fields": fields, "source": source})
        return {"id": f"recEV{len(_events_created)}"}
    return {"id": "recOTHER", "fields": fields}


def _domain_record_fields(table, record_id, **kwargs):
    if table == "Leads":
        return {LeadFields.DOMAIN: "general"}
    return {}


airtable_gateway.airtable_patch = _fake_gw_patch
airtable_gateway.airtable_create = _counting_create
airtable_read_adapter.get_record_fields = _domain_record_fields

_EXEC_CTX = {"contract_id": "c1", "approved_by": "owner1", "claim_execution_id": "e1"}

try:
    # -- approved Leads patch success -> exactly one event --
    _events_created.clear()
    _patch_ok["value"] = True
    result = approval_actions.tma_write(
        op="patch", table="Leads", action="tma_patch_lead",
        requested_by="manager1", fields={"status": "active"}, record_id="recLEAD001",
        audit_action="lead_patch", audit_details="x",
        identity=None, trusted_source="tma_api", execution_context=_EXEC_CTX,
    )
    check("approved Leads patch success -> tool result ok", result["ok"] is True)
    check("approved Leads patch success -> exactly one Lead Event created", len(_events_created) == 1)

    # -- approved Leads patch failure -> zero events --
    _events_created.clear()
    _patch_ok["value"] = False
    result_fail = approval_actions.tma_write(
        op="patch", table="Leads", action="tma_set_lead_outcome",
        requested_by="manager1", fields={"Business Outcome": "converted "}, record_id="recLEAD001",
        audit_action="lead_outcome", audit_details="x",
        identity=None, trusted_source="tma_api", execution_context=_EXEC_CTX,
    )
    check("approved Leads patch failure -> tool result not ok", result_fail["ok"] is False)
    check("approved Leads patch failure -> zero Lead Events created", len(_events_created) == 0)
    _patch_ok["value"] = True

    # -- update_lead_status shape (always-approval path) -> exactly one event --
    _events_created.clear()
    approval_actions.tma_write(
        op="patch", table="Leads", action="tma_update_lead_status",
        requested_by="manager1", fields={"status": "active"}, record_id="recLEAD001",
        audit_action="lead_status_update", audit_details="x",
        identity=None, trusted_source="tma_api", execution_context=_EXEC_CTX,
    )
    check("update_lead_status (approved) -> exactly one Lead Event created", len(_events_created) == 1)

    # -- approved non-Leads write (Tasks) -> zero events, even on success --
    _events_created.clear()
    approval_actions.tma_write(
        op="patch", table="Tasks", action="tma_some_task_action",
        requested_by="manager1", fields={"status": "done"}, record_id="recTASK1",
        audit_action="task_update", audit_details="x",
        identity=None, trusted_source="tma_api", execution_context=_EXEC_CTX,
    )
    check("approved non-Leads (Tasks) write -> zero Lead Events created", len(_events_created) == 0)

    # -- approved Leads "post" op (create) -> zero events (only patch triggers) --
    _events_created.clear()
    approval_actions.tma_write(
        op="post", table="Leads", action="tma_create_something",
        requested_by="manager1", fields={"Name": "x"}, record_id="",
        audit_action="x", audit_details="x",
        identity=None, trusted_source="tma_api", execution_context=_EXEC_CTX,
    )
    check("approved Leads 'post' op -> zero Lead Events created (only patch wired)", len(_events_created) == 0)
finally:
    approval_actions._verify_active_execution_claim = _orig_verify_claim
    airtable_gateway.airtable_create = _orig_create
    airtable_read_adapter.get_record_fields = _orig_get_record_fields


# ═════════════════════════════════════════════════════════════════
# 4. Integration — new events pass the existing Phase 1.1 linkage gate
# ═════════════════════════════════════════════════════════════════
print("\n[4] New events pass tma_api._event_linked_to_lead")

_captured_fields = {}


def _capturing_create(table, fields, source="unknown"):
    if table == Tables.LEAD_EVENTS:
        _captured_fields.clear()
        _captured_fields.update(fields)
        return {"id": "recEVX", "fields": fields}
    return {"id": "recOTHER", "fields": fields}


airtable_gateway.airtable_create = _capturing_create
airtable_read_adapter.get_record_fields = lambda table, record_id, **kwargs: (
    {LeadFields.DOMAIN: "general"} if table == "Leads" else {}
)
try:
    write_tma_lead_event("recLEAD001", "lead_patch", {"status": "active"})
    fake_event = {"id": "recEVX", "fields": _captured_fields}
    check("newly created event carries its own Lead link field",
          fake_event["fields"].get(LeadEventFields.LEAD_LINK) == ["recLEAD001"])
    check("newly created event passes _event_linked_to_lead('recLEAD001')",
          tma_api._event_linked_to_lead(fake_event, "recLEAD001") is True)
    check("newly created event fails _event_linked_to_lead for a different lead_id",
          tma_api._event_linked_to_lead(fake_event, "recOTHERLEAD") is False)
finally:
    airtable_gateway.airtable_create = _orig_create
    airtable_read_adapter.get_record_fields = _orig_get_record_fields


# ═════════════════════════════════════════════════════════════════
# 5. No invented schema — Event Type is always the live 'other' value
# ═════════════════════════════════════════════════════════════════
print("\n[5] No invented schema values")
_LIVE_EVENT_TYPES = {"interest", "note", "domain_change", "followup_request", "other"}
check("LeadEventType.OTHER is a live schema value", LeadEventType.OTHER in _LIVE_EVENT_TYPES)
check("this bridge never references a non-existent Event Type constant",
      not any(name.startswith("LEAD_PATCH") or name.startswith("OUTCOME_CHANGE")
              or name.startswith("STATUS_CHANGE") or name.startswith("FOLLOWUP_CHANGE")
              for name in dir(LeadEventType)))


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═'*52}")
print(f"BUG-104 TMA Lead Event Bridge: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
