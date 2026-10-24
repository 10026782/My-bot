"""בדיקות E1a (מבחן לחץ נזילות, כרית בלבד): parity מול המנוע, אורקלים, הפרדת הון ילדים, שלושה אירועים נפרדים. ללא רשת/שירותים."""

import json
import re

import pytest

from portfolio_lab import Asset, Scenario, simulate
from portfolio_lab.liquidity_stress import build_stress_view, normalize_params, run_cushion

CRISIS = {"decline_pct": 40, "start_month": 1, "recovery_years": 2}


def _p(**kw):
    return normalize_params(kw)


# ── parity מול המנוע ──
@pytest.mark.parametrize("crisis", [None, {"decline_pct": 30, "start_month": 7, "recovery_years": 1}])
def test_parity_with_engine_without_outflows(crisis):
    p = _p(fund_value=500_000, monthly_deposit=8000, monthly_support=0, annual_return_pct=7, annual_fee_pct=0.2,
           horizon_months=120, phase="accumulation", cushion_modes=[0], crisis=crisis)
    mine = run_cushion(p, 0)["final_nominal"]
    asset = Asset(annual_return=0.07, annual_fee=0.002)
    if crisis:
        from portfolio_lab.simulator_view import crisis_asset_monthly
        asset = crisis_asset_monthly(asset, 0.3, 1, 7, 1, 10)
    eng = simulate(Scenario(years=10, initial=500_000, monthly_contribution=8000, inflation=0.02, assets=(asset,)))["final"]["value_after_costs"]
    assert mine == pytest.approx(eng, rel=1e-9)


# ── אורקל כרית ──
def test_cushion_funds_burn_until_exhausted_then_sells():
    p = _p(fund_value=1_000_000, monthly_deposit=0, monthly_support=10_000, annual_return_pct=0, annual_fee_pct=0,
           cushion_modes=[0], horizon_months=24)
    run = run_cushion({**p, "net_burn": 10_000}, 5)  # כרית של 5 חודשי תזרים
    assert run["cushion_exhausted_month"] == 5
    assert [e["month"] for e in run["forced"]] == list(range(6, 25))
    assert run["final_nominal"] == pytest.approx(1_000_000 - 24 * 10_000)


def test_net_burn_includes_other_income_and_deposits():
    p = _p(monthly_support=10_000, monthly_deposit=8_000, other_monthly_expenses=1_000, other_monthly_income=500)
    assert p["net_burn"] == pytest.approx(2_500)


def test_months_of_support_covered_vs_net_burn():
    v = build_stress_view({"monthly_support": 10_000, "monthly_deposit": 8_000, "crisis": CRISIS})
    m24 = next(m for m in v["modes"] if m["cushion_months"] == 24)
    assert m24["free_cushion"] == 48_000 and m24["months_of_support_covered"] == pytest.approx(4.8)
    assert v["net_burn"]["net_burn_per_month"] == 2_000


# ── שלושה אירועים נפרדים ──
def test_forced_sale_without_shortfall_and_collateral_not_applicable():
    v = build_stress_view({"crisis": CRISIS, "cushion_modes": [0]})
    ev = v["modes"][0]["events"]
    assert ev["forced_sale"]["count"] > 0 and ev["cash_shortfall"]["count"] == 0
    assert ev["collateral_call"]["status"] == "not_applicable_no_loan"


def test_shortfall_without_cushion_when_fund_runs_out():
    v = build_stress_view({"fund_value": 100_000, "monthly_deposit": 0, "monthly_support": 20_000, "annual_return_pct": 0,
                           "annual_fee_pct": 0, "cushion_modes": [0], "horizon_months": 12})
    ev = v["modes"][0]["events"]
    assert ev["cash_shortfall"]["count"] > 0 and ev["forced_sale"]["count"] > 0
    assert ev["cash_shortfall"]["first_month"] == 6  # 5 חודשים מכוסים במכירה, בשישי נגמר הכסף


def test_no_forced_sale_when_deposits_cover_support():
    v = build_stress_view({"monthly_deposit": 10_000, "monthly_support": 10_000, "crisis": CRISIS, "cushion_modes": [0]})
    m = v["modes"][0]
    assert m["events"]["forced_sale"]["count"] == 0 and m["window_24m"]["forced_sale_free"] is True


def test_more_cushion_never_increases_forced_sales_in_window():
    v = build_stress_view({"crisis": CRISIS})
    totals = [m["events"]["forced_sale"]["total_amount"] for m in v["modes"]]
    assert totals == sorted(totals, reverse=True)


