"""Owner-scoped FCC reads. Every record leaves this module only after
``data_access_policy.filter_records`` — aggregates are computed on the filtered
set, so another person's goals never reach a total, a search or a plan.

Reads go through ``tools.airtable_read_adapter`` (read-only provider adapter);
writes are never done here (see ``writer`` + the ActionGateway path).
"""

from __future__ import annotations

import logging
import re
from datetime import date

from airtable_schema import FinEventFields, FinGoalFields, LoanFields, Tables
from core import data_access_policy as policy
from core.financial_control import assets as fcc_assets, calc, loans as fcc_loans

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


# Presentation mapping only: header cards read goals by their editable ``Category``
# value. Goals themselves stay data (no hard-coded list); a missing category simply
# leaves the card empty ("set a goal").
# Goal families (presentation only; the Goals table is unchanged):
#   recurring     period_sum        e.g. monthly income      -> target / actual / remaining / weekly pace
#   monthly_level recurring_level   e.g. lower the instalment -> target / achieved / remaining (no weekly pace)
#   cumulative    cumulative        e.g. close loans, emergency fund -> total target / actual / remaining / % (pace only with an end date)
#   project       no amount target  e.g. sell a property     -> status + next action + date, never ₪0 / "—"
NUMERIC_CATEGORIES = ("income", "savings", "emergency_fund", "debt")
SUMMARY_CATEGORIES = {
    "income": ("income", "הכנסה"),
    "savings": ("savings", "חיסכון"),
    "debt": ("debt_repaid", "חוב", "debt"),
    "emergency_fund": ("emergency_fund", "קרן חירום"),
}


def _category_key(category) -> str | None:
    if isinstance(category, dict):
        category = category.get("name")
    cat = str(category or "").strip().casefold()
    for key, names in SUMMARY_CATEGORIES.items():
        if cat in {n.casefold() for n in names}:
            return key
    return None


def classify_row(row: dict, next_action: dict | None) -> dict:
    """Decide the goal family. No amount target + not a numeric category => project/milestone:
    amounts are blanked (no ₪0 / dead "—" cells) and the card carries the next action instead."""
    if row.get("target") is None and _category_key(row.get("category")) is None:
        row.update(mode="project", status="project", actual=None, remaining=None, direct_costs=None, net=None,
                   remaining_periods=None, dynamic_target_per_week=None, next_action=next_action)
    return row


# summary card key -> (category key, modes that belong to the card). Different modes are NEVER summed together.
_CARDS = {
    "income": ("income", ("recurring",)),
    "savings": ("savings", ("monthly_level",)),        # standing monthly allocation vs target (never resets); legacy cumulative: see _CARD_FALLBACKS
    "emergency_fund": ("emergency_fund", ("cumulative",)),
    "debt_repaid": ("debt", ("cumulative",)),
    "payment_reduction": ("debt", ("recurring", "monthly_level")),
}


# A legacy one-time (cumulative) savings goal still shows on the savings card until it is switched to a monthly
# allocation — but only when no monthly savings goal exists, so the two families are never summed.
_CARD_FALLBACKS = {"savings": ("cumulative",)}


def _parent_map(goals: list[dict], active_ids: set[str]) -> dict[str, str]:
    """child -> parent from the explicit ``Contributes To`` link. Only active parents count; self-links
    and cycles are dropped (a cycle would otherwise count an event inside itself)."""
    raw = {}
    for g in goals:
        pid = calc.parent_goal_id(g.get("fields") or {}, FinGoalFields)
        if pid and pid != g["id"] and pid in active_ids and g["id"] in active_ids:
            raw[g["id"]] = pid
    out = {}
    for child, parent in raw.items():
        seen, cur = {child}, parent
        while cur in raw and cur not in seen:
            seen.add(cur)
            cur = raw[cur]
        if cur not in seen:
            out[child] = parent
    return out


