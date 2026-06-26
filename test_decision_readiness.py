#!/usr/bin/env python3
# test_decision_readiness.py — Regression tests for Decision Hub Stage 3
# Readiness Engine.
#
# Run: python3 test_decision_readiness.py
# Pass condition: exit code 0, all assertions green.
#
# Covers the 6 SPEC-mandated cases (Decision Hub Stage 3: Readiness Engine):
#   - READY with strong evidence and no missing info
#   - NOT_READY with missing evidence
#   - REVIEW with unresolved conflict
#   - pressure-only event does not improve readiness
#   - high-risk legal/financial missing evidence escalates
#   - empty events does not crash
#
# No Claude calls here — confidence_result is always passed in explicitly
# (calc_readiness never calls detect_conflicts_ai_lazy itself; that's Stage 2's
# job, already covered by test_decision_confidence.py).

from __future__ import annotations

import sys

from decision_readiness import calc_readiness, build_readiness_message, detect_escalation
from decision_confidence import ConfidenceResult
from airtable_schema import (
    DecisionFields as DF,
    DecisionDomain as DOMAIN,
    DecisionExposureType as EXPOSURE,
    DecisionReadiness as DR,
    DecisionEventFields as EF,
    DecisionTrustLevel as TL,
    DecisionEventStatus as ES,
    DecisionEventTag as TAG,
)

_passed = 0
_failed = 0


