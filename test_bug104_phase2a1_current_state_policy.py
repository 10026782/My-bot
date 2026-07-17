#!/usr/bin/env python3
# test_bug104_phase2a1_current_state_policy.py
# BUG-104 — Core Reasoning Activation Program
# Phase 2A.1 — Current State Policy Implementation
#
# Run: python3 test_bug104_phase2a1_current_state_policy.py
# Pass condition: exit code 0, all assertions green.
#
# Covers the Phase 2A.1 policy implemented in
# core/adapters/leads_adapter.py::_normalise_status() /
# core/leads_reasoning_projection.py (Business Outcome added to the live ->
# adapter field map), per
# docs/architecture/bug-104/PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md:
#
#   A. Business Outcome terminal (positive/negative/administrative) overrides
#      status entirely.
#   B. Business Outcome intermediate does not close the lead.
#   C. If Business Outcome is not terminal, status drives operational state.
#   D. Score remains lead_score display/passthrough only, never state.
#   E. Lead Events affect evidence/confidence only, never state directly.
#   F. tier / Next Action / Next Followup / Domain category / Domain risk
#      assessment / Domain summary are ignored in Phase 2A.1.
#
# Uses the REAL (unstubbed) airtable_schema / decision_orchestrator modules,
# same approach as test_bug104_phase1_1_contract_hardening.py.

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

from airtable_schema import DecisionStatus
from decision_orchestrator import orchestrate
from core.leads_reasoning_projection import build_reasoning_entity, build_reasoning_projection


def _entity(status_raw: str = "", outcome_raw: str = "", extra_fields: dict | None = None):
    fields = {"Name": "x", "domain": "general"}
    if status_raw:
        fields["status"] = status_raw
    if outcome_raw:
        fields["Business Outcome"] = outcome_raw
    fields.update(extra_fields or {})
    return build_reasoning_entity({"id": "recL", "fields": fields}, [])


def _orchestrate_for(entity):
    return orchestrate(
        {"id": entity.entity_id, "fields": {"Status": entity.status, "Title": "x"}},
        [], [], require_feature_flag=False,
    )


# ═════════════════════════════════════════════════════════════════
# A. Business Outcome terminal positive
# ═════════════════════════════════════════════════════════════════
print("\n[A] Business Outcome terminal positive")

for status_raw in ("active", "new"):
    ent = _entity(status_raw=status_raw, outcome_raw="converted ")
    check(f"converted + status={status_raw} -> DecisionStatus.DECIDED_YES",
          ent.status == DecisionStatus.DECIDED_YES)
    orch = _orchestrate_for(ent)
    check(f"converted + status={status_raw} -> orchestrator phase DECIDED",
          orch.phase == "DECIDED")
    check(f"converted + status={status_raw} -> current_state reflects yes",
          orch.current_state == "הוחלט — כן")
    check(f"converted + status={status_raw} -> next_step not generic 'add evidence'",
          "ראיות" not in orch.next_step.action and "אירועים" not in orch.next_step.action)


# ═════════════════════════════════════════════════════════════════
# B. Business Outcome terminal negative
# ═════════════════════════════════════════════════════════════════
print("\n[B] Business Outcome terminal negative")

for outcome_raw in ("lost ", "not_relevant "):
    ent = _entity(status_raw="active", outcome_raw=outcome_raw)
    check(f"{outcome_raw!r} + status=active -> DecisionStatus.DECIDED_NO",
          ent.status == DecisionStatus.DECIDED_NO)
    orch = _orchestrate_for(ent)
    check(f"{outcome_raw!r} -> orchestrator phase DECIDED (negative branch)",
          orch.phase == "DECIDED")
    check(f"{outcome_raw!r} -> current_state reflects no",
          orch.current_state == "הוחלט — לא")
    check(f"{outcome_raw!r} -> next_step not generic 'add evidence'",
          "ראיות" not in orch.next_step.action and "אירועים" not in orch.next_step.action)

# not_relevant + status=new (spec example)
ent_nr = _entity(status_raw="new", outcome_raw="not_relevant ")
check("not_relevant + status=new -> DECIDED_NO", ent_nr.status == DecisionStatus.DECIDED_NO)


# ═════════════════════════════════════════════════════════════════
# C. Business Outcome terminal administrative
# ═════════════════════════════════════════════════════════════════
print("\n[C] Business Outcome terminal administrative")

for outcome_raw in ("duplicate ", "archived"):
    ent = _entity(status_raw="active", outcome_raw=outcome_raw)
    check(f"{outcome_raw!r} + status=active -> DecisionStatus.CANCELLED",
          ent.status == DecisionStatus.CANCELLED)
    orch = _orchestrate_for(ent)
    check(f"{outcome_raw!r} -> orchestrator phase CLOSED (administrative branch)",
          orch.phase == "CLOSED")
    check(f"{outcome_raw!r} -> current_state reflects cancellation",
          orch.current_state == "בוטל")


# ═════════════════════════════════════════════════════════════════
# D. Business Outcome intermediate — does not close the lead
# ═════════════════════════════════════════════════════════════════
print("\n[D] Business Outcome intermediate")

EVENT = {"id": "recEV1", "fields": {"Event Type": "interest", "Message": "x",
                                    "Created At": "2026-07-10T09:00:00Z"}}

