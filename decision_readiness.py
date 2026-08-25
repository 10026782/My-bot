# decision_readiness.py — Decision Hub Stage 3: Readiness Engine
#
# Stage 1 (decision_pipeline.py) scores each Event. Stage 2 (decision_confidence.py)
# scores the whole Decision (Confidence Score, Evidence, Missing Evidence, AI
# Conflict Detection). Stage 3 answers one question on top of both: is this
# Decision ready for a human to sign off on, or is something still missing?
#
# READY does not execute anything — it only signals "ready for human approval".
# No Gateway change, no app.py change, no new table, no auto-action.
#
# Reuse, not duplication (MODULE_RULES SoA): missing-evidence detection is
# delegated to decision_confidence.detect_missing_evidence() — same pure
# function Stage 2 already uses, not reimplemented here. Trust ranking reuses
# decision_pipeline._trust_rank(). DecisionFields.READINESS and
# DecisionReadiness.READY/NOT_READY already existed in airtable_schema.py
# before this module — DecisionReadiness.REVIEW was added (this session) as
# an explicit, disclosed extension of that pre-existing enum, not a new one.
#
# MODULE_RULES Gate 1: pure/read-only over Events + Decision already fetched
# by the caller — no direct Airtable writes (persistence, if any, happens in
# the caller, same pattern as Stage 2's _persist_confidence in cmd_decision.py).

from __future__ import annotations

from dataclasses import dataclass, field

from decision_confidence import ConfidenceResult, detect_missing_evidence
from decision_pipeline import _trust_rank
from airtable_schema import (
    DecisionFields as DF,
    DecisionReadiness as DR,
    DecisionEventFields as EF,
    DecisionEventStatus as ES,
    DecisionEventTag as TAG,
    DecisionTrustLevel as TL,
    DecisionExposureType as EXPOSURE,
)
from tma_api import record_fields

_READY_THRESHOLD = 0.75
_MIN_SUBSTANTIVE_TRUST = TL.T2

_STATUS_EMOJI = {DR.READY: "✅", DR.REVIEW: "🟡", DR.NOT_READY: "🔴"}
_STATUS_LABEL_HE = {
    DR.READY: "מוכנה להכרעה",
    DR.REVIEW: "דורשת בדיקה לפני הכרעה",
    DR.NOT_READY: "לא מוכנה להכרעה",
}


@dataclass
class ReadinessResult:
    status: str  # DecisionReadiness.READY / NOT_READY / REVIEW
    score: float
    blockers: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)
    escalation: list[str] = field(default_factory=list)
    user_message: str = ""
    can_decide: bool = False


def _active_events(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("fields", {}).get(EF.STATUS, ES.ACTIVE) != ES.SUPERSEDED]


def _is_pressure_only(event: dict) -> bool:
    return TAG.PRESSURE_ONLY in (event.get("fields", {}).get(EF.TAGS) or [])


