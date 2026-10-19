"""בדיקות משבר תוך-שנתי (Portfolio Lab, נתיב 1ב): מנוע (monthly_returns) ושכבת ה-view. ללא רשת/שירותים חיצוניים."""

import pytest

from portfolio_lab import Asset, Scenario, simulate
from portfolio_lab.simulator_view import _scenario, _with_crisis, build_simulator_view, crisis_asset_monthly, normalize_params

BASE = {"years": 20, "strategies": ["global"]}


def _crisis(month=None, decline=30, year=5, recovery="fast"):
    c = {"decline_pct": decline, "year": year, "recovery": recovery}
    if month is not None:
        c["month"] = month
    return c


def _view(**kw):
    return build_simulator_view({**BASE, **kw})


def _final(params, crisis):
    p = normalize_params({**BASE, **params, "crisis": crisis})
    return simulate(_with_crisis(_scenario(p, "global"), p["crisis"]))["final"]


# ── מנוע ──
def test_engine_empty_monthly_returns_leaves_result_and_digest_unchanged():
    plain = simulate(Scenario(years=10, assets=(Asset(annual_return=0.07),)))
    same = simulate(Scenario(years=10, assets=(Asset(annual_return=0.07, monthly_returns=()),)))
    assert plain["replay_digest"] == same["replay_digest"] and "monthly_returns" not in str(plain["inputs"])


def test_engine_override_replaces_exactly_one_month_zero_fee_oracle():
    # הון התחלתי בלבד, ללא הפקדות ודמי ניהול: ההון = f^11 · (1-d), כש-f גורם המגמה החודשי
    r, d = 0.08, 0.3
    f = (1 + r) ** (1 / 12)
    scenario = Scenario(years=10, initial=1000.0, monthly_contribution=0.0, inflation=0.0,
                        assets=(Asset(annual_return=r, annual_fee=0.0, monthly_returns=((5, -d),)),))
    final = simulate(scenario)["final"]["value_after_costs"]
    assert final == pytest.approx(1000.0 * f ** 119 * (1 - d))


@pytest.mark.parametrize("bad", [((-1, -0.1),), ((120, -0.1),), ((1, -1.0),), ((1, -0.1), (1, -0.2)), ((True, -0.1),), "x"])
def test_engine_rejects_invalid_monthly_returns(bad):
    with pytest.raises(ValueError):
        Scenario(years=10, assets=(Asset(monthly_returns=bad),))


# ── חזרה לנתיב המגמה ──
@pytest.mark.parametrize("recovery,n", [("fast", 1), ("prolonged", 3)])
@pytest.mark.parametrize("month", [1, 6, 12])
def test_recovery_returns_to_trend_path(recovery, n, month):
    d, r = 0.3, 0.08
    f = (1 + r) ** (1 / 12)
    asset = crisis_asset_monthly(Asset(annual_return=r, annual_fee=0), d, 5, month, n, 30)
    start = 4 * 12 + month - 1
    rates = dict(asset.monthly_returns)
    wealth = 1.0
    for k in range(start, start + 12 * n + 1):
        wealth *= 1 + rates[k]
    assert wealth == pytest.approx(f ** (12 * n + 1))
    assert rates[start] == -d and min(rates) == start and max(rates) == start + 12 * n


# ── קצה: תחילת/אמצע/סוף שנה, אופק קצר, חריגה מהאופק ──
@pytest.mark.parametrize("month", [1, 6, 12])
def test_start_mid_end_of_year_run_and_are_ordered_by_deposit_timing(month):
    v = _view(crisis=_crisis(month))
    c = v["charts"]["growth"]["crisis"]
    assert c["applied"] and c["settings"]["month"] == month
    assert c["intra_year"]["month"] == month and len(c["intra_year"]["timing_by_month"]) == 12
    assert [r["month"] for r in c["intra_year"]["timing_by_month"]] == list(range(1, 13))
    assert [r["is_selected"] for r in c["intra_year"]["timing_by_month"]].count(True) == 1


def test_timing_table_row_for_selected_month_equals_headline_result():
    c = _view(crisis=_crisis(9))["charts"]["growth"]["crisis"]
    row = next(r for r in c["intra_year"]["timing_by_month"] if r["is_selected"])
    assert row["final_nominal"] == c["final_nominal"] and row["delta_vs_no_crisis"] == c["delta_vs_no_crisis"]


def test_timing_changes_the_result_not_only_depth():
    rows = _view(crisis=_crisis(6))["charts"]["growth"]["crisis"]["intra_year"]["timing_by_month"]
    assert len({round(r["final_nominal"]) for r in rows}) > 1


def test_deposit_order_end_vs_begin():
    end = _view(crisis=_crisis(3), deposit_timing="end")["charts"]["growth"]["crisis"]["intra_year"]
    begin = _view(crisis=_crisis(3), deposit_timing="begin")["charts"]["growth"]["crisis"]["intra_year"]
    assert "אחרי הירידה" in end["deposit_order_note"] and "לפני הירידה" in begin["deposit_order_note"]
    assert _final({"deposit_timing": "end"}, _crisis(3))["value_after_costs"] != _final({"deposit_timing": "begin"}, _crisis(3))["value_after_costs"]


