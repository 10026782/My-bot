"""מקורות מימון מוצעים ליעד (שלב 1, `GOAL_FUNDING_SOURCES_SPEC.md`) — שכבת הרכבה טהורה: ללא I/O, Airtable, LLM או כתיבה.

מהנתונים הקיימים של הבעלים בלבד (חשבונות, נכסים, חייבים לי, הקצאות) נגזרת רשימת מועמדים ליעד, בחמש קטגוריות נפרדות שאינן מסוכמות:
(1) `liquid_now` כסף נזיל עכשיו; (2) `liquid_by_due_date` כסף שיהפוך לנגיש עד תאריך היעד; (3) `conditional_on_action` מותנה בפעולה
(מכירת נכס, אימות נזילות); (4) `expected_not_guaranteed` צפוי שאינו מובטח (גביית חוב); (5) `future_deposits` הפקדות מתוכננות שטרם בוצעו.

לכל חשבון מוצג גם `expected_at_due` — ערך תחזית לפי הנחות גלויות (`accounts_forecast.account_value_points`), נפרד מהיתרה המדווחת ואינו מובטח.
אין המלצה, אין ציון, אין דירוג, אין `total_available`: כל שורה מציגה סכום (או "חסר"), תנאים, מועדים והשפעה על יתרת ההון — ללא סיכום בין
קטגוריות. נתון חסר נשאר `None` + `missing_inputs`, לא 0. בלי מס ובלי הערכת שווי או תמורה של נכס; זמן מכירה ידני של הבעלים. `Liquid From` אינו
זכאות: מצב הנזילות נגזר מ-`accounts_forecast` (`_liquidity_profile` / `_state_at`) ללא שינוי. חשבון שהוקצה ליעד אחר מסומן `allocated_elsewhere`
ואינו נספר פעמיים. הפקדה מתוכננת מסומנת `included_in_forecast` / `not_included` כדי שלא תיספר פעמיים עם הכסף הקיים. המנוע ו-`funding_plan` לא משתנים.
"""

from __future__ import annotations

import math
from datetime import date

from core.financial_control import loans as fcc_loans

from . import accounts_forecast as af
from . import funding_plan as fp

SOURCES_SCHEMA_VERSION = "1.0"
CATEGORIES = ("liquid_now", "liquid_by_due_date", "conditional_on_action", "expected_not_guaranteed", "future_deposits")
_RANK = {"locked": 0, "conditional": 1, "accessible": 2}
_BASIS_CONDITIONS = {
    "immediate": [], "retirement_immediate": ["retirement_product_not_one_time_cash"],
    "dated": ["liquid_from_reached_eligibility_unverified"], "undated": ["liquid_from_missing"], "unverified": ["liquidity_unverified"],
}


def _point(day: date | None, today: date) -> dict:
    """תאריך -> הנקודה שממנה A2 קורא מצב/ערך: סוף החודש האחרון שהושלם עד התאריך (0 = היום). `slot None` = תאריך חסר או שעבר."""
    slot = None if day is None else fp._slot(day, today.replace(day=1))
    if slot is None:
        return {"date": day.isoformat() if day else None, "slot": None, "as_of": None}
    as_of = today if slot == 0 else af._month_end(fp._add_months(today.replace(day=1), slot - 1))
    return {"date": day.isoformat(), "slot": slot, "as_of": as_of}


def _states(profile: dict, points: dict) -> dict:
    return {name: (af._state_at(profile, p["as_of"]) if p["as_of"] is not None else None) for name, p in points.items()}


def _balance_amount(account: dict):
    balance = account.get("balance") or {}
    value = balance.get("value")
    return (float(value), balance.get("as_of")) if isinstance(value, (int, float)) and not isinstance(value, bool) else (None, None)


def _allocation_view(overview: dict, goal_id: str) -> dict:
    """לכל חשבון: כמה הוקצה ליעד הזה / ליעדים אחרים (מהצילום האחרון, עובדה). חשבון בהקצאת יתר אינו מקבל סכום 'לא מוקצה' — לא מנחשים."""
    out = {}
    for row in overview.get("accounts") or []:
        mine = sum(a["resolved_amount"] for a in row["allocations"] if a["goal_id"] == goal_id)
        elsewhere = sum(a["resolved_amount"] for a in row["allocations"] if a["goal_id"] != goal_id)
        out[row["id"]] = {
            "allocated_to_this_goal": round(mine, 2), "allocated_elsewhere_amount": round(elsewhere, 2),
            "allocated_elsewhere": elsewhere > 0.005, "over_allocated": row["over_allocated"],
            "amount_not_allocated_elsewhere": None if row["over_allocated"] else round(max(row["value"] - elsewhere, 0.0), 2),
        }
    return out


