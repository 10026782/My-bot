"""מתכנן מימון יעד (שלב 1, `GOAL_FUNDING_PLANNER_SPEC.md`) — שכבת הרכבה טהורה: ללא I/O, Airtable, LLM או כתיבה.

יעד (סכום + תאריך) -> צורך -> השוואה בין אפשרויות מימון. אין המלצה, אין ציון, אין דירוג, אין שדה `total_available`:
כל אפשרות מחזירה סכום, מועד זמינות, רמת ודאות (`confirmed` / `expected` / `uncertain` / `unknown`, מיפוי דטרמיניסטי), תנאים למימוש,
השפעה על התזרים החודשי, התחייבויות חדשות, עלות כוללת וסיכונים. "צפוי" לעולם אינו מוצג כ"קיים": הכיסוי של תוכנית מפוצל לפי ודאות.

הצורך מחושב לפי הכסף **המאושר** בלבד (`gap = target - confirmed`); כסף צפוי מוצג בנפרד ואינו מקטין את גודל האפשרויות.
בלי מודל מס, בלי כללי הלוואה/הצמדה, בלי ביצוע. המנוע (`portfolio_lab.engine.simulate`) לא משתנה; כל מספר שהוזן מסומן `owner_entered`.
"""

from __future__ import annotations

import calendar
import math
import re
from datetime import date

from core.financial_control import loans as fcc_loans

from . import accounts_forecast as af
from .engine import simulate
from .models import Asset, Scenario

FUNDING_SCHEMA_VERSION = "1.0"
OPTION_TYPES = ("existing_balance", "new_deposits", "asset_sale", "loan", "work_income", "receivable_collection", "obligations_reduction", "custom")
CERTAINTIES = ("confirmed", "expected", "uncertain", "unknown")
_MAX_GOALS, _MAX_OPTIONS, _MAX_PLAN = 10, 20, 60
_MAX_MARGIN_MONTHS = 60
_MAX_MONEY = 10_000_000_000.0
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_REC = re.compile(r"^rec[A-Za-z0-9]{1,37}$")
_MAX_MONTHS = 100 * 12
_BISECT_ITERATIONS, _DOUBLINGS, _TOLERANCE = 60, 40, 0.005

_ALLOWED = {
    "existing_balance": set(),
    "new_deposits": {"account_id", "hypothetical", "release_confirmed"},
    "asset_sale": {"asset_id", "net_proceeds", "expected_date", "confirmed_buyer"},
    "loan": {"amount", "annual_rate_pct", "term_months", "available_by", "collateral", "approved", "terms_verified"},
    "work_income": {"based_on"},
    "receivable_collection": {"loan_id", "expected_net", "expected_date"},
    "obligations_reduction": {"monthly_amount"},
    "custom": {"label", "amount", "available_by", "monthly_cost", "one_time_cost", "certainty"},
}
_HYPOTHETICAL = {"expected_return_pct", "fee_pct", "deposit_fee_pct", "immediate", "liquid_from"}


# ── קלט ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def _money(value, name, *, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 or (value == 0 and not allow_zero) or value > _MAX_MONEY:
        raise ValueError(f"{name} must be {'zero or ' if allow_zero else ''}positive and at most {int(_MAX_MONEY)}")
    return float(value)


def _date(value, name, *, required=True):
    if value is None and not required:
        return None
    parsed = af._iso_date(value) if isinstance(value, str) else None
    if parsed is None:
        raise ValueError(f"{name} must be an ISO date")
    return parsed


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false")
    return value


def _normalize_option(raw, index: int) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("each option must be an object")
    kind = raw.get("type")
    if kind not in OPTION_TYPES or kind == "existing_balance":
        raise ValueError(f"option type must be one of: {', '.join(t for t in OPTION_TYPES if t != 'existing_balance')} (existing_balance is automatic)")
    extra = set(raw) - {"id", "type"} - _ALLOWED[kind]
    if extra:
        raise ValueError(f"unknown option fields: {', '.join(sorted(extra))}")
    option_id = raw.get("id", f"{kind}_{index + 1}")
    if not isinstance(option_id, str) or not _ID.match(option_id) or option_id == "existing_balance":
        raise ValueError("option id must be a short identifier")
    out: dict = {"id": option_id, "type": kind}
    if kind == "new_deposits":
        account_id, hypo = raw.get("account_id"), raw.get("hypothetical")
        if (account_id is None) == (hypo is None):
            raise ValueError("new_deposits needs exactly one of account_id or hypothetical")
        if account_id is not None:
            if not isinstance(account_id, str) or not _REC.match(account_id):
                raise ValueError("account_id must be an account id")
            out["account_id"] = account_id
        else:
            if not isinstance(hypo, dict) or set(hypo) - _HYPOTHETICAL:
                raise ValueError("hypothetical has unknown fields")
            clean = {}
            for key, lo, hi in (("expected_return_pct", -50, 50), ("fee_pct", 0, 10), ("deposit_fee_pct", 0, 10)):
                if key in hypo:
                    clean[key] = af._number(hypo[key], key, lo, hi)
            if "immediate" in hypo:
                clean["immediate"] = _bool(hypo["immediate"], "immediate")
            if "liquid_from" in hypo:
                clean["liquid_from"] = _date(hypo["liquid_from"], "liquid_from")
            if clean.get("immediate") and "liquid_from" in clean:
                raise ValueError("hypothetical: immediate and liquid_from are exclusive")
            out["hypothetical"] = clean
        out["release_confirmed"] = _bool(raw.get("release_confirmed", False), "release_confirmed")
    elif kind == "asset_sale":
        if raw.get("asset_id") is not None:
            if not isinstance(raw["asset_id"], str) or not _REC.match(raw["asset_id"]):
                raise ValueError("asset_id must be an asset id")
            out["asset_id"] = raw["asset_id"]
        out["net_proceeds"] = _money(raw.get("net_proceeds"), "net_proceeds")
        out["expected_date"] = _date(raw.get("expected_date"), "expected_date")
        out["confirmed_buyer"] = _bool(raw.get("confirmed_buyer", False), "confirmed_buyer")
    elif kind == "loan":
        out["amount"] = _money(raw.get("amount"), "amount")
        out["annual_rate_pct"] = af._number(raw.get("annual_rate_pct"), "annual_rate_pct", 0, 100)
        months = raw.get("term_months")
        if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= 600:
            raise ValueError("term_months must be an integer from 1 to 600")
        out["term_months"] = months
        out["available_by"] = _date(raw.get("available_by"), "available_by")
        collateral = raw.get("collateral")
        if collateral is not None and (not isinstance(collateral, str) or len(collateral) > 60):
            raise ValueError("collateral must be a short text")
        out["collateral"] = collateral
        out["approved"] = _bool(raw.get("approved", False), "approved")
        out["terms_verified"] = _bool(raw.get("terms_verified", False), "terms_verified")
    elif kind == "work_income":
        based_on = raw.get("based_on")
        if based_on is not None and (not isinstance(based_on, str) or not _ID.match(based_on)):
            raise ValueError("based_on must be an option id")
        out["based_on"] = based_on
    elif kind == "receivable_collection":
        if not isinstance(raw.get("loan_id"), str) or not _REC.match(raw["loan_id"]):
            raise ValueError("loan_id must be a loan id")
        out["loan_id"] = raw["loan_id"]
        out["expected_net"] = _money(raw.get("expected_net"), "expected_net")
        out["expected_date"] = _date(raw.get("expected_date"), "expected_date")
    elif kind == "obligations_reduction":
        out["monthly_amount"] = None if raw.get("monthly_amount") is None else _money(raw["monthly_amount"], "monthly_amount")
    elif kind == "custom":
        label = raw.get("label")
        if not isinstance(label, str) or not 0 < len(label.strip()) <= 60:
            raise ValueError("label must be a short text")
        out["label"] = label.strip()
        out["amount"] = _money(raw.get("amount"), "amount")
        out["available_by"] = _date(raw.get("available_by"), "available_by", required=False)
        out["monthly_cost"] = _money(raw.get("monthly_cost", 0), "monthly_cost", allow_zero=True)
        out["one_time_cost"] = _money(raw.get("one_time_cost", 0), "one_time_cost", allow_zero=True)
        certainty = raw.get("certainty")
        if certainty is not None and certainty not in ("expected", "uncertain"):
            raise ValueError("custom certainty must be expected or uncertain")
        out["certainty"] = certainty
    return out


