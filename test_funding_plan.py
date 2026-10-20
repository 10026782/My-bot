"""Goal Funding Planner, step 1 — pure engine (no network, no Airtable, no writes). See docs/portfolio_lab/GOAL_FUNDING_PLANNER_SPEC.md.

A goal becomes a neutral comparison of funding options. Expected money is never presented as money that already exists, nothing is
recommended, scored or ranked, and the same shekel is never counted for two goals.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from core.financial_control import loans as fcc_loans
from portfolio_lab import funding_plan as fp
from test_accounts_forecast import FLAT, TODAY, acct, plan
from test_goal_allocations_model import al, cash

G, G2, ASSET, LOAN, OWED = "recG1", "recG2", "recAS1", "recLN1", "recOW1"
FLAT_ASSUMPTIONS = {k: v for k, v in FLAT.items() if k != "years"}


def goal_rec(gid=G, target=120000, end="2030-12-31", category="savings", title="חתונה"):
    return {"id": gid, "title": title, "category": category, "status": "active", "target_amount": target, "end_date": end}


def inputs(accounts=None, goals=None, allocations=None, **extra):
    base = {"goals": goals if goals is not None else [goal_rec()], "accounts_view": plan(accounts or []), "allocations": allocations or [],
            "goal_rows": [], "loans": [], "assets": [], "obligations": None, "income": None, "savings_plan": {}}
    base.update(extra)
    return base


def request(*options, goal_ids=(G,), allocation_plan=(), assumptions=None):
    return fp.normalize_request({"goal_ids": list(goal_ids), "options": list(options), "allocation_plan": list(allocation_plan),
                                 "assumptions": FLAT_ASSUMPTIONS if assumptions is None else assumptions})


def run(inp, req):
    return fp.build_funding_plan(inp, req, TODAY)


def opts(out, index=0):
    return {o["id"]: o for o in out["goals"][index]["options"]}


def deposit_option(**hypo):
    return {"id": "dep", "type": "new_deposits", "hypothetical": {"immediate": True, **hypo}}


def asset(**extra):
    return {"id": ASSET, "name": "דירה", "asset_type": "Residential", "current_value": 2000000, "ownership_pct": 100, "mortgage_balance": None,
            "monthly_income": None, "linked_debt": None, "linked_loans": [], **extra}


def receivable(arrangement=None, balance=100000, direction="owed_to_me", active=True):
    return {"id": OWED, "name": "חוב", "direction": direction, "active": active, "arrangement": arrangement, "early_closure_balance": balance}


# ═══ request validation ═══

@pytest.mark.parametrize("body", [
    [], {"goal_ids": []}, {"goal_ids": ["x"]}, {"goal_ids": [G, G]}, {"goal_ids": [G], "extra": 1},
    {"goal_ids": [G], "options": [{"type": "existing_balance"}]},
    {"goal_ids": [G], "options": [{"type": "nope"}]},
    {"goal_ids": [G], "options": [{"type": "custom", "label": "x", "amount": 5, "bad": 1}]},
    {"goal_ids": [G], "options": [{"id": "a", "type": "custom", "label": "x", "amount": 5}, {"id": "a", "type": "custom", "label": "y", "amount": 5}]},
    {"goal_ids": [G], "options": [{"type": "new_deposits"}]},
    {"goal_ids": [G], "options": [{"type": "new_deposits", "account_id": "recA", "hypothetical": {"immediate": True}}]},
    {"goal_ids": [G], "options": [{"type": "new_deposits", "hypothetical": {"immediate": True, "liquid_from": "2030-01-01"}}]},
    {"goal_ids": [G], "options": [{"type": "new_deposits", "hypothetical": {"immediate": True, "tax": 1}}]},
    {"goal_ids": [G], "options": [{"type": "custom", "label": "x", "amount": 5, "certainty": "confirmed"}]},
    {"goal_ids": [G], "allocation_plan": [{"goal_id": G, "option_id": "missing", "amount": 5}]},
    {"goal_ids": [G], "assumptions": {"tax_pct": 1}},
])
def test_invalid_requests_are_rejected(body):
    with pytest.raises(ValueError):
        fp.normalize_request(body)


@pytest.mark.parametrize("amount", [0, -5, float("nan"), float("inf"), True, "100", None, 1e12])
def test_money_must_be_a_positive_finite_number(amount):
    with pytest.raises(ValueError):
        fp.normalize_request({"goal_ids": [G], "options": [{"type": "custom", "label": "x", "amount": amount}]})


def test_error_messages_never_echo_values():
    with pytest.raises(ValueError) as e:
        fp.normalize_request({"goal_ids": [G], "options": [{"type": "custom", "label": "x", "amount": -987654}]})
    assert "987654" not in str(e.value)


# ═══ the need ═══

@pytest.mark.parametrize("goal,reason", [
    (goal_rec(target=None), "missing_target"), (goal_rec(end=None), "missing_date"), (goal_rec(end="2025-01-01"), "past_date"),
    (goal_rec(end="2026-10-20"), "due_this_month"), (goal_rec(end="2140-01-01"), "beyond_horizon"),
])
def test_goals_that_cannot_be_planned_say_why_and_get_no_options(goal, reason):
    need = run(inputs(goals=[goal]), request({"type": "custom", "label": "x", "amount": 5}))["goals"][0]
    assert need["need"]["reason"] == reason and need["options"] == [] and need["need"]["gap"] is None


def test_a_parent_goal_is_flagged_not_planned():
    rows = [{"goal_id": G2, "parent_id": G, "method": "cumulative", "net": 0}]
    out = run(inputs(goals=[goal_rec(), goal_rec(G2)], goal_rows=rows), request(goal_ids=(G, G2)))
    assert out["goals"][0]["need"]["reason"] == "parent_goal_rollup_not_supported" and out["goals"][0]["options"] == []
    assert out["goals"][1]["need"]["reason"] is None


def test_unknown_goal_is_rejected():
    with pytest.raises(ValueError):
        run(inputs(), request(goal_ids=("recZZ",)))


# ═══ existing money: allocation basis, no double counting ═══

def test_no_allocation_means_unknown_and_nothing_is_counted():
    out = run(inputs([cash(value=500000)]), request())
    ex = opts(out)["existing_balance"]
    assert ex["feasible"] == "unknown" and ex["reason"] == "no_allocation" and ex["covers_amount"] is None
    assert out["goals"][0]["need"]["confirmed_existing"] == 0.0 and out["goals"][0]["need"]["gap"] == 120000.0
    assert ex["details"]["potential_accessible_value"] == 500000          # information only, never counted as coverage


def test_an_allocation_to_an_accessible_account_is_confirmed_and_shrinks_the_gap():
    out = run(inputs([cash(value=50000)], allocations=[al("a1", G, "recI", "fixed_amount", 30000)]), request())
    ex, need = opts(out)["existing_balance"], out["goals"][0]["need"]
    assert ex["feasible"] is True and ex["certainty"] == "confirmed" and ex["covers_amount"] == 30000
    assert need["confirmed_existing"] == 30000 and need["gap"] == 90000 and need["sizing_basis"] == "target_minus_confirmed"


def test_an_allocation_to_a_pension_is_not_money_for_this_goal():
    pension = acct("recP", 400000, account_type="pension", liquidity="age_based")
    out = run(inputs([pension], allocations=[al("a1", G, "recP", "percent", 100)]), request())
    ex = opts(out)["existing_balance"]
    assert ex["feasible"] is False and ex["covers_amount"] == 0.0 and out["goals"][0]["need"]["gap"] == 120000.0


def test_over_allocation_is_not_counted_and_is_shown():
    out = run(inputs([cash(value=1000)], allocations=[al("a1", G, "recI", "fixed_amount", 900), al("a2", G2, "recI", "fixed_amount", 900)],
                     goals=[goal_rec(), goal_rec(G2)]), request())
    ex = opts(out)["existing_balance"]
    assert ex["feasible"] is False and ex["reason"] == "over_allocated" and "over_committed_pool" in ex["risks"] and ex["covers_amount"] == 0.0


def test_progress_events_are_the_basis_only_without_an_allocation_and_never_added_to_one():
    rows = [{"goal_id": G, "method": "cumulative", "net": 20000}]
    only_events = run(inputs(goal_rows=rows), request())
    ex = opts(only_events)["existing_balance"]
    assert ex["covers_amount"] == 20000 and ex["details"]["basis"] == "progress_events" and "self_reported_balance" in ex["risks"]
    assert only_events["goals"][0]["need"]["gap"] == 100000.0
    both = run(inputs([cash(value=50000)], allocations=[al("a1", G, "recI", "fixed_amount", 30000)], goal_rows=rows), request())
    ex = opts(both)["existing_balance"]
    assert ex["covers_amount"] == 30000 and "event_allocation_overlap" in ex["risks"] and ex["details"]["progress_events_actual"] == 20000
    assert both["goals"][0]["need"]["gap"] == 90000.0                       # 120000 - 30000, the events are not added on top


def test_a_covered_goal_gets_no_funding_options():
    out = run(inputs([cash(value=500000)], allocations=[al("a1", G, "recI", "fixed_amount", 130000)]), request({"type": "custom", "label": "x", "amount": 5}))
    assert out["goals"][0]["need"]["reason"] == "already_covered" and len(out["goals"][0]["options"]) == 1


# ═══ new deposits: the required monthly amount comes from the engine ═══

def test_required_monthly_at_zero_return_is_the_gap_over_the_months():
    out = run(inputs(), request(deposit_option()))
    d = opts(out)["dep"]
    assert d["feasible"] is True and d["details"]["deposit_months"] == 51
    assert d["details"]["required_monthly"] == pytest.approx(120000 / 51, abs=0.01)
    assert d["monthly_cash_effect"] == pytest.approx(-120000 / 51, abs=0.01) and d["certainty"] == "expected"
    assert d["covers_amount"] == 120000 and d["total_cost"] == 0.0 and d["available_by"] == "2030-12-31"


def test_a_positive_return_needs_less_and_fees_cost_money():
    flat = opts(run(inputs(), request(deposit_option())))["dep"]["details"]["required_monthly"]
    grown = opts(run(inputs(), request(deposit_option(expected_return_pct=5))))["dep"]
    assert grown["details"]["required_monthly"] < flat and "depends_on_assumed_return" in grown["risks"]
    fees = opts(run(inputs(), request(deposit_option(expected_return_pct=5, fee_pct=1, deposit_fee_pct=2))))["dep"]
    assert fees["total_cost"] > 0 and fees["details"]["required_monthly"] > grown["details"]["required_monthly"]


def test_the_search_is_deterministic():
    a = run(inputs(), request(deposit_option(expected_return_pct=4, fee_pct=0.3)))
    b = run(inputs(), request(deposit_option(expected_return_pct=4, fee_pct=0.3)))
    assert a == b


def test_the_required_deposit_actually_reaches_the_gap():
    out = run(inputs(), request(deposit_option(expected_return_pct=4, fee_pct=0.3)))
    d = opts(out)["dep"]["details"]
    p = fp.af.normalize_params({"years": 10, **FLAT_ASSUMPTIONS})
    reached = fp._value_at(51, d["required_monthly"], years=10, annual_return=0.04, fee=0.003, deposit_fee_pct=0.0, p=p, start="2026-10-01")
    assert reached >= 120000 - 0.01 and fp._value_at(51, d["required_monthly"] - 1, years=10, annual_return=0.04, fee=0.003, deposit_fee_pct=0.0, p=p, start="2026-10-01") < 120000


def test_unreachable_under_the_assumptions_is_reported_not_guessed(monkeypatch):
    monkeypatch.setattr(fp, "_value_at", lambda *a, **k: 0.0)
    d = opts(run(inputs(), request(deposit_option())))["dep"]
    assert d["feasible"] is False and d["reason"] == "unreachable_under_assumptions" and d["monthly_cash_effect"] is None


@pytest.mark.parametrize("account,extra,feasible,reason", [
    (acct("recP", 1, account_type="pension", liquidity="immediate"), {}, False, "not_accessible_by_due"),
    (acct("recP", 1, account_type="pension", liquidity="immediate"), {"release_confirmed": True}, False, "not_accessible_by_due"),
    (acct("recL", 1, liquidity="locked_until_date", liquid_from="2032-01-01"), {}, False, "not_accessible_by_due"),
    (acct("recL", 1, liquidity="locked_until_date", liquid_from="2030-06-01"), {}, "unknown", "release_not_verified"),
    (acct("recL", 1, liquidity="locked_until_date", liquid_from="2030-06-01"), {"release_confirmed": True}, True, None),
    (acct("recL", 1, liquidity="locked_until_date"), {}, False, "not_accessible_by_due"),
    (acct("recL", 1, liquidity="unknown"), {}, "unknown", "liquidity_unverified"),
    (cash("recL", 1), {}, True, None),
])
def test_a_deposit_account_must_be_accessible_by_the_due_date(account, extra, feasible, reason):
    d = opts(run(inputs([account]), request({"id": "dep", "type": "new_deposits", "account_id": account["id"], **extra})))["dep"]
    assert d["feasible"] == feasible and d["feasible"] is feasible and d["reason"] == reason
    if feasible == "unknown":
        assert d["certainty"] == "uncertain" and "release_not_verified" in d["risks"]
    if feasible is True:
        assert d["certainty"] == "expected"


def test_a_hypothetical_account_needs_liquidity_and_a_release_date_is_not_an_entitlement():
    d = opts(run(inputs(), request({"id": "dep", "type": "new_deposits", "hypothetical": {"expected_return_pct": 4}})))["dep"]
    assert d["feasible"] == "unknown" and d["missing_inputs"] == ["liquidity"] and d["certainty"] == "unknown"
    late = opts(run(inputs(), request({"id": "dep", "type": "new_deposits", "hypothetical": {"liquid_from": "2031-01-01"}})))["dep"]
    assert late["feasible"] is False and late["reason"] == "not_accessible_by_due"
    early = opts(run(inputs(), request({"id": "dep", "type": "new_deposits", "hypothetical": {"liquid_from": "2030-01-01"}})))["dep"]
    assert early["feasible"] == "unknown" and early["reason"] == "release_not_verified" and "release_rules_confirmed" in early["conditions"]
    confirmed = opts(run(inputs(), request({"id": "dep", "type": "new_deposits", "release_confirmed": True, "hypothetical": {"liquid_from": "2030-01-01"}})))["dep"]
    assert confirmed["feasible"] is True and confirmed["certainty"] == "expected"


def test_an_unknown_account_id_is_rejected():
    with pytest.raises(ValueError):
        run(inputs(), request({"type": "new_deposits", "account_id": "recNOPE"}))


# ═══ loan ═══

def loan_option(**over):
    return {"id": "loan", "type": "loan", "amount": 100000, "annual_rate_pct": 6, "term_months": 60, "available_by": "2029-01-01", **over}


def test_a_loan_shows_payment_cost_and_the_new_liability_and_is_not_certain_until_approved():
    out = run(inputs(), request(loan_option()))
    ln = opts(out)["loan"]
    pay = round(fcc_loans.pmt(100000, 6, 60), 2)
    assert ln["new_liabilities"] == {"amount": 100000.0, "monthly_payment": pay, "term_months": 60}
    assert ln["monthly_cash_effect"] == -pay and ln["total_cost"] == round(fcc_loans.pmt(100000, 6, 60) * 60 - 100000, 2)
    assert ln["feasible"] is True and ln["certainty"] == "uncertain" and ln["conditions"] == ["loan_approved"]
    assert "terms_unverified" in ln["risks"] and "timing_uncertain" in ln["risks"]
    approved = opts(run(inputs(), request(loan_option(approved=True, terms_verified=True, collateral="קרן"))))["loan"]
    assert approved["certainty"] == "expected" and "terms_unverified" not in approved["risks"] and "collateral_growth_not_modeled" in approved["risks"]


def test_a_zero_rate_loan_costs_nothing_and_a_late_loan_is_not_feasible():
    assert opts(run(inputs(), request(loan_option(annual_rate_pct=0))))["loan"]["total_cost"] == 0.0
    late = opts(run(inputs(), request(loan_option(available_by="2031-01-01"))))["loan"]
    assert late["feasible"] is False and late["reason"] == "available_after_due"


def test_a_loan_does_not_touch_the_accumulation_forecast_inputs():
    inp = inputs([cash(value=5000)])
    before = copy.deepcopy(inp)
    run(inp, request(loan_option()))
    assert inp == before


# ═══ asset sale ═══

def sale(**over):
    return {"id": "sale", "type": "asset_sale", "asset_id": ASSET, "net_proceeds": 300000, "expected_date": "2030-03-01", **over}


def test_a_sale_uses_the_entered_net_proceeds_and_flags_debt_overlap_and_lost_income():
    out = run(inputs(assets=[asset(mortgage_balance=500000, monthly_income=4000, linked_loans=[{"id": LOAN}])]), request(sale()))
    s = opts(out)["sale"]
    assert s["covers_amount"] == 300000 and s["certainty"] == "uncertain" and "buyer_found" in s["conditions"]
    assert {"debt_overlap_unresolved", "lost_income", "timing_uncertain"} <= set(s["risks"]) and s["monthly_cash_effect"] == -4000.0
    assert s["details"]["asset"]["mortgage_balance"] == 500000
    assert opts(run(inputs(assets=[asset()]), request(sale(confirmed_buyer=True))))["sale"]["certainty"] == "expected"


def test_a_sale_after_the_due_date_is_not_feasible_and_an_unknown_asset_is_rejected():
    late = opts(run(inputs(assets=[asset()]), request(sale(expected_date="2031-01-01"))))["sale"]
    assert late["feasible"] is False and late["reason"] == "available_after_due"
    with pytest.raises(ValueError):
        run(inputs(assets=[]), request(sale()))


# ═══ receivable, obligations, custom, work income ═══

def collect(**over):
    return {"id": "owed", "type": "receivable_collection", "loan_id": OWED, "expected_net": 100000, "expected_date": "2029-01-01", **over}


def test_a_debt_owed_to_me_is_not_money_I_have_today():
    out = run(inputs(loans=[receivable(arrangement=None)]), request(collect()), )
    r = opts(out)["owed"]
    assert r["certainty"] == "uncertain" and r["feasible"] == "unknown" and r["reason"] == "no_arrangement"
    assert {"receivable_no_arrangement", "timing_uncertain"} <= set(r["risks"]) and out["goals"][0]["need"]["confirmed_existing"] == 0.0
    arranged = opts(run(inputs(loans=[receivable(arrangement="monthly")]), request(collect())))["owed"]
    assert arranged["certainty"] == "expected" and arranged["feasible"] is True


@pytest.mark.parametrize("loan", [receivable(direction="owed_by_me"), receivable(active=False)])
def test_only_an_active_debt_owed_to_me_can_be_collected(loan):
    with pytest.raises(ValueError):
        run(inputs(loans=[loan]), request(collect()))


def test_flagged_obligations_are_a_potential_monthly_saving_not_money():
    out = run(inputs(obligations={"potential_saving": 3000}), request({"id": "cut", "type": "obligations_reduction"}))
    o = opts(out)["cut"]
    assert o["covers_amount"] == 3000 * 51 and o["monthly_cash_effect"] == 3000 and o["certainty"] == "uncertain" and o["feasible"] == "unknown"
    none = opts(run(inputs(obligations={"potential_saving": 0}), request({"id": "cut", "type": "obligations_reduction"})))["cut"]
    assert none["feasible"] is False and none["reason"] == "no_flagged_obligations"


def test_custom_option_defaults_and_missing_date():
    ok = opts(run(inputs(), request({"id": "c", "type": "custom", "label": "מענק", "amount": 40000, "available_by": "2029-05-01", "one_time_cost": 500})))["c"]
    assert ok["feasible"] is True and ok["certainty"] == "expected" and ok["one_time_cost"] == 500 and ok["details"]["label"] == "מענק"
    nodate = opts(run(inputs(), request({"id": "c", "type": "custom", "label": "מענק", "amount": 40000})))["c"]
    assert nodate["feasible"] == "unknown" and nodate["missing_inputs"] == ["available_by"] and nodate["certainty"] == "uncertain"


def test_work_income_is_derived_from_a_deposit_option_and_never_assumed():
    out = run(inputs(income={"target": 15000, "actual": 9000, "remaining": 6000}),
              request(deposit_option(), {"id": "work", "type": "work_income", "based_on": "dep"}))
    w, d = opts(out)["work"], opts(out)["dep"]
    assert w["monthly_cash_effect"] == -d["monthly_cash_effect"] and w["certainty"] == "uncertain" and w["feasible"] == "unknown"
    assert w["details"]["income_goal"]["remaining"] == 6000
    assert opts(run(inputs(), request({"id": "work", "type": "work_income"})))["work"]["reason"] == "based_on_missing"


# ═══ the principle: expected is not existing ═══

def test_100k_owed_to_me_does_not_cover_the_goal():
    out = run(inputs(loans=[receivable(balance=100000)]), request(collect(expected_net=100000), allocation_plan=[{"goal_id": G, "option_id": "owed", "amount": 100000}]))
    plan_ = out["goals"][0]["plan"]
    assert plan_["covered"]["uncertain"] == 100000 and plan_["covered"]["confirmed"] == 0.0
    assert plan_["remaining_after_confirmed"] == 120000.0 and plan_["remaining_after_confirmed_and_expected"] == 120000.0


def test_3000_a_month_is_not_36000_in_the_account():
    goals = [goal_rec(target=36000, end="2027-10-31")]
    out = run(inputs(goals=goals, obligations={"potential_saving": 3000}), request({"id": "cut", "type": "obligations_reduction"},
              allocation_plan=[{"goal_id": G, "option_id": "cut", "amount": 20000}]))
    plan_ = out["goals"][0]["plan"]
    assert plan_["covered"]["confirmed"] == 0.0 and plan_["covered"]["uncertain"] == 20000 and plan_["remaining_after_confirmed"] == 36000.0


def test_coverage_is_split_by_certainty_and_never_one_total():
    out = run(inputs([cash(value=50000)], allocations=[al("a1", G, "recI", "fixed_amount", 20000)], loans=[receivable(arrangement="monthly")]),
              request(collect(expected_net=30000), {"id": "c", "type": "custom", "label": "x", "amount": 10000, "certainty": "uncertain", "available_by": "2029-01-01"},
                      allocation_plan=[{"goal_id": G, "option_id": "owed", "amount": 30000}, {"goal_id": G, "option_id": "c", "amount": 10000}]))
    covered = out["goals"][0]["plan"]["covered"]
    assert covered == {"confirmed": 20000.0, "expected": 30000.0, "uncertain": 10000.0, "unknown": 0.0}
    assert out["goals"][0]["plan"]["remaining_after_confirmed"] == 100000.0 and out["goals"][0]["plan"]["remaining_after_confirmed_and_expected"] == 70000.0


def test_no_recommendation_score_rank_or_total_anywhere_in_the_output():
    out = run(inputs([cash(value=50000)], allocations=[al("a1", G, "recI", "fixed_amount", 20000)], loans=[receivable()], assets=[asset()], obligations={"potential_saving": 100}),
              request(deposit_option(), loan_option(), sale(), collect(), {"id": "cut", "type": "obligations_reduction"},
                      {"id": "c", "type": "custom", "label": "x", "amount": 5, "available_by": "2029-01-01"}, {"id": "w", "type": "work_income", "based_on": "dep"}))
    banned = {"score", "rank", "ranking", "recommended", "best", "winner", "total_available", "balanced_score"}
    found = set()

    def walk(x):
        if isinstance(x, dict):
            found.update(banned & set(x))
            [walk(v) for v in x.values()]
        elif isinstance(x, list):
            [walk(v) for v in x]
    walk(out)
    assert not found and "payoff" not in json.dumps(out)


def test_every_option_returns_the_whole_contract_and_the_order_is_by_type_not_by_result():
    out = run(inputs(loans=[receivable()], assets=[asset()], obligations={"potential_saving": 100}),
              request(sale(), collect(), deposit_option(), loan_option(), {"id": "cut", "type": "obligations_reduction"}, {"id": "c", "type": "custom", "label": "x", "amount": 5}))
    keys = {"id", "type", "feasible", "reason", "covers_amount", "available_by", "monthly_cash_effect", "one_time_cost", "total_cost", "new_liabilities",
            "time_to_realize_months", "certainty", "conditions", "risks", "assumptions", "missing_inputs", "provenance", "details"}
    order = [o["type"] for o in out["goals"][0]["options"]]
    assert all(set(o) == keys and o["certainty"] in fp.CERTAINTIES for o in out["goals"][0]["options"])
    assert order == sorted(order, key=fp.OPTION_TYPES.index)
    shuffled = run(inputs(loans=[receivable()], assets=[asset()], obligations={"potential_saving": 100}),
                   request({"id": "c", "type": "custom", "label": "x", "amount": 5}, {"id": "cut", "type": "obligations_reduction"}, loan_option(), deposit_option(), collect(), sale()))
    assert [o["id"] for o in shuffled["goals"][0]["options"]] == [o["id"] for o in out["goals"][0]["options"]]


# ═══ plan checks ═══

def test_a_plan_cannot_use_an_infeasible_option_or_more_than_it_covers():
    with pytest.raises(ValueError):
        run(inputs(assets=[asset()]), request(sale(expected_date="2031-01-01"), allocation_plan=[{"goal_id": G, "option_id": "sale", "amount": 10}]))
    with pytest.raises(ValueError):
        run(inputs(assets=[asset()]), request(sale(), allocation_plan=[{"goal_id": G, "option_id": "sale", "amount": 300001}]))


def test_one_pool_for_two_goals_is_over_committed_and_not_silently_clipped():
    goals = [goal_rec(), goal_rec(G2, title="חתונה 2")]
    out = run(inputs(goals=goals, assets=[asset()]), request(sale(), goal_ids=(G, G2),
              allocation_plan=[{"goal_id": G, "option_id": "sale", "amount": 200000}, {"goal_id": G2, "option_id": "sale", "amount": 200000}]))
    assert out["portfolio"]["over_committed"] == ["sale"]
    assert out["goals"][0]["plan"]["covered"]["uncertain"] == 200000 and out["goals"][1]["plan"]["covered"]["uncertain"] == 200000
    within = run(inputs(goals=goals, assets=[asset()]), request(sale(), goal_ids=(G, G2),
                 allocation_plan=[{"goal_id": G, "option_id": "sale", "amount": 150000}, {"goal_id": G2, "option_id": "sale", "amount": 150000}]))
    assert within["portfolio"]["over_committed"] == []


def test_the_order_of_goals_does_not_change_pool_results():
    goals = [goal_rec(), goal_rec(G2, title="חתונה 2")]
    plan_ = [{"goal_id": G, "option_id": "sale", "amount": 200000}, {"goal_id": G2, "option_id": "sale", "amount": 200000}]
    a = run(inputs(goals=goals, assets=[asset()]), request(sale(), goal_ids=(G, G2), allocation_plan=plan_))
    b = run(inputs(goals=goals, assets=[asset()]), request(sale(), goal_ids=(G2, G), allocation_plan=list(reversed(plan_))))
    assert a["portfolio"]["over_committed"] == b["portfolio"]["over_committed"] == ["sale"]


def test_portfolio_shows_planned_and_actual_savings_as_two_separate_figures():
    """The standing PLAN (`target`) and what was ACTUALLY put aside (`actual`) are different questions (forward-looking vs how far we got):
    each has its own figure and its own shortfall; neither is ever presented under the other's name."""
    plan_ = [{"goal_id": G, "option_id": "dep", "amount": 120000}]
    out = run(inputs(savings_plan={"target": 5000, "actual": 1000}), request(deposit_option(), allocation_plan=plan_))
    p = out["portfolio"]
    burden = 120000 / 51
    assert p["plan_chosen"] and p["monthly_burden_in_plan"] == pytest.approx(burden, abs=0.01)
    assert p["planned_monthly_savings"] == 5000 and p["actual_monthly_savings"] == 1000
    assert p["shortfall_vs_planned"] == 0.0 and p["shortfall_vs_actual"] == pytest.approx(burden - 1000, abs=0.01)
    assert p["planned_known"] is True and p["actual_known"] is True
    only_actual = run(inputs(savings_plan={"actual": 1000}), request(deposit_option(), allocation_plan=plan_))["portfolio"]
    assert only_actual["planned_known"] is False and only_actual["planned_monthly_savings"] is None and only_actual["shortfall_vs_planned"] is None
    assert only_actual["actual_known"] is True
    unknown = run(inputs(), request(deposit_option(), allocation_plan=plan_))["portfolio"]
    assert unknown["planned_known"] is False and unknown["actual_known"] is False
    assert unknown["shortfall_vs_planned"] is None and unknown["shortfall_vs_actual"] is None
    nothing = run(inputs(), request(deposit_option()))["portfolio"]
    assert nothing["plan_chosen"] is False and nothing["monthly_burden_in_plan"] is None


