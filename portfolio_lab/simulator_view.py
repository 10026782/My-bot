"""שכבת תצוגה לסימולטור — מחזירה נתונים מובנים בלבד (KPI, סדרות גרף, טבלה, תובנות).

אין כאן חישוב פיננסי חדש: כל הערך הכספי מגיע מ-`portfolio_lab.simulate/compare`.
כאן רק בחירת תרחישים להרצה (רגישות, משבר) וניסוח. ללא I/O, Airtable או LLM.
המודול נפרד מה-UI בכוונה, כדי שבעתיד Decision Hub / מחקרים יוכלו לצרוך
`build_simulator_view` ישירות.
"""

from dataclasses import replace
import math

from .engine import compare, simulate, strategy_assets
from .models import ENGINE_VERSION, Asset, Scenario

VIEW_SCHEMA_VERSION = "1.0"

STRATEGY_LABELS = {
    "global": "100% קרן עולמית",
    "world_em": "World + EM",
    "three_funds": "השילוש",
    "experimental_90_10": "90/10",
}
# הנחות ברירת מחדל לרכיבי האסטרטגיות — זהות לדוגמת docs/portfolio_lab/comparison.json.
# אלה הנחות להמחשה בלבד, לא נתוני שוק.
DEFAULT_COMPONENT_RETURNS = {
    "msci_world": 0.075,
    "emerging_markets": 0.065,
    "sp500": 0.085,
    "europe": 0.07,
    "selected_stocks": 0.06,
}
COMPONENT_LABELS = {
    "global_accumulating": "קרן עולמית (לפי התשואה שהוזנה)",
    "msci_world": "World",
    "emerging_markets": "שווקים מתעוררים",
    "sp500": "S&P 500",
    "europe": "אירופה",
    "selected_stocks": "מניות נבחרות (ניסויי)",
}
CRISIS_DECLINES = (10, 20, 30, 40, 50)
RECOVERY_YEARS = {"fast": 1, "prolonged": 3}
CONTRIBUTION_FACTORS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
HORIZON_CHOICES = (10, 15, 20, 30, 40, 50, 60)
DEFAULT_CRISIS_DECLINE = 30
EARLY_LATE_SPLIT = (0.1, 0.7)  # אחוז מהאופק: משבר מוקדם מול מאוחר

DEFAULTS = {
    "initial": 0.0,
    "monthly_contribution": 8000.0,
    "years": 30,
    "annual_return_pct": 8.0,
    "annual_fee_pct": 0.15,
    "inflation_pct": 2.0,
    "deposit_timing": "end",
    "index_contributions": False,
    "strategies": ["global", "world_em", "three_funds", "experimental_90_10"],
    "baseline": "global",
    "crisis": None,
}


def _num(params, key, minimum=None, maximum=None):
    value = params.get(key, DEFAULTS[key])
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key} must be <= {maximum}")
    return float(value)


