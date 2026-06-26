#!/usr/bin/env python3
# decision_attention.py -- Decision Hub Stage 4 attention scoring.
#
# Deterministic, read-only logic. This module does not write records, mutate
# pipeline state, or execute actions.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from airtable_schema import (
    DecisionEventFields,
    DecisionFields,
)
from decision_attention_policy import (
    DEFAULT_ATTENTION_POLICY,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_NONE,
    AttentionPolicy,
)

FEATURE_FLAG = "FEATURE_DECISION_HUB"


@dataclass(frozen=True)
class AttentionItem:
    decision_id: str
    title: str
    priority: str
    score: int
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "title": self.title,
            "priority": self.priority,
            "score": self.score,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AttentionSignals:
    fields: dict
    events: tuple[dict, ...]
    now: datetime
    readiness: str
    age_days: int | None
    deadline: datetime | None
    pressure_count: int
    position_shift_count: int
    has_real_change: bool
    inactive_days: int | None
    has_missing_info: bool
    confidence_score: float | None = None
    evidence: tuple[dict, ...] = ()


def detect_attention(
    decisions: Iterable[dict],
    events_by_decision: dict[str, list[dict]] | None = None,
    now: datetime | None = None,
    require_feature_flag: bool = True,
    policy: AttentionPolicy = DEFAULT_ATTENTION_POLICY,
) -> list[dict]:
    """Return attention items for open decisions, highest priority first."""
    if require_feature_flag and not _feature_enabled():
        return []

    now = _as_aware(now or datetime.now(timezone.utc))
    events_by_decision = events_by_decision or {}
    items: list[AttentionItem] = []

    for decision in decisions:
        decision_id = decision.get("id", "")
        item = calc_priority(
            decision,
            events_by_decision.get(decision_id, []),
            now=now,
            require_feature_flag=False,
            policy=policy,
        )
        if item.priority != PRIORITY_NONE:
            items.append(item)

    items.sort(key=lambda item: (-item.score, item.title.lower(), item.decision_id))
    return [item.as_dict() for item in items]


def calc_priority(
    decision: dict,
    events: Iterable[dict] | None = None,
    now: datetime | None = None,
    require_feature_flag: bool = True,
    policy: AttentionPolicy = DEFAULT_ATTENTION_POLICY,
    confidence_score: float | None = None,
    evidence: Iterable[dict] | None = None,
) -> AttentionItem:
    """Calculate deterministic attention priority for one decision."""
    if require_feature_flag and not _feature_enabled():
        return _none_item(decision)

    fields = _fields(decision)
    if fields.get(DecisionFields.STATUS) in policy.closed_statuses:
        return _none_item(decision)

    signals = _build_signals(
        decision,
        events or [],
        now=now,
        policy=policy,
        confidence_score=confidence_score,
        evidence=evidence or [],
    )
    reasons: list[str] = []
    score = 0

    if (
        signals.readiness in policy.not_ready_values
        and signals.age_days is not None
        and signals.age_days >= policy.not_ready_days
    ):
        score += policy.score_not_ready_old
        reasons.append(f"Readiness = NOT_READY for {signals.age_days} days")
    elif (
        signals.readiness in policy.review_values
        and signals.age_days is not None
        and signals.age_days >= policy.review_days
    ):
        score += policy.score_review_old
        reasons.append(f"Readiness = REVIEW for {signals.age_days} days")

    if signals.deadline:
        days_left = _days_between(signals.now, signals.deadline)
        if days_left < 0:
            score += policy.score_deadline_overdue
            reasons.append(f"Deadline overdue by {abs(days_left)} days")
        elif days_left <= policy.deadline_urgent_days:
            score += policy.score_deadline_urgent
            reasons.append(f"Deadline in {days_left} days")
        elif days_left <= policy.deadline_soon_days:
            score += policy.score_deadline_soon
            reasons.append(f"Deadline in {days_left} days")

    if signals.pressure_count >= policy.pressure_repeat_count and signals.has_real_change:
        score += policy.score_repeated_pressure_with_change
        reasons.append(f"{signals.pressure_count} pressure messages")

    if signals.position_shift_count >= policy.position_shift_count:
        score += policy.score_position_shifts
        reasons.append(f"{signals.position_shift_count} position changes")

    if signals.inactive_days is not None and signals.inactive_days >= policy.inactive_days:
        score += policy.score_inactive
        reasons.append(f"No activity for {signals.inactive_days} days")

    if signals.has_missing_info:
        score += policy.score_missing_info
        reasons.append("Missing information remains")

    if not reasons:
        return _none_item(decision)

    if score >= policy.high_priority_score:
        priority = PRIORITY_HIGH
    elif score >= policy.medium_priority_score:
        priority = PRIORITY_MEDIUM
    else:
        priority = PRIORITY_LOW

    return AttentionItem(
        decision_id=decision.get("id", ""),
        title=fields.get(DecisionFields.TITLE, ""),
        priority=priority,
        score=score,
        reasons=tuple(reasons),
    )


