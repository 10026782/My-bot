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


# ═══ required monthly deposit card: when does each deposit reach the goal (Q-R8: two SEPARATE forecasts) ═══

def arrival(out, basis, index=0):
    return next(a for a in card(out, index)["arrival"] if a["basis"] == basis)


def with_card(monthly=None, **extra):
    body = {"goal_ids": [G], "options": [], "allocation_plan": [], "assumptions": FLAT_ASSUMPTIONS}
    if monthly is not None:
        body["card_monthly"] = monthly
    return fp.normalize_request({**body, **extra})


def test_two_separate_arrival_forecasts_planned_and_entered_never_combined():
    out = run(inputs(savings_plan={"target": 13000}), with_card(5000))
    planned, entered = arrival(out, "planned"), arrival(out, "entered")
    assert (planned["monthly"], planned["reach_date"], planned["months_vs_due"]) == (13000.0, "2027-07-31", -41)       # 120000 / 13000 -> 10th month
    assert (entered["monthly"], entered["reach_date"], entered["months_vs_due"]) == (5000.0, "2028-09-30", -27)        # 120000 / 5000 -> 24th month
    assert [a["basis"] for a in card(out)["arrival"]] == ["planned", "entered"]                                       # no third, combined forecast


def test_the_required_deposit_arrives_in_the_due_month_not_later_and_one_cent_less_does_not():
    c = card(run(inputs(), with_card()))
    on_time = card(run(inputs(), with_card(c["amount"])))
    assert arrival({"goals": [{"required_monthly_card": on_time}]}, "entered")["months_vs_due"] <= 0
    short = card(run(inputs(), with_card(c["amount"] - 1)))
    assert arrival({"goals": [{"required_monthly_card": short}]}, "entered")["months_vs_due"] > 0


def test_no_arrival_within_the_horizon_is_said_plainly_with_no_invented_date():
    out = run(inputs(goals=[goal_rec(target=10_000_000)]), with_card(1))
    a = arrival(out, "entered")
    assert a["reached"] is False and a["reach_date"] is None and a["months_vs_due"] is None


def test_a_missing_planned_figure_is_missing_not_zero_and_no_entered_figure_means_no_second_forecast():
    out = run(inputs(), with_card())
    assert card(out)["arrival"] == [{"basis": "planned", "monthly": None}]
    assert arrival(run(inputs(savings_plan={"target": 0}), with_card()), "planned") == {"basis": "planned", "monthly": None}


@pytest.mark.parametrize("bad", [0, -5, "5000", True, float("nan"), 10**11])
def test_the_figure_typed_on_the_card_must_be_a_positive_amount(bad):
    with pytest.raises(ValueError):
        with_card(bad)


def test_arrival_is_deterministic_and_does_not_change_the_rest_of_the_answer():
    a = run(inputs(savings_plan={"target": 13000}), with_card(5000))
    assert a == run(inputs(savings_plan={"target": 13000}), with_card(5000))
    b = run(inputs(savings_plan={"target": 13000}), with_card())
    assert a["goals"][0]["need"] == b["goals"][0]["need"] and a["portfolio"] == b["portfolio"]
    assert {k: v for k, v in card(a).items() if k != "arrival"} == {k: v for k, v in card(b).items() if k != "arrival"}


# ═══ the chain's C4: where the required deposit sits — routes A / B / C(ד׳) side by side (GOAL_FUNDING_CHAIN_SPEC §1.2) ═══

INCOME = {"target": 18000, "actual": 9000, "remaining": 9000}


def routes(out, index=0, basis="gap"):
    alt = next(a for a in card(out, index)["alternatives"] if a["basis"] == basis)
    return alt["required"], {r["key"]: r for r in alt["routes"]}


def with_existing(amount=None, **extra):
    body = {"goal_ids": [G], "options": [], "allocation_plan": [], "assumptions": FLAT_ASSUMPTIONS, **extra}
    if amount is not None:
        body["from_existing"] = amount
    return fp.normalize_request(body)


