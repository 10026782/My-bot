# decision_confidence.py — Decision Hub Stage 2: Smart Trust Layer (F17)
#
# Stage 1 (decision_pipeline.py) scores each Event in isolation. Stage 2 looks
# at the whole Decision: do the events it rests on agree, what's missing, how
# confident should the Owner be before signing.
#
# AI Conflict Detection is Lazy + Cached, NOT eager (Eliyahu's approval
# condition on SPEC F17): it never runs on event ingest. It runs only when a
# Decision is opened or explicitly refreshed (called from cmd_decision.py's
# /decision status handler), restricted to the same Claim Topic, restricted to
# Trust Level >= T1, deduped by event-pair hash, and capped per run.
#
# This fulfils the _has_keyword_conflict() stub decision_pipeline.py left as a
# no-op in Stage 1 ("תוגדר במפרט Stage 1.x / Stage 2") — via AI comparison
# instead of keyword matching. The keyword stub itself is left untouched;
# Stage 2 is a parallel signal (DecisionEventTag.CONFLICT), not a replacement.
#
# MODULE_RULES Gate 1: every function here is pure/read-only over Events
# already fetched by the caller — no direct Airtable writes. The one infra
# call (call_anthropic_text) is the same shared LLM wrapper already used
# directly by lead_qualifier.py/daily_collector.py, not a new injection point.

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field

from decision_pipeline import _trust_rank
from airtable_schema import (
    DecisionEventFields as EF,
    DecisionTrustLevel as TL,
    DecisionEventStatus as ES,
    DecisionDomain as DOMAIN,
)

logger = logging.getLogger(__name__)

_MAX_AI_COMPARISONS_PER_RUN = 5
_CONFLICT_PENALTY = 0.15
_MISSING_PENALTY = 0.10
_MIN_TRUST_FOR_AI_CONFLICT = TL.T1

# event_pair_hash -> ConflictResult. Process-local; fine for MVP (mirrors the
# in-process _pending dict pattern already used in cmd_decision.py — no new
# persistence layer for an optimization cache).
_conflict_cache: dict[str, "ConflictResult"] = {}

_TRUST_SCORE: dict[str, float] = {TL.T0: 0.1, TL.T1: 0.4, TL.T2: 0.7, TL.T3: 0.95}

# Spec F17 keyed this by an undefined "decision_type" concept that doesn't
# exist anywhere in the schema (Decisions only has Domain). Mapped onto the
# existing DecisionDomain values instead of inventing a parallel taxonomy —
# disclosed deviation, see CHANGE_CONTROL_LOG.md F17 entry.
REQUIRED_EVIDENCE: dict[str, list[str]] = {
    DOMAIN.REAL_ESTATE: ["חוזה", "שמאות", "אישור בנק", "חוות דעת עו\"ד"],
    DOMAIN.IMPORT: ["הצעת מחיר", "חוזה", "אישור שותפים"],
    DOMAIN.PARTNERSHIP: ["הצעת מחיר", "חוזה", "אישור שותפים"],
    DOMAIN.RECRUITMENT: ["קורות חיים", "ראיון", "המלצות"],
    DOMAIN.GENERAL: ["מסמך תומך"],
}
_DEFAULT_REQUIRED_EVIDENCE = REQUIRED_EVIDENCE[DOMAIN.GENERAL]


@dataclass
class ConflictResult:
    is_conflict: bool
    aspect: str | None = None
    severity: str | None = None  # low/med/high
    event_ids: tuple[str, str] = ("", "")


@dataclass
class ConfidenceResult:
    score: float
    supporting: list[str] = field(default_factory=list)
    conflicting: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _active_events(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("fields", {}).get(EF.STATUS, ES.ACTIVE) != ES.SUPERSEDED]


def _event_pair_hash(event_a: dict, event_b: dict) -> str:
    ids = sorted([event_a.get("id", ""), event_b.get("id", "")])
    return hashlib.sha256("|".join(ids).encode()).hexdigest()


