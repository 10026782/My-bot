"""Owner-scoped FCC reads. Every record leaves this module only after
``data_access_policy.filter_records`` — aggregates are computed on the filtered
set, so another person's goals never reach a total, a search or a plan.

Reads go through ``tools.airtable_read_adapter`` (read-only provider adapter);
writes are never done here (see ``writer`` + the ActionGateway path).
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import re
from datetime import date, timedelta

from airtable_schema import CashflowRuleFields, FinEventFields, FinGoalFields, FundingPlanFields, GoalAllocationFields, LoanFields, Tables
from core import data_access_policy as policy
from core.financial_control import assets as fcc_assets, calc, cashflow as fcc_cashflow, amortization as fcc_amortization, loans as fcc_loans, refinance as fcc_refinance

logger = logging.getLogger(__name__)

_MAX_ROWS = 500
_WIDE_ROWS = 8000                    # statement imports: hundreds of rows a month must not be silently cut at 500
_ROW_LIMIT = contextvars.ContextVar("fcc_row_limit", default=_MAX_ROWS)


@contextlib.contextmanager
def wide_reads(limit: int = _WIDE_ROWS):
    """Reads inside the block may return up to ``limit`` rows (only the imported-events reads use it)."""
    token = _ROW_LIMIT.set(limit)
    try:
        yield
    finally:
        _ROW_LIMIT.reset(token)


def _read(table: str, formula: str = "") -> list[dict]:
    from tools.airtable_read_adapter import list_records
    return list_records(table, formula, max_records=_ROW_LIMIT.get(), paginate=True)


def _record_fields(table: str, record_id: str) -> dict:
    from tools.airtable_read_adapter import get_record_fields
    return get_record_fields(table, record_id)


def my_goals(identity) -> list[dict]:
    """Active-or-not goals of the caller only. Unresolved identity -> PersonalDataAccessDenied."""
    records = _read(Tables.FIN_GOALS)
    mine = policy.filter_records(Tables.FIN_GOALS, records, identity)
    return sorted(mine, key=lambda r: ((r.get("fields") or {}).get(FinGoalFields.DISPLAY_ORDER) or 9999))


_IMPORT_SOURCE = "import:"          # Financial Progress Events.Source of a row written by a statement import (no goal link)


def _is_import(ev: dict) -> bool:
    return str((ev.get("fields") or {}).get(FinEventFields.SOURCE) or "").startswith(_IMPORT_SOURCE)


def my_events(identity, imported: str = "exclude", since: date | None = None) -> list[dict]:
    """The caller's own events. ``imported``: "exclude" (default — goal progress and every pre-import consumer, unaffected by how many statement rows exist),
    "only" (statement-import rows, optionally ``since`` a date: they are numerous, so the read is wide and date-limited) or "all"."""
    F = FinEventFields
    clauses = []
    if imported == "exclude":
        clauses.append(f"NOT(LEFT({{{F.SOURCE}}},{len(_IMPORT_SOURCE)})='{_IMPORT_SOURCE}')")
    elif imported == "only":
        clauses.append(f"LEFT({{{F.SOURCE}}},{len(_IMPORT_SOURCE)})='{_IMPORT_SOURCE}'")
    if since is not None and imported == "only":
        clauses.append(f"IS_AFTER({{{F.OCCURRED_AT}}},'{(since - timedelta(days=1)).isoformat()}')")
    formula = clauses[0] if len(clauses) == 1 else f"AND({','.join(clauses)})" if clauses else ""
    ctx = wide_reads() if imported != "exclude" else contextlib.nullcontext()
    with ctx:
        records = policy.filter_records(Tables.FIN_EVENTS, _read(Tables.FIN_EVENTS, formula), identity)
    if imported == "exclude":                                                  # belt and braces: the formula only saves transfer, this is the rule
        records = [e for e in records if not _is_import(e)]
    elif imported == "only":
        records = [e for e in records if _is_import(e)
                   and (since is None or (calc._d((e.get("fields") or {}).get(F.OCCURRED_AT)) or date.min) >= since)]
    return records


def existing_import_fields(identity, since: date | None = None) -> dict[str, dict]:
    """The caller's own imported rows by idempotency key -> their fields (what a re-import may still fill: the billing date, the instalments label)."""
    out = {}
    for e in my_events(identity, "only", since):
        f = e.get("fields") or {}
        key = str(f.get(FinEventFields.IDEMPOTENCY_KEY) or "")
        if key:
            out[key] = f
    return out


def existing_import_keys(identity, since: date | None = None) -> set[str]:
    """Idempotency keys of the caller's own imported rows (a re-imported statement writes nothing)."""
    return {str((e.get("fields") or {}).get(FinEventFields.IDEMPOTENCY_KEY) or "") for e in my_events(identity, "only", since)} - {""}


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


def _cumulative_by_default(category) -> bool:
    """The categories draft.INFERENCE gives a cumulative Calc Method: future_goal by its raw key; debt / emergency_fund also by their Hebrew and legacy
    names (SUMMARY_CATEGORIES: "חוב", "debt_repaid", "קרן חירום"). Every other category (long_term / investment / savings / income / other / empty)
    with an empty method stays period_sum, exactly as on every other screen."""
    return _raw_category(category) == "future_goal" or _category_key(category) in ("debt", "emergency_fund")