def test_route_a_adds_the_whole_deposit_to_the_required_income_and_leaves_the_planned_deposits_alone():
    required, r = routes(run(inputs(savings_plan={"target": 13000}, income=INCOME), with_existing()))
    a = r["A"]
    assert required == card(run(inputs(), with_existing()))["amount"]
    assert (a["income_need_before"], a["income_need_after"]) == (18000.0, round(18000 + required, 2))
    assert (a["planned_before"], a["planned_after"], a["reduces_planned_deposits"], a["feasible"]) == (13000.0, 13000.0, False, True)


def test_route_b_takes_the_whole_deposit_out_of_the_planned_deposits_and_warns_that_it_reduces_them():
    required, r = routes(run(inputs(savings_plan={"target": 13000}, income=INCOME), with_existing()))
    b = r["B"]
    assert (b["income_need_after"], b["planned_after"], b["feasible"]) == (18000.0, round(13000 - required, 2), True)
    assert b["reduces_planned_deposits"] is True                                  # the UI must show the prominent warning (Q-C12): never silent


def test_route_b_is_not_possible_when_the_deposit_is_bigger_than_the_planned_deposits_and_says_by_how_much():
    required, r = routes(run(inputs(savings_plan={"target": 1000}, income=INCOME), with_existing()))
    b = r["B"]
    assert b["feasible"] is False and b["reason"] == "exceeds_planned" and b["shortfall"] == round(required - 1000, 2) and b["planned_after"] is None
    assert r["A"]["feasible"] is True                                              # the other route is still shown, not hidden


def test_route_d_splits_the_deposit_between_existing_deposits_and_more_income_and_the_percent_is_computed():
    required, r = routes(run(inputs(savings_plan={"target": 13000}, income=INCOME), with_existing(1000)))
    c = r["C"]
    assert c["from_existing"] == 1000.0 and c["top_up_income"] == round(required - 1000, 2)
    assert c["income_need_after"] == round(18000 + required - 1000, 2) and c["planned_after"] == 12000.0
    assert c["existing_share_pct"] == round(1000 / required * 100, 1) and c["reduces_planned_deposits"] is True and c["feasible"] is True


def test_route_d_edges_more_than_required_more_than_planned_and_nothing_entered():
    required, r = routes(run(inputs(savings_plan={"target": 13000}, income=INCOME), with_existing(5000)))
    assert r["C"]["top_up_income"] == 0.0 and r["C"]["over_required_by"] == round(5000 - required, 2) and r["C"]["existing_share_pct"] == 100.0
    _, r = routes(run(inputs(savings_plan={"target": 800}, income=INCOME), with_existing(1000)))
    assert r["C"]["feasible"] is False and r["C"]["reason"] == "exceeds_planned" and r["C"]["shortfall"] == 200.0
    _, r = routes(run(inputs(savings_plan={"target": 13000}, income=INCOME), with_existing()))
    assert r["C"] == {"key": "C", "feasible": "unknown", "reason": "amount_not_entered"}


def test_missing_income_or_planned_savings_is_missing_never_zero():
    required, r = routes(run(inputs(), with_existing(1000)))
    assert r["A"]["income_need_before"] is None and r["A"]["income_need_after"] is None and r["A"]["planned_before"] is None
    assert r["B"]["feasible"] == "unknown" and r["B"]["reason"] == "planned_missing" and r["B"]["planned_after"] is None
    assert r["C"]["feasible"] == "unknown" and r["C"]["income_need_after"] is None


def test_routes_are_in_a_fixed_order_and_carry_no_ranking_or_recommendation():
    out = run(inputs(savings_plan={"target": 13000}, income=INCOME), with_existing(1000))
    alt = card(out)["alternatives"][0]
    assert [x["key"] for x in alt["routes"]] == ["A", "B", "C"]
    text = json.dumps(alt, ensure_ascii=False).lower()
    assert not re.search(r"recommend|score|rank|best|cheapest|המלצה|ציון|דירוג|כדאי", text)


