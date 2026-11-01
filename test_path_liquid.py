"""P3 stage 1 — the liquid-cash module (use_liquid_cash / wait), checked against closed-form compound growth."""

from __future__ import annotations

import pytest

from portfolio_lab.path_comparison import core, liquid_paths


def frame(compare_at="2029-10-25", **over):
    raw = {"today": "2026-10-25", "compare_at": compare_at, "inflation_pct": [2.5, 2.5, 2.5], "owner_inputs_label": "הנחות בעלים"}
    raw.update(over)
    return core.make_frame(raw)


def cash(**over):
    spec = {"id": "cash", "label": "מזומן", "type": "use_liquid_cash", "amount": 100000, "expected_return_pct": 6, "fee_pct": 0, "withdraw_fee": 0}
    spec.update(over)
    return spec


def test_using_cash_costs_the_forgone_growth_and_the_after_tax_row_nets_the_preliminary_tax_checked_in_closed_form():
    r = liquid_paths.evaluate(frame(), cash())
    growth = 100000 * 1.06 ** 3 - 100000                         # 19,101.60
    cpi = 1.025 ** 3
    tax = 0.25 * (growth - 100000 * (cpi - 1))                   # tax on the REAL part only
    nw = r["measures"]["net_worth"]
    assert nw["before_latent_tax"]["nominal"] == pytest.approx(-growth, abs=0.01) and nw["after_latent_tax"]["nominal"] == pytest.approx(-(growth - tax), abs=0.01)
    assert nw["after_latent_tax"]["real"] == pytest.approx(-(growth - tax) / cpi, abs=0.01)
    assert r["cost"]["opportunity_cost"] == pytest.approx(growth, abs=0.01) and r["measures"]["economic_cost"]["net_cost"] == pytest.approx(growth - tax, abs=0.01)
    assert r["tax"]["event"] == "none" and r["tax"]["status"] == "preliminary_estimate" and r["provenance"]["tax_on_forgone_growth"] == pytest.approx(tax, abs=0.01)
    assert r["movement_kind"] == "equity_conversion" and r["purpose"] == "fund_amount" and r["funds_amount"] == 100000.0 and r["certainty"] == "expected"
    assert r["after_action"]["given_up"]["lost_future_value"] == pytest.approx(growth, abs=0.01)


def test_a_loss_below_inflation_is_not_taxed_and_a_withdraw_fee_counts_in_both_rows():
    low = liquid_paths.evaluate(frame(), cash(expected_return_pct=1))
    assert low["provenance"]["tax_on_forgone_growth"] == 0.0 and low["measures"]["net_worth"]["before_latent_tax"] == low["measures"]["net_worth"]["after_latent_tax"]
    fee = liquid_paths.evaluate(frame(), cash(withdraw_fee=300))
    base = liquid_paths.evaluate(frame(), cash())
    assert fee["measures"]["net_worth"]["after_latent_tax"]["nominal"] == pytest.approx(base["measures"]["net_worth"]["after_latent_tax"]["nominal"] - 300, abs=0.01)
    assert fee["measures"]["liquidity"]["cash_available"] == 99700.0 and fee["cost"]["fees_total"] == 300.0


def test_a_management_fee_lowers_the_forgone_growth():
    assert liquid_paths.evaluate(frame(), cash(fee_pct=1))["cost"]["opportunity_cost"] < liquid_paths.evaluate(frame(), cash(fee_pct=0))["cost"]["opportunity_cost"]


def test_missing_return_or_fee_is_missing_never_zero_and_no_total_is_shown():
    r = liquid_paths.evaluate(frame(), cash(expected_return_pct=None, withdraw_fee=None))
    assert set(r["missing_inputs"]) == {"expected_return_pct", "withdraw_fee"} and r["certainty"] == "unknown"
    assert r["measures"]["net_worth"]["after_latent_tax"]["nominal"] is None and r["measures"]["economic_cost"]["net_cost"] is None and r["cost"]["opportunity_cost"] is None
    assert r["tax"]["status"] == "not_assessed"
    only = liquid_paths.evaluate(frame(), cash(withdraw_fee=None))
    assert only["missing_inputs"] == ["withdraw_fee"] and only["measures"]["net_worth"]["before_latent_tax"]["nominal"] is None and only["cost"]["opportunity_cost"] is not None


def test_locked_money_is_not_a_funding_path_conditional_money_is_less_certain_and_the_balance_is_checked():
    with pytest.raises(ValueError):
        liquid_paths.evaluate(frame(), cash(liquidity_state="locked"))
    cond = liquid_paths.evaluate(frame(), cash(liquidity_state="conditional"))
    assert cond["certainty"] == "uncertain" and "release_not_verified" in cond["risks"] and cond["measures"]["liquidity"]["state"] == "conditional"
    with pytest.raises(ValueError):
        liquid_paths.evaluate(frame(), cash(balance=50000))
    ok = liquid_paths.evaluate(frame(), cash(balance=130000))
    assert ok["after_action"]["capital_remaining"] == 30000.0 and ok["after_action"]["assets_remaining"][0]["value"] == 30000.0


@pytest.mark.parametrize("over", [{"amount": 0}, {"amount": "1"}, {"expected_return_pct": 99}, {"fee_pct": -1}, {"withdraw_fee": -5}, {"liquidity_state": "maybe"},
                                  {"available_on": "2027-06-01"}, {"surprise": 1}, {"id": " "}])
def test_bad_cash_inputs_are_rejected(over):
    with pytest.raises(ValueError):
        liquid_paths.evaluate(frame(), cash(**over))


def test_describe_inputs_and_unknown_types():
    assert "expected_return_pct" in liquid_paths.describe_inputs("use_liquid_cash")["required"]
    with pytest.raises(ValueError):
        liquid_paths.describe_inputs("loan")
    with pytest.raises(ValueError):
        liquid_paths.evaluate(frame(), {"id": "x", "label": "x", "type": "take_loan"})


# ═══ wait ═══

def wait(**over):
    spec = {"id": "wait", "label": "להמתין", "type": "wait", "amount": 250000, "until": "2027-10-25", "price_change_pct": 4}
    spec.update(over)
    return spec


def test_waiting_moves_nothing_now_does_not_fund_on_time_and_costs_only_the_entered_price_change():
    r = liquid_paths.evaluate(frame(), wait())
    assert r["movement_kind"] == "no_movement" and r["cash_flows"] == [] and r["provenance"]["funds_on_time"] is False and "goal_not_funded_on_time" in r["risks"]
    assert r["measures"]["economic_cost"]["net_cost"] == pytest.approx(10000.0) and r["measures"]["net_worth"]["after_latent_tax"]["nominal"] == pytest.approx(-10000.0)
    assert r["funds_amount"] == 250000.0 and r["measures"]["liquidity"]["cash_available"] == 0.0


def test_no_price_assumption_is_missing_not_zero():
    r = liquid_paths.evaluate(frame(), wait(price_change_pct=None))
    assert r["missing_inputs"] == ["price_change_pct"] and r["measures"]["economic_cost"]["net_cost"] is None and r["certainty"] == "unknown"
    assert r["index_used"]["name"] is None


@pytest.mark.parametrize("over", [{"until": "2026-10-25"}, {"until": "2030-01-01"}, {"until": "soon"}, {"amount": 0}, {"price_change_pct": -95}])
def test_bad_wait_inputs_are_rejected(over):
    with pytest.raises(ValueError):
        liquid_paths.evaluate(frame(), wait(**over))
