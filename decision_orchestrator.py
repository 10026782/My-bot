# decision_orchestrator.py — Decision Hub Stage 6: Lifecycle Orchestrator
#
# Pull-only. Called from /decision status and explicit refresh. This module
# never sends messages, creates tasks, executes actions, or mutates canonical
# Decision state. It only describes the current lifecycle phase and next step.

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from airtable_schema import (
    DecisionDomain as DOMAIN,
    DecisionFields as DF,
    DecisionReadiness as DR,
    DecisionStakeholderFields as SF,
    DecisionStakeholderPosition as SP,
    DecisionStakeholderRole as SR,
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

OWNER_LABEL = "בעל ההחלטה"
MANAGER_LABEL = "מנהל"
TEAM_LABEL = "הצוות"
SYSTEM_LABEL = "המערכת"

CONFIDENCE_READY_THRESHOLD = 0.60
CONFIDENCE_DECIDE_THRESHOLD = 0.75


@dataclass(frozen=True)
class NextStep:
    """One actionable step in the decision lifecycle."""

    action: str
    responsible: str
    detail: str = ""


@dataclass
class OrchestratorResult:
    """A read-only lifecycle snapshot for one Decision."""

    decision_id: str
    title: str
    phase: str
    current_state: str
    next_step: NextStep
    blockers: list[str] = field(default_factory=list)
    awaiting_owner: bool = False
    confidence_score: float = 0.0
    missing_evidence: list[str] = field(default_factory=list)
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
            "blockers": self.blockers,
            "awaiting_owner": self.awaiting_owner,
            "confidence_score": self.confidence_score,
            "missing_evidence": self.missing_evidence,
            "after_resolution": self.after_resolution,
        }


def orchestrate(
    decision: dict,
    events: list[dict] | None = None,
    stakeholders: list[dict] | None = None,
    precomputed_confidence=None,
    require_feature_flag: bool = True,
) -> OrchestratorResult:
    """Return the first matching lifecycle route for a Decision.

    A supplied ``precomputed_confidence`` is reused as-is. Otherwise confidence
    is calculated deterministically with ``conflicts=[]`` so this stage never
    triggers AI conflict detection by itself.
    """
    if require_feature_flag and not _feature_enabled():
        return _disabled_result(decision)

    events = events or []
    stakeholders = stakeholders or []
    fields = _fields(decision)
    decision_id = decision.get("id", "")
    title = fields.get(DF.TITLE, "")
    status = fields.get(DF.STATUS, "")
    readiness = fields.get(DF.READINESS, "")
    domain = fields.get(DF.DOMAIN, DOMAIN.GENERAL)

    if status in (DecisionStatus.DECIDED_YES, DecisionStatus.DECIDED_NO):
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_DECIDED,
            current_state=_decided_label(status),
            next_step=NextStep(
                "העבר לביצוע" if status == DecisionStatus.DECIDED_YES else "ארכב החלטה",
                OWNER_LABEL,
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

    score, missing = _resolve_confidence(events, domain, precomputed_confidence)
    attention_reasons = _resolve_attention(decision, events)
    owner = _find_stakeholder(stakeholders, SR.DECIDER)
    pending_stakeholders = _pending_stakeholders(stakeholders)

    # Routing is intentionally top-to-bottom: first match wins.
    if _is_not_ready(readiness):
        blockers = missing or ["חסר מידע — סוג לא ידוע"]
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_BLOCKED,
            current_state="לא מוכן להחלטה",
            next_step=NextStep(
                action=_missing_action(missing),
                responsible=_owner_or(owner, TEAM_LABEL),
                detail=", ".join(missing),
            ),
            blockers=blockers,
            confidence_score=score,
            missing_evidence=missing,
            after_resolution="המערכת תסמן את ההחלטה כ-REVIEW לאישור הבעלים.",
        )

    if pending_stakeholders:
        names = [_stakeholder_name(stakeholder) for stakeholder in pending_stakeholders]
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
            blockers=[f"עמדה לא ידועה: {name}" for name in names],
            confidence_score=score,
            missing_evidence=missing,
            after_resolution="לאחר קבלת כל העמדות המערכת תעריך מחדש.",
        )

    # No events is still COLLECTING rather than REVIEW: there is nothing to
    # review yet. Once evidence exists, low confidence requires owner review.
    if score < CONFIDENCE_READY_THRESHOLD and events:
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_REVIEW,
            current_state=f"Confidence נמוך ({int(score * 100)}%) — נדרשת בדיקה",
            next_step=NextStep(
                action="סקור את הראיות הקיימות והחלט אם להמשיך",
                responsible=_owner_or(owner, OWNER_LABEL),
                detail=_confidence_detail(score, missing),
            ),
            blockers=_confidence_blockers(score, missing, attention_reasons),
            awaiting_owner=True,
            confidence_score=score,
            missing_evidence=missing,
            after_resolution="לאחר האישור תוכל לקבל את ההחלטה הסופית.",
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
                detail=f"Confidence: {int(score * 100)}%",
            ),
            blockers=[reason for reason in attention_reasons if reason],
            awaiting_owner=True,
            confidence_score=score,
            missing_evidence=missing,
            after_resolution="לאחר אישור המוכנות המערכת תמתין להחלטה הסופית.",
        )

    if score >= CONFIDENCE_DECIDE_THRESHOLD or _is_ready(readiness):
        return OrchestratorResult(
            decision_id=decision_id,
            title=title,
            phase=PHASE_AWAITING,
            current_state=f"מוכן להחלטה (Confidence {int(score * 100)}%)",
            next_step=NextStep(
                action="קבל את ההחלטה הסופית",
                responsible=_owner_or(owner, OWNER_LABEL),
                detail=_decision_detail(fields),
            ),
            awaiting_owner=True,
            confidence_score=score,
            missing_evidence=missing,
            after_resolution="לאחר ההחלטה המערכת תסמן DECIDED ותעביר לביצוע.",
        )

    return OrchestratorResult(
        decision_id=decision_id,
        title=title,
        phase=PHASE_COLLECTING,
        current_state="בתהליך איסוף מידע",
        next_step=NextStep(
            action="הוסף ראיות ועדכן אירועים",
            responsible=_owner_or(owner, TEAM_LABEL),
            detail=_missing_action(missing) if missing else "",
        ),
        blockers=attention_reasons[:3],
        confidence_score=score,
        missing_evidence=missing,
        after_resolution="לאחר הגעה ל-Confidence מספיק המערכת תעלה לשלב REVIEW.",
    )


