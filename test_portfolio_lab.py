"""Unit/CLI checks only; no credentials, network, bot or external services."""

from dataclasses import replace
import json
import math
import subprocess
import sys

import pytest

from portfolio_lab import Asset, Scenario, Source, TaxAssessment, compare, simulate, strategy_assets


def scenario(**kwargs):
    return Scenario(years=10, assets=(Asset(annual_return=0, annual_fee=0),), **kwargs)


def test_zero_and_no_investment():
    result = simulate(scenario(initial=500))
    assert result["final"]["value_after_costs"] == 500 + 8000 * 120
    empty = simulate(scenario(monthly_contribution=0))
    assert empty["final"]["value_after_costs"] == 0
    assert empty["purchase_lots"] == []
    assert empty["final"]["tax"] is None


@pytest.mark.parametrize("timing", ["begin", "end"])
@pytest.mark.parametrize("convention", ["effective_annual", "nominal_annual_monthly"])
def test_independent_annuity_formula(timing, convention):
    s = Scenario(initial=12345, deposit_timing=timing, assets=(Asset(annual_return=0.08, return_convention=convention, annual_fee=0),))
    i = 1.08 ** (1 / 12) - 1 if convention == "effective_annual" else 0.08 / 12
    n = s.years * 12
    expected = s.initial * (1 + i) ** n + 8000 * ((1 + i) ** n - 1) / i * (1 + i if timing == "begin" else 1)
    result = simulate(s)
    assert result["final"]["value_after_costs"] == pytest.approx(expected, rel=1e-12)
    expected_year = s.initial * (1 + i) ** 12 + 8000 * ((1 + i) ** 12 - 1) / i * (1 + i if timing == "begin" else 1)
    assert result["annual"][0]["value_after_costs"] == pytest.approx(expected_year)


