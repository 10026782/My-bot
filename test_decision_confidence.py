#!/usr/bin/env python3
# test_decision_confidence.py — Regression tests for Decision Hub Stage 2 Smart
# Trust Layer (F17).
#
# Run: python3 test_decision_confidence.py
# Pass condition: exit code 0, all assertions green.
#
# Covers (SPEC F17, as amended by Eliyahu's Lazy+Cached approval condition):
#   - calc_confidence(): weighted trust average, conflict penalty, clamp,
#     empty-events fallback, supporting/conflicting split
#   - build_evidence_summary(): per-Event-Type counts, empty fallback
#   - detect_missing_evidence(): per-domain REQUIRED_EVIDENCE template check
#   - detect_conflicts_ai_lazy(): Trust>=T1 filter, same-Claim-Topic grouping,
#     event_pair_hash cache (hit doesn't call Claude, doesn't count against cap),
#     _MAX_AI_COMPARISONS_PER_RUN cap
#
# detect_conflict_ai() (the actual Claude call) is monkeypatched throughout —
# zero network calls, zero API cost, mirrors test_decision_trust.py's
# FakeVerifier mocking style.

from __future__ import annotations

import sys

import decision_confidence as dc
from decision_confidence import (
    calc_confidence, build_evidence_summary, detect_missing_evidence,
    detect_conflicts_ai_lazy, ConflictResult,
)
from airtable_schema import (
    DecisionEventFields as EF,
    DecisionTrustLevel as TL,
    DecisionEventStatus as ES,
    DecisionDomain as DOMAIN,
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


def ev(id_, trust=TL.T2, topic=None, status=ES.ACTIVE, event_type="מסמך", summary="", raw=""):
    fields = {EF.TRUST_LEVEL: trust, EF.STATUS: status, EF.EVENT_TYPE: event_type}
    if topic is not None:
        fields[EF.CLAIM_TOPIC] = topic
    if summary:
        fields[EF.AI_SUMMARY] = summary
    if raw:
        fields[EF.RAW_CONTENT] = raw
    return {"id": id_, "fields": fields}


# ═════════════════════════════════════════════════════════════════
# calc_confidence
# ═════════════════════════════════════════════════════════════════

check("calc_confidence: no events -> score 0, missing flag",
      calc_confidence([]).score == 0.0 and calc_confidence([]).missing)

events = [ev("rec1", trust=TL.T3), ev("rec2", trust=TL.T3)]
result = calc_confidence(events, conflicts=[])
check("calc_confidence: all T3, no conflicts -> score == T3 weight (0.95)", result.score == 0.95)
check("calc_confidence: all-supporting when no conflicts", set(result.supporting) == {"rec1", "rec2"})

events_mixed = [ev("rec1", trust=TL.T0), ev("rec2", trust=TL.T3)]
result = calc_confidence(events_mixed, conflicts=[])
check("calc_confidence: weighted average of T0+T3", result.score == round((0.1 + 0.95) / 2, 2))

events = [ev("rec1", trust=TL.T3), ev("rec2", trust=TL.T3)]
conflicts = [ConflictResult(is_conflict=True, event_ids=("rec1", "rec2"))]
result = calc_confidence(events, conflicts=conflicts)
check("calc_confidence: conflict penalty applied (0.95 - 0.15)", abs(result.score - 0.80) < 0.001)
check("calc_confidence: conflicting ids surfaced", result.conflicting == ["rec1", "rec2"])
check("calc_confidence: conflicting events excluded from supporting", result.supporting == [])

events_many_conflicts = [ev("r1", trust=TL.T3), ev("r2", trust=TL.T3)]
many_conflicts = [ConflictResult(is_conflict=True, event_ids=("r1", "r2")) for _ in range(10)]
result = calc_confidence(events_many_conflicts, conflicts=many_conflicts)
check("calc_confidence: score clamped to 0 floor under heavy conflict penalty", result.score == 0.0)

superseded = [ev("rec1", trust=TL.T3, status=ES.SUPERSEDED), ev("rec2", trust=TL.T1)]
result = calc_confidence(superseded, conflicts=[])
check("calc_confidence: superseded events excluded from scoring", result.score == 0.4 and result.supporting == ["rec2"])

check("calc_confidence: conflicts=None triggers lazy AI path (no crash, no Claim Topic -> no comparisons)",
      calc_confidence([ev("rec1", trust=TL.T2), ev("rec2", trust=TL.T2)]).score is not None)

domain_result = calc_confidence([ev("rec1", trust=TL.T3)], conflicts=[], domain=DOMAIN.GENERAL)
check("calc_confidence: domain applies missing-evidence penalty",
      domain_result.score == 0.85)
check("calc_confidence: domain returns missing evidence",
      domain_result.missing == dc.REQUIRED_EVIDENCE[DOMAIN.GENERAL])

required_general = dc.REQUIRED_EVIDENCE[DOMAIN.GENERAL][0]
complete_result = calc_confidence(
    [ev("rec1", trust=TL.T3, summary=required_general)],
    conflicts=[],
    domain=DOMAIN.GENERAL,
)
check("calc_confidence: present domain evidence avoids missing penalty",
      complete_result.score == 0.95 and complete_result.missing == [])


# ═════════════════════════════════════════════════════════════════
# build_evidence_summary
# ═════════════════════════════════════════════════════════════════

check("build_evidence_summary: no active events -> placeholder", build_evidence_summary([]) == "(אין ראיות מקושרות)")

events = [ev("r1", event_type="חוזה"), ev("r2", event_type="חוזה"), ev("r3", event_type="טיוטה")]
summary = build_evidence_summary(events)
check("build_evidence_summary: counts per Event Type", "2 חוזה" in summary and "1 טיוטה" in summary)

superseded_only = [ev("r1", status=ES.SUPERSEDED)]
check("build_evidence_summary: ignores superseded events", build_evidence_summary(superseded_only) == "(אין ראיות מקושרות)")


# ═════════════════════════════════════════════════════════════════
# detect_missing_evidence
# ═════════════════════════════════════════════════════════════════

check("detect_missing_evidence: unknown domain falls back to GENERAL template",
      detect_missing_evidence("לא קיים", []) == dc.REQUIRED_EVIDENCE[DOMAIN.GENERAL])

events = [ev("r1", summary="חתמנו על חוזה אחרי שמאות מלאה")]
missing = detect_missing_evidence(DOMAIN.REAL_ESTATE, events)
check("detect_missing_evidence: present items removed from missing list",
      "חוזה" not in missing and "שמאות" not in missing)
check("detect_missing_evidence: absent items remain", "אישור בנק" in missing and 'חוות דעת עו"ד' in missing)

check("detect_missing_evidence: no events -> all required items missing",
      detect_missing_evidence(DOMAIN.RECRUITMENT, []) == dc.REQUIRED_EVIDENCE[DOMAIN.RECRUITMENT])


# ═════════════════════════════════════════════════════════════════
# detect_conflicts_ai_lazy — Trust filter / Claim Topic grouping / cache / cap
# ═════════════════════════════════════════════════════════════════

def _reset_cache():
    dc._conflict_cache.clear()


def _mock_ai(calls_log, is_conflict=False):
    def fake(event_a, event_b):
        calls_log.append((event_a["id"], event_b["id"]))
        return ConflictResult(is_conflict=is_conflict, event_ids=(event_a["id"], event_b["id"]))
    return fake


_reset_cache()
calls = []
dc.detect_conflict_ai = _mock_ai(calls)
events_no_topic = [ev("r1", trust=TL.T2, topic=None), ev("r2", trust=TL.T2, topic=None)]
detect_conflicts_ai_lazy(events_no_topic)
check("detect_conflicts_ai_lazy: events without Claim Topic are never compared", calls == [])

_reset_cache()
calls = []
dc.detect_conflict_ai = _mock_ai(calls)
events_low_trust = [ev("r1", trust=TL.T0, topic="price"), ev("r2", trust=TL.T1, topic="price")]
detect_conflicts_ai_lazy(events_low_trust)
check("detect_conflicts_ai_lazy: T0 (below T1 floor) excluded from comparisons", calls == [])

_reset_cache()
calls = []
dc.detect_conflict_ai = _mock_ai(calls)
events_diff_topic = [ev("r1", trust=TL.T2, topic="price"), ev("r2", trust=TL.T2, topic="date")]
detect_conflicts_ai_lazy(events_diff_topic)
check("detect_conflicts_ai_lazy: different Claim Topics are never compared", calls == [])

_reset_cache()
calls = []
dc.detect_conflict_ai = _mock_ai(calls)
events_same_topic = [ev("r1", trust=TL.T2, topic="price"), ev("r2", trust=TL.T3, topic="price")]
results = detect_conflicts_ai_lazy(events_same_topic)
check("detect_conflicts_ai_lazy: same topic, both Trust>=T1 -> compared once", len(calls) == 1)

_reset_cache()
calls = []
dc.detect_conflict_ai = _mock_ai(calls)
events_same_topic2 = [ev("r1", trust=TL.T2, topic="price"), ev("r2", trust=TL.T3, topic="price")]
detect_conflicts_ai_lazy(events_same_topic2)
detect_conflicts_ai_lazy(events_same_topic2)
check("detect_conflicts_ai_lazy: second run on same pair hits cache, no new Claude call", len(calls) == 1)

_reset_cache()
calls = []
dc.detect_conflict_ai = _mock_ai(calls, is_conflict=True)
events_conflict = [ev("r1", trust=TL.T2, topic="price"), ev("r2", trust=TL.T3, topic="price")]
results = detect_conflicts_ai_lazy(events_conflict)
check("detect_conflicts_ai_lazy: conflict result surfaced in return list", len(results) == 1 and results[0].is_conflict)

_reset_cache()
calls = []
dc.detect_conflict_ai = _mock_ai(calls)
many_events = [ev(f"r{i}", trust=TL.T2, topic="price") for i in range(6)]  # C(6,2)=15 pairs > cap of 5
detect_conflicts_ai_lazy(many_events)
check(f"detect_conflicts_ai_lazy: capped at {dc._MAX_AI_COMPARISONS_PER_RUN} new Claude calls per run",
      len(calls) == dc._MAX_AI_COMPARISONS_PER_RUN)

_reset_cache()
calls = []
dc.detect_conflict_ai = _mock_ai(calls)
superseded_excluded = [
    ev("r1", trust=TL.T2, topic="price", status=ES.SUPERSEDED),
    ev("r2", trust=TL.T2, topic="price"),
]
detect_conflicts_ai_lazy(superseded_excluded)
check("detect_conflicts_ai_lazy: superseded events excluded from comparison pool", calls == [])


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'═'*50}")
    print(f"Decision Hub Stage 2 Smart Trust Layer: {_passed}/{_passed+_failed} passed")
    if _failed:
        print(f"FAILED: {_failed} test(s)")
    sys.exit(0 if _failed == 0 else 1)
