"""D1 step 7 / A1: per-account + consolidated forecast, a pure assembly layer over the unchanged engine. No network."""

from __future__ import annotations

import copy
import pathlib
from datetime import date

import pytest

from portfolio_lab.accounts_forecast import build_accounts_forecast, normalize_params
from portfolio_lab.engine import simulate
from portfolio_lab.models import Asset, Scenario

TODAY = date(2026, 10, 15)


def acct(aid, value=100000, status="active", fee=None, **extra):
    balance = None if value is None else {"value": value, "as_of": "2026-10-01", "verification": "self_reported",
                                          "estimate": {"value": value + 5, "movements_since": 5, "movement_count": 1, "label": "estimate"}}
    return {"id": aid, "name": f"name-{aid}", "account_type": "study_fund", "status": status, "management_fee_pct": fee, "balance": balance, **extra}


VIEW = {"accounts": [acct("recA", 100000, fee=0.5), acct("recB", 50000), acct("recC", None), acct("recD", 7, status="closed")],
        "totals": {"all_self_reported": True}}


def run(params=None, view=VIEW):
    return build_accounts_forecast(view, params, TODAY)


def test_consolidated_is_the_sum_of_the_per_account_engine_results():
    out = run({"years": 10, "monthly_contributions": {"recA": 1000}})
    assert [a["id"] for a in out["accounts"]] == ["recA", "recB"]
    for key in ("final_nominal", "final_real", "invested"):
        assert out["consolidated"][key] == pytest.approx(sum(a[key] for a in out["accounts"]), abs=0.02)
    assert out["consolidated"]["start_value"] == 150000.0
    assert len(out["consolidated"]["series"]) == 10 and out["consolidated"]["series"][-1]["nominal"] == out["consolidated"]["final_nominal"]


def test_each_account_equals_a_direct_engine_run_so_the_engine_is_not_reimplemented():
    out = run({"years": 15, "annual_return_pct": 7, "inflation_pct": 3, "monthly_contributions": {"recA": 2500}})
    a = out["accounts"][0]
    direct = simulate(Scenario(years=15, initial=100000.0, monthly_contribution=2500.0, inflation=0.03, start_date="2026-10-01",
                               assets=(Asset(name="account", annual_return=0.07, annual_fee=0.005),)))
    assert a["final_nominal"] == direct["final"]["value_after_costs"] and a["final_real"] == direct["final"]["real_value"]


def test_contribution_is_an_input_never_invented_and_starting_value_is_the_snapshot():
    out = run({"years": 10})
    assert all(a["monthly_contribution"] == 0.0 and a["invested"] == a["start_value"] for a in out["accounts"])      # invested = start + deposits (none)
    assert [a["start_value"] for a in out["accounts"]] == [100000, 50000] and out["accounts"][0]["start_as_of"] == "2026-10-01"
    assert "estimate" not in str(out["accounts"][0].keys())        # the labelled movements-estimate is not used as a start


def test_fee_comes_from_the_account_when_present_else_the_labelled_default():
    out = run({"annual_fee_pct": 0.3})
    by = {a["id"]: a for a in out["accounts"]}
    assert (by["recA"]["fee_pct"], by["recA"]["fee_source"]) == (0.5, "account")
    assert (by["recB"]["fee_pct"], by["recB"]["fee_source"]) == (0.3, "default")
    bad = copy.deepcopy(VIEW); bad["accounts"][0]["management_fee_pct"] = 99
    assert {a["id"]: a for a in run(None, bad)["accounts"]}["recA"]["fee_source"] == "default"      # an implausible fee is not trusted


def test_closed_and_snapshotless_accounts_are_excluded_and_counted_not_hidden_or_zeroed():
    out = run()
    assert out["excluded"] == {"without_snapshot": 1, "closed": 1}
    assert all(a["id"] not in ("recC", "recD") for a in out["accounts"])
    empty = run(None, {"accounts": [acct("recC", None)], "totals": {}})
    assert empty["accounts"] == [] and empty["consolidated"]["final_nominal"] is None and empty["consolidated"]["start_value"] == 0