def test_short_horizon_crisis_in_last_month_is_truncated_and_valid():
    v = _view(years=10, crisis=_crisis(12, decline=50, year=10, recovery="prolonged"))
    c = v["charts"]["growth"]["crisis"]
    assert c["recovery_truncated_by_horizon"] and c["intra_year"]["recovery_truncated_by_horizon"]
    assert c["final_nominal"] < v["kpis"]["final_nominal"]
    path = c["intra_year"]["monthly_path"]
    assert path[-1]["month_index"] == 10 * 12 - 1 and path[0]["month_index"] == 9 * 12 + 11 - 12


def test_recovery_beyond_horizon_flag_off_when_it_fits():
    c = _view(years=20, crisis=_crisis(1, year=2, recovery="fast"))["charts"]["growth"]["crisis"]
    assert not c["recovery_truncated_by_horizon"]


def test_monthly_path_window_and_consistency():
    c = _view(crisis=_crisis(6, year=5, recovery="fast"))["charts"]["growth"]["crisis"]
    path = c["intra_year"]["monthly_path"]
    start = 4 * 12 + 5
    assert path[0]["month_index"] == start - 12 and path[-1]["month_index"] == start + 12 + 12
    before = [r for r in path if r["month_index"] < start]
    assert all(r["nominal_crisis"] == r["nominal_no_crisis"] for r in before)
    at = next(r for r in path if r["month_index"] == start)
    assert at["nominal_crisis"] < at["nominal_no_crisis"]
    assert all(r["t_years"] == (r["month_index"] + 1) / 12 for r in path)


# ── תאימות לאחור ושער קלט ──
def test_annual_crisis_unchanged_without_month():
    c = _view(crisis=_crisis())["charts"]["growth"]["crisis"]
    assert "intra_year" not in c and "month" not in c["settings"]


@pytest.mark.parametrize("month", [0, 13, -1, 1.5, "3", True])
def test_invalid_month_rejected(month):
    with pytest.raises(ValueError):
        build_simulator_view({**BASE, "crisis": {**_crisis(), "month": month}})


def test_deterministic_and_no_probability_fields():
    a = _view(crisis=_crisis(4)); b = _view(crisis=_crisis(4))
    assert a == b and "probab" not in str(a["charts"]).lower() and "success" not in str(a["charts"]).lower()
    assert not any("intra-year crash timing is not modelled" in w for w in a["warnings"])


# ── שילוב עם #1341: crisis.by_strategy מכבד את crisis.month ──
def test_by_strategy_honors_the_selected_month_and_matches_independent_engine_runs():
    params = {"years": 20, "crisis": _crisis(7)}
    rows = build_simulator_view(params)["charts"]["growth"]["crisis"]["by_strategy"]
    assert [r["strategy"] for r in rows][0] == "global" and len(rows) == 4
    p = normalize_params(params)
    for r in rows:
        shocked = simulate(_with_crisis(_scenario(p, r["strategy"]), p["crisis"]))["final"]
        assert r["final_nominal"] == shocked["value_after_costs"] and r["final_real"] == shocked["real_value"]
    annual = build_simulator_view({"years": 20, "crisis": _crisis()})["charts"]["growth"]["crisis"]["by_strategy"]
    assert [round(r["final_nominal"]) for r in rows] != [round(r["final_nominal"]) for r in annual]       # חודש 7 ≠ מסלול שנתי
    head = build_simulator_view(params)["charts"]["growth"]["crisis"]
    assert rows[0]["final_nominal"] == head["final_nominal"] and rows[0]["gap_vs_baseline"] == 0.0


def test_by_strategy_month_changes_with_the_month_not_only_the_depth():
    def final(month):
        rows = build_simulator_view({"years": 20, "crisis": _crisis(month)})["charts"]["growth"]["crisis"]["by_strategy"]
        return {r["strategy"]: r["final_nominal"] for r in rows}
    jan, dec = final(1), final(12)
    assert all(jan[k] != dec[k] for k in jan)


def test_intra_year_crisis_rejects_a_per_year_return_path():
    with pytest.raises(ValueError):
        crisis_asset_monthly(Asset(annual_return=(0.05, 0.06) * 5), 0.3, 2, 6, 1, 10)


def test_existing_scenario_digest_unchanged_from_main():
    # ערך שנמדד על origin/main (a2c0b8bf) לפני הוספת Asset.monthly_returns
    assert build_simulator_view({})["replay_digest"] == "a993cee736cb0cc3342f105ae7266cd175ff13ba9a03b3546fb25ed5a33b53c4"
    crisis = build_simulator_view({"years": 20, "crisis": _crisis()})
    assert crisis["replay_digest"] == "98cae07130c512ee4eedeec30ba89883659263a315a30d685c2cf4138f788209"


# ── שילוב עם C3 (#1345): compare_to לא מתנגש עם crisis.month ──
def test_compare_to_and_crisis_month_coexist_and_the_comparison_ignores_the_crisis():
    both = build_simulator_view({**BASE, "crisis": _crisis(8), "compare_to": {"annual_return_pct": 6}})
    only_compare = build_simulator_view({**BASE, "compare_to": {"annual_return_pct": 6}})
    assert both["charts"]["scenario_comparison"] == only_compare["charts"]["scenario_comparison"]
    assert both["charts"]["growth"]["crisis"]["intra_year"]["month"] == 8 and both["charts"]["growth"]["crisis"]["by_strategy"]
    assert both["inputs"]["crisis"]["month"] == 8 and "compare" not in both["inputs"]
    with pytest.raises(ValueError):
        build_simulator_view({**BASE, "crisis": _crisis(13), "compare_to": {"annual_return_pct": 6}})
