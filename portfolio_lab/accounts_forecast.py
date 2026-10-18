"""תחזית לכל חשבון וסכום מאוחד (D1 שלב 7 / A1) — שכבת הרכבה בלבד מעל המנוע.

המנוע (`portfolio_lab.engine.simulate`) לא משתנה: לכל חשבון פעיל עם יתרה מדווחת מורצת סימולציה אחת, והסכום המאוחד הוא
סכום תוצאות המנוע לפי שנה (צבירה, לא חישוב פיננסי חדש). ללא I/O, Airtable, LLM או כתיבה.

עקרונות (FAMILY_WEALTH_ACCOUNTS_SPEC §5): נקודת המוצא היא עובדה (צילום היתרה האחרון) ותמיד מתויגת עם תאריכה; כל השאר הנחות
של הבעלים (תשואה, אינפלציה, הפקדה חודשית פר חשבון — ברירת מחדל 0, לא נגזרת ולא מומצאת). חשבון בלי צילום או סגור אינו נכנס
לתחזית ונספר בנפרד. דמי ניהול: `Management Fee %` של החשבון אם הוזן, אחרת ברירת המחדל מהקלט (ומסומן).

תשומות לכל חשבון (D1 שלב 9) — ערך שהבעלים הזין בחשבון גובר על ברירת מחדל, וכל מקור מסומן; ריק = "חסר לדיוק", לא מומצא:
הפקדה חודשית (הקלדה במסך > `Planned Monthly Deposit` > 0), דמי ניהול מהפקדה (מנוכים מההפקדה לפני המנוע; ה"הושקע" ברוטו),
תשואה (`Expected Return %`; ריאלית כש־Linkage=cpi ואז מומרת לנומינלית בהנחת האינפלציה), עלות ביטוח חודשית קבועה (נומינלית).

נזילות וכיסוי מטרות (D1 שלב 10 / A2): לכל חודש כל חשבון נמצא באחד משלושה מצבים — `accessible` (נזילות מאומתת: רק חשבון שסומן
`immediate` ואינו מוצר פרישה), `conditional` (תאריך שחרור הגיע או נזילות לא מאומתת — אין להסיק זכאות למשיכה מגיל/תאריך בלבד),
`locked`. תמיד `accessible + conditional + locked = שווי מאוחד`. כיסוי מטרה משתמש רק ב-`accessible`, בערך נומינלי בסוף החודש האחרון שהושלם עד תאריך היעד
(שורות חודשיות מהמנוע; הפקדות וצמיחה שאחרי תאריך היעד אינן נספרות); זה כיסוי פוטנציאלי ולא הקצאה — אותו כסף עשוי להופיע בכיסוי של כמה מטרות עד B2. ללא מס/משיכות (A3).
"""

from __future__ import annotations

import math
from calendar import monthrange
from datetime import date

from .engine import simulate
from .models import ENGINE_VERSION, Asset, Scenario

FORECAST_SCHEMA_VERSION = "1.0"
DEFAULTS = {
    "years": 20,
    "annual_return_pct": 6.0,
    "annual_fee_pct": 0.15,
    "inflation_pct": 2.0,
    "deposit_timing": "end",
    "monthly_contributions": {},
}
_MAX_ACCOUNTS = 50
GOAL_CATEGORIES = {"long_term", "emergency_fund", "investment", "savings"}
RETIREMENT_TYPES = {"pension", "managers_insurance"}          # מוצרי פרישה: לעולם לא `accessible` כסכום חד-פעמי
STATES = ("accessible", "conditional", "locked")
LINKAGES = {"none", "cpi", "sp500", "other_index", "fx", "unknown"}
TRACKS = {"equities", "bonds", "mixed", "index_tracking", "money_market", "unknown"}


def _number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be from {minimum} to {maximum}")
    return float(value)


