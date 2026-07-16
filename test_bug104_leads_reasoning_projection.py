#!/usr/bin/env python3
# test_bug104_leads_reasoning_projection.py
# BUG-104 — Core Reasoning Activation Program · Phase 1
# Leads Read-Only Reasoning Projection
#
# Run: python3 test_bug104_leads_reasoning_projection.py
# Pass condition: exit code 0, all assertions green.
#
# Covers (per the approved Phase-1 contract + re-audit fixes P1-A/B/C):
#   Flag states  — unset→off, invalid→off, off/shadow/on behavior
#   Read budget  — off: 0 reads; linked events → exactly 1; no links → 0;
#                  engines/adapter: 0 repository reads
#   P1-A lookup  — formula built from event record IDs (from the Lead snapshot),
#                  never the lead ID; empty links → available/count 0, no read;
#                  real read failure → EVENTS_UNAVAILABLE
#   P1-B normal. — live lowercase schema mapped to the adapter; status/domain/
#                  channel not defaulted away; input snapshot never mutated
#   P1-C readiness — readiness is a distinct honest state, never == phase,
#                  never positive when absent, never positive when degraded
#   Determinism  — same input + same as_of → same projection; stable serialize
#   API compat   — Flask test-client: 401/403/404 unchanged; off byte-compatible

from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime, timezone

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


AS_OF = datetime(2026, 7, 16, 9, 0, 0, tzinfo=timezone.utc)

# Live-schema Lead record (lowercase fields, as production Airtable stores them),
# with a reverse-link "Lead Events" list of event record IDs.
LEAD = {
    "id": "recLEAD001",
    "fields": {
        "Name": "יוסי כהן",
        "phone": "0501234567",
        "status": "active",
        "Score": 72,
        "tier": "lohet",
        "source": "campaign-x",
        "channel": "whatsapp",
        "domain": "real_estate",
        "created_at": "2026-07-01T09:00:00Z",
        "updated_at": "2026-07-12T09:00:00Z",
        "notes": "לקוח חם",
        "summary": "מעוניין בדירת 3 חדרים",
        "Lead Events": ["recEV1", "recEV2"],
    },
}

EVENTS = [
    {"id": "recEV1", "fields": {"Event Type": "interest", "Message": "מעוניין בדירת 3 חדרים",
                               "Created At": "2026-07-10T09:00:00Z"}},
    {"id": "recEV2", "fields": {"Event Type": "note", "Message": "לחזור אליו מחר",
                               "Created At": "2026-07-12T09:00:00Z"}},
]


# ═════════════════════════════════════════════════════════════════
# 1. Pure projection builder — data quality & verifier honesty
# ═════════════════════════════════════════════════════════════════
print("\n[1] Pure projection builder")
from core.leads_reasoning_projection import (
    build_reasoning_projection,
    build_reasoning_entity,
    degraded_projection,
    EVENTS_UNAVAILABLE,
    VERIFIER_VERIFIED,
    VERIFIER_UNVERIFIED,
    VERIFIER_INSUFFICIENT,
    VERIFIER_UNAVAILABLE,
    VERIFIER_ERROR,
    READINESS_UNKNOWN,
    READINESS_UNAVAILABLE,
)

p_events = build_reasoning_projection(LEAD, EVENTS, AS_OF)
p_empty  = build_reasoning_projection(LEAD, [], AS_OF)
p_unavail = build_reasoning_projection(LEAD, EVENTS_UNAVAILABLE, AS_OF)

for key in ("state", "readiness", "confidence", "missing_evidence", "verifier",
            "next_step", "as_of", "lead_score", "events", "engine"):
    check(f"projection has '{key}'", key in p_events)

check("as_of is the passed timestamp (deterministic, not now())",
      p_events["as_of"] == AS_OF.isoformat())
check("confidence.score is a float in [0,1]",
      isinstance(p_events["confidence"]["score"], float) and 0.0 <= p_events["confidence"]["score"] <= 1.0)

# Verifier honesty — never 'verified' from the read-only path
check("verifier NEVER 'verified' (events present)", p_events["verifier"]["status"] != VERIFIER_VERIFIED)
check("verifier 'unverified' when events present", p_events["verifier"]["status"] == VERIFIER_UNVERIFIED)
check("verifier 'insufficient_evidence' when events empty", p_empty["verifier"]["status"] == VERIFIER_INSUFFICIENT)
check("verifier 'unavailable' when events unread", p_unavail["verifier"]["status"] == VERIFIER_UNAVAILABLE)
check("events.available False when unread", p_unavail["events"]["available"] is False)
check("events.available True when read", p_events["events"]["available"] is True)
check("events.count reflects list length", p_events["events"]["count"] == 2)