def _item(source_type: str, source_id, name, **fields) -> dict:
    base = {"source_type": source_type, "source_id": source_id, "name": name, "amount": None, "amount_status": "missing", "as_of": None,
            "certainty": "unknown", "conditions": [], "risks": [], "missing_inputs": [], "balance_effect": None, "provenance": {},
            "option_template": None, "owner_must_enter": []}
    base.update(fields)
    return base


def _expected_at(account: dict, points: dict, assumptions: dict, today: date) -> dict | None:
    """ערך צפוי של חשבון בתאריך היעד (ובקצוות החלון) לפי `accounts_forecast` והנחות גלויות — נפרד מהיתרה המדווחת ואינו מובטח.
    כולל את ההפקדה החודשית המתוכננת של החשבון (אם יש) והתשואה/דמי הניהול כפי שהוזנו או כברירת מחדל. None = אין צילום יתרה או אין תאריך."""
    if not af._eligible(account):
        return None
    slots = {name: p["slot"] for name, p in points.items() if name != "now"}
    known = [v for v in slots.values() if v is not None]
    if not known:
        return None
    years = min(max(10, math.ceil(max(known) / 12)), 100)
    values = af.account_value_points(account, {"years": years, **assumptions}, today)

    def at(slot):
        return None if slot is None or slot >= len(values) else round(values[slot], 2)

    planned = af._valid(account.get("planned_monthly_deposit"), 0, 10_000_000)
    return {"label": "expected_by_assumptions", "guaranteed": False, "amount": at(slots["due"]), "early": at(slots["early"]), "late": at(slots["late"]),
            "includes_planned_deposits": bool(planned), "monthly_planned_deposit_included": planned or 0.0,
            "note": "forecast value under the shown assumptions; separate from the reported balance, not an entitlement to withdraw"}


def _account_item(account: dict, goal_id: str, points: dict, alloc: dict, expected: dict | None) -> tuple[str, dict]:
    profile = af._liquidity_profile(account)
    states = _states(profile, points)
    amount, as_of = _balance_amount(account)
    item = _item(
        "account", account.get("id"), account.get("name"), amount=amount, amount_status="reported" if amount is not None else "missing", as_of=as_of,
        certainty="confirmed" if states["now"] == "accessible" else "uncertain", conditions=list(_BASIS_CONDITIONS[profile["basis"]]),
        risks=["self_reported_balance"] if amount is not None else [], missing_inputs=([] if amount is not None else ["balance_snapshot"]) + ([profile["gap"]] if profile["gap"] else []),
        balance_effect="uses_existing_balance", provenance={"amount": "reported_balance_snapshot", "liquidity": "account_fields"},
        expected_at_due=expected,
        liquidity={"basis": profile["basis"], "liquid_from": profile["liquid_from"].isoformat() if profile["liquid_from"] else None, "state_at": states},
        allocation=alloc.get(account.get("id")) or {"allocated_to_this_goal": None, "allocated_elsewhere_amount": None, "allocated_elsewhere": False,
                                                      "over_allocated": False, "amount_not_allocated_elsewhere": None},
        option_note="existing_balance_is_automatic_via_goal_allocation")
    if item["allocation"]["allocated_elsewhere"]:
        item["risks"].append("allocated_elsewhere")
    if item["allocation"]["over_allocated"]:
        item["risks"].append("over_allocated")
    now, due = states["now"], states["due"]
    if now == "accessible":
        return "liquid_now", item
    if due == "accessible":
        return "liquid_by_due_date", item
    if now == "conditional" or due == "conditional":
        return "conditional_on_action", item
    return "not_available", item