def normalize_params(params):
    """קלט גולמי (אחוזים כפי שמוצגים במסך) → קלט מנורמל; ValueError על קלט לא תקף."""
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    unknown = set(params) - set(DEFAULTS) - {"component_returns_pct"}
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    years = params.get("years", DEFAULTS["years"])
    if isinstance(years, bool) or not isinstance(years, int) or not 10 <= years <= 100:
        raise ValueError("years must be an integer from 10 to 100")
    timing = params.get("deposit_timing", DEFAULTS["deposit_timing"])
    if timing not in {"begin", "end"}:
        raise ValueError("deposit_timing must be begin or end")
    index = params.get("index_contributions", DEFAULTS["index_contributions"])
    if not isinstance(index, bool):
        raise ValueError("index_contributions must be boolean")
    strategies = params.get("strategies", DEFAULTS["strategies"])
    if not isinstance(strategies, list) or not strategies or any(s not in STRATEGY_LABELS for s in strategies):
        raise ValueError("strategies must be a nonempty list of known strategies")
    baseline = params.get("baseline", DEFAULTS["baseline"])
    if baseline not in STRATEGY_LABELS:
        raise ValueError("unknown baseline strategy")
    ordered = [baseline] + [s for s in dict.fromkeys(strategies) if s != baseline]
    components = dict(DEFAULT_COMPONENT_RETURNS)
    overrides = params.get("component_returns_pct", {})
    if not isinstance(overrides, dict) or set(overrides) - set(components):
        raise ValueError("component_returns_pct has unknown components")
    for name, pct in overrides.items():
        if isinstance(pct, bool) or not isinstance(pct, (int, float)) or not -50 <= pct <= 50:
            raise ValueError(f"component_returns_pct.{name} must be a number from -50 to 50")
        components[name] = pct / 100
    crisis = params.get("crisis")
    if crisis is not None:
        if not isinstance(crisis, dict) or set(crisis) - {"decline_pct", "year", "recovery", "month"}:
            raise ValueError("crisis must contain decline_pct, year, recovery and optionally month")
        if crisis.get("decline_pct") not in CRISIS_DECLINES:
            raise ValueError("crisis decline_pct must be one of 10/20/30/40/50")
        if crisis.get("recovery") not in RECOVERY_YEARS:
            raise ValueError("crisis recovery must be fast or prolonged")
        year = crisis.get("year")
        if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= years:
            raise ValueError("crisis year must be an integer within the horizon")
        month = crisis.get("month")
        if month is not None and (isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12):
            raise ValueError("crisis month must be an integer from 1 to 12")
        crisis = {"decline_pct": crisis["decline_pct"], "year": year, "recovery": crisis["recovery"]}
        if month is not None:
            crisis["month"] = month
    return {
        "initial": _num(params, "initial", 0),
        "monthly_contribution": _num(params, "monthly_contribution", 0),
        "years": years,
        "annual_return": _num(params, "annual_return_pct", -50, 50) / 100,
        "annual_fee": _num(params, "annual_fee_pct", 0, 10) / 100,
        "inflation": _num(params, "inflation_pct", -50, 50) / 100,
        "deposit_timing": timing,
        "index_contributions": index,
        "strategies": ordered,
        "components": components,
        "crisis": crisis,
    }


def _assumptions(p):
    """נכסים לכל אסטרטגיה: הרכיב העולמי לפי הקלט, שאר הרכיבים לפי הנחות ההמחשה."""
    table = {"global_accumulating": Asset(name="global_accumulating", annual_return=p["annual_return"], annual_fee=p["annual_fee"])}
    for name, rate in p["components"].items():
        table[name] = Asset(name=name, annual_return=rate, annual_fee=p["annual_fee"])
    return table


def _scenario(p, template, **overrides):
    values = {
        "years": p["years"], "initial": p["initial"], "monthly_contribution": p["monthly_contribution"],
        "inflation": p["inflation"], "index_contributions": p["index_contributions"],
        "deposit_timing": p["deposit_timing"], "assets": strategy_assets(template, _assumptions(p)),
    }
    values.update(overrides)
    return Scenario(**values)


def crisis_asset(asset, decline, year, recovery_years, years_count):
    """מסלול שנתי עם ירידה בשנה `year` והתאוששות לנתיב המגמה על פני `recovery_years`.

    לאחר ההתאוששות הנכס חוזר לנתיב שהיה מגיע אליו בלי המשבר:
    (1-d)·g^n = (1+r)^(n+1). התאוששות שחורגת מהאופק נחתכת (נשארים מתחת למגמה).
    זו הנחה מודלית, לא תחזית ולא נתון היסטורי.
    """
    rate = asset.annual_return[0]
    path = [rate] * years_count
    path[year - 1] = -decline
    n = recovery_years
    growth = ((1 + rate) ** (n + 1) / (1 - decline)) ** (1 / n) - 1
    for offset in range(1, n + 1):
        if year - 1 + offset < years_count:
            path[year - 1 + offset] = growth
    return replace(asset, annual_return=tuple(path))