# Lead score honesty
check("lead_score value normalized to int", p_events["lead_score"]["value"] == 72)
check("lead_score state present", p_events["lead_score"]["state"] == "present")
check("lead_score never recomputed", p_events["lead_score"]["recomputed"] is False)
check("lead_score source stated honestly", p_events["lead_score"]["source"] == "lead_record.Score")

p_missing_score = build_reasoning_projection({"id": "recX", "fields": {"Name": "דנה"}}, [], AS_OF)
check("missing score → value None", p_missing_score["lead_score"]["value"] is None)
check("missing score → state 'missing'", p_missing_score["lead_score"]["state"] == "missing")
check("missing score → source None (not invented)", p_missing_score["lead_score"]["source"] is None)

p_bad_score = build_reasoning_projection({"id": "recX", "fields": {"Name": "רון", "Score": "abc"}}, [], AS_OF)
check("non-numeric score → value None", p_bad_score["lead_score"]["value"] is None)
check("non-numeric score → state 'invalid'", p_bad_score["lead_score"]["state"] == "invalid")

p_alt = build_reasoning_projection({"id": "recX", "fields": {"Name": "x", "Lead Score": 40}}, [], AS_OF)
check("alternate 'Lead Score' field honored", p_alt["lead_score"]["value"] == 40
      and p_alt["lead_score"]["source"] == "lead_record.Lead Score")

p_partial = build_reasoning_projection({"id": "recP", "fields": {}}, [], AS_OF)
check("partial (empty fields) record does not crash", isinstance(p_partial, dict))
p_unknown = build_reasoning_projection(
    {"id": "recU", "fields": {"Name": "x", "Score": 10, "TotallyUnknownField": {"x": 1}}}, [], AS_OF)
check("unknown fields ignored safely", isinstance(p_unknown, dict) and p_unknown["engine"]["degraded"] is False)

for name, proj in (("events", p_events), ("empty", p_empty), ("unavail", p_unavail)):
    try:
        json.dumps(proj)
        check(f"projection '{name}' is JSON serializable", True)
    except (TypeError, ValueError):
        check(f"projection '{name}' is JSON serializable", False)


# ═════════════════════════════════════════════════════════════════
# 2. P1-B — canonical live-schema normalization → ReasoningEntity
# ═════════════════════════════════════════════════════════════════
print("\n[2] P1-B — live-schema normalization")
live_rec = {
    "id": "recL",
    "fields": {
        "Name": "רון לוי", "phone": "0509998888", "status": "lost", "Score": 80,
        "tier": "lohet", "source": "campaign-x", "channel": "email",
        "created_at": "2026-07-01T00:00:00Z", "updated_at": "2026-07-10T00:00:00Z",
        "domain": "real_estate", "notes": "n", "summary": "s",
    },
}
snapshot_before = copy.deepcopy(live_rec)
ent = build_reasoning_entity(live_rec, [])

check("status=lost does NOT become OPEN", ent.status != "OPEN")
check("status=lost maps to DECIDED_NO", ent.status == "DECIDED_NO")
check("domain=real_estate does NOT become general", ent.domain == "real_estate")
check("channel=email does NOT become whatsapp", ent.metadata["channel"] == "email")
check("lowercase tier reaches ReasoningEntity", ent.metadata["tier"] == "lohet")
check("lowercase phone reaches ReasoningEntity", ent.metadata["phone"] == "0509998888")
check("created_at reaches ReasoningEntity", ent.metadata["created"] == "2026-07-01T00:00:00Z")
check("updated_at reaches ReasoningEntity (Last Updated)", ent.metadata["last_updated"] == "2026-07-10T00:00:00Z")
check("Score passed through, not recomputed", ent.metadata["lead_score"] == 80)
check("input lead snapshot is NOT mutated", live_rec == snapshot_before)

# A live channel-like source must not silently reclassify an explicit domain.
ent2 = build_reasoning_entity({"id": "r", "fields": {"Name": "x", "source": "whatsapp",
                                                     "domain": "import"}}, [])
check("explicit domain wins over channel-like source", ent2.domain == "import")