def test_routes_are_also_given_for_each_plan_remainder_and_nothing_else_changes():
    plan_req = with_existing(1000, options=[{"id": "sale", "type": "asset_sale", "net_proceeds": 90000, "expected_date": "2027-06-01", "confirmed_buyer": False}],
                             allocation_plan=[{"goal_id": G, "option_id": "sale", "amount": 90000}])
    out = run(inputs(assets=[asset()], savings_plan={"target": 13000}, income=INCOME), plan_req)
    bases = {a["basis"]: a for a in card(out)["alternatives"]}
    assert bases["after_all_selected"]["remaining"] == 30000.0 and bases["after_all_selected"]["required"] == pytest.approx(30000 / 51, abs=0.01)
    assert out["goals"][0]["plan"]["remaining_after_confirmed"] == 120000 and out["portfolio"]["monthly_burden_in_plan"] == 0.0


@pytest.mark.parametrize("bad", [0, -1, "1000", True, float("inf"), 10**11])
def test_the_amount_from_existing_deposits_must_be_a_positive_amount(bad):
    with pytest.raises(ValueError):
        with_existing(bad)


# ═══ no English on the Hebrew screen: every code / note the server can emit has a Hebrew entry in the client (drift guard) ═══

def _client_keys(map_name: str) -> set:
    src = Path("tma-frontend/src/lib/familyWealth.ts").read_text(encoding="utf-8")
    block = re.search(rf"const {map_name}[^=]*=\s*\{{(.*?)\n\}};|const {map_name}[^=]*=\s*\{{(.*?)\}};", src, re.S)
    body = (block.group(1) or block.group(2)) if block else ""
    return set(re.findall(r"(?:^|[,{\s])([A-Za-z_][A-Za-z0-9_]*)\s*:", body))


def _rich_runs():
    runs = []
    for kwargs, opts in (
        ({"savings_plan": {"target": 13000, "actual": 0}, "income": INCOME, "loans": [receivable()], "assets": [asset()], "obligations": {"potential_saving": 100}},
         [{"id": "c", "type": "custom", "label": "x", "amount": 5}, {"id": "cut", "type": "obligations_reduction"}, loan_option(), deposit_option(expected_return_pct=4), collect(), sale(),
          {"id": "wi", "type": "work_income", "based_on": "dep"}]),
        ({"savings_plan": {}}, [{"id": "dep", "type": "new_deposits", "hypothetical": {"liquid_from": "2031-06-01"}}]),
        ({"savings_plan": {}, "assets": [asset()]}, [sale(expected_date="2031-01-01"), loan_option(available_by="2031-06-01")]),
    ):
        runs.append(run(inputs(**kwargs), request(*opts)))
    runs.append(run(inputs(goals=[goal_rec(end=None)]), request()))
    runs.append(run(inputs(goals=[goal_rec(end="2020-01-01")]), request()))
    runs.append(run(inputs(), request(deposit_option(), allocation_plan=[{"goal_id": G, "option_id": "dep", "amount": 1000}])))
    return runs


def test_every_code_the_server_emits_has_a_hebrew_label_in_the_client():
    codes = {"conditions": set(), "risks": set(), "missing_inputs": set(), "reasons": set(), "need_reasons": set()}
    for out in _rich_runs():
        for g in out["goals"]:
            if g["need"]["reason"]:
                codes["need_reasons"].add(g["need"]["reason"])
            for o in g["options"]:
                codes["conditions"] |= set(o["conditions"]); codes["risks"] |= set(o["risks"]); codes["missing_inputs"] |= set(o["missing_inputs"])
                if o["reason"]:
                    codes["reasons"].add(o["reason"])
    known = {"conditions": _client_keys("FUNDING_CONDITIONS"), "risks": _client_keys("FUNDING_RISKS"), "missing_inputs": _client_keys("MISSING_INPUT_LABELS"),
             "reasons": _client_keys("FUNDING_REASONS"), "need_reasons": _client_keys("NEED_REASONS")}
    assert all(known.values()) and all(codes[k] for k in ("conditions", "risks", "reasons")), "the guard must see both sides (not vacuous)"
    missing = {k: sorted(codes[k] - known[k]) for k in codes if codes[k] - known[k]}
    assert not missing, f"codes shown raw (English) on the Hebrew screen: {missing}"


