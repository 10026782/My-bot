"""בדיקות משבר על כל האסטרטגיות בהשוואה (Portfolio Lab, נתיב 1א). ללא רשת/אישורים/שירותים חיצוניים."""

import pytest

from portfolio_lab import simulate
from portfolio_lab.simulator_view import (
    STRATEGY_LABELS, _assumptions, _scenario, _with_crisis, build_simulator_view, normalize_params,
)

CRISIS = {"decline_pct": 30, "year": 5, "recovery": "fast"}


def _view(**kwargs):
    return build_simulator_view({"years": 20, **kwargs})


def test_no_crisis_has_no_by_strategy():
    c = _view()["charts"]["growth"]["crisis"]
    assert c == {"applied": False}


def test_by_strategy_covers_all_compared_strategies_in_order():
    v = _view(crisis=CRISIS, strategies=["world_em", "three_funds", "global"], baseline="three_funds")
    rows = v["charts"]["growth"]["crisis"]["by_strategy"]
    assert [r["strategy"] for r in rows] == ["three_funds", "world_em", "global"]
    assert [r["is_baseline"] for r in rows] == [True, False, False]
    assert all(r["label"] == STRATEGY_LABELS[r["strategy"]] for r in rows)


@pytest.mark.parametrize("strategy", list(STRATEGY_LABELS))
def test_each_row_matches_independent_engine_run(strategy):
    p = normalize_params({"years": 20, "crisis": CRISIS})
    shocked = simulate(_with_crisis(_scenario(p, strategy), p["crisis"]))["final"]
    plain = simulate(_scenario(p, strategy))["final"]
    row = next(r for r in _view(crisis=CRISIS)["charts"]["growth"]["crisis"]["by_strategy"] if r["strategy"] == strategy)
    assert row["final_nominal"] == shocked["value_after_costs"]
    assert row["final_real"] == shocked["real_value"]
    assert row["final_nominal_no_crisis"] == plain["value_after_costs"]
    assert row["delta_vs_no_crisis"] == pytest.approx(shocked["value_after_costs"] - plain["value_after_costs"])


def test_primary_row_equals_existing_primary_crisis_block():
    c = _view(crisis=CRISIS)["charts"]["growth"]["crisis"]
    base = c["by_strategy"][0]
    assert base["final_nominal"] == c["final_nominal"] and base["delta_vs_no_crisis"] == c["delta_vs_no_crisis"]
    assert base["gap_vs_baseline"] == 0.0


def test_gap_is_difference_to_baseline_under_crisis():
    rows = _view(crisis=CRISIS)["charts"]["growth"]["crisis"]["by_strategy"]
    for r in rows:
        assert r["gap_vs_baseline"] == pytest.approx(r["final_nominal"] - rows[0]["final_nominal"])


def test_single_strategy_and_deterministic():
    one = _view(crisis=CRISIS, strategies=["global"])
    assert len(one["charts"]["growth"]["crisis"]["by_strategy"]) == 1
    assert _view(crisis=CRISIS) == _view(crisis=CRISIS)


def test_assumptions_unaffected_by_crisis_helper():
    p = normalize_params({"crisis": CRISIS})
    assert "global_accumulating" in _assumptions(p)