def normalize_request(body) -> dict:
    """גוף הבקשה הגולמי -> קלט מנורמל; ValueError על קלט לא תקף. מזהי הרשומות נבדקים מול הנתונים של הבעלים ב-`build_funding_plan`."""
    if not isinstance(body, dict):
        raise ValueError("body must be an object")
    unknown = set(body) - {"goal_id", "goal_ids", "assumptions", "options", "allocation_plan", "date_margin_months", "card_monthly", "from_existing", "schedule", "schedule_goal_ids"}
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    goal_ids = body.get("goal_ids")
    if body.get("goal_id") is not None:
        if goal_ids is not None:
            raise ValueError("send goal_id or goal_ids, not both")
        goal_ids = [body["goal_id"]]
    if not isinstance(goal_ids, list) or not 1 <= len(goal_ids) <= _MAX_GOALS or len(set(map(str, goal_ids))) != len(goal_ids):
        raise ValueError(f"goal_ids must list 1 to {_MAX_GOALS} distinct goal ids")
    for gid in goal_ids:
        if not isinstance(gid, str) or not _REC.match(gid):
            raise ValueError("goal_ids must be goal ids")
    assumptions = body.get("assumptions", {})
    if not isinstance(assumptions, dict) or set(assumptions) - {"annual_return_pct", "annual_fee_pct", "inflation_pct"}:
        raise ValueError("assumptions has unknown fields")
    options_raw = body.get("options", [])
    if not isinstance(options_raw, list) or len(options_raw) > _MAX_OPTIONS:
        raise ValueError(f"options must be a list of at most {_MAX_OPTIONS}")
    options = [_normalize_option(o, i) for i, o in enumerate(options_raw)]
    if len({o["id"] for o in options}) != len(options):
        raise ValueError("option ids must be unique")
    plan_raw = body.get("allocation_plan", [])
    if not isinstance(plan_raw, list) or len(plan_raw) > _MAX_PLAN:
        raise ValueError(f"allocation_plan must be a list of at most {_MAX_PLAN}")
    plan = []
    for entry in plan_raw:
        if not isinstance(entry, dict) or set(entry) != {"goal_id", "option_id", "amount"}:
            raise ValueError("allocation_plan entries need goal_id, option_id and amount")
        if entry["goal_id"] not in goal_ids or entry["option_id"] not in {o["id"] for o in options}:
            raise ValueError("allocation_plan refers to an unknown goal or option")
        plan.append({"goal_id": entry["goal_id"], "option_id": entry["option_id"], "amount": _money(entry["amount"], "amount")})
    if len({(e["goal_id"], e["option_id"]) for e in plan}) != len(plan):
        raise ValueError("allocation_plan has a duplicate goal/option pair")
    margin = body.get("date_margin_months")
    if margin is not None and (isinstance(margin, bool) or not isinstance(margin, int) or not 0 <= margin <= _MAX_MARGIN_MONTHS):
        raise ValueError(f"date_margin_months must be a whole number of months 0 to {_MAX_MARGIN_MONTHS}")
    card_monthly = body.get("card_monthly")
    if card_monthly is not None:
        card_monthly = _money(card_monthly, "card_monthly")                         # a figure typed on the card: a positive amount per month, never inferred
    from_existing = body.get("from_existing")
    if from_existing is not None:
        from_existing = _money(from_existing, "from_existing")                       # route ד׳: how much of the deposit comes from existing deposits (a typed amount)
    schedule = body.get("schedule", False)
    if not isinstance(schedule, bool):
        raise ValueError("schedule must be true or false")
    schedule_ids = body.get("schedule_goal_ids")
    if schedule_ids is not None:
        if not isinstance(schedule_ids, list) or len(schedule_ids) > _MAX_GOALS or not all(isinstance(i, str) and _REC.match(i) for i in schedule_ids):
            raise ValueError(f"schedule_goal_ids must list at most {_MAX_GOALS} goal ids")
    return {"goal_ids": goal_ids, "assumptions": assumptions, "options": options, "allocation_plan": plan, "date_margin_months": margin,
            "card_monthly": card_monthly, "from_existing": from_existing, "schedule": schedule, "schedule_goal_ids": schedule_ids}


# ── עזרים ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def _compact_variant(plan: dict) -> dict:
    """One end of a date window: the goal's need and, per option, only the fields that move with the date (server numbers, no details)."""
    out = plan["goals"][0]
    need = out["need"]
    return {"due": need["due"], "reason": need["reason"], "gap": need.get("gap"), "months_to_due": need["months_to_due"],
            "required_card": out.get("required_monthly_card"),
            "options": [{k: o.get(k) for k in ("id", "type", "feasible", "reason", "covers_amount", "available_by", "monthly_cash_effect", "certainty",
                                               "time_to_realize_months")} | {"required_monthly": (o.get("details") or {}).get("required_monthly")}
                        for o in out.get("options") or []]}


def _date_window(inputs: dict, request: dict, goal: dict, margin: int, today: date) -> dict | None:
    """The goal's date is an ESTIMATE (± ``margin`` months): the same options recomputed at the early and the late end. The point estimate stays the
    main answer; the window only shows how much each option moves. Allocations are not carried into the variants."""
    due = af._iso_date(goal.get("end_date"))
    if due is None or margin <= 0:
        return None
    ends = {}
    for name, shift in (("early", -margin), ("late", margin)):
        moved = {**inputs, "goals": [{**g, "end_date": _add_months(due, shift).isoformat()} if g.get("id") == goal["id"] else g
                                     for g in inputs.get("goals") or []]}
        ends[name] = _compact_variant(build_funding_plan(moved, {**request, "goal_ids": [goal["id"]], "allocation_plan": [], "date_margin_months": 0},
                                                         today, _window_variant=True))
    return {"margin_months": margin, **ends,
            "note": "the date is an estimate: each end is the same options recomputed at the earliest / latest date; nothing here picks a date for you"}


