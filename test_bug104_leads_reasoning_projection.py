#!/usr/bin/env python3
# test_bug104_leads_reasoning_projection.py
# BUG-104 — Core Reasoning Activation Program · Phase 1
# Leads Read-Only Reasoning Projection
#
# Run: python3 test_bug104_leads_reasoning_projection.py
# Pass condition: exit code 0, all assertions green.
#
# Covers (per the approved Phase-1 contract):
#   Flag states  — unset→off, invalid→off, off/shadow/on behavior
#   Read budget  — off: 0 Lead-Events reads; shadow/on: ≤1; engines: 0 reads
#   Determinism  — same input + same as_of → same projection; stable serialize
#   Data quality — score valid/missing/non-numeric; events empty/unavailable;
#                  verifier honesty; partial record; unknown fields ignored
#   API compat   — off response byte-compatible (no new field); no mutation

from __future__ import annotations

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

LEAD = {
    "id": "recLEAD001",
    "fields": {
        "Name": "יוסי כהן",
        "Score": 72,
        "status": "active",
        "domain": "real_estate",
        "source": "whatsapp",
    },
}

EVENTS = [
    {"id": "ev1", "fields": {"Event Type": "interest", "Message": "מעוניין בדירת 3 חדרים",
                             "Created At": "2026-07-10T09:00:00Z"}},
    {"id": "ev2", "fields": {"Event Type": "note", "Message": "לחזור אליו מחר",
                             "Created At": "2026-07-12T09:00:00Z"}},
]


# ═════════════════════════════════════════════════════════════════
# 1. Pure projection builder — data quality & verifier honesty
# ═════════════════════════════════════════════════════════════════
print("\n[1] Pure projection builder")
from core.leads_reasoning_projection import (
    build_reasoning_projection,
    degraded_projection,
    EVENTS_UNAVAILABLE,
    VERIFIER_VERIFIED,
    VERIFIER_UNVERIFIED,
    VERIFIER_INSUFFICIENT,
    VERIFIER_UNAVAILABLE,
    VERIFIER_ERROR,
)

p_events = build_reasoning_projection(LEAD, EVENTS, AS_OF)
p_empty  = build_reasoning_projection(LEAD, [], AS_OF)
p_unavail = build_reasoning_projection(LEAD, EVENTS_UNAVAILABLE, AS_OF)

# Contract shape — required fields present
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

# "Lead Score" alternate field name
p_alt = build_reasoning_projection({"id": "recX", "fields": {"Name": "x", "Lead Score": 40}}, [], AS_OF)
check("alternate 'Lead Score' field honored", p_alt["lead_score"]["value"] == 40
      and p_alt["lead_score"]["source"] == "lead_record.Lead Score")

# Partial record / unknown fields ignored safely
p_partial = build_reasoning_projection({"id": "recP", "fields": {}}, [], AS_OF)
check("partial (empty fields) record does not crash", isinstance(p_partial, dict))
p_unknown = build_reasoning_projection(
    {"id": "recU", "fields": {"Name": "x", "Score": 10, "TotallyUnknownField": {"x": 1}}}, [], AS_OF)
check("unknown fields ignored safely", isinstance(p_unknown, dict) and p_unknown["engine"]["degraded"] is False)

# JSON serializable (no python objects, no datetime)
for name, proj in (("events", p_events), ("empty", p_empty), ("unavail", p_unavail)):
    try:
        json.dumps(proj)
        check(f"projection '{name}' is JSON serializable", True)
    except (TypeError, ValueError):
        check(f"projection '{name}' is JSON serializable", False)


# ═════════════════════════════════════════════════════════════════
# 2. Determinism
# ═════════════════════════════════════════════════════════════════
print("\n[2] Determinism")
a = build_reasoning_projection(LEAD, EVENTS, AS_OF)
b = build_reasoning_projection(LEAD, EVENTS, AS_OF)
check("same input + same as_of → identical projection",
      json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))

# Different as_of only changes as_of-derived output, not a random now()
c = build_reasoning_projection(LEAD, EVENTS, datetime(2026, 7, 16, 9, 0, 0, tzinfo=timezone.utc))
check("re-run with equal as_of value → identical", json.dumps(a, sort_keys=True) == json.dumps(c, sort_keys=True))

# String lists are sorted → stable serialization
check("missing_evidence is sorted", a["missing_evidence"] == sorted(a["missing_evidence"]))


