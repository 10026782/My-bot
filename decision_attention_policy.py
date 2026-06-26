#!/usr/bin/env python3
# decision_attention_policy.py -- Tunable Decision Hub attention policy.
#
# Keep scoring thresholds and weights here so decision_attention.py can stay
# focused on deterministic signal extraction and priority calculation.

from __future__ import annotations

from dataclasses import dataclass

from airtable_schema import (
    DecisionDeltaType,
    DecisionEventTag,
    DecisionStatus,
)

PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"
PRIORITY_NONE = "NONE"


@dataclass(frozen=True)
class AttentionPolicy:
    not_ready_days: int = 3
    review_days: int = 2
    deadline_soon_days: int = 7
    deadline_urgent_days: int = 3
    inactive_days: int = 14
    pressure_repeat_count: int = 4
    position_shift_count: int = 2

    score_not_ready_old: int = 35
    score_review_old: int = 30
    score_deadline_overdue: int = 45
    score_deadline_urgent: int = 40
    score_deadline_soon: int = 20
    score_repeated_pressure_with_change: int = 15
    score_position_shifts: int = 25
    score_inactive: int = 15
    score_missing_info: int = 10

    high_priority_score: int = 40
    medium_priority_score: int = 30

    closed_statuses: frozenset[str] = frozenset(
        {
            DecisionStatus.DECIDED_YES,
            DecisionStatus.DECIDED_NO,
            DecisionStatus.CANCELLED,
            "Closed",
            "Done",
        }
    )
    not_ready_values: frozenset[str] = frozenset({"NOT_READY", "Not Ready", "NotReady"})
    review_values: frozenset[str] = frozenset({"REVIEW", "Review", "Needs Review", "NeedsReview"})
    pressure_values: frozenset[str] = frozenset(
        {
            DecisionDeltaType.PRESSURE,
            DecisionEventTag.PRESSURE_ONLY,
            "Pressure",
            "pressure",
            "לחץ",
        }
    )
    position_shift_values: frozenset[str] = frozenset(
        {
            DecisionDeltaType.POSITION_SHIFT,
            "Position Shift",
            "position_shift",
            "שינוי_עמדה",
        }
    )
    deadline_fields: tuple[str, ...] = ("Deadline", "Due Date", "Target Date", "deadline", "due_date")


DEFAULT_ATTENTION_POLICY = AttentionPolicy()