def classify_row(row: dict, next_action: dict | None) -> dict:
    """Decide the goal family. No amount target + not a numeric category => project/milestone:
    amounts are blanked (no ₪0 / dead "—" cells) and the card carries the next action instead."""
    if row.get("target") is None and _category_key(row.get("category")) is None:
        row.update(mode="project", status="project", actual=None, remaining=None, direct_costs=None, net=None,
                   remaining_periods=None, dynamic_target_per_week=None, weekly=None, next_action=next_action)
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
            wk = row.get("weekly")
            if wk:                                                    # the fixed weekly quota: same week for every goal, so the parts add up
                tot = card.setdefault("weekly", {"week_start": wk["week_start"], "week_end": wk["week_end"], "quota": 0.0, "carry_in": 0.0,
                                                 "required": 0.0, "actual": 0.0, "remaining": 0.0, "surplus": 0.0, "balance": 0.0, "held_total": 0.0, "closing": None})
                for k in ("quota", "carry_in", "required", "actual", "remaining", "surplus", "balance", "held_total"):
                    tot[k] = round(tot[k] + wk[k], 2)
                if wk.get("closing"):                                 # the open question: same week for every goal, amounts add up
                    cl = tot.get("closing")
                    tot["closing"] = ({**wk["closing"], "goal_id": row["goal_id"]} if cl is None
                                      else {**cl, "amount": round(cl["amount"] + wk["closing"]["amount"], 2)})


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


def my_funding_plans(identity) -> list[dict]:
    """Funding planner step 2: the caller's OWN saved plan snapshots (owner-scoped table). Read-only; used to supersede an earlier plan of the same goal."""
    return policy.filter_records(Tables.FUNDING_PLANS, _read(Tables.FUNDING_PLANS), identity)


def _json_field(value):
    """A saved snapshot cell -> parsed JSON, or None when empty / not valid JSON (the comparison then says it cannot compare)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


def chosen_plan_snapshots_for_funding(identity) -> list[dict]:
    """Funding planner step 3: the caller's OWN ``chosen`` saved plans (owner-scoped table, read-only), reduced to what the pure comparison needs:
    goal, date computed / saved, the frozen selected options, request and result snapshots. Nothing here is written back."""
    out = []
    for r in my_funding_plans(identity):
        f = r.get("fields") or {}
        goal = f.get(FundingPlanFields.GOAL)
        if str(_sel(f.get(FundingPlanFields.STATUS)) or "").lower() != "chosen" or not (isinstance(goal, list) and len(goal) == 1 and isinstance(goal[0], str)):
            continue
        out.append({"id": r.get("id"), "goal_id": goal[0], "as_of": str(f.get(FundingPlanFields.AS_OF) or "")[:10] or None,
                    "saved_at": str(f.get(FundingPlanFields.CREATED_AT) or "")[:10] or None,
                    "selected": _json_field(f.get(FundingPlanFields.SELECTED_OPTIONS)), "request": _json_field(f.get(FundingPlanFields.REQUEST_SNAPSHOT)),
                    "result": _json_field(f.get(FundingPlanFields.RESULT_SNAPSHOT))})
    return out


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


def commitment_rows(records: list[dict]) -> list[dict]:
    """Active obligations with their NAME, for the cashflow recommendations only (never summed into any total)."""
    from airtable_schema import RecObFields as RF
    rows = []
    for rec in records:
        f = rec.get("fields") or {}
        if not f.get(RF.ACTIVE):
            continue
        rows.append({"name": str(f.get(RF.NAME) or "").strip(), "monthly": calc.monthly_equivalent(f.get(RF.AMOUNT), _sel(f.get(RF.FREQUENCY))),
                     "review_status": _sel(f.get(RF.REVIEW_STATUS)), "essentiality": _sel(f.get(RF.ESSENTIALITY)),
                     "saving": calc._num(f.get(RF.POTENTIAL_SAVING))})
    return rows


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


def my_accounts(identity) -> list[dict]:
    """The caller's own Financial Accounts rows (owner-scoped; a denied identity propagates)."""
    return policy.filter_records(Tables.FIN_ACCOUNTS, _read(Tables.FIN_ACCOUNTS), identity)


def loan_scenarios(identity, budget: float, today: date | None = None) -> dict:
    """Early-payoff budget simulation over the caller's own active loans. Pure computation: no write, no execution."""
    records = policy.filter_records(Tables.LOANS, _read(Tables.LOANS), identity)
    return fcc_loans.scenarios(records, today or date.today(), budget)


def loan_refinance(identity, params: dict, today: date | None = None) -> dict:
    """Refinance simulation: the caller's own active loans rolled into ONE mortgage at the typed offer. Pure computation over their own rows (and their own stored lender
    schedules, read once): nothing is saved."""
    offer = fcc_refinance.parse_offer(params)
    day = today or date.today()
    records = my_loans(identity)
    schedules = {r.get("id"): fcc_amortization.loads((r.get("fields") or {}).get(LoanFields.SCHEDULE)) for r in records}
    return fcc_refinance.simulate([fcc_loans.loan_item(r, day) for r in records], offer, {k: v for k, v in schedules.items() if v}, day)


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
    payload = fcc_loans.build(records, today, {k: v for k, v in names.items() if v}, debt_goal, tasks)
    payload["auto_step"] = loan_auto_step_enabled()          # the screen says balances follow their schedule only when the job is on
    return payload


LOAN_AUTO_STEP_FLAG = "FEATURE_FCC_LOAN_AUTO_STEP"        # default OFF: the monthly job writes to the owner's loans


def loan_auto_step_enabled() -> bool:
    import feature_flags
    return feature_flags.is_enabled(LOAN_AUTO_STEP_FLAG)