def _asset_item(asset: dict) -> dict:
    linked = [l.get("name") for l in asset.get("linked_loans") or []]
    risks = ["debt_overlap_unresolved"] if (asset.get("mortgage_balance") or 0) > 0 or asset.get("linked_loans") else []
    if (asset.get("monthly_income") or 0) > 0:
        risks.append("lost_income")
    return _item(
        "asset", asset.get("id"), asset.get("name"), as_of=None, certainty="uncertain", conditions=["owner_decides_to_sell", "sale_closes"], risks=risks,
        missing_inputs=["net_proceeds", "expected_sale_date"], balance_effect="converts_asset_to_cash",
        provenance={"recorded_value": "owner_recorded_gross", "net_proceeds": "owner_entered", "time_to_sell": "owner_manual"},
        asset={"asset_type": asset.get("asset_type"), "recorded_value": asset.get("current_value"), "ownership_pct": asset.get("ownership_pct"),
               "mortgage_balance": asset.get("mortgage_balance"), "linked_debt": asset.get("linked_debt"), "linked_loan_names": linked,
               "monthly_income": asset.get("monthly_income")},
        option_template={"type": "asset_sale", "asset_id": asset.get("id")}, owner_must_enter=["net_proceeds", "expected_date"])


def _receivable_item(loan: dict) -> dict:
    arranged = loan.get("arrangement") is not None
    balance = loan.get("early_closure_balance")
    return _item(
        "receivable", loan.get("id"), loan.get("name"), amount=balance, amount_status="recorded_balance" if balance is not None else "missing",
        certainty="expected" if arranged else "uncertain", conditions=["debtor_pays_on_schedule"] if arranged else ["debtor_arrangement"],
        risks=["timing_uncertain"] + ([] if arranged else ["receivable_no_arrangement"]),
        missing_inputs=([] if balance is not None else ["recorded_balance"]) + ([] if arranged else ["arrangement"]),
        balance_effect="converts_receivable_to_cash", provenance={"amount": "recorded_balance_not_expected_net"},
        receivable={"arrangement": loan.get("arrangement"), "next_payment_due": loan.get("next_payment_due"), "end_date": loan.get("end_date")},
        option_template={"type": "receivable_collection", "loan_id": loan.get("id")}, owner_must_enter=["expected_net", "expected_date"])


def _deposit_item(account: dict, planned: float, points: dict, window: dict | None) -> dict:
    profile = af._liquidity_profile(account)
    slot = points["due"]["slot"]
    fee = af._valid(account.get("deposit_fee_pct"), 0, 10)

    def total(point):
        return None if point["slot"] is None else round(planned * point["slot"], 2)

    item = _item(
        "planned_deposit", account.get("id"), account.get("name"), amount=total(points["due"]), amount_status="planned_nominal" if slot is not None else "missing",
        as_of=None, certainty="expected", conditions=["deposits_actually_made"], risks=["not_yet_deposited"],
        missing_inputs=(["goal_date"] if slot is None else []) + ([] if fee is not None else ["deposit_fee"]), balance_effect="adds_future_deposits_to_account",
        provenance={"monthly_amount": "account_planned_monthly_deposit", "growth": "not_included"},
        deposit={"monthly_planned": planned, "months_until_due": slot, "deposit_fee_pct": fee, "state_at": _states(profile, points)},
        forecast_inclusion="included_in_forecast", forecast_inclusion_note="already_inside_forecast_projection_do_not_add_to_existing_balance",
        option_template={"type": "new_deposits", "account_id": account.get("id")})
    if window:
        item["window"] = {name: {"months": points[name]["slot"], "amount": total(points[name])} for name in ("early", "late")}
    return item


