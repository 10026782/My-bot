"""בדיקות מסך הסימולטור: שכבת ה-view, השרת המקומי וההפרדה מהבוט. ללא רשת/אישורים/שירותים חיצוניים."""

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

from portfolio_lab import Asset, Scenario, simulate
from portfolio_lab.simulator_view import (
    CRISIS_DECLINES, STRATEGY_LABELS, build_simulator_view, crisis_asset, normalize_params,
)
from portfolio_lab.models import TaxAssessment, Source


def view(**kwargs):
    return build_simulator_view(kwargs)


def test_kpis_match_engine_exactly():
    v = view(years=20, monthly_contribution=5000, initial=10000, annual_return_pct=7, annual_fee_pct=0.2, inflation_pct=2.5)
    engine = simulate(Scenario(years=20, initial=10000, monthly_contribution=5000, inflation=0.025,
                               assets=(Asset(annual_return=0.07, annual_fee=0.002),)))["final"]
    k = v["kpis"]
    assert k["final_nominal"] == engine["value_after_costs"]
    assert k["final_real"] == engine["real_value"]
    assert k["contributions"] == engine["contributions"]
    assert k["nominal_profit"] == engine["nominal_profit"]
    assert k["real_profit"] == engine["real_profit"]
    assert k["management_fees_paid"] == engine["management_cost"]
    assert k["total_cost_impact"] == engine["cost_impact"]
    assert k["net_effective_annual_return"] == engine["nominal_annualized_twr_after_recurring_costs"]
    assert v["source"] == "portfolio_lab" and v["currency"] == "ILS"


def test_tax_not_calculated_without_model():
    k = view()["kpis"]["after_tax"]
    assert k["value"] is None and k["display"] == "לא מחושב"


def test_tax_shown_only_with_model_and_flagged_theoretical():
    src = Source("synthetic test", "2026-10-13", "test only")

    def model(ctx):
        return TaxAssessment(ctx.proceeds_before_tax * 0.1, "t", "1", {}, src, False)

    k = build_simulator_view({"years": 10}, tax_model=model)["kpis"]["after_tax"]
    assert k["value"] is not None and "תיאורטית" in k["note"]


def test_breakdown_sums_to_value_before_costs():
    b = view(years=25)["charts"]["breakdown"]
    assert b["contributions"] + b["profit_net"] + b["costs"] == pytest.approx(b["total_before_costs"])
    assert min(b.values()) >= 0


def test_comparison_table_and_baseline_gap():
    v = view(years=30, strategies=["world_em", "three_funds"], baseline="global")
    names = [r["strategy"] for r in v["comparison_table"]]
    assert names == ["global", "world_em", "three_funds"]
    base = v["comparison_table"][0]
    assert base["is_baseline"] and base["gap_vs_baseline"] == 0
    for r in v["comparison_table"][1:]:
        assert r["gap_vs_baseline"] == pytest.approx(r["final_nominal"] - base["final_nominal"])
    assert set(v["charts"]["strategy_comparison"]) == set(names)
    assert {r["label"] for r in v["comparison_table"]} <= set(STRATEGY_LABELS.values())


def test_sensitivity_monotonic_and_includes_base():
    v = view(years=30, monthly_contribution=6000)
    c = v["charts"]["sensitivity"]["monthly_contribution"]
    assert [r["final_nominal"] for r in c] == sorted(r["final_nominal"] for r in c)
    assert any(r["factor"] == 1.0 and r["final_nominal"] == v["kpis"]["final_nominal"] for r in c)
    d = v["charts"]["sensitivity"]["duration"]
    assert [r["years"] for r in d] == sorted(r["years"] for r in d)
    assert any(r["years"] == 30 and r["final_nominal"] == v["kpis"]["final_nominal"] for r in d)


@pytest.mark.parametrize("decline", CRISIS_DECLINES)
@pytest.mark.parametrize("recovery", ["fast", "prolonged"])
def test_crisis_returns_to_trend_path(decline, recovery):
    asset = Asset(annual_return=0.08, annual_fee=0)
    n = 1 if recovery == "fast" else 3
    shocked = crisis_asset(asset, decline / 100, 5, n, 30)
    path = shocked.annual_return
    assert path[4] == pytest.approx(-decline / 100)
    factor = (1 - decline / 100)
    for i in range(5, 5 + n):
        factor *= 1 + path[i]
    assert factor == pytest.approx(1.08 ** (n + 1))
    assert path[:4] == (0.08,) * 4 and path[5 + n:] == (0.08,) * (30 - 5 - n)