def auto_step_identities() -> list:
    """The owners the monthly job may act for: registry identities with the OWNER role that the FCC gate (flag + canary allowlist) admits.
    Nobody else's loans are ever read or written."""
    import identity as identity_module
    from core.financial_control import gate
    found, seen = [], set()
    for key in list(identity_module._REGISTRY):
        channel, _, external_id = str(key).partition(":")
        who = identity_module.resolve_identity(channel, external_id)
        if who.role == identity_module.Role.OWNER and who.user_id not in seen and gate.enabled_for(who):
            seen.add(who.user_id)
            found.append(who)
    return found


def plan_loan_auto_step(identity, today: date | None = None) -> list[dict]:
    """READ-ONLY plan of the monthly job for ONE owner: every due instalment of the owner's own loans (``loans.auto_step``).
    The writes are executed by the scheduler job through the Airtable gateway — this package never writes."""
    today = today or date.today()
    return [step for step in (fcc_loans.auto_step(rec, today) for rec in my_loans(identity)) if step is not None]


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


RECENT_INCOMES = 12


def recent_incomes(goals: list[dict], events: list[dict], limit: int = RECENT_INCOMES) -> list[dict]:
    """The latest income entries the owner booked (one-time income and its direct costs), newest first, each with the source / goal it was
    booked on, so a second entry is never made by mistake. The same goal + kind + amount + day shown twice is flagged as a possible duplicate.
    Own rows only (the callers pass the owner-scoped goals / events); superseded rows and non-income goals never appear."""
    income = {g["id"]: (g.get("fields") or {}).get(FinGoalFields.TITLE) for g in goals
              if _category_key((g.get("fields") or {}).get(FinGoalFields.CATEGORY)) == "income"}
    rows = []
    for ev in events:
        f = ev.get("fields") or {}
        kind = _sel(f.get(FinEventFields.KIND))
        gid = next((g for g in _goal_ids_of(ev) if g in income), None)
        day, amount = calc._d(f.get(FinEventFields.OCCURRED_AT)), calc._num(f.get(FinEventFields.AMOUNT))
        if kind not in (calc.ONE_TIME, calc.DIRECT_COST) or gid is None or day is None or amount is None or f.get(FinEventFields.SUPERSEDED_BY):
            continue
        rows.append({"id": ev.get("id"), "date": day.isoformat(), "goal_id": gid, "source": income[gid], "kind": kind,
                     "amount": abs(amount), "note": (f.get(FinEventFields.NOTE) or "").strip() or None})
    rows.sort(key=lambda r: (r["date"], str(r["id"])), reverse=True)
    rows = rows[:limit]
    seen: dict[tuple, int] = {}
    for r in rows:
        key = (r["goal_id"], r["kind"], r["amount"], r["date"])
        seen[key] = seen.get(key, 0) + 1
    for r in rows:
        r["possible_duplicate"] = seen[(r["goal_id"], r["kind"], r["amount"], r["date"])] > 1
    return rows


RECENT_EVENTS = 10


def recent_progress_events(events: list[dict], limit: int = RECENT_EVENTS) -> list[dict]:
    """The "התקדמות אחרונה" list: the latest goal-progress events, newest first. Allow-list of the known goal-event kinds
    (``calc.EVENT_KINDS``), applied BEFORE the cut to ``limit``: any other kind (a balance snapshot, withdrawal, fee, transfer, or a deposit with no goal link ...)
    is never shown as progress and never pushes a real progress event out of the list. Fail-closed for kinds added later."""
    def kind_of(e: dict) -> str | None:
        k = (e.get("fields") or {}).get(FinEventFields.KIND)
        return k.get("name") if isinstance(k, dict) else k

    shown = [e for e in events if kind_of(e) in calc.EVENT_KINDS and not _is_import(e)           # a statement import is not goal progress (hundreds of rows)
             and (kind_of(e) != calc.DEPOSIT or _goal_ids_of(e))]       # an account deposit is goal progress only when linked to a goal
    shown.sort(key=lambda e: str((e.get("fields") or {}).get(FinEventFields.OCCURRED_AT) or ""), reverse=True)
    return [{"goal_ids": _goal_ids_of(e), **{k: (e.get("fields") or {}).get(k) for k in (
        FinEventFields.AMOUNT, FinEventFields.KIND, FinEventFields.OCCURRED_AT, FinEventFields.NOTE)}} for e in shown[:limit]]


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


def savings_history_view(goals: list[dict], own: dict[str, list[calc.Event]], active_ids: set[str], today: date) -> dict | None:
    """Self-reported deposit history of the single long-term destination goal vs the standing level of the active savings
    goal(s). None when there is no unambiguous destination. Pure derivation from existing events — nothing is written."""
    dests = [g for g in goals if g["id"] in active_ids
             and _raw_category((g.get("fields") or {}).get(FinGoalFields.CATEGORY)) == SAVINGS_DESTINATION_CATEGORY]
    if len(dests) != 1:
        return None
    plan: list[calc.Event] = []
    for g in goals:
        if g["id"] in active_ids and _category_key((g.get("fields") or {}).get(FinGoalFields.CATEGORY)) == "savings":
            plan.extend(own.get(g["id"], []))
    return calc.deposit_history(own.get(dests[0]["id"], []), plan, today)


def _own_accounts_data(identity):
    """The caller's own account rows and events (both through the owner-scoped policy) + the resolved actor + the pure accounts module.
    Shared by the read-only accounts view and the pace inputs. An unresolved identity raises PersonalDataAccessDenied."""
    from core.financial_control import accounts as fcc_accounts
    mine = policy.filter_records(Tables.FIN_ACCOUNTS, _read(Tables.FIN_ACCOUNTS), identity)
    events = my_events(identity)
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        raise policy.PersonalDataAccessDenied(policy.UNRESOLVED_MESSAGE)
    return fcc_accounts, mine, events, actor