def format_orchestrator_card(result: OrchestratorResult) -> str:
    """Render an OrchestratorResult as Telegram-ready Markdown."""
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
        lines.extend(["", "⛔ *חסמים:*"])
        lines.extend(f"  • {blocker}" for blocker in result.blockers)

    if result.missing_evidence:
        lines.extend(["", "📋 *ראיות חסרות:*"])
        lines.extend(f"  • {item}" for item in result.missing_evidence)

    if result.confidence_score > 0:
        lines.extend([
            "",
            f"📊 *Confidence:* {_confidence_bar(result.confidence_score)} "
            f"{int(result.confidence_score * 100)}%",
        ])

    if result.awaiting_owner:
        lines.extend(["", "⏳ _ממתין לאישור בעלים_"])

    if result.after_resolution:
        lines.extend(["", f"💡 _לאחר הפתרון: {result.after_resolution}_"])

    return "\n".join(lines)


def append_orchestrator_to_card(
    decision: dict,
    events: list[dict],
    stakeholders: list[dict],
    precomputed_confidence=None,
) -> str:
    """Return an appendable card block, or an empty string on any failure."""
    try:
        result = orchestrate(
            decision,
            events,
            stakeholders,
            precomputed_confidence=precomputed_confidence,
        )
        return "\n" + format_orchestrator_card(result)
    except Exception as exc:
        logger.warning("[Orchestrator] append_orchestrator_to_card failed: %s", exc)
        return ""


def _resolve_confidence(events: list[dict], domain: str, precomputed_confidence) -> tuple[float, list[str]]:
    try:
        if precomputed_confidence is None:
            from decision_confidence import calc_confidence

            confidence_result = calc_confidence(events, conflicts=[], domain=domain)
        else:
            confidence_result = precomputed_confidence
        return float(confidence_result.score), list(confidence_result.missing)
    except Exception as exc:
        logger.warning("[Orchestrator] confidence resolution failed: %s", exc)
        return 0.0, []


