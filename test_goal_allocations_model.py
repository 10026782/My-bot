"""B2 step 3 — read model of ``Goal Allocations`` + integration into the A2 forecast. Pure (no network, no Airtable, no writes).

An allocation is a label on money that already sits in an account: it never changes a balance, never creates a deposit/withdrawal and
is not liquidity. Over-allocation is shown, never clipped; the same shekel is never counted for two goals.
"""

from __future__ import annotations

import copy
from datetime import date

import pytest

from portfolio_lab.accounts_forecast import build_accounts_forecast
from test_accounts_forecast import FLAT, TODAY, acct, goal, plan


def al(aid, goal_id, account_id, mode="percent", value=10, status="active", eff=None):
    return {"id": aid, "goal_id": goal_id, "account_id": account_id, "mode": mode, "status": status, "effective_from": eff,
            "percent": value if mode == "percent" else None, "amount": value if mode == "fixed_amount" else None}


def run(accounts, goals, allocations, params=None):
    return build_accounts_forecast(plan(accounts), {**FLAT, **(params or {})}, TODAY, goals=goals, allocations=allocations)


def cash(aid="recI", value=1000, **extra):
    return acct(aid, value, liquidity="immediate", account_type="liquid", **extra)


def g(out, gid):
    return next(x for x in out["goals"] if x["id"] == gid)


def ao(out, gid):
    return next(x for x in out["allocations"]["goals"] if x["id"] == gid)


def acc(out, aid):
    return next(x for x in out["allocations"]["accounts"] if x["id"] == aid)


# ═══ backward compatibility: an empty table changes nothing ═══

def test_empty_or_missing_allocations_leave_a2_unchanged_and_show_zero():
    accounts, goals = [cash(), acct("recK", 500, liquidity="unknown")], [goal("a", target=900), goal("b", "long_term", target=5000)]
    base = build_accounts_forecast(plan(accounts), FLAT, TODAY, goals=goals)
    for allocations in (None, []):
        out = run(accounts, goals, allocations)
        assert out["allocations"]["has_allocations"] is False and out["allocations"]["count"] == 0
        assert out["allocations"]["totals"] == {"accounts_value": 1500.0, "allocated": 0.0, "unallocated": 1500.0, "over_allocated": 0.0}
        assert out["allocations"]["goals"] == [] and out["allocations"]["over_allocated_accounts"] == 0
        for key in ("accounts", "consolidated", "goals", "goals_skipped", "data_gaps"):
            assert out[key] == base[key], key
    assert [x["basis"] for x in base["goals"]] == ["potential", "potential"] and all(x["allocated_value"] is None for x in base["goals"])


# ═══ calculations ═══

def test_percent_and_fixed_totals_per_goal_per_account_and_unallocated():
    out = run([cash(value=1000)], [goal("a", target=250), goal("b", target=150)], [al("1", "a", "recI", "percent", 30), al("2", "b", "recI", "fixed_amount", 200)])
    a = acc(out, "recI")
    assert (a["value"], a["allocated"], a["unallocated"], a["over_allocated"], a["over_by"]) == (1000.0, 500.0, 500.0, False, 0.0)
    assert a["allocated_pct"] == 50.0 and [x["resolved_amount"] for x in a["allocations"]] == [300.0, 200.0]
    assert (ao(out, "a")["allocated"], ao(out, "b")["allocated"]) == (300.0, 200.0)
    assert out["allocations"]["totals"] == {"accounts_value": 1000.0, "allocated": 500.0, "unallocated": 500.0, "over_allocated": 0.0}
    assert out["allocations"]["totals"]["allocated"] + out["allocations"]["totals"]["unallocated"] == out["allocations"]["totals"]["accounts_value"]


