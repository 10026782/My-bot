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
    DecisionDeltaType,
    DecisionEventFields,
    DecisionEventTag,
    DecisionFields,
    DecisionStatus,
)

FEATURE_FLAG = "FEATURE_DECISION_HUB"

PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"
PRIORITY_NONE = "NONE"

NOT_READY_DAYS = 3
REVIEW_DAYS = 2
DEADLINE_SOON_DAYS = 7
DEADLINE_URGENT_DAYS = 3
INACTIVE_DAYS = 14
PRESSURE_REPEAT_COUNT = 4
POSITION_SHIFT_COUNT = 2

_CLOSED_STATUSES = {
    DecisionStatus.DECIDED_YES,
    DecisionStatus.DECIDED_NO,
    DecisionStatus.CANCELLED,
    "Closed",
    "Done",
}

_NOT_READY_VALUES = {"NOT_READY", "Not Ready", "NotReady"}
_REVIEW_VALUES = {"REVIEW", "Review", "Needs Review", "NeedsReview"}

_PRESSURE_VALUES = {
    DecisionDeltaType.PRESSURE,
    DecisionEventTag.PRESSURE_ONLY,
    "Pressure",
    "pressure",
    "לחץ",
}

_POSITION_SHIFT_VALUES = {
    DecisionDeltaType.POSITION_SHIFT,
    "Position Shift",
    "position_shift",
    "שינוי_עמדה",
}

_DEADLINE_FIELDS = ("Deadline", "Due Date", "Target Date", "deadline", "due_date")


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


def detect_attention(
    decisions: Iterable[dict],
    events_by_decision: dict[str, list[dict]] | None = None,
    now: datetime | None = None,
    require_feature_flag: bool = True,
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
) -> AttentionItem:
    """Calculate deterministic attention priority for one decision."""
    if require_feature_flag and not _feature_enabled():
        return _none_item(decision)

    fields = _fields(decision)
    if fields.get(DecisionFields.STATUS) in _CLOSED_STATUSES:
        return _none_item(decision)

    now = _as_aware(now or datetime.now(timezone.utc))
    events = list(events or [])
    reasons: list[str] = []
    score = 0

    readiness = fields.get(DecisionFields.READINESS, "")
    age_days = _decision_age_days(fields, now)
    if readiness in _NOT_READY_VALUES and age_days is not None and age_days >= NOT_READY_DAYS:
        score += 35
        reasons.append(f"Readiness = NOT_READY for {age_days} days")
    elif readiness in _REVIEW_VALUES and age_days is not None and age_days >= REVIEW_DAYS:
        score += 30
        reasons.append(f"Readiness = REVIEW for {age_days} days")

    deadline = _deadline(fields)
    if deadline:
        days_left = _days_between(now, deadline)
        if days_left < 0:
            score += 45
            reasons.append(f"Deadline overdue by {abs(days_left)} days")
        elif days_left <= DEADLINE_URGENT_DAYS:
            score += 40
            reasons.append(f"Deadline in {days_left} days")
        elif days_left <= DEADLINE_SOON_DAYS:
            score += 20
            reasons.append(f"Deadline in {days_left} days")

    pressure_count = _count_pressure(events)
    position_shift_count = _count_position_shifts(events)
    has_real_change = position_shift_count > 0 or _has_non_pressure_event(events)
    if pressure_count >= PRESSURE_REPEAT_COUNT and has_real_change:
        score += 15
        reasons.append(f"{pressure_count} pressure messages")

    if position_shift_count >= POSITION_SHIFT_COUNT:
        score += 25
        reasons.append(f"{position_shift_count} position changes")

    inactive_days = _inactive_days(fields, events, now)
    if inactive_days is not None and inactive_days >= INACTIVE_DAYS:
        score += 15
        reasons.append(f"No activity for {inactive_days} days")

    if str(fields.get(DecisionFields.MISSING_INFO, "")).strip():
        score += 10
        reasons.append("Missing information remains")

    if not reasons:
        return _none_item(decision)

    if score >= 40:
        priority = PRIORITY_HIGH
    elif score >= 30:
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


def _deadline(fields: dict) -> datetime | None:
    return _first_datetime(*(fields.get(name) for name in _DEADLINE_FIELDS))


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


def _count_pressure(events: list[dict]) -> int:
    return sum(1 for event in events if _event_has_any(event, _PRESSURE_VALUES))


def _count_position_shifts(events: list[dict]) -> int:
    return sum(1 for event in events if _event_has_any(event, _POSITION_SHIFT_VALUES))


def _has_non_pressure_event(events: list[dict]) -> bool:
    for event in events:
        fields = _fields(event)
        delta_type = fields.get(DecisionEventFields.DELTA_TYPE)
        tags = fields.get(DecisionEventFields.TAGS) or []
        if delta_type and delta_type not in _PRESSURE_VALUES:
            return True
        if isinstance(tags, str):
            tags = [tags]
        if any(tag not in _PRESSURE_VALUES for tag in tags):
            return True
    return False


def _event_has_any(event: dict, values: set[str]) -> bool:
    fields = _fields(event)
    delta_type = fields.get(DecisionEventFields.DELTA_TYPE)
    tags = fields.get(DecisionEventFields.TAGS) or []
    if isinstance(tags, str):
        tags = [tags]
    return delta_type in values or any(tag in values for tag in tags)