def test_the_planner_does_not_mutate_its_inputs():
    inp = inputs([cash(value=50000)], allocations=[al("a1", G, "recI", "fixed_amount", 20000)], loans=[receivable()], assets=[asset()], obligations={"potential_saving": 100})
    before = copy.deepcopy(inp)
    run(inp, request(deposit_option(), sale(), collect(), loan_option(), {"id": "cut", "type": "obligations_reduction"}))
    assert inp == before


# ═══ static guard: pure module, one reader, one endpoint ═══

ROOT = Path(__file__).parent


def test_the_engine_has_no_io_and_only_the_reader_and_endpoint_use_it():
    src = (ROOT / "portfolio_lab" / "funding_plan.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+(requests|httpx|urllib|socket|airtable|tools|anthropic|openai|os|subprocess)\b", src, re.M)
    assert "airtable_gateway" not in src and "Tables." not in src and "propose_action" not in src
    users = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py") if "node_modules" not in p.parts and p.name != "funding_plan.py"
                   and not p.name.startswith("test_") and re.search(r"portfolio_lab\.funding_plan|from portfolio_lab import funding_plan|import funding_plan", p.read_text(encoding="utf-8")))
    assert users == ["portfolio_lab/funding_sources.py", "tma_api.py"]       # the endpoint, and the pure candidate-list module that reuses its date helpers
    svc = (ROOT / "core" / "financial_control" / "service.py").read_text(encoding="utf-8")
    body = svc[svc.index("def funding_inputs"):svc.index("def overview(")]
    assert "propose_action" not in body and "airtable_gateway" not in body and "_write" not in body


