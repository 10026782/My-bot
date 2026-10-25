"""מבחן לחץ נזילות לקרן המשפחתית (E1a) — שכבה טהורה מעל Portfolio Lab, ללא I/O, Airtable או LLM.

המנוע (`portfolio_lab.engine.simulate`) לא משתנה: הוא ללא משיכות ולכן אינו יכול לבטא "מכירת יחידות אחרי ירידה".
כאן לולאה חודשית עצמאית ביחידות, שמשתמשת באותו נתיב תשואות (`crisis_asset_monthly`, אותו גורם חודשי ודמי ניהול);
התאמה למנוע מוכחת בבדיקת parity (test_portfolio_lab_liquidity_stress.py).

E1a: כרית נזילות. E1b: הלוואה (קרן, ריבית, פירעונות, יתרת חוב), סף LTV (קלט בלבד), דרישת בטוחות ותיקונה.
שלושה אירועים מוצגים בנפרד: דרישת בטוחות, מכירה כפויה (עם `cause`: תזרים או דרישת בטוחות), מחסור במזומן.
בטוחה = נכס סיכון + מזומן משועבד (אם הוגדר); מזומן חופשי אינו בטוחה אך מכסה תזרים ותיקון; מזומן מיועד להתחייבויות משפחתיות אינו מממן דבר.
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
_TOP_KEYS = set(DEFAULTS) | {"loan", "crisis", "cushion_modes", "cash_buckets", "protected_capital"}
_CRISIS_KEYS = {"decline_pct", "start_month", "recovery_years"}
_BUCKET_KEYS = {"free", "pledged", "family_earmarked"}
_UNSUPPORTED = {"cushion_basis": "cushion_basis is fixed to net burn"}
_LOAN_KEYS = {"amount", "annual_rate_pct", "interest_only", "term_months", "max_ltv_pct", "terms_verified", "collateral", "cure_order", "use_proceeds"}
_PROCEEDS_KEYS = {"kind", "monthly_income", "asset_value"}
_COLLATERAL = ("risky_and_pledged", "risky_only")
_CURE_SOURCES = ("cushion", "risky_sale")


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

    p["loan"] = _normalize_loan(params.get("loan"))
    first = _payment(p["loan"], p["loan"]["amount"], 1) if p["loan"] else (0.0, 0.0)
    asset_income = p["loan"]["income"] if p["loan"] else 0.0
    p["net_burn"] = max(0.0, p["support"] + p["other_expenses"] - p["other_income"] - asset_income - p["deposit"] + first[0] + first[1])
    if sum(reserved.values()) + max(months) * p["net_burn"] > p["fund_value"]:
        raise ValueError("reserved cash plus the largest cushion exceeds fund_value")
    if p["loan"] and p["loan"]["amount"] > p["fund_value"]:
        raise ValueError("loan.amount must not exceed fund_value")
    return p


def _normalize_loan(raw):
    if raw is None:
        return None
    raw = _dict(raw, "loan", _LOAN_KEYS)
    for required in ("amount", "annual_rate_pct", "max_ltv_pct"):
        if required not in raw:
            raise ValueError(f"loan.{required} is required")  # סף LTV הוא קלט בלבד — אין ברירת מחדל בנקאית
    interest_only = raw.get("interest_only", True)
    if type(interest_only) is not bool:
        raise ValueError("loan.interest_only must be boolean")
    if interest_only and "term_months" in raw:
        raise ValueError("loan.term_months applies only to an amortizing loan")
    if not interest_only and "term_months" not in raw:
        raise ValueError("loan.term_months is required when interest_only is false")
    terms_verified = raw.get("terms_verified", False)
    if type(terms_verified) is not bool:
        raise ValueError("loan.terms_verified must be boolean")
    collateral = raw.get("collateral", "risky_and_pledged")
    if collateral not in _COLLATERAL:
        raise ValueError(f"loan.collateral must be one of {_COLLATERAL}")
    cure = raw.get("cure_order", list(_CURE_SOURCES))
    if not isinstance(cure, (list, tuple)) or not cure or len(set(cure)) != len(cure) or any(c not in _CURE_SOURCES for c in cure):
        raise ValueError(f"loan.cure_order must be a unique subset of {_CURE_SOURCES}")
    proceeds = _dict(raw.get("use_proceeds", {"kind": "none"}), "loan.use_proceeds", _PROCEEDS_KEYS)
    kind = proceeds.get("kind", "none")
    if kind not in ("none", "asset_income"):
        raise ValueError("loan.use_proceeds.kind must be none or asset_income")
    if kind == "none" and set(proceeds) - {"kind"}:
        raise ValueError("loan.use_proceeds income/value apply only to asset_income")
    return {
        "amount": _num(raw, "amount", 1, 1e12, default=0),
        "rate": _num(raw, "annual_rate_pct", 0, 100, default=0) / 100,
        "interest_only": interest_only,
        "term": None if interest_only else _int(raw["term_months"], "loan.term_months", 1, 600),
        "max_ltv": _num(raw, "max_ltv_pct", 5, 95, default=0) / 100,
        "terms_verified": terms_verified,
        "collateral": collateral,
        "cure_order": list(cure),
        "proceeds": kind,
        "income": _num(proceeds, "monthly_income", 0, 1e9, default=0) if kind == "asset_income" else 0.0,
        "asset_value": _num(proceeds, "asset_value", 0, 1e12, default=0) if kind == "asset_income" else 0.0,
    }


def _payment(loan, debt, month):
    """(ריבית, פירעון קרן) לחודש `month` (1-based) לפי יתרת החוב. ריבית = יתרה × שיעור שנתי / 12; ריבית בלבד: אין פירעון קרן באופק."""
    i = loan["rate"] / 12
    interest = debt * i
    if loan["interest_only"] or month > loan["term"]:
        return interest, 0.0
    n = loan["term"] - month + 1  # שפיצר לפי יתרה ותקופה שנותרה: תשלום קבוע
    pmt = debt / n if i == 0 else debt * i / (1 - (1 + i) ** -n)
    return interest, pmt - interest


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


def _cure(loan, debt, free, units, price, pledged):
    """תיקון דרישת בטוחות לפי `cure_order`. מחזיר (חוב, מזומן חופשי, יחידות, פירעון מכרית, מכירה, יתרת חוסר)."""
    mx = loan["max_ltv"]
    from_free = sold = 0.0
    for source in loan["cure_order"]:
        coll = units * price + (pledged if loan["collateral"] == "risky_and_pledged" else 0.0)
        gap = debt - mx * coll
        if gap <= _EPS:
            break
        if source == "cushion":  # מזומן חופשי אינו בטוחה: פירעון ממנו אינו מקטין את הבטוחה
            y = min(free, gap)
            free -= y
            debt -= y
            from_free += y
        else:  # מכירת נכס סיכון מקטינה גם את הבטוחה: x = gap / (1 - LTV)
            x = min(gap / (1 - mx), units * price)
            units = max(units - x / price, 0.0)
            debt -= x
            sold += x
    coll = units * price + (pledged if loan["collateral"] == "risky_and_pledged" else 0.0)
    return debt, free, units, from_free, sold, max(debt - mx * coll, 0.0)


def run_cushion(p, cushion_months, with_crisis=True):
    """הרצה חודשית אחת למצב כרית. מחזיר תוצאה גולמית (ללא עיגול).
    סדר בחודש: תשואה ודמי ניהול → החזר הלוואה ותזרים נטו (כרית, ואז מכירה) → בדיקת LTV ותיקון דרישת בטוחות."""
    factors = _net_factors(p, with_crisis)
    cash_factor = (1 + p["cash_return"]) ** (1 / 12)
    loan = p["loan"]
    free = cushion_months * p["net_burn"]
    pledged = p["reserved"]["pledged"]
    earmarked = p["reserved"]["family_earmarked"]
    units = p["fund_value"] - pledged - earmarked - free  # מחיר פתיחה 1
    if units < -_EPS:
        raise ValueError("reserved cash plus cushion exceeds fund_value")
    units = max(units, 0.0)
    price = 1.0
    cpi = 1.0
    debt = loan["amount"] if loan else 0.0
    asset_income = loan["income"] if loan else 0.0
    asset_value = loan["asset_value"] if loan else 0.0
    withdrawing = p["phase"] == "withdrawal"
    base_out = (p["support"] + p["other_expenses"] - p["other_income"]) if withdrawing else 0.0
    forced, shortfall, calls = [], [], []
    exhausted = None
    series = []
    for m in range(p["horizon"]):
        price *= factors[m]
        free *= cash_factor
        pledged *= cash_factor
        earmarked *= cash_factor
        cpi *= (1 + p["inflation"]) ** (1 / 12)
        interest = principal = 0.0
        if loan and debt > _EPS:
            interest, principal = _payment(loan, debt, m + 1)
        payment = interest + principal
        net_out = base_out - asset_income + payment - p["deposit"]
        unmet = 0.0
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
                    unmet = rest - sold
                    shortfall.append({"month": m + 1, "amount": unmet})
                if sold > _EPS:
                    forced.append({"month": m + 1, "amount": sold, "units": sold / price, "price_index": price, "cause": "cashflow"})
        if loan:
            unpaid = min(unmet, payment)  # חוסר מכוסה קודם כהחזר ההלוואה (שמרני): הלא-משולם מצטבר לחוב
            paid = payment - unpaid
            paid_interest = min(paid, interest)
            debt = max(debt + (interest - paid_interest) - (paid - paid_interest), 0.0)
        if exhausted is None and cushion_months and free <= _EPS:
            exhausted = m + 1
        ltv = None
        if loan and debt > _EPS:
            coll = units * price + (pledged if loan["collateral"] == "risky_and_pledged" else 0.0)
            ltv = debt / coll if coll > _EPS else None
            if ltv is None or ltv > loan["max_ltv"] + _EPS:
                before = {"month": m + 1, "ltv": ltv, "debt": debt, "collateral": coll}
                debt, free, units, from_free, sold, left = _cure(loan, debt, free, units, price, pledged)
                before.update(cured_from_free_cash=from_free, cured_from_risky_sale=sold, unresolved=left, amount=from_free + sold + left)
                calls.append(before)
                if sold > _EPS:
                    forced.append({"month": m + 1, "amount": sold, "units": sold / price, "price_index": price, "cause": "collateral_call"})
        risky = units * price
        fund_total = risky + free + pledged + earmarked
        series.append({"month": m + 1, "risky": risky, "free_cash": free, "reserved_cash": pledged + earmarked, "total": fund_total,
                       "debt": debt, "ltv": ltv, "net_worth": fund_total - debt + (asset_value if loan else 0.0)})
    last = series[-1]
    return {"final_nominal": last["total"], "final_real": last["total"] / cpi, "final_debt": debt,
            "final_net_worth": last["net_worth"], "final_net_worth_real": last["net_worth"] / cpi,
            "forced": forced, "shortfall": shortfall, "calls": calls,
            "cushion_exhausted_month": exhausted, "free_cushion_start": cushion_months * p["net_burn"], "series": series}


def _round(x):
    return None if x is None else round(x, 2)


def _event_block(events, key_fields):
    total = sum(e["amount"] for e in events)
    return {"count": len(events), "first_month": events[0]["month"] if events else None, "total_amount": _round(total),
            "events": [{k: (e[k] if k in ("month", "cause") else _round(e[k])) for k in key_fields if k in e} for e in events[:MAX_EVENTS_SHOWN]],
            "events_truncated": len(events) > MAX_EVENTS_SHOWN}


def _in_window(events, start):
    return any(start <= e["month"] < start + WINDOW_MONTHS for e in events)


def _call_block(p, calls):
    if not p["loan"]:
        return {"status": "not_applicable_no_loan", "count": 0}
    block = _event_block(calls, ("month", "amount", "debt", "collateral", "cured_from_free_cash", "cured_from_risky_sale", "unresolved"))
    for shown, call in zip(block["events"], calls):
        shown["ltv"] = None if call["ltv"] is None else round(call["ltv"], 4)
    block["status"] = "evaluated"
    block["unresolved_count"] = sum(1 for c in calls if c["unresolved"] > _EPS)
    return block


def _initial_collateral(p, months):
    """(נכס סיכון התחלתי, בטוחה התחלתית) למצב כרית: מזומן חופשי יוצא מהנכס ואינו בטוחה."""
    loan = p["loan"]
    risky0 = p["fund_value"] - p["reserved"]["pledged"] - p["reserved"]["family_earmarked"] - months * p["net_burn"]
    return risky0, risky0 + (p["reserved"]["pledged"] if loan["collateral"] == "risky_and_pledged" else 0.0)


def _trigger_decline_pct(p, months):
    """ירידה מינימלית בנכס הסיכון (במצב ההתחלתי, לפני תזרים) שמפעילה דרישת בטוחות; None אם לא תופעל לעולם / אין נכס סיכון."""
    loan = p["loan"]
    risky0, _ = _initial_collateral(p, months)
    if risky0 <= _EPS:
        return None
    pledged = p["reserved"]["pledged"] if loan["collateral"] == "risky_and_pledged" else 0.0
    ratio = (loan["amount"] / loan["max_ltv"] - pledged) / risky0
    if ratio <= 0:
        return None
    return round(max(0.0, 1 - ratio) * 100, 2)


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
                  "collateral_call_free": (not _in_window(run["calls"], start)) if p["loan"] else None}
    free_start = run["free_cushion_start"]
    return {
        "cushion_months": months,
        "label": "ללא כרית" if months == 0 else f"{months} חודשי תזרים נטו",
        "free_cushion": _round(free_start),
        "months_of_support_covered": _round(free_start / p["support"]) if p["support"] else None,
        "events": {
            "collateral_call": _call_block(p, run["calls"]),
            "forced_sale": _event_block(run["forced"], ("month", "amount", "units", "price_index", "cause")),
            "cash_shortfall": _event_block(run["shortfall"], ("month", "amount")),
        },
        "forced_sale_by_cause": {c: round(sum(e["amount"] for e in run["forced"] if e["cause"] == c), 2) for c in ("cashflow", "collateral_call")},
        "initial_collateral": _round(_initial_collateral(p, months)[1]) if p["loan"] else None,
        "initial_ltv": (round(p["loan"]["amount"] / _initial_collateral(p, months)[1], 4) if _initial_collateral(p, months)[1] > _EPS else None) if p["loan"] else None,
        "trigger_decline_pct": _trigger_decline_pct(p, months) if p["loan"] else None,
        "cushion_exhausted_month": run["cushion_exhausted_month"],
        "window_24m": window,
        "final_net_value": _round(run["final_nominal"]),
        "final_real_value": _round(run["final_real"]),
        "final_debt": _round(run["final_debt"]),
        "final_net_worth": _round(run["final_net_worth"]),
        "final_net_worth_real": _round(run["final_net_worth_real"]),
        "max_ltv": None if not p["loan"] else max((round(r["ltv"], 4) for r in run["series"] if r["ltv"] is not None), default=None),
        "delta_vs_no_crisis": _round(run["final_net_worth"] - base["final_net_worth"]) if crisis else 0.0,
        "series": [{k: (v if k == "month" else (round(v, 4) if k == "ltv" and v is not None else _round(v))) for k, v in row.items()} for row in run["series"]],
    }


def _loan_view(p):
    loan = p["loan"]
    if not loan:
        return None
    interest, principal = _payment(loan, loan["amount"], 1)
    return {
        "principal": _round(loan["amount"]), "annual_rate_pct": round(loan["rate"] * 100, 4),
        "interest_only": loan["interest_only"], "term_months": loan["term"],
        "first_month_interest": _round(interest), "first_month_principal_repayment": _round(principal),
        "max_ltv_pct": round(loan["max_ltv"] * 100, 4), "max_ltv_source": "owner_entered",
        "terms_verified": loan["terms_verified"], "collateral": loan["collateral"], "cure_order": loan["cure_order"],
        "proceeds": {"kind": loan["proceeds"], "monthly_income": _round(loan["income"]), "asset_value": _round(loan["asset_value"]),
                     "note": "תמורת ההלוואה מחוץ לקרן; הנכס (אם הוזן) קבוע נומינלית, אינו בטוחה, ואינו מושפע מהמשבר."
                     if loan["proceeds"] == "asset_income" else "תמורת ההלוואה הוצאה ללא תשואה: מוסיפה חוב בלי נכס."},
    }


def build_stress_view(params=None):
    """חוזה הפלט של E1a/E1b: השוואת מצבי כרית תחת משבר, לפי הנחות שהוזנו. טהור ודטרמיניסטי."""
    p = normalize_params(params)
    modes = [_mode_view(p, m) for m in p["cushion_months"]]
    loan = p["loan"]
    first_interest, first_principal = _payment(loan, loan["amount"], 1) if loan else (0.0, 0.0)
    notes = [
        "תרחיש לפי הנחות שהוזנו; אין כאן הערכת סיכוי, המלצה או תנאי בנק מאומתים.",
        "מכירה כפויה: מכירת נכס סיכון לצורך תזרים או לתיקון דרישת בטוחות (שדה cause). מחסור במזומן: אין מזומן חופשי ואין נכס סיכון שמכסה את התזרים. דרישת בטוחות: LTV חרג מהסף שהוזן. שלושתם אירועים נפרדים.",
        "כרית נמדדת לפי תזרים נטו (כולל ריבית ופירעונות בחודש הראשון). מזומן חופשי מכסה תזרים ותיקון בטוחות אך אינו נספר כבטוחה; מזומן משועבד נספר כבטוחה ואינו מממן; מזומן מיועד להתחייבויות משפחתיות אינו מממן דבר.",
        "ללא מס, ללא אינפלציה בתזרים (סכומים נומינליים קבועים).",
    ]
    if loan and not loan["terms_verified"]:
        notes.append("תנאי ההלוואה (סף LTV, ריבית) הוזנו ידנית ולא אומתו מול בנק.")
    if loan and loan["interest_only"]:
        notes.append("הלוואה בריבית בלבד: הקרן אינה נפרעת באופק והיתרה מנוכה בשווי הנקי.")
    view = {
        "schema_version": STRESS_SCHEMA_VERSION,
        "result_type": RESULT_TYPE,
        "engine_version": ENGINE_VERSION,
        "inputs_echo": {k: p[k] for k in ("fund_value", "phase", "deposit", "support", "other_expenses", "other_income",
                                          "annual_return", "annual_fee", "inflation", "cash_return", "horizon", "crisis",
                                          "cushion_months", "reserved")},
        "loan": _loan_view(p),
        "net_burn": {
            "components": {"support": p["support"], "other_expenses": p["other_expenses"], "loan_interest": _round(first_interest),
                           "loan_repayments": _round(first_principal), "less_other_income": -p["other_income"],
                           "less_asset_income": -(loan["income"] if loan else 0.0), "less_deposits": -p["deposit"]},
            "net_burn_per_month": _round(p["net_burn"]),
            "basis": "net_burn",
        },
        "protected_capital": {"amount": _round(p["protected_amount"]), "separation": "hard",
                              "note": "הון הילדים מופרד: אינו חלק מהקרן, אינו בטוחה ואינו מממן הפסדים; לא נכלל בחישוב."},
        "modes": modes,
        "notes": notes,
    }
    view["replay_digest"] = hashlib.sha256(json.dumps(view, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return view