def _slot(due: date, start: date) -> int | None:
    """סמנטיקת A2: הערך נקרא בסוף החודש האחרון שהושלם עד התאריך (0 = פתיחה)."""
    idx = _months_between(start, due)
    if idx < 0:
        return None
    return idx + 1 if due >= af._month_end(due) else idx


def _risks(*codes) -> list:
    return [c for c in codes if c]


def _result(option: dict, **fields) -> dict:
    base = {
        "id": option["id"], "type": option["type"], "feasible": "unknown", "reason": None, "covers_amount": None, "available_by": None,
        "monthly_cash_effect": None, "one_time_cost": None, "total_cost": None, "new_liabilities": None, "time_to_realize_months": None,
        "certainty": "unknown", "conditions": [], "risks": [], "assumptions": [], "missing_inputs": [], "provenance": {}, "details": {},
    }
    base.update(fields)
    return base


def _with_timing(result: dict, available_by: date | None, today: date) -> dict:
    if available_by is not None:
        result["available_by"] = available_by.isoformat()
        result["time_to_realize_months"] = max(_months_between(today, available_by), 0)
    return result


def _value_at(slot: int, monthly: float, *, years: int, annual_return: float, fee: float, deposit_fee_pct: float, p: dict, start: str) -> float:
    """ערך הכסף **החדש** (פתיחה 0) בסוף החודש ה-`slot`, לפי המנוע ללא שינוי."""
    result = simulate(Scenario(
        years=years, initial=0.0, monthly_contribution=monthly * (1 - deposit_fee_pct / 100), inflation=p["inflation"],
        deposit_timing=p["deposit_timing"], start_date=start, assets=(Asset(name="account", annual_return=annual_return, annual_fee=fee),)), monthly=True)
    return float(result["monthly"][slot - 1]["value_after_costs"])


def required_monthly(gap: float, slot: int, *, years: int, annual_return: float, fee: float, deposit_fee_pct: float, p: dict, start: str) -> float | None:
    """הפקדה חודשית נדרשת כך שערך הכסף החדש בסוף החודש ה-`slot` יגיע ל-`gap`; חיפוש בינארי דטרמיניסטי מעל המנוע. None = לא ניתן להשגה."""
    if gap <= 0:
        return 0.0
    if slot < 1:
        return None

    def value(c: float) -> float:
        return _value_at(slot, c, years=years, annual_return=annual_return, fee=fee, deposit_fee_pct=deposit_fee_pct, p=p, start=start)

    lo, hi = 0.0, max(gap / slot, 1.0)
    for _ in range(_DOUBLINGS):
        if value(hi) >= gap:
            break
        lo, hi = hi, hi * 2
    else:
        return None
    for _ in range(_BISECT_ITERATIONS):
        mid = (lo + hi) / 2
        if value(mid) >= gap:
            hi = mid
        else:
            lo = mid
        if hi - lo <= _TOLERANCE:
            break
    return math.ceil(hi * 100) / 100                # עיגול כלפי מעלה לאגורה: ההפקדה המוצגת תמיד מגיעה ליעד


# ── אפשרויות ──────────────────────────────────────────────────────────────────────────────────────────────────────

def _existing_balance(ctx: dict, goal: dict) -> dict:
    option = {"id": "existing_balance", "type": "existing_balance"}
    alloc, item = ctx["alloc_goals"].get(goal["id"]), ctx["forecast_goals"].get(goal["id"])
    events = goal.get("progress_events_actual")
    if alloc is None:
        res = _result(option, feasible="unknown", reason="no_allocation", missing_inputs=["goal_allocation"],
                      provenance={"basis": "none"})
        if item and item.get("accessible_value") is not None:
            res["details"]["potential_accessible_value"] = item["accessible_value"]            # מידע בלבד: כיסוי פוטנציאלי, לא הקצאה
            res["risks"] = _risks("allocated_elsewhere" if item.get("potential_caveat") == "allocated_elsewhere" else None)
        if goal.get("method") == "cumulative" and events:
            res.update(covers_amount=events, certainty="confirmed", feasible=True, reason=None,
                       provenance={"basis": "progress_events", "amount": "self_reported"}, risks=["self_reported_balance"])
            res["details"]["basis"] = "progress_events"
        return res
    now = float(alloc.get("accessible") or 0.0)
    reason = (item or {}).get("reason") if (item or {}).get("basis") == "allocation" else None
    res = _result(option, provenance={"basis": "allocation", "amount": "self_reported"}, risks=["self_reported_balance"])
    res["details"].update(basis="allocation", allocated_now=alloc.get("allocated"), accessible_now=now,
                          conditional_now=alloc.get("conditional"), locked_now=alloc.get("locked"))
    if alloc.get("status") != "ok":
        res.update(feasible=False, reason="over_allocated", covers_amount=0.0)
        res["risks"].append("over_committed_pool")
    elif reason in ("allocated_not_accessible", "allocation_not_yet_effective", "allocation_effective_after_due"):
        res.update(feasible=False, reason={"allocated_not_accessible": "not_accessible_by_due"}.get(reason, reason), covers_amount=0.0)
    elif item and item.get("basis") == "allocation" and item.get("accessible_value") is not None:
        projected = float(item["accessible_value"])
        confirmed = min(now, projected)
        res.update(feasible=True, covers_amount=round(projected, 2), certainty="confirmed" if confirmed >= projected - 0.005 else "expected")
        res["details"].update(confirmed_amount=round(confirmed, 2), expected_amount=round(max(projected - confirmed, 0.0), 2))
        if projected - confirmed > 0.005:
            res["conditions"].append("liquid_from_reached" if now < float(alloc.get("allocated") or 0.0) else "growth_as_assumed")
            res["risks"].append("depends_on_assumed_return")
    else:
        res.update(feasible="unknown", reason="no_coverage_basis", missing_inputs=["target_amount", "end_date"])
    if goal.get("progress_events_actual"):
        res["risks"].append("event_allocation_overlap")
        res["details"]["progress_events_actual"] = goal["progress_events_actual"]      # מידע בלבד, לא מתווסף
    return res


def _deposit_access(state: str, basis: str, release_confirmed: bool):
    """(feasible, reason) לפי A2: רק `immediate` נגיש; תאריך שחרור שהגיע הוא `conditional` — לא מסיקים זכאות, אלא אם הבעלים אישר את כללי השחרור."""
    if state == "accessible":
        return True, None
    if state == "conditional" and basis == "dated":
        return (True, None) if release_confirmed else ("unknown", "release_not_verified")
    if state == "conditional" and basis == "unverified":
        return "unknown", "liquidity_unverified"
    return False, "not_accessible_by_due"                    # נעול, חסר תאריך, או מוצר פרישה (לעולם לא כסכום חד־פעמי)


