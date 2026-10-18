"""סימולציה חודשית ללא I/O, נתוני שוק או כללי מס מובנים."""

from calendar import monthrange
from dataclasses import asdict, replace
from datetime import date
import hashlib
import json
import math

from .models import ENGINE_VERSION, Asset, PurchaseLot, SaleContext, Scenario, Source, TaxAssessment, TaxModel, number, text


ALLOCATION_TEMPLATES = {
    "global": {"global_accumulating": 1.0},
    "world_em": {"msci_world": 0.9, "emerging_markets": 0.1},
    "three_funds": {"sp500": 0.6, "europe": 0.2, "emerging_markets": 0.2},
    "experimental_90_10": {"global_accumulating": 0.9, "selected_stocks": 0.1},
}


def strategy_assets(template: str, assumptions: dict[str, Asset], weights=None) -> tuple[Asset, ...]:
    """תשואות ועמלות חייבות להגיע מהקורא; משקלי הדוגמה אינם המלצה."""
    if template not in ALLOCATION_TEMPLATES:
        raise ValueError("unknown allocation template")
    allocation = dict(ALLOCATION_TEMPLATES[template] if weights is None else weights)
    if set(allocation) != set(ALLOCATION_TEMPLATES[template]):
        raise ValueError("weights must contain exactly the template components")
    assets = tuple(replace(assumptions[name], name=name, weight=weight) for name, weight in allocation.items())
    Scenario(assets=assets)
    return assets


def _year(values, index):
    return values[0] if len(values) == 1 else values[index]


def _dates(start, month):
    offset = start.year * 12 + start.month - 1 + month
    year, zero_month = divmod(offset, 12)
    first = date(year, zero_month + 1, 1)
    return first.isoformat(), date(year, zero_month + 1, monthrange(year, zero_month + 1)[1]).isoformat()