def normalize_params(params) -> dict:
    """קלט גולמי (אחוזים כפי שמוצגים במסך) -> קלט מנורמל; ValueError על קלט לא תקף."""
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    years = params.get("years", DEFAULTS["years"])
    if isinstance(years, bool) or not isinstance(years, int) or not 10 <= years <= 100:
        raise ValueError("years must be an integer from 10 to 100")
    timing = params.get("deposit_timing", DEFAULTS["deposit_timing"])
    if timing not in {"begin", "end"}:
        raise ValueError("deposit_timing must be begin or end")
    contributions = params.get("monthly_contributions", {})
    if not isinstance(contributions, dict) or len(contributions) > _MAX_ACCOUNTS:
        raise ValueError("monthly_contributions must be an object of account id -> amount")
    clean = {}
    for account_id, amount in contributions.items():
        if not isinstance(account_id, str) or not account_id.startswith("rec") or len(account_id) > 40:
            raise ValueError("monthly_contributions keys must be account ids")
        clean[account_id] = _number(amount, "monthly_contributions", 0, 10_000_000)
    return {
        "years": years, "deposit_timing": timing, "monthly_contributions": clean,
        "annual_return": _number(params.get("annual_return_pct", DEFAULTS["annual_return_pct"]), "annual_return_pct", -50, 50) / 100,
        "annual_fee": _number(params.get("annual_fee_pct", DEFAULTS["annual_fee_pct"]), "annual_fee_pct", 0, 10) / 100,
        "inflation": _number(params.get("inflation_pct", DEFAULTS["inflation_pct"]), "inflation_pct", -50, 50) / 100,
    }


def _fee(account: dict, default_fee: float) -> tuple[float, str]:
    """(fee as a fraction, source). The account's own fee wins when it is a sane number; otherwise the screen's default, labelled."""
    own = account.get("management_fee_pct")
    if isinstance(own, (int, float)) and not isinstance(own, bool) and math.isfinite(own) and 0 <= own <= 10:
        return own / 100, "account"
    return default_fee, "default"