def test_a_plan_that_allocates_more_than_the_target_shows_the_excess_and_changes_nothing():
    """Display only: the excess over the goal is reported (`over_target_by`), nothing is trimmed or rewritten, and an exact fit shows 0."""
    goals = [goal_rec(target=250000)]
    over = run(inputs(goals=goals, assets=[asset()]), request(sale(), allocation_plan=[{"goal_id": G, "option_id": "sale", "amount": 275000}]))
    plan_ = over["goals"][0]["plan"]
    assert plan_["allocations"][0]["amount"] == 275000                                   # the owner's number is kept as entered
    assert plan_["allocated_total"] == 275000 and plan_["over_target_by"] == 25000
    exact = run(inputs(goals=goals, assets=[asset()]), request(sale(), allocation_plan=[{"goal_id": G, "option_id": "sale", "amount": 250000}]))
    assert exact["goals"][0]["plan"]["over_target_by"] == 0.0


# ═══ required monthly deposit card (REQUIRED_MONTHLY_DEPOSIT_CARD_SPEC) ═══

def card(out, index=0):
    return out["goals"][index]["required_monthly_card"]


def test_the_card_answers_how_much_per_month_without_an_account_or_an_option():
    out = run(inputs(), request())
    c = card(out)
    assert c["amount"] == pytest.approx(120000 / 51, abs=0.01) and c["months"] == 51 and c["due"] == "2030-12-31" and c["gap"] == 120000
    assert c["basis"] == "assumptions" and c["total_deposits"] == pytest.approx(c["amount"] * 51, abs=0.01)
    assert out["goals"][0]["options"] and "slot" not in out["goals"][0]["need"]