def _new_deposits(option: dict, ctx: dict, goal: dict) -> dict:
    today, p = ctx["today"], ctx["p"]
    slot, due = goal["slot"], goal["due"]
    res = _result(option, certainty="expected", conditions=["owner_confirms_deposits"], assumptions=["growth_as_assumed"],
                  risks=["depends_on_assumed_return"])
    if "account_id" in option:
        account = ctx["accounts"].get(option["account_id"])
        if account is None:
            raise ValueError("unknown account in options")
        inputs = af._account_inputs(account, p, {})
        profile = af._liquidity_profile(account)
        access, access_reason = _deposit_access(af._state_at(profile, due), profile["basis"], option["release_confirmed"])
        fee, annual_return, deposit_fee = inputs["fee"], inputs["annual_return"], inputs["deposit_fee"]
        res["missing_inputs"] = [m for m in inputs["missing"] if m in ("management_fee", "expected_return", "deposit_fee")]
        res["provenance"] = {"assumptions": "account" if inputs["return_source"] == "account" else "assumed"}
        res["details"]["account_id"] = account["id"]
        res["details"]["account_name"] = account.get("name")
    else:
        hypo = option["hypothetical"]
        fee = hypo.get("fee_pct", p["annual_fee"] * 100) / 100
        annual_return = hypo.get("expected_return_pct", p["annual_return"] * 100) / 100
        deposit_fee = hypo.get("deposit_fee_pct", 0.0)
        liquid_from = hypo.get("liquid_from")
        res["provenance"] = {"assumptions": "owner_entered"}
        res["details"]["hypothetical"] = True
        if hypo.get("immediate"):
            access, access_reason = True, None
        elif liquid_from is None:
            res["missing_inputs"].append("liquidity")
            res.update(feasible="unknown", reason="liquidity_unknown", certainty="unknown")
            return res
        else:
            access, access_reason = _deposit_access("conditional" if liquid_from <= due else "locked", "dated", option["release_confirmed"])
    if access is False:
        res.update(feasible=False, reason=access_reason, certainty="unknown")
        res["risks"].append("not_accessible_by_due")
        return res
    if access == "unknown":
        res["conditions"] = ["liquid_from_reached", "release_rules_confirmed"] if access_reason == "release_not_verified" else ["liquidity_verified"]
        res["risks"].append("release_not_verified")
    gap = goal["gap"]
    start = ctx["start"]
    monthly = required_monthly(gap, slot, years=ctx["years"], annual_return=annual_return, fee=fee, deposit_fee_pct=deposit_fee, p=p, start=start)
    if monthly is None:
        res.update(feasible=False, reason="unreachable_under_assumptions", certainty="unknown")
        res["risks"].append("unreachable_under_assumptions")
        return res
    with_fee = _value_at(slot, monthly, years=ctx["years"], annual_return=annual_return, fee=fee, deposit_fee_pct=deposit_fee, p=p, start=start)
    no_fee = _value_at(slot, monthly, years=ctx["years"], annual_return=annual_return, fee=0.0, deposit_fee_pct=deposit_fee, p=p, start=start)
    deposit_fees = monthly * deposit_fee / 100 * slot
    res.update(feasible=access, reason=access_reason if access == "unknown" else None, certainty="expected" if access is True else "uncertain",
               covers_amount=round(gap, 2), monthly_cash_effect=-monthly, total_cost=round(max(no_fee - with_fee, 0.0) + deposit_fees, 2))
    res["details"].update(required_monthly=monthly, deposit_months=slot, total_deposits=round(monthly * slot, 2),
                          annual_return_pct=round(annual_return * 100, 4), fee_pct=round(fee * 100, 4), deposit_fee_pct=deposit_fee)
    res["assumptions"].append("new money only (account's existing balance is not counted)")
    return _with_timing(res, due, today)


def _loan(option: dict, ctx: dict, goal: dict) -> dict:
    n, amount = option["term_months"], option["amount"]
    raw_payment = fcc_loans.pmt(amount, option["annual_rate_pct"], n)
    payment = round(raw_payment, 2)
    res = _result(option, covers_amount=amount, monthly_cash_effect=-payment, total_cost=round(raw_payment * n - amount, 2),
                  new_liabilities={"amount": amount, "monthly_payment": payment, "term_months": n},
                  certainty="expected" if option["approved"] else "uncertain", conditions=[] if option["approved"] else ["loan_approved"],
                  provenance={"terms": "owner_entered"}, risks=_risks(None if option["terms_verified"] else "terms_unverified",
                                                                      "collateral_growth_not_modeled" if option["collateral"] else None,
                                                                      None if option["approved"] else "timing_uncertain"))
    res["assumptions"].append("annual rate / 12, level instalment; no indexation, fees or early-repayment cost")
    res["details"].update(collateral=option["collateral"], approved=option["approved"])
    if option["available_by"] > goal["due"]:
        res.update(feasible=False, reason="available_after_due")
    else:
        res["feasible"] = True
    return _with_timing(res, option["available_by"], ctx["today"])


def _asset_sale(option: dict, ctx: dict, goal: dict) -> dict:
    res = _result(option, covers_amount=option["net_proceeds"], certainty="expected" if option["confirmed_buyer"] else "uncertain",
                  conditions=["sale_closes"] + ([] if option["confirmed_buyer"] else ["buyer_found"]),
                  provenance={"net_proceeds": "owner_entered"}, risks=[] if option["confirmed_buyer"] else ["timing_uncertain"])
    asset_id = option.get("asset_id")
    if asset_id is not None:
        asset = ctx["assets"].get(asset_id)
        if asset is None:
            raise ValueError("unknown asset in options")
        res["details"]["asset"] = {k: asset.get(k) for k in ("id", "name", "asset_type", "current_value", "ownership_pct", "mortgage_balance",
                                                              "monthly_income", "linked_debt", "linked_loans")}
        if (asset.get("mortgage_balance") or 0) > 0 or asset.get("linked_loans"):
            res["risks"].append("debt_overlap_unresolved")
        if (asset.get("monthly_income") or 0) > 0:
            res["risks"].append("lost_income")
            res["monthly_cash_effect"] = -float(asset["monthly_income"])
        res["assumptions"].append("net proceeds as entered; sale amount on record is gross and is not used")
    if option["expected_date"] > goal["due"]:
        res.update(feasible=False, reason="available_after_due")
    else:
        res["feasible"] = True
    return _with_timing(res, option["expected_date"], ctx["today"])


def _receivable(option: dict, ctx: dict, goal: dict) -> dict:
    loan = ctx["loans"].get(option["loan_id"])
    if loan is None or loan.get("direction") != fcc_loans.OWED_TO_ME or not loan.get("active"):
        raise ValueError("loan_id must be an active debt owed to you")
    arranged = loan.get("arrangement") is not None
    res = _result(option, covers_amount=option["expected_net"], certainty="expected" if arranged else "uncertain",
                  conditions=["debtor_arrangement"] if not arranged else ["debtor_pays_on_schedule"], provenance={"expected_net": "owner_entered"},
                  risks=_risks("timing_uncertain", None if arranged else "receivable_no_arrangement"))
    res["details"].update(loan_name=loan.get("name"), recorded_balance=loan.get("early_closure_balance"), arrangement=loan.get("arrangement"))
    res["assumptions"].append("collected money is not income and is not a liability of yours")
    if option["expected_date"] > goal["due"]:
        res.update(feasible=False, reason="available_after_due")
    else:
        res["feasible"] = True if arranged else "unknown"
        res["reason"] = None if arranged else "no_arrangement"
    return _with_timing(res, option["expected_date"], ctx["today"])