def _valid(value, minimum, maximum):
    """ערך חשבון תקף (מספר סופי בטווח) או None — ערך פגום לעולם לא נכנס לחישוב ומופיע כחסר."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value) if minimum <= value <= maximum else None


def _account_inputs(account: dict, p: dict, typed: dict) -> dict:
    """תשומות החשבון + מקור כל אחת + מה שחסר. טהור."""
    fee, fee_source = _fee(account, p["annual_fee"])
    if account["id"] in typed:
        monthly, monthly_source = typed[account["id"]], "typed"
    else:
        planned = _valid(account.get("planned_monthly_deposit"), 0, 10_000_000)
        monthly, monthly_source = (planned, "account") if planned is not None else (0.0, "default")
    deposit_fee = _valid(account.get("deposit_fee_pct"), 0, 10)
    expected = _valid(account.get("expected_return_pct"), -50, 50)
    linkage = account.get("linkage") if account.get("linkage") in LINKAGES else None
    if expected is None:
        annual_return, return_source, return_kind = p["annual_return"], "default", "nominal"
    elif linkage == "cpi":
        annual_return, return_source, return_kind = (1 + expected / 100) * (1 + p["inflation"]) - 1, "account", "real_to_nominal"
    else:
        annual_return, return_source, return_kind = expected / 100, "account", "nominal"
    insurance = _valid(account.get("insurance_cost_monthly"), 0, 1_000_000)
    as_of = account.get("insurance_cost_as_of") if isinstance(account.get("insurance_cost_as_of"), str) else None
    track = account.get("investment_track") if account.get("investment_track") in TRACKS else None
    missing = []
    if fee_source == "default":
        missing.append("management_fee")
    if deposit_fee is None:
        missing.append("deposit_fee")
    if expected is None:
        missing.append("expected_return")
    if monthly_source == "default":
        missing.append("monthly_deposit")
    if track in (None, "unknown"):
        missing.append("investment_track")
    if linkage in (None, "unknown"):
        missing.append("linkage")
    if insurance is None:
        missing.append("insurance_cost")
    elif not as_of:
        missing.append("insurance_cost_date")
    return {"fee": fee, "fee_source": fee_source, "monthly": monthly, "monthly_source": monthly_source,
            "deposit_fee": deposit_fee or 0.0, "deposit_fee_known": deposit_fee is not None,
            "annual_return": annual_return, "return_source": return_source, "return_kind": return_kind,
            "return_input_pct": expected, "linkage": linkage, "track": track, "insurance": insurance or 0.0,
            "insurance_known": insurance is not None, "insurance_as_of": as_of, "missing": missing}


def _iso_date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _liquidity_profile(account: dict) -> dict:
    """סיווג נזילות של חשבון מהשדות הקיימים בלבד (`Liquidity`, `Liquid From`, `Account Type`). טהור; לא מסיק זכאות."""
    liq = account.get("liquidity")
    released = _iso_date(account.get("liquid_from"))
    retirement = account.get("account_type") in RETIREMENT_TYPES
    if liq == "immediate":
        basis = "retirement_immediate" if retirement else "immediate"
        return {"basis": basis, "liquid_from": None, "gap": None, "ceiling": "conditional" if retirement else "accessible"}
    if liq in ("locked_until_date", "age_based"):
        if released is None:
            return {"basis": "undated", "liquid_from": None, "gap": "liquid_from", "ceiling": "locked"}
        return {"basis": "dated", "liquid_from": released, "gap": None, "ceiling": "conditional"}
    return {"basis": "unverified", "liquid_from": None, "gap": "liquidity", "ceiling": "conditional"}


def _state_at(profile: dict, month_end: date) -> str:
    """מצב החשבון בסוף חודש: dated נפתח ל-conditional כשסוף החודש ≥ תאריך השחרור (לא accessible לעולם); undated נעול; unverified מותנה."""
    basis = profile["basis"]
    if basis == "immediate":
        return "accessible"
    if basis == "dated":
        return "conditional" if month_end >= profile["liquid_from"] else "locked"
    return profile["ceiling"]


def _month_end(d: date) -> date:
    return d.replace(day=monthrange(d.year, d.month)[1])


def _goal_number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 else None


def _goal_coverage(goals, start: date, years: int, month_totals: list[dict], immediate_totals: list[float], has_accessible: bool, has_immediate: bool):
    """כיסוי פוטנציאלי לכל מטרה מאושרת. `accessible` בלבד; קרן חירום — רק חשבונות `immediate` מאומתים. לא הקצאה, לא המלצה."""
    items, skipped = [], {"other_category": 0, "inactive": 0}
    for g in goals or []:
        if not isinstance(g, dict):
            continue
        if g.get("status") not in (None, "active"):
            skipped["inactive"] += 1
            continue
        if g.get("category") not in GOAL_CATEGORIES:
            skipped["other_category"] += 1
            continue
        item = {"id": g.get("id"), "title": g.get("title"), "category": g.get("category"), "target_amount": None, "due_month": None,
                "verdict": "not_comparable", "reason": None, "gap": None, "value_as_of": None, "accessible_value": None, "conditional_value": None, "locked_value": None}
        target, due = _goal_number(g.get("target_amount")), _iso_date(g.get("end_date"))
        item["target_amount"] = target
        if due is not None:
            item["due_month"] = due.strftime("%Y-%m")
        idx = None if due is None else (due.year - start.year) * 12 + (due.month - start.month)
        # ערך הכיסוי נקרא מסוף החודש האחרון שהושלם עד תאריך היעד (שמרני): הפקדה/צמיחה שאחרי התאריך — גם באותו חודש — לא נספרות.
        slot = None if due is None or idx < 0 or idx >= years * 12 else (idx + 1 if due >= _month_end(due) else idx)
        emergency = g.get("category") == "emergency_fund"
        if target is None:
            item["reason"] = "missing_target"
        elif due is None:
            item["reason"] = "missing_date"
        elif idx < 0:
            item["reason"] = "past_date"
        elif idx >= years * 12:
            item["reason"] = "beyond_horizon"
        elif not (has_immediate if emergency else has_accessible):
            item["reason"] = "no_verified_accessible_account"
            row = month_totals[slot]                      # מידע בלבד: כמה מותנה/נעול בחודש הקריאה — אינו נספר לכיסוי
            item.update(value_as_of=row["as_of"], conditional_value=round(row["conditional"], 2), locked_value=round(row["locked"], 2))
        else:
            row = month_totals[slot]
            accessible = immediate_totals[slot] if emergency else row["accessible"]
            item.update(value_as_of=row["as_of"], accessible_value=round(accessible, 2), conditional_value=round(row["conditional"], 2), locked_value=round(row["locked"], 2))
            if accessible + 0.005 >= target:
                item["verdict"] = "covered"
            else:
                item.update(verdict="short", gap=round(target - accessible, 2))
        items.append(item)
    return items, skipped


def _eligible(account: dict) -> bool:
    return account.get("status") != "closed" and bool(account.get("balance")) and account["balance"].get("value") is not None


def build_accounts_forecast(view: dict, params: dict | None = None, today: date | None = None, goals: list | None = None) -> dict:
    """``view`` = the owner's ``accounts_overview`` output (already owner-scoped); ``goals`` = the owner's own goals (id/title/category/status/
target_amount/end_date), passed in so this module stays free of I/O. Raises ValueError on invalid params."""
    p = normalize_params(params)
    today = today or date.today()
    start = today.replace(day=1).isoformat()
    accounts = [a for a in (view or {}).get("accounts") or [] if isinstance(a, dict)]
    eligible = [a for a in accounts if _eligible(a)]
    known = {a.get("id") for a in accounts}
    if set(p["monthly_contributions"]) - known:
        raise ValueError("monthly_contributions has an unknown account")
    rows, series_total = [], {}
    gaps = []
    months = p["years"] * 12
    # אינדקס 0 = יתרת הפתיחה (לפני כל צמיחה/הפקדה), אינדקס k+1 = סוף חודש k של המנוע; כך אפשר לקרוא "סוף החודש האחרון שהושלם עד תאריך יעד"
    month_totals = [{"accessible": 0.0, "conditional": 0.0, "locked": 0.0, "total": 0.0, "as_of": None} for _ in range(months + 1)]
    immediate_totals = [0.0] * (months + 1)
    start_day = date.fromisoformat(start)
    has_accessible = has_immediate = False
    for a in eligible:
        x = _account_inputs(a, p, p["monthly_contributions"])
        fee, fee_source, monthly = x["fee"], x["fee_source"], x["monthly"]
        net_monthly = monthly * (1 - x["deposit_fee"] / 100)
        result = simulate(Scenario(
            years=p["years"], initial=float(a["balance"]["value"]), monthly_contribution=net_monthly, inflation=p["inflation"],
            deposit_timing=p["deposit_timing"], start_date=start, monthly_fixed_cost=x["insurance"],
            assets=(Asset(name="account", annual_return=x["annual_return"], annual_fee=fee),)), monthly=True)
        profile = _liquidity_profile(a)
        has_accessible = has_accessible or profile["ceiling"] == "accessible"
        has_immediate = has_immediate or profile["basis"] == "immediate"
        points = [{"slot": 0, "as_of": today, "value": float(a["balance"]["value"])}] + [
            {"slot": m["month"] + 1, "as_of": date.fromisoformat(m["as_of"]), "value": m["value_after_costs"]} for m in result["monthly"]]
        for pt in points:
            row = month_totals[pt["slot"]]
            row[_state_at(profile, pt["as_of"])] += pt["value"]
            row["total"] += pt["value"]
            row["as_of"] = pt["as_of"].isoformat()
            if profile["basis"] == "immediate":
                immediate_totals[pt["slot"]] += pt["value"]
        x["missing"] = x["missing"] + ([profile["gap"]] if profile["gap"] else [])
        initial = float(a["balance"]["value"])
        series = [{"year": r["year"], "nominal": r["value_after_costs"], "real": r["real_value"],
                   "invested": initial + monthly * 12 * r["year"]} for r in result["annual"]]
        for r in series:
            t = series_total.setdefault(r["year"], {"year": r["year"], "nominal": 0.0, "real": 0.0, "invested": 0.0})
            for key in ("nominal", "real", "invested"):
                t[key] += r[key]
        final = result["final"]
        invested = initial + monthly * 12 * p["years"]
        deposit_fees = monthly * (x["deposit_fee"] / 100) * 12 * p["years"]
        rows.append({
            "id": a["id"], "name": a.get("name"), "account_type": a.get("account_type"),
            "start_value": a["balance"]["value"], "start_as_of": a["balance"]["as_of"], "verification": a["balance"].get("verification"),
            "monthly_contribution": monthly, "monthly_contribution_source": x["monthly_source"],
            "fee_pct": round(fee * 100, 4), "fee_source": fee_source,
            "deposit_fee_pct": x["deposit_fee"], "deposit_fee_known": x["deposit_fee_known"],
            "return_pct": round(x["annual_return"] * 100, 4), "return_source": x["return_source"], "return_kind": x["return_kind"],
            "linkage": x["linkage"], "investment_track": x["track"],
            "insurance_cost_monthly": x["insurance"], "insurance_cost_known": x["insurance_known"], "insurance_cost_as_of": x["insurance_as_of"],
            "final_nominal": final["value_after_costs"], "final_real": final["real_value"],
            "invested": invested, "nominal_profit": final["value_after_costs"] - invested,
            "costs_paid": final["costs_paid"] + deposit_fees, "deposit_fees_paid": round(deposit_fees, 2),
            "insurance_paid": round(final.get("fixed_cost", 0.0), 2),
            "liquidity": {"basis": profile["basis"], "liquid_from": profile["liquid_from"].isoformat() if profile["liquid_from"] else None,
                          "state_now": _state_at(profile, date.fromisoformat(result["monthly"][0]["as_of"])),
                          "state_at_horizon": _state_at(profile, date.fromisoformat(result["monthly"][-1]["as_of"]))},
            "missing": x["missing"],
            "series": series,
        })
        if x["missing"]:
            gaps.append({"id": a["id"], "name": a.get("name"), "missing": x["missing"]})
    total_series = [{k: (round(v, 2) if k != "year" else v) for k, v in series_total[y].items()} for y in sorted(series_total)]
    for point in total_series:                                  # יתרת הסכום מחושבת כך ש-נגיש + מותנה + נעול = מאוחד בדיוק של אגורה
        row = month_totals[point["year"] * 12]
        parts = {k: round(row[k], 2) for k in STATES}
        residue = round(point["nominal"] - sum(parts.values()), 2)          # at most an agora or two from independent rounding
        if residue:
            parts[max(parts, key=parts.get)] = round(parts[max(parts, key=parts.get)] + residue, 2)
        point.update(parts)
    goal_items, goals_skipped = _goal_coverage(goals, start_day, p["years"], month_totals, immediate_totals, has_accessible, has_immediate)
    last = total_series[-1] if total_series else None
    t = (view or {}).get("totals") or {}
    return {
        "schema_version": FORECAST_SCHEMA_VERSION, "engine_version": ENGINE_VERSION, "result_type": "assumption_based_projection",
        "start_date": start, "years": p["years"],
        "assumptions": {"annual_return_pct": round(p["annual_return"] * 100, 4), "annual_fee_pct_default": round(p["annual_fee"] * 100, 4),
                        "inflation_pct": round(p["inflation"] * 100, 4), "deposit_timing": p["deposit_timing"]},
        "accounts": rows,
        "consolidated": {
            "accounts": len(rows), "start_value": round(sum(r["start_value"] for r in rows), 2),
            "final_nominal": last["nominal"] if last else None, "final_real": last["real"] if last else None,
            "invested": last["invested"] if last else None, "series": total_series,
        },
        "excluded": {"without_snapshot": sum(1 for a in accounts if a.get("status") != "closed" and not _eligible(a)),
                     "closed": sum(1 for a in accounts if a.get("status") == "closed")},
        "data_gaps": gaps,
        "goals": goal_items, "goals_skipped": goals_skipped,
        "all_self_reported": t.get("all_self_reported"),
        "warnings": ["תחזית מבוססת הנחות — לא הבטחת תשואה ולא המלצת השקעה.",
                     "נקודת המוצא היא היתרה האחרונה שדווחה בכל חשבון, בתאריך שלה; אין עדכון אוטומטי מבנק או מקרן.",
                     "הפקדה חודשית פר חשבון היא הנחה: מה שהוקלד במסך, אחרת ״הפקדה חודשית מתוכננת״ שבחשבון, אחרת 0 — לא נגזרת מהפקדות בפועל. ״סך שהושקע״ כולל את נקודת המוצא ואת דמי הניהול מההפקדה.",
                     "תשואה שהוזנה בחשבון גוברת על ההנחה הכללית; בחשבון צמוד מדד היא ריאלית ומומרת לנומינלית בהנחת האינפלציה. הצמדה אחרת (מדד/מט״ח) אינה מדמה את המדד — תיעוד בלבד.",
                     "עלות ביטוח חודשית היא סכום נומינלי קבוע שהוזן; אינה מתעדכנת באינפלציה ואינה כוללת כיסוי משתנה לפי גיל.",
                     "נזילות היא סיווג בלבד: ״נגיש״ = חשבון שסומן נזיל מיד ואינו מוצר פרישה; ״מותנה״ = תאריך שחרור הגיע או שהנזילות לא אומתה — אין זכאות למשיכה מגיל או מתאריך בלבד; ״נעול״ = אחרת.",
                     "כיסוי מטרה הוא כיסוי פוטנציאלי בערך נומינלי בסוף החודש האחרון שהושלם עד תאריך היעד (כסף שהופקד רק אחריו אינו נספר) ומתבסס על ״נגיש״ בלבד; אינו הקצאת כספים למטרה — אותו כסף עשוי להופיע בכיסוי של כמה מטרות, עד שייקבע ייעוד חשבונות. אין כאן המלצת השקעה או משיכה.",
                     "לא כולל מס ולא משיכות בפועל."],
        "as_of": today.isoformat(),
    }