# ── sequence ──
def test_sequence_matters_only_with_net_outflows():
    def final(start, **kw):
        p = _p(crisis={"decline_pct": 40, "start_month": start, "recovery_years": 2}, cushion_modes=[0], **kw)
        return run_cushion(p, 0)["final_nominal"]
    flat = dict(monthly_deposit=0, monthly_support=0)
    assert final(1, **flat) == pytest.approx(final(61, **flat))  # בלי תזרים: חזרה לנתיב המגמה, סדר לא משנה
    out = dict(monthly_deposit=0, monthly_support=15_000)
    assert final(1, **out) != pytest.approx(final(61, **out))  # עם משיכות: סדר התשואות משנה


def test_no_crisis_delta_zero():
    v = build_stress_view({"cushion_modes": [0, 12]})
    assert all(m["delta_vs_no_crisis"] == 0 and m["window_24m"] is None for m in v["modes"])


def test_crisis_lowers_final_value():
    v = build_stress_view({"crisis": CRISIS})
    deltas = [m["delta_vs_no_crisis"] for m in v["modes"]]
    assert deltas[0] < 0 and deltas == sorted(deltas)  # כרית מקטינה את הנזק
    assert deltas[-1] == pytest.approx(0, abs=0.01)  # 24 חודשי תזרים מכסים את חלון ההתאוששות: אין מכירה במחירי שפל, חזרה לנתיב המגמה


# ── הפרדת הון ילדים וקופות מזומן ──
@pytest.mark.parametrize("bad", [{"in_collateral": True}, {"amount": 100, "in_collateral": False}, {"amount": 1, "pledged": True}])
def test_protected_capital_cannot_be_pledged_or_extended(bad):
    with pytest.raises(ValueError):
        normalize_params({"protected_capital": bad})


def test_protected_capital_untouched_by_any_scenario():
    a = build_stress_view({"crisis": CRISIS, "protected_capital": {"amount": 500_000}})
    b = build_stress_view({"crisis": {**CRISIS, "decline_pct": 80}, "protected_capital": {"amount": 500_000}})
    assert a["protected_capital"] == b["protected_capital"] and a["protected_capital"]["separation"] == "hard"
    assert [m["final_net_value"] for m in build_stress_view({"crisis": CRISIS})["modes"]] == [m["final_net_value"] for m in a["modes"]]


def test_reserved_cash_never_funds_flows():
    base = {"fund_value": 1_000_000, "monthly_deposit": 0, "monthly_support": 10_000, "annual_return_pct": 0, "annual_fee_pct": 0,
            "cushion_modes": [0], "horizon_months": 12}
    plain = build_stress_view(base)["modes"][0]
    held = build_stress_view({**base, "cash_buckets": {"pledged": 200_000, "family_earmarked": 100_000}})["modes"][0]
    assert held["series"][-1]["reserved_cash"] == 300_000
    assert held["final_net_value"] == plain["final_net_value"]  # שמור, לא מושקע ולא מוצא
    assert held["events"]["forced_sale"]["count"] == plain["events"]["forced_sale"]["count"]


def test_free_bucket_is_derived_not_input():
    with pytest.raises(ValueError):
        normalize_params({"cash_buckets": {"free": 10}})


# ── ולידציה ──
@pytest.mark.parametrize("bad", [
    {"loan": {"amount": 1}}, {"cushion_basis": "support_only"}, {"unknown": 1},
    {"fund_value": float("nan")}, {"fund_value": True}, {"monthly_deposit": -1},
    {"phase": "x"}, {"crisis": {"start_month": 1}}, {"crisis": {"decline_pct": 95}},
    {"crisis": {"decline_pct": 40, "start_month": 999}}, {"cushion_modes": []}, {"cushion_modes": [12, 12]},
    {"cushion_modes": [True]}, {"horizon_months": 0}, {"horizon_months": 10_000},
    {"fund_value": 100_000, "cushion_modes": [60]},
])
def test_invalid_inputs_rejected(bad):
    with pytest.raises(ValueError):
        build_stress_view(bad)


# ── דטרמיניזם וניסוח ──
def test_deterministic_and_digest():
    a, b = build_stress_view({"crisis": CRISIS}), build_stress_view({"crisis": CRISIS})
    assert a == b and a["replay_digest"] == b["replay_digest"]
    assert a["result_type"] == "stress_scenario_under_stated_assumptions"


def test_no_forbidden_wording_in_output():
    text = json.dumps(build_stress_view({"crisis": CRISIS}), ensure_ascii=False).lower()
    assert not re.search(r"probabilit|success_rate|chance|recommend|\bsafe\b|סיכוי להצליח|הסתברות", text)