def test_the_card_equals_the_direct_required_monthly_call():
    out = run(inputs(), request(deposit_option(expected_return_pct=4, fee_pct=0.3), assumptions={"annual_return_pct": 4, "annual_fee_pct": 0.3, "inflation_pct": 0}))
    assert card(out)["amount"] == opts(out)["dep"]["details"]["required_monthly"]
    p = fp.af.normalize_params({"years": 10, "annual_return_pct": 4, "annual_fee_pct": 0.3, "inflation_pct": 0})
    assert card(out)["amount"] == fp.required_monthly(120000, 51, years=10, annual_return=0.04, fee=0.003, deposit_fee_pct=0.0, p=p, start="2026-10-01")


def test_the_card_shows_each_assumption_with_its_source():
    owner = card(run(inputs(), request()))["assumptions"]["sources"]
    assert owner == {"annual_return_pct": "owner", "annual_fee_pct": "owner", "inflation_pct": "owner"}
    mixed = card(run(inputs(), request(assumptions={"annual_return_pct": 5})))
    assert mixed["assumptions"]["annual_return_pct"] == 5 and mixed["assumptions"]["sources"] == {
        "annual_return_pct": "owner", "annual_fee_pct": "default", "inflation_pct": "default"}


def test_the_sensitivity_range_is_two_points_each_way_and_monotonic():
    c = card(run(inputs(), request(assumptions={"annual_return_pct": 5, "annual_fee_pct": 0, "inflation_pct": 0})))
    low, base, high = c["sensitivity"]
    assert (low["annual_return_pct"], base["annual_return_pct"], high["annual_return_pct"]) == (3.0, 5.0, 7.0)
    assert low["amount"] >= base["amount"] >= high["amount"] and base["amount"] == c["amount"]


