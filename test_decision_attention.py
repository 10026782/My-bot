#!/usr/bin/env python3
# test_decision_attention.py -- Regression tests for Decision Hub Stage 4.
#
# Run: python3 test_decision_attention.py

from __future__ import annotations

import sys
from datetime import datetime, timezone

from airtable_schema import DecisionEventFields, DecisionFields, DecisionStatus
from decision_attention import (
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_NONE,
    build_attention_summary,
    calc_priority,
    detect_attention,
)
from decision_attention_policy import AttentionPolicy

NOW = datetime(2026, 6, 26, tzinfo=timezone.utc)

_passed = 0
_failed = 0


def check(desc: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        print(f"OK {desc}")
        _passed += 1
    else:
        print(f"FAIL {desc}")
        _failed += 1


def decision(record_id: str = "recD", title: str = "Blue View", **fields) -> dict:
    base = {
        DecisionFields.TITLE: title,
        DecisionFields.STATUS: DecisionStatus.OPEN,
        DecisionFields.CREATED: "2026-06-01",
        DecisionFields.LAST_UPDATED: "2026-06-20",
    }
    base.update(fields)
    return {"id": record_id, "fields": base}


def event(date: str = "2026-06-24", delta: str = "", tags=None) -> dict:
    fields = {
        DecisionEventFields.EVENT_DATE: date,
        DecisionEventFields.DELTA_TYPE: delta,
    }
    if tags is not None:
        fields[DecisionEventFields.TAGS] = tags
    return {"id": f"evt-{date}-{delta}", "fields": fields}


close_deadline = calc_priority(decision(Deadline="2026-06-28"), now=NOW, require_feature_flag=False)
check("deadline close raises high priority", close_deadline.priority == PRIORITY_HIGH)

far_deadline = calc_priority(
    decision(Deadline="2026-07-20", **{DecisionFields.LAST_UPDATED: "2026-06-25"}),
    now=NOW,
    require_feature_flag=False,
)
check("deadline far does not create attention", far_deadline.priority == PRIORITY_NONE)

pressure_events = [event(delta="Pressure") for _ in range(4)]
pressure_only = calc_priority(
    decision(**{DecisionFields.LAST_UPDATED: "2026-06-25"}),
    pressure_events,
    now=NOW,
    require_feature_flag=False,
)
check("pressure alone does not create priority", pressure_only.priority == PRIORITY_NONE)

old_review = calc_priority(
    decision(**{DecisionFields.READINESS: "REVIEW", DecisionFields.LAST_UPDATED: "2026-06-20"}),
    now=NOW,
    require_feature_flag=False,
)
check("old REVIEW creates attention", old_review.priority in {PRIORITY_MEDIUM, PRIORITY_HIGH})

old_not_ready = calc_priority(
    decision(**{DecisionFields.READINESS: "NOT_READY", DecisionFields.LAST_UPDATED: "2026-06-20"}),
    now=NOW,
    require_feature_flag=False,
)
check("old NOT_READY creates attention", old_not_ready.priority in {PRIORITY_MEDIUM, PRIORITY_HIGH})

closed = calc_priority(
    decision(Deadline="2026-06-27", **{DecisionFields.STATUS: DecisionStatus.DECIDED_YES}),
    now=NOW,
    require_feature_flag=False,
)
check("closed decision is excluded", closed.priority == PRIORITY_NONE)

ordered = detect_attention(
    [
        decision("recLow", "Review", **{DecisionFields.READINESS: "REVIEW"}),
        decision("recHigh", "Urgent", Deadline="2026-06-27", **{DecisionFields.READINESS: "NOT_READY"}),
    ],
    now=NOW,
    require_feature_flag=False,
)
check("priority ordering puts highest score first", ordered[0]["decision_id"] == "recHigh")

check("empty list returns empty attention list", detect_attention([], now=NOW, require_feature_flag=False) == [])

summary = build_attention_summary(close_deadline)
check("summary includes title and priority", "Blue View" in summary and "Priority:" in summary)

custom_policy = AttentionPolicy(deadline_urgent_days=1, deadline_soon_days=1)
custom_deadline = calc_priority(
    decision(Deadline="2026-06-28"),
    now=NOW,
    require_feature_flag=False,
    policy=custom_policy,
)
check("custom policy can tune deadline urgency", custom_deadline.priority == PRIORITY_NONE)

future_inputs = calc_priority(
    decision(**{DecisionFields.READINESS: "REVIEW", DecisionFields.LAST_UPDATED: "2026-06-20"}),
    now=NOW,
    require_feature_flag=False,
    confidence_score=0.42,
    evidence=[{"source": "future"}],
)
check("future confidence/evidence inputs are accepted", future_inputs.priority in {PRIORITY_MEDIUM, PRIORITY_HIGH})

print(f"Decision Attention: {_passed}/{_passed + _failed} passed")
sys.exit(1 if _failed else 0)