def simulate(scenario: Scenario, tax_model: TaxModel | None = None, *, monthly: bool = False) -> dict:
    """כל הפקדה מתוזמנת בנפרד; המס מופעל רק במכירה המלאה ההיפותטית. `monthly=True` מוסיף שורה לכל חודש (סוף החודש) ל-`monthly`
    ונכלל ב-digest; ברירת המחדל לא משנה דבר בתוצאה."""
    if not isinstance(scenario, Scenario):
        raise ValueError("simulate requires Scenario")
    start = date.fromisoformat(scenario.start_date)
    assets = scenario.assets
    balances = [0.0] * len(assets)
    zero_cost = [0.0] * len(assets)
    prices = [1.0] * len(assets)
    lots = []
    contributed = real_contributed = management_cost = buy_cost = fixed_cost = 0.0
    cpi = gross_index = net_index = 1.0
    rows = []
    month_rows = []
    gross_known = all(a.return_basis == "gross" for a in assets)

    def deposit(amount, purchased_on):
        nonlocal contributed, real_contributed, buy_cost
        contributed += amount
        real_contributed += amount / cpi
        for i, asset in enumerate(assets):
            cash = amount * asset.weight
            fee = cash * asset.buy_fee
            balances[i] += cash - fee
            zero_cost[i] += cash
            buy_cost += fee
            if cash:
                lots.append(PurchaseLot(asset.name, purchased_on, (cash - fee) / prices[i], prices[i], cash, fee, cpi))

    deposit(scenario.initial, scenario.start_date)
    for month in range(scenario.years * 12):
        year = month // 12
        first, last = _dates(start, month)
        base = _year(scenario.monthly_contribution, year)
        if scenario.deposit_timing == "begin":
            deposit(base * cpi if scenario.index_contributions else base, first)
        old_total = sum(balances)
        gross_total = sum(zero_cost)
        gross_weights = [b / gross_total for b in zero_cost] if gross_total else [a.weight for a in assets]
        # ללא הון, מדדי התשואה מתארים את משקלי ההפקדות בלבד.
        weights = [b / old_total for b in balances] if old_total else [a.weight for a in assets]
        gross_factors = []
        net_factors = []
        for i, asset in enumerate(assets):
            rate = _year(asset.annual_return, year)
            factor = (1 + rate) ** (1 / 12) if asset.return_convention == "effective_annual" else 1 + rate / 12
            retained = (1 - asset.annual_fee) ** (1 / 12)
            gross_factors.append(factor)
            net_factors.append(factor * retained)
            zero_cost[i] *= factor
            grown = balances[i] * factor
            fee = grown * (1 - retained)
            management_cost += fee
            balances[i] = grown - fee
            prices[i] *= factor * retained
            if not math.isfinite(prices[i]) or prices[i] <= 0:
                raise ValueError("price overflow/underflow; inputs exceed supported numeric range")
        if scenario.monthly_fixed_cost:      # עלות קבועה נומינלית (למשל ביטוח בפנסיה): יורדת מהיתרה אחרי צמיחה ודמי ניהול, בחלוקה יחסית
            total = sum(balances)
            charge = min(scenario.monthly_fixed_cost, total)
            if total:
                balances = [b - charge * b / total for b in balances]
            fixed_cost += charge
        gross_index *= sum(w * f for w, f in zip(gross_weights, gross_factors))
        net_index *= sum(w * f for w, f in zip(weights, net_factors))
        cpi *= (1 + _year(scenario.inflation, year)) ** (1 / 12)
        if not math.isfinite(cpi) or cpi <= 0:
            raise ValueError("CPI overflow/underflow")
        if scenario.deposit_timing == "end":
            deposit(base * cpi if scenario.index_contributions else base, last)
        value = sum(balances)
        sale_cost = sum(b * a.sell_fee for b, a in zip(balances, assets))
        if monthly:
            month_rows.append({"month": month, "as_of": last, "value_after_costs": value, "real_value": value / cpi, "contributions": contributed})
        if (month + 1) % 12 == 0:
            rows.append({
                "year": year + 1, "as_of": last, "value_before_costs": sum(zero_cost) if gross_known else None,
                "value_after_costs": value, "real_value": value / cpi,
                "contributions": contributed, "real_contributions": real_contributed,
                "nominal_profit": value - contributed, "real_profit": value / cpi - real_contributed,
                "management_cost": management_cost, "buy_cost": buy_cost,
                "costs_paid": management_cost + buy_cost + fixed_cost,
                "cost_impact": sum(zero_cost) - value if gross_known else None,
                "cpi": cpi, "sale_cost": sale_cost, "proceeds_before_tax": value - sale_cost,
                "tax_during_accumulation": 0.0,
            })
            if scenario.monthly_fixed_cost:
                rows[-1]["fixed_cost"] = fixed_cost
    final = dict(rows[-1])
    final.update({
        "nominal_annualized_twr_before_costs": gross_index ** (1 / scenario.years) - 1 if gross_known else None,
        "nominal_annualized_twr_after_recurring_costs": net_index ** (1 / scenario.years) - 1,
        "real_annualized_twr_after_recurring_costs": (net_index / cpi) ** (1 / scenario.years) - 1,
        "total_costs_if_sold": management_cost + buy_cost + fixed_cost + sale_cost,
        "nominal_profit_after_sale_before_tax": value - sale_cost - contributed,
        "tax": None, "proceeds_after_tax": None, "nominal_profit_after_tax": None, "tax_status": "not_assessed",
    })
    assessment = None
    if tax_model is not None:
        context = SaleContext(last, tuple(lots), tuple(zip((a.name for a in assets), prices)), value, sale_cost, value - sale_cost, cpi)
        assessment = tax_model(context)
        if not isinstance(assessment, TaxAssessment):
            raise ValueError("tax model must return TaxAssessment")
        number(assessment.amount, "tax", 0, context.proceeds_before_tax)
        text(assessment.rule_id, "rule_id")
        text(assessment.rule_version, "rule_version")
        if not isinstance(assessment.source, Source) or not isinstance(assessment.parameters, dict):
            raise ValueError("tax assessment requires dated source and parameters")
        if type(assessment.externally_verified) is not bool:
            raise ValueError("externally_verified must be boolean")
        final.update(tax=assessment.amount, proceeds_after_tax=context.proceeds_before_tax - assessment.amount,
                     nominal_profit_after_tax=context.proceeds_before_tax - assessment.amount - contributed,
                     tax_status="externally_verified_adapter" if assessment.externally_verified else "scenario")
    warnings = [
        "Inputs are assumptions unless independently authenticated; no probabilities or investment recommendations.",
        "Annual returns are smoothed across 12 months; intra-year crash timing is not modelled.",
        "No rebalancing, leverage, withdrawals or partial sales; weights drift.",
        "Tax is assessed only for hypothetical terminal full sale; adapter verification is asserted by its provider.",
    ]
    if "selected_stocks" in {a.name for a in assets}:
        warnings.append("Selected-stock allocation is experimental; no selection model is validated.")
    if not scenario.sources:
        warnings.append("No source or data date supplied; provenance is unverified.")
    if not gross_known:
        warnings.append("Net recurring returns supplied: true before-cost values and cost impact are unavailable.")
    statistics = {}
    for asset in assets:
        rates = [_year(asset.annual_return, y) for y in range(scenario.years)]
        effective = rates if asset.return_convention == "effective_annual" else [(1 + r / 12) ** 12 - 1 for r in rates]
        statistics[asset.name] = {
            "basis": asset.return_basis,
            "arithmetic_mean_effective_annual": math.fsum(effective) / scenario.years,
            "geometric_mean_effective_annual": math.expm1(math.fsum(math.log1p(r) for r in effective) / scenario.years),
        }
    inputs = asdict(scenario)
    if not scenario.monthly_fixed_cost:
        inputs.pop("monthly_fixed_cost")           # שדה חדש מופיע רק כשנעשה בו שימוש — digest של תרחישים קיימים לא משתנה
    result = {
        "engine_version": ENGINE_VERSION, "currency": "ILS", "result_type": scenario.result_type,
        "inputs": inputs, "assumptions": {
            "deposit_timing": scenario.deposit_timing,
            "growth": "effective annual root or nominal annual / 12, then recurring fee, every month",
            "fee": "annual fraction of assets lost; monthly retained factor (1-fee)^(1/12)",
            "inflation_indexing": "CPI at each deposit date relative to start date",
            "twr": "monthly linked portfolio returns; excludes buy/sell fees and tax",
            "real_profit": "deflated final value minus separately deflated deposits",
            "units": "synthetic accounting units, not market prices",
        },
        "warnings": warnings, "annual": rows, "final": final,
        "input_return_statistics": statistics,
        "data_as_of": sorted({source.as_of for source in scenario.sources}) or None,
        "purchase_lots": [asdict(lot) for lot in lots],
        "tax_assessment": asdict(assessment) if assessment else None,
    }
    if monthly:
        result["monthly"] = month_rows
    try:
        serialized = json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("nonfinite or non-JSON result; unsupported numeric range/adapter metadata") from error
    result["replay_digest"] = hashlib.sha256(serialized.encode()).hexdigest()
    return result