def test_changing_contributions_and_inflation():
    amounts = [1000] * 5 + [2000] * 5
    final = simulate(scenario(monthly_contribution=amounts))["final"]
    assert final["contributions"] == 180000
    assert final["real_value"] == pytest.approx(180000 / 1.02 ** 10)
    real_paid = sum(amounts[m // 12] / 1.02 ** ((m + 1) / 12) for m in range(120))
    assert final["real_profit"] == pytest.approx(180000 / 1.02 ** 10 - real_paid)


@pytest.mark.parametrize("timing,offset", [("begin", 0), ("end", 1)])
def test_indexed_deposits(timing, offset):
    s = scenario(monthly_contribution=1000, index_contributions=True, deposit_timing=timing)
    final = simulate(s)["final"]
    expected = sum(1000 * 1.02 ** ((m + offset) / 12) for m in range(120))
    assert final["contributions"] == pytest.approx(expected)
    assert final["real_contributions"] == pytest.approx(120000)


def test_inflation_years_and_real_return():
    s = Scenario(years=10, initial=100, monthly_contribution=0, inflation=[0.01] * 5 + [0.03] * 5, assets=(Asset(annual_return=0.08, annual_fee=0),))
    f = simulate(s)["final"]
    cpi = 1.01 ** 5 * 1.03 ** 5
    assert f["real_value"] == pytest.approx(100 * 1.08 ** 10 / cpi)
    assert f["real_annualized_twr_after_recurring_costs"] == pytest.approx(1.08 / cpi ** 0.1 - 1)


def test_fee_formula_and_accounting():
    s = Scenario(years=10, initial=100000, monthly_contribution=0, assets=(Asset(annual_return=0.08, annual_fee=0.01, buy_fee=0.02, sell_fee=0.03),))
    f = simulate(s)["final"]
    assert f["value_before_costs"] == pytest.approx(100000 * 1.08 ** 10)
    assert f["value_after_costs"] == pytest.approx(98000 * (1.08 * 0.99) ** 10)
    assert f["buy_cost"] == 2000
    assert f["sale_cost"] == pytest.approx(f["value_after_costs"] * 0.03)
    assert f["proceeds_before_tax"] == pytest.approx(f["value_after_costs"] * 0.97)
    assert f["cost_impact"] == pytest.approx(f["value_before_costs"] - f["value_after_costs"])
    assert f["cost_impact"] > f["costs_paid"]
    flat = simulate(Scenario(years=10, initial=100, monthly_contribution=0, assets=(Asset(annual_return=0, annual_fee=0.01),)))["final"]
    assert flat["management_cost"] + flat["value_after_costs"] == pytest.approx(100)


def test_buy_fee_and_monthly_fee_timing():
    s = scenario(monthly_contribution=100, inflation=0)
    s = replace(s, assets=(Asset(annual_return=0, annual_fee=0, buy_fee=0.01),))
    assert simulate(s)["final"]["value_after_costs"] == pytest.approx(11880)
    assert simulate(s)["final"]["costs_paid"] == pytest.approx(120)
    fee = 0.12
    s = replace(s, assets=(Asset(annual_return=0, annual_fee=fee),))
    factor = (1 - fee) ** (1 / 12)
    expected = sum(100 * factor ** k for k in range(120))
    assert simulate(s)["final"]["value_after_costs"] == pytest.approx(expected)


def test_net_returns_do_not_double_count():
    with pytest.raises(ValueError, match="double counting"):
        Asset(return_basis="net_recurring")
    s = Scenario(years=10, assets=(Asset(return_basis="net_recurring", annual_fee=0),))
    r = simulate(s)
    assert r["final"]["value_before_costs"] is None
    assert r["final"]["cost_impact"] is None
    assert r["final"]["nominal_annualized_twr_before_costs"] is None


@pytest.mark.parametrize("drop", [0.1, 0.2, 0.3, 0.4, 0.5])
def test_crash_recovery_and_sequence(drop):
    rates = [-drop, 1 / (1 - drop) - 1] + [0.08] * 8
    reverse = list(reversed(rates))
    a = Scenario(years=10, inflation=0, assets=(Asset(annual_return=rates, annual_fee=0),))
    b = replace(a, assets=(Asset(annual_return=reverse, annual_fee=0),))
    ra, rb = simulate(a), simulate(b)
    assert sum(rates) == pytest.approx(sum(reverse))
    assert math.prod(1 + r for r in rates) == pytest.approx(math.prod(1 + r for r in reverse))
    assert ra["final"]["contributions"] == rb["final"]["contributions"] == 960000
    assert ra["final"]["value_after_costs"] != pytest.approx(rb["final"]["value_after_costs"])
    assert ra["final"]["nominal_annualized_twr_before_costs"] == pytest.approx(rb["final"]["nominal_annualized_twr_before_costs"])
    lump_a = simulate(replace(a, initial=100, monthly_contribution=0))
    lump_b = simulate(replace(b, initial=100, monthly_contribution=0))
    assert lump_a["final"]["value_after_costs"] == pytest.approx(lump_b["final"]["value_after_costs"])


def test_terminal_tax_port_and_dated_lots():
    calls = []
    def synthetic_tax(context):
        calls.append(context)
        prices = dict(context.closing_prices)
        gain = sum(l.units * prices[l.asset] - l.cash_paid for l in context.lots)
        return TaxAssessment(max(gain, 0) * 0.2, "synthetic-nominal-full-sale", "test-v1", {"rate": 0.2, "basis": "nominal_cash_paid"}, Source("test-only", "2026-10-13", "Not Israeli law"))
    s = Scenario(years=10, initial=100, monthly_contribution=50, assets=(Asset(annual_return=0.08, annual_fee=0),))
    result = simulate(s, synthetic_tax)
    assert len(calls) == 1
    context = calls[0]
    assert len(context.lots) == 121
    assert context.lots[0].purchased_on == "2026-01-01"
    assert context.lots[1].purchased_on == "2026-01-31"
    assert context.lots[2].purchased_on == "2026-02-28"
    assert context.lots[0].unit_price != context.lots[1].unit_price
    assert sum(l.units * dict(context.closing_prices)[l.asset] for l in context.lots) == pytest.approx(context.gross_proceeds)
    f = result["final"]
    assert f["tax"] == pytest.approx(f["nominal_profit"] * 0.2)
    assert f["proceeds_after_tax"] == pytest.approx(f["proceeds_before_tax"] - f["tax"])
    assert f["tax_status"] == "scenario"
    assert all(row["tax_during_accumulation"] == 0 for row in result["annual"])


def test_invalid_tax_assessment():
    def bad(context):
        return TaxAssessment(context.proceeds_before_tax + 1, "test", "1", {}, Source("test", "2026-10-13", "synthetic"))
    with pytest.raises(ValueError, match="tax"):
        simulate(scenario(), bad)


def test_comparison_templates_and_independent_returns():
    rates = {"global_accumulating": 0.06, "msci_world": 0.07, "emerging_markets": 0.04, "sp500": 0.08, "europe": 0.05, "selected_stocks": 0.02}
    assumptions = {name: Asset(name=name, annual_return=r, annual_fee=0) for name, r in rates.items()}
    scenarios = {name: Scenario(years=10, assets=strategy_assets(name, assumptions)) for name in ("global", "world_em", "three_funds", "experimental_90_10")}
    r = compare(scenarios)
    assert len(r["strategies"]) == 4
    assert r["gaps_vs_baseline"]["global"]["after_costs"] == 0
    assert r["gaps_vs_baseline"]["world_em"]["after_costs"] != 0
    assert r["gaps_vs_baseline"]["world_em"]["after_tax"] is None
    assert any("experimental" in w for w in r["strategies"]["experimental_90_10"]["warnings"])
    with pytest.raises(ValueError, match="identical"):
        compare({"a": scenarios["global"], "b": replace(scenarios["global"], monthly_contribution=1)})
    edited = strategy_assets("world_em", assumptions, {"msci_world": 0.7, "emerging_markets": 0.3})
    assert edited[0].weight == 0.7


def test_multisleeve_buy_hold_equals_independent_sleeves():
    assets = (Asset(name="a", weight=0.3, annual_return=0.1, annual_fee=0.002), Asset(name="b", weight=0.7, annual_return=-0.02, annual_fee=0.001))
    s = Scenario(years=10, initial=10000, assets=assets)
    expected = sum(simulate(replace(s, initial=s.initial * a.weight, monthly_contribution=8000 * a.weight, assets=(replace(a, weight=1),)))["final"]["value_after_costs"] for a in assets)
    assert simulate(s)["final"]["value_after_costs"] == pytest.approx(expected)


def test_100_year_large_values_and_replay():
    s = Scenario(years=100, initial=10**12, monthly_contribution=10**9)
    r = simulate(s)
    assert len(r["annual"]) == 100
    assert math.isfinite(r["final"]["value_after_costs"])
    replay = simulate(Scenario.from_dict(json.loads(json.dumps(r["inputs"]))))
    assert replay == r
    json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("kwargs", [{"years": 9}, {"years": True}, {"initial": -1}, {"initial": float("nan")}, {"inflation": -1}, {"monthly_contribution": [1, 2]}, {"index_contributions": 1}, {"deposit_timing": "daily"}, {"start_date": "2026-01-02"}, {"result_type": "historical"}])
def test_invalid_scenario(kwargs):
    with pytest.raises((ValueError, TypeError)):
        Scenario(**kwargs)


@pytest.mark.parametrize("kwargs", [{"weight": 2}, {"annual_fee": 1}, {"buy_fee": -1}, {"annual_return": -1}, {"annual_return": float("inf")}, {"annual_return": True}, {"return_convention": "guess"}])
def test_invalid_asset(kwargs):
    with pytest.raises(ValueError):
        Asset(**kwargs)


def test_invalid_weights_and_lengths():
    with pytest.raises(ValueError, match="sum"):
        Scenario(assets=(Asset(weight=0.5),))
    with pytest.raises(ValueError, match="annual_return"):
        Scenario(assets=(Asset(annual_return=[0.1, 0.2]),))


def test_cli_roundtrip_and_comparison():
    data = {"years": 10, "monthly_contribution": 100, "inflation": 0, "assets": [{"annual_return": 0, "annual_fee": 0}]}
    run = subprocess.run([sys.executable, "-m", "portfolio_lab"], input=json.dumps(data), text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == json.loads(json.dumps(simulate(Scenario.from_dict(data))))
    run = subprocess.run([sys.executable, "-m", "portfolio_lab"], input=json.dumps({"strategies": {"a": data, "b": data}}), text=True, capture_output=True)
    assert run.returncode == 0
    assert json.loads(run.stdout)["gaps_vs_baseline"]["b"]["after_costs"] == 0


@pytest.mark.parametrize("payload", ['{"initial": NaN}', '{"years": 10, "years": 20}', '[]', '{"unknown": 1}', '{"strategies": []}', '{"assets": [null]}'])
def test_cli_errors(payload):
    run = subprocess.run([sys.executable, "-m", "portfolio_lab"], input=payload, text=True, capture_output=True)
    assert run.returncode == 2
    assert run.stdout == ""
    assert "error" in json.loads(run.stderr)


def test_external_calculator_snapshot():
    # Calculator.net result fetched 2026-10-13; nominal APR, monthly end deposits.
    s = Scenario(assets=(Asset(annual_return=0.08, return_convention="nominal_annual_monthly", annual_fee=0),))
    assert round(simulate(s)["final"]["value_after_costs"], 2) == 142308219.78
    assert round(((1 + 0.08 / 12) ** 12 - 1) * 100, 5) == 8.29995


def test_fee_annuity_independent_formula():
    s = Scenario(assets=(Asset(annual_return=0.08, annual_fee=0.0015),))
    i = (1.08 * (1 - 0.0015)) ** (1 / 12) - 1
    expected = 8000 * ((1 + i) ** 720 - 1) / i
    assert simulate(s)["final"]["value_after_costs"] == pytest.approx(expected, rel=1e-12)


def test_return_statistics_and_comparison_digest():
    rates = [-0.5, 1] + [0.08] * 8
    s = Scenario(years=10, assets=(Asset(annual_return=rates, annual_fee=0),))
    r = simulate(s)
    stats = r["input_return_statistics"]["global_accumulating"]
    assert stats["arithmetic_mean_effective_annual"] == pytest.approx(sum(rates) / 10)
    assert stats["geometric_mean_effective_annual"] == pytest.approx(math.prod(1 + r for r in rates) ** 0.1 - 1)
    cmp = compare({"experiment": replace(s, assets=(replace(s.assets[0], name="selected_stocks"),))})
    result = cmp["strategies"]["experiment"]
    assert result == simulate(Scenario.from_dict(json.loads(json.dumps(result["inputs"]))))


def test_import_has_no_bot_dependencies():
    code = "import sys; import portfolio_lab; assert not any(x in sys.modules for x in ('core', 'flask', 'requests', 'numpy', 'airtable', 'anthropic'))"
    run = subprocess.run([sys.executable, "-S", "-c", code], text=True, capture_output=True)
    assert run.returncode == 0, run.stderr


def test_equivalent_nominal_and_effective_inputs():
    nominal = 0.08
    effective = (1 + nominal / 12) ** 12 - 1
    a = Scenario(assets=(Asset(annual_return=nominal, return_convention="nominal_annual_monthly"),))
    b = replace(a, assets=(Asset(annual_return=effective),))
    assert simulate(a)["final"]["value_after_costs"] == pytest.approx(simulate(b)["final"]["value_after_costs"], rel=1e-12)
    assert effective > nominal


def test_60_year_management_fees_independent_sum():
    growth = 1.08 ** (1 / 12)
    retention = 0.9985 ** (1 / 12)
    q = growth * retention
    n = 720
    # Sum of opening balances for an end-month annuity; fees precede each deposit.
    opening_balance_sum = 8000 / (q - 1) * ((q ** n - 1) / (q - 1) - n)
    expected_paid = opening_balance_sum * growth * (1 - retention)
    f = simulate(Scenario())["final"]
    assert f["management_cost"] == pytest.approx(expected_paid, rel=1e-12)
    assert f["management_cost"] == pytest.approx(2201761.1480555823)
    assert f["cost_impact"] > f["management_cost"]


def test_diverging_assets_are_not_automatically_rebalanced():
    assets = (Asset(name="growth", weight=0.5, annual_return=0.1, annual_fee=0), Asset(name="flat", weight=0.5, annual_return=0, annual_fee=0))
    s = Scenario(years=60, initial=1000, monthly_contribution=0, assets=assets)
    f = simulate(s)["final"]
    buy_hold = 500 * 1.1 ** 60 + 500
    annually_rebalanced = 1000 * 1.05 ** 60
    assert f["value_after_costs"] == pytest.approx(buy_hold, rel=1e-12)
    assert f["value_after_costs"] != pytest.approx(annually_rebalanced)
    assert f["nominal_annualized_twr_before_costs"] == pytest.approx((buy_hold / 1000) ** (1 / 60) - 1)


def test_fixture_means_provenance_and_unassessed_tax():
    from pathlib import Path
    data = json.loads(Path("docs/portfolio_lab/crises.json").read_text())
    result = compare({name: Scenario.from_dict(s) for name, s in data["strategies"].items()})
    for output in result["strategies"].values():
        stats = output["input_return_statistics"]["global_accumulating"]
        assert stats["arithmetic_mean_effective_annual"] == pytest.approx(0.0864)
        assert stats["geometric_mean_effective_annual"] == pytest.approx(0.08)
        assert output["result_type"] == "assumption_based_projection"
        assert output["inputs"]["sources"][0]["reference"] == "unverified-demonstration"
        assert output["final"]["tax_status"] == "not_assessed"
        assert output["final"]["proceeds_after_tax"] is None
        assert any("assumptions" in warning for warning in output["warnings"])