def accounts_view(identity, today: date | None = None) -> dict:
    """The "החשבונות" tab (D1 step 7 / B1): the caller's own financial accounts + the consolidated value, read-only.
    Both tables go through the owner-scoped policy (``filter_records``); ``accounts_overview`` additionally filters on the
    resolved owner (defence in depth). Nothing is written. An unresolved identity raises PersonalDataAccessDenied."""
    today = today or date.today()
    fcc_accounts, mine, events, actor = _own_accounts_data(identity)
    return fcc_accounts.accounts_overview(mine, events, today, owner_id=actor.profile_id)


def pace_inputs(identity, today: date | None = None) -> dict:
    """C4 (actual accumulation pace vs plan): everything the pure pace tracker needs, from the caller's OWN rows only. Read-only (nothing
    here writes). Accounts and events go through the owner-scoped policy (an unresolved identity raises PersonalDataAccessDenied); the goal-level
    deposit history is the existing ``savings_history_view`` derivation (self-reported, nothing stored)."""
    today = today or date.today()
    fcc_accounts, mine, events, actor = _own_accounts_data(identity)
    overview_rows = fcc_accounts.accounts_overview(mine, events, today, owner_id=actor.profile_id)
    goals = my_goals(identity)
    by_goal: dict[str, list[dict]] = {}
    for ev in events:
        for gid in _goal_ids_of(ev):
            by_goal.setdefault(gid, []).append(ev)
    active_ids = {g["id"] for g in goals if str((g.get("fields") or {}).get(FinGoalFields.STATUS) or "active").lower() in ("active", "פעיל")}
    own = {g["id"]: calc.parse_events(by_goal.get(g["id"], []), FinEventFields) for g in goals}
    return {
        "as_of": today.isoformat(),
        "accounts": [{k: r.get(k) for k in ("id", "name", "status", "planned_monthly_deposit", "expected_return_pct", "management_fee_pct")}
                     for r in overview_rows["accounts"]],
        "events": fcc_accounts.account_events(mine, events, owner_id=actor.profile_id),
        "skipped_events": overview_rows["skipped_events"],
        "savings_history": savings_history_view(goals, own, active_ids, today),
    }


def net_worth_view(identity, today: date | None = None) -> dict:
    """The unified net worth card (C2): accounts + assets − own debts, broken down, read-only. Every table goes through the
    owner-scoped policy; unlike the other tabs a read failure is NOT degraded to an empty section here (an empty loans list would
    silently inflate the net worth), so it propagates. Nothing is written. An unresolved identity raises PersonalDataAccessDenied."""
    from core.financial_control import net_worth as fcc_net_worth
    today = today or date.today()
    accounts = accounts_view(identity, today)
    assets = policy.filter_records("Assets", _read("Assets"), identity)
    loan_items = [fcc_loans.loan_item(r, today) for r in my_loans(identity)]
    return fcc_net_worth.net_worth(accounts, assets, loan_items, today)


def _raw_category(category) -> str | None:
    """The stored category key as written (select name or text), lower-cased; unlike ``_category_key`` it does not collapse to the summary families."""
    if isinstance(category, dict):
        category = category.get("name")
    return str(category or "").strip().casefold() or None


def goals_for_forecast(identity, today: date | None = None) -> list[dict]:
    """The caller's own goals, reduced to what the accounts forecast needs (A2): id, title, category, status, target amount, due date.
    Goes through the owner-scoped ``my_goals`` (unresolved identity -> PersonalDataAccessDenied). Read-only; no free text beyond the title.
    The target is the EFFECTIVE one — the latest ``target_change`` event on/before today wins over the base field, exactly as on the overview — so a
    goal whose target the owner changed (the base field keeps its first value, history stays in the events) is planned against its current target."""
    today = today or date.today()
    goals = my_goals(identity)
    by_goal: dict[str, list[dict]] = {}
    for ev in my_events(identity):
        for gid in _goal_ids_of(ev):
            by_goal.setdefault(gid, []).append(ev)
    out = []
    for g in goals:
        f = g.get("fields") or {}
        events = calc.parse_events(by_goal.get(g.get("id"), []), FinEventFields)
        out.append({
            "id": g.get("id"), "title": f.get(FinGoalFields.TITLE) or None, "category": _raw_category(f.get(FinGoalFields.CATEGORY)),
            "status": str(f.get(FinGoalFields.STATUS) or "active").lower(),
            "target_amount": calc.effective_target(calc._num(f.get(FinGoalFields.TARGET_AMOUNT)), [e for e in events if not e.superseded], today),
            "end_date": (calc._d(f.get(FinGoalFields.END_DATE)).isoformat() if calc._d(f.get(FinGoalFields.END_DATE)) else None),
            "date_margin_months": calc.date_margin_months(f.get(FinGoalFields.DATE_MARGIN)),
        })
    return out


def _single_link(value):
    """One linked record id, or None when the link is empty or holds several (a row that must not be guessed at)."""
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        return value[0]
    return None


def allocations_for_forecast(identity) -> list[dict]:
    """B2: the caller's own ``Goal Allocations`` rows, reduced to what the read model needs. Read-only (nothing here writes).
    Owner-scoped through the table policy (unresolved identity -> PersonalDataAccessDenied); the pure model then keeps only rows whose
    goal AND account are among the caller's own, so a link to someone else's record never contributes or leaks a name."""
    out = []
    for r in policy.filter_records(Tables.GOAL_ALLOCATIONS, _read(Tables.GOAL_ALLOCATIONS), identity):
        f = r.get("fields") or {}
        out.append({
            "id": r.get("id"), "goal_id": _single_link(f.get(GoalAllocationFields.GOAL)),
            "account_id": _single_link(f.get(GoalAllocationFields.ACCOUNT)),
            "mode": str(f.get(GoalAllocationFields.MODE) or "").lower() or None,
            "percent": calc._num(f.get(GoalAllocationFields.PERCENT)), "amount": calc._num(f.get(GoalAllocationFields.AMOUNT)),
            "status": str(f.get(GoalAllocationFields.STATUS) or "").lower() or None,
            "effective_from": (calc._d(f.get(GoalAllocationFields.EFFECTIVE_FROM)).isoformat() if calc._d(f.get(GoalAllocationFields.EFFECTIVE_FROM)) else None),
        })
    return out