def _obligations(option: dict, ctx: dict, goal: dict) -> dict:
    owner_amount = option.get("monthly_amount")
    saving = owner_amount if owner_amount is not None else float((ctx["obligations"] or {}).get("potential_saving") or 0.0)
    res = _result(option, certainty="uncertain", conditions=["owner_confirms_savings"], risks=["timing_uncertain"],
                  provenance={"monthly_saving": "owner_entered" if owner_amount is not None else "flagged_obligations"})
    res["assumptions"].append("a commitment is not an actual expense; the saving is potential until the owner confirms it")
    if saving <= 0:
        res.update(feasible=False, reason="no_flagged_obligations", covers_amount=0.0)
        return res
    months = max(goal["slot"], 0)
    res.update(feasible="unknown", reason="savings_not_confirmed", covers_amount=round(saving * months, 2), monthly_cash_effect=round(saving, 2))
    res["details"].update(monthly_saving=round(saving, 2), months=months)
    return _with_timing(res, goal["due"], ctx["today"])


def _custom(option: dict, ctx: dict, goal: dict) -> dict:
    certainty = option["certainty"] or ("expected" if option["available_by"] else "uncertain")
    res = _result(option, covers_amount=option["amount"], certainty=certainty, provenance={"all": "owner_entered"},
                  monthly_cash_effect=-option["monthly_cost"] if option["monthly_cost"] else None,
                  one_time_cost=option["one_time_cost"] or None, total_cost=option["one_time_cost"] or None,
                  risks=_risks("timing_uncertain" if option["available_by"] is None or certainty == "uncertain" else None))
    res["details"]["label"] = option["label"]
    if option["available_by"] is None:
        res.update(feasible="unknown", reason="available_by_missing", missing_inputs=["available_by"])
    elif option["available_by"] > goal["due"]:
        res.update(feasible=False, reason="available_after_due")
    else:
        res["feasible"] = True
    return _with_timing(res, option["available_by"], ctx["today"])


def _work_income(option: dict, ctx: dict, goal: dict, solved: dict) -> dict:
    res = _result(option, certainty="uncertain", conditions=["extra_income_available"], provenance={"based_on": option.get("based_on")})
    base = solved.get(option.get("based_on"))
    if base is None or base["type"] != "new_deposits":
        res.update(feasible="unknown", reason="based_on_missing", missing_inputs=["based_on"])
        return res
    if base["feasible"] is not True:
        res.update(feasible=False, reason="based_on_not_feasible")
        return res
    required = float(base["details"]["required_monthly"])
    res.update(feasible="unknown", reason="income_not_confirmed", covers_amount=base["covers_amount"], monthly_cash_effect=required)
    res["details"].update(extra_net_income_required_monthly=required, income_goal=ctx.get("income"))
    res["assumptions"].append("extra net monthly income equal to the deposit required by the referenced option; availability of work is not assumed")
    return _with_timing(res, goal["due"], ctx["today"])


# ── צורך ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def _need(goal_rec: dict, ctx: dict) -> dict:
    today = ctx["today"]
    target, due = af._goal_number(goal_rec.get("target_amount")), af._iso_date(goal_rec.get("end_date"))
    row = ctx["goal_rows"].get(goal_rec["id"], {})
    need = {"goal_id": goal_rec["id"], "title": goal_rec.get("title"), "category": goal_rec.get("category"), "target": target,
            "due": due.isoformat() if due else None, "months_to_due": None, "reason": None, "sizing_basis": "target_minus_confirmed",
            "confirmed_existing": 0.0, "expected_existing": 0.0, "progress_events_actual": None, "gap": None}
    if goal_rec["id"] in ctx["parents"]:
        need["reason"] = "parent_goal_rollup_not_supported"
    elif target is None:
        need["reason"] = "missing_target"
    elif due is None:
        need["reason"] = "missing_date"
    else:
        slot = _slot(due, today.replace(day=1))
        months = _months_between(today.replace(day=1), due)
        need["months_to_due"] = max(months, 0)
        if months < 0:
            need["reason"] = "past_date"
        elif months >= _MAX_MONTHS:
            need["reason"] = "beyond_horizon"
        elif slot is None or slot < 1:
            need["reason"] = "due_this_month"          # אין חודש שהושלם עד התאריך: לא ניתן לחשב בבטחה
    if row.get("method") == "cumulative":
        need["progress_events_actual"] = float(row["net"]) if row.get("net") else None
    return need


def _certainty_counts(entries: list) -> dict:
    out = {c: 0.0 for c in CERTAINTIES}
    for certainty, amount in entries:
        out[certainty if certainty in out else "unknown"] += amount
    return {k: round(v, 2) for k, v in out.items()}


def _reach(gap: float, monthly: float, ctx: dict, due: date, today: date) -> dict:
    """מתי הכסף **החדש** שמופקד `monthly` כל חודש מגיע ל-`gap` — קריאה בלבד מאותו מנוע (אותה `_value_at` / `simulate`, חיפוש לפי חודשים,
    לא נוסחה חדשה). לא מגיע באופק החישוב -> `reached: False` ואין תאריך מומצא. `months_vs_due`: שלילי = לפני התאריך, חיובי = אחריו."""
    p, start, years = ctx["p"], ctx["start"], ctx["years"]
    out = {"monthly": round(monthly, 2), "reached": False, "reach_date": None, "months_vs_due": None}
    if monthly <= 0:
        return out
    series = simulate(Scenario(years=years, initial=0.0, monthly_contribution=monthly, inflation=p["inflation"], deposit_timing=p["deposit_timing"],
                               start_date=start, assets=(Asset(name="account", annual_return=p["annual_return"], annual_fee=p["annual_fee"]),)), monthly=True)["monthly"]
    first = next((i for i, row in enumerate(series) if float(row["value_after_costs"]) >= gap), None)
    if first is None:
        return out
    day = af._month_end(_add_months(af._iso_date(start), first))
    out.update(reached=True, reach_date=day.isoformat(), months_vs_due=_months_between(due, day))
    return out


_SENSITIVITY_PP = 2.0                                    # ±נקודות אחוז סביב התשואה הנחשבת (Q-R2; טווח מותאם — שלב נפרד)


