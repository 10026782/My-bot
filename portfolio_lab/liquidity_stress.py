"""מבחן לחץ נזילות לקרן המשפחתית (E1a) — שכבה טהורה מעל Portfolio Lab, ללא I/O, Airtable או LLM.

המנוע (`portfolio_lab.engine.simulate`) לא משתנה: הוא ללא משיכות ולכן אינו יכול לבטא "מכירת יחידות אחרי ירידה".
כאן לולאה חודשית עצמאית ביחידות, שמשתמשת באותו נתיב תשואות (`crisis_asset_monthly`, אותו גורם חודשי ודמי ניהול);
התאמה למנוע מוכחת בבדיקת parity (test_portfolio_lab_liquidity_stress.py).

E1a: כרית נזילות בלבד, ללא הלוואה. שלושה אירועים מוצגים בנפרד: דרישת בטוחות (לא רלוונטית ללא הלוואה), מכירה כפויה, מחסור במזומן.
הון הילדים מופרד בקשיחות: אינו חלק מהקרן, אינו בטוחה ואינו מממן — קלט שמנסה אחרת נדחה, לא מתעלמים ממנו.
תוצאה בלבד לפי הנחות שהוזנו: ללא הסתברויות, ללא המלצה, ללא מס, ללא תנאי בנק.
"""

import hashlib
import json
import math

from .models import ENGINE_VERSION, Asset
from .simulator_view import crisis_asset_monthly

STRESS_SCHEMA_VERSION = "1.0"
RESULT_TYPE = "stress_scenario_under_stated_assumptions"
WINDOW_MONTHS = 24
MAX_HORIZON = 360
MAX_EVENTS_SHOWN = 60
DEFAULT_CUSHION_MONTHS = (0, 12, 24)
_EPS = 1e-9

DEFAULTS = {
    "fund_value": 3_000_000.0,
    "phase": "withdrawal",
    "monthly_deposit": 8000.0,
    "monthly_support": 10000.0,
    "other_monthly_expenses": 0.0,
    "other_monthly_income": 0.0,
    "annual_return_pct": 8.0,
    "annual_fee_pct": 0.15,
    "inflation_pct": 2.0,
    "cash_return_pct": 0.0,
    "horizon_months": 120,
}
_TOP_KEYS = set(DEFAULTS) | {"crisis", "cushion_modes", "cash_buckets", "protected_capital"}
_CRISIS_KEYS = {"decline_pct", "start_month", "recovery_years"}
_BUCKET_KEYS = {"free", "pledged", "family_earmarked"}
_UNSUPPORTED = {"loan": "loan is not supported in E1a (cushion-only stage)", "cushion_basis": "cushion_basis is fixed to net burn"}


def _num(params, key, minimum=None, maximum=None, default=None):
    value = params.get(key, DEFAULTS.get(key) if default is None else default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key} must be <= {maximum}")
    return float(value)


