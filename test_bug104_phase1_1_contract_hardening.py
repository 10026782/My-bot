#!/usr/bin/env python3
# test_bug104_phase1_1_contract_hardening.py
# BUG-104 — Core Reasoning Activation Program
# Phase 1.1 — Lead Reasoning Contract Hardening
#
# Run: python3 test_bug104_phase1_1_contract_hardening.py
# Pass condition: exit code 0, all assertions green.
#
# Covers the two Phase-1.1 fixes, using the REAL (unstubbed) airtable_schema /
# decision_attention / decision_orchestrator modules — not the fake stub
# test_core_reasoning.py installs for its own isolated unit tests:
#
#   1. Status vocabulary mismatch fix — LeadsAdapter._normalise_status() now
#      returns the literal DecisionStatus values the shared Attention/
#      Orchestrator engines actually compare against, not a parallel
#      "OPEN"/"DECIDED_YES" vocabulary that never matched anything.
#   2. Lead Events linkage validation — an event is only admitted when its
#      OWN LeadEventFields.LEAD_LINK field explicitly contains lead_id, not
#      merely because it was reverse-link-reachable from the Lead snapshot.
#
# Explicitly OUT of scope for this file (Phase 2 policy, not touched here):
# Business Outcome / Next Action / Next Followup mapping, Score->confidence,
# Interaction Log / TMA receipts, any change to off/shadow/on semantics or
# the public projection envelope.

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta

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


# ═════════════════════════════════════════════════════════════════
# 1. Status vocabulary — canonical DecisionStatus values reached
# ═════════════════════════════════════════════════════════════════
print("\n[1] Status vocabulary mismatch fix")

from airtable_schema import DecisionStatus
from decision_attention import calc_priority
from decision_attention_policy import DEFAULT_ATTENTION_POLICY
from decision_orchestrator import orchestrate
from core.leads_reasoning_projection import build_reasoning_entity


def _entity_for_status(status_raw: str, extra_fields: dict | None = None):
    fields = {"Name": "x", "status": status_raw, "domain": "general"}
    fields.update(extra_fields or {})
    return build_reasoning_entity({"id": "recL", "fields": fields}, [])


# -- lead פתוח אינו נחשב סגור --
ent_open = _entity_for_status("new")
check("open lead maps to DecisionStatus.OPEN literal", ent_open.status == DecisionStatus.OPEN)
check("open lead status NOT in closed_statuses",
      ent_open.status not in DEFAULT_ATTENTION_POLICY.closed_statuses)

# -- converted/won -> canonical DECIDED_YES --
ent_conv = _entity_for_status("converted")
check("converted maps to DecisionStatus.DECIDED_YES literal", ent_conv.status == DecisionStatus.DECIDED_YES)
ent_conv_he = _entity_for_status("הומר")
check("הומר (Hebrew converted) maps to DecisionStatus.DECIDED_YES",
      ent_conv_he.status == DecisionStatus.DECIDED_YES)

# -- lost -> canonical DECIDED_NO --
ent_lost = _entity_for_status("lost")
check("lost maps to DecisionStatus.DECIDED_NO literal", ent_lost.status == DecisionStatus.DECIDED_NO)
ent_lost_he = _entity_for_status("אבוד")
check("אבוד (Hebrew lost) maps to DecisionStatus.DECIDED_NO", ent_lost_he.status == DecisionStatus.DECIDED_NO)

# -- cancelled -> canonical CANCELLED --
ent_can = _entity_for_status("cancelled")
check("cancelled maps to DecisionStatus.CANCELLED literal", ent_can.status == DecisionStatus.CANCELLED)
ent_can_he = _entity_for_status("בוטל")
check("בוטל (Hebrew cancelled) maps to DecisionStatus.CANCELLED", ent_can_he.status == DecisionStatus.CANCELLED)

# -- Attention actually enters the expected branch (real engine, real policy) --
item_open = calc_priority(
    {"id": "recL", "fields": {"Status": ent_open.status}}, [], require_feature_flag=False,
)
check("open lead NOT short-circuited by Attention's closed_statuses check",
      ent_open.status not in DEFAULT_ATTENTION_POLICY.closed_statuses)

for label, ent in (("converted", ent_conv), ("lost", ent_lost), ("cancelled", ent_can)):
    item = calc_priority({"id": "recL", "fields": {"Status": ent.status}}, [], require_feature_flag=False)
    check(f"{label}: Attention closed_statuses check fires -> priority NONE",
          item.priority == "NONE" and ent.status in DEFAULT_ATTENTION_POLICY.closed_statuses)