def _alternatives(required: float, income_target, planned, from_existing) -> dict:
    """איפה ההפקדה הנדרשת `required` יושבת (GOAL_FUNDING_CHAIN_SPEC §1.2, שלב C4) — שלוש חלופות זו לצד זו, בסדר קבוע, בלי דירוג ובלי המלצה.
    חיבור וחיסור של מספרים מוצגים בלבד (לא נוסחה כספית חדשה); כל מה שחסר נאמר כ"חסר" ולא כ-0; הקצאת הפקדה בפועל — רק דרך "אשר" הקיים.
    A: כולה נוספת לצורך ההכנסה החודשית. B: כולה על חשבון ההפקדה המתוכננת (מצמצמת אותה — אזהרה, Q-C12). C (מסלול ד׳): הבעלים מזין כמה בא
    מההפקדות הקיימות והשאר משלים את ההכנסה הנדרשת; האחוז מחושב כאן ומוצג בלבד (Q-C4)."""
    inc = float(income_target) if isinstance(income_target, (int, float)) and not isinstance(income_target, bool) else None
    pln = float(planned) if isinstance(planned, (int, float)) and not isinstance(planned, bool) else None
    r = round(required, 2)

    def row(key, *, income_after, planned_after, reduces, **extra):
        return {"key": key, "feasible": True, "reason": None, "income_need_before": inc, "income_need_after": income_after,
                "planned_before": pln, "planned_after": planned_after, "shortfall": None, "reduces_planned_deposits": reduces, **extra}

    a = row("A", income_after=round(inc + r, 2) if inc is not None else None, planned_after=pln, reduces=False, top_up_income=r, from_existing=0.0)
    b = row("B", income_after=inc, planned_after=round(pln - r, 2) if pln is not None else None, reduces=True, top_up_income=0.0, from_existing=r)
    if pln is None:
        b["feasible"], b["reason"] = "unknown", "planned_missing"
    elif r > pln + 0.005:
        b.update(feasible=False, reason="exceeds_planned", shortfall=round(r - pln, 2), planned_after=None)
    if from_existing is None:
        c = {"key": "C", "feasible": "unknown", "reason": "amount_not_entered"}
    else:
        f = round(float(from_existing), 2)
        top = round(max(r - f, 0.0), 2)
        c = row("C", income_after=round(inc + top, 2) if inc is not None else None, planned_after=round(pln - f, 2) if pln is not None else None,
                reduces=True, top_up_income=top, from_existing=f, existing_share_pct=round(min(f / r * 100, 100.0), 1) if r > 0 else None,
                over_required_by=round(f - r, 2) if f > r + 0.005 else None)
        if pln is None:
            c["feasible"], c["reason"] = "unknown", "planned_missing"
        elif f > pln + 0.005:
            c.update(feasible=False, reason="exceeds_planned", shortfall=round(f - pln, 2), planned_after=None)
    return {"required": r, "routes": [a, b, c],
            "note": "side by side, in a fixed order; a route that lowers the planned deposits may lower a fund's deposit — that is your explicit choice"}


def _required_monthly_card(need: dict, plan: dict | None, ctx: dict, request: dict, planned_monthly, today: date, *, light: bool = False) -> dict:
    """הפקדה חודשית נדרשת ליעד (REQUIRED_MONTHLY_DEPOSIT_CARD_SPEC): כמה כסף **חדש** להפקיד כל חודש כדי להגיע לפער עד התאריך, לפי הנחות גלויות
    ובעלות מקור. אותו חיפוש בינארי מעל המנוע כמו `required_monthly` — אין נוסחה חדשה; קריאה בלבד, לא כותב ולא משנה "נותר" או "מבט תיק".
    `scenarios` = אותה הפקדה על שארית שונה (אחרי מאושר / אחרי מאושר וצפוי / אחרי כל התוכנית) — כל אחת מסומנת, ואף אחת אינה "הכסף הזמין"."""
    if need["reason"] not in (None, "already_covered"):
        return {"amount": None, "reason": need["reason"]}
    if need["reason"] == "already_covered":
        return {"amount": 0.0, "reason": "no_gap", "gap": need.get("gap")}
    p, start, years, slot = ctx["p"], ctx["start"], ctx["years"], need["slot"]
    fee, deposit_fee = p["annual_fee"], 0.0

    def amount(remaining: float, annual_return: float):
        return required_monthly(remaining, slot, years=years, annual_return=annual_return, fee=fee, deposit_fee_pct=deposit_fee, p=p, start=start)

    base_return, gap = p["annual_return"], need["gap"]
    main = amount(gap, base_return)
    if light:                                          # a window end / the schedule: only the amount (same search), none of the extras
        return {"amount": main, "reason": None if main is not None else "unreachable_under_assumptions", "gap": gap, "months": slot, "due": need["due"]}
    sources = {k: ("owner" if k in request["assumptions"] else "default") for k in ("annual_return_pct", "annual_fee_pct", "inflation_pct")}
    sensitivity = [{"label": label, "annual_return_pct": round((base_return + shift) * 100, 4), "amount": amount(gap, base_return + shift)}
                   for label, shift in (("low", -_SENSITIVITY_PP / 100), ("base", 0.0), ("high", _SENSITIVITY_PP / 100))
                   if -0.5 <= base_return + shift <= 0.5]
    scenarios = []
    if plan:
        target = need["target"]
        for basis, remaining in (("after_confirmed", plan["remaining_after_confirmed"]),
                                 ("after_confirmed_and_expected", plan["remaining_after_confirmed_and_expected"]),
                                 ("after_all_selected", round(max(target - plan["allocated_total"], 0.0), 2))):
            scenarios.append({"basis": basis, "remaining": remaining, "amount": amount(remaining, base_return)})
    # two SEPARATE forecasts of the arrival date — never combined (Q-R8): the family's standing planned savings and the figure typed on the card
    due = af._iso_date(need["due"])
    arrival = [{"basis": "planned", **(_reach(gap, float(planned_monthly), ctx, due, today) if planned_monthly else {"monthly": None})}]
    if request.get("card_monthly"):
        arrival.append({"basis": "entered", **_reach(gap, float(request["card_monthly"]), ctx, due, today)})
    return {"amount": main, "reason": None if main is not None else "unreachable_under_assumptions", "gap": gap, "months": slot, "due": need["due"],
            "arrival": arrival,
            "alternatives": [{"basis": basis, "remaining": remaining, **_alternatives(value, (ctx.get("income") or {}).get("target"), planned_monthly, request.get("from_existing"))}
                             for basis, remaining, value in [("gap", gap, main)] + [(sc["basis"], sc["remaining"], sc["amount"]) for sc in scenarios if sc["remaining"] != gap]
                             if value is not None and remaining > 0],
            "total_deposits": round(main * slot, 2) if main is not None else None,
            "assumptions": {"annual_return_pct": round(base_return * 100, 4), "fee_pct": round(fee * 100, 4), "deposit_fee_pct": deposit_fee,
                            "inflation_pct": round(p["inflation"] * 100, 4), "sources": sources},
            "basis": "assumptions", "sensitivity": sensitivity, "scenarios": scenarios,
            "planned_monthly_savings": planned_monthly,
            "note": "new money only (existing balances are not counted); not split between goals; the planned figure is the family's standing plan, shown beside it and never netted"}