def detect_conflict_ai(event_a: dict, event_b: dict) -> ConflictResult:
    """קריאה בודדת ל-Claude להשוואת שני אירועים מאותו Claim Topic.
    לא נקראת ישירות בזרימה — ראו detect_conflicts_ai_lazy() למגבלות."""
    from llm_fallback import call_anthropic_text

    fa = event_a.get("fields", {})
    fb = event_b.get("fields", {})
    text_a = fa.get(EF.AI_SUMMARY) or fa.get(EF.RAW_CONTENT, "")
    text_b = fb.get(EF.AI_SUMMARY) or fb.get(EF.RAW_CONTENT, "")

    prompt = (
        "שני אירועים מתוך אותו תהליך החלטה עסקית. קבע אם הם סותרים מבחינה "
        "עניינית (לא ניסוח). החזר JSON בלבד, ללא טקסט נוסף: "
        '{"is_conflict": true/false, "aspect": "<תחום הסתירה או null>", '
        '"severity": "low"/"med"/"high"/null}\n\n'
        f"אירוע א: {text_a}\n\nאירוע ב: {text_b}"
    )
    try:
        raw = call_anthropic_text(
            source="decision_confidence.detect_conflict_ai",
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        data = json.loads(raw)
        return ConflictResult(
            is_conflict=bool(data.get("is_conflict")),
            aspect=data.get("aspect"),
            severity=data.get("severity"),
            event_ids=(event_a.get("id", ""), event_b.get("id", "")),
        )
    except Exception as e:
        logger.warning(f"[decision_confidence] detect_conflict_ai failed: {e}")
        return ConflictResult(is_conflict=False, event_ids=(event_a.get("id", ""), event_b.get("id", "")))


def detect_conflicts_ai_lazy(events: list[dict]) -> list[ConflictResult]:
    """
    Lazy + cached conflict scan. נקרא רק בפתיחת/Refresh של Decision — לעולם לא ב-ingest.
    מגבלות (תנאי האישור של אליהו ל-SPEC F17):
      - רק אירועים מאותו Claim Topic
      - רק Trust Level >= T1
      - cache לפי event_pair_hash — לא משווים זוג פעמיים
      - מקסימום _MAX_AI_COMPARISONS_PER_RUN קריאות Claude חדשות לכל ריצה
        (זוגות שכבר ב-cache לא נספרים במגבלה, רק קריאות Claude בפועל)
    """
    eligible = [
        e for e in _active_events(events)
        if _trust_rank(e.get("fields", {}).get(EF.TRUST_LEVEL, "")) >= _trust_rank(_MIN_TRUST_FOR_AI_CONFLICT)
        and e.get("fields", {}).get(EF.CLAIM_TOPIC)
    ]

    by_topic: dict[str, list[dict]] = {}
    for e in eligible:
        by_topic.setdefault(e["fields"][EF.CLAIM_TOPIC], []).append(e)

    results: list[ConflictResult] = []
    comparisons = 0
    for topic_events in by_topic.values():
        for i in range(len(topic_events)):
            for j in range(i + 1, len(topic_events)):
                a, b = topic_events[i], topic_events[j]
                h = _event_pair_hash(a, b)
                if h in _conflict_cache:
                    cached = _conflict_cache[h]
                    if cached.is_conflict:
                        results.append(cached)
                    continue
                if comparisons >= _MAX_AI_COMPARISONS_PER_RUN:
                    continue  # ה-cache עדיין נבדק לזוגות אחרים; רק לא קוראים ל-Claude יותר בריצה הזו
                comparisons += 1
                result = detect_conflict_ai(a, b)
                _conflict_cache[h] = result
                if result.is_conflict:
                    results.append(result)
    return results


def calc_confidence(
    events: list[dict],
    conflicts: list[ConflictResult] | None = None,
    domain: str | None = None,
) -> ConfidenceResult:
    """
    ציון confidence להחלטה לפי האירועים התומכים בה.
    score = weighted_avg(trust) - 0.15*conflicts - 0.10*missing, clamped [0,1].
    conflicts=None -> מריץ detect_conflicts_ai_lazy() (קורא ל-Claude, מוגבל וזמין-cache).
    conflicts=[] (במפורש) -> מדלג על AI, שימושי לבדיקות/refresh ללא תקציב Claude.
    domain=None -> שומר תאימות לאחור ללא missing-evidence penalty.
    """
    active = _active_events(events)
    if not active:
        return ConfidenceResult(score=0.0, missing=["אין אירועים מקושרים"])

    trust_scores = [_TRUST_SCORE.get(e["fields"].get(EF.TRUST_LEVEL, ""), 0.3) for e in active]
    base_score = sum(trust_scores) / len(trust_scores)

    if conflicts is None:
        conflicts = detect_conflicts_ai_lazy(events)
    conflict_penalty = _CONFLICT_PENALTY * len(conflicts)

    missing = detect_missing_evidence(domain, events) if domain else []
    missing_penalty = _MISSING_PENALTY * len(missing)

    score = max(0.0, min(1.0, base_score - conflict_penalty - missing_penalty))

    conflicting_ids = {eid for c in conflicts for eid in c.event_ids if eid}
    supporting = [e["id"] for e in active if e.get("id") not in conflicting_ids]

    return ConfidenceResult(
        score=round(score, 2),
        supporting=supporting,
        conflicting=sorted(conflicting_ids),
        missing=missing,
    )


def detect_missing_evidence(domain: str, events: list[dict]) -> list[str]:
    """
    משווה תוכן האירועים הפעילים מול תבנית REQUIRED_EVIDENCE[domain].
    לא LLM — בדיקת מילת-מפתח פשוטה: קיים Event שמזכיר את הפריט הנדרש?
    """
    required = REQUIRED_EVIDENCE.get(domain, _DEFAULT_REQUIRED_EVIDENCE)
    present_text = " ".join(
        f"{e.get('fields', {}).get(EF.AI_SUMMARY, '')} {e.get('fields', {}).get(EF.RAW_CONTENT, '')}"
        for e in _active_events(events)
    )
    return [item for item in required if item not in present_text]


def build_evidence_summary(events: list[dict]) -> str:
    """תקציר קריא לבני אדם של האירועים התומכים — לשדה Evidence Summary."""
    active = _active_events(events)
    if not active:
        return "(אין ראיות מקושרות)"
    counts: dict[str, int] = {}
    for e in active:
        et = e.get("fields", {}).get(EF.EVENT_TYPE) or "אחר"
        counts[et] = counts.get(et, 0) + 1
    return ", ".join(f"{count} {etype}" for etype, count in counts.items())