def _rolled_up(goal_id: str, own: dict[str, list[calc.Event]], parent_of: dict[str, str]) -> list[calc.Event]:
    """Own events + all descendants' events (target changes of a source never move the parent's target),
    de-duplicated by event record id."""
    result, seen = list(own.get(goal_id, [])), {e.ref for e in own.get(goal_id, []) if e.ref}
    stack, visited = [goal_id], {goal_id}
    while stack:
        cur = stack.pop()
        for child, parent in parent_of.items():
            if parent != cur or child in visited:
                continue
            visited.add(child)
            stack.append(child)
            for e in own.get(child, []):
                if e.kind == calc.TARGET_CHANGE or (e.ref and e.ref in seen):
                    continue
                if e.ref:
                    seen.add(e.ref)
                result.append(e)
    return result


def _attach_sources(rows: list[dict]) -> None:
    """Parent rows list their direct sources. Weekly sources are minimums inside the parent's weekly
    pace, so ``other_sources_needed`` = max(parent weekly pace - what the weekly sources still owe, 0)."""
    for row in rows:
        kids = [r for r in rows if r.get("parent_id") == row["goal_id"] and r.get("target") is not None]
        if not kids:
            continue
        row["sources"] = [{"goal_id": k["goal_id"], "title": k["title"], "period_type": k.get("period_type"),
                           "target": k["target"], "actual": k["actual"], "remaining": k["remaining"],
                           "direct_costs": k.get("direct_costs") or 0.0, "net": k.get("net")} for k in kids]
        owed = sum(k["remaining"] or 0.0 for k in kids if k.get("period_type") == "weekly")
        pace = row.get("dynamic_target_per_week")
        row["weekly_sources_required"] = round(owed, 2)
        row["other_sources_needed"] = None if pace is None else round(max(pace - owed, 0.0), 2)


def _accumulate(out: dict, rows: list[dict], cards: dict) -> None:
    for row in rows:
        if row.get("mode") == "project" or row.get("target") is None or row.get("is_source"):
            continue            # a source's target/actual live inside its parent (no double counting)
        cat = _category_key(row.get("category"))
        for key, (card_cat, modes) in cards.items():
            if cat != card_cat or row.get("mode") not in modes:
                continue
            card = out.setdefault(key, {"target": 0.0, "actual": 0.0, "remaining": 0.0, "direct_costs": 0.0,
                                        "net": 0.0, "dynamic_target_per_week": 0.0, "goals": 0, "mode": row.get("mode")})
            card["goals"] += 1
            for src in row.get("sources") or []:
                card.setdefault("sources", []).append(src)
            if row.get("sources"):
                card["weekly_sources_required"] = round(card.get("weekly_sources_required", 0.0) + row["weekly_sources_required"], 2)
                if row.get("other_sources_needed") is not None:
                    card["other_sources_needed"] = round(card.get("other_sources_needed", 0.0) + row["other_sources_needed"], 2)
            for field in ("target", "actual", "remaining", "dynamic_target_per_week", "direct_costs", "net",
                          "deposited_month", "gap_month", "gap_last_month"):
                if field in ("deposited_month", "gap_month", "gap_last_month") and field not in row:
                    continue
                card[field] = round(card.get(field, 0.0) + (row.get(field) or 0.0), 2)


def summarize(rows: list[dict]) -> dict:
    """Header cards: per (category, family) sums over the owner's rows only. A cumulative loan balance
    is never added to a monthly instalment reduction, and projects never enter any card."""
    out: dict[str, dict] = {}
    _accumulate(out, rows, _CARDS)
    missing = {k: (_CARDS[k][0], modes) for k, modes in _CARD_FALLBACKS.items() if k not in out}
    if missing:
        _accumulate(out, rows, missing)
    return out


_FCC_TAG = re.compile(r"\[FCC:([A-Za-z0-9]+)\]")