def test_unreachable_under_the_assumptions_gives_no_number(monkeypatch):
    monkeypatch.setattr(fp, "_value_at", lambda *a, **k: 0.0)
    c = card(run(inputs(), request()))
    assert c["amount"] is None and c["reason"] == "unreachable_under_assumptions" and c["total_deposits"] is None


def test_a_goal_that_cannot_be_sized_says_why_and_a_covered_goal_needs_nothing():
    assert card(run(inputs(goals=[goal_rec(end=None)]), request())) == {"amount": None, "reason": "missing_date"}
    covered = card(run(inputs([cash(value=500000)], allocations=[al("a1", G, "recI", "fixed_amount", 130000)]), request()))
    assert covered["amount"] == 0.0 and covered["reason"] == "no_gap"


def test_a_plan_adds_the_same_deposit_for_each_remainder_and_changes_nothing_else():
    plan_req = request(sale(), allocation_plan=[{"goal_id": G, "option_id": "sale", "amount": 90000}])
    out = run(inputs(assets=[asset()]), plan_req)
    c = card(out)
    by = {s["basis"]: s for s in c["scenarios"]}
    assert by["after_confirmed"]["remaining"] == 120000 and by["after_confirmed_and_expected"]["remaining"] == 120000
    assert by["after_all_selected"]["remaining"] == 30000 and by["after_all_selected"]["amount"] == pytest.approx(30000 / 51, abs=0.01)
    plan_ = out["goals"][0]["plan"]
    assert plan_["monthly_burden"] == 0.0 and out["portfolio"]["monthly_burden_in_plan"] == 0.0          # the card is a question, not a commitment
    assert plan_["remaining_after_confirmed"] == 120000 and plan_["covered"]["uncertain"] == 90000


def test_the_planned_savings_sit_beside_the_required_deposit_and_are_never_netted():
    c = card(run(inputs(savings_plan={"target": 13000, "actual": 0}), request()))
    assert c["planned_monthly_savings"] == 13000 and c["amount"] == pytest.approx(120000 / 51, abs=0.01)
    assert card(run(inputs(), request()))["planned_monthly_savings"] is None


def test_the_card_has_no_recommendation_score_or_ranking():
    text = json.dumps(card(run(inputs(), request())), ensure_ascii=False).lower()
    assert not re.search(r"recommend|score|rank|המלצה|ציון|דירוג|best|cheapest", text)