def test_the_same_money_is_never_counted_for_two_goals_and_the_sum_identity_holds():
    accounts = [cash("recI", 1000), cash("recJ", 600)]
    allocations = [al("1", "a", "recI", "percent", 40), al("2", "b", "recI", "percent", 60), al("3", "a", "recJ", "fixed_amount", 100)]
    out = run(accounts, [goal("a", target=1), goal("b", target=1)], allocations)
    t = out["allocations"]["totals"]
    assert sum(x["allocated"] for x in out["allocations"]["goals"]) == pytest.approx(t["allocated"]) == pytest.approx(1100.0)
    assert t["allocated"] + t["unallocated"] == pytest.approx(t["accounts_value"]) == pytest.approx(1600.0)
    assert (acc(out, "recI")["unallocated"], acc(out, "recJ")["unallocated"]) == (0.0, 500.0)


def test_over_allocation_is_shown_explicitly_and_not_clipped_to_zero():
    for bad in ([al("1", "a", "recI", "percent", 70), al("2", "b", "recI", "percent", 50)],
                [al("1", "a", "recI", "fixed_amount", 700), al("2", "b", "recI", "fixed_amount", 500)]):
        out = run([cash(value=1000)], [goal("a", target=300), goal("b", target=300)], bad)
        a = acc(out, "recI")
        assert a["over_allocated"] is True and a["over_by"] == 200.0 and a["allocated"] == 1200.0 and a["unallocated"] == 0.0
        assert all(x["counted"] is False for x in a["allocations"])
        assert out["allocations"]["totals"]["over_allocated"] == 200.0 and out["allocations"]["over_allocated_accounts"] == 1
        assert out["allocations"]["totals"]["allocated"] == 0.0 and out["allocations"]["totals"]["accounts_value"] == 0.0     # not folded into the healthy sums
        assert (ao(out, "a")["status"], ao(out, "a")["blocked_by_over_allocation"]) == ("blocked_over_allocation", 700.0)
        assert [(x["verdict"], x["reason"]) for x in out["goals"]] == [("not_comparable", "over_allocated")] * 2            # no covered/short guess


def test_percent_over_100_is_over_allocation_even_when_the_value_is_zero_like():
    out = run([cash(value=1000)], [goal("a", target=1)], [al("1", "a", "recI", "percent", 100), al("2", "a", "recI", "percent", 0.5)])
    assert acc(out, "recI")["over_allocated"] is True


def test_goal_with_one_healthy_and_one_over_allocated_source_is_partial_not_covered():
    accounts = [cash("recI", 1000), cash("recJ", 1000)]
    out = run(accounts, [goal("a", target=100)], [al("1", "a", "recI", "percent", 50), al("2", "a", "recJ", "fixed_amount", 1500)])
    assert (ao(out, "a")["allocated"], ao(out, "a")["blocked_by_over_allocation"], ao(out, "a")["status"]) == (500.0, 1500.0, "partial_over_allocation")
    assert g(out, "a")["verdict"] == "not_comparable" and g(out, "a")["reason"] == "over_allocated"


def test_duplicate_goal_account_pair_is_summed_and_flagged():
    out = run([cash()], [goal("a", target=1)], [al("1", "a", "recI", "percent", 10), al("2", "a", "recI", "percent", 15)])
    assert ao(out, "a")["allocated"] == 250.0 and out["allocations"]["duplicate_goal_account_pairs"] == 1


# ═══ allocated != accessible (liquidity stays A2's) ═══

def test_allocation_to_a_pension_is_allocated_but_not_accessible_and_not_a_shortfall():
    pension = acct("recP", 90000, liquidity="immediate", account_type="pension", liquid_from="2020-01-01")
    out = run([pension], [goal("a", "long_term", target=50000)], [al("1", "a", "recP", "percent", 100)])
    x = ao(out, "a")
    assert (x["allocated"], x["accessible"], x["conditional"], x["locked"]) == (90000.0, 0.0, 90000.0, 0.0)
    c = g(out, "a")
    assert (c["verdict"], c["reason"], c["basis"]) == ("not_comparable", "allocated_not_accessible", "allocation")
    assert (c["allocated_value"], c["accessible_value"], c["conditional_value"]) == (90000.0, 0.0, 90000.0) and c["gap"] is None