def fcc_tasks(identity) -> list[dict]:
    """Open follow-up Tasks created from FCC goals, owned by the caller only."""
    from airtable_schema import TaskFields
    from core.financial_control.draft import FCC_TASK_TOPIC
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        return []
    out = []
    for rec in _read(Tables.TASKS):
        f = rec.get("fields") or {}
        if f.get(TaskFields.STATUS) == "בוצע":
            continue
        if actor.profile_id not in policy.owner_refs(f, TaskFields.OWNER):
            continue
        topic = f.get(TaskFields.TOPIC)
        topic = topic.get("name") if isinstance(topic, dict) else topic
        desc = str(f.get(TaskFields.DESCRIPTION) or "")
        if topic != FCC_TASK_TOPIC or "[FCC:" not in desc:
            continue
        tag = _FCC_TAG.search(desc)
        out.append({"id": rec.get("id"), "goal_id": tag.group(1) if tag else None, "title": f.get(TaskFields.NAME),
                    "due_date": f.get(TaskFields.DUE_DATE), "status": f.get(TaskFields.STATUS)})
    return sorted(out, key=lambda t: (t["due_date"] is None, str(t["due_date"] or "")))


_ASSET_TAG = re.compile(r"\[FCC-ASSET:(rec[A-Za-z0-9]+)\]")
_SUBJECT_TAG = re.compile(r"\[FCC-(ASSET|LOAN):(rec[A-Za-z0-9]+)\]")


def next_actions(identity) -> list[dict]:
    """OPEN next-action Tasks of the caller's assets AND loans (Topic כספים + a ``[FCC-ASSET:<id>]`` / ``[FCC-LOAN:<id>]`` tag).
    Owner-scoped like every Task read; a closed (בוצע) task is history and not returned. The responsible person is a line in the
    description. ``subject_kind`` / ``subject_id`` name what the action belongs to (``asset_id`` is kept for assets)."""
    from airtable_schema import TaskFields
    from core.financial_control.draft import FCC_TASK_TOPIC
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        return []
    out = []
    for rec in _read(Tables.TASKS):
        f = rec.get("fields") or {}
        status = _sel(f.get(TaskFields.STATUS))
        if status == "בוצע" or actor.profile_id not in policy.owner_refs(f, TaskFields.OWNER):
            continue
        desc = str(f.get(TaskFields.DESCRIPTION) or "")
        tag = _SUBJECT_TAG.search(desc)
        if _sel(f.get(TaskFields.TOPIC)) != FCC_TASK_TOPIC or tag is None:
            continue
        owner = next((l.split(":", 1)[1].strip() for l in desc.splitlines() if l.startswith("אחראי:")), None)
        history = "\n".join(l for l in desc.splitlines() if l.strip() and not l.startswith("[FCC-") and not l.startswith("אחראי:"))
        kind = tag.group(1).lower()
        row = {"id": rec.get("id"), "subject_kind": kind, "subject_id": tag.group(2), "title": f.get(TaskFields.NAME),
               "status": status or "ממתין", "due_date": f.get(TaskFields.DUE_DATE), "owner": owner, "history": history,
               "description": desc}
        if kind == "asset":
            row["asset_id"] = tag.group(2)
        out.append(row)
    return sorted(out, key=lambda t: (t["due_date"] is None, str(t["due_date"] or ""), str(t["title"] or "")))


def asset_tasks(identity) -> list[dict]:
    """Open next actions of the caller's ASSETS only."""
    return [t for t in next_actions(identity) if t["subject_kind"] == "asset"]


def loan_tasks(identity) -> list[dict]:
    """Open next actions of the caller's LOANS / debts owed to the caller."""
    return [t for t in next_actions(identity) if t["subject_kind"] == "loan"]


def my_obligations(identity) -> list[dict]:
    """Recurring commitments of the caller only (owner-scoped table)."""
    return policy.filter_records(Tables.REC_OBLIGATIONS, _read(Tables.REC_OBLIGATIONS), identity)


def _sel(value):
    return value.get("name") if isinstance(value, dict) else value


def obligation_items(records: list[dict]) -> list[dict]:
    """Active obligations as {monthly, review_status, saving}; the monthly equivalent is computed here (the
    Airtable formula is display-only), so the number does not depend on the storage provider."""
    from airtable_schema import RecObFields as RF
    items = []
    for rec in records:
        f = rec.get("fields") or {}
        if not f.get(RF.ACTIVE):
            continue
        items.append({"monthly": calc.monthly_equivalent(f.get(RF.AMOUNT), _sel(f.get(RF.FREQUENCY))),
                      "review_status": _sel(f.get(RF.REVIEW_STATUS)),
                      "saving": calc._num(f.get(RF.POTENTIAL_SAVING))})
    return items