def test_no_free_text_leaves_and_the_input_view_is_not_mutated():
    view = copy.deepcopy(VIEW)
    view["accounts"][0]["notes"] = "private note"
    before = copy.deepcopy(view)
    text = repr(run(None, view))
    assert "private note" not in text and view == before
    assert result_is_labelled(run())


def result_is_labelled(out):
    return out["result_type"] == "assumption_based_projection" and any("הבטחת תשואה" in w for w in out["warnings"])


@pytest.mark.parametrize("params", [
    {"years": 9}, {"years": 101}, {"years": 20.5}, {"years": True}, {"annual_return_pct": 51}, {"annual_return_pct": float("nan")},
    {"annual_fee_pct": -1}, {"annual_fee_pct": 11}, {"inflation_pct": "2"}, {"deposit_timing": "mid"}, {"bogus": 1}, [], "x",
    {"monthly_contributions": {"recA": -5}}, {"monthly_contributions": {"recA": "100"}}, {"monthly_contributions": {"bad": 5}},
    {"monthly_contributions": []}, {"monthly_contributions": {"recZZZ": 5}},
])
def test_invalid_params_are_rejected(params):
    with pytest.raises(ValueError):
        run(params)


def test_defaults_are_the_documented_ones():
    p = normalize_params(None)
    assert (p["years"], p["annual_return"], p["annual_fee"], p["inflation"], p["deposit_timing"]) == (20, 0.06, 0.0015, 0.02, "end")