def check(desc: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        print(f"✅ {desc}")
        _passed += 1
    else:
        print(f"❌ {desc}")
        _failed += 1


def dec(domain=DOMAIN.GENERAL, exposure_type=""):
    return {"id": "decX", "fields": {DF.DOMAIN: domain, DF.EXPOSURE_TYPE: exposure_type}}


def ev(id_, trust=TL.T2, status=ES.ACTIVE, event_type="מסמך", summary="", tags=None):
    fields = {EF.TRUST_LEVEL: trust, EF.STATUS: status, EF.EVENT_TYPE: event_type}
    if summary:
        fields[EF.AI_SUMMARY] = summary
    if tags:
        fields[EF.TAGS] = tags
    return {"id": id_, "fields": fields}


def conf(score=0.9, supporting=None, conflicting=None):
    return ConfidenceResult(score=score, supporting=supporting or [], conflicting=conflicting or [], missing=[])


# ═════════════════════════════════════════════════════════════════
# 1. READY — strong evidence, no missing info
# ═════════════════════════════════════════════════════════════════

events = [
    ev("r1", trust=TL.T3, summary="מסמך תומך מצורף"),
    ev("r2", trust=TL.T3, summary="מסמך תומך נוסף"),
]
result = calc_readiness(dec(DOMAIN.GENERAL), events, conf(score=0.95, supporting=["r1", "r2"]))
check("READY: strong evidence + no missing -> status READY", result.status == DR.READY)
check("READY: no blockers", result.blockers == [])
check("READY: can_decide True", result.can_decide is True)
check("READY: missing_info empty", result.missing_info == [])
check("build_readiness_message doesn't crash on READY", "✅" in build_readiness_message(result))


# ═════════════════════════════════════════════════════════════════
# 2. NOT_READY — missing evidence
# ═════════════════════════════════════════════════════════════════

events = [ev("r1", trust=TL.T3, summary="")]
result = calc_readiness(dec(DOMAIN.REAL_ESTATE), events, conf(score=0.9, supporting=["r1"]))
check("NOT_READY: missing required evidence -> status NOT_READY", result.status == DR.NOT_READY)
check("NOT_READY: missing_info non-empty", len(result.missing_info) > 0)
check("NOT_READY: blockers non-empty", len(result.blockers) > 0)
check("NOT_READY: can_decide False", result.can_decide is False)


# ═════════════════════════════════════════════════════════════════
# 3. REVIEW — unresolved conflict
# ═════════════════════════════════════════════════════════════════

events = [
    ev("r1", trust=TL.T3, summary="מסמך תומך"),
    ev("r2", trust=TL.T3, summary="מסמך תומך"),
]
result = calc_readiness(dec(DOMAIN.GENERAL), events, conf(score=0.8, conflicting=["r1", "r2"]))
check("REVIEW: unresolved conflict -> status REVIEW", result.status == DR.REVIEW)
check("REVIEW: conflict reflected in blockers", any("קונפליקט" in b for b in result.blockers))
check("REVIEW: can_decide False", result.can_decide is False)


# ═════════════════════════════════════════════════════════════════
# 4. Pressure-only event does not improve readiness
# ═════════════════════════════════════════════════════════════════

events = [ev("r1", trust=TL.T3, summary="מסמך תומך", tags=[TAG.PRESSURE_ONLY])]
result = calc_readiness(dec(DOMAIN.GENERAL), events, conf(score=0.95, supporting=["r1"]))
check("pressure-only: high score + high trust but pressure-tagged -> NOT READY",
      result.status != DR.READY)
check("pressure-only: substantive-evidence blocker present",
      any("אירועי לחץ" in b for b in result.blockers))

mixed_events = [
    ev("r1", trust=TL.T3, summary="מסמך תומך", tags=[TAG.PRESSURE_ONLY]),
    ev("r2", trust=TL.T3, summary="מסמך תומך"),
]
result_mixed = calc_readiness(dec(DOMAIN.GENERAL), mixed_events, conf(score=0.95, supporting=["r1", "r2"]))
check("pressure-only: one substantive T3 event alongside pressure-only -> still READY",
      result_mixed.status == DR.READY)


# ═════════════════════════════════════════════════════════════════
# 5. High-risk legal/financial missing evidence escalates
# ═════════════════════════════════════════════════════════════════

events = [ev("r1", trust=TL.T3, summary="")]
result_legal = calc_readiness(dec(DOMAIN.REAL_ESTATE, EXPOSURE.LEGAL), events, conf(score=0.9, supporting=["r1"]))
check("legal exposure + missing evidence -> REVIEW (high-risk anomaly)", result_legal.status == DR.REVIEW)
check('legal exposure escalates to lawyer', 'לפנות לעו"ד' in result_legal.escalation)
check("legal exposure also escalates missing-document", "להעלות/לשייך מסמך תומך" in result_legal.escalation)

result_fin = calc_readiness(dec(DOMAIN.IMPORT, EXPOSURE.FINANCIAL), events, conf(score=0.9, supporting=["r1"]))
check("financial exposure + missing evidence -> REVIEW", result_fin.status == DR.REVIEW)
check('financial exposure escalates to accountant', 'לפנות לרו"ח/יועץ פיננסי' in result_fin.escalation)

result_partner = calc_readiness(
    dec(DOMAIN.GENERAL),
    [ev("r1", trust=TL.T3, summary="מסמך תומך"), ev("r2", trust=TL.T3, summary="מסמך תומך")],
    conf(score=0.8, conflicting=["r1", "r2"]),
)
check("unresolved conflict escalates to partner-position request",
      "לקבל עמדת שותף" in detect_escalation(dec(DOMAIN.GENERAL), result_partner))


# ═════════════════════════════════════════════════════════════════
# 6. Empty events does not crash
# ═════════════════════════════════════════════════════════════════

result_empty = calc_readiness(dec(DOMAIN.GENERAL), [], conf(score=0.0))
check("empty events: no crash, status computed", result_empty.status in (DR.READY, DR.NOT_READY, DR.REVIEW))
check("empty events: not READY", result_empty.status != DR.READY)
check("empty events: missing_info == full GENERAL template",
      result_empty.missing_info == ["מסמך תומך"])
check("build_readiness_message doesn't crash on empty-events result",
      isinstance(build_readiness_message(result_empty), str))


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════

print(f"\n{'═'*50}")
print(f"Decision Hub Stage 3 Readiness Engine: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
