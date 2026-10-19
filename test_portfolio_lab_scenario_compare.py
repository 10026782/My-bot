"""בדיקות השוואת תרחישים C3 (Portfolio Lab, נתיב 1ג): שני סטי הנחות ופער ביניהם. ללא רשת/שירותים חיצוניים."""

import pytest

from portfolio_lab import Asset, Scenario, simulate
from portfolio_lab.simulator_view import build_simulator_view

BASE = {"years": 20, "strategies": ["global"]}


def _cmp(**compare_to):
    return build_simulator_view({**BASE, "compare_to": compare_to})["charts"]["scenario_comparison"]


def _engine(**kw):
    values = {"years": 20, "initial": 0.0, "monthly_contribution": 8000.0, "inflation": 0.02, "return": 0.08, "fee": 0.0015}
    values.update(kw)
    scenario = Scenario(years=values["years"], initial=values["initial"], monthly_contribution=values["monthly_contribution"],
                        inflation=values["inflation"], assets=(Asset(annual_return=values["return"], annual_fee=values["fee"]),))
    return simulate(scenario)["final"]


def test_not_applied_without_compare_to():
    assert build_simulator_view(BASE)["charts"]["scenario_comparison"] == {"applied": False}


def test_both_sets_match_independent_engine_runs():
    c = _cmp(annual_return_pct=6, monthly_contribution=9000)
    a = _engine(**{"fee": 0.0015})
    b = _engine(**{"return": 0.06, "monthly_contribution": 9000.0})
    assert c["a"]["kpis"]["final_nominal"] == a["value_after_costs"]
    assert c["b"]["kpis"]["final_nominal"] == b["value_after_costs"]
    assert c["b"]["kpis"]["final_real"] == b["real_value"]


def test_gaps_are_b_minus_a_and_series_aligned():
    c = _cmp(annual_fee_pct=1.0)
    g = c["gaps_b_minus_a"]
    assert g["final_nominal"] == pytest.approx(c["b"]["kpis"]["final_nominal"] - c["a"]["kpis"]["final_nominal"])
    assert g["final_nominal"] < 0 and g["management_fees_paid"] > 0
    assert len(g["series"]) == 20 == len(c["a"]["series"]) == len(c["b"]["series"])
    assert g["series"][-1]["nominal"] == pytest.approx(g["final_nominal"])


def test_set_a_equals_main_result_and_changed_fields_listed():
    v = build_simulator_view({**BASE, "compare_to": {"inflation_pct": 4, "annual_return_pct": 8}})
    c = v["charts"]["scenario_comparison"]
    assert c["a"]["kpis"]["final_nominal"] == v["kpis"]["final_nominal"]
    assert [f["field"] for f in c["changed_fields"]] == ["inflation_pct"]    # תשואה זהה לסט א' — לא נחשבת שינוי
    assert c["changed_fields"][0]["a"] == 2.0 and c["changed_fields"][0]["b"] == 4.0


def test_timing_and_indexing_overrides():
    c = _cmp(deposit_timing="begin", index_contributions=True)
    assert {f["field"] for f in c["changed_fields"]} == {"deposit_timing", "index_contributions"}
    assert c["gaps_b_minus_a"]["contributions"] > 0


def test_crisis_does_not_apply_to_comparison_and_main_result_unchanged():
    crisis = {"decline_pct": 30, "year": 5, "recovery": "fast"}
    plain = build_simulator_view({**BASE, "compare_to": {"annual_return_pct": 6}})
    shocked = build_simulator_view({**BASE, "crisis": crisis, "compare_to": {"annual_return_pct": 6}})
    assert shocked["charts"]["scenario_comparison"] == plain["charts"]["scenario_comparison"]
    assert shocked["charts"]["growth"]["crisis"]["applied"]


@pytest.mark.parametrize("bad", [
    {}, [], "x", {"years": 30}, {"strategies": ["global"]}, {"crisis": None}, {"surprise": 1},
    {"annual_return_pct": 8}, {"annual_return_pct": 999}, {"annual_fee_pct": -1}, {"deposit_timing": "mid"},
    {"index_contributions": "yes"}, {"monthly_contribution": True}, {"monthly_contribution": float("nan")},
])
def test_invalid_compare_to_rejected(bad):
    with pytest.raises(ValueError):
        build_simulator_view({**BASE, "compare_to": bad})


def test_deterministic_neutral_no_probabilities_or_ranking():
    a = _cmp(annual_return_pct=5)
    assert a == _cmp(annual_return_pct=5)
    text = str(a).lower()
    assert "probab" not in text and "rank" not in text and "best" not in text and "recommend" not in text.replace("המלצה", "")
    assert "אינו ציון" in a["note"]


def test_existing_output_unchanged_other_than_new_key():
    plain = build_simulator_view(BASE)
    with_cmp = build_simulator_view({**BASE, "compare_to": {"annual_return_pct": 6}})
    for key in ("kpis", "comparison_table", "insights", "assumptions", "replay_digest"):
        assert plain[key] == with_cmp[key]
    assert "compare" not in with_cmp["inputs"]