def test_every_server_note_and_assumption_is_translated_by_a_prefix_in_the_client():
    src = Path("tma-frontend/src/lib/familyWealth.ts").read_text(encoding="utf-8")
    prefixes = re.findall(r'^\s*\["([^"]+)",\s*"', src[src.index("const SERVER_NOTES_HE"):src.index("export const serverNote")], re.M)
    assert prefixes
    texts = set()
    for out in _rich_runs():
        for g in out["goals"]:
            texts |= {a for o in g["options"] for a in o["assumptions"]}
            if g.get("plan"):
                texts.add(g["plan"]["note"])
            if g.get("required_monthly_card", {}).get("note"):
                texts.add(g["required_monthly_card"]["note"])
    untranslated = sorted(t for t in texts if not any(t.startswith(p) for p in prefixes))
    assert not untranslated, f"English shown as written on the Hebrew screen: {untranslated}"


# ═══ the date is an estimate: the required deposit at each end of the window, inside the card (SPEC §3 / O4) ═══

def windowed(end="2030-12-31", margin=12):
    return card(run(inputs(goals=[{**goal_rec(end=end), "date_margin_months": margin}]), request()))


def test_the_card_shows_the_required_deposit_at_both_ends_of_the_date_window_and_the_point_estimate_stays():
    c = windowed()
    point = card(run(inputs(), request()))["amount"]
    assert c["amount"] == point                                             # the point estimate is unchanged by the window
    w = c["window"]
    assert w["margin_months"] == 12 and w["early"]["due"] == "2029-12-31" and w["late"]["due"] == "2031-12-31"
    assert w["early"]["amount"] > c["amount"] > w["late"]["amount"]         # an earlier date needs more per month, a later one less (server numbers)
    p = fp.af.normalize_params({"years": 10, **FLAT_ASSUMPTIONS})
    assert w["late"]["amount"] == fp.required_monthly(120000, 63, years=10, annual_return=0.0, fee=0.0, deposit_fee_pct=0.0, p=p, start="2026-10-01")


def test_a_window_end_that_already_passed_says_so_and_has_no_number():
    w = windowed(end="2027-06-30", margin=24)["window"]
    assert w["early"]["reason"] == "past_date" and w["early"]["amount"] is None
    assert w["late"]["amount"] is not None and w["late"]["reason"] is None


def test_no_window_without_a_margin_and_the_variants_do_not_recurse_into_a_window():
    assert "window" not in card(run(inputs(), request()))
    out = run(inputs(goals=[{**goal_rec(), "date_margin_months": 6}]), request())
    early = out["goals"][0]["window"]["early"]
    assert early["required_card"]["amount"] is not None and "window" not in early["required_card"] and "alternatives" not in early["required_card"]


# ═══ monthly commitments schedule (GOAL_FUNDING_CHAIN_SPEC §4: Q-C5 read-only, Q-C6 all active goals with a filter, Q-C7 a release is its own row) ═══

G3 = "recG3"


def sched_goals():
    return [goal_rec(G, 120000, "2028-10-19", title="אלחנן"), goal_rec(G2, 120000, "2030-01-19", title="נתנאל"), goal_rec(G3, 120000, "2031-04-19", title="יוסף"),
            goal_rec("recG4", None, None, title="פרויקט ללא סכום ותאריך"), goal_rec("recG5", 50000, None, title="חצי מוגדר"),
            {**goal_rec("recG6", 9000, "2029-01-01", title="הושלם"), "status": "done"}]