def crisis_asset_monthly(asset, decline, year, month, recovery_years, years_count):
    """משבר תוך-שנתי: בחודש `month` (1-12) של שנה `year` הנכס יורד בבת אחת ב-`decline` (במקום צמיחת המגמה של אותו חודש).

    ההתאוששות פרוסה על 12·`recovery_years` החודשים שאחרי חודש הירידה בצמיחה חודשית קבועה g עד לנתיב המגמה:
    (1-d)·g^R = f^(R+1), כש-f הוא גורם המגמה החודשי (1+r)^(1/12) ו-R=12·n. חודשים שמחוץ לאופק נחתכים.
    סדר מול ההפקדה נקבע ע"י `deposit_timing` של התרחיש (ראו _intra_year_order_note): הפקדת סוף חודש נקנית אחרי הירידה,
    הפקדת תחילת חודש חשופה לה. הנחה מודלית, לא תחזית.
    """
    rate = asset.annual_return[0]
    f = (1 + rate) ** (1 / 12)
    start = (year - 1) * 12 + (month - 1)
    total = years_count * 12
    months = 12 * recovery_years
    g = ((f ** (months + 1)) / (1 - decline)) ** (1 / months)
    overrides = [(start, -decline)] + [(start + j, g - 1) for j in range(1, months + 1) if start + j < total]
    return replace(asset, monthly_returns=tuple(overrides))


def _with_crisis(scenario, crisis):
    decline = crisis["decline_pct"] / 100
    n = RECOVERY_YEARS[crisis["recovery"]]
    if crisis.get("month") is not None:
        assets = tuple(crisis_asset_monthly(a, decline, crisis["year"], crisis["month"], n, scenario.years) for a in scenario.assets)
    else:
        assets = tuple(crisis_asset(a, decline, crisis["year"], n, scenario.years) for a in scenario.assets)
    return replace(scenario, assets=assets)


def _intra_year_order_note(timing, month):
    if timing == "begin":
        return (f"הפקדות בתחילת החודש: ההפקדה של חודש {month} נעשית לפני הירידה ולכן נחשפת אליה; "
                "ההפקדות מהחודש שאחריו נקנות במחיר שאחרי הירידה.")
    return (f"הפקדות בסוף החודש: ההפקדה של חודש {month} נעשית אחרי הירידה ולכן נקנית במחיר הנמוך; "
            "רק היתרה שנצברה עד אז נחשפת לירידה.")


def _final(scenario):
    return simulate(scenario)["final"]


def _kpis(result):
    final = result["final"]
    tax = final["tax"]
    verified = result["tax_assessment"] is not None and final["tax_status"] == "externally_verified_adapter"
    if tax is None:
        after_tax = {"value": None, "display": "לא מחושב", "note": "לא הוזן מודל מס תקף"}
    else:
        after_tax = {
            "value": final["proceeds_after_tax"], "display": None,
            "note": "מבוסס מודל מס שאומת חיצונית" if verified else "תוצאה תיאורטית בלבד — מודל מס לא אומת",
        }
    return {
        "final_nominal": final["value_after_costs"],
        "final_real": final["real_value"],
        "contributions": final["contributions"],
        "nominal_profit": final["nominal_profit"],
        "real_profit": final["real_profit"],
        "management_fees_paid": final["management_cost"],
        "total_cost_impact": final["cost_impact"],
        "net_effective_annual_return": final["nominal_annualized_twr_after_recurring_costs"],
        "real_effective_annual_return": final["real_annualized_twr_after_recurring_costs"],
        "after_tax": after_tax,
    }


def _series(result):
    return [{"year": r["year"], "nominal": r["value_after_costs"], "real": r["real_value"], "contributions": r["contributions"]}
            for r in result["annual"]]


def _breakdown(final):
    gross = final["value_before_costs"]
    costs = final["cost_impact"]
    parts = {
        "contributions": final["contributions"],
        "profit_net": final["value_after_costs"] - final["contributions"],
        "costs": costs,
    }
    # שיעורים מחושבים כאן (לא ב-JS) כדי שה-UI יציג בלבד
    parts["shares"] = {k: (v / gross if gross else 0.0) for k, v in parts.items()}
    parts["total_before_costs"] = gross
    return parts


def _sensitivity(p, base_final):
    contribution = []
    for factor in CONTRIBUTION_FACTORS:
        s = _scenario(p, p["strategies"][0], monthly_contribution=p["monthly_contribution"] * factor)
        f = base_final if factor == 1.0 else _final(s)
        contribution.append({"factor": factor, "monthly_contribution": p["monthly_contribution"] * factor,
                             "final_nominal": f["value_after_costs"], "final_real": f["real_value"]})
    horizons = sorted({h for h in HORIZON_CHOICES if h <= 100} | {p["years"]})
    duration = []
    for years in horizons:
        if years == p["years"]:
            f = base_final
        else:
            f = _final(_scenario(p, p["strategies"][0], years=years))
        duration.append({"years": years, "final_nominal": f["value_after_costs"], "final_real": f["real_value"],
                         "contributions": f["contributions"]})
    return {"monthly_contribution": contribution, "duration": duration}