def _resolve_attention(decision: dict, events: list[dict]) -> list[str]:
    try:
        from decision_attention import calc_priority

        attention = calc_priority(decision, events, require_feature_flag=False)
        return list(attention.reasons)
    except Exception as exc:
        logger.warning("[Orchestrator] calc_priority failed: %s", exc)
        return []


def _feature_enabled() -> bool:
    try:
        from feature_flags import is_enabled

        return bool(is_enabled(FEATURE_FLAG))
    except Exception:
        return False


def _fields(record: dict) -> dict:
    return record.get("fields", record)


def _is_not_ready(readiness: str) -> bool:
    return readiness in {DR.NOT_READY, "Not Ready", "NotReady"}


def _is_review(readiness: str) -> bool:
    return readiness in {DR.REVIEW, "Review", "Needs Review", "NeedsReview"}


def _is_ready(readiness: str) -> bool:
    return readiness in {DR.READY, "Ready"}


def _decided_label(status: str) -> str:
    return "הוחלט — כן" if status == DecisionStatus.DECIDED_YES else "הוחלט — לא"


def _find_stakeholder(stakeholders: list[dict], role: str) -> dict | None:
    return next((stakeholder for stakeholder in stakeholders if _fields(stakeholder).get(SF.ROLE) == role), None)


def _pending_stakeholders(stakeholders: list[dict]) -> list[dict]:
    pending_values = {SP.PENDING, SP.UNKNOWN, "PENDING", "Pending", "", None}
    return [
        stakeholder
        for stakeholder in stakeholders
        if _fields(stakeholder).get(SF.POSITION) in pending_values
        and _fields(stakeholder).get(SF.ROLE) != SR.DECIDER
    ]


def _stakeholder_name(stakeholder: dict) -> str:
    fields = _fields(stakeholder)
    contact = fields.get(SF.CONTACT)
    if isinstance(contact, list) and contact:
        return str(contact[0])
    return fields.get(SF.POSITION_DETAILS) or "לא ידוע"


def _owner_or(owner: dict | None, fallback: str) -> str:
    return _stakeholder_name(owner) if owner else fallback


def _missing_action(missing: list[str]) -> str:
    return f"השג {missing[0]}" if missing else "השלם את איסוף המידע"


def _confidence_detail(score: float, missing: list[str]) -> str:
    parts = [f"Confidence נוכחי: {int(score * 100)}%"]
    if missing:
        parts.append(f"חסר: {', '.join(missing[:2])}")
    return " | ".join(parts)


def _confidence_blockers(score: float, missing: list[str], attention: list[str]) -> list[str]:
    blockers = [
        f"Confidence {int(score * 100)}% — מתחת לסף "
        f"({int(CONFIDENCE_READY_THRESHOLD * 100)}%)"
    ]
    blockers.extend(missing[:2])
    blockers.extend(reason for reason in attention[:2] if reason not in blockers)
    return blockers


def _decision_detail(fields: dict) -> str:
    parts = []
    exposure = fields.get(DF.ESTIMATED_EXPOSURE)
    if exposure:
        rendered = f"{exposure:,.0f}₪" if isinstance(exposure, (int, float)) else str(exposure)
        parts.append(f"חשיפה: {rendered}")
    urgency = fields.get(DF.URGENCY)
    if urgency:
        parts.append(f"דחיפות: {urgency}")
    return " | ".join(parts)


def _confidence_bar(score: float) -> str:
    filled = max(0, min(10, round(score * 10)))
    return "█" * filled + "░" * (10 - filled)


def _disabled_result(decision: dict) -> OrchestratorResult:
    fields = _fields(decision)
    return OrchestratorResult(
        decision_id=decision.get("id", ""),
        title=fields.get(DF.TITLE, ""),
        phase=PHASE_COLLECTING,
        current_state="Orchestrator לא פעיל",
        next_step=NextStep("הפעל FEATURE_DECISION_HUB", SYSTEM_LABEL),
    )