ent_ms = _entity(status_raw="active", outcome_raw="meeting_scheduled ")
check("meeting_scheduled + status=active -> not DECIDED_YES/NO/CANCELLED",
      ent_ms.status not in (DecisionStatus.DECIDED_YES, DecisionStatus.DECIDED_NO, DecisionStatus.CANCELLED))
check("meeting_scheduled + status=active -> falls to operational OPEN",
      ent_ms.status == DecisionStatus.OPEN)

orch_ms = orchestrate(
    {"id": "recL", "fields": {"Status": ent_ms.status, "Title": "x"}},
    [EVENT, EVENT], [], require_feature_flag=False,
)
check("meeting_scheduled + events present -> orchestrator phase NOT DECIDED/CLOSED",
      orch_ms.phase not in ("DECIDED", "CLOSED"))

for outcome_raw in ("needs_followup ", "open ", "ליד חדש"):
    ent = _entity(status_raw="active", outcome_raw=outcome_raw)
    check(f"intermediate outcome {outcome_raw!r} -> not terminal (status stays OPEN)",
          ent.status == DecisionStatus.OPEN)


# ═════════════════════════════════════════════════════════════════
# E. Status fallback (Business Outcome missing)
# ═════════════════════════════════════════════════════════════════
print("\n[E] Status fallback — Business Outcome missing")

ent_done = _entity(status_raw="done")
check("Business Outcome missing + status=done -> DECIDED_YES",
      ent_done.status == DecisionStatus.DECIDED_YES)
orch_done = _orchestrate_for(ent_done)
check("status=done alone -> orchestrator phase DECIDED", orch_done.phase == "DECIDED")


# ═════════════════════════════════════════════════════════════════
# F. Live status mapping — no crash, expected OPEN behavior
# ═════════════════════════════════════════════════════════════════
print("\n[F] Live status mapping (no Business Outcome)")

_OPEN_STATUSES = ("active", "waiting_call", "waiting_response", "high_confidence", "new", "ליד חדש")
for status_raw in _OPEN_STATUSES:
    ent = _entity(status_raw=status_raw)
    check(f"status={status_raw!r} -> no crash, DecisionStatus.OPEN",
          ent.status == DecisionStatus.OPEN)
    orch = _orchestrate_for(ent)
    check(f"status={status_raw!r} -> orchestrator phase NOT DECIDED/CLOSED",
          orch.phase not in ("DECIDED", "CLOSED"))

ent_hc = _entity(status_raw="high_confidence")
check("high_confidence preserves a metadata signal (not silently indistinguishable)",
      ent_hc.metadata.get("status_high_signal") is True)
ent_active = _entity(status_raw="active")
check("active does NOT set the high_confidence metadata signal",
      ent_active.metadata.get("status_high_signal") is False)


# ═════════════════════════════════════════════════════════════════
# G. Score — passthrough only, never independently sets DECIDED/CLOSED
# ═════════════════════════════════════════════════════════════════
print("\n[G] Score does not become confidence/state")

ent_hi_score = _entity(status_raw="active", extra_fields={"Score": 98})
check("Score=98 does not change entity.status by itself", ent_hi_score.status == DecisionStatus.OPEN)
check("Score reaches metadata.lead_score honestly", ent_hi_score.metadata["lead_score"] == 98)

proj_hi_score = build_reasoning_projection(
    {"id": "recX", "fields": {"Name": "x", "domain": "general", "status": "active", "Score": 98}},
    [], AS_OF,
)
check("high Score alone -> projection state not DECIDED (no events, no terminal outcome)",
      proj_hi_score["state"] != "DECIDED")
check("lead_score passthrough reflects raw Score, unrelated to state",
      proj_hi_score["lead_score"]["value"] == 98)


# ═════════════════════════════════════════════════════════════════
# H. Excluded fields — tier / Next Action / Next Followup / Domain* ignored
# ═════════════════════════════════════════════════════════════════
print("\n[H] Excluded fields do not change Phase 2A.1 terminal policy")

baseline = _entity(status_raw="active", outcome_raw="converted ")
polluted = _entity(status_raw="active", outcome_raw="converted ", extra_fields={
    "tier": "רותח",
    "Next Action": "Call Back",
    "Next Followup": "2026-08-01",
    "Domain category": "Technology",
    "Domain risk assessment": "High risk",
    "Domain summary": "irrelevant ai text",
})
check("injecting excluded fields does not change entity.status",
      polluted.status == baseline.status == DecisionStatus.DECIDED_YES)

orch_baseline = _orchestrate_for(baseline)
orch_polluted = _orchestrate_for(polluted)
check("injecting excluded fields does not change orchestrator phase",
      orch_polluted.phase == orch_baseline.phase == "DECIDED")

# Excluded fields must also not appear in the public projection envelope.
proj_polluted = build_reasoning_projection(
    {"id": "recX", "fields": {
        "Name": "x", "domain": "general", "status": "active", "Business Outcome": "meeting_scheduled ",
        "tier": "רותח", "Next Action": "Call Back", "Next Followup": "2026-08-01",
        "Domain category": "Technology", "Domain risk assessment": "High risk",
        "Domain summary": "irrelevant ai text",
    }},
    [], AS_OF,
)
check("projection top-level envelope unaffected by excluded fields",
      set(proj_polluted.keys()) == {"version", "as_of", "state", "readiness", "confidence",
                                     "missing_evidence", "verifier", "next_step",
                                     "attention_priority", "lead_score", "events", "engine"})


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print(f"BUG-104 Phase 2A.1 current state policy: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