def obligations_overview(identity) -> dict:
    try:
        return calc.summarize_obligations(obligation_items(my_obligations(identity)))
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] obligations read failed")
        return calc.summarize_obligations([])


def receipts_overview(identity) -> dict:
    """Caller's OWN business expenses still missing a receipt (count + amount only, no row details).
    ``Expenses`` is a shared ledger, so rows are kept only when the caller is in the row's ``owner``
    link; an unresolved identity or any read failure yields zeros (never another person's rows)."""
    from airtable_schema import ExpenseFields as XF
    empty = {"missing_count": 0, "missing_amount": 0.0}
    try:
        actor = policy.resolve_actor(identity)
        if not actor.resolved:
            return empty
        records = _read(Tables.EXPENSES)
    except Exception:
        logger.exception("[fcc] receipts read failed")
        return empty
    count, amount = 0, 0.0
    for rec in records:
        f = rec.get("fields") or {}
        if actor.profile_id not in policy.owner_refs(f, "owner"):
            continue
        status = f.get(XF.RECEIPT_STATUS)
        status = status.get("name") if isinstance(status, dict) else status
        if f.get(XF.RECEIPT_REQUIRED) and status != "received":
            count += 1
            amount += abs(float(f.get(XF.AMOUNT) or 0))
    return {"missing_count": count, "missing_amount": round(amount, 2)}


def my_loans(identity) -> list[dict]:
    """The caller's own Loans rows (owner-scoped; a denied identity propagates)."""
    return policy.filter_records(Tables.LOANS, _read(Tables.LOANS), identity)


def my_assets(identity) -> list[dict]:
    """The caller's own Assets rows (owner-scoped; a denied identity propagates)."""
    return policy.filter_records("Assets", _read("Assets"), identity)


def loan_scenarios(identity, budget: float, today: date | None = None) -> dict:
    """Early-payoff budget simulation over the caller's own active loans. Pure computation: no write, no execution."""
    records = policy.filter_records(Tables.LOANS, _read(Tables.LOANS), identity)
    return fcc_loans.scenarios(records, today or date.today(), budget)


def loans_overview(identity, today: date, debt_goal: dict | None = None) -> dict:
    """Caller's own loans (owner-scoped table) with derived numbers. Asset names come only from the caller's own
    Assets rows. A read failure degrades to an empty section; a denied identity still propagates."""
    try:
        records = policy.filter_records(Tables.LOANS, _read(Tables.LOANS), identity)
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] loans read failed")
        return fcc_loans.build([], today, None, debt_goal)
    names: dict[str, str] = {}
    if any((r.get("fields") or {}).get(LoanFields.RELATED_ASSET) for r in records):
        try:
            for a in policy.filter_records("Assets", _read("Assets"), identity):
                names[a["id"]] = (a.get("fields") or {}).get("Name") or ""
        except policy.PersonalDataAccessDenied:
            raise
        except Exception:
            logger.exception("[fcc] loan asset names read failed")
    try:
        tasks = loan_tasks(identity)
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] loan next actions read failed")
        tasks = []
    return fcc_loans.build(records, today, {k: v for k, v in names.items() if v}, debt_goal, tasks)


def assets_overview(identity, loan_items: list[dict]) -> dict:
    """Caller's own assets (owner-scoped table) with their linked loans. Read-only; a read failure degrades to an
    empty section, a denied identity still propagates."""
    try:
        records = policy.filter_records("Assets", _read("Assets"), identity)
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] assets read failed")
        records = []
    try:
        tasks = asset_tasks(identity)
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] asset next actions read failed")
        tasks = []
    mine = [i for i in loan_items if i.get("direction") != fcc_loans.OWED_TO_ME]       # a debt owed TO the owner is not asset-linked debt
    return fcc_assets.build(records, mine, tasks, fcc_loans.debt_balance(loan_items))


def _raw_category(category) -> str:
    return str((category.get("name") if isinstance(category, dict) else category) or "").strip().casefold()