def schedule(goals=None, *, planned=13000, only=None, assumptions=None):
    body = {"goal_ids": [G], "options": [], "allocation_plan": [], "assumptions": FLAT_ASSUMPTIONS if assumptions is None else assumptions, "schedule": True}
    if only is not None:
        body["schedule_goal_ids"] = only
    inp = inputs(goals=goals if goals is not None else sched_goals(), savings_plan={"target": planned} if planned is not None else {})
    return run(inp, fp.normalize_request(body))["schedule"]


def test_successive_goals_are_not_summed_as_if_parallel_and_a_finished_deposit_is_released_in_its_own_row():
    sc = schedule()
    rows = {r["goal_id"]: r for r in sc["rows"]}
    assert [st["goal_ids"] for st in sc["steps"]] == [[G, G2, G3], [G2, G3], [G3]]                  # the burden steps DOWN as deposits end
    assert [st["burden"] for st in sc["steps"]] == [round(sum(r["amount"] for r in rows.values()), 2),
                                                    round(rows[G2]["amount"] + rows[G3]["amount"], 2), rows[G3]["amount"]]
    assert sc["peak_burden"] == sc["steps"][0]["burden"]
    assert [(x["goal_id"], x["released_from"]) for x in sc["releases"]] == [(G, "2028-10-01"), (G2, "2030-01-01"), (G3, "2031-04-01")]
    assert all(x["amount"] == rows[x["goal_id"]]["amount"] for x in sc["releases"])


def test_each_amount_is_the_same_required_monthly_search_on_the_goals_own_gap_and_months():
    sc = schedule()
    p = fp.af.normalize_params({"years": 10, **FLAT_ASSUMPTIONS})
    r = next(x for x in sc["rows"] if x["goal_id"] == G2)
    assert r["months"] == 39 and r["start"] == "2026-10-01" and r["end"] == "2029-12-01"        # due 19/01/2030: the last COMPLETED month is 12/2029 (A2)
    assert r["amount"] == fp.required_monthly(120000, 39, years=10, annual_return=0.0, fee=0.0, deposit_fee_pct=0.0, p=p, start="2026-10-01")
    assert r["amount"] == card(run(inputs(goals=sched_goals()), request(goal_ids=(G2,))))["amount"]


def test_the_filter_recomputes_the_curve_for_the_chosen_goals_only_and_keeps_the_others_listed():
    sc = schedule(only=[G2])
    assert [r["selected"] for r in sc["rows"]] == [False, True, False] and [st["goal_ids"] for st in sc["steps"]] == [[G2]]
    assert [x["goal_id"] for x in sc["releases"]] == [G2] and sc["peak_burden"] == next(r["amount"] for r in sc["rows"] if r["goal_id"] == G2)
    assert schedule(only=[])["steps"] == [] and schedule(only=[])["peak_burden"] == 0.0


def test_goals_that_cannot_be_scheduled_are_listed_with_why_never_zero_and_inactive_goals_are_not_included():
    sc = schedule()
    ex = {e["goal_id"]: e["reason"] for e in sc["excluded"]}
    assert ex == {"recG5": "missing_date"}                                    # "פרויקט" (nothing defined) is not a funding goal; "הושלם" is not active
    assert "recG4" not in {r["goal_id"] for r in sc["rows"]} and "recG6" not in {r["goal_id"] for r in sc["rows"]}