def build_commitments_schedule(inputs: dict, request: dict, today: date) -> dict:
    """לוח התחייבויות חודשי (GOAL_FUNDING_CHAIN_SPEC §4, Q-C5/Q-C6/Q-C7): לכל יעד פעיל עם סכום ותאריך — ההפקדה החודשית הנדרשת (אותו חיפוש בינארי מעל המנוע,
    על הפער, בהנחות הבקשה), מהחודש הנוכחי ועד חודש היעד; ועקומת הנטל החודשי **בזמן**: יעדים עוקבים לא מסוכמים כמקבילים, והפקדה שמסתיימת מוצגת כשורת שחרור
    נפרדת (קו, לא הבטחה). קריאה בלבד: לא נשמר, לא מקצה קיבולת בין יעדים, לא משנה "נותר"/"מבט תיק". חסר = ברשימת ההשמטות, לא 0. תאריך אחד לכל יעד (נקודת ההערכה)."""
    start = today.replace(day=1)
    planned = (inputs.get("savings_plan") or {}).get("target")
    planned = float(planned) if isinstance(planned, (int, float)) and not isinstance(planned, bool) else None
    active = [g for g in inputs.get("goals") or [] if isinstance(g, dict) and g.get("id") and str(g.get("status") or "active").lower() in ("active", "פעיל")]
    candidates, excluded = [], []
    for g in active:
        target, due = af._goal_number(g.get("target_amount")), af._iso_date(g.get("end_date"))
        title = g.get("title")
        if target is None and due is None:
            continue                                                     # not a funding goal at all (e.g. a project): nothing half-defined to report
        reason = "missing_target" if target is None else "missing_date" if due is None else "past_date" if due < start else None
        (excluded if reason else candidates).append({"goal_id": g["id"], "title": title, "reason": reason} if reason else {"goal_id": g["id"], "title": title, "due": due})
    candidates.sort(key=lambda c: (c["due"], c["goal_id"]))
    truncated = len(candidates) > _MAX_GOALS
    chosen = candidates[:_MAX_GOALS]
    rows = []
    if chosen:
        sub = {**request, "goal_ids": [c["goal_id"] for c in chosen], "options": [], "allocation_plan": [], "date_margin_months": 0, "card_monthly": None,
               "from_existing": None, "schedule": False, "schedule_goal_ids": None}
        plan = build_funding_plan(inputs, sub, today, _window_variant=True)
        title_of = {c["goal_id"]: c["title"] for c in chosen}
        for out in plan["goals"]:
            need, card = out["need"], out["required_monthly_card"]
            gid = need["goal_id"]
            if card.get("amount") is None or need["reason"] not in (None, "already_covered") or card.get("reason") == "no_gap":
                excluded.append({"goal_id": gid, "title": title_of.get(gid), "reason": card.get("reason") or need["reason"]})
            elif card["amount"] > 0:
                months = int(card["months"])
                rows.append({"goal_id": gid, "title": title_of.get(gid), "amount": card["amount"], "months": months, "due": need["due"],
                             "start": start.isoformat(), "end": _add_months(start, months - 1).isoformat(), "released_from": _add_months(start, months).isoformat()})
    wanted = request.get("schedule_goal_ids")
    for r in rows:
        r["selected"] = wanted is None or r["goal_id"] in wanted
    sel = [r for r in rows if r["selected"]]
    breaks = sorted({0} | {r["months"] for r in sel})
    steps = []
    for lo, hi in zip(breaks, breaks[1:]):
        live = [r for r in sel if r["months"] > lo]
        burden = round(sum(r["amount"] for r in live), 2)
        steps.append({"from": _add_months(start, lo).isoformat(), "to": _add_months(start, hi - 1).isoformat(), "burden": burden,
                      "goal_ids": [r["goal_id"] for r in live], "shortfall_vs_planned": round(max(burden - planned, 0.0), 2) if planned is not None else None})
    peak = max((st["burden"] for st in steps), default=0.0)
    releases = sorted(({"goal_id": r["goal_id"], "title": r["title"], "amount": r["amount"], "released_from": r["released_from"]} for r in sel),
                      key=lambda x: (x["released_from"], x["goal_id"]))
    return {"as_of": today.isoformat(), "start": start.isoformat(), "rows": rows, "steps": steps, "releases": releases, "peak_burden": peak,
            "planned_monthly_savings": planned,
            "peak_shortfall": round(max(peak - planned, 0.0), 2) if planned is not None else None,
            "excluded": excluded[:20], "truncated": truncated,
            "assumptions": dict(request.get("assumptions") or {}),
            "notes": ["read_only", "one_date_per_goal", "no_capacity_allocation", "not_continuing_deposits"]}


# ── בניית התוכנית ─────────────────────────────────────────────────────────────────────────────────────────────────

