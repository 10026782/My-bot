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
import tools.airtable_tools as airtable_tools
from core.lead_event_writer import write_tma_lead_event
from airtable_schema import LeadEventFields, LeadEventType, Tables, LeadFields

_orig_create = airtable_gateway.airtable_create
_orig_get_records = airtable_tools.airtable_get_records

_created: list[dict] = []
_create_should_fail = {"value": False}
_create_should_raise = {"value": False}
_domain_lookup_calls = {"n": 0}
_domain_lookup_return = {"value": [{"id": "recLEAD001", "fields": {LeadFields.DOMAIN: "recruitment"}}]}


def _fake_create(table, fields, source="unknown"):
    if _create_should_raise["value"]:
        raise RuntimeError("boom")
    if table != Tables.LEAD_EVENTS:
        return {"id": "recOTHER", "fields": fields}
    if _create_should_fail["value"]:
        return None
    _created.append({"table": table, "fields": fields, "source": source})
    return {"id": f"recEV{len(_created)}", "fields": fields}


def _fake_get_records(table, filter_formula=""):
    _domain_lookup_calls["n"] += 1
    if table == "Leads":
        return _domain_lookup_return["value"]
    return []


airtable_gateway.airtable_create = _fake_create
airtable_tools.airtable_get_records = _fake_get_records

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
    _domain_lookup_return["value"] = [{"id": "recL2", "fields": {LeadFields.DOMAIN: "real_estate"}}]
    write_tma_lead_event("recL2", "lead_patch", {"status": "active"})
    check("domain 'real_estate' passes through unchanged", _created[0]["fields"][LeadEventFields.DOMAIN] == "real_estate")

    # -- domain passthrough: saas --
    _created.clear()
    _domain_lookup_return["value"] = [{"id": "recL3", "fields": {LeadFields.DOMAIN: "saas"}}]
    write_tma_lead_event("recL3", "lead_patch", {"status": "active"})
    check("domain 'saas' passes through unchanged", _created[0]["fields"][LeadEventFields.DOMAIN] == "saas")

    # -- domain passthrough: import --
    _created.clear()
    _domain_lookup_return["value"] = [{"id": "recL4", "fields": {LeadFields.DOMAIN: "import"}}]
    write_tma_lead_event("recL4", "lead_patch", {"status": "active"})
    check("domain 'import' passes through unchanged", _created[0]["fields"][LeadEventFields.DOMAIN] == "import")

    # -- missing domain field entirely -> general --
    _created.clear()
    _domain_lookup_return["value"] = [{"id": "recL5", "fields": {}}]
    write_tma_lead_event("recL5", "lead_patch", {"status": "active"})
    check("missing domain -> general fallback", _created[0]["fields"][LeadEventFields.DOMAIN] == "general")

    # -- unrecognized raw domain (e.g. a project_slug value) -> general, no invented option --
    _created.clear()
    _domain_lookup_return["value"] = [{"id": "recL6", "fields": {LeadFields.DOMAIN: "blueview"}}]
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
    _domain_lookup_return["value"] = [{"id": "recL8", "fields": {LeadFields.DOMAIN: "general"}}]
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
    _domain_lookup_return["value"] = [{"id": "recL11", "fields": {LeadFields.DOMAIN: "general"}}]
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
    airtable_tools.airtable_get_records = _orig_get_records


# ═════════════════════════════════════════════════════════════════
# 2. tma_api.py — owner-immediate path (patch_lead / set_lead_outcome)
# ═════════════════════════════════════════════════════════════════
print("\n[2] tma_api owner-immediate path")

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
_orig_at_get_record = tma_api._at_get_record

_patch_should_fail = {"value": False}
_events_created = []


def _fake_at_patch(table, record_id, fields):
    return not _patch_should_fail["value"]


def _counting_create(table, fields, source="unknown"):
    if table == Tables.LEAD_EVENTS:
        _events_created.append({"fields": fields, "source": source})
        return {"id": f"recEV{len(_events_created)}"}
    return {"id": "recOTHER", "fields": fields}


def _domain_records(table, filter_formula=""):
    if table == "Leads":
        return [{"id": "recLEAD001", "fields": {LeadFields.DOMAIN: "general"}}]
    return []