def test_module_is_pure_no_io_or_airtable_imports():
    text = (pathlib.Path(__file__).parent / "portfolio_lab/accounts_forecast.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "airtable", "core.financial_control", "open(", "os.environ", "anthropic"):
        assert forbidden not in text, forbidden


# ── D1 step 9: per-account inputs (planned deposit, deposit fee, expected return + linkage, insurance cost) ──────────────
def plan(view_accounts):
    return {"accounts": view_accounts, "totals": {"all_self_reported": True}}


def one(params=None, **extra):
    return run(params, plan([acct("recA", 100000, **extra)]))["accounts"][0]


def test_engine_fixed_monthly_cost_is_exact_and_zero_is_a_no_op():
    base = dict(years=10, initial=100000.0, monthly_contribution=0.0, inflation=0.0, start_date="2026-10-01",
                assets=(Asset(name="a", annual_return=0.0, annual_fee=0.0),))
    assert simulate(Scenario(**base))["final"]["value_after_costs"] == pytest.approx(100000.0)
    out = simulate(Scenario(monthly_fixed_cost=100.0, **base))["final"]
    assert out["value_after_costs"] == pytest.approx(100000.0 - 100.0 * 120) and out["fixed_cost"] == pytest.approx(12000.0)
    assert out["costs_paid"] == pytest.approx(12000.0)
    drained = simulate(Scenario(monthly_fixed_cost=5000.0, **base))["final"]
    assert drained["value_after_costs"] == 0 and drained["fixed_cost"] == pytest.approx(100000.0)      # never below zero
    with pytest.raises(ValueError):
        Scenario(monthly_fixed_cost=-1.0, **base)


def test_planned_deposit_is_the_default_but_a_typed_value_wins_and_each_source_is_labelled():
    assert (one(planned_monthly_deposit=1500)["monthly_contribution"], one(planned_monthly_deposit=1500)["monthly_contribution_source"]) == (1500, "account")
    typed = run({"monthly_contributions": {"recA": 200}}, plan([acct("recA", 100000, planned_monthly_deposit=1500)]))["accounts"][0]
    assert (typed["monthly_contribution"], typed["monthly_contribution_source"]) == (200, "typed")
    none = one()
    assert (none["monthly_contribution"], none["monthly_contribution_source"]) == (0.0, "default") and "monthly_deposit" in none["missing"]
    assert one(planned_monthly_deposit=-5)["monthly_contribution_source"] == "default"          # corrupt value is not trusted


def test_deposit_fee_is_taken_from_each_deposit_and_invested_stays_gross():
    a = one({"years": 10, "annual_return_pct": 0, "annual_fee_pct": 0, "inflation_pct": 0}, planned_monthly_deposit=1000, deposit_fee_pct=2.0)
    assert a["invested"] == pytest.approx(100000 + 1000 * 120)
    assert a["deposit_fees_paid"] == pytest.approx(1000 * 0.02 * 120)
    assert a["final_nominal"] == pytest.approx(100000 + 980 * 120)
    assert a["costs_paid"] == pytest.approx(a["deposit_fees_paid"]) and a["nominal_profit"] == pytest.approx(-a["deposit_fees_paid"])
    assert one(planned_monthly_deposit=1000)["deposit_fee_known"] is False and "deposit_fee" in one()["missing"]


def test_expected_return_overrides_the_global_and_cpi_linkage_converts_real_to_nominal():
    g = {"annual_return_pct": 6, "inflation_pct": 2}
    d = one(g)
    assert (d["return_pct"], d["return_source"], d["return_kind"]) == (6.0, "default", "nominal") and "expected_return" in d["missing"]
    n = one(g, expected_return_pct=4.0, linkage="sp500")
    assert (n["return_pct"], n["return_source"], n["return_kind"]) == (4.0, "account", "nominal")
    c = one(g, expected_return_pct=4.0, linkage="cpi")
    assert c["return_kind"] == "real_to_nominal" and c["return_pct"] == pytest.approx((1.04 * 1.02 - 1) * 100, abs=1e-3)
    assert one(g, expected_return_pct=900)["return_source"] == "default"                         # implausible value is not trusted


def test_insurance_cost_reduces_the_result_and_is_reported_separately():
    g = {"years": 10, "annual_return_pct": 0, "annual_fee_pct": 0, "inflation_pct": 0}
    a = one(g, insurance_cost_monthly=200, insurance_cost_as_of="2026-01-01")
    assert a["insurance_paid"] == pytest.approx(24000) and a["final_nominal"] == pytest.approx(100000 - 24000)
    assert a["insurance_cost_known"] is True and "insurance_cost" not in a["missing"] and "insurance_cost_date" not in a["missing"]
    assert "insurance_cost_date" in one(g, insurance_cost_monthly=200)["missing"]
    unknown = one(g)
    assert unknown["insurance_paid"] == 0 and unknown["insurance_cost_known"] is False and "insurance_cost" in unknown["missing"]


def test_data_gaps_list_every_account_with_missing_inputs_and_an_unknown_choice_counts_as_missing():
    full = acct("recA", 100000, fee=0.5, planned_monthly_deposit=500, deposit_fee_pct=1, expected_return_pct=5, investment_track="mixed",
                linkage="none", insurance_cost_monthly=0, insurance_cost_as_of="2026-01-01")
    out = run(None, plan([full, acct("recB", 1000, investment_track="unknown", linkage="unknown")]))
    assert out["accounts"][0]["missing"] == [] and [g["id"] for g in out["data_gaps"]] == ["recB"]
    assert {"investment_track", "linkage", "management_fee"} <= set(out["data_gaps"][0]["missing"])
    assert run(None, plan([full]))["data_gaps"] == []


def test_accounts_overview_reads_the_new_fields_and_tolerates_their_absence():
    from core.financial_control import accounts as fa
    from airtable_schema import FinAccountFields as F
    rec = {"id": "recA", "fields": {F.NAME: "x", F.PLANNED_MONTHLY_DEPOSIT: 2154, F.DEPOSIT_FEE: 1.88, F.INVESTMENT_TRACK: {"name": "mixed"},
                                    F.LINKAGE: {"name": "cpi"}, F.LINKAGE_NOTES: "מדד", F.EXPECTED_RETURN: 3.5,
                                    F.INSURANCE_COST_MONTHLY: 120, F.INSURANCE_COST_AS_OF: "2026-09-30"}}
    row = fa.accounts_overview([rec, {"id": "recB", "fields": {F.NAME: "bare"}}], [], TODAY)["accounts"]
    assert (row[0]["planned_monthly_deposit"], row[0]["deposit_fee_pct"], row[0]["investment_track"], row[0]["linkage"]) == (2154.0, 1.88, "mixed", "cpi")
    assert (row[0]["expected_return_pct"], row[0]["insurance_cost_monthly"], row[0]["insurance_cost_as_of"]) == (3.5, 120.0, "2026-09-30")
    assert all(row[1][k] is None for k in ("planned_monthly_deposit", "deposit_fee_pct", "investment_track", "linkage", "expected_return_pct", "insurance_cost_monthly"))


# ── D1 step 9 review gaps ───────────────────────────────────────────────────────────────────────────────────────────────
def test_cpi_linkage_does_not_apply_inflation_twice():
    g = {"years": 10, "annual_fee_pct": 0, "inflation_pct": 5}
    a = one(g, expected_return_pct=4.0, linkage="cpi")
    assert a["return_kind"] == "real_to_nominal"
    assert a["final_real"] == pytest.approx(100000 * 1.04 ** 10, rel=1e-6)           # the real result is the owner's real return, nothing more
    assert a["final_nominal"] == pytest.approx(100000 * (1.04 * 1.05) ** 10, rel=1e-6)
    nominal = one(g, expected_return_pct=4.0, linkage="none")                       # same number, not CPI-linked: stays nominal, inflation erodes it
    assert nominal["final_nominal"] == pytest.approx(100000 * 1.04 ** 10, rel=1e-6) and nominal["final_real"] < a["final_real"]


def test_costs_are_counted_once_each_deposit_fee_management_fee_and_insurance():
    g = {"years": 10, "annual_return_pct": 0, "annual_fee_pct": 0, "inflation_pct": 0}
    a = one(g, planned_monthly_deposit=1000, deposit_fee_pct=2.0, insurance_cost_monthly=100, insurance_cost_as_of="2026-01-01")
    assert a["deposit_fees_paid"] == pytest.approx(2400) and a["insurance_paid"] == pytest.approx(12000)
    assert a["costs_paid"] == pytest.approx(2400 + 12000)                            # no management fee, no engine buy_fee: nothing counted twice
    assert a["final_nominal"] == pytest.approx(100000 + 980 * 120 - 12000)
    assert a["invested"] == pytest.approx(100000 + 1000 * 120)
    d = simulate(Scenario(years=10, initial=100000.0, monthly_contribution=980.0, inflation=0.0, start_date="2026-10-01", monthly_fixed_cost=100.0,
                          assets=(Asset(name="account", annual_return=0.0, annual_fee=0.0),)))["final"]
    assert d["buy_cost"] == 0 and d["management_cost"] == 0                          # the deposit fee is not also an engine buy fee


def test_empty_fields_stay_null_in_the_view_and_are_never_coerced_to_zero_by_the_forecast():
    view = plan([acct("recA", 100000)])
    before = copy.deepcopy(view)
    a = run({"years": 10}, view)["accounts"][0]
    assert view == before                                                            # nothing written back into the input
    assert a["monthly_contribution_source"] == "default" and a["insurance_cost_known"] is False and a["deposit_fee_known"] is False
    assert {"monthly_deposit", "deposit_fee", "expected_return", "insurance_cost", "management_fee"} <= set(a["missing"])


def test_historical_deposits_are_not_assumed_to_continue_and_a_snapshot_is_not_topped_up():
    from core.financial_control import accounts as fa
    from airtable_schema import FinAccountFields as F, FinEventFields as E
    acc = {"id": "recA", "fields": {F.NAME: "x", F.STATUS: "active"}}

    def ev(rid, kind, amount, day):
        return {"id": rid, "fields": {E.KIND: {"name": kind}, E.AMOUNT: amount, E.OCCURRED_AT: day, E.ACCOUNT: ["recA"]}}
    events = [ev("recDold", "deposit", 700, "2026-08-01"), ev("recS", "balance_snapshot", 100000, "2026-10-01"), ev("recDnew", "deposit", 500, "2026-10-05")]
    view = fa.accounts_overview([acc], events, TODAY)
    assert view["accounts"][0]["balance"]["value"] == 100000 and view["accounts"][0]["balance"]["estimate"]["movements_since"] == 500    # the old deposit is inside the snapshot
    out = build_accounts_forecast(view, {"years": 10}, TODAY)["accounts"][0]
    assert out["start_value"] == 100000 and out["monthly_contribution"] == 0.0 and out["monthly_contribution_source"] == "default"    # no recurring deposit inferred