def _int(value, key, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _dict(value, key, allowed):
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{key}: unknown fields {sorted(unknown)}")
    return value


def normalize_params(params=None):
    """קלט גולמי (אחוזים כפי שמוצגים) → קלט מנורמל (שברים); ValueError על קלט לא תקף או על שדה לא נתמך."""
    params = {} if params is None else params
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    for key, reason in _UNSUPPORTED.items():
        if key in params:
            raise ValueError(reason)
    unknown = set(params) - _TOP_KEYS
    if unknown:
        raise ValueError(f"unknown fields {sorted(unknown)}")
    phase = params.get("phase", DEFAULTS["phase"])
    if phase not in ("accumulation", "withdrawal"):
        raise ValueError("phase must be accumulation or withdrawal")
    horizon = _int(params.get("horizon_months", DEFAULTS["horizon_months"]), "horizon_months", 1, MAX_HORIZON)
    p = {
        "fund_value": _num(params, "fund_value", 1, 1e12),
        "phase": phase,
        "deposit": _num(params, "monthly_deposit", 0, 1e9),
        "support": _num(params, "monthly_support", 0, 1e9),
        "other_expenses": _num(params, "other_monthly_expenses", 0, 1e9),
        "other_income": _num(params, "other_monthly_income", 0, 1e9),
        "annual_return": _num(params, "annual_return_pct", -50, 100) / 100,
        "annual_fee": _num(params, "annual_fee_pct", 0, 10) / 100,
        "inflation": _num(params, "inflation_pct", -10, 100) / 100,
        "cash_return": _num(params, "cash_return_pct", -50, 100) / 100,
        "horizon": horizon,
    }
    if p["annual_return"] <= -1 or p["annual_fee"] >= 1:
        raise ValueError("return/fee out of range")

    crisis = params.get("crisis")
    if crisis is None:
        p["crisis"] = None
    else:
        crisis = _dict(crisis, "crisis", _CRISIS_KEYS)
        if "decline_pct" not in crisis:
            raise ValueError("crisis.decline_pct is required")
        decline = _num(crisis, "decline_pct", 1, 90)
        p["crisis"] = {
            "decline": decline / 100,
            "start_month": _int(crisis.get("start_month", 1), "crisis.start_month", 1, horizon),
            "recovery_years": _int(crisis.get("recovery_years", 2), "crisis.recovery_years", 1, 10),
        }

    modes = params.get("cushion_modes", list(DEFAULT_CUSHION_MONTHS))
    if not isinstance(modes, (list, tuple)) or not 1 <= len(modes) <= 5:
        raise ValueError("cushion_modes must be a list of 1-5 month counts")
    months = [_int(m, "cushion_modes[]", 0, 60) for m in modes]
    if len(set(months)) != len(months):
        raise ValueError("cushion_modes must be unique")
    p["cushion_months"] = months

    buckets = _dict(params.get("cash_buckets", {}), "cash_buckets", _BUCKET_KEYS)
    reserved = {}
    for name in ("pledged", "family_earmarked"):
        reserved[name] = _num(buckets, name, 0, 1e12, default=0)
    if _num(buckets, "free", 0, 1e12, default=0):
        raise ValueError("cash_buckets.free is derived from the cushion mode; leave it 0")
    p["reserved"] = reserved

    protected = _dict(params.get("protected_capital", {}), "protected_capital", {"amount"})
    p["protected_amount"] = _num(protected, "amount", 0, 1e12, default=0)

    p["net_burn"] = max(0.0, p["support"] + p["other_expenses"] - p["other_income"] - p["deposit"])
    if sum(reserved.values()) + max(months) * p["net_burn"] > p["fund_value"]:
        raise ValueError("reserved cash plus the largest cushion exceeds fund_value")
    return p


def _net_factors(p, with_crisis):
    """גורם חודשי נטו לכל חודש — זהה למנוע: גורם מגמה (או ירידה/התאוששות) כפול שימור דמי הניהול."""
    asset = Asset(annual_return=p["annual_return"], annual_fee=p["annual_fee"])
    crisis = p["crisis"]
    years_count = -(-p["horizon"] // 12)
    if with_crisis and crisis:
        year, month = divmod(crisis["start_month"] - 1, 12)
        asset = crisis_asset_monthly(asset, crisis["decline"], year + 1, month + 1, crisis["recovery_years"], years_count)
    overrides = dict(asset.monthly_returns)
    trend = (1 + p["annual_return"]) ** (1 / 12)
    retained = (1 - p["annual_fee"]) ** (1 / 12)
    return [(1 + overrides[m] if m in overrides else trend) * retained for m in range(p["horizon"])]


def run_cushion(p, cushion_months, with_crisis=True):
    """הרצה חודשית אחת למצב כרית. מחזיר תוצאה גולמית (ללא עיגול). סדר בחודש: תשואה ודמי ניהול → תזרים נטו."""
    factors = _net_factors(p, with_crisis)
    cash_factor = (1 + p["cash_return"]) ** (1 / 12)
    free = cushion_months * p["net_burn"]
    reserved = p["reserved"]["pledged"] + p["reserved"]["family_earmarked"]
    units = p["fund_value"] - reserved - free  # מחיר פתיחה 1
    if units < -_EPS:
        raise ValueError("reserved cash plus cushion exceeds fund_value")
    units = max(units, 0.0)
    price = 1.0
    cpi = 1.0
    withdrawing = p["phase"] == "withdrawal"
    out_flow = (p["support"] + p["other_expenses"] - p["other_income"]) if withdrawing else 0.0
    net_out = out_flow - p["deposit"]
    forced, shortfall = [], []
    exhausted = None
    series = []
    for m in range(p["horizon"]):
        price *= factors[m]
        free *= cash_factor
        reserved *= cash_factor
        cpi *= (1 + p["inflation"]) ** (1 / 12)
        if net_out < 0:
            units += -net_out / price
        elif net_out > 0:
            take = min(free, net_out)
            free -= take
            rest = net_out - take
            if rest > _EPS:
                if rest / price <= units + _EPS:
                    units = max(units - rest / price, 0.0)
                    sold = rest
                else:
                    sold = units * price
                    units = 0.0
                    shortfall.append({"month": m + 1, "amount": rest - sold})
                if sold > _EPS:
                    forced.append({"month": m + 1, "amount": sold, "units": sold / price, "price_index": price})
        if exhausted is None and cushion_months and free <= _EPS:
            exhausted = m + 1
        risky = units * price
        series.append({"month": m + 1, "risky": risky, "free_cash": free, "reserved_cash": reserved, "total": risky + free + reserved})
    final = series[-1]["total"]
    return {"final_nominal": final, "final_real": final / cpi, "forced": forced, "shortfall": shortfall,
            "cushion_exhausted_month": exhausted, "free_cushion_start": cushion_months * p["net_burn"], "series": series}


def _round(x):
    return round(x, 2)


def _event_block(events, key_fields):
    total = sum(e["amount"] for e in events)
    return {"count": len(events), "first_month": events[0]["month"] if events else None, "total_amount": _round(total),
            "events": [{k: (_round(e[k]) if k != "month" else e[k]) for k in key_fields} for e in events[:MAX_EVENTS_SHOWN]],
            "events_truncated": len(events) > MAX_EVENTS_SHOWN}


def _in_window(events, start):
    return any(start <= e["month"] < start + WINDOW_MONTHS for e in events)


def _mode_view(p, months):
    run = run_cushion(p, months)
    base = run_cushion(p, months, with_crisis=False)
    crisis = p["crisis"]
    window = None
    if crisis:
        start = crisis["start_month"]
        window = {"months": WINDOW_MONTHS, "from_month": start, "to_month": min(start + WINDOW_MONTHS - 1, p["horizon"]),
                  "forced_sale_free": not _in_window(run["forced"], start),
                  "shortfall_free": not _in_window(run["shortfall"], start),
                  "collateral_call": None}  # E1a ללא הלוואה — לא רלוונטי
    free_start = run["free_cushion_start"]
    return {
        "cushion_months": months,
        "label": "ללא כרית" if months == 0 else f"{months} חודשי תזרים נטו",
        "free_cushion": _round(free_start),
        "months_of_support_covered": _round(free_start / p["support"]) if p["support"] else None,
        "events": {
            "collateral_call": {"status": "not_applicable_no_loan", "count": 0},
            "forced_sale": _event_block(run["forced"], ("month", "amount", "units", "price_index")),
            "cash_shortfall": _event_block(run["shortfall"], ("month", "amount")),
        },
        "cushion_exhausted_month": run["cushion_exhausted_month"],
        "window_24m": window,
        "final_net_value": _round(run["final_nominal"]),
        "final_real_value": _round(run["final_real"]),
        "delta_vs_no_crisis": _round(run["final_nominal"] - base["final_nominal"]) if crisis else 0.0,
        "series": [{k: (v if k == "month" else _round(v)) for k, v in row.items()} for row in run["series"]],
    }


def build_stress_view(params=None):
    """חוזה הפלט של E1a: השוואת מצבי כרית תחת משבר, לפי הנחות שהוזנו. טהור ודטרמיניסטי."""
    p = normalize_params(params)
    modes = [_mode_view(p, m) for m in p["cushion_months"]]
    view = {
        "schema_version": STRESS_SCHEMA_VERSION,
        "result_type": RESULT_TYPE,
        "engine_version": ENGINE_VERSION,
        "inputs_echo": {k: p[k] for k in ("fund_value", "phase", "deposit", "support", "other_expenses", "other_income",
                                          "annual_return", "annual_fee", "inflation", "cash_return", "horizon", "crisis",
                                          "cushion_months", "reserved")},
        "net_burn": {
            "components": {"support": p["support"], "other_expenses": p["other_expenses"], "loan_interest": 0.0,
                           "loan_repayments": 0.0, "less_other_income": -p["other_income"], "less_deposits": -p["deposit"]},
            "net_burn_per_month": _round(p["net_burn"]),
            "basis": "net_burn",
        },
        "protected_capital": {"amount": _round(p["protected_amount"]), "separation": "hard",
                              "note": "הון הילדים מופרד: אינו חלק מהקרן, אינו בטוחה ואינו מממן הפסדים; לא נכלל בחישוב."},
        "modes": modes,
        "notes": [
            "תרחיש לפי הנחות שהוזנו; אין כאן הערכת סיכוי, המלצה או תנאי בנק מאומתים.",
            "מכירה כפויה: מכירת נכס סיכון לצורך תזרים. מחסור במזומן: אין מזומן חופשי ואין נכס סיכון שמכסה את התזרים. שניהם נפרדים מדרישת בטוחות (לא רלוונטית ללא הלוואה).",
            "כרית נמדדת לפי תזרים נטו; מזומן משועבד או מיועד להתחייבויות משפחתיות שמור ואינו מממן תזרים.",
            "ללא מס, ללא אינפלציה בתזרים (סכומים נומינליים קבועים), ללא הלוואה (E1b).",
        ],
    }
    view["replay_digest"] = hashlib.sha256(json.dumps(view, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return view
