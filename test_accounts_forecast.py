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
                linkage="none", insurance_cost_monthly=0, insurance_cost_as_of="2026-01-01", liquidity="immediate")
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


# ═══ D1 step 10 / A2: three liquidity states + goal coverage (monthly, server side) ═══
FLAT = {"years": 10, "annual_return_pct": 0, "annual_fee_pct": 0, "inflation_pct": 0}      # constant balances: a state change is the only thing that moves a bucket


def goal(gid="g1", category="savings", target=1000, end="2027-12-31", status="active", title="מטרה"):
    return {"id": gid, "title": title, "category": category, "status": status, "target_amount": target, "end_date": end}


def cover(accounts, goals, params=None):
    return build_accounts_forecast(plan(accounts), {**FLAT, **(params or {})}, TODAY, goals=goals)


def item(out, gid="g1"):
    return next(g for g in out["goals"] if g["id"] == gid)


def test_engine_monthly_rows_are_opt_in_and_default_digests_are_unchanged():
    base = Scenario(years=30, initial=0.0, monthly_contribution=8000.0, inflation=0.02, start_date="2026-01-01", assets=(Asset(),))
    default = simulate(base)
    assert "monthly" not in default and "monthly_fixed_cost" not in default["inputs"] and "fixed_cost" not in default["annual"][0]
    assert default["replay_digest"] == "a993cee736cb0cc3342f105ae7266cd175ff13ba9a03b3546fb25ed5a33b53c4"       # same as before the fixed-cost feature
    m = simulate(base, monthly=True)
    assert len(m["monthly"]) == 360 and m["monthly"][11]["value_after_costs"] == m["annual"][0]["value_after_costs"]
    assert m["monthly"][0]["as_of"] == "2026-01-31" and m["final"] == default["final"]


def test_each_account_lands_in_exactly_one_state_and_release_dates_apply_at_the_month_not_the_year():
    out = cover([acct("recI", 1000, liquidity="immediate"),
                 acct("recS", 5000, liquidity="locked_until_date", liquid_from="2027-11-28"),
                 acct("recP", 20000, liquidity="age_based", liquid_from="2040-03-15", account_type="pension"),
                 acct("recU", 300, liquidity="unknown"),
                 acct("recN", 700, liquidity="age_based")],
                [goal("oct", target=1, end="2027-10-31"), goal("nov", target=1, end="2027-11-30"), goal("mid", target=1, end="2027-11-15")])
    oct_, nov, mid = item(out, "oct"), item(out, "nov"), item(out, "mid")
    assert (mid["value_as_of"], mid["locked_value"]) == ("2027-10-31", 5000 + 20000 + 700)        # released on 28/11 but the due date 15/11 precedes it: still locked
    assert (oct_["accessible_value"], oct_["conditional_value"], oct_["locked_value"]) == (1000.0, 300.0, 5000 + 20000 + 700)     # Oct 2027: study fund still locked
    assert (nov["accessible_value"], nov["conditional_value"], nov["locked_value"]) == (1000.0, 300.0 + 5000, 20000 + 700)        # Nov 2027: released month -> conditional, NOT accessible
    by = {a["id"]: a["liquidity"] for a in out["accounts"]}
    assert by["recS"] == {"basis": "dated", "liquid_from": "2027-11-28", "state_now": "locked", "state_at_horizon": "conditional"}
    assert by["recP"]["state_at_horizon"] == "locked" and by["recU"]["basis"] == "unverified" and by["recN"]["basis"] == "undated"


def test_accessible_plus_conditional_plus_locked_equals_the_consolidated_value_in_every_period():
    out = cover([acct("recI", 1234.56, liquidity="immediate"), acct("recS", 7777.77, liquidity="locked_until_date", liquid_from="2029-06-30"),
                 acct("recP", 98765.43, liquidity="age_based", liquid_from="2033-01-01", account_type="pension"), acct("recU", 55.55)],
                [], {"annual_return_pct": 6.5, "annual_fee_pct": 0.4, "inflation_pct": 2.1, "years": 15, "monthly_contributions": {"recI": 333.33, "recS": 111.11}})
    series = out["consolidated"]["series"]
    assert len(series) == 15
    for point in series:
        assert point["accessible"] + point["conditional"] + point["locked"] == pytest.approx(point["nominal"], abs=0.005)
        assert min(point["accessible"], point["conditional"], point["locked"]) >= 0
    assert series[0]["locked"] > 0 and series[-1]["locked"] == 0         # the study fund and the pension are released by year 15; nothing is dropped