def _crisis_block(p, base_scenario, base_final):
    """משבר אחד שנבחר + תחנות הזמן של התובנות מחושבים על האסטרטגיה הראשית."""
    crisis = p["crisis"]
    if crisis is None:
        return {"applied": False}
    shocked = simulate(_with_crisis(base_scenario, crisis))
    f = shocked["final"]
    month = crisis.get("month")
    if month is None:
        truncated = crisis["year"] - 1 + RECOVERY_YEARS[crisis["recovery"]] >= p["years"]
    else:
        truncated = (crisis["year"] - 1) * 12 + (month - 1) + 12 * RECOVERY_YEARS[crisis["recovery"]] >= p["years"] * 12
    block = {
        "applied": True, "settings": crisis,
        "final_nominal": f["value_after_costs"], "final_real": f["real_value"],
        "delta_vs_no_crisis": f["value_after_costs"] - base_final["value_after_costs"],
        "series": _series(shocked),
        "recovery_truncated_by_horizon": truncated,
        "note": "ההתאוששות מחזירה לנתיב המגמה בלי המשבר, וההפקדה השוטפת קונה בזול בזמן הירידה — "
                "לכן השווי הסופי עשוי לעלות בהשוואה לנתיב ללא משבר. זו תוצאה של הנחות המודל, לא תחזית.",
    }
    if month is not None:
        block["intra_year"] = _intra_year_block(p, base_scenario, crisis, base_final, truncated)
    return block


def _intra_year_block(p, scenario, crisis, base_final, truncated):
    """משבר תוך-שנתי: מסלול חודשי סביב המשבר + אותו משבר בכל אחד מ-12 חודשי השנה (איך העיתוי מול ההפקדות משנה את התוצאה)."""
    month = crisis["month"]
    n = RECOVERY_YEARS[crisis["recovery"]]
    total = p["years"] * 12
    start = (crisis["year"] - 1) * 12 + (month - 1)
    first = max(0, start - 12)
    last = min(total - 1, start + 12 * n + 12)
    plain = simulate(scenario, monthly=True)["monthly"]
    shocked = simulate(_with_crisis(scenario, crisis), monthly=True)["monthly"]
    path = [{"month_index": i, "t_years": (i + 1) / 12, "year": i // 12 + 1, "month": i % 12 + 1,
             "nominal_no_crisis": plain[i]["value_after_costs"], "nominal_crisis": shocked[i]["value_after_costs"],
             "real_no_crisis": plain[i]["real_value"], "real_crisis": shocked[i]["real_value"],
             "contributions": plain[i]["contributions"]} for i in range(first, last + 1)]
    by_month = []
    for m in range(1, 13):
        alt = {**crisis, "month": m}
        f = _final(_with_crisis(scenario, alt))
        by_month.append({"month": m, "is_selected": m == month, "final_nominal": f["value_after_costs"], "final_real": f["real_value"],
                         "delta_vs_no_crisis": f["value_after_costs"] - base_final["value_after_costs"]})
    return {
        "month": month, "year": crisis["year"], "recovery_months": 12 * n, "recovery_truncated_by_horizon": truncated,
        "monthly_path": path, "timing_by_month": by_month,
        "deposit_order_note": _intra_year_order_note(p["deposit_timing"], month),
        "note": ("הירידה מוחלת בבת אחת על חודש אחד; ההתאוששות פרוסה בצמיחה חודשית קבועה עד לנתיב המגמה. "
                 "ההפקדות ממשיכות כרגיל, ולכן עיתוי המשבר מול ההפקדות (לא רק עומק הירידה) משנה את התוצאה. תוצאת מודל, לא תחזית."),
    }


RLM = "\u200f"  # מונע בלבול כיווניות של % ו-₪ בתוך טקסט עברי


def _money(value):
    return f"{value:,.0f} ₪{RLM}"