# Distinguishing test: identical staleness, open vs cancelled -> only the
# open lead reaches real signal computation (proves the closed branch is a
# genuine short-circuit, not just a coincidental NONE result).
_stale = (AS_OF - timedelta(days=30)).isoformat()
ent_open_stale = _entity_for_status("new", {"updated_at": _stale})
ent_can_stale = _entity_for_status("cancelled", {"updated_at": _stale})
item_open_stale = calc_priority(
    {"id": "recL", "fields": {"Status": ent_open_stale.status,
                              "Last Updated": ent_open_stale.metadata.get("last_updated", "")}},
    [], now=AS_OF, require_feature_flag=False,
)
item_can_stale = calc_priority(
    {"id": "recL", "fields": {"Status": ent_can_stale.status,
                              "Last Updated": ent_can_stale.metadata.get("last_updated", "")}},
    [], now=AS_OF, require_feature_flag=False,
)
check("open+stale lead reaches real signal computation (non-NONE priority)",
      item_open_stale.priority != "NONE" and bool(item_open_stale.reasons))
check("cancelled+stale lead still short-circuits to NONE despite same staleness",
      item_can_stale.priority == "NONE" and not item_can_stale.reasons)

# -- Orchestrator actually enters the expected branch (real engine) --
orch_open = orchestrate(
    {"id": "recL", "fields": {"Status": ent_open.status, "Title": "x"}}, [], [], require_feature_flag=False,
)
check("open lead orchestrator phase != DECIDED/CLOSED", orch_open.phase not in ("DECIDED", "CLOSED"))

orch_conv = orchestrate(
    {"id": "recL", "fields": {"Status": ent_conv.status, "Title": "x"}}, [], [], require_feature_flag=False,
)
check("converted -> orchestrator phase DECIDED (Decided Yes branch)", orch_conv.phase == "DECIDED")
check("converted -> orchestrator current_state reflects yes", orch_conv.current_state == "הוחלט — כן")

orch_lost = orchestrate(
    {"id": "recL", "fields": {"Status": ent_lost.status, "Title": "x"}}, [], [], require_feature_flag=False,
)
check("lost -> orchestrator phase DECIDED (Decided No branch)", orch_lost.phase == "DECIDED")
check("lost -> orchestrator current_state reflects no", orch_lost.current_state == "הוחלט — לא")

orch_can = orchestrate(
    {"id": "recL", "fields": {"Status": ent_can.status, "Title": "x"}}, [], [], require_feature_flag=False,
)
check("cancelled -> orchestrator phase CLOSED (Cancelled branch)", orch_can.phase == "CLOSED")
check("cancelled -> orchestrator current_state reflects cancellation", orch_can.current_state == "בוטל")

# -- unknown/unmapped raw status falls back to OPEN, not a made-up value --
ent_unknown = _entity_for_status("some_unrecognised_value")
check("unrecognised raw status falls back to DecisionStatus.OPEN",
      ent_unknown.status == DecisionStatus.OPEN)


# ═════════════════════════════════════════════════════════════════
# 2. Lead Events linkage validation (tma_api._read_lead_events)
# ═════════════════════════════════════════════════════════════════
print("\n[2] Lead Events linkage validation")
import tma_api

LEAD_ID = "recLEAD001"
EVENT_MATCHING = {"id": "recEV1", "fields": {"Event Type": "interest", "Message": "x",
                                             "Lead": [LEAD_ID]}}
EVENT_WRONG_LINK = {"id": "recEV2", "fields": {"Event Type": "note", "Message": "y",
                                               "Lead": ["recOTHERLEAD"]}}
EVENT_MALFORMED_LINK = {"id": "recEV3", "fields": {"Event Type": "note", "Message": "z",
                                                   "Lead": "recLEAD001"}}   # not a list
EVENT_MISSING_LINK = {"id": "recEV4", "fields": {"Event Type": "note", "Message": "w"}}   # no Lead field at all

_calls = []
_orig_at_list = tma_api._at_list


def _fake_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        _calls.append(formula)
        return [EVENT_MATCHING, EVENT_WRONG_LINK, EVENT_MALFORMED_LINK, EVENT_MISSING_LINK]
    return []


tma_api._at_list = _fake_at_list
try:
    lead_rec = {"id": LEAD_ID, "fields": {"Name": "x", "Lead Events": ["recEV1", "recEV2", "recEV3", "recEV4"]}}
    _calls.clear()
    result = tma_api._read_lead_events(lead_rec)
    check("reverse link + matching own Lead field -> admitted", any(e["id"] == "recEV1" for e in result))
    check("reverse link + wrong own Lead field -> excluded", not any(e["id"] == "recEV2" for e in result))
    check("malformed own Lead field (not a list) -> excluded", not any(e["id"] == "recEV3" for e in result))
    check("missing own Lead field entirely -> excluded", not any(e["id"] == "recEV4" for e in result))
    check("exactly one admitted event out of four fetched", len(result) == 1)
    check("linkage filtering used no extra Airtable call (still exactly one)", len(_calls) == 1)
finally:
    tma_api._at_list = _orig_at_list

# empty events -> available True, count 0, no Airtable call
_calls.clear()
tma_api._at_list = _fake_at_list
try:
    lead_no_links = {"id": "recNL", "fields": {"Name": "x"}}
    result_empty = tma_api._read_lead_events(lead_no_links)
    check("no linked events -> [] (available, count 0)", result_empty == [])
    check("no linked events -> zero Airtable calls", len(_calls) == 0)
