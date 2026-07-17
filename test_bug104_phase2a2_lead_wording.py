#!/usr/bin/env python3
# test_bug104_phase2a2_lead_wording.py
# BUG-104 — Core Reasoning Activation Program
# Phase 2A.2 — Lead-specific Evidence & Next Step Wording
#
# Run: python3 test_bug104_phase2a2_lead_wording.py
# Pass condition: exit code 0, all assertions green.
#
# Covers the wording post-processing in
# core/leads_reasoning_projection.py::_apply_lead_wording() /
# build_reasoning_projection(), per
# docs/architecture/bug-104/PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md Example A
# and PHASE_2A_CLOSEOUT.md §5A:
#
#   A. Lead with no events -> COLLECTING, lead-specific missing_evidence +
#      next_step.action, no generic Decision wording.
#   B. Lead with events, REVIEW -> lead-specific, review-oriented next_step,
#      engine clean.
#   C. Terminal converted -> stays DECIDED, execution-oriented next_step,
#      missing_evidence does not re-open the lead.
#   D. meeting_scheduled (intermediate Business Outcome) -> stays non-terminal,
#      lead-specific wording, not generic Decision-document wording.
#
# Uses the REAL (unstubbed) airtable_schema / decision_orchestrator /
# decision_confidence modules, same approach as
# test_bug104_phase1_1_contract_hardening.py / test_bug104_phase2a1_current_state_policy.py.

from __future__ import annotations

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


AS_OF = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)

from core.leads_reasoning_projection import build_reasoning_projection

_GENERIC_DECISION_STRINGS = ("מסמך תומך", "הוסף ראיות ועדכן אירועים", "השג אין אירועים מקושרים")


def _projection(fields: dict, events: list | None = None):
    return build_reasoning_projection({"id": "recL", "fields": fields}, events or [], AS_OF)


def _all_text(proj: dict) -> str:
    parts = [str(proj.get("state", ""))]
    parts += [str(m) for m in proj.get("missing_evidence", [])]
    ns = proj.get("next_step") or {}
    parts += [str(ns.get("action", "")), str(ns.get("detail", "")), str(ns.get("responsible", ""))]
    return " | ".join(parts)


# ═════════════════════════════════════════════════════════════════
# A. Lead with no events -> COLLECTING, lead-specific wording
# ═════════════════════════════════════════════════════════════════
print("\n[A] Lead with no events")

p_a = _projection({"Name": "x", "domain": "general", "status": "active"}, events=[])

check("state remains COLLECTING", p_a["state"] == "COLLECTING")
check("missing_evidence is lead-specific", p_a["missing_evidence"] == ["חסרה היסטוריית טיפול בליד"])
check("next_step.action is lead-specific", p_a["next_step"]["action"] == "הוסף הערת טיפול או עדכן תוצאת ליד")
check("no 'מסמך תומך' anywhere in the projection text", "מסמך תומך" not in _all_text(p_a))
check("no 'השג אין אירועים מקושרים' anywhere in the projection text",
      "השג אין אירועים מקושרים" not in _all_text(p_a))
check("no 'אין אירועים מקושרים' leaked into missing_evidence",
      "אין אירועים מקושרים" not in p_a["missing_evidence"])
check("no generic 'הוסף ראיות ועדכן אירועים' action leaked through",
      p_a["next_step"]["action"] != "הוסף ראיות ועדכן אירועים")
check("engine not degraded", p_a["engine"]["degraded"] is False)
check("engine has no errors", p_a["engine"]["errors"] == [])


# ═════════════════════════════════════════════════════════════════
# B. Lead with events, REVIEW -> lead-specific, review-oriented
# ═════════════════════════════════════════════════════════════════
print("\n[B] Lead with events, REVIEW")

# Low-trust events (unknown source_reliability inferred from an unrecognised
# channel) keep confidence < 0.60 so the orchestrator's REVIEW branch fires
# (confidence_score < 0.60 and event_records is non-empty).
LOW_TRUST_EVENT = {"id": "recEV1", "fields": {
    "Event Type": "note", "Message": "x", "Created At": "2026-07-10T09:00:00Z",
}}

p_b = _projection(
    {"Name": "x", "domain": "general", "status": "active", "channel": "unknown"},
    events=[LOW_TRUST_EVENT],
)

check("state remains REVIEW (precondition for this test)", p_b["state"] == "REVIEW")
check("next_step.action is review-oriented and lead-specific",
      p_b["next_step"]["action"] == "סקור את היסטוריית הטיפול והחלט על המשך")