def test_locked_and_unverified_allocations_are_split_by_state_and_only_accessible_counts_for_coverage():
    accounts = [cash("recI", 1000), acct("recL", 4000, liquidity="locked_until_date", liquid_from="2030-01-01"), acct("recU", 2000, liquidity="unknown")]
    out = run(accounts, [goal("a", target=800)], [al("1", "a", "recI", "fixed_amount", 500), al("2", "a", "recL", "percent", 50), al("3", "a", "recU", "percent", 50)])
    x = ao(out, "a")
    assert (x["accessible"], x["locked"], x["conditional"], x["allocated"]) == (500.0, 2000.0, 1000.0, 3500.0)
    c = g(out, "a")
    assert (c["verdict"], c["gap"], c["accessible_value"], c["allocated_value"]) == ("short", 300.0, 500.0, 3500.0)
    assert x["sources"][0]["liquidity_state"] == "accessible"


def test_allocating_does_not_change_balances_liquidity_or_the_consolidated_forecast():
    accounts = [cash("recI", 1000), acct("recP", 9000, liquidity="immediate", account_type="pension")]
    base = build_accounts_forecast(plan(accounts), FLAT, TODAY, goals=[goal("a", target=1)])
    out = run(accounts, [goal("a", target=1)], [al("1", "a", "recI", "percent", 100), al("2", "a", "recP", "percent", 100)])
    for key in ("accounts", "consolidated", "excluded", "data_gaps"):
        assert out[key] == base[key], key


def test_potential_goal_stays_a2_and_reports_how_much_accessible_money_is_allocated_elsewhere():
    out = run([cash(value=1000)], [goal("a", target=400), goal("p", target=900)], [al("1", "a", "recI", "percent", 40)])
    assert (g(out, "a")["basis"], g(out, "a")["verdict"], g(out, "a")["allocated_value"]) == ("allocation", "covered", 400.0)
    p = g(out, "p")
    assert (p["basis"], p["verdict"], p["accessible_value"], p["allocated_elsewhere_accessible"]) == ("potential", "covered", 1000.0, 400.0)
    assert "אינה הופכת חשבון לנזיל" in " ".join(out["warnings"])


# ═══ forecast over time ═══

def test_percent_grows_with_the_account_and_fixed_stays_nominal():
    accounts = [cash("recI", 1000, expected_return_pct=10)]
    out = run(accounts, [goal("a", target=1, end="2027-12-31"), goal("b", target=1, end="2027-12-31")],
              [al("1", "a", "recI", "percent", 50), al("2", "b", "recI", "fixed_amount", 300)], {"annual_return_pct": 10})
    full = build_accounts_forecast(plan(accounts), {**FLAT, "annual_return_pct": 10}, TODAY, goals=[goal("p", target=1, end="2027-12-31")])
    pool = full["goals"][0]["accessible_value"]
    assert pool > 1000
    assert g(out, "a")["allocated_value"] == pytest.approx(pool * 0.5, abs=0.02)
    assert g(out, "b")["allocated_value"] == 300.0


def test_future_cap_scales_fixed_allocations_and_says_so_when_the_account_shrinks():
    accounts = [cash("recI", 1000, insurance_cost_monthly=50)]
    out = run(accounts, [goal("a", target=1, end="2027-12-31"), goal("b", target=1, end="2027-12-31")],
              [al("1", "a", "recI", "fixed_amount", 500), al("2", "b", "recI", "fixed_amount", 500)])
    assert acc(out, "recI")["over_allocated"] is False                                  # exactly the snapshot: not over-allocated today
    a, b = g(out, "a"), g(out, "b")
    assert a["allocation_capped"] is True and b["allocation_capped"] is True and a["allocated_value"] < 500.0
    assert a["allocated_value"] + b["allocated_value"] == pytest.approx(a["accessible_value"] + b["accessible_value"])
    assert a["allocated_value"] + b["allocated_value"] <= 1000.0