def _pct(fraction, digits=1):
    return f"{fraction * 100:.{digits}f}%{RLM}"


def _insights(p, base_scenario, base_final, sensitivity):
    insights = []
    base = base_final["value_after_costs"]
    up = next(x for x in sensitivity["monthly_contribution"] if x["factor"] == 1.25)
    if p["monthly_contribution"] > 0:
        insights.append({"topic": "contribution", "text": (
            f"הגדלת ההפקדה החודשית ב-25%{RLM} ל-{_money(up['monthly_contribution'])} מעלה את השווי הסופי הנומינלי "
            f"ב-{_money(up['final_nominal'] - base)} ({_pct(up['final_nominal'] / base - 1)}), לפי ההנחות שהוזנו.")})
    longer = min(p["years"] + 5, 100)
    if longer > p["years"]:
        extended = _final(replace(base_scenario, years=longer, monthly_contribution=base_scenario.monthly_contribution,
                                  inflation=base_scenario.inflation))
        insights.append({"topic": "duration", "text": (
            f"הארכת התקופה מ-{p['years']} ל-{longer} שנים מוסיפה {_money(extended['value_after_costs'] - base)} "
            f"({_pct(extended['value_after_costs'] / base - 1)}) לשווי הנומינלי; חלק מהתוספת הוא הפקדות נוספות.")})
    higher_fee = replace(base_scenario, assets=tuple(replace(a, annual_fee=min(a.annual_fee + 0.005, 0.99)) for a in base_scenario.assets))
    fee_final = _final(higher_fee)
    gap = base - fee_final["value_after_costs"]
    insights.append({"topic": "fees", "text": (
        f"דמי ניהול ששולמו בפועל: {_money(base_final['management_cost'])}. העלאה של 0.5 נקודות אחוז בדמי הניהול "
        f"הייתה מקטינה את השווי הסופי ב-{_money(gap)} ({_pct(gap / base)}).")})
    early_year = max(1, round(p["years"] * EARLY_LATE_SPLIT[0]))
    late_year = max(early_year + 1, round(p["years"] * EARLY_LATE_SPLIT[1]))
    decline = (p["crisis"] or {}).get("decline_pct", DEFAULT_CRISIS_DECLINE)
    recovery = (p["crisis"] or {}).get("recovery", "fast")
    outcomes = {}
    for label, year in (("early", early_year), ("late", late_year)):
        crisis = {"decline_pct": decline, "year": year, "recovery": recovery}
        outcomes[label] = _final(_with_crisis(base_scenario, crisis))["value_after_costs"]
    insights.append({"topic": "crisis_timing", "text": (
        f"תרחיש הדגמה של ירידה של {decline}%{RLM} עם התאוששות {'מהירה' if recovery == 'fast' else 'ממושכת'}: "
        f"בשנה {early_year} השווי הסופי {_money(outcomes['early'])}, בשנה {late_year} — {_money(outcomes['late'])}. "
        f"תלוי בהנחות המודל ובהפקדה השוטפת; אינו תחזית.")})
    real_share = base_final["real_value"] / base
    insights.append({"topic": "inflation", "text": (
        f"הכוח הקנייתי של השווי הסופי הוא {_pct(real_share)} מהערך הנומינלי, לפי אינפלציה של {_pct(p['inflation'])} בשנה.")})
    return insights[:5]


