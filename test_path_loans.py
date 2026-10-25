"""P3 stage 1 — the loans module (take_loan / prepay_loan), checked against an independent amortization written in the test."""

from __future__ import annotations

from datetime import date

import pytest

from portfolio_lab.path_comparison import core, loan_paths

TODAY = date(2026, 10, 25)


def frame(compare_at="2029-10-25", **over):
    raw = {"today": "2026-10-25", "compare_at": compare_at, "inflation_pct": [2.5, 2.5, 2.5, 2.5, 2.5], "owner_inputs_label": "הנחות בעלים"}
    raw.update(over)
    return core.make_frame(raw)


def loan(**over):
    spec = {"id": "loan", "label": "הלוואה", "type": "take_loan", "amount": 120000, "annual_rate_pct": 6, "term_months": 24, "fees": 0}
    spec.update(over)
    return spec


def oracle(principal, rate_pct, n, paid):
    """Independent level-payment amortization: (payment, interest paid in the first `paid` payments, balance after them)."""
    i = rate_pct / 1200
    pay = principal / n if i == 0 else principal * i / (1 - (1 + i) ** -n)
    bal, interest = principal, 0.0
    for _ in range(paid):
        step = bal * i
        interest += step
        bal -= pay - step
    return pay, interest, bal


# ═══ take_loan ═══

def test_the_loan_amounts_match_an_independent_amortization_over_the_whole_term():
    r = loan_paths.evaluate(frame("2029-10-25"), loan())
    pay, interest, _ = oracle(120000, 6, 24, 24)
    assert r["result"]["monthly_cash_effect"] == pytest.approx(-pay, abs=0.01)
    assert r["cost"]["interest_total"] == pytest.approx(pay * 24 - 120000, abs=0.01) == pytest.approx(interest, abs=0.01)
    assert r["measures"]["economic_cost"]["net_cost"] == pytest.approx(interest, abs=0.01)
    assert r["provenance"]["payments_through_compare"] == 24 and r["provenance"]["liability_at_compare"] == 0.0
    assert r["result"]["cash_at_compare_date"] == pytest.approx(120000 - pay * 24, abs=0.01)


def test_when_the_compare_date_is_before_the_end_only_the_interest_so_far_counts_and_the_liability_remains():
    r = loan_paths.evaluate(frame("2027-10-25"), loan(term_months=60))
    pay, interest, bal = oracle(120000, 6, 60, 12)
    assert r["provenance"]["payments_through_compare"] == 12
    assert r["measures"]["economic_cost"]["net_cost"] == pytest.approx(interest, abs=0.01) and r["provenance"]["liability_at_compare"] == pytest.approx(bal, abs=0.01)
    assert r["cost"]["interest_total"] == pytest.approx(pay * 60 - 120000, abs=0.01)
    assert r["cost"]["interest_total"] > r["measures"]["economic_cost"]["net_cost"]


def test_a_loan_is_not_a_tax_event_and_the_two_latent_tax_rows_coincide():
    r = loan_paths.evaluate(frame(), loan())
    assert r["tax"]["event"] == "none" and r["tax"]["status"] == "not_assessed"
    nw = r["measures"]["net_worth"]
    assert nw["before_latent_tax"] == nw["after_latent_tax"] and nw["after_latent_tax"]["nominal"] == -r["measures"]["economic_cost"]["net_cost"]
    assert r["movement_kind"] == "liability" and r["purpose"] == "fund_amount" and r["funds_amount"] == 120000.0 and r["result"]["balance_effect"] == "adds_liability"


