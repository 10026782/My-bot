"""Owner-scoped FCC reads. Every record leaves this module only after
``data_access_policy.filter_records`` — aggregates are computed on the filtered
set, so another person's goals never reach a total, a search or a plan.

Reads go through ``tools.airtable_read_adapter`` (read-only provider adapter);
writes are never done here (see ``writer`` + the ActionGateway path).
"""

from __future__ import annotations

import logging
from datetime import date

from airtable_schema import FinEventFields, FinGoalFields, Tables
from core import data_access_policy as policy
from core.financial_control import calc

logger = logging.getLogger(__name__)

_MAX_ROWS = 500


def _read(table: str, formula: str = "") -> list[dict]:
    from tools.airtable_read_adapter import list_records
    return list_records(table, formula, max_records=_MAX_ROWS, paginate=True)


def _record_fields(table: str, record_id: str) -> dict:
    from tools.airtable_read_adapter import get_record_fields
    return get_record_fields(table, record_id)


def my_goals(identity) -> list[dict]:
    """Active-or-not goals of the caller only. Unresolved identity -> PersonalDataAccessDenied."""
    records = _read(Tables.FIN_GOALS)
    mine = policy.filter_records(Tables.FIN_GOALS, records, identity)
    return sorted(mine, key=lambda r: ((r.get("fields") or {}).get(FinGoalFields.DISPLAY_ORDER) or 9999))


def my_events(identity) -> list[dict]:
    return policy.filter_records(Tables.FIN_EVENTS, _read(Tables.FIN_EVENTS), identity)


def _goal_ids_of(event: dict) -> list[str]:
    value = (event.get("fields") or {}).get(FinEventFields.GOAL)
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def assert_goal_owned(goal_id: str, identity) -> dict:
    """Return the goal's fields iff the caller is its owner-of-record, else raise.
    Used at propose time AND at execution time (cross-owner link guard)."""
    if not isinstance(goal_id, str) or not goal_id.startswith("rec"):
        raise policy.PersonalDataAccessDenied(policy.DENIED_MESSAGE)
    try:
        fields = _record_fields(Tables.FIN_GOALS, goal_id)
    except Exception as exc:
        raise policy.PersonalDataAccessDenied(policy.UNRESOLVED_MESSAGE) from exc
    policy.authorize_record(Tables.FIN_GOALS, fields, identity)
    return fields


def overview(identity, today: date | None = None) -> dict:
    """Private screen payload: goals with derived numbers + monthly cash improvement."""
    today = today or date.today()
    goals = my_goals(identity)
    events = my_events(identity)
    by_goal: dict[str, list[dict]] = {}
    for ev in events:
        for gid in _goal_ids_of(ev):
            by_goal.setdefault(gid, []).append(ev)

    rows, all_events = [], []
    for goal in goals:
        parsed = calc.parse_events(by_goal.get(goal["id"], []), FinEventFields)
        all_events.extend(parsed)
        gf = goal.get("fields") or {}
        if str(gf.get(FinGoalFields.STATUS) or "active").lower() not in ("active", "פעיל"):
            continue
        row = calc.compute_goal(goal, parsed, today, FinGoalFields)
        row["category"] = gf.get(FinGoalFields.CATEGORY)
        row["priority"] = gf.get(FinGoalFields.PRIORITY)
        rows.append(row)

    return {
        "goals": rows,
        "monthly_cash_improvement": calc.monthly_cash_improvement(all_events, today),
        "recent_events": [
            {"goal_ids": _goal_ids_of(e), **{k: (e.get("fields") or {}).get(k) for k in (
                FinEventFields.AMOUNT, FinEventFields.KIND, FinEventFields.OCCURRED_AT, FinEventFields.NOTE)}}
            for e in sorted(events, key=lambda e: str((e.get("fields") or {}).get(FinEventFields.OCCURRED_AT) or ""),
                            reverse=True)[:10]
        ],
        "as_of": today.isoformat(),
    }


def open_followups(identity, goal_id: str) -> list[dict]:
    """Open Tasks owned by the caller that already reference this goal (dedupe source)."""
    from airtable_schema import TaskFields
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        return []
    tag = f"[FCC:{goal_id}]"
    out = []
    for rec in _read(Tables.TASKS):
        f = rec.get("fields") or {}
        if f.get(TaskFields.STATUS) == "בוצע":
            continue
        if actor.profile_id not in policy.owner_refs(f, TaskFields.OWNER):
            continue
        if tag in str(f.get(TaskFields.DESCRIPTION) or ""):
            out.append(rec)
    return out