def _assumption_list(p):
    items = [
        {"id": "return", "text": f"תשואה ברוטו אפקטיבית שנתית של {p['annual_return'] * 100:.2f}% לקרן העולמית", "assumption_based": True},
        {"id": "fee", "text": f"דמי ניהול של {p['annual_fee'] * 100:.2f}% בשנה, זהים לכל הרכיבים", "assumption_based": True},
        {"id": "inflation", "text": f"אינפלציה קבועה של {p['inflation'] * 100:.2f}% בשנה", "assumption_based": True},
        {"id": "timing", "text": "הפקדות בתחילת החודש" if p["deposit_timing"] == "begin" else "הפקדות בסוף החודש", "assumption_based": False},
        {"id": "indexing", "text": "הפקדות צמודות לאינפלציה" if p["index_contributions"] else "הפקדות נומינליות קבועות", "assumption_based": False},
        {"id": "components", "text": "תשואות רכיבי האסטרטגיות האחרות (" + ", ".join(
            f"{COMPONENT_LABELS[k]} {v * 100:.1f}%" for k, v in p["components"].items()) + ") הן הנחות להמחשה ואינן נתוני שוק", "assumption_based": True},
        {"id": "weights", "text": "משקלי האסטרטגיות הם דוגמאות מהמנוע, ללא איזון מחדש; אינם המלצה", "assumption_based": True},
        {"id": "smoothing", "text": "תשואה שנתית מפוזרת על 12 חודשים; אין מודל לירידה חדה בתוך שנה", "assumption_based": True},
        {"id": "tax", "text": "מס: לא מחושב. כל נתון מס שלא אומת חיצונית הוא תוצאה תיאורטית בלבד", "assumption_based": True},
    ]
    if p["crisis"]:
        c = p["crisis"]
        month_text = "" if c.get("month") is None else f", בחודש {c['month']} של השנה (ירידה בבת אחת)"
        items.append({"id": "crisis", "text": (
            f"תרחיש משבר: ירידה של {c['decline_pct']}% בשנה {c['year']}{month_text}, התאוששות {'מהירה (שנה)' if c['recovery'] == 'fast' else 'ממושכת (3 שנים)'} "
            "לנתיב המגמה; תרחיש מודלי בלבד"), "assumption_based": True})
    return items


def build_simulator_view(params=None, tax_model=None):
    """הכניסה היחידה: אחוזים כפי שמוצגים במסך → מבנה JSON מלא להצגה."""
    p = normalize_params(DEFAULTS_COPY() if params is None else params)
    scenarios = {name: _scenario(p, name) for name in p["strategies"]}
    comparison = compare(scenarios, {p["strategies"][0]: tax_model} if tax_model else None)
    primary_name = p["strategies"][0]
    primary = comparison["strategies"][primary_name]
    base_scenario = scenarios[primary_name]
    base_final = primary["final"]
    sensitivity = _sensitivity(p, base_final)
    table = []
    gaps = comparison["gaps_vs_baseline"]
    for name in p["strategies"]:
        f = comparison["strategies"][name]["final"]
        table.append({
            "strategy": name, "label": STRATEGY_LABELS[name], "is_baseline": name == primary_name,
            "final_nominal": f["value_after_costs"], "final_real": f["real_value"],
            "contributions": f["contributions"], "net_profit": f["nominal_profit"],
            "costs": f["costs_paid"], "gap_vs_baseline": gaps[name]["after_costs"],
        })
    warnings = list(primary["warnings"])
    if (p["crisis"] or {}).get("month") is not None:
        smoothed = "Annual returns are smoothed across 12 months; intra-year crash timing is not modelled."
        warnings = [w for w in warnings if w != smoothed]
        warnings.append("Only the selected crisis month is modelled as a one-month drop; all other months follow the annual smoothing. Model scenario, not a forecast.")
    if p["strategies"] != ["global"] and len(p["strategies"]) > 1:
        warnings.append("השוואת אסטרטגיות מבוססת על הנחות תשואה להמחשה; אינה דירוג של קרנות אמיתיות.")
    return {
        "schema_version": VIEW_SCHEMA_VERSION, "source": "portfolio_lab", "engine_version": ENGINE_VERSION,
        "result_type": primary["result_type"], "currency": "ILS",
        "inputs": {k: v for k, v in p.items() if k not in {"components"}},
        "primary_strategy": {"id": primary_name, "label": STRATEGY_LABELS[primary_name]},
        "kpis": _kpis(primary),
        "charts": {
            "growth": {"series": _series(primary), "crisis": _crisis_block(p, base_scenario, base_final)},
            "strategy_comparison": {name: _series(comparison["strategies"][name]) for name in p["strategies"]},
            "breakdown": _breakdown(base_final),
            "sensitivity": sensitivity,
        },
        "comparison_table": table,
        "insights": _insights(p, base_scenario, base_final, sensitivity),
        "assumptions": _assumption_list(p),
        "warnings": warnings,
        "labels": {"strategies": STRATEGY_LABELS, "components": COMPONENT_LABELS},
        "replay_digest": primary["replay_digest"],
    }


def DEFAULTS_COPY():
    return {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