def funding_inputs(identity, today: date | None = None) -> dict:
    """Goal Funding Planner (step 1): everything the pure planner needs, from the caller's OWN rows only. Read-only (nothing here writes);
    every read goes through the owner-scoped readers above, so an unresolved identity raises PersonalDataAccessDenied and another person's
    goals, accounts, loans, assets or obligations never reach the planner."""
    today = today or date.today()
    ov = overview(identity, today, default_method=calc.CUMULATIVE)       # a goal saved without a Calc Method is a cumulative pot for funding (never period_sum)
    summary = ov.get("summary") or {}
    income, savings = summary.get("income") or {}, summary.get("savings") or {}
    return {
        "goals": goals_for_forecast(identity, today), "accounts_view": accounts_view(identity, today), "allocations": allocations_for_forecast(identity),
        "goal_rows": [{k: r.get(k) for k in ("goal_id", "parent_id", "method", "net", "actual", "remaining", "status")} for r in ov.get("goals") or []],
        "loans": (ov.get("loans") or {}).get("items") or [], "assets": (ov.get("assets") or {}).get("items") or [],
        "obligations": ov.get("obligations"),
        "income": {k: income.get(k) for k in ("target", "actual", "remaining")} if income else None,
        "savings_plan": {k: savings.get(k) for k in ("target", "actual")} if savings else {},
        "savings_release": ov.get("savings_release"), "monthly_cash_improvement": ov.get("monthly_cash_improvement"),
        "saved_plans": chosen_plan_snapshots_for_funding(identity),
    }


# ── Cashflow rules (the owner's own "this description means this" rules; bank / card import) ──────────────────────────
def my_cashflow_rules(identity) -> list[dict]:
    """The caller's own Cashflow Rules rows (owner-scoped; a denied identity propagates)."""
    return policy.filter_records(Tables.CASHFLOW_RULES, _read(Tables.CASHFLOW_RULES), identity)


def cashflow_rule_items(records: list[dict], applies_to: str | None = None) -> list[dict]:
    """Rule rows -> the items ``bank_import.owner_rules_from`` reads. Only DECIDED rules count: an empty Kind (a description still waiting for the
    owner), ``Status = pending`` / ``disabled`` and a row with neither a Match nor a Row Key are skipped, never guessed. ``applies_to`` ("bank" |
    "card") keeps the rules of that source and the ones for "any" (an empty value counts as "any")."""
    F = CashflowRuleFields
    items: list[dict] = []
    for rec in records:
        f = rec.get("fields") or {}
        kind, status = _sel(f.get(F.KIND)), _sel(f.get(F.STATUS))
        scope = _sel(f.get(F.APPLIES_TO)) or "any"
        if not kind or status in ("pending", "disabled") or (applies_to and scope not in ("any", applies_to)):
            continue
        direction = _sel(f.get(F.DIRECTION))
        item = {"kind": kind, "category": str(f.get(F.CATEGORY) or "").strip() or None, "direction": None if direction in (None, "", "any") else direction}
        key = str(f.get(F.ROW_KEY) or "").strip()
        if key:
            item["key"] = key
        else:
            item["match"] = str(f.get(F.MATCH) or "").strip()
        if item.get("match") or item.get("key"):
            items.append(item)
    return items


def cashflow_rules(identity, applies_to: str | None = None) -> list:
    """The caller's decided rules as ``bank_import`` rules (the owner's rules win over the built-in ones). A read failure is an error here, not an
    empty list: importing with the owner's rules silently missing would classify the owner's own descriptions wrongly."""
    from core.financial_control import bank_import  # noqa: PLC0415 — pure module
    return bank_import.owner_rules_from(cashflow_rule_items(my_cashflow_rules(identity), applies_to))


# ── Monthly cashflow (income by source vs. expenses by category) — read-only ─────────────────────────────────────────
_SOURCE_NOTE = re.compile(r"^\s*מקור\s*:\s*(.+?)\s*$")        # an income booked on the total goal as "מקור אחר": the name is in the note


def _event_txn(ev: dict, category: str | None = None, signed: bool = False, basis: str = "billing") -> fcc_cashflow.Txn | None:
    """``signed``: an expense keeps its sign (an imported refund is a negative expense); income and direct costs are always positive.
    ``basis``: "billing" (the cashflow tab: a card row counts on its statement's billing date when it has one) or "occurred" (the consumption
    tab: the day of the purchase; an instalment, a loan and a card fee are dated by their billing in ``Occurred At`` already)."""
    f = ev.get("fields") or {}
    day, amount = calc._d(f.get(FinEventFields.OCCURRED_AT)), calc._num(f.get(FinEventFields.AMOUNT))
    if basis == "billing":
        day = calc._d(f.get(FinEventFields.BILLING_DATE)) or day
    if day is None or amount is None or f.get(FinEventFields.SUPERSEDED_BY):
        return None
    return fcc_cashflow.Txn(amount if signed else abs(amount), day, category, ev.get("id"), str(f.get(FinEventFields.NOTE) or "").strip())