FIXED_INCOME_CATEGORY = "fixed_income"        # live Financial Goals.Category choice (a standing income, not part of the income goal)
SAVINGS_DESTINATION_CATEGORY = "long_term"    # the pension portfolio goal: the one active goal of this category receives deposits


def savings_release_view(rows: list[dict], summary: dict, own: dict[str, list[calc.Event]], goals: list[dict],
                         active_ids: set[str], today: date) -> dict | None:
    """The monthly "freed for savings" picture, or None when it cannot be derived (no income goal / no fixed income).
    Pure derivation from existing goals and events — nothing is written or assumed from a title."""
    income = summary.get("income")
    fixed = round(sum(r.get("target") or 0.0 for r in rows if _raw_category(r.get("category")) == FIXED_INCOME_CATEGORY), 2)
    if not income or not income.get("target") or fixed <= 0:
        return None
    dests = [g for g in goals if g["id"] in active_ids
             and _raw_category((g.get("fields") or {}).get(FinGoalFields.CATEGORY)) == SAVINGS_DESTINATION_CATEGORY]
    dest = dests[0] if len(dests) == 1 else None
    deposited = calc.deposits_in_month(own.get(dest["id"], []), today) if dest else 0.0
    out = calc.savings_release(income.get("net") if income.get("net") is not None else income.get("actual"),
                               income["target"], fixed, deposited)
    out.update(month=today.strftime("%Y-%m"), closing=calc.month_closing(today),
               destination=({"id": dest["id"], "title": (dest.get("fields") or {}).get(FinGoalFields.TITLE)} if dest else None))
    return out


def overview(identity, today: date | None = None) -> dict:
    """Private screen payload: goals with derived numbers + monthly cash improvement."""
    today = today or date.today()
    goals = my_goals(identity)
    events = my_events(identity)
    by_goal: dict[str, list[dict]] = {}
    for ev in events:
        for gid in _goal_ids_of(ev):
            by_goal.setdefault(gid, []).append(ev)

    tasks = fcc_tasks(identity)
    next_by_goal: dict[str, dict] = {}
    for t in tasks:                                           # tasks are sorted by due date: first wins
        if t.get("goal_id") and t["goal_id"] not in next_by_goal:
            next_by_goal[t["goal_id"]] = {"title": t["title"], "due_date": t["due_date"]}

    active_ids = {g["id"] for g in goals
                  if str((g.get("fields") or {}).get(FinGoalFields.STATUS) or "active").lower() in ("active", "פעיל")}
    parent_of = _parent_map(goals, active_ids)
    own: dict[str, list[calc.Event]] = {
        g["id"]: calc.parse_events(by_goal.get(g["id"], []), FinEventFields) for g in goals}

    rows, all_events = [], []
    for goal in goals:
        all_events.extend(own[goal["id"]])
        if goal["id"] not in active_ids:
            continue
        gf = goal.get("fields") or {}
        # parent goal = its own events + every descendant source's events, each event once (roll-up)
        row = calc.compute_goal(goal, _rolled_up(goal["id"], own, parent_of), today, FinGoalFields)
        row["category"] = gf.get(FinGoalFields.CATEGORY)
        row["priority"] = gf.get(FinGoalFields.PRIORITY)
        row["parent_id"] = parent_of.get(goal["id"])
        row["is_source"] = goal["id"] in parent_of
        if row.get("mode") == "monthly_level" and _category_key(gf.get(FinGoalFields.CATEGORY)) == "savings":
            row.update(calc.deposit_status(own[goal["id"]], today))      # plan (level) vs actual deposits this month
        rows.append(classify_row(row, next_by_goal.get(goal["id"])))
    _attach_sources(rows)
    summary = summarize(rows)
    loans_payload = loans_overview(identity, today, summary.get("debt_repaid"))

    return {
        "goals": rows,
        "summary": summary,
        "savings_release": savings_release_view(rows, summary, own, goals, active_ids, today),
        "loans": loans_payload,
        "assets": assets_overview(identity, loans_payload["items"]),
        "household": {"month_total": calc.household_month_total(all_events, today)},
        "receipts": receipts_overview(identity),
        "obligations": obligations_overview(identity),
        "tasks": tasks,
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