# ═════════════════════════════════════════════════════════════════
# 3. P1-C — readiness is honest, never == phase
# ═════════════════════════════════════════════════════════════════
print("\n[3] P1-C — readiness contract")
check("readiness is a structured state (dict)", isinstance(p_events["readiness"], dict))
check("readiness has a status", "status" in p_events["readiness"])
check("readiness status is 'unknown' (no leads policy)", p_events["readiness"]["status"] == READINESS_UNKNOWN)
check("readiness has a fixed deterministic reason", bool(p_events["readiness"].get("reason")))
check("readiness is NOT the phase/state value", p_events["readiness"] != p_events["state"])
check("readiness never a positive 'READY'-like value",
      p_events["readiness"]["status"] not in ("READY", "ready", "DECIDED", p_events["state"]))
_deg = degraded_projection(AS_OF, "boom")
check("degraded readiness is 'unavailable' (not positive)", _deg["readiness"]["status"] == READINESS_UNAVAILABLE)
check("degraded readiness is not the phase", _deg["readiness"] != _deg["state"])


# ═════════════════════════════════════════════════════════════════
# 4. Determinism + degraded projection
# ═════════════════════════════════════════════════════════════════
print("\n[4] Determinism + degraded projection")
a = build_reasoning_projection(LEAD, EVENTS, AS_OF)
b = build_reasoning_projection(LEAD, EVENTS, AS_OF)
check("same input + same as_of → identical projection",
      json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
check("missing_evidence is sorted", a["missing_evidence"] == sorted(a["missing_evidence"]))

d = degraded_projection(AS_OF, "boom")
check("degraded verifier is 'error'", d["verifier"]["status"] == VERIFIER_ERROR)
check("degraded engine.degraded True", d["engine"]["degraded"] is True)
check("degraded is JSON serializable", isinstance(json.dumps(d), str))
check("degraded never claims verified", d["verifier"]["status"] != VERIFIER_VERIFIED)


# ═════════════════════════════════════════════════════════════════
# 5. P1-A — Lead-Events lookup keyed by linked event IDs (endpoint)
# ═════════════════════════════════════════════════════════════════
print("\n[5] P1-A — Lead-Events lookup + read budget")
import tma_api

_calls = []
_orig_at_list = tma_api._at_list


def _fake_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        _calls.append(formula)
        return EVENTS
    return []


tma_api._at_list = _fake_at_list
try:
    # lead WITH linked event IDs → exactly one read, formula from event IDs
    _calls.clear()
    r = tma_api._read_lead_events(LEAD)
    check("linked events → exactly one Lead-Events read", len(_calls) == 1)
    check("formula uses event RECORD_IDs, not the lead ID",
          "recEV1" in _calls[0] and "recEV2" in _calls[0] and LEAD["id"] not in _calls[0])
    check("formula uses RECORD_ID() (events table), not linked display",
          "RECORD_ID()" in _calls[0] and "ARRAYJOIN" not in _calls[0])
    check("linked events → returns event list", r == EVENTS)

    # lead WITHOUT linked events → zero reads, available empty
    _calls.clear()
    r0 = tma_api._read_lead_events({"id": "recX", "fields": {"Name": "x"}})
    check("no linked events → zero Lead-Events reads", len(_calls) == 0)
    check("no linked events → [] (available, empty)", r0 == [])

    # malformed IDs are rejected before the formula (defense in depth)
    _calls.clear()
    rj = tma_api._read_lead_events({"id": "recX", "fields": {"Lead Events": ["not-a-rec", 123]}})
    check("malformed linked IDs → zero reads, []", len(_calls) == 0 and rj == [])
finally:
    tma_api._at_list = _orig_at_list

# Real read failure → EVENTS_UNAVAILABLE (None)
_orig_at_list2 = tma_api._at_list


def _raising_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        raise tma_api.AirtableError(table, 500, "boom")
    return []


tma_api._at_list = _raising_at_list
try:
    ru = tma_api._read_lead_events(LEAD)
    check("real read failure → EVENTS_UNAVAILABLE (None)", ru is None)
finally:
    tma_api._at_list = _orig_at_list2


# ═════════════════════════════════════════════════════════════════
# 6. Flag states + read budget (endpoint gate)
# ═════════════════════════════════════════════════════════════════
print("\n[6] Flag states + read budget (endpoint gate)")
_events_reads = {"n": 0}
_orig3 = tma_api._at_list


def _counting_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        _events_reads["n"] += 1
        return EVENTS
    return []


tma_api._at_list = _counting_at_list


def _run_apply(state_value, rec=LEAD):
    if state_value is None:
        os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)
    else:
        os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = state_value
    _events_reads["n"] = 0
    payload = {"id": rec["id"], "name": "x", "score": 72}
    before = dict(payload)
    tma_api._apply_leads_reasoning_projection(payload, rec)
    return payload, before, _events_reads["n"]