def test_effective_from_in_the_future_is_not_counted_today_but_counts_from_that_month():
    accounts = [cash(value=1000)]
    out = run(accounts, [goal("early", target=1, end="2027-01-31"), goal("late", target=1, end="2027-12-31")],
              [al("1", "early", "recI", "percent", 20, eff="2027-06-01"), al("2", "late", "recI", "percent", 20, eff="2027-06-01")])
    assert out["allocations"]["skipped"]["not_yet_effective"] == 2 and out["allocations"]["totals"]["allocated"] == 0.0
    assert (g(out, "early")["verdict"], g(out, "early")["reason"]) == ("not_comparable", "allocation_not_yet_effective")
    assert (g(out, "late")["verdict"], g(out, "late")["allocated_value"]) == ("covered", 200.0)


# ═══ ownership / leakage / invalid rows ═══

def test_links_to_someone_elses_goal_or_account_never_contribute_or_leak_a_name():
    out = run([cash(value=1000)], [goal("mine", target=1, title="שלי")],
              [al("1", "mine", "recDANA_ACC", "fixed_amount", 999999), al("2", "danaGoal", "recI", "fixed_amount", 888888), al("3", "mine", "recI", "percent", 10)])
    assert out["allocations"]["skipped"]["unknown_link"] == 2 and out["allocations"]["count"] == 1
    assert out["allocations"]["totals"]["allocated"] == 100.0
    text = str(out)
    assert "999999" not in text and "888888" not in text and "danaGoal" not in text and "recDANA_ACC" not in text


def test_inactive_missing_status_bad_links_values_closed_and_snapshotless_accounts_are_skipped_with_a_reason():
    accounts = [cash("recI", 1000), acct("recX", 50, status="closed", liquidity="immediate"), acct("recN", None, liquidity="immediate")]
    rows = [al("ok", "a", "recI", "percent", 10), al("e", "a", "recI", "percent", 10, status="ended"), al("m", "a", "recI", "percent", 10, status=None),
            {"id": "nl", "goal_id": None, "account_id": "recI", "mode": "percent", "percent": 5, "status": "active"},
            {"id": "ml", "goal_id": "a", "account_id": ["recI"], "mode": "percent", "percent": 5, "status": "active"},
            al("p0", "a", "recI", "percent", 0), al("p101", "a", "recI", "percent", 101), al("f0", "a", "recI", "fixed_amount", -5),
            {**al("md", "a", "recI"), "mode": "bogus"}, al("d", "a", "recI", "percent", 5, eff="not-a-date"),
            al("cl", "a", "recX", "percent", 10), al("ns", "a", "recN", "percent", 10), "junk", None]
    out = run(accounts, [goal("a", target=1)], rows)
    s = out["allocations"]["skipped"]
    assert out["allocations"]["count"] == 1 and out["allocations"]["totals"]["allocated"] == 100.0
    assert (s["inactive"], s["status_missing"], s["invalid_link"], s["invalid_value"], s["account_closed"], s["no_snapshot"]) == (1, 1, 2, 5, 1, 1)


def test_allocation_to_a_goal_outside_the_coverage_categories_is_shown_but_has_no_verdict():
    out = run([cash()], [goal("inc", "income", target=1)], [al("1", "inc", "recI", "percent", 10)])
    assert ao(out, "inc")["allocated"] == 100.0 and out["goals"] == [] and out["goals_skipped"]["other_category"] == 1


def test_inputs_are_not_mutated():
    accounts, goals, rows = [cash()], [goal("a", target=1)], [al("1", "a", "recI", "percent", 10)]
    snapshot = copy.deepcopy((accounts, goals, rows))
    run(accounts, goals, rows)
    assert (accounts, goals, rows) == snapshot
