"""Derived FCC numbers. Pure functions, no I/O, no hard-coded goals/targets.

Progress is event-based: nothing here is stored as a running total. Target
revisions are events too (kind ``target_change``) so history is never rewritten.

Event kinds:
  one_time           amount that happened once (income, saving, repayment)
  monthly_recurring  a change to the MONTHLY run-rate (new income stream,
                     cancelled expense, lower instalment) — never summed into
                     one-time totals
  target_change      ``amount`` is the new target, effective from occurred_at
  note               no amount semantics
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

ONE_TIME = "one_time"
MONTHLY_RECURRING = "monthly_recurring"
TARGET_CHANGE = "target_change"
NOTE = "note"
EVENT_KINDS = (ONE_TIME, MONTHLY_RECURRING, TARGET_CHANGE, NOTE)

# calc_method values (data, not an enum the code branches business meaning on)
PERIOD_SUM = "period_sum"          # one_time events inside the current period
CUMULATIVE = "cumulative"          # all one_time events since start_date
RECURRING_LEVEL = "recurring_level"  # sum of monthly_recurring run-rate changes

# Presentation family of a numeric goal (derived from the method; "project" is decided by the service
# from the absence of any amount target — see service.classify_row).
MODE_BY_METHOD = {PERIOD_SUM: "recurring", RECURRING_LEVEL: "monthly_level", CUMULATIVE: "cumulative"}


def _d(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip()[:10]).date()
        except ValueError:
            return None
    return None


def _num(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class Event:
    kind: str
    amount: float
    occurred: date
    superseded: bool = False


def parse_events(records: list[dict], ev_fields) -> list[Event]:
    """Airtable event rows -> Event list. Malformed rows are skipped, never guessed."""
    out: list[Event] = []
    for rec in records or []:
        f = (rec or {}).get("fields") or {}
        kind = f.get(ev_fields.KIND)
        if isinstance(kind, dict):
            kind = kind.get("name")
        amount = _num(f.get(ev_fields.AMOUNT))
        occurred = _d(f.get(ev_fields.OCCURRED_AT))
        if kind not in EVENT_KINDS or occurred is None:
            continue
        if amount is None and kind != NOTE:
            continue
        out.append(Event(kind, amount or 0.0, occurred, bool(f.get(ev_fields.SUPERSEDED_BY))))
    return out


def period_bounds(period_type: str, today: date, start: date | None, end: date | None) -> tuple[date, date]:
    """Current period [start, end] from goal data. Monthly = calendar month of ``today``."""
    if period_type == "monthly":
        return today.replace(day=1), today.replace(day=calendar.monthrange(today.year, today.month)[1])
    if period_type == "weekly":
        begin = today - timedelta(days=(today.weekday() + 1) % 7)   # Sunday-start (IL)
        return begin, begin + timedelta(days=6)
    return start or today, end or start or today


def weeks_left(today: date, period_end: date) -> int:
    """Sunday-start weeks from the week containing ``today`` to ``period_end`` inclusive."""
    if period_end < today:
        return 0
    wk_start = today - timedelta(days=(today.weekday() + 1) % 7)
    return (period_end - wk_start).days // 7 + 1


def days_left(today: date, period_end: date) -> int:
    """Calendar days left in the period, today included (last day of the month => 1)."""
    return max((period_end - today).days + 1, 0)


def effective_target(base_target: float | None, events: list[Event], as_of: date) -> float | None:
    """Latest target_change on/before ``as_of`` wins; history stays in the events."""
    target = base_target
    changes = sorted(
        (e for e in events if e.kind == TARGET_CHANGE and not e.superseded and e.occurred <= as_of),
        key=lambda e: e.occurred,
    )
    if changes:
        target = changes[-1].amount
    return target


def parent_goal_id(fields: dict, gf) -> str | None:
    """Explicit "contributes to" link (Financial Goals -> Financial Goals). No inference from titles."""
    name = getattr(gf, "PARENT_GOAL", None)
    value = fields.get(name) if name else None
    if isinstance(value, list):
        value = next((v for v in value if isinstance(v, str)), None)
    return value if isinstance(value, str) and value.startswith("rec") else None


def compute_goal(goal: dict, events: list[Event], today: date, gf) -> dict:
    """Derived view of one goal. ``goal`` is an Airtable record, ``gf`` its field names."""
    f = goal.get("fields") or {}
    method = f.get(gf.CALC_METHOD)
    if isinstance(method, dict):
        method = method.get("name")
    method = method or PERIOD_SUM
    period_type = f.get(gf.PERIOD_TYPE)
    if isinstance(period_type, dict):
        period_type = period_type.get("name")
    start, end = _d(f.get(gf.START_DATE)), _d(f.get(gf.END_DATE))
    p_start, p_end = period_bounds(period_type or "monthly", today, start, end)
    live = [e for e in events if not e.superseded]

    target = effective_target(_num(f.get(gf.TARGET_AMOUNT)), live, today)

    if method == CUMULATIVE:
        since = start or date.min
        actual = sum(e.amount for e in live if e.kind == ONE_TIME and since <= e.occurred <= today)
        horizon_end = end
    elif method == RECURRING_LEVEL:
        actual = sum(e.amount for e in live if e.kind == MONTHLY_RECURRING and e.occurred <= today)
        horizon_end = p_end
    else:
        actual = sum(e.amount for e in live if e.kind == ONE_TIME and p_start <= e.occurred <= p_end)
        horizon_end = p_end

    remaining = None if target is None else max(target - actual, 0.0)
    periods = weeks_left(today, horizon_end) if horizon_end else None
    dynamic = None
    if method == PERIOD_SUM and period_type == "monthly":
        # monthly goal => weekly pace by REAL calendar days: remaining / days left * min(7, days left).
        # Never remaining / whole weeks: months of 28/30/31 days and partial first/last weeks stay correct.
        left = days_left(today, p_end)
        if remaining is not None and left:
            dynamic = round(remaining / left * min(7, left), 2)
        elif remaining == 0:
            dynamic = 0.0
    elif remaining is not None and periods:
        dynamic = round(remaining / periods, 2)
    elif remaining == 0:
        dynamic = 0.0
    if method == RECURRING_LEVEL:
        dynamic = None          # a change in the monthly run-rate has no weekly pace

    if target is None:
        status = "missing_target"
    elif remaining == 0:
        status = "achieved"
    elif horizon_end and horizon_end < today:
        status = "overdue"
    else:
        status = "in_progress"

    return {
        "goal_id": goal.get("id"),
        "parent_id": parent_goal_id(f, gf),
        "period_type": period_type or "monthly",
        "title": f.get(gf.TITLE),
        "method": method,
        "mode": MODE_BY_METHOD.get(method, "recurring"),
        "end_date": end.isoformat() if end else None,
        "period_start": p_start.isoformat(),
        "period_end": (horizon_end or p_end).isoformat(),
        "target": target,
        "actual": round(actual, 2),
        "remaining": None if remaining is None else round(remaining, 2),
        "remaining_periods": periods,
        "dynamic_target_per_week": dynamic,
        "status": status,
    }


def monthly_cash_improvement(events: list[Event], today: date) -> float:
    """Sum of run-rate changes only; one-time amounts are never blended in."""
    return round(
        sum(e.amount for e in events if e.kind == MONTHLY_RECURRING and not e.superseded and e.occurred <= today), 2,
    )