try:
    pl, before, reads = _run_apply(None)
    check("unset flag → off (no 'reasoning'), 0 reads, byte-compatible",
          "reasoning" not in pl and reads == 0 and pl == before)

    pl, before, reads = _run_apply("banana")
    check("invalid flag → off (no 'reasoning'), 0 reads", "reasoning" not in pl and reads == 0)

    pl, before, reads = _run_apply("off")
    check("off → no 'reasoning', 0 reads (byte-compatible)",
          "reasoning" not in pl and reads == 0 and pl == before)

    pl, before, reads = _run_apply("shadow")
    check("shadow → response unchanged (no 'reasoning')", "reasoning" not in pl and pl == before)
    check("shadow (linked events) → exactly one read", reads == 1)

    pl, before, reads = _run_apply("on")
    check("on → 'reasoning' projection present", "reasoning" in pl)
    check("on (linked events) → exactly one read", reads == 1)
    check("on → projection has verifier + as_of + readiness",
          all(k in pl["reasoning"] for k in ("verifier", "as_of", "readiness")))

    # on, lead WITHOUT linked events → zero reads, available empty
    lead_no_links = {"id": "recNL", "fields": {"Name": "x", "Score": 5, "status": "new", "domain": "general"}}
    pl, before, reads = _run_apply("on", rec=lead_no_links)
    check("on (no links) → zero reads, reasoning present", reads == 0 and "reasoning" in pl)
    check("on (no links) → events available, count 0",
          pl["reasoning"]["events"]["available"] is True and pl["reasoning"]["events"]["count"] == 0)
finally:
    tma_api._at_list = _orig3
    os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)


# read failure through the gate → honest unavailable, endpoint survives
tma_api._at_list = _raising_at_list
try:
    os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = "on"
    payload = {"id": LEAD["id"], "name": "x"}
    tma_api._apply_leads_reasoning_projection(payload, LEAD)
    check("read failure → 'reasoning' attached (endpoint survives)", "reasoning" in payload)
    check("read failure → verifier 'unavailable' (honest)",
          payload["reasoning"]["verifier"]["status"] == VERIFIER_UNAVAILABLE)
finally:
    tma_api._at_list = _orig_at_list2
    os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)


# ═════════════════════════════════════════════════════════════════
# 7. Engines/adapter perform no repository reads
# ═════════════════════════════════════════════════════════════════
print("\n[7] Engines/adapter do no repository reads")
import tools.airtable_gateway as _gw
_orig_search = getattr(_gw, "airtable_search", None)


def _boom(*a, **k):
    raise AssertionError("engine/adapter attempted an Airtable read")


if _orig_search is not None:
    _gw.airtable_search = _boom
try:
    proj = build_reasoning_projection(LEAD, EVENTS, AS_OF)
    check("build touches no airtable_gateway.airtable_search", True)
    check("build still produces a projection", isinstance(proj, dict))
except AssertionError as e:
    check(f"build touches no airtable read ({e})", False)
finally:
    if _orig_search is not None:
        _gw.airtable_search = _orig_search


# ═════════════════════════════════════════════════════════════════
# 8. Real Flask test-client — GET /api/leads/<lead_id>
# ═════════════════════════════════════════════════════════════════
print("\n[8] Flask test-client — GET /api/leads/<id>")
from flask import Flask
from identity import Role


class _FakeIdentity:
    def __init__(self, role, allow_domain=True):
        self.role = role
        self._allow = allow_domain

    def can_access_domain(self, domain):
        return self._allow


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    return app.test_client()


_client = _make_client()
_HDR = {"X-Telegram-Init-Data": "x"}

_state = {"identity": _FakeIdentity(Role.OWNER), "lead": LEAD, "events_reads": 0, "last_formula": None}
_orig_validate = tma_api._validate_initdata
_orig_resolve  = tma_api.resolve_identity
_orig_get      = tma_api._at_get_record
_orig_list     = tma_api._at_list

tma_api._validate_initdata = lambda s: {"id": "1"}
tma_api.resolve_identity   = lambda ch, tid: _state["identity"]
tma_api._at_get_record     = lambda table, rid: _state["lead"]