def test_missing_fees_are_missing_not_zero_and_no_total_is_shown():
    r = loan_paths.evaluate(frame(), loan(fees=None))
    assert r["missing_inputs"] == ["fees"] and r["cost"]["fees_total"] is None
    assert r["measures"]["economic_cost"]["net_cost"] is None and r["result"]["cash_at_compare_date"] is None
    assert r["measures"]["net_worth"]["after_latent_tax"]["nominal"] is None and r["measures"]["liquidity"]["cash_available"] is None
    assert any(c["caveat_id"] == "missing_is_missing" for c in r["caveats"])
    paid = loan_paths.evaluate(frame(), loan(fees=1500))
    pay, interest, _ = oracle(120000, 6, 24, 24)
    assert paid["measures"]["economic_cost"]["net_cost"] == pytest.approx(interest + 1500, abs=0.01) and paid["measures"]["liquidity"]["cash_available"] == 118500.0
    assert [f["kind"] for f in paid["cash_flows"][:2]] == ["loan_proceeds", "fee"]


def test_certainty_follows_approval_and_unverified_terms_are_a_risk():
    approved = loan_paths.evaluate(frame(), loan(approved=True, terms_verified=True))
    assert approved["certainty"] == "expected" and "terms_unverified" not in approved["risks"] and approved["index_used"]["verified"] is True
    pending = loan_paths.evaluate(frame(), loan())
    assert pending["certainty"] == "uncertain" and {"terms_unverified", "timing_uncertain", "interest_deductibility_not_assumed"} <= set(pending["risks"])
    assert pending["measures"]["liquidity"]["state"] == "conditional" and approved["measures"]["liquidity"]["state"] == "accessible"


def test_a_zero_rate_loan_costs_no_interest_and_the_retained_capital_shows_its_latent_tax():
    zero = loan_paths.evaluate(frame(), loan(annual_rate_pct=0))
    assert zero["cost"]["interest_total"] == pytest.approx(0, abs=1e-6) and zero["result"]["monthly_cash_effect"] == pytest.approx(-5000, abs=0.01)
    kept = loan_paths.evaluate(frame(), loan(retained_capital=250000, retained_return_pct=6, retained_fee_pct=0.5))
    asset = kept["after_action"]["assets_remaining"][0]
    grown = core.lump_value(frame(), 250000, 6, 0.5)
    assert asset["growth_to_compare"] == pytest.approx(grown["nominal"] - 250000, abs=0.01) and asset["latent_tax_on_growth"] > 0
    assert kept["tax"]["status"] == "preliminary_estimate" and kept["tax"]["latent_at_compare"] == pytest.approx(asset["latent_tax_on_growth"], abs=0.01)
    assert any(c["caveat_id"] == "tax_rate_estimate" for c in kept["caveats"])
    assert loan_paths.evaluate(frame(), loan(retained_capital=250000))["tax"]["status"] == "not_assessed"            # no return entered: nothing invented


@pytest.mark.parametrize("over", [
    {"amount": 0}, {"amount": -5}, {"amount": "120000"}, {"amount": True}, {"annual_rate_pct": -1}, {"annual_rate_pct": 150}, {"term_months": 0}, {"term_months": 12.5},
    {"term_months": 1000}, {"linkage": "cpi"}, {"starts_on": "2030-01-01"}, {"starts_on": "2026-01-01"}, {"approved_by": "x"}, {"fees": -1}, {"id": ""}, {"label": None},
])
def test_bad_loan_inputs_are_rejected(over):
    with pytest.raises(ValueError):
        loan_paths.evaluate(frame(), loan(**over))


def test_only_the_declared_loan_types_and_a_valid_frame_are_accepted():
    with pytest.raises(ValueError):
        loan_paths.evaluate(frame(), loan(type="sell_asset"))
    with pytest.raises(ValueError):
        loan_paths.evaluate({"today": "2026-10-25"}, loan())
    assert loan_paths.describe_inputs("take_loan")["required"] == ["amount", "annual_rate_pct", "term_months"]
    with pytest.raises(ValueError):
        loan_paths.describe_inputs("sell_asset")


