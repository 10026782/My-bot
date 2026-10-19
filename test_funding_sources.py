"""Goal funding sources, step 1 — pure candidate list (no network, no Airtable, no writes). See docs/portfolio_lab/GOAL_FUNDING_SOURCES_SPEC.md.

Five separate categories, no totals, nothing recommended, scored or ranked; missing stays missing; allocated-elsewhere is flagged, not recounted.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from portfolio_lab import funding_plan as fp
from portfolio_lab import funding_sources as fs
from test_accounts_forecast import TODAY, acct, plan
from test_goal_allocations_model import al, cash

G, G2 = "recG1", "recG2"
FORBIDDEN_KEYS = {"recommended", "recommendation", "score", "rank", "ranking", "total_available", "best"}


def goal_rec(gid=G, target=120000, end="2030-12-31", **extra):
    return {"id": gid, "title": "חתונה", "category": "savings", "status": "active", "target_amount": target, "end_date": end, **extra}


def inputs(accounts=None, goals=None, allocations=None, **extra):
    base = {"goals": goals if goals is not None else [goal_rec()], "accounts_view": plan(accounts or []), "allocations": allocations or [],
            "goal_rows": [], "loans": [], "assets": [], "obligations": None, "income": None, "savings_plan": {}}
    base.update(extra)
    return base


def request(goal_ids=(G,), margin=None):
    return fp.normalize_request({"goal_ids": list(goal_ids), "date_margin_months": margin})


def run(inp, goal_ids=(G,), margin=None):
    return fs.build_suggested_sources(inp, request(goal_ids, margin), TODAY)


def cats(out, index=0):
    return out["goals"][index]["categories"]


def ids(rows):
    return [r["source_id"] for r in rows]


def keys_of(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from keys_of(v)
    elif isinstance(value, list):
        for v in value:
            yield from keys_of(v)


def asset(**extra):
    return {"id": "recAS1", "name": "דירה", "asset_type": "Residential", "current_value": 2000000, "ownership_pct": 100, "mortgage_balance": None,
            "monthly_income": None, "linked_debt": None, "linked_loans": [], **extra}


def owed(arrangement=None, balance=100000, active=True, loan_id="recOW1"):
    return {"id": loan_id, "name": "חוב", "direction": "owed_to_me", "active": active, "arrangement": arrangement, "early_closure_balance": balance,
            "next_payment_due": None, "end_date": None}


# ── קטגוריות וחוזה ───────────────────────────────────────────────────────────────────────────────────────────────

def test_five_separate_categories_and_no_totals_or_ranking_keys():
    out = run(inputs([cash("recI"), acct("recL", 5000, liquidity="locked_until_date", liquid_from="2029-01-01", planned_monthly_deposit=100)],
                     assets=[asset()], loans=[owed(arrangement="monthly")]))
    assert tuple(cats(out)) == fs.CATEGORIES and len(fs.CATEGORIES) == 5
    assert not (set(keys_of(out)) & FORBIDDEN_KEYS)
    assert not [k for k in keys_of(out) if k.startswith("total") or "sum" in k]


def test_source_has_no_forbidden_key_in_code():
    text = Path("portfolio_lab/funding_sources.py").read_text(encoding="utf-8")
    assert not re.search(r"""["'](recommended|score|rank|total_available)["']\s*:""", text)


def test_immediate_account_is_liquid_now_and_shows_state_now_and_at_due():
    row = cats(run(inputs([cash("recI", 1000)])))["liquid_now"][0]
    assert row["amount"] == 1000 and row["amount_status"] == "reported" and row["certainty"] == "confirmed"
    assert row["liquidity"]["state_at"]["now"] == "accessible" == row["liquidity"]["state_at"]["due"]
    assert row["option_template"] is None                                          # existing_balance is automatic, never an added option


def test_a_dated_account_past_its_release_date_is_conditional_never_accessible():
    out = run(inputs([acct("recD", 5000, liquidity="locked_until_date", liquid_from="2027-01-01")]))
    c = cats(out)
    assert ids(c["conditional_on_action"]) == ["recD"] and not c["liquid_now"] and not c["liquid_by_due_date"]
    row = c["conditional_on_action"][0]
    assert row["liquidity"]["state_at"]["now"] == "locked" and row["liquidity"]["state_at"]["due"] == "conditional"
    assert "liquid_from_reached_eligibility_unverified" in row["conditions"]       # Liquid From is not an entitlement


def test_unverified_liquidity_is_conditional_and_missing_is_marked():
    row = cats(run(inputs([acct("recU", 7000)])))["conditional_on_action"][0]
    assert "liquidity" in row["missing_inputs"] and row["certainty"] == "uncertain"


def test_undated_locked_account_is_listed_as_unavailable_not_as_a_source():
    out = run(inputs([acct("recK", 7000, liquidity="locked_until_date")]))
    assert all(not rows for name, rows in cats(out).items() if name != "future_deposits")
    gone = out["goals"][0]["not_available_by_due_date"]
    assert ids(gone) == ["recK"] and "liquid_from" in gone[0]["missing_inputs"]


def test_a_retirement_product_is_never_one_time_cash():
    out = run(inputs([acct("recP", 9000, account_type="pension", liquidity="immediate")]))
    row = cats(out)["conditional_on_action"][0]
    assert "retirement_product_not_one_time_cash" in row["conditions"] and not cats(out)["liquid_now"]


def test_missing_balance_is_missing_not_zero_and_closed_is_left_out():
    out = run(inputs([acct("recN", None, liquidity="immediate"), acct("recX", 5, status="closed", liquidity="immediate")]))
    row = cats(out)["liquid_now"][0]
    assert row["amount"] is None and row["amount_status"] == "missing" and "balance_snapshot" in row["missing_inputs"]
    assert "recX" not in json.dumps(out)


def test_a_goal_without_a_date_or_in_the_past_keeps_now_and_hides_due_states():
    for end, reason in ((None, "missing_date"), ("2020-01-01", "past_date")):
        out = run(inputs([cash("recI")], goals=[goal_rec(end=end)]))
        goal = out["goals"][0]
        assert goal["reason"] == reason and ids(goal["categories"]["liquid_now"]) == ["recI"]
        assert goal["categories"]["liquid_now"][0]["liquidity"]["state_at"]["due"] is None


# ── ספירה כפולה ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_an_account_allocated_to_another_goal_is_flagged_not_recounted():
    accounts = [cash("recI", 1000)]
    out = run(inputs(accounts, goals=[goal_rec(G), goal_rec(G2)], allocations=[al("a1", G2, "recI", "fixed_amount", 400)]), goal_ids=(G, G2))
    first, second = cats(out, 0)["liquid_now"][0], cats(out, 1)["liquid_now"][0]
    assert first["allocation"]["allocated_elsewhere"] is True and "allocated_elsewhere" in first["risks"]
    assert first["allocation"]["allocated_elsewhere_amount"] == 400 and first["allocation"]["amount_not_allocated_elsewhere"] == 600
    assert second["allocation"]["allocated_elsewhere"] is False and second["allocation"]["allocated_to_this_goal"] == 400
    assert first["amount"] == 1000 == second["amount"]                              # the reported balance is not netted or summed


def test_over_allocation_is_flagged_and_no_free_amount_is_invented():
    out = run(inputs([cash("recI", 1000)], goals=[goal_rec(G), goal_rec(G2)], allocations=[al("a1", G2, "recI", "fixed_amount", 5000)]))
    row = cats(out)["liquid_now"][0]
    assert row["allocation"]["over_allocated"] is True and row["allocation"]["amount_not_allocated_elsewhere"] is None and "over_allocated" in row["risks"]


# ── נכסים, חייבים לי, הפקדות ─────────────────────────────────────────────────────────────────────────────────────

def test_an_asset_is_conditional_with_no_estimated_proceeds_or_sale_date():
    row = cats(run(inputs(assets=[asset(mortgage_balance=300000, monthly_income=4000)])))["conditional_on_action"][0]
    assert row["source_type"] == "asset" and row["amount"] is None and row["amount_status"] == "missing"
    assert set(row["missing_inputs"]) == {"net_proceeds", "expected_sale_date"} and "available_by" not in row
    assert {"debt_overlap_unresolved", "lost_income"} <= set(row["risks"])
    assert row["option_template"] == {"type": "asset_sale", "asset_id": "recAS1"} and row["owner_must_enter"] == ["net_proceeds", "expected_date"]
    assert row["asset"]["recorded_value"] == 2000000 and row["provenance"]["time_to_sell"] == "owner_manual"


def test_a_debt_owed_to_me_is_expected_not_guaranteed_and_never_liquid():
    out = run(inputs(loans=[owed(), owed(arrangement="monthly", loan_id="recOW2"), owed(active=False, loan_id="recOW3"),
                            {**owed(loan_id="recMine"), "direction": "owed_by_me"}]))
    c = cats(out)
    assert ids(c["expected_not_guaranteed"]) == ["recOW1", "recOW2"] and not c["liquid_now"] and not c["liquid_by_due_date"]
    plain, arranged = c["expected_not_guaranteed"]
    assert plain["certainty"] == "uncertain" and "receivable_no_arrangement" in plain["risks"] and arranged["certainty"] == "expected"
    assert plain["option_template"] == {"type": "receivable_collection", "loan_id": "recOW1"}


def test_receivable_without_a_recorded_balance_is_missing():
    row = cats(run(inputs(loans=[owed(balance=None)])))["expected_not_guaranteed"][0]
    assert row["amount"] is None and "recorded_balance" in row["missing_inputs"]


def test_planned_deposits_are_separate_marked_and_not_added_to_the_balance():
    out = run(inputs([cash("recI", 1000, planned_monthly_deposit=500), acct("recNo", None, planned_monthly_deposit=300, liquidity="immediate")]))
    c = cats(out)
    dep = {r["source_id"]: r for r in c["future_deposits"]}
    slot = fp._slot(fp.af._iso_date("2030-12-31"), TODAY.replace(day=1))
    assert dep["recI"]["amount"] == 500 * slot and dep["recI"]["forecast_inclusion"] == "included_in_forecast"
    assert dep["recNo"]["forecast_inclusion"] == "not_included"
    assert c["liquid_now"][0]["amount"] == 1000                                     # the existing balance excludes the future deposits
    assert dep["recI"]["certainty"] == "expected" and dep["recI"]["option_template"] == {"type": "new_deposits", "account_id": "recI"}


def test_missing_or_zero_planned_deposit():
    out = run(inputs([cash("recA", 100), cash("recB", 100, planned_monthly_deposit=0)]))
    assert cats(out)["future_deposits"] == []
    assert [g["account_id"] for g in out["goals"][0]["gaps"]["future_deposits"]] == ["recA"]


# ── חלון תאריך, דטרמיניזם, בטיחות ───────────────────────────────────────────────────────────────────────────────

def test_date_window_recomputes_states_at_the_early_and_late_ends():
    accounts = [acct("recD", 5000, liquidity="locked_until_date", liquid_from="2030-06-01", planned_monthly_deposit=100)]
    out = run(inputs(accounts), margin=12)
    goal = out["goals"][0]
    assert goal["date_window"]["margin_months"] == 12 and goal["date_window"]["early"] == "2029-12-31" and goal["date_window"]["late"] == "2031-12-31"
    state = goal["categories"]["conditional_on_action"][0]["liquidity"]["state_at"]
    assert state["early"] == "locked" and state["due"] == "conditional" and state["late"] == "conditional"
    dep = goal["categories"]["future_deposits"][0]
    assert dep["window"]["early"]["amount"] < dep["amount"] < dep["window"]["late"]["amount"]


def test_goal_margin_field_is_used_and_no_window_without_a_margin():
    assert run(inputs([cash("recI")]))["goals"][0]["date_window"] is None
    assert run(inputs([cash("recI")], goals=[goal_rec(date_margin_months=6)]))["goals"][0]["date_window"]["margin_months"] == 6


def test_deterministic_and_inputs_are_not_mutated():
    inp = inputs([cash("recI", 1000, planned_monthly_deposit=50)], assets=[asset()], loans=[owed()], allocations=[al("a1", G, "recI", "percent", 10)])
    before = copy.deepcopy(inp)
    first = json.dumps(run(inp, margin=3), sort_keys=True, default=str)
    assert first == json.dumps(run(inp, margin=3), sort_keys=True, default=str) and inp == before


def test_unknown_goal_is_rejected_and_output_is_json_serialisable():
    with pytest.raises(ValueError, match="unknown goal"):
        run(inputs(), goal_ids=("recZZZ",))
    json.dumps(run(inputs([cash("recI")], assets=[asset()])))


def test_foreign_rows_are_not_in_the_input_so_never_in_the_output():
    out = run(inputs([cash("recMine", 1)]))
    assert ids(cats(out)["liquid_now"]) == ["recMine"]


def test_module_is_pure_and_does_not_touch_the_engine_or_funding_plan():
    text = Path("portfolio_lab/funding_sources.py").read_text(encoding="utf-8")
    for forbidden in ("airtable", "requests", "anthropic", "open(", "dispatch_tool", "simulate("):
        assert forbidden not in text, forbidden