def build_attention_summary(item: AttentionItem | dict) -> str:
    """Render a compact human-readable attention block."""
    if isinstance(item, AttentionItem):
        item = item.as_dict()
    if not item or item.get("priority") == PRIORITY_NONE:
        return ""

    reasons = item.get("reasons") or []
    reason_lines = "\n".join(f"- {reason}" for reason in reasons) or "- Attention required"
    return (
        "Decision:\n"
        f"{item.get('title', '')}\n\n"
        "Priority:\n"
        f"{item.get('priority', '')}\n\n"
        "Reason:\n"
        f"{reason_lines}"
    )


def _feature_enabled() -> bool:
    try:
        from feature_flags import is_enabled

        return bool(is_enabled(FEATURE_FLAG))
    except Exception:
        return False


def _none_item(decision: dict) -> AttentionItem:
    fields = _fields(decision)
    return AttentionItem(
        decision_id=decision.get("id", ""),
        title=fields.get(DecisionFields.TITLE, ""),
        priority=PRIORITY_NONE,
        score=0,
        reasons=(),
    )


def _fields(record: dict) -> dict:
    return record.get("fields", record)


def _build_signals(
    decision: dict,
    events: Iterable[dict],
    now: datetime | None,
    policy: AttentionPolicy,
    confidence_score: float | None = None,
    evidence: Iterable[dict] | None = None,
) -> AttentionSignals:
    fields = _fields(decision)
    now = _as_aware(now or datetime.now(timezone.utc))
    event_list = tuple(events or ())
    pressure_count = _count_pressure(event_list, policy)
    position_shift_count = _count_position_shifts(event_list, policy)
    has_real_change = position_shift_count > 0 or _has_non_pressure_event(event_list, policy)

    return AttentionSignals(
        fields=fields,
        events=event_list,
        now=now,
        readiness=fields.get(DecisionFields.READINESS, ""),
        age_days=_decision_age_days(fields, now),
        deadline=_deadline(fields, policy),
        pressure_count=pressure_count,
        position_shift_count=position_shift_count,
        has_real_change=has_real_change,
        inactive_days=_inactive_days(fields, list(event_list), now),
        has_missing_info=bool(str(fields.get(DecisionFields.MISSING_INFO, "")).strip()),
        confidence_score=confidence_score,
        evidence=tuple(evidence or ()),
    )


def _decision_age_days(fields: dict, now: datetime) -> int | None:
    start = _first_datetime(
        fields.get(DecisionFields.LAST_UPDATED),
        fields.get(DecisionFields.CREATED),
    )
    if not start:
        return None
    return max(0, _days_between(start, now))


def _inactive_days(fields: dict, events: list[dict], now: datetime) -> int | None:
    latest = _latest_event_date(events) or _first_datetime(
        fields.get(DecisionFields.LAST_UPDATED),
        fields.get(DecisionFields.CREATED),
    )
    if not latest:
        return None
    return max(0, _days_between(latest, now))


def _deadline(fields: dict, policy: AttentionPolicy) -> datetime | None:
    return _first_datetime(*(fields.get(name) for name in policy.deadline_fields))


def _latest_event_date(events: list[dict]) -> datetime | None:
    dates = [
        parsed
        for parsed in (_parse_datetime(_fields(event).get(DecisionEventFields.EVENT_DATE)) for event in events)
        if parsed
    ]
    if not dates:
        return None
    return max(dates)


def _first_datetime(*values) -> datetime | None:
    for value in values:
        parsed = _parse_datetime(value)
        if parsed:
            return parsed
    return None


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return _as_aware(value)
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    for fmt in (None, "%Y-%m-%d"):
        try:
            parsed = datetime.fromisoformat(normalized) if fmt is None else datetime.strptime(normalized, fmt)
            return _as_aware(parsed)
        except ValueError:
            continue
    return None


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _days_between(start: datetime, end: datetime) -> int:
    return (end.date() - start.date()).days


def _count_pressure(events: Iterable[dict], policy: AttentionPolicy) -> int:
    return sum(1 for event in events if _event_has_any(event, policy.pressure_values))


def _count_position_shifts(events: Iterable[dict], policy: AttentionPolicy) -> int:
    return sum(1 for event in events if _event_has_any(event, policy.position_shift_values))


def _has_non_pressure_event(events: Iterable[dict], policy: AttentionPolicy) -> bool:
    for event in events:
        fields = _fields(event)
        delta_type = fields.get(DecisionEventFields.DELTA_TYPE)
        tags = fields.get(DecisionEventFields.TAGS) or []
        if delta_type and delta_type not in policy.pressure_values:
            return True
        if isinstance(tags, str):
            tags = [tags]
        if any(tag not in policy.pressure_values for tag in tags):
            return True
    return False


def _event_has_any(event: dict, values: frozenset[str]) -> bool:
    fields = _fields(event)
    delta_type = fields.get(DecisionEventFields.DELTA_TYPE)
    tags = fields.get(DecisionEventFields.TAGS) or []
    if isinstance(tags, str):
        tags = [tags]
    return delta_type in values or any(tag in values for tag in tags)