def test_pension_and_unknown_are_never_accessible_even_when_marked_immediate_or_released():
    out = cover([acct("recP", 90000, liquidity="immediate", account_type="pension", liquid_from="2020-01-01"),
                 acct("recK", 40000, liquidity="locked_until_date", liquid_from="2020-01-01", account_type="study_fund"),
                 acct("recU", 500, liquidity="unknown")], [goal(target=1, end="2027-12-31")])
    g = item(out)
    assert g["verdict"] == "not_comparable" and g["reason"] == "no_verified_accessible_account"            # no false "short" and no false "covered"
    assert g["accessible_value"] is None
    assert out["accounts"][0]["liquidity"]["basis"] == "retirement_immediate" and out["accounts"][0]["liquidity"]["state_now"] == "conditional"
    assert all(p["accessible"] == 0 for p in out["consolidated"]["series"])


def test_a_date_alone_never_makes_money_accessible():
    out = cover([acct("recK", 40000, liquidity="locked_until_date", liquid_from="2026-01-01"), acct("recI", 10, liquidity="immediate")], [goal(target=39000)])
    g = item(out)
    assert g["verdict"] == "short" and g["accessible_value"] == 10.0 and g["conditional_value"] == 40000.0 and g["gap"] == 38990.0


def test_goal_verdicts_covered_short_and_the_gap():
    accounts = [acct("recI", 1000, liquidity="immediate")]
    assert item(cover(accounts, [goal(target=1000)]))["verdict"] == "covered"
    assert item(cover(accounts, [goal(target=999.99)]))["verdict"] == "covered"
    short = item(cover(accounts, [goal(target=1500.5)]))
    assert (short["verdict"], short["gap"], short["accessible_value"]) == ("short", 500.5, 1000.0)
    assert short["due_month"] == "2027-12" and short["target_amount"] == 1500.5


def test_goal_value_is_read_at_the_due_month_from_monthly_rows_not_the_previous_year_end():
    out = cover([acct("recI", 1000, liquidity="immediate")], [goal("mar", target=1, end="2027-03-31"), goal("dec", target=1, end="2026-12-31")],
                {"monthly_contributions": {"recI": 100}})
    assert item(out, "dec")["accessible_value"] == 1000 + 3 * 100          # Oct, Nov, Dec 2026 month-end deposits (start month = Oct 2026)
    assert item(out, "mar")["accessible_value"] == 1000 + 6 * 100          # Oct 2026 .. Mar 2027
    year_end = out["consolidated"]["series"][0]["accessible"]
    assert year_end == 1000 + 12 * 100 and item(out, "mar")["accessible_value"] != year_end


def test_goal_is_not_comparable_with_a_named_reason_and_never_a_guess():
    acc = [acct("recI", 1000, liquidity="immediate")]
    assert item(cover(acc, [goal(target=None)]))["reason"] == "missing_target"
    assert item(cover(acc, [goal(target=0)]))["reason"] == "missing_target"
    assert item(cover(acc, [goal(end=None)]))["reason"] == "missing_date"
    assert item(cover(acc, [goal(end="not a date")]))["reason"] == "missing_date"
    assert item(cover(acc, [goal(end="2026-09-30")]))["reason"] == "past_date"
    assert item(cover(acc, [goal(end="2036-10-31")]))["reason"] == "beyond_horizon"          # the horizon is 10 years from Oct 2026 (last month Sep 2036)
    assert item(cover(acc, [goal(end="2036-09-30")]))["verdict"] == "covered"
    for g in cover(acc, [goal(target=None)])["goals"]:
        assert g["verdict"] == "not_comparable" and g["gap"] is None and g["accessible_value"] is None


def test_only_the_approved_categories_and_active_goals_take_part():
    acc = [acct("recI", 1000, liquidity="immediate")]
    goals = [goal(f"g-{c}", c) for c in ("long_term", "emergency_fund", "investment", "savings")] + [
        goal("inc", "income"), goal("debt", "debt"), goal("proj", "project"), goal("old", "savings", status="done"), goal("odd", None), "junk", None]
    out = cover(acc, goals)
    assert [g["id"] for g in out["goals"]] == ["g-long_term", "g-emergency_fund", "g-investment", "g-savings"]
    assert out["goals_skipped"] == {"other_category": 4, "inactive": 1}


def test_emergency_fund_is_checked_against_immediate_accounts_only():
    out = cover([acct("recI", 800, liquidity="immediate"), acct("recK", 50000, liquidity="locked_until_date", liquid_from="2026-01-01"),
                 acct("recU", 9000)], [goal("em", "emergency_fund", target=1000)])
    em = item(out, "em")
    assert (em["verdict"], em["accessible_value"], em["gap"]) == ("short", 800.0, 200.0)
    only_conditional = cover([acct("recK", 50000, liquidity="locked_until_date", liquid_from="2026-01-01")], [goal("em", "emergency_fund", target=1000)])
    assert item(only_conditional, "em")["reason"] == "no_verified_accessible_account"


