"""תחזית לכל חשבון וסכום מאוחד (D1 שלב 7 / A1) — שכבת הרכבה בלבד מעל המנוע.

המנוע (`portfolio_lab.engine.simulate`) לא משתנה: לכל חשבון פעיל עם יתרה מדווחת מורצת סימולציה אחת, והסכום המאוחד הוא
סכום תוצאות המנוע לפי שנה (צבירה, לא חישוב פיננסי חדש). ללא I/O, Airtable, LLM או כתיבה.

עקרונות (FAMILY_WEALTH_ACCOUNTS_SPEC §5): נקודת המוצא היא עובדה (צילום היתרה האחרון) ותמיד מתויגת עם תאריכה; כל השאר הנחות
של הבעלים (תשואה, אינפלציה, הפקדה חודשית פר חשבון — ברירת מחדל 0, לא נגזרת ולא מומצאת). חשבון בלי צילום או סגור אינו נכנס
לתחזית ונספר בנפרד. דמי ניהול: `Management Fee %` של החשבון אם הוזן, אחרת ברירת המחדל מהקלט (ומסומן).
"""

from __future__ import annotations

import math
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


def _eligible(account: dict) -> bool:
    return account.get("status") != "closed" and bool(account.get("balance")) and account["balance"].get("value") is not None


def build_accounts_forecast(view: dict, params: dict | None = None, today: date | None = None) -> dict:
    """``view`` = the owner's ``accounts_overview`` output (already owner-scoped). Raises ValueError on invalid params."""
    p = normalize_params(params)
    today = today or date.today()
    start = today.replace(day=1).isoformat()
    accounts = [a for a in (view or {}).get("accounts") or [] if isinstance(a, dict)]
    eligible = [a for a in accounts if _eligible(a)]
    known = {a.get("id") for a in accounts}
    if set(p["monthly_contributions"]) - known:
        raise ValueError("monthly_contributions has an unknown account")
    rows, series_total = [], {}
    for a in eligible:
        fee, fee_source = _fee(a, p["annual_fee"])
        monthly = p["monthly_contributions"].get(a["id"], 0.0)
        result = simulate(Scenario(
            years=p["years"], initial=float(a["balance"]["value"]), monthly_contribution=monthly, inflation=p["inflation"],
            deposit_timing=p["deposit_timing"], start_date=start,
            assets=(Asset(name="account", annual_return=p["annual_return"], annual_fee=fee),)))
        series = [{"year": r["year"], "nominal": r["value_after_costs"], "real": r["real_value"], "invested": r["contributions"]}
                  for r in result["annual"]]
        for r in series:
            t = series_total.setdefault(r["year"], {"year": r["year"], "nominal": 0.0, "real": 0.0, "invested": 0.0})
            for key in ("nominal", "real", "invested"):
                t[key] += r[key]
        final = result["final"]
        rows.append({
            "id": a["id"], "name": a.get("name"), "account_type": a.get("account_type"),
            "start_value": a["balance"]["value"], "start_as_of": a["balance"]["as_of"], "verification": a["balance"].get("verification"),
            "monthly_contribution": monthly, "fee_pct": round(fee * 100, 4), "fee_source": fee_source,
            "final_nominal": final["value_after_costs"], "final_real": final["real_value"],
            "invested": final["contributions"], "nominal_profit": final["nominal_profit"], "costs_paid": final["costs_paid"],
            "series": series,
        })
    total_series = [{k: (round(v, 2) if k != "year" else v) for k, v in series_total[y].items()} for y in sorted(series_total)]
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
        "all_self_reported": t.get("all_self_reported"),
        "warnings": ["תחזית מבוססת הנחות — לא הבטחת תשואה ולא המלצת השקעה.",
                     "נקודת המוצא היא היתרה האחרונה שדווחה בכל חשבון, בתאריך שלה; אין עדכון אוטומטי מבנק או מקרן.",
                     "הפקדה חודשית פר חשבון היא הנחה שהוזנה (ברירת מחדל 0), לא נגזרת מהפקדות בפועל. ״סך שהושקע״ כולל את נקודת המוצא.",
                     "לא כולל מס, משיכות או אילוצי נזילות."],
        "as_of": today.isoformat(),
    }