def rule_change_for(chosen: dict, category: str, rule_rows: list[dict]) -> dict | None:
    """The ONE write that makes the owner's classification of an imported expense permanent: patch the rule row that already carries this description
    (pending, or decided with another category — the owner changed his mind) or create a decided rule when there is none. None when the existing rule
    already says exactly this. Pure over its arguments; ``chosen`` is a ``classify_waiting`` item."""
    from core.financial_control import bank_import as bi  # noqa: PLC0415
    F = CashflowRuleFields
    group = chosen.get("group") or bi.normalize(chosen.get("label") or "")
    if not group:
        return None
    for rec in rule_rows:
        f = rec.get("fields") or {}
        if f.get(F.ROW_KEY) or bi.normalize(str(f.get(F.MATCH) or "")) != group or str(_sel(f.get(F.DIRECTION)) or "debit") not in ("debit", "any"):
            continue
        if str(_sel(f.get(F.STATUS)) or "") == "active" and _sel(f.get(F.KIND)) == "expense" and str(f.get(F.CATEGORY) or "") == category:
            return None
        if str(_sel(f.get(F.STATUS)) or "") in ("pending", "active") and _sel(f.get(F.KIND)) in (None, "expense"):
            return {"op": "patch", "table": Tables.CASHFLOW_RULES, "record_id": rec.get("id"), "fields": {F.KIND: "expense", F.CATEGORY: category, F.STATUS: "active"},
                    "audit_action": "fcc_classify_rule", "audit_details": str(rec.get("id"))}
    from core.financial_control import import_plan as ip  # noqa: PLC0415
    return {"op": "post", "table": Tables.CASHFLOW_RULES,
            "fields": {F.MATCH: ip.mask_numbers(chosen.get("label") or "")[:200], F.APPLIES_TO: chosen["source"], F.DIRECTION: "debit", F.KIND: "expense", F.CATEGORY: category,
                       F.STATUS: "active"}, "audit_action": "fcc_rule_from_classification", "audit_details": group[:100]}


def rules_waiting(identity) -> list[dict]:
    """The caller's DESCRIPTIONS still waiting for a decision (``Cashflow Rules`` rows, Status pending, no Kind): expenses only — a credit is never
    classified here (income needs the owner's explicit approval) and a row-key rule (a transfer to check one by one) is not a description."""
    F = CashflowRuleFields
    out = []
    for rec in my_cashflow_rules(identity):
        f = rec.get("fields") or {}
        match = str(f.get(F.MATCH) or "").strip()
        if (not match or f.get(F.ROW_KEY) or str(_sel(f.get(F.STATUS)) or "") != "pending" or _sel(f.get(F.KIND))
                or str(_sel(f.get(F.DIRECTION)) or "") != "debit"):
            continue
        out.append({"id": rec.get("id"), "match": match, "applies_to": str(_sel(f.get(F.APPLIES_TO)) or "any"),
                    "times_seen": int(calc._num(f.get(F.TIMES_SEEN)) or 1), "amount": round(calc._num(f.get(F.EXAMPLE_AMOUNT)) or 0.0, 2),
                    "last_seen": str(f.get(F.LAST_SEEN) or "")})
    return out


def rules_view(waiting: list[dict], skip: frozenset[str] = frozenset()) -> dict:
    """Pure: the count and the NEXT description (the most seen, then the largest amount, not skipped)."""
    pool = sorted((w for w in waiting if w["id"] not in skip), key=lambda w: (-w["times_seen"], -w["amount"], w["match"]))
    return {"total": len(waiting), "item": pool[0] if pool else None}


def classify_waiting(identity) -> list[dict]:
    """The caller's expenses that still have NO category — imported ones and manually recorded ones — for the one-by-one screen. Owner-scoped
    (``my_events``). A manual entry has no meaningful description and is never grouped with another."""
    from core.financial_control import bank_import as bi  # noqa: PLC0415
    F = FinEventFields
    waiting = []
    for ev in my_events(identity) + my_events(identity, "only"):
        f = ev.get("fields") or {}
        amount, day = calc._num(f.get(F.AMOUNT)), calc._d(f.get(F.OCCURRED_AT))
        if (_sel(f.get(F.KIND)) != "household_expense" or f.get(F.SUPERSEDED_BY) or amount is None or day is None
                or fcc_cashflow.category_key(_sel(f.get(F.EXPENSE_CATEGORY))) != fcc_cashflow.UNCATEGORIZED):
            continue
        source = str(_sel(f.get(F.SOURCE)) or "")
        kind = "card" if source == "import:card" else "bank" if source == "import:bank" else "manual"
        label = str(f.get(F.RAW_TEXT) or "").strip() if kind != "manual" else ""
        waiting.append({"id": ev.get("id"), "date": day.isoformat(), "amount": round(amount, 2), "label": label or "הוצאה שנרשמה ידנית",
                        "source": kind, "group": bi.normalize(label) if label else ""})
    return waiting


def classify_view(waiting: list[dict], skip: frozenset[str] = frozenset()) -> dict:
    """Pure: what the screen shows — the count / sum still waiting and the NEXT one (the largest amount not skipped; ``same_count`` = the other waiting
    rows with the same description, so one answer can cover them)."""
    groups: dict[str, int] = {}
    for w in waiting:
        groups[w["group"]] = groups.get(w["group"], 0) + 1
    pool = sorted((w for w in waiting if w["id"] not in skip), key=lambda w: (-abs(w["amount"]), w["date"], w["id"] or ""))
    item = None
    if pool:
        w = pool[0]
        item = {"id": w["id"], "date": w["date"], "amount": w["amount"], "label": w["label"], "source": w["source"], "same_count": groups[w["group"]] - 1 if w["group"] else 0}
    return {"total": len(waiting), "total_amount": round(sum(w["amount"] for w in waiting), 2), "item": item}


