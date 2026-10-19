"""קצב צבירה בפועל מול התוכנית (C4) — שכבת הרכבה בלבד מעל המנוע; ללא I/O, Airtable, LLM או כתיבה.

המנוע (`portfolio_lab.engine.simulate`) לא משתנה: כל סכום עתידי/מתוכנן הוא תוצאת הרצה שלו. מה שנקרא מהנתונים הוא עובדות מדווחות
בלבד (צילומי יתרה והפקדות/משיכות/עמלות/העברות מתועדות, כולן `self_reported` אלא אם סומן אחרת) — הקלט נבנה בשרת, מנתוני הבעלים עצמו.

עקרונות מחייבים (החלטת בעלים 19/10/2026):
* מבחינים בין שלושה דברים: **תנועות מתועדות** (הפקדות/משיכות/עמלות/העברות), **שינוי שווי** (יתרה אחרונה פחות ראשונה) ו**שינוי שאינו מוסבר**
  (שינוי השווי פחות התנועות המתועדות: תשואה, ריבית, ותנועות שלא תועדו — לא מזוהה כתשואה).
* תשואה מדויקת אינה מחושבת משתי יתרות כשיש תנועות ביניהן: מוצג `exact: None` וטווח מסומן `approximate_range` (גבולות לפי תזמון התנועות
  הקיצוני בתוך התקופה), או "לא ניתן לחשב" (תקופה קצרה מ-30 יום, יתרת פתיחה אפס, מכנה לא חיובי). גם ללא תנועות מתועדות ייתכנו תנועות שלא תועדו.
* נתון חסר הוא `None` עם קוד ב-`missing` — לא אפס. אירוע באותו יום של צילום יתרה אינו נספר (אי-ודאות אם נכלל ביתרה) ומדווח כ-`same_day_events`.
* התחזית המעודכנת היא אקסטרפולציה של הקצב בפועל מההנחות המוצגות — לא תחזית. אין הסתברויות, ציון, דירוג או המלצה; תיקון המסלול הוא המחשה
  ניטרלית של השפעת שינוי בהפקדה החודשית.
"""

from __future__ import annotations

import math
from datetime import date

from .engine import simulate
from .models import ENGINE_VERSION, Asset, Scenario

PACE_SCHEMA_VERSION = "1.0"
DEFAULTS = {"years": 10, "annual_return_pct": 6.0, "annual_fee_pct": 0.15, "inflation_pct": 2.0}
MIN_RETURN_DAYS = 30            # פחות מכך — אין משמעות לתשואה תקופתית
MIN_ANNUALIZE_DAYS = 90
_MAX_ACCOUNTS = 50
CORRECTION_STEPS = (-1000.0, -500.0, 500.0, 1000.0, 2000.0)     # שינוי בהפקדה החודשית הכוללת, בשקלים
_FLOW_KINDS = ("deposit", "withdrawal", "fee", "transfer")
EXTRAPOLATION_LABEL = "אקסטרפולציה של הקצב בפועל — לא תחזית"


def _number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be from {minimum} to {maximum}")
    return float(value)


def normalize_params(params) -> dict:
    """קלט גולמי (אחוזים כפי שמוצגים במסך) -> מנורמל; ValueError על קלט לא תקף."""
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    years = params.get("years", DEFAULTS["years"])
    if isinstance(years, bool) or not isinstance(years, int) or not 10 <= years <= 50:
        raise ValueError("years must be an integer from 10 to 50")
    return {
        "years": years,
        "annual_return": _number(params.get("annual_return_pct", DEFAULTS["annual_return_pct"]), "annual_return_pct", -50, 50) / 100,
        "annual_fee": _number(params.get("annual_fee_pct", DEFAULTS["annual_fee_pct"]), "annual_fee_pct", 0, 10) / 100,
        "inflation": _number(params.get("inflation_pct", DEFAULTS["inflation_pct"]), "inflation_pct", -50, 50) / 100,
    }


def _valid(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value) if minimum <= value <= maximum else None