def test_the_same_money_may_cover_several_goals_and_nothing_is_allocated_or_recommended():
    out = cover([acct("recI", 1000, liquidity="immediate")], [goal("a", "savings", target=800), goal("b", "long_term", target=900), goal("c", "investment", target=1000)])
    assert [g["verdict"] for g in out["goals"]] == ["covered"] * 3 and {g["accessible_value"] for g in out["goals"]} == {1000.0}         # no allocation
    text = " ".join(out["warnings"])
    assert "אותו כסף" in text and "כיסוי פוטנציאלי" in text and "אין כאן המלצת השקעה או משיכה" in text
    assert out["consolidated"]["series"][0]["accessible"] == 1000.0                              # the pool itself is not reduced by goals


def test_no_money_is_counted_twice_across_states_or_by_the_deposit_fee():
    out = cover([acct("recI", 1000, liquidity="immediate"), acct("recS", 2000, liquidity="locked_until_date", liquid_from="2026-12-31")],
                [goal(target=1, end="2027-01-31")], {"monthly_contributions": {"recI": 100, "recS": 50}})
    g = item(out)
    total = g["accessible_value"] + g["conditional_value"] + g["locked_value"]
    assert total == pytest.approx(1000 + 4 * 100 + 2000 + 4 * 50)                                  # Oct..Jan: each deposit lands once, in its own account's state
    assert g["conditional_value"] == pytest.approx(2000 + 4 * 50)                                  # released in Dec 2026 -> conditional, not also accessible


def test_without_goals_or_liquidity_fields_the_forecast_is_backward_compatible():
    out = run({"years": 10})
    assert out["goals"] == [] and out["goals_skipped"] == {"other_category": 0, "inactive": 0}
    a = out["accounts"][0]
    assert a["liquidity"]["basis"] == "unverified" and "liquidity" in a["missing"] and a["final_nominal"] > 0
    assert all(p["accessible"] == 0 and p["locked"] == 0 and p["conditional"] == p["nominal"] for p in out["consolidated"]["series"])
    assert {"final_nominal", "final_real", "invested", "costs_paid", "series", "monthly_contribution"} <= set(a)


def test_liquidity_gaps_are_reported_as_missing_inputs():
    out = cover([acct("recA", 10, liquidity="locked_until_date"), acct("recB", 10, liquidity="age_based", liquid_from="2040-01-01"), acct("recC", 10)], [])
    miss = {a["id"]: a["missing"] for a in out["accounts"]}
    assert "liquid_from" in miss["recA"] and "liquid_from" not in miss["recB"] and "liquidity" in miss["recC"]


def test_input_view_and_goals_are_not_mutated():
    accounts, goals = [acct("recI", 1000, liquidity="immediate")], [goal()]
    before = copy.deepcopy((accounts, goals))
    cover(accounts, goals)
    assert (accounts, goals) == before


def test_money_deposited_after_the_due_date_never_makes_a_goal_covered():
    acc = [acct("recI", 1000, liquidity="immediate")]
    deposits = {"monthly_contributions": {"recI": 500}}          # lands on the last day of each month
    mid = item(cover(acc, [goal(target=1400, end="2026-10-20")], deposits))           # due mid-month, the 500 arrives on Oct 31
    assert (mid["verdict"], mid["gap"]) == ("short", 400.0)
    assert mid["accessible_value"] == 1000.0 and mid["value_as_of"] == "2026-10-15"       # the opening balance, as of the forecast day - nothing later
    end = item(cover(acc, [goal(target=1400, end="2026-10-31")], deposits))           # due on the last day: that month's deposit is on or before the date
    assert (end["verdict"], end["accessible_value"], end["value_as_of"]) == ("covered", 1500.0, "2026-10-31")
    nxt = item(cover(acc, [goal(target=1900, end="2026-11-29")], deposits))           # due 29/11: only the Oct 31 deposit counts, not Nov 30
    assert (nxt["verdict"], nxt["accessible_value"], nxt["value_as_of"]) == ("short", 1500.0, "2026-10-31")
    assert item(cover(acc, [goal(target=1900, end="2026-11-30")], deposits))["verdict"] == "covered"


def test_growth_after_the_due_date_inside_the_month_is_not_counted_either():
    acc = [acct("recI", 1000, liquidity="immediate")]
    out = cover(acc, [goal("a", target=1, end="2026-12-15"), goal("b", target=1, end="2026-12-31")], {"annual_return_pct": 12})
    a, b = item(out, "a"), item(out, "b")
    assert a["value_as_of"] == "2026-11-30" and b["value_as_of"] == "2026-12-31" and a["accessible_value"] < b["accessible_value"]