def cashflow_inputs(goals: list[dict], events: list[dict], today: date, basis: str = "billing") -> tuple[list[fcc_cashflow.IncomeSource], list[fcc_cashflow.Txn]]:
    """Owner-scoped goals + events (already policy-filtered by the caller) -> cashflow model inputs. Pure over its arguments.

    * income goals: a source goal (it has a parent) or a goal with no sources of its own is a source by its title; the events booked
      directly on a TOTAL goal that has sources are "כללי" unless the note names the source (``מקור: <שם>``);
    * ``fixed_income`` goals are standing monthly sources at their effective target (a recorded entry replaces it, never adds);
    * expenses are the ``household_expense`` events with their ``Expense Category`` (empty = uncategorized)."""
    by_goal: dict[str, list[dict]] = {}
    for ev in events:
        for gid in _goal_ids_of(ev):
            by_goal.setdefault(gid, []).append(ev)
    parents = {calc.parent_goal_id(g.get("fields") or {}, FinGoalFields) for g in goals} - {None}

    gross: dict[str, list] = {}
    costs: dict[str, list] = {}
    kinds: dict[str, str] = {}
    standing: dict[str, tuple[float, date | None]] = {}

    def add(name: str, kind: str, bucket: dict, txn):
        kinds.setdefault(name, kind)
        bucket.setdefault(name, []).append(txn)

    for g in goals:
        gf = g.get("fields") or {}
        fixed_goal = _raw_category(gf.get(FinGoalFields.CATEGORY)) == FIXED_INCOME_CATEGORY
        income_goal = _category_key(gf.get(FinGoalFields.CATEGORY)) == "income"
        title = str(gf.get(FinGoalFields.TITLE) or "").strip() or fcc_cashflow.GENERAL_SOURCE
        mine = by_goal.get(g["id"], [])
        if fixed_goal:
            base = calc._num(gf.get(FinGoalFields.TARGET_AMOUNT))
            target = calc.effective_target(base, calc.parse_events(mine, FinEventFields), today)
            if target:
                standing[title] = (float(target), calc._d(gf.get(FinGoalFields.START_DATE)))
            kinds.setdefault(title, fcc_cashflow.FIXED)
        elif not income_goal:
            continue
        is_total = g["id"] in parents
        for ev in mine:
            kind = _sel((ev.get("fields") or {}).get(FinEventFields.KIND))
            if kind not in (calc.ONE_TIME, calc.DIRECT_COST):
                continue
            txn = _event_txn(ev)
            if txn is None:
                continue
            name, skind = title, (fcc_cashflow.FIXED if fixed_goal else fcc_cashflow.VARIABLE)
            if is_total:
                m = _SOURCE_NOTE.match(txn.label or "")
                name, skind = (m.group(1), fcc_cashflow.VARIABLE) if m else (fcc_cashflow.GENERAL_SOURCE, fcc_cashflow.GENERAL)
            add(name, skind, gross if kind == calc.ONE_TIME else costs, txn)

    for ev in events:                                          # income imported from a statement: no goal, the source name in the note ("מקור: <שם>")
        if _goal_ids_of(ev) or not _is_import(ev) or _sel((ev.get("fields") or {}).get(FinEventFields.KIND)) != calc.ONE_TIME:
            continue
        txn, m = _event_txn(ev), None
        m = _SOURCE_NOTE.match(txn.label or "") if txn else None
        if txn and m:
            add(m.group(1), fcc_cashflow.VARIABLE, gross, txn)

    sources = []
    for name in sorted(set(gross) | set(costs) | set(standing), key=lambda n: (kinds.get(n) != fcc_cashflow.FIXED, n)):
        fixed = standing.get(name)
        sources.append(fcc_cashflow.IncomeSource(
            name, kinds.get(name, fcc_cashflow.VARIABLE), tuple(gross.get(name, ())), tuple(costs.get(name, ())),
            fixed[0] if fixed else None, fixed[1] if fixed else None))

    expenses = []
    for ev in events:
        f = ev.get("fields") or {}
        if _sel(f.get(FinEventFields.KIND)) != calc.HOUSEHOLD_EXPENSE:
            continue
        category = _sel(f.get(FinEventFields.EXPENSE_CATEGORY))
        if _is_import(ev) and fcc_cashflow.category_key(category) == fcc_cashflow.LOANS:
            continue                                         # an imported loan row (written before loans stopped being imported) is ignored: the loans tab holds the exact amounts
        txn = _event_txn(ev, category, signed=True, basis=basis)
        if txn is not None:
            expenses.append(txn)
    return sources, expenses


def loans_by_month(identity, today: date, months: int) -> tuple[dict[str, float] | None, list[str], list[str]]:
    """The loans tab's monthly cost for each month of the window (``fcc_loans.monthly_schedule``). A read failure is None = unknown (never a guess); a denied
    identity propagates."""
    try:
        windows = fcc_cashflow.month_windows(today, months)
        return fcc_loans.monthly_schedule(my_loans(identity), windows, today)
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] loans schedule read failed")
        return None, [], []