check("next_step.action is not the generic Decision review wording",
      p_b["next_step"]["action"] != "סקור את הראיות הקיימות והחלט אם להמשיך")
check("no generic Decision wording anywhere in the projection text",
      not any(s in _all_text(p_b) for s in _GENERIC_DECISION_STRINGS))
check("engine.degraded=false", p_b["engine"]["degraded"] is False)
check("errors=[]", p_b["engine"]["errors"] == [])


# ═════════════════════════════════════════════════════════════════
# C. Terminal converted -> stays DECIDED, execution-oriented, no reopen
# ═════════════════════════════════════════════════════════════════
print("\n[C] Terminal converted")

p_c_no_events = _projection(
    {"Name": "x", "domain": "general", "status": "active", "Business Outcome": "converted "},
    events=[],
)
p_c_with_events = _projection(
    {"Name": "x", "domain": "general", "status": "active", "Business Outcome": "converted "},
    events=[LOW_TRUST_EVENT],
)

for label, p_c in (("no events", p_c_no_events), ("with events", p_c_with_events)):
    check(f"[{label}] state remains DECIDED", p_c["state"] == "DECIDED")
    check(f"[{label}] next_step remains terminal/execution-oriented",
          p_c["next_step"]["action"] == "העבר לביצוע")
    check(f"[{label}] missing_evidence does not re-open the lead (empty)",
          p_c["missing_evidence"] == [])
    check(f"[{label}] no generic Decision wording leaked through",
          not any(s in _all_text(p_c) for s in _GENERIC_DECISION_STRINGS))
    check(f"[{label}] no lead-specific 'no history' wording either (nothing to re-open with)",
          "חסרה היסטוריית טיפול בליד" not in _all_text(p_c))


# ═════════════════════════════════════════════════════════════════
# D. meeting_scheduled (intermediate) -> stays non-terminal, lead-specific
# ═════════════════════════════════════════════════════════════════
print("\n[D] meeting_scheduled (intermediate Business Outcome)")

p_d_no_events = _projection(
    {"Name": "x", "domain": "general", "status": "active", "Business Outcome": "meeting_scheduled "},
    events=[],
)
p_d_with_events = _projection(
    {"Name": "x", "domain": "general", "status": "active", "Business Outcome": "meeting_scheduled "},
    events=[LOW_TRUST_EVENT],
)

for label, p_d in (("no events", p_d_no_events), ("with events", p_d_with_events)):
    check(f"[{label}] state is not DECIDED/CLOSED (non-terminal)", p_d["state"] not in ("DECIDED", "CLOSED"))
    check(f"[{label}] wording is lead-specific, not generic Decision-document wording",
          not any(s in _all_text(p_d) for s in _GENERIC_DECISION_STRINGS))

check("meeting_scheduled + no events -> lead-specific COLLECTING wording",
      p_d_no_events["next_step"]["action"] == "הוסף הערת טיפול או עדכן תוצאת ליד")
check("meeting_scheduled + no events -> lead-specific missing_evidence",
      p_d_no_events["missing_evidence"] == ["חסרה היסטוריית טיפול בליד"])
check("meeting_scheduled + low-trust events -> lead-specific REVIEW wording",
      p_d_with_events["next_step"]["action"] == "סקור את היסטוריית הטיפול והחלט על המשך")


# ═════════════════════════════════════════════════════════════════
# Confirm no state-logic regression: Phase 2A.1 precedence still holds
# ═════════════════════════════════════════════════════════════════
print("\n[Regression] Phase 2A.1 precedence untouched by wording changes")

p_lost = _projection({"Name": "x", "domain": "general", "status": "active", "Business Outcome": "lost "}, [])
check("lost -> still DECIDED (negative)", p_lost["state"] == "DECIDED")
check("lost -> missing_evidence cleared (terminal)", p_lost["missing_evidence"] == [])

p_dup = _projection({"Name": "x", "domain": "general", "status": "active", "Business Outcome": "duplicate "}, [])
check("duplicate -> still CLOSED (administrative)", p_dup["state"] == "CLOSED")
check("duplicate -> next_step untouched by wording map", p_dup["next_step"]["action"] == "ארכב")

p_done = _projection({"Name": "x", "domain": "general", "status": "done"}, [])
check("status=done alone -> still DECIDED (status fallback)", p_done["state"] == "DECIDED")


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print(f"BUG-104 Phase 2A.2 lead-specific wording: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