# ═════════════════════════════════════════════════════════════════
# 3. Degraded projection (honest, never success)
# ═════════════════════════════════════════════════════════════════
print("\n[3] Degraded projection")
d = degraded_projection(AS_OF, "boom")
check("degraded verifier is 'error'", d["verifier"]["status"] == VERIFIER_ERROR)
check("degraded engine.degraded True", d["engine"]["degraded"] is True)
check("degraded is JSON serializable", isinstance(json.dumps(d), str))
check("degraded never claims verified", d["verifier"]["status"] != VERIFIER_VERIFIED)


# ═════════════════════════════════════════════════════════════════
# 4. Flag states + read budget (endpoint wiring)
# ═════════════════════════════════════════════════════════════════
print("\n[4] Flag states + read budget (endpoint wiring)")
import feature_flags
import tma_api

# Count Lead-Events reads by monkeypatching tma_api._at_list
_events_reads = {"n": 0}
_orig_at_list = tma_api._at_list


def _fake_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        _events_reads["n"] += 1
        return EVENTS
    return _orig_at_list(table, formula, max_records=max_records, strict=strict)


tma_api._at_list = _fake_at_list


def _run_apply(state_value):
    if state_value is None:
        os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)
    else:
        os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = state_value
    _events_reads["n"] = 0
    payload = {"id": LEAD["id"], "name": "יוסי כהן", "score": 72}
    before = dict(payload)
    tma_api._apply_leads_reasoning_projection(payload, LEAD)
    return payload, before, _events_reads["n"]


try:
    # unset → off
    pl, before, reads = _run_apply(None)
    check("unset flag → off (no 'reasoning' field)", "reasoning" not in pl)
    check("unset flag → 0 Lead-Events reads", reads == 0)
    check("unset flag → response byte-compatible", pl == before)

    # invalid → off
    pl, before, reads = _run_apply("banana")
    check("invalid flag → off (no 'reasoning' field)", "reasoning" not in pl)
    check("invalid flag → 0 Lead-Events reads", reads == 0)

    # off → off
    pl, before, reads = _run_apply("off")
    check("off → no 'reasoning' field", "reasoning" not in pl)
    check("off → 0 Lead-Events reads (byte-compatible)", reads == 0 and pl == before)

    # shadow → reasoning computed, response unchanged, ≤1 read
    pl, before, reads = _run_apply("shadow")
    check("shadow → response unchanged (no 'reasoning' field)", "reasoning" not in pl and pl == before)
    check("shadow → at most one Lead-Events read", reads <= 1)
    check("shadow → exactly one Lead-Events read (state requires it)", reads == 1)

    # on → reasoning projection returned, ≤1 read
    pl, before, reads = _run_apply("on")
    check("on → 'reasoning' projection present", "reasoning" in pl)
    check("on → at most one Lead-Events read", reads <= 1)
    check("on → projection has verifier + as_of", "verifier" in pl["reasoning"] and "as_of" in pl["reasoning"])
    check("on → JSON serializable payload", isinstance(json.dumps(pl), str))
finally:
    tma_api._at_list = _orig_at_list
    os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)


# ═════════════════════════════════════════════════════════════════
# 5. Read-failure → honest 'unavailable', endpoint does not crash
# ═════════════════════════════════════════════════════════════════
print("\n[5] Lead-Events read failure → honest unavailable")
_orig_at_list2 = tma_api._at_list


def _raising_at_list(table, formula="", max_records=50, strict=False):
    if table == tma_api.Tables.LEAD_EVENTS:
        raise tma_api.AirtableError(table, 500, "boom")
    return _orig_at_list2(table, formula, max_records=max_records, strict=strict)


tma_api._at_list = _raising_at_list
try:
    os.environ["FEATURE_CORE_REASONING_LEADS_STATE"] = "on"
    payload = {"id": LEAD["id"], "name": "x"}
    tma_api._apply_leads_reasoning_projection(payload, LEAD)
    check("read failure → 'reasoning' still attached (endpoint survives)", "reasoning" in payload)
    check("read failure → verifier 'unavailable' (honest)",
          payload["reasoning"]["verifier"]["status"] == VERIFIER_UNAVAILABLE)
finally:
    tma_api._at_list = _orig_at_list2
    os.environ.pop("FEATURE_CORE_REASONING_LEADS_STATE", None)


# ═════════════════════════════════════════════════════════════════
# 6. Engines/adapter perform no repository reads
# ═════════════════════════════════════════════════════════════════
print("\n[6] Engines/adapter do no repository reads")
# The builder uses ReasoningPorts() (all-null). Prove no Airtable gateway call
# happens during a build by making the gateway raise if touched.
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
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═'*52}")
print(f"BUG-104 Phase-1 projection: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