def cashflow_view(identity, today: date | None = None, months: int = 6) -> dict:
    """The owner's monthly cashflow. Owner-scoped reads only; a denied identity propagates. A loans read failure degrades to "no scheduled
    payment" (never to a guessed one)."""
    today = today or date.today()
    window_start = fcc_cashflow.month_windows(today, months)[0][1]
    goals, events = my_goals(identity), my_events(identity) + my_events(identity, "only", window_start)
    sources, expenses = cashflow_inputs(goals, events, today)
    by_month, undated, closed_undated = loans_by_month(identity, today, months)
    commitments = None                                       # unknown (a failed read) is not "no commitments"
    try:
        commitments = commitment_rows(my_obligations(identity))
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] cashflow commitments read failed")
    view = fcc_cashflow.build(sources, expenses, today, months, None, commitments, by_month)
    view["loans_payments_known"] = by_month is not None
    view["loans_undated"] = undated[:5]                                   # loans with no start date: counted in the current month only
    view["loans_closed_undated"] = closed_undated[:5]                      # closed loans with no end date: not counted
    try:                                                      # the entry to the one-by-one classification screen (None = unknown, never "nothing waiting")
        queue = classify_view(classify_waiting(identity))
        view["to_classify"] = {"total": queue["total"], "total_amount": queue["total_amount"]}
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] cashflow classify queue read failed")
        view["to_classify"] = None
    try:
        view["rules_to_classify"] = {"total": len(rules_waiting(identity))}
    except policy.PersonalDataAccessDenied:
        raise
    except Exception:
        logger.exception("[fcc] cashflow pending rules read failed")
        view["rules_to_classify"] = None
    return view


_BILLING_LOOKBACK_DAYS = 45          # how far before the month an imported card row's purchase can lie and still be billed in it


def month_summary(goals: list[dict], events: list[dict], today: date, loans_by_month_: dict[str, float] | None) -> dict | None:
    """The CURRENT month's bottom line for the monthly-conduct tab: income (net), expenses and what is left for saving — the SAME numbers as the cashflow tab
    (card rows by their billing date; the scheduled loan payment only when no loan charge was recorded). None when it cannot be derived (never a guess)."""
    try:
        sources, expenses = cashflow_inputs(goals, events, today)
        m = fcc_cashflow.build(sources, expenses, today, 1, None, None, loans_by_month_)["months"][-1]
        return {"month": m["month"], "partial": m["partial"], "day": m["day"], "days_in_month": m["days_in_month"],
                "income": m["income"]["net"], "expenses": m["expenses"]["total"], "balance": m["balance"],
                "surplus": m["surplus"], "shortfall": m["shortfall"], "missing": m["missing"]}
    except Exception:                                        # noqa: BLE001 — the monthly screen must load without it
        logger.exception("[fcc] month summary failed")
        return None


def consumption_view(identity, today: date | None = None, months: int = 6) -> dict:
    """When the money was CONSUMED (the owner's "צריכה" tab): expenses by category per month by the day of the purchase, never loans (a loan is a business
    decision taken when it was taken, not monthly consumption). A purchase paid in instalments counts on each payment's billing month and is also summed
    apart (``installments``). Insights only (changes, spikes, large items) — the gap / surplus and the commitments belong to the cashflow tab."""
    from core.financial_control import import_plan as ip  # noqa: PLC0415
    today = today or date.today()
    window_start = fcc_cashflow.month_windows(today, months)[0][1]
    goals, events = my_goals(identity), my_events(identity) + my_events(identity, "only", window_start)
    _, expenses = cashflow_inputs(goals, events, today, basis="occurred")
    expenses = [t for t in expenses if fcc_cashflow.category_key(t.category) != fcc_cashflow.LOANS]
    view = fcc_cashflow.build([], expenses, today, months)
    inst: dict[str, float] = {}
    for t in expenses:
        if t.label == ip.INSTALMENTS_NOTE and t.amount > 0:
            key = f"{t.occurred.year:04d}-{t.occurred.month:02d}"
            inst[key] = round(inst.get(key, 0.0) + t.amount, 2)
    rows = [{"month": r["month"], "is_current": r["is_current"], "partial": r["partial"], "expenses": r["expenses"], "installments": inst.get(r["month"], 0.0)}
            for r in view["months"]]
    return {"months": rows, "insights": view["insights"], "categories": view["categories"], "as_of": view["as_of"]}


def overview(identity, today: date | None = None, default_method: str | None = None) -> dict:
    """Private screen payload: goals with derived numbers + monthly cash improvement. ``default_method`` (funding planner only) is the Calc Method
    assumed for a goal whose own field is empty; None keeps ``calc.compute_goal``'s default (period_sum) for every other screen."""
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
    imported = my_events(identity, "only", today.replace(day=1) - timedelta(days=_BILLING_LOOKBACK_DAYS))      # a card row bought last month can be BILLED this month
    all_events.extend(calc.parse_events(imported, FinEventFields))                           # imported rows have no goal; the household card still counts the month's
    for goal in goals:
        all_events.extend(own[goal["id"]])
        if goal["id"] not in active_ids:
            continue
        gf = goal.get("fields") or {}
        # parent goal = its own events + every descendant source's events, each event once (roll-up)
        if default_method and not gf.get(FinGoalFields.CALC_METHOD) and _cumulative_by_default(gf.get(FinGoalFields.CATEGORY)):
            goal = {**goal, "fields": {**gf, FinGoalFields.CALC_METHOD: default_method}}
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
        "savings_history": savings_history_view(goals, own, active_ids, today),
        "loans": loans_payload,
        "assets": assets_overview(identity, loans_payload["items"]),
        "recent_incomes": recent_incomes(goals, events),
        "household": {"month_total": calc.household_month_total(all_events, today)},
        "month_summary": month_summary(goals, events + imported, today, loans_by_month(identity, today, 1)[0]),
        "receipts": receipts_overview(identity),
        "obligations": obligations_overview(identity),
        "tasks": tasks,
        "monthly_cash_improvement": calc.monthly_cash_improvement(all_events, today),
        "recent_events": recent_progress_events(events),
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