def _day(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(value) if isinstance(value, str) else None


def _month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


def _run(initial, monthly, annual_return, annual_fee, inflation, years, start="2026-01-01"):
    return simulate(Scenario(years=years, initial=initial, monthly_contribution=monthly, inflation=inflation, start_date=start,
                             assets=(Asset(annual_return=annual_return, annual_fee=annual_fee),)), monthly=True)


def _clean_events(events, known):
    out = []
    for e in events or []:
        day = _day(e.get("day"))
        amount = _valid(e.get("amount"), 0, 1e12)
        if day is None or amount is None or e.get("account") not in known or e.get("kind") not in _FLOW_KINDS + ("balance_snapshot",):
            continue
        out.append({"kind": e["kind"], "amount": amount, "day": day, "account": e["account"], "counter": e.get("counter"), "id": str(e.get("id") or ""),
                    "verification": e.get("verification") or "self_reported"})
    return out


def _return_block(b0, b1, flows, first, last):
    """תשואה בתקופה: אף פעם לא מספר מדויק כשיש תנועות; טווח מסומן או סיבה שאינו ניתן לחישוב."""
    days = (last - first).days
    block = {"exact": None, "days": days, "documented_flow_count": len(flows), "undocumented_flows_possible": True}
    change = b1 - b0 - sum(f for _, f in flows)
    if days < MIN_RETURN_DAYS:
        return {**block, "status": "period_too_short", "range": None, "annualized_range": None}
    if b0 <= 0:
        return {**block, "status": "start_balance_not_positive", "range": None, "annualized_range": None}
    positive = sum(f for _, f in flows if f > 0)
    negative = sum(f for _, f in flows if f < 0)
    denominators = (b0 + negative, b0 + positive)             # תזמון קיצוני של התנועות בתוך התקופה (מוקדם / מאוחר)
    if min(denominators) <= 0:
        return {**block, "status": "undefined_denominator", "range": None, "annualized_range": None}
    bounds = sorted(change / d for d in denominators)
    annual = None
    if days >= MIN_ANNUALIZE_DAYS:
        annual = [(1 + r) ** (365 / days) - 1 if r > -1 else None for r in bounds]
        annual = {"low": annual[0], "high": annual[1]} if None not in annual else None
    return {**block, "status": "approximate_range", "range": {"low": bounds[0], "high": bounds[1]}, "annualized_range": annual}


def _account_row(acc, events, today, p):
    aid = acc["id"]
    row = {"id": aid, "name": acc.get("name"), "status": "no_snapshot", "missing": [], "verification": None}
    snaps = sorted((e for e in events if e["kind"] == "balance_snapshot" and e["account"] == aid and e["day"] <= today),
                   key=lambda e: (e["day"], e["id"]))
    if not snaps:
        return row, None
    first, last = snaps[0], snaps[-1]
    row.update(latest_balance={"value": last["amount"], "as_of": last["day"].isoformat()}, verification=last["verification"])
    if last["day"] <= first["day"]:
        row["status"] = "single_snapshot"
        return row, None
    months = _month_index(last["day"]) - _month_index(first["day"])
    row.update(start_balance={"value": first["amount"], "as_of": first["day"].isoformat()}, window={"from": first["day"].isoformat(),
               "to": last["day"].isoformat(), "months": months})
    window = [e for e in events if e["kind"] in _FLOW_KINDS and aid in (e["account"], e["counter"]) and first["day"] < e["day"] < last["day"]]
    same_day = sum(1 for e in events if e["kind"] in _FLOW_KINDS and aid in (e["account"], e["counter"]) and e["day"] in (first["day"], last["day"]))
    sums = {"deposit": 0.0, "withdrawal": 0.0, "fee": 0.0, "transfer_in": 0.0, "transfer_out": 0.0}
    counts = dict.fromkeys(sums, 0)
    flows = []
    for e in window:
        key = e["kind"] if e["kind"] != "transfer" else ("transfer_out" if e["account"] == aid else "transfer_in")
        sums[key] += e["amount"]
        counts[key] += 1
        flows.append((e["day"], e["amount"] if key in ("deposit", "transfer_in") else -e["amount"]))
    net = round(sum(f for _, f in flows), 2)
    deposit_events = counts["deposit"]
    row["flows"] = {"deposits": round(sums["deposit"], 2) if deposit_events else None, "deposit_count": deposit_events,
                    "withdrawals": round(sums["withdrawal"], 2), "fees": round(sums["fee"], 2),
                    "transfers_in": round(sums["transfer_in"], 2), "transfers_out": round(sums["transfer_out"], 2),
                    "net_documented": net, "event_count": len(window), "same_day_events": same_day}
    if not deposit_events:
        row["missing"].append("deposit_events")
    change = last["amount"] - first["amount"]
    row["value_change"] = {"total": round(change, 2), "documented_flows": net, "unexplained": round(change - net, 2),
                           "note": "השינוי שאינו מוסבר כולל תשואה, ריבית ותנועות שלא תועדו — אינו תשואה מאומתת"}
    row["return"] = _return_block(first["amount"], last["amount"], flows, first["day"], last["day"])
    monthly = _valid(acc.get("planned_monthly_deposit"), 0, 10_000_000)
    expected = _valid(acc.get("expected_return_pct"), -50, 50)
    fee = _valid(acc.get("management_fee_pct"), 0, 10)
    if expected is None:
        row["missing"].append("expected_return")
    if fee is None:
        row["missing"].append("management_fee")
    if months < 1:
        row["status"] = "short_period"
        return row, {"b0": first["amount"], "b1": last["amount"], "months": months, "net": net, "deposit_events": deposit_events}
    row["status"] = "compared"
    if monthly is None:
        row["missing"].append("planned_monthly_deposit")
        row["planned"] = None
        row["deviation"] = None
        return row, {"b0": first["amount"], "b1": last["amount"], "months": months, "net": net, "deposit_events": deposit_events}
    annual_return = expected / 100 if expected is not None else p["annual_return"]
    annual_fee = fee / 100 if fee is not None else p["annual_fee"]
    years = max(10, math.ceil(max(months, _month_index(today) - _month_index(first["day"])) / 12))
    sim = _run(first["amount"], monthly, annual_return, annual_fee, p["inflation"], years, first["day"].replace(day=1).isoformat())["monthly"]
    planned_at_last = sim[months - 1]["value_after_costs"]
    months_today = _month_index(today) - _month_index(first["day"])
    deposits_only = first["amount"] + monthly * months
    planned_deposits = monthly * months
    row["planned"] = {
        "monthly_deposit": monthly, "return_pct": annual_return * 100, "return_source": "account" if expected is not None else "default",
        "fee_pct": annual_fee * 100, "fee_source": "account" if fee is not None else "default",
        "deposits_total": round(planned_deposits, 2), "value_at_comparison": round(planned_at_last, 2),
        "value_deposits_only": round(deposits_only, 2),
        "value_to_date": round(sim[months_today - 1]["value_after_costs"], 2) if months_today >= 1 else None,
        "to_date": today.isoformat(),
    }
    row["deviation"] = {
        "vs_plan": round(last["amount"] - planned_at_last, 2), "vs_deposits_only": round(last["amount"] - deposits_only, 2),
        "deposits_gap": round(sums["deposit"] - planned_deposits, 2) if deposit_events else None,
    }
    return row, {"b0": first["amount"], "b1": last["amount"], "months": months, "net": net, "deposit_events": deposit_events, "monthly": monthly,
                 "planned_at_last": planned_at_last, "deposits_only": deposits_only, "planned_deposits": planned_deposits,
                 "deposits": sums["deposit"], "withdrawals": sums["withdrawal"], "fees": sums["fee"],
                 "transfers_in": sums["transfer_in"], "transfers_out": sums["transfer_out"], "unexplained": change - net}


def _series(result):
    return [{"year": r["year"], "nominal": r["value_after_costs"], "real": r["real_value"], "contributions": r["contributions"]} for r in result["annual"]]


def _consolidated(rows, facts):
    compared = [f for f in facts if f and "planned_at_last" in f]
    out = {"accounts_compared": len([r for r in rows if r["status"] in ("compared", "short_period")]),
           "accounts_with_plan": len(compared), "accounts_without_plan": len([r for r in rows if r["status"] == "compared" and r.get("planned") is None]),
           "accounts_without_snapshot": len([r for r in rows if r["status"] == "no_snapshot"]),
           "accounts_single_snapshot": len([r for r in rows if r["status"] == "single_snapshot"]),
           "accounts_short_period": len([r for r in rows if r["status"] == "short_period"])}
    if not compared:
        return {**out, "deviation": None}
    s = lambda k: round(sum(f[k] for f in compared), 2)           # noqa: E731
    windows = [r["window"] for r in rows if r["status"] == "compared" and r.get("planned")]
    deposits_complete = all(f["deposit_events"] for f in compared)
    return {**out,
            "window": {"from": min(w["from"] for w in windows), "to": max(w["to"] for w in windows)},
            "start_balance": s("b0"), "latest_balance": s("b1"),
            "planned": {"deposits_total": s("planned_deposits"), "value_at_comparison": s("planned_at_last"), "value_deposits_only": s("deposits_only")},
            "flows": {"deposits": s("deposits") if deposits_complete else None, "deposits_complete": deposits_complete,
                      "withdrawals": s("withdrawals"), "fees": s("fees"), "transfers_in": s("transfers_in"), "transfers_out": s("transfers_out"),
                      "net_documented": s("net")},
            "value_change": {"total": round(s("b1") - s("b0"), 2), "documented_flows": s("net"), "unexplained": s("unexplained")},
            "deviation": {"vs_plan": round(s("b1") - s("planned_at_last"), 2), "vs_deposits_only": round(s("b1") - s("deposits_only"), 2),
                          "deposits_gap": round(s("deposits") - s("planned_deposits"), 2) if deposits_complete else None},
            "return": {"exact": None, "status": "not_computed_consolidated", "note": "תשואה מחושבת לכל חשבון בנפרד; אין תשואה מאוחדת מדויקת"}}


def _forecast(initial, as_of_oldest, planned_monthly, actual_monthly, goal_monthly, p):
    years = p["years"]

    def line(monthly, source):
        if monthly is None:
            return None
        result = simulate(Scenario(years=years, initial=initial, monthly_contribution=monthly, inflation=p["inflation"],
                                   assets=(Asset(annual_return=p["annual_return"], annual_fee=p["annual_fee"]),)))
        return {"source": source, "monthly_deposit": monthly, "final_nominal": result["final"]["value_after_costs"],
                "final_real": result["final"]["real_value"], "series": _series(result)}

    lines = {"planned_pace": line(planned_monthly, "planned_monthly_deposits"),
             "actual_pace": line(actual_monthly, "documented_flows_per_month"),
             "goal_history_pace": line(goal_monthly, "savings_history_monthly_average")}
    gaps = {}
    for name in ("actual_pace", "goal_history_pace"):
        if lines[name] and lines["planned_pace"]:
            gaps[f"{name}_vs_planned_pace"] = lines[name]["final_nominal"] - lines["planned_pace"]["final_nominal"]
    return {"applied": True, "horizon_years": years, "starting_value": round(initial, 2), "oldest_snapshot": as_of_oldest,
            "label": EXTRAPOLATION_LABEL,
            "assumptions": {"annual_return_pct": p["annual_return"] * 100, "annual_fee_pct": p["annual_fee"] * 100, "inflation_pct": p["inflation"] * 100,
                            "note": "אותן הנחות לכל הקווים; ההון ההתחלתי הוא סכום היתרות האחרונות המדווחות; אין מס"},
            "lines": lines, "gaps": gaps}


def _correction(initial, forecast, p):
    """המחשה ניטרלית: איך שינוי בהפקדה החודשית הכוללת משנה את סוף האופק. הסכום לינארי בהפקדה, לכן שיפוע מהרצות מנוע."""
    actual, planned = forecast["lines"]["actual_pace"], forecast["lines"]["planned_pace"]
    if actual is None:
        return {"applied": False, "reason": forecast.get("actual_pace_unavailable_reason") or "no_actual_pace"}

    def final(monthly):
        return simulate(Scenario(years=p["years"], initial=initial, monthly_contribution=max(monthly, 0.0), inflation=p["inflation"],
                                 assets=(Asset(annual_return=p["annual_return"], annual_fee=p["annual_fee"]),)))["final"]["value_after_costs"]

    slope = (final(1000.0) - final(0.0)) / 1000.0
    base = actual["final_nominal"]
    rows = [{"monthly_change": step, "monthly_deposit": max(actual["monthly_deposit"] + step, 0.0),
             "final_nominal": final(actual["monthly_deposit"] + step),
             "delta_vs_updated_forecast": final(actual["monthly_deposit"] + step) - base}
            for step in CORRECTION_STEPS if actual["monthly_deposit"] + step >= 0]
    needed = None
    if planned is not None and slope > 0:
        needed = (planned["final_nominal"] - base) / slope
    return {"applied": True, "base_monthly_deposit": actual["monthly_deposit"], "rows": rows,
            "monthly_change_to_match_planned_end": needed,
            "note": "המחשה ניטרלית של השפעת שינוי בהפקדה החודשית הכוללת על סוף האופק, מהנחות התחזית המוצגות — אינה המלצה ואינה תחזית."}


def build_pace_view(inputs: dict, params=None, today: date | None = None) -> dict:
    """קלט: `inputs` שנבנה בשרת מנתוני הבעלים עצמו (accounts, events, savings_history); פלט: JSON מלא להצגה. טהור."""
    p = normalize_params(params)
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be an object")
    today = today or _day(inputs.get("as_of")) or date.today()
    accounts = [a for a in (inputs.get("accounts") or []) if isinstance(a, dict) and a.get("id")][:_MAX_ACCOUNTS]
    active = [a for a in accounts if a.get("status") != "closed"]
    events = _clean_events(inputs.get("events"), {a["id"] for a in accounts})
    rows, facts = [], []
    for acc in active:
        row, fact = _account_row(acc, events, today, p)
        rows.append(row)
        facts.append(fact)
    view = {"schema_version": PACE_SCHEMA_VERSION, "source": "portfolio_lab", "engine_version": ENGINE_VERSION, "currency": "ILS",
            "result_type": "assumption_based_projection", "data_basis": "self_reported", "as_of": today.isoformat(),
            "accounts": rows, "consolidated": _consolidated(rows, facts),
            "closed_accounts": len(accounts) - len(active), "skipped_events": int(inputs.get("skipped_events") or 0)}
    with_value = [r for r in rows if r.get("latest_balance")]
    if not with_value:
        view["forecast"] = {"applied": False, "reason": "no_balances"}
        view["course_correction"] = {"applied": False, "reason": "no_forecast"}
    else:
        initial = sum(r["latest_balance"]["value"] for r in with_value)
        by_id = {a["id"]: a for a in active}
        planned_values = [_valid(by_id[r["id"]].get("planned_monthly_deposit"), 0, 10_000_000) for r in with_value]
        planned_monthly = sum(v for v in planned_values if v is not None) if any(v is not None for v in planned_values) else None
        paces = [f["net"] / f["months"] for f in facts if f and f["months"] >= 1 and (f["deposit_events"] or f["net"] != 0)]
        actual_monthly = round(sum(paces), 2) if paces else None
        actual_reason = None if paces else "no_documented_flows"
        if actual_monthly is not None and actual_monthly < 0:      # המנוע אינו מדמה משיכות — לא מייצרים קו מומצא
            actual_monthly, actual_reason = None, "negative_net_flow_not_modelled"
        goal = inputs.get("savings_history") or {}
        goal_monthly = _valid(goal.get("monthly_average"), 0, 1e9)
        view["forecast"] = _forecast(initial, min(r["latest_balance"]["as_of"] for r in with_value), planned_monthly, actual_monthly, goal_monthly, p)
        view["forecast"]["actual_pace_unavailable_reason"] = actual_reason if actual_monthly is None else None
        view["forecast"]["coverage"] = {
            "accounts_with_balance": len(with_value),
            "accounts_with_planned_deposit": sum(v is not None for v in planned_values),
            "accounts_with_actual_pace": len(paces),
            "planned_missing_is_not_zero": True,
        }
        view["goal_level_history"] = ({k: goal.get(k) for k in ("ytd", "ytd_plan", "ytd_gap", "months_elapsed", "monthly_average", "streak")}
                                      if goal else None)
        view["course_correction"] = _correction(initial, view["forecast"], p)
    view["assumptions"] = [
        "כל הנתונים הם דיווח עצמי של הבעלים (יתרות והפקדות), לא מאומתים מול בנק/גוף מנהל.",
        "ההשוואה לתוכנית נעשית בתאריך הצילום האחרון של כל חשבון; הון מתוכנן = יתרת הפתיחה + הפקדה חודשית מתוכננת (הנוכחית) × חודשים קלנדריים, בהנחת התשואה המוצגת.",
        "אירוע בתאריך של צילום יתרה (ראשון/אחרון) אינו נספר כתנועה — לא ידוע אם נכלל ביתרה.",
        "שינוי שאינו מוסבר = שינוי שווי פחות תנועות מתועדות; אינו תשואה מאומתת. תשואה מדויקת אינה מחושבת כשיש תנועות בין היתרות — מוצג טווח מסומן.",
        EXTRAPOLATION_LABEL + ".",
    ]
    return view