def build_suggested_sources(inputs: dict, request: dict, today: date | None = None) -> dict:
    """`inputs` = נתוני הבעלים בלבד (`service.funding_inputs`); `request` = פלט `funding_plan.normalize_request`. קריאה בלבד, דטרמיניסטי."""
    today = today or date.today()
    goals = {g["id"]: g for g in inputs.get("goals") or [] if isinstance(g, dict) and g.get("id")}
    for gid in request["goal_ids"]:
        if gid not in goals:
            raise ValueError("unknown goal")
    assumptions = dict(request.get("assumptions") or {})
    p = af.normalize_params({"years": 10, **assumptions})                 # ValueError on invalid assumptions, same as the plan
    accounts = [a for a in (inputs.get("accounts_view") or {}).get("accounts") or [] if isinstance(a, dict) and a.get("id")]
    live = [a for a in accounts if a.get("status") != "closed"]
    eligible = [a for a in accounts if af._eligible(a)]
    info = {a["id"]: {"profile": af._liquidity_profile(a), "value": float(a["balance"]["value"]), "as_of": a["balance"].get("as_of")} for a in eligible}
    titles = {gid: g.get("title") for gid, g in goals.items()}
    valid, skipped = af._classify_allocations(inputs.get("allocations") or [], titles, {a["id"]: a for a in accounts}, {a["id"] for a in eligible})
    overview, _flags = af._allocations_now(valid, titles, info, {a["id"]: a for a in accounts}, today, skipped)
    owed = [l for l in inputs.get("loans") or [] if l.get("direction") == fcc_loans.OWED_TO_ME and l.get("active")]
    outputs = []
    for gid in request["goal_ids"]:
        goal = goals[gid]
        due = af._iso_date(goal.get("end_date"))
        reason = "missing_date" if due is None else ("past_date" if fp._months_between(today.replace(day=1), due) < 0 else None)
        usable_due = due if reason is None else None
        override = request.get("date_margin_months")
        margin = override if override is not None else int(goal.get("date_margin_months") or 0)
        window = bool(usable_due and margin > 0)
        points = {"now": _point(today, today), "due": _point(usable_due, today),
                  "early": _point(fp._add_months(usable_due, -margin) if window else None, today),
                  "late": _point(fp._add_months(usable_due, margin) if window else None, today)}
        alloc = _allocation_view(overview, gid)
        cats: dict[str, list] = {c: [] for c in CATEGORIES}
        unavailable, gaps = [], []
        for account in live:
            where, item = _account_item(account, gid, points, alloc, _expected_at(account, points, assumptions, today))
            (unavailable if where == "not_available" else cats[where]).append(item)
            planned = af._valid(account.get("planned_monthly_deposit"), 0, 10_000_000)
            if planned is None:
                gaps.append({"account_id": account["id"], "name": account.get("name"), "missing": ["planned_monthly_deposit"]})
            elif planned > 0 and points["due"]["slot"] != 0:
                dep = _deposit_item(account, planned, points, window)
                if not af._eligible(account):
                    dep.update(forecast_inclusion="not_included", forecast_inclusion_note="account_has_no_balance_snapshot_so_the_forecast_omits_it")
                cats["future_deposits"].append(dep)
        cats["conditional_on_action"] += [_asset_item(a) for a in inputs.get("assets") or [] if a.get("id")]
        cats["expected_not_guaranteed"] += [_receivable_item(l) for l in owed]
        for rows in (*cats.values(), unavailable):
            rows.sort(key=lambda r: (r["source_type"], str(r["name"] or ""), str(r["source_id"])))
        outputs.append({
            "goal_id": gid, "title": goal.get("title"), "target_amount": af._goal_number(goal.get("target_amount")),
            "due": due.isoformat() if due else None, "reason": reason,
            "date_window": ({"margin_months": margin, "early": points["early"]["date"], "late": points["late"]["date"],
                             "note": "the date is an estimate; each end is the same states recomputed, nothing here picks a date"} if window else None),
            "categories": cats, "counts": {c: len(cats[c]) for c in CATEGORIES}, "not_available_by_due_date": unavailable, "gaps": {"future_deposits": gaps}})
    return {
        "schema_version": SOURCES_SCHEMA_VERSION, "result_type": "goal_funding_sources", "as_of": today.isoformat(), "goals": outputs,
        "assumptions": {"annual_return_pct": round(p["annual_return"] * 100, 4), "annual_fee_pct": round(p["annual_fee"] * 100, 4),
                        "inflation_pct": round(p["inflation"] * 100, 4), "note": "account-level return, fee and planned deposit, when entered, override these defaults"},
        "category_labels": {"liquid_now": "כסף נזיל עכשיו", "liquid_by_due_date": "כסף שיהפוך לנגיש עד תאריך היעד", "conditional_on_action": "מותנה בפעולה",
                            "expected_not_guaranteed": "צפוי ואינו מובטח", "future_deposits": "הפקדות עתידיות שטרם בוצעו"},
        "warnings": ["רשימת מועמדים בלבד — לא המלצה, לא ציון ולא בחירה עבורך; הקטגוריות אינן מסוכמות זו עם זו.",
                     "יתרות הן הצילום האחרון שדווח, לא תחזית. ״מותנה״ אינו נגיש: תאריך שחרור אינו זכאות למשיכה.",
                     "נכס אינו מוצע כמכירה מובטחת: תמורה נטו ומועד מזין הבעלים; אין הערכת שווי ואין מס.",
                     "הפקדה מתוכננת שכבר נכללת בתחזית אינה נוספת ליתרה הקיימת (included_in_forecast).",
                     "״צפוי לפי הנחות״ הוא ערך תחזית (כולל הפקדה מתוכננת של החשבון) ונפרד מהיתרה המדווחת; אינו מובטח ואינו זכאות למשיכה."],
    }