def test_a_later_start_moves_the_payments_and_is_deterministic():
    a = loan_paths.evaluate(frame(), loan(starts_on="2027-01-25"))
    assert a["cash_flows"][0]["date"] == "2027-01-25" and a["cash_flows"][1]["date"] == "2027-02-25"
    assert a == loan_paths.evaluate(frame(), loan(starts_on="2027-01-25"))


# ═══ prepay_loan ═══

def prepay(**over):
    spec = {"id": "prepay", "label": "פירעון מוקדם", "type": "prepay_loan", "balance": 100000, "annual_rate_pct": 6, "remaining_months": 60, "early_fee": 500,
            "source_return_pct": 4, "source_fee_pct": 0.5}
    spec.update(over)
    return spec


def test_prepayment_benefit_is_the_interest_avoided_minus_the_fee_and_the_forgone_growth_checked_independently():
    f = frame("2027-10-25")
    r = loan_paths.evaluate(f, prepay())
    pay, interest, _ = oracle(100000, 6, 60, 12)
    grown = core.lump_value(f, 100000, 4, 0.5)
    growth = grown["nominal"] - 100000
    tax = core.tax_on_growth(f, 100000, growth)
    assert r["provenance"]["interest_avoided_through_compare"] == pytest.approx(interest, abs=0.01)
    assert r["measures"]["net_worth"]["before_latent_tax"]["nominal"] == pytest.approx(interest - 500 - growth, abs=0.01)
    assert r["measures"]["net_worth"]["after_latent_tax"]["nominal"] == pytest.approx(interest - 500 - (growth - tax), abs=0.01)
    assert r["measures"]["economic_cost"]["net_cost"] == pytest.approx((500 + (growth - tax)) - interest, abs=0.01)                # cost minus benefit
    assert r["movement_kind"] == "equity_conversion" and r["purpose"] == "reduce_debt" and r["funds_amount"] is None
    assert r["result"]["monthly_cash_effect"] == pytest.approx(pay, abs=0.01) and r["cost"]["fees_total"] == 500.0 and r["cost"]["opportunity_cost"] == pytest.approx(growth, abs=0.01)


def test_prepayment_with_a_missing_fee_or_return_is_missing_not_zero():
    r = loan_paths.evaluate(frame("2027-10-25"), prepay(early_fee=None, source_return_pct=None))
    assert set(r["missing_inputs"]) == {"early_fee", "source_return_pct"} and r["certainty"] == "unknown"
    assert r["measures"]["net_worth"]["after_latent_tax"]["nominal"] is None and r["measures"]["economic_cost"]["net_cost"] is None
    only_fee = loan_paths.evaluate(frame("2027-10-25"), prepay(early_fee=None))
    assert only_fee["missing_inputs"] == ["early_fee"] and only_fee["measures"]["net_worth"]["before_latent_tax"]["nominal"] is None


def test_a_higher_source_return_makes_prepayment_cost_more_and_the_numbers_move_monotonically():
    f = frame("2027-10-25")
    costs = [loan_paths.evaluate(f, prepay(source_return_pct=x))["measures"]["net_worth"]["after_latent_tax"]["nominal"] for x in (0, 3, 6, 9)]
    assert costs == sorted(costs, reverse=True)


@pytest.mark.parametrize("over", [{"balance": 0}, {"remaining_months": 0}, {"remaining_months": 7.5}, {"early_fee": -1}, {"amount": 5}, {"source_return_pct": 90}, {"monthly_payment": 1000}])
def test_bad_prepayment_inputs_are_rejected_and_partial_prepayment_is_not_supported(over):
    with pytest.raises(ValueError):
        loan_paths.evaluate(frame("2027-10-25"), prepay(**over))


def test_the_ranking_helpers_of_payoff_are_never_used():
    import ast
    from pathlib import Path
    tree = ast.parse(Path("portfolio_lab/path_comparison/loan_paths.py").read_text(encoding="utf-8"))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "core.financial_control.loans" in imported and not any("payoff" in m for m in imported)