finally:
    tma_api._at_list = _orig_at_list

# event read failure -> EVENTS_UNAVAILABLE (None) -> available False, count 0
def _raising_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        raise tma_api.AirtableError(table, 500, "boom")
    return []


tma_api._at_list = _raising_at_list
try:
    lead_with_links = {"id": LEAD_ID, "fields": {"Name": "x", "Lead Events": ["recEV1"]}}
    result_fail = tma_api._read_lead_events(lead_with_links)
    check("read failure -> EVENTS_UNAVAILABLE (None)", result_fail is None)
finally:
    tma_api._at_list = _orig_at_list


# ═════════════════════════════════════════════════════════════════
# 3. Projection-level: linkage-filtered events -> honest available/count
# ═════════════════════════════════════════════════════════════════
print("\n[3] Projection reflects linkage-filtered events honestly")
from core.leads_reasoning_projection import build_reasoning_projection, EVENTS_UNAVAILABLE

LEAD = {"id": LEAD_ID, "fields": {"Name": "x", "Score": 50, "status": "new", "domain": "general"}}

p_admitted_only = build_reasoning_projection(LEAD, [EVENT_MATCHING], AS_OF)
check("projection events.count reflects only pre-filtered (admitted) events",
      p_admitted_only["events"]["count"] == 1 and p_admitted_only["events"]["available"] is True)

p_empty = build_reasoning_projection(LEAD, [], AS_OF)
check("projection events empty -> available True, count 0",
      p_empty["events"]["available"] is True and p_empty["events"]["count"] == 0)

p_unavailable = build_reasoning_projection(LEAD, EVENTS_UNAVAILABLE, AS_OF)
check("projection events unavailable -> available False, count 0",
      p_unavailable["events"]["available"] is False and p_unavailable["events"]["count"] == 0)


# ═════════════════════════════════════════════════════════════════
# 4. Determinism
# ═════════════════════════════════════════════════════════════════
print("\n[4] Determinism")
a = build_reasoning_projection(LEAD, [EVENT_MATCHING], AS_OF)
b = build_reasoning_projection(LEAD, [EVENT_MATCHING], AS_OF)
check("same input + same as_of -> identical projection",
      json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))


# ═════════════════════════════════════════════════════════════════
# 5. Public contract unchanged — envelope, version, off/shadow/on semantics
# ═════════════════════════════════════════════════════════════════
print("\n[5] Public contract unchanged")
from core.leads_reasoning_projection import PROJECTION_VERSION

check("PROJECTION_VERSION still 1", PROJECTION_VERSION == 1)
check("events shape is exactly {available, count}",
      set(a["events"].keys()) == {"available", "count"})
check("no events.sources / provenance leaked into public projection",
      "sources" not in a["events"] and "provenance" not in a)
for key in ("state", "readiness", "confidence", "missing_evidence", "verifier",
            "next_step", "attention_priority", "lead_score", "events", "engine", "as_of", "version"):
    check(f"projection top-level key '{key}' present (envelope unchanged)", key in a)
check("no unexpected new top-level keys",
      set(a.keys()) == {"version", "as_of", "state", "readiness", "confidence",
                        "missing_evidence", "verifier", "next_step",
                        "attention_priority", "lead_score", "events", "engine"})

# off/shadow/on gate semantics unchanged (read budget + envelope), through the endpoint
_events_reads = {"n": 0}
_orig3 = tma_api._at_list


def _counting_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        _events_reads["n"] += 1
        return [EVENT_MATCHING]
    return []


tma_api._at_list = _counting_at_list


def _run_apply(state_value, rec):
    if state_value is None:
        os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)
    else:
        os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = state_value
    _events_reads["n"] = 0
    payload = {"id": rec["id"], "name": "x", "score": 50}
    before = dict(payload)
    tma_api._apply_leads_reasoning_projection(payload, rec)
    return payload, before, _events_reads["n"]


lead_with_link = {"id": LEAD_ID, "fields": {"Name": "x", "Score": 50, "status": "new",
                                            "domain": "general", "Lead Events": ["recEV1"]}}
try:
    pl, before, reads = _run_apply("off", lead_with_link)
    check("off -> no 'reasoning' key, 0 reads, byte-compatible",
          "reasoning" not in pl and reads == 0 and pl == before)

    pl, before, reads = _run_apply("shadow", lead_with_link)
    check("shadow -> response unchanged (no 'reasoning')", "reasoning" not in pl and pl == before)
    check("shadow -> exactly one Lead-Events read (linked event present)", reads == 1)

    pl, before, reads = _run_apply("on", lead_with_link)
    check("on -> 'reasoning' present", "reasoning" in pl)
    check("on -> exactly one Lead-Events read", reads == 1)
    check("on -> events reflect the linkage-admitted event", pl["reasoning"]["events"]["count"] == 1)
finally:
    tma_api._at_list = _orig3
    os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print(f"BUG-104 Phase 1.1 contract hardening: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