tma_api._validate_initdata = lambda s: {"id": "1"}
tma_api.resolve_identity = lambda ch, tid: _FakeIdentity(Role.OWNER)
tma_api._at_patch = _fake_at_patch
airtable_gateway.airtable_create = _counting_create
airtable_tools.airtable_get_records = _domain_records

try:
    # -- owner patch success -> exactly one event --
    _events_created.clear()
    _patch_should_fail["value"] = False
    r = _client.patch("/api/leads/recLEAD001", json={"status": "active"}, headers=_HDR)
    check("owner patch success -> 200", r.status_code == 200)
    check("owner patch success -> exactly one Lead Event created", len(_events_created) == 1)

    # -- owner patch failure -> zero events --
    _events_created.clear()
    _patch_should_fail["value"] = True
    r = _client.patch("/api/leads/recLEAD001", json={"status": "active"}, headers=_HDR)
    check("owner patch failure -> 500", r.status_code == 500)
    check("owner patch failure -> zero Lead Events created", len(_events_created) == 0)
    _patch_should_fail["value"] = False

    # -- owner outcome success -> exactly one event --
    _events_created.clear()
    r = _client.post("/api/leads/recLEAD001/outcome", json={"outcome": "converted"}, headers=_HDR)
    check("owner outcome success -> 200", r.status_code == 200)
    check("owner outcome success -> exactly one Lead Event created", len(_events_created) == 1)

    # -- owner outcome failure -> zero events --
    _events_created.clear()
    _patch_should_fail["value"] = True
    r = _client.post("/api/leads/recLEAD001/outcome", json={"outcome": "converted"}, headers=_HDR)
    check("owner outcome failure -> 500", r.status_code == 500)
    check("owner outcome failure -> zero Lead Events created", len(_events_created) == 0)
    _patch_should_fail["value"] = False

    # -- GET lead -> no event wiring on the read path --
    tma_api._at_get_record = lambda table, rid: {"id": rid, "fields": {"Name": "x"}}
    _events_created.clear()
    r = _client.get("/api/leads/recLEAD001", headers=_HDR)
    check("GET lead -> zero Lead Events created", len(_events_created) == 0)

    # -- create_lead_task -> no event (doesn't PATCH the Lead) --
    _events_created.clear()
    r = _client.post("/api/leads/recLEAD001/task", json={"title": "call back"}, headers=_HDR)
    check("create_lead_task -> zero Lead Events created", len(_events_created) == 0)

    # -- create_followup -> no event (doesn't PATCH the Lead) --
    _events_created.clear()
    r = _client.post("/api/followup", json={"lead_id": "recLEAD001", "note": "x"}, headers=_HDR)
    check("create_followup -> zero Lead Events created", len(_events_created) == 0)
finally:
    tma_api._validate_initdata = _orig_validate
    tma_api.resolve_identity = _orig_resolve
    tma_api._at_patch = _orig_at_patch
    tma_api._at_get_record = _orig_at_get_record
    airtable_gateway.airtable_create = _orig_create
    airtable_tools.airtable_get_records = _orig_get_records


# ═════════════════════════════════════════════════════════════════
# 3. tools/approval_actions.py::tma_write() — Manager-approved path
# ═════════════════════════════════════════════════════════════════
print("\n[3] tma_write() — approved-write path")

import tools.approval_actions as approval_actions

_orig_verify_claim = approval_actions._verify_active_execution_claim
approval_actions._verify_active_execution_claim = lambda *a, **kw: True

_patch_ok = {"value": True}


def _fake_gw_patch(table, record_id, fields, source="unknown"):
    return _patch_ok["value"]


airtable_gateway.airtable_patch = _fake_gw_patch
airtable_gateway.airtable_create = _counting_create
airtable_tools.airtable_get_records = _domain_records

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
    airtable_tools.airtable_get_records = _orig_get_records


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
airtable_tools.airtable_get_records = lambda table, filter_formula="": (
    [{"id": "recLEAD001", "fields": {LeadFields.DOMAIN: "general"}}] if table == "Leads" else []
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
    airtable_tools.airtable_get_records = _orig_get_records


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