def _client_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        _state["events_reads"] += 1
        _state["last_formula"] = formula
        return EVENTS
    return []   # interaction log timeline etc.


tma_api._at_list = _client_at_list


def _get(lead_id="recLEAD001", headers=_HDR):
    _state["events_reads"] = 0
    _state["last_formula"] = None
    return _client.get(f"/api/leads/{lead_id}", headers=headers)


try:
    # unauthorized — no init-data header
    r = _client.get("/api/leads/recLEAD001")
    check("unauthorized (no header) → 401", r.status_code == 401)

    # forbidden — role not allowed (guest)
    _state["identity"] = _FakeIdentity(Role.GUEST)
    os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = "on"
    r = _get()
    check("forbidden role → 403", r.status_code == 403)
    check("forbidden → 0 Lead-Events reads", _state["events_reads"] == 0)

    # 404 — lead not found; no Lead-Events read
    _state["identity"] = _FakeIdentity(Role.OWNER)
    _state["lead"] = None
    r = _get("recMISSING")
    check("missing lead → 404", r.status_code == 404)
    check("404 → 0 Lead-Events reads", _state["events_reads"] == 0)
    _state["lead"] = LEAD

    # partner domain check runs BEFORE reasoning
    _state["identity"] = _FakeIdentity(Role.PARTNER, allow_domain=False)
    r = _get()
    check("partner without domain access → 403", r.status_code == 403)
    check("partner-forbidden → 0 Lead-Events reads (before reasoning)", _state["events_reads"] == 0)
    _state["identity"] = _FakeIdentity(Role.OWNER)

    # off — old payload, zero reads, no 'reasoning'
    os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = "off"
    r = _get()
    body = r.get_json()
    check("off → 200", r.status_code == 200)
    check("off → no 'reasoning' field (byte-compatible)", "reasoning" not in body)
    check("off → 0 Lead-Events reads", _state["events_reads"] == 0)

    # shadow — old payload, one read (linked events), no 'reasoning'
    os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = "shadow"
    r = _get()
    body = r.get_json()
    check("shadow → 200, no 'reasoning'", r.status_code == 200 and "reasoning" not in body)
    check("shadow (linked events) → exactly one read", _state["events_reads"] == 1)

    # on — reasoning attached, one read, formula from event IDs
    os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = "on"
    r = _get()
    body = r.get_json()
    check("on → 200 with 'reasoning'", r.status_code == 200 and "reasoning" in body)
    check("on (linked events) → exactly one read", _state["events_reads"] == 1)
    check("on → formula uses event record IDs (not lead id)",
          "RECORD_ID()" in (_state["last_formula"] or "") and "recEV1" in (_state["last_formula"] or "")
          and LEAD["id"] not in (_state["last_formula"] or ""))
    check("on → live-schema record normalized (reasoning produced, not degraded)",
          body["reasoning"]["engine"]["degraded"] is False)
    check("on → readiness is honest state, not phase",
          body["reasoning"]["readiness"] != body["reasoning"]["state"])

    # on, lead without linked events → zero reads, available empty
    _state["lead"] = {"id": "recNL", "fields": {"Name": "x", "Score": 5, "status": "new", "domain": "general"}}
    r = _get("recNL")
    body = r.get_json()
    check("on (no links) → zero reads", _state["events_reads"] == 0)
    check("on (no links) → events available count 0",
          body["reasoning"]["events"]["available"] is True and body["reasoning"]["events"]["count"] == 0)
    _state["lead"] = LEAD

    # read failure → honest unavailable, endpoint 200
    def _failing_list(table, formula="", max_records=50, strict=False):
        if table == tma_api.Tables.LEAD_EVENTS:
            raise tma_api.AirtableError(table, 500, "boom")
        return []
    tma_api._at_list = _failing_list
    r = _get()
    body = r.get_json()
    check("read failure → 200 (endpoint survives)", r.status_code == 200)
    check("read failure → verifier 'unavailable'",
          body["reasoning"]["verifier"]["status"] == VERIFIER_UNAVAILABLE)
    tma_api._at_list = _client_at_list
finally:
    tma_api._validate_initdata = _orig_validate
    tma_api.resolve_identity   = _orig_resolve
    tma_api._at_get_record     = _orig_get
    tma_api._at_list           = _orig_list
    os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═'*52}")
print(f"BUG-104 Phase-1 projection: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
