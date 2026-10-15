"""Derived FCC numbers. Pure functions, no I/O, no hard-coded goals/targets.

Progress is event-based: nothing here is stored as a running total. Target
revisions are events too (kind ``target_change``) so history is never rewritten.

Event kinds:
  one_time           amount that happened once (income, saving, repayment)
  monthly_recurring  a change to the MONTHLY run-rate (new income stream,
                     cancelled expense, lower instalment) — never summed into
                     one-time totals
  direct_cost        positive cost tied directly to producing income (fuel, parking, fee).
                     ``actual`` stays gross (display); ``net`` = gross - costs drives remaining, pace and status
  target_change      ``amount`` is the new target, effective from occurred_at
  note               no amount semantics
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

ONE_TIME = "one_time"
MONTHLY_RECURRING = "monthly_recurring"
TARGET_CHANGE = "target_change"
DIRECT_COST = "direct_cost"
HOUSEHOLD_EXPENSE = "household_expense"   # private household spend: shown separately, never part of income/net
NOTE = "note"
DEPOSIT = "deposit"                       # a deposit into a financial account, linked to a goal (D1 step 6); counted ONLY as a deposit
EVENT_KINDS = (ONE_TIME, MONTHLY_RECURRING, TARGET_CHANGE, DIRECT_COST, HOUSEHOLD_EXPENSE, NOTE, DEPOSIT)
# Kinds that count as "a deposit made": the existing self-reported one_time, plus an account deposit. Never both for one event.
DEPOSIT_KINDS = (ONE_TIME, DEPOSIT)

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
    ref: str | None = None      # Airtable record id: the same event is never counted twice in a roll-up
    note: str = ""              # the event's free text (a weekly-surplus decision is read back from it)


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
        out.append(Event(kind, amount or 0.0, occurred, bool(f.get(ev_fields.SUPERSEDED_BY)), (rec or {}).get("id"), str(f.get(ev_fields.NOTE) or "")))
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


WEEK_SURPLUS_NOTE = "עודף שבועי"
MONTH_SUMMARY_NOTE = "סיכום חודש"
# how a closed week's surplus was settled: moved to the next week / kept for the month-end decision / spent / saved
WEEK_DECISION_WORDS = {"carry": "הועבר", "hold": "נשמר", "use": "נוצל", "save": "נחסך"}
MONTH_DECISION_WORDS = {"use": "נוצל", "save": "נחסך"}
_WEEK_NOTE_RE = re.compile(r"^" + WEEK_SURPLUS_NOTE + r" (\d{4}-\d{2}-\d{2}): (הועבר|נשמר|נוצל|נחסך)")
_MONTH_NOTE_RE = re.compile(r"^" + MONTH_SUMMARY_NOTE + r" (\d{4}-\d{2}): (נוצל|נחסך)")


def week_surplus_note(week_start: str, decision: str) -> str:
    return f"{WEEK_SURPLUS_NOTE} {week_start}: {WEEK_DECISION_WORDS[decision]}"


def month_summary_note(month: str, decision: str) -> str:
    return f"{MONTH_SUMMARY_NOTE} {month}: {MONTH_DECISION_WORDS[decision]}"


def week_decisions(live: list) -> dict[str, list[tuple[str, float]]]:
    """week_start -> [(decision word, amount)] read back from the note events written by the weekly-surplus question."""
    out: dict[str, list[tuple[str, float]]] = {}
    for e in live:
        m = _WEEK_NOTE_RE.match(e.note or "") if e.kind == NOTE else None
        if m:
            out.setdefault(m.group(1), []).append((m.group(2), e.amount))
    return out


def month_decisions(live: list) -> dict[str, float]:
    """YYYY-MM -> the amount of the pot already used / saved at the month-end decision."""
    out: dict[str, float] = {}
    for e in live:
        m = _MONTH_NOTE_RE.match(e.note or "") if e.kind == NOTE else None
        if m:
            out[m.group(1)] = out.get(m.group(1), 0.0) + e.amount
    return out


def weekly_quota(target: float | None, live: list, today: date) -> dict | None:
    """The TRUE weekly quota of a monthly goal, next to the dynamic pace: target / days-in-month × 7, each day at its OWN month's rate (a week
    that crosses a month end takes its last days from the next month's rate). Sunday-start weeks; the ledger starts at the first Sunday of the
    month of the current week's Sunday (the days before it belong to the previous month's last week); today's effective target is used for every week.

    Every week has its own quota. A SHORTFALL carries to the next week (it is still owed). A SURPLUS does not lower the next week by itself:
    unless the owner moved it to the next week, spent it or saved it, it is HELD for the month-end decision, and the held amount is visible all month
    (``held_total``). Decisions are read back from marker notes (see ``week_decisions`` / ``month_decisions``)."""
    if not target or target <= 0:
        return None
    rate = lambda day: target / calendar.monthrange(day.year, day.month)[1]
    net = lambda a, b: sum(e.amount for e in live if e.kind == ONE_TIME and a <= e.occurred <= b) \
        - sum(abs(e.amount) for e in live if e.kind == DIRECT_COST and a <= e.occurred <= b)
    sunday = lambda day: day - timedelta(days=(day.weekday() + 1) % 7)
    decided, month_done = week_decisions(live), month_decisions(live)
    this_week = sunday(today)
    first = this_week.replace(day=1)
    start, carry, history, held_prior = first + timedelta(days=(6 - first.weekday()) % 7), 0.0, [], 0.0
    while True:
        end = start + timedelta(days=6)
        quota = sum(rate(start + timedelta(days=i)) for i in range(7))
        actual = net(start, end)
        required = quota + carry
        balance = actual - required                              # > 0 surplus, < 0 shortfall
        surplus = max(balance, 0.0)
        words = decided.get(start.isoformat(), [])
        moved = sum((a or surplus) for w, a in words if w == "הועבר")        # an old marker without an amount moved the whole surplus
        moved = min(moved, surplus)
        spent = min(sum(a for w, a in words if w in ("נוצל", "נחסך")), surplus - moved)
        held = round(surplus - moved - spent, 2)
        if start == this_week:
            month = start.strftime("%Y-%m")
            held_total = max(round(held_prior + held - month_done.get(month, 0.0), 2), 0.0)
            return {"closing": _week_closing(start, end, surplus, held_total, history, today, decided, month_done, live, target),
                    "week_start": start.isoformat(), "week_end": end.isoformat(), "quota": round(quota, 2), "carry_in": round(carry, 2),
                    "required": round(max(required, 0.0), 2), "actual": round(actual, 2),
                    "remaining": round(max(required - actual, 0.0), 2), "surplus": held,
                    "balance": round(balance, 2), "held_total": held_total, "history": history}
        history.append({"week_start": start.isoformat(), "week_end": end.isoformat(), "quota": round(quota, 2),
                        "actual": round(actual, 2), "balance": round(balance, 2), "surplus": round(surplus, 2), "held": held})
        held_prior += held
        carry = (-balance if balance < 0 else 0.0) - moved
        start = start + timedelta(days=7)


def _week_closing(start: date, end: date, surplus: float, held_total: float, history: list[dict], today: date, decided: dict,
                  month_done: dict, live: list, target: float) -> dict | None:
    """The open question about a closed week's surplus. ``kind`` "week": what to do with THIS week's surplus (hold it for the month end — the
    default —, move it to the next week, spend it or save it); asked for the week that is closing (Friday / Saturday) or, until answered, the one
    that just closed. ``kind`` "month": the last week of a month, or the first days after it, asks what to do with the whole held amount (spend / save).
    Never twice for the same week or month."""
    month = start.strftime("%Y-%m")
    last_of_month = (start + timedelta(days=7)).month != start.month
    if last_of_month and (today.weekday() in (4, 5) or today > end):
        if month in month_done or held_total < 1:
            return None
        return {"kind": "month", "month": month, "week_start": start.isoformat(), "week_end": end.isoformat(), "amount": round(held_total, 2)}
    if today.weekday() in (4, 5) and not last_of_month:
        cand = {"week_start": start, "week_end": end, "surplus": surplus}
    elif history:
        h = history[-1]
        cand = {"week_start": date.fromisoformat(h["week_start"]), "week_end": date.fromisoformat(h["week_end"]), "surplus": h["surplus"]}
    else:
        previous = weekly_quota(target, live, start - timedelta(days=1)) if start.day <= 7 else None
        c = (previous or {}).get("closing")
        return c if c and c["kind"] == "month" else None
    ws = cand["week_start"]
    if ws.isoformat() in decided or cand["surplus"] < 1:
        return None
    return {"kind": "week", "week_start": ws.isoformat(), "week_end": cand["week_end"].isoformat(), "amount": round(cand["surplus"], 2)}


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
        costs = sum(abs(e.amount) for e in live if e.kind == DIRECT_COST and since <= e.occurred <= today)
        horizon_end = end
    elif method == RECURRING_LEVEL:
        actual = sum(e.amount for e in live if e.kind == MONTHLY_RECURRING and e.occurred <= today)
        costs = 0.0
        horizon_end = p_end
    else:
        actual = sum(e.amount for e in live if e.kind == ONE_TIME and p_start <= e.occurred <= p_end)
        costs = sum(abs(e.amount) for e in live if e.kind == DIRECT_COST and p_start <= e.occurred <= p_end)
        horizon_end = p_end

    # progress toward the target is NET (what is actually earned): direct costs reduce it, so the pace rises
    remaining = None if target is None else max(target - (actual - costs), 0.0)
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
        "actual": round(actual, 2),                      # gross (display only); remaining / pace / status use net
        "direct_costs": round(costs, 2),
        "net": round(actual - costs, 2),
        "remaining": None if remaining is None else round(remaining, 2),
        "remaining_periods": periods,
        "dynamic_target_per_week": dynamic,
        "weekly": weekly_quota(target, live, today) if method == PERIOD_SUM and period_type == "monthly" else None,
        "status": status,
    }


_PER_MONTH = {"monthly": 1.0, "quarterly": 1 / 3, "yearly": 1 / 12}
FLAGGED_REVIEW = ("reduce", "cancel", "negotiate")


def monthly_equivalent(amount, frequency) -> float | None:
    """Per-charge amount -> monthly cost. ``custom`` / unknown frequency has no honest conversion -> None."""
    amt = _num(amount)
    factor = _PER_MONTH.get(str(frequency or "").strip().lower())
    if amt is None or factor is None:
        return None
    return round(abs(amt) * factor, 2)


def summarize_obligations(items: list[dict]) -> dict:
    """items: {monthly, review_status, saving} of ACTIVE obligations. A commitment is never an actual expense:
    these numbers are never added to income, net or household spend."""
    total = flagged = saving = 0.0
    flagged_count = cancel_pending = 0
    for it in items:
        monthly = it.get("monthly")
        if monthly is None:
            continue
        total += monthly
        if it.get("review_status") in FLAGGED_REVIEW:
            flagged_count += 1
            cancel_pending += it["review_status"] == "cancel"
            flagged += monthly
            saving += it.get("saving") if it.get("saving") is not None else (
                monthly if it["review_status"] == "cancel" else 0.0)
    return {"total_monthly": round(total, 2), "flagged_count": flagged_count,
            "flagged_monthly": round(flagged, 2), "cancel_pending": cancel_pending, "potential_saving": round(saving, 2), "count": len(items)}


def monthly_level_now(events: list[Event], today: date) -> float:
    """Current standing level of a ``recurring_level`` goal: the running total of its monthly_recurring changes."""
    return round(sum(e.amount for e in events
                     if e.kind == MONTHLY_RECURRING and not e.superseded and e.occurred <= today), 2)


def _deposits(events: list[Event]) -> list[Event]:
    """Live deposits (one_time or deposit), each Airtable record once: the same ``ref`` is never counted twice."""
    seen: set[str] = set()
    out: list[Event] = []
    for e in events:
        if e.superseded or e.kind not in DEPOSIT_KINDS:
            continue
        if e.ref:
            if e.ref in seen:
                continue
            seen.add(e.ref)
        out.append(e)
    return out


def deposit_status(events: list[Event], today: date) -> dict:
    """Standing-order savings: PLAN (the standing level) vs ACTUAL (one_time deposits recorded in the month).
    A missed month is a recorded gap, never an automatic catch-up: next month's target is not inflated; a make-up
    deposit is simply a deposit in the month it is made. Superseded events are ignored."""
    live = [e for e in events if not e.superseded]
    this_start = today.replace(day=1)
    last_end = this_start - timedelta(days=1)
    last_start = last_end.replace(day=1)
    level = sum(e.amount for e in live if e.kind == MONTHLY_RECURRING and e.occurred <= today)
    level_last = sum(e.amount for e in live if e.kind == MONTHLY_RECURRING and e.occurred <= last_end)
    deps = _deposits(events)
    dep = sum(e.amount for e in deps if this_start <= e.occurred <= today)
    dep_last = sum(e.amount for e in deps if last_start <= e.occurred <= last_end)
    return {"level": round(level, 2), "deposited_month": round(dep, 2),
            "gap_month": round(max(level - dep, 0.0), 2),
            "deposited_last_month": round(dep_last, 2), "level_last_month": round(level_last, 2),
            "gap_last_month": round(max(level_last - dep_last, 0.0), 2)}


def household_month_total(events: list[Event], today: date) -> float:
    """Household spend in the calendar month of ``today`` (separate from income/net, superseded ignored)."""
    start = today.replace(day=1)
    return round(sum(abs(e.amount) for e in events
                     if e.kind == HOUSEHOLD_EXPENSE and not e.superseded and start <= e.occurred <= today), 2)


def monthly_cash_improvement(events: list[Event], today: date) -> float:
    """Sum of run-rate changes only; one-time amounts are never blended in."""
    return round(
        sum(e.amount for e in events if e.kind == MONTHLY_RECURRING and not e.superseded and e.occurred <= today), 2,
    )


def savings_release(net: float, income_target: float, fixed_level: float, deposited: float) -> dict:
    """What the month frees for savings. The fixed income (e.g. 8,000 a month) is only "free" once the income goal is met
    from the OTHER sources: every shekel the goal still lacks is taken from the fixed income, and every shekel above
    the goal is extra. available = max(net - (target - fixed), 0); e.g. goal 15,000, fixed 8,000, net 10,000 -> 3,000."""
    net, target, fixed, dep = (round(max(float(v or 0.0), 0.0), 2) for v in (net, income_target, fixed_level, deposited))
    shortfall = max(target - net, 0.0)
    from_fixed = max(fixed - shortfall, 0.0)
    extra = max(net - target, 0.0)
    available = round(from_fixed + extra, 2)
    expected = round(fixed + extra, 2)                   # what a full month would put away
    return {"income_net": net, "income_target": target, "fixed_level": fixed, "shortfall": round(shortfall, 2),
            "from_fixed": round(from_fixed, 2), "extra": round(extra, 2), "available": available,
            "deposited": dep, "remaining": round(max(available - dep, 0.0), 2), "expected": expected,
            "gap": round(max(expected - dep, 0.0), 2)}


def deposits_in_month(events: list[Event], today: date) -> float:
    """one_time deposits recorded in the current calendar month (superseded ones ignored)."""
    start = today.replace(day=1)
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return round(sum(e.amount for e in _deposits(events) if start <= e.occurred <= end), 2)


def _month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


def deposit_history(deposits: list[Event], plan: list[Event], today: date, months: int = 12) -> dict:
    """Self-reported deposit history from existing events only (nothing stored): deposits = one_time / deposit events on the long-term
    goal, plan = monthly_recurring events of the savings goal(s) (the standing level in force at each month's end).
    YTD covers January..the current month; the average is over those calendar months (a missed month counts as 0);
    the streak counts consecutive months with a deposit, ending this month (or last month while this one has none yet).
    Superseded events are ignored; a missed month is a gap, never caught up."""
    live = [e for e in _deposits(deposits) if e.occurred <= today]
    plans = [e for e in plan if not e.superseded and e.kind == MONTHLY_RECURRING]
    per_month: dict[int, float] = {}
    for e in live:
        per_month[_month_index(e.occurred)] = per_month.get(_month_index(e.occurred), 0.0) + e.amount
    now = _month_index(today)

    def level_at(idx: int) -> float:
        return sum(e.amount for e in plans if _month_index(e.occurred) <= idx)

    elapsed = today.month
    ytd_idx = range(now - elapsed + 1, now + 1)
    ytd = sum(per_month.get(i, 0.0) for i in ytd_idx)
    ytd_plan = sum(max(level_at(i), 0.0) for i in ytd_idx)
    start = now if per_month.get(now, 0.0) > 0 else now - 1
    streak, i = 0, start
    while per_month.get(i, 0.0) > 0:
        streak += 1
        i -= 1
    recent = []
    for i in range(now - months + 1, now + 1):
        y, m = divmod(i, 12)
        recent.append({"month": f"{y:04d}-{m + 1:02d}", "deposited": round(per_month.get(i, 0.0), 2),
                       "plan": round(max(level_at(i), 0.0), 2)})
    last = max((e.occurred for e in live), default=None)
    return {"ytd": round(ytd, 2), "ytd_plan": round(ytd_plan, 2), "ytd_gap": round(max(ytd_plan - ytd, 0.0), 2),
            "months_elapsed": elapsed, "monthly_average": round(ytd / elapsed, 2), "streak": streak,
            "last_deposit": last.isoformat() if last else None, "deposit_count": len(live), "recent": recent}


def month_closing(today: date, window: int = 7) -> bool:
    """The last ``window`` days of the calendar month: the "how much did you put away?" question is due."""
    return calendar.monthrange(today.year, today.month)[1] - today.day < window