def test_a_covered_goal_has_no_deposit_row_and_a_missing_planned_figure_is_missing():
    covered = inputs([cash(value=500000)], allocations=[al("a1", G, "recI", "fixed_amount", 130000)], goals=sched_goals(), savings_plan={})
    sc = fp.build_funding_plan(covered, fp.normalize_request({"goal_ids": [G], "options": [], "allocation_plan": [], "assumptions": FLAT_ASSUMPTIONS, "schedule": True}), TODAY)["schedule"]
    assert G not in {r["goal_id"] for r in sc["rows"]} and {e["goal_id"]: e["reason"] for e in sc["excluded"]}[G] == "no_gap"
    assert sc["planned_monthly_savings"] is None and all(st["shortfall_vs_planned"] is None for st in sc["steps"]) and sc["peak_shortfall"] is None


def test_the_shortfall_against_the_planned_savings_is_per_step_and_never_negative():
    sc = schedule(planned=9000)
    assert [st["shortfall_vs_planned"] for st in sc["steps"]] == [round(max(st["burden"] - 9000, 0.0), 2) for st in sc["steps"]]
    assert sc["steps"][0]["shortfall_vs_planned"] > 0 and sc["steps"][-1]["shortfall_vs_planned"] == 0.0 and sc["peak_shortfall"] == sc["steps"][0]["shortfall_vs_planned"]
    assert schedule(planned=100000)["peak_shortfall"] == 0.0                         # never negative


def test_more_than_ten_goals_is_said_not_silently_dropped_and_the_schedule_is_off_by_default():
    many = [goal_rec(G, 10000, "2029-01-15")] + [goal_rec(f"recM{i:02d}", 10000, f"2030-0{1 + i % 9}-15", title=f"יעד {i}") for i in range(11)]
    sc = schedule(goals=many)
    assert sc["truncated"] is True and len(sc["rows"]) == 10
    assert "schedule" not in run(inputs(goals=sched_goals()), request())
    with pytest.raises(ValueError):
        fp.normalize_request({"goal_ids": [G], "schedule": "yes"})
    with pytest.raises(ValueError):
        fp.normalize_request({"goal_ids": [G], "schedule_goal_ids": ["bad id"]})


def test_the_schedule_changes_nothing_else_and_carries_no_recommendation_or_english_prose():
    body = {"goal_ids": [G], "options": [], "allocation_plan": [], "assumptions": FLAT_ASSUMPTIONS}
    a = run(inputs(goals=sched_goals(), savings_plan={"target": 13000}), fp.normalize_request({**body, "schedule": True}))
    b = run(inputs(goals=sched_goals(), savings_plan={"target": 13000}), fp.normalize_request(body))
    assert {k: v for k, v in a.items() if k != "schedule"} == b
    text = json.dumps(a["schedule"], ensure_ascii=False).lower()
    assert not re.search(r"recommend|score|rank|best|המלצה|ציון|דירוג|כדאי", text)
    assert all(re.fullmatch(r"[a-z_]+", n) for n in a["schedule"]["notes"])        # codes only; the Hebrew wording lives in the client


def test_every_schedule_reason_and_note_has_a_hebrew_entry_in_the_client():
    goals = sched_goals() + [goal_rec("recG7", 50000, "2020-01-01", title="עבר"), goal_rec("recG8", None, "2029-01-01", title="בלי סכום")]
    seen_reasons, seen_notes = set(), set()
    for sc in (schedule(goals=goals), schedule(goals=goals, planned=None)):
        seen_reasons |= {e["reason"] for e in sc["excluded"]}
        seen_notes |= set(sc["notes"])
    covered = run(inputs([cash(value=500000)], allocations=[al("a1", G, "recI", "fixed_amount", 130000)], goals=sched_goals()),
                  fp.normalize_request({"goal_ids": [G], "options": [], "allocation_plan": [], "assumptions": FLAT_ASSUMPTIONS, "schedule": True}))["schedule"]
    seen_reasons |= {e["reason"] for e in covered["excluded"]}
    assert {"missing_date", "missing_target", "past_date", "no_gap"} <= seen_reasons
    assert seen_reasons <= _client_keys("SCHEDULE_EXCLUDED") and seen_notes <= _client_keys("SCHEDULE_NOTES") and seen_notes