def build_funding_plan(inputs: dict, request: dict, today: date | None = None, *, _window_variant: bool = False) -> dict:
    """`inputs` = נתוני הבעלים עצמו בלבד (מוכנים בשרת דרך `service.funding_inputs`); `request` = פלט `normalize_request`."""
    today = today or date.today()
    p = af.normalize_params({"years": 10, **request["assumptions"]})
    goals = {g["id"]: g for g in inputs.get("goals") or [] if isinstance(g, dict) and g.get("id")}
    for gid in request["goal_ids"]:
        if gid not in goals:
            raise ValueError("unknown goal")
    goal_rows = {r["goal_id"]: r for r in inputs.get("goal_rows") or [] if r.get("goal_id")}
    parents = {r["parent_id"] for r in goal_rows.values() if r.get("parent_id")}
    base_ctx = {"today": today, "goal_rows": goal_rows, "parents": parents}

    needs = {gid: _need({**goals[gid], "id": gid}, base_ctx) for gid in request["goal_ids"]}
    calculable = {gid: n for gid, n in needs.items() if n["reason"] is None}
    start = today.replace(day=1).isoformat()
    slots = {gid: _slot(af._iso_date(n["due"]), today.replace(day=1)) for gid, n in calculable.items()}
    years = max([10] + [math.ceil(s / 12) for s in slots.values() if s]) if slots else 10
    years = min(years, 100)
    p = af.normalize_params({"years": years, **request["assumptions"]})

    forecast = af.build_accounts_forecast(inputs.get("accounts_view") or {}, {"years": years, **request["assumptions"]}, today=today,
                                          goals=inputs.get("goals") or [], allocations=inputs.get("allocations") or [])
    ctx = {
        **base_ctx, "p": p, "years": years, "start": start,
        "accounts": {a["id"]: a for a in (inputs.get("accounts_view") or {}).get("accounts") or [] if a.get("id")},
        "assets": {a["id"]: a for a in inputs.get("assets") or [] if a.get("id")},
        "loans": {l["id"]: l for l in inputs.get("loans") or [] if l.get("id")},
        "obligations": inputs.get("obligations"), "income": inputs.get("income"),
        "alloc_goals": {g["id"]: g for g in (forecast.get("allocations") or {}).get("goals") or []},
        "forecast_goals": {g["id"]: g for g in forecast.get("goals") or [] if g.get("id")},
    }

    results: dict[str, dict] = {}
    plan_by_goal: dict[str, list] = {gid: [] for gid in request["goal_ids"]}
    for entry in request["allocation_plan"]:
        plan_by_goal[entry["goal_id"]].append(entry)

    goal_outputs = []
    for gid in request["goal_ids"]:
        need = needs[gid]
        out = {"need": need, "options": [], "plan": None}
        if need["reason"] is not None:
            goal_outputs.append(out)
            continue
        due, slot = af._iso_date(need["due"]), slots[gid]
        goal = {"id": gid, "due": due, "slot": slot, "method": goal_rows.get(gid, {}).get("method"),
                "progress_events_actual": need["progress_events_actual"]}
        existing = _existing_balance(ctx, goal)
        confirmed = float(existing["details"].get("confirmed_amount", existing["covers_amount"] if existing["certainty"] == "confirmed" and existing["feasible"] is True else 0.0) or 0.0)
        expected = float(existing["details"].get("expected_amount", 0.0) or 0.0)
        target = need["target"]
        need.update(confirmed_existing=round(min(confirmed, target), 2), expected_existing=round(expected, 2),
                    gap=round(max(target - confirmed, 0.0), 2), gap_after_expected=round(max(target - confirmed - expected, 0.0), 2))
        goal["gap"] = need["gap"]
        solved: dict[str, dict] = {}
        opts = [existing]
        if need["gap"] <= 0:
            need["reason"] = "already_covered"
            out["options"] = opts
            goal_outputs.append(out)
            continue
        fns = {"new_deposits": _new_deposits, "loan": _loan, "asset_sale": _asset_sale, "receivable_collection": _receivable,
               "obligations_reduction": _obligations, "custom": _custom}
        deferred = []
        for option in request["options"]:
            if option["type"] == "work_income":
                deferred.append(option)
                continue
            res = fns[option["type"]](option, ctx, goal)
            solved[option["id"]] = res
            opts.append(res)
        for option in deferred:
            opts.append(_work_income(option, ctx, goal, solved))
        order = {t: i for i, t in enumerate(OPTION_TYPES)}
        opts.sort(key=lambda r: (order[r["type"]], r["id"]))               # סדר קבוע לפי סוג — לעולם לא לפי תוצאה
        out["options"] = opts
        results[gid] = {r["id"]: r for r in opts}
        goal_outputs.append(out)

    # תוכנית: פיצול הצורך בין אפשרויות; כסף קיים מאושר/צפוי נכלל תמיד, וכל השאר לפי ודאות האפשרות — בלי סכום אחד
    pool_use: dict[str, float] = {}
    for out in goal_outputs:
        gid = out["need"]["goal_id"]
        entries = plan_by_goal[gid]
        if not entries:
            continue
        opts = results.get(gid)
        if opts is None:
            raise ValueError("allocation_plan refers to a goal without computed options")
        need = out["need"]
        parts = [("confirmed", need["confirmed_existing"]), ("expected", need["expected_existing"])]
        allocations, monthly_burden, monthly_release, dates = [], 0.0, 0.0, []
        for entry in entries:
            res = opts[entry["option_id"]]
            if res["feasible"] is False:
                raise ValueError("allocation_plan uses an option that is not feasible for this goal")
            if res["covers_amount"] is None or entry["amount"] > res["covers_amount"] + 0.005:
                raise ValueError("allocation_plan amount exceeds what the option covers")
            parts.append((res["certainty"], entry["amount"]))
            pool_use[res["id"]] = pool_use.get(res["id"], 0.0) + entry["amount"]
            if res["monthly_cash_effect"] is not None and res["covers_amount"]:
                share = res["monthly_cash_effect"] * entry["amount"] / res["covers_amount"]
                if share < 0:
                    monthly_burden += -share
                else:
                    monthly_release += share
            if res["available_by"]:
                dates.append(res["available_by"])
            allocations.append({"option_id": entry["option_id"], "amount": entry["amount"], "certainty": res["certainty"],
                                "available_by": res["available_by"], "conditions": res["conditions"]})
        covered = _certainty_counts(parts)
        target = need["target"]
        out["plan"] = {
            "allocations": allocations, "covered": covered, "earliest_available_by": min(dates) if dates else None,
            "remaining_after_confirmed": round(max(target - covered["confirmed"], 0.0), 2),
            "remaining_after_confirmed_and_expected": round(max(target - covered["confirmed"] - covered["expected"], 0.0), 2),
            "monthly_burden": round(monthly_burden, 2), "monthly_release": round(monthly_release, 2),
            "allocated_total": round(sum(covered.values()), 2), "over_target_by": round(max(sum(covered.values()) - target, 0.0), 2),
            "note": "coverage is split by certainty and is never summed into one 'available' figure"}
    pool_totals = {}
    for gid, opts in results.items():
        for oid, res in opts.items():
            if res["type"] in ("asset_sale", "loan", "receivable_collection", "custom") and res["covers_amount"]:
                pool_totals[oid] = res["covers_amount"]
    over = sorted(oid for oid, used in pool_use.items() if oid in pool_totals and used > pool_totals[oid] + 0.005)

    savings = inputs.get("savings_plan") or {}
    # two different figures, never mixed: the standing PLAN (`target`, looking forward) and what was ACTUALLY put aside (`actual`, how far we got)
    planned = savings.get("target") if isinstance(savings.get("target"), (int, float)) else None
    actual = savings.get("actual") if isinstance(savings.get("actual"), (int, float)) else None
    total_burden = round(sum(o["plan"]["monthly_burden"] for o in goal_outputs if o["plan"]), 2) if any(o["plan"] for o in goal_outputs) else None

    def _short(base):
        return round(max(total_burden - base, 0.0), 2) if total_burden is not None and base is not None else None
    portfolio = {
        "monthly_burden_in_plan": total_burden, "planned_monthly_savings": planned, "actual_monthly_savings": actual,
        "shortfall_vs_planned": _short(planned), "shortfall_vs_actual": _short(actual),
        "planned_known": planned is not None, "actual_known": actual is not None, "plan_chosen": total_burden is not None,
        "info": {"savings_release": inputs.get("savings_release"), "monthly_cash_improvement": inputs.get("monthly_cash_improvement")},
        "over_committed": over,
    }
    for out in goal_outputs:
        gid = out["need"]["goal_id"]
        out["need"]["slot"] = slots.get(gid)
        out["required_monthly_card"] = _required_monthly_card(out["need"], out["plan"], ctx, request, planned, today, light=_window_variant)
        out["need"].pop("slot", None)
    if not _window_variant:
        for out in goal_outputs:
            need = out["need"]
            override = request.get("date_margin_months")
            margin = override if override is not None else int(goals[need["goal_id"]].get("date_margin_months") or 0)
            need["date_margin_months"] = margin
            if need["reason"] is None and margin > 0:
                out["window"] = _date_window(inputs, request, goals[need["goal_id"]], margin, today)
                if out["window"]:                      # the same required deposit at each end of the date estimate (read from the variants, not recomputed here)
                    out["required_monthly_card"]["window"] = {"margin_months": margin, **{
                        end: {"due": out["window"][end]["due"], "amount": (out["window"][end].get("required_card") or {}).get("amount"),
                              "reason": (out["window"][end].get("required_card") or {}).get("reason") or out["window"][end]["reason"]}
                        for end in ("early", "late")}}
    schedule = build_commitments_schedule(inputs, request, today) if request.get("schedule") and not _window_variant else None
    warnings = ["השוואה בין אפשרויות בלבד — לא המלצה ולא בחירה עבורך.", "כסף צפוי או לא ודאי אינו כסף קיים: הכיסוי מפוצל לפי ודאות.",
                "אין מודל מס; תמורה נטו, ריבית ותקופה הם כפי שהוזנו ('תנאים לא אומתו' אלא אם סומן אחרת)."]
    return {"schema_version": FUNDING_SCHEMA_VERSION, "result_type": "funding_plan_comparison", "as_of": today.isoformat(),
            "assumptions": {"annual_return_pct": p["annual_return"] * 100, "annual_fee_pct": p["annual_fee"] * 100, "inflation_pct": p["inflation"] * 100,
                            "horizon_years": years},
            "goals": goal_outputs, "portfolio": portfolio, "warnings": warnings, **({"schedule": schedule} if schedule is not None else {})}