def calc_readiness(decision: dict, events: list[dict], confidence_result: ConfidenceResult) -> ReadinessResult:
    """
    מחשב מוכנות החלטה להכרעה אנושית. לא מבצע שום פעולה — תצוגה בלבד.

    כללים (SPEC Stage 3):
      1. ראיה T0 פעילה לא יכולה להפוך החלטה ל-READY.
      2. חשיפה בסיכון גבוה (משפטי/כספי) + ראיות חסרות -> NOT_READY/REVIEW.
      3. Confidence Score מתחת לסף -> NOT_READY.
      4. קונפליקטים פתוחים -> REVIEW.
      5. Missing Evidence לא ריק -> NOT_READY.
      6. אירועי "לחץ בלבד" לעולם לא משדרגים מוכנות (לא נספרים כראיה מהותית).
      7. ראיות T2/T3 מהותיות מספיקות + אין חסמים -> READY.
      8. READY = איתות בלבד להכרעה אנושית, לא ביצוע.

    סף READY: score >= 0.75 וללא חסמים. REVIEW: קונפליקט פתוח / אנומליית
    סיכון-גבוה / מקור T0 פעיל. אחרת: NOT_READY.
    """
    fields = record_fields(decision)
    active = _active_events(events)

    domain = fields.get(DF.DOMAIN, "")
    missing_evidence = detect_missing_evidence(domain, events)

    blockers: list[str] = []

    if missing_evidence:
        blockers.append("ראיות חסרות: " + ", ".join(missing_evidence))

    has_t0 = any(record_fields(e).get(EF.TRUST_LEVEL) == TL.T0 for e in active)
    if has_t0:
        blockers.append("קיים מקור ברמת אמינות T0 בין הראיות הפעילות")

    has_conflict = bool(confidence_result.conflicting)
    if has_conflict:
        blockers.append(f"קונפליקטים פתוחים בין אירועים ({len(confidence_result.conflicting)})")

    exposure_type = fields.get(DF.EXPOSURE_TYPE, "")
    high_risk_exposure = exposure_type in (EXPOSURE.LEGAL, EXPOSURE.FINANCIAL)
    high_risk_anomaly = high_risk_exposure and bool(missing_evidence)
    if high_risk_anomaly:
        blockers.append(f"חשיפה ברמת סיכון גבוהה ({exposure_type}) עם ראיות חסרות")

    score = confidence_result.score
    if score < _READY_THRESHOLD:
        blockers.append(f"ביטחון בהחלטה ({int(score * 100)}%) מתחת לסף ({int(_READY_THRESHOLD * 100)}%)")

    substantive = [e for e in active if not _is_pressure_only(e)]
    has_enough_substantive = any(
        _trust_rank(record_fields(e).get(EF.TRUST_LEVEL, "")) >= _trust_rank(_MIN_SUBSTANTIVE_TRUST)
        for e in substantive
    )
    if not has_enough_substantive:
        blockers.append("אין מספיק ראיות מהותיות באמינות T2/T3 (לא כולל אירועי לחץ בלבד)")

    if not blockers:
        status = DR.READY
    elif has_conflict or high_risk_anomaly or has_t0:
        status = DR.REVIEW
    else:
        status = DR.NOT_READY

    can_decide = status == DR.READY

    if status == DR.READY:
        user_message = "ההחלטה מוכנה להכרעה — ניתן להעלות לאישור."
    elif status == DR.REVIEW:
        user_message = "ההחלטה דורשת בדיקה לפני הכרעה — יש קונפליקט או אנומליה שצריך אדם לפתור."
    else:
        user_message = "ההחלטה לא מוכנה להכרעה — חסר מידע מהותי."

    result = ReadinessResult(
        status=status,
        score=score,
        blockers=blockers,
        missing_info=list(missing_evidence),
        escalation=[],
        user_message=user_message,
        can_decide=can_decide,
    )
    result.escalation = detect_escalation(decision, result)
    return result


def detect_escalation(decision: dict, result: ReadinessResult) -> list[str]:
    """
    מחזיר רשימת תבניות escalation לפי המצב — מי כדאי שיבדוק את ההחלטה.
    פועל רק על decision["fields"] + result המחושב — לא מקבל events (לפי חתימת SPEC).
    """
    fields = decision.get("fields", {})
    exposure_type = fields.get(DF.EXPOSURE_TYPE, "")
    escalations: list[str] = []

    if result.status != DR.READY:
        if exposure_type == EXPOSURE.LEGAL:
            escalations.append('לפנות לעו"ד')
        if exposure_type == EXPOSURE.FINANCIAL:
            escalations.append('לפנות לרו"ח/יועץ פיננסי')

    if any("קונפליקט" in b for b in result.blockers):
        escalations.append("לקבל עמדת שותף")

    if result.missing_info:
        escalations.append("להעלות/לשייך מסמך תומך")

    return list(dict.fromkeys(escalations))  # dedupe, preserve order


def build_readiness_message(result: ReadinessResult) -> str:
    """תקציר קריא לבני אדם של מוכנות ההחלטה — לשדה תצוגה ב-/decision status."""
    emoji = _STATUS_EMOJI.get(result.status, "⚪")
    label = _STATUS_LABEL_HE.get(result.status, result.status)
    lines = [f"{emoji} מוכנות להכרעה: {label} ({int(result.score * 100)}%)", result.user_message]

    if result.blockers:
        lines.append("🚧 חסמים:\n" + "\n".join(f"  • {b}" for b in result.blockers))
    if result.missing_info:
        lines.append("❓ חסר כדי להחליט:\n" + "\n".join(f"  • {m}" for m in result.missing_info))
    if result.escalation:
        lines.append("📣 מומלץ:\n" + "\n".join(f"  • {e}" for e in result.escalation))

    return "\n".join(lines)