def compare(scenarios: dict[str, Scenario], tax_models: dict[str, TaxModel] | None = None) -> dict:
    """פערים מול החלופה הראשונה, כאשר תזרים והנחות אינפלציה זהים."""
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError("comparison needs named scenarios")
    baseline_name, baseline = next(iter(scenarios.items()))
    common = ("years", "initial", "monthly_contribution", "inflation", "index_contributions", "deposit_timing", "start_date")
    if tax_models is not None and (not isinstance(tax_models, dict) or set(tax_models) - set(scenarios)):
        raise ValueError("tax models must refer to named comparison scenarios")
    results = {}
    for name, scenario in scenarios.items():
        text(name, "strategy name")
        if any(getattr(scenario, key) != getattr(baseline, key) for key in common):
            raise ValueError("comparison requires identical cash flows, horizon and inflation")
        results[name] = simulate(scenario, (tax_models or {}).get(name))
    base = results[baseline_name]["final"]
    gaps = {}
    for name, result in results.items():
        final = result["final"]
        gaps[name] = {
            "after_costs": final["value_after_costs"] - base["value_after_costs"],
            "after_sale_before_tax": final["proceeds_before_tax"] - base["proceeds_before_tax"],
            "after_tax": final["proceeds_after_tax"] - base["proceeds_after_tax"] if final["proceeds_after_tax"] is not None and base["proceeds_after_tax"] is not None else None,
        }
    return {"baseline": baseline_name, "strategies": results, "gaps_vs_baseline": gaps}