def test_crisis_block_and_truncation():
    v = view(years=10, crisis={"decline_pct": 50, "year": 10, "recovery": "prolonged"})
    c = v["charts"]["growth"]["crisis"]
    assert c["applied"] and c["recovery_truncated_by_horizon"]
    assert c["final_nominal"] < v["kpis"]["final_nominal"]
    assert "applied" in view()["charts"]["growth"]["crisis"] and not view()["charts"]["growth"]["crisis"]["applied"]


def test_insights_count_and_no_recommendations():
    insights = view()["insights"]
    assert 3 <= len(insights) <= 5
    text = " ".join(i["text"] for i in insights)
    for forbidden in ("מומלץ", "כדאי לקנות", "מכור", "קנה "):
        assert forbidden not in text
    assert {"contribution", "fees", "crisis_timing"} <= {i["topic"] for i in insights}


def test_assumptions_and_warnings_exposed():
    v = view(crisis={"decline_pct": 20, "year": 3, "recovery": "fast"})
    ids = {a["id"] for a in v["assumptions"]}
    assert {"return", "fee", "inflation", "tax", "components", "crisis"} <= ids
    assert all(a["assumption_based"] for a in v["assumptions"] if a["id"] in {"return", "tax", "components"})
    assert v["result_type"] == "assumption_based_projection" and v["warnings"]


def test_deterministic_and_no_input_mutation():
    params = {"years": 15, "strategies": ["global", "world_em"]}
    snapshot = json.dumps(params, sort_keys=True)
    assert json.dumps(build_simulator_view(params), sort_keys=True) == json.dumps(build_simulator_view(params), sort_keys=True)
    assert json.dumps(params, sort_keys=True) == snapshot
    json.dumps(build_simulator_view(params), allow_nan=False)


@pytest.mark.parametrize("bad", [
    {"years": 5}, {"years": 101}, {"years": "30"}, {"years": True}, {"monthly_contribution": -1},
    {"annual_return_pct": float("nan")}, {"annual_return_pct": -100}, {"annual_fee_pct": -0.1},
    {"deposit_timing": "mid"}, {"index_contributions": "yes"}, {"strategies": []}, {"strategies": ["nope"]},
    {"baseline": "nope"}, {"surprise": 1}, {"crisis": {"decline_pct": 15, "year": 3, "recovery": "fast"}},
    {"crisis": {"decline_pct": 20, "year": 99, "recovery": "fast"}}, {"crisis": {"decline_pct": 20, "year": 3, "recovery": "slow"}},
    {"component_returns_pct": {"bitcoin": 5}}, "not-an-object",
])
def test_invalid_input_rejected(bad):
    with pytest.raises(ValueError):
        build_simulator_view(bad)


def test_index_and_timing_flow_through():
    a = view(years=20, index_contributions=True, deposit_timing="begin")
    b = view(years=20)
    assert a["kpis"]["contributions"] > b["kpis"]["contributions"]
    assert a["inputs"]["deposit_timing"] == "begin"
    assert normalize_params({})["strategies"][0] == "global"


@pytest.fixture(scope="module")
def server():
    from portfolio_lab.ui import make_server
    srv = make_server(0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _post(base, body, raw=False):
    data = body if raw else json.dumps(body).encode()
    req = urllib.request.Request(base + "/api/simulate", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_server_serves_page_and_binds_loopback(server):
    assert server.startswith("http://127.0.0.1:")
    with urllib.request.urlopen(server + "/") as r:
        html = r.read().decode()
    assert r.status == 200 and 'dir="rtl"' in html and "/api/simulate" in html
    # אין משאבי רשת חיצוניים (מרחב השמות של SVG אינו משאב)
    assert "https://" not in html and "http://" not in html.replace("http://www.w3.org/2000/svg", "")
    assert "src=" not in html and "<link" not in html


def test_server_simulate_ok_and_errors(server):
    status, body = _post(server, {"years": 12})
    assert status == 200 and body["kpis"]["final_nominal"] > 0
    assert _post(server, {"years": 3})[0] == 400
    assert _post(server, b"{not json", raw=True)[0] == 400
    assert _post(server, b"x" * 70000, raw=True)[0] == 413
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(server + "/nope")
    assert e.value.code == 404


def test_isolated_from_bot_and_external_services():
    code = ("import sys; import portfolio_lab.simulator_view, portfolio_lab.ui; "
            "bad=[m for m in sys.modules if m.split('.')[0] in {'flask','app','airtable','anthropic','numpy','tools','requests','httpx'}]; "
            "sys.exit(1 if bad else 0)")
    assert subprocess.run([sys.executable, "-S", "-c", code]).returncode == 0
