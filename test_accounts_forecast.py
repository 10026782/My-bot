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
