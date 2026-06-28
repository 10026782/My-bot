"""Decision Hub Stage 6: read-only lifecycle orchestration.

The orchestrator is pull-only. It receives records already fetched by the
caller, determines the first matching lifecycle phase, and returns a display
model. It never writes canonical state, sends messages, or creates actions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from airtable_schema import (
    DecisionDomain as Domain,
    DecisionFields as DF,
    DecisionReadiness as Readiness,
    DecisionStakeholderFields as SF,
    DecisionStakeholderPosition as StakeholderPosition,
    DecisionStakeholderRole as StakeholderRole,
    DecisionStatus,
)

logger = logging.getLogger(__name__)

FEATURE_FLAG = "FEATURE_DECISION_HUB"

PHASE_COLLECTING = "COLLECTING"
PHASE_BLOCKED = "BLOCKED"
PHASE_REVIEW = "REVIEW"
PHASE_AWAITING = "AWAITING"
PHASE_DECIDED = "DECIDED"
PHASE_CLOSED = "CLOSED"

CONFIDENCE_REVIEW_THRESHOLD = 0.60
CONFIDENCE_DECIDE_THRESHOLD = 0.75

OWNER_LABEL = "בעל ההחלטה"
MANAGER_LABEL = "מנהל"
TEAM_LABEL = "הצוות"
SYSTEM_LABEL = "המערכת"


@dataclass(frozen=True)
class NextStep:
    action: str
    responsible: str
    detail: str = ""


@dataclass(frozen=True)
class OrchestratorResult:
    decision_id: str
    title: str
    phase: str
    current_state: str
    next_step: NextStep
    blockers: tuple[str, ...] = field(default_factory=tuple)
    awaiting_owner: bool = False
    confidence_score: float = 0.0
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    after_resolution: str = ""

    def as_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "title": self.title,
            "phase": self.phase,
            "current_state": self.current_state,
            "next_step": {
                "action": self.next_step.action,
                "responsible": self.next_step.responsible,
                "detail": self.next_step.detail,
            },
            "blockers": list(self.blockers),
            "awaiting_owner": self.awaiting_owner,
            "confidence_score": self.confidence_score,
            "missing_evidence": list(self.missing_evidence),
            "after_resolution": self.after_resolution,
        }


def orchestrate(
    decision: dict,
    events: list[dict] | None = None,
    stakeholders: list[dict] | None = None,
    precomputed_confidence=None,
    require_feature_flag: bool = True,
) -> OrchestratorResult:
    """Return the first matching lifecycle route for one Decision.

    Stage 6 reuses ``precomputed_confidence`` when supplied. Without it, the
    fallback explicitly passes ``conflicts=[]`` to Stage 2, keeping this module
    deterministic and preventing Stage 6 from triggering AI conflict checks.
    """
    if require_feature_flag and not _feature_enabled():
        return _disabled_result(decision)

    event_records = list(events or [])
    stakeholder_records = list(stakeholders or [])
    fields = _fields(decision)
    decision_id = decision.get("id", "")
    title = str(fields.get(DF.TITLE, ""))
    status = fields.get(DF.STATUS, "")
    readiness = fields.get(DF.READINESS, "")

    if status in (DecisionStatus.DECIDED_YES, DecisionStatus.DECIDED_NO):
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_DECIDED,
            current_state=(
                "הוחלט — כן"
                if status == DecisionStatus.DECIDED_YES
                else "הוחלט — לא"
            ),
            next_step=NextStep(
                action=(
                    "העבר לביצוע"
                    if status == DecisionStatus.DECIDED_YES
                    else "ארכב החלטה"
                ),
                responsible=OWNER_LABEL,
            ),
            after_resolution="סגירת תהליך ההחלטה.",
        )

    if status == DecisionStatus.CANCELLED:
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_CLOSED,
            current_state="בוטל",
            next_step=NextStep("ארכב", SYSTEM_LABEL),
        )

    confidence_score, missing_evidence = _confidence_snapshot(
        event_records,
        fields.get(DF.DOMAIN, Domain.GENERAL),
        precomputed_confidence,
    )
    attention_reasons = _attention_reasons(decision, event_records)
    owner = _find_stakeholder(stakeholder_records, StakeholderRole.DECIDER)
    pending_stakeholders = _pending_stakeholders(stakeholder_records)

    # Routing is intentionally ordered. First match wins.
    if _is_not_ready(readiness):
        blockers = missing_evidence or ("חסר מידע — סוג לא ידוע",)
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_BLOCKED,
            current_state="לא מוכן להחלטה",
            next_step=NextStep(
                action=_missing_action(missing_evidence),
                responsible=_owner_or(owner, TEAM_LABEL),
                detail=", ".join(missing_evidence),
            ),
            blockers=blockers,
            confidence_score=confidence_score,
            missing_evidence=missing_evidence,
            after_resolution="ההחלטה תעבור ל-REVIEW לאישור הבעלים.",
        )

    if pending_stakeholders:
        names = tuple(_stakeholder_name(item) for item in pending_stakeholders)
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_BLOCKED,
            current_state="ממתין לעמדות בעלי עניין",
            next_step=NextStep(
                action="קבל עמדת הצדדים הפתוחים",
                responsible=_owner_or(owner, MANAGER_LABEL),
                detail=", ".join(names),
            ),
            blockers=tuple(f"עמדה לא ידועה: {name}" for name in names),
            confidence_score=confidence_score,
            missing_evidence=missing_evidence,
            after_resolution="לאחר קבלת העמדות תבוצע הערכה מחדש.",
        )

    # With no evidence there is nothing to review yet; remain COLLECTING.
    if confidence_score < CONFIDENCE_REVIEW_THRESHOLD and event_records:
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_REVIEW,
            current_state=(
                f"Confidence נמוך ({int(confidence_score * 100)}%) — נדרשת בדיקה"
            ),
            next_step=NextStep(
                action="סקור את הראיות הקיימות והחלט אם להמשיך",
                responsible=_owner_or(owner, OWNER_LABEL),
                detail=_confidence_detail(confidence_score, missing_evidence),
            ),
            blockers=_confidence_blockers(
                confidence_score,
                missing_evidence,
                attention_reasons,
            ),
            awaiting_owner=True,
            confidence_score=confidence_score,
            missing_evidence=missing_evidence,
            after_resolution="לאחר האישור ניתן יהיה להתקדם להחלטה הסופית.",
        )

    if _is_review(readiness):
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_REVIEW,
            current_state="ממתין לאישור מוכנות",
            next_step=NextStep(
                action="אשר שהמידע מספיק לקבלת החלטה",
                responsible=_owner_or(owner, OWNER_LABEL),
                detail=f"Confidence: {int(confidence_score * 100)}%",
            ),
            blockers=attention_reasons,
            awaiting_owner=True,
            confidence_score=confidence_score,
            missing_evidence=missing_evidence,
            after_resolution="לאחר אישור המוכנות תתבקש החלטה סופית.",
        )

    if (
        confidence_score >= CONFIDENCE_DECIDE_THRESHOLD
        or _is_ready(readiness)
    ):
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_AWAITING,
            current_state=(
                f"מוכן להחלטה (Confidence {int(confidence_score * 100)}%)"
            ),
            next_step=NextStep(
                action="קבל את ההחלטה הסופית",
                responsible=_owner_or(owner, OWNER_LABEL),
                detail=_decision_detail(fields),
            ),
            awaiting_owner=True,
            confidence_score=confidence_score,
            missing_evidence=missing_evidence,
            after_resolution="לאחר ההחלטה הסטטוס יעבור ל-DECIDED.",
        )

    return OrchestratorResult(
        decision_id=decision_id,
        title=title,
        phase=PHASE_COLLECTING,
        current_state="בתהליך איסוף מידע",
        next_step=NextStep(
            action="הוסף ראיות ועדכן אירועים",
            responsible=_owner_or(owner, TEAM_LABEL),
            detail=_missing_action(missing_evidence) if missing_evidence else "",
        ),
        blockers=attention_reasons[:3],
        confidence_score=confidence_score,
        missing_evidence=missing_evidence,
        after_resolution="עם מספיק ראיות ההחלטה תעבור ל-REVIEW.",
    )


def format_orchestrator_card(result: OrchestratorResult) -> str:
    """Render a Telegram-ready Markdown block."""
    lines = [
        "────────────────────",
        f"🔄 *מצב תהליך:* {result.current_state}",
        "",
        f"➡️ *צעד הבא:* {result.next_step.action}",
        f"👤 *אחראי:* {result.next_step.responsible}",
    ]

    if result.next_step.detail:
        lines.append(f"📎 {result.next_step.detail}")
    if result.blockers:
        lines.extend(("", "⛔ *חסמים:*"))
        lines.extend(f"  • {blocker}" for blocker in result.blockers)
    if result.missing_evidence:
        lines.extend(("", "📋 *ראיות חסרות:*"))
        lines.extend(f"  • {item}" for item in result.missing_evidence)
    if result.confidence_score > 0:
        lines.extend(
            (
                "",
                f"📊 *Confidence:* {_confidence_bar(result.confidence_score)} "
                f"{int(result.confidence_score * 100)}%",
            )
        )
    if result.awaiting_owner:
        lines.extend(("", "⏳ _ממתין לאישור בעלים_"))
    if result.after_resolution:
        lines.extend(("", f"💡 _לאחר הפתרון: {result.after_resolution}_"))

    return "\n".join(lines)


def append_orchestrator_to_card(
    decision: dict,
    events: list[dict],
    stakeholders: list[dict],
    precomputed_confidence=None,
) -> str:
    """Return an appendable block; fail open so the base card still renders."""
    try:
        result = orchestrate(
            decision,
            events,
            stakeholders,
            precomputed_confidence=precomputed_confidence,
        )
        return "\n" + format_orchestrator_card(result)
    except Exception as exc:
        logger.warning("[Orchestrator] card append failed: %s", exc)
        return ""


def _confidence_snapshot(
    events: list[dict],
    domain: str,
    precomputed_confidence,
) -> tuple[float, tuple[str, ...]]:
    if precomputed_confidence is not None:
        result = precomputed_confidence
    else:
        from decision_confidence import calc_confidence

        result = calc_confidence(events, conflicts=[], domain=domain)
    return float(result.score), tuple(result.missing or ())


def _attention_reasons(decision: dict, events: list[dict]) -> tuple[str, ...]:
    try:
        from decision_attention import calc_priority

        result = calc_priority(decision, events, require_feature_flag=False)
        return tuple(result.reasons)
    except Exception as exc:
        logger.warning("[Orchestrator] attention unavailable: %s", exc)
        return ()


def _feature_enabled() -> bool:
    try:
        from feature_flags import is_enabled

        return bool(is_enabled(FEATURE_FLAG))
    except Exception:
        return False


def _fields(record: dict) -> dict:
    return record.get("fields", record)


def _is_not_ready(value: str) -> bool:
    return value in {Readiness.NOT_READY, "Not Ready", "NotReady"}


def _is_review(value: str) -> bool:
    return value in {Readiness.REVIEW, "Review", "Needs Review", "NeedsReview"}


def _is_ready(value: str) -> bool:
    return value in {Readiness.READY, "Ready"}


def _find_stakeholder(stakeholders: list[dict], role: str) -> dict | None:
    return next(
        (
            stakeholder
            for stakeholder in stakeholders
            if _fields(stakeholder).get(SF.ROLE) == role
        ),
        None,
    )


def _pending_stakeholders(stakeholders: list[dict]) -> list[dict]:
    pending_values = {
        StakeholderPosition.PENDING,
        StakeholderPosition.UNKNOWN,
        "PENDING",
        "Pending",
        "",
        None,
    }
    return [
        stakeholder
        for stakeholder in stakeholders
        if _fields(stakeholder).get(SF.POSITION) in pending_values
        and _fields(stakeholder).get(SF.ROLE) != StakeholderRole.DECIDER
    ]


def _stakeholder_name(stakeholder: dict) -> str:
    fields = _fields(stakeholder)
    contact = fields.get(SF.CONTACT)
    if isinstance(contact, list) and contact:
        return str(contact[0])
    return str(fields.get(SF.POSITION_DETAILS) or "לא ידוע")


def _owner_or(owner: dict | None, fallback: str) -> str:
    return _stakeholder_name(owner) if owner else fallback


def _missing_action(missing: tuple[str, ...]) -> str:
    return f"השג {missing[0]}" if missing else "השלם את איסוף המידע"


def _confidence_detail(score: float, missing: tuple[str, ...]) -> str:
    parts = [f"Confidence נוכחי: {int(score * 100)}%"]
    if missing:
        parts.append(f"חסר: {', '.join(missing[:2])}")
    return " | ".join(parts)


def _confidence_blockers(
    score: float,
    missing: tuple[str, ...],
    attention: tuple[str, ...],
) -> tuple[str, ...]:
    blockers = [
        f"Confidence {int(score * 100)}% — מתחת לסף "
        f"({int(CONFIDENCE_REVIEW_THRESHOLD * 100)}%)"
    ]
    blockers.extend(missing[:2])
    blockers.extend(reason for reason in attention[:2] if reason not in blockers)
    return tuple(blockers)


def _decision_detail(fields: dict) -> str:
    details = []
    exposure = fields.get(DF.ESTIMATED_EXPOSURE)
    if exposure:
        rendered = (
            f"{exposure:,.0f}₪"
            if isinstance(exposure, (int, float))
            else str(exposure)
        )
        details.append(f"חשיפה: {rendered}")
    urgency = fields.get(DF.URGENCY)
    if urgency:
        details.append(f"דחיפות: {urgency}")
    return " | ".join(details)


def _confidence_bar(score: float) -> str:
    filled = max(0, min(10, round(score * 10)))
    return "█" * filled + "░" * (10 - filled)


def _disabled_result(decision: dict) -> OrchestratorResult:
    fields = _fields(decision)
    return OrchestratorResult(
        decision_id=decision.get("id", ""),
        title=str(fields.get(DF.TITLE, "")),
        phase=PHASE_COLLECTING,
        current_state="Orchestrator לא פעיל",
        next_step=NextStep("הפעל FEATURE_DECISION_HUB", SYSTEM_LABEL),
    )
