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
    assert min(b["contributions"], b["profit_net"], b["costs"]) >= 0
    assert sum(b["shares"].values()) == pytest.approx(1)


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


def _post(base, body, raw=False, headers=None):
    data = body if raw else json.dumps(body).encode()
    req = urllib.request.Request(base + "/api/simulate", data=data, headers={"Content-Type": "application/json", **(headers or {})})
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
    assert 'style="' not in html  # CSP בלי unsafe-inline חוסם מאפייני style


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


def _raw(server, method, path, headers=None, body=None):
    import http.client
    host, port = server.replace("http://", "").split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    for k, v in (headers or {}).items():
        conn.putheader(k, v)
    conn.endheaders(body)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, dict(r.getheaders()), data


def test_server_rejects_foreign_host_origin_and_content_type(server):
    port = server.rsplit(":", 1)[1]
    ok = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json", "Content-Length": "2"}
    assert _raw(server, "GET", "/", {"Host": "evil.example"})[0] == 403          # DNS rebinding
    assert _raw(server, "GET", "/", {"Host": f"127.0.0.1:{port}"})[0] == 200
    assert _raw(server, "POST", "/api/simulate", {**ok, "Origin": "http://evil.example"}, b"{}")[0] == 403
    assert _raw(server, "POST", "/api/simulate", {**ok, "Content-Type": "text/plain"}, b"{}")[0] == 415
    assert _raw(server, "POST", "/api/simulate", {k: v for k, v in ok.items() if k != "Content-Length"})[0] == 411
    assert _raw(server, "POST", "/api/simulate", {**ok, "Content-Length": "-5"})[0] == 413
    assert _raw(server, "POST", "/api/simulate", {**ok, "Origin": f"http://127.0.0.1:{port}"}, b"{}")[0] == 200


def test_security_headers_and_nonce_csp(server):
    port = server.rsplit(":", 1)[1]
    status, headers, body = _raw(server, "GET", "/?x=1", {"Host": f"127.0.0.1:{port}"})
    assert status == 200
    h = {k.lower(): v for k, v in headers.items()}
    csp = h["content-security-policy"]
    assert "default-src 'none'" in csp and "unsafe-inline" not in csp and "unsafe-eval" not in csp
    nonce = csp.split("script-src 'nonce-")[1].split("'")[0]
    assert f'<script nonce="{nonce}">'.encode() in body and b"__NONCE__" not in body
    assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff" and h["cache-control"] == "no-store"
    # nonce חדש בכל בקשה
    n2 = {k.lower(): v for k, v in _raw(server, "GET", "/", {"Host": f"127.0.0.1:{port}"})[1].items()}["content-security-policy"]
    assert n2 != csp


@pytest.mark.parametrize("payload", [
    {"strategies": [[1]]}, {"baseline": ["x"]}, {"crisis": {"decline_pct": [], "year": 1, "recovery": "fast"}},
    {"initial": 10 ** 400}, {"initial": 1e300, "monthly_contribution": 1e300}, {"years": 100, "annual_return_pct": 50, "initial": 1e200},
    {"component_returns_pct": {"europe": "x"}}, {"strategies": ["global"] * 5000}, [], None, 5, "x",
])
def test_hostile_payloads_never_500_or_leak(server, payload):
    status, body = _post(server, payload)
    assert status in (200, 400)
    assert "Traceback" not in json.dumps(body) and "File \"" not in json.dumps(body)


def test_server_refuses_production_and_non_loopback():
    from portfolio_lab import ui
    assert ui.production_reason({}) is None
    assert "RENDER" in ui.production_reason({"RENDER": "true"})
    assert "ENV" in ui.production_reason({"ENV": "production"})
    with pytest.raises(SystemExit):
        old = dict(__import__("os").environ)
        __import__("os").environ["RENDER"] = "1"
        try:
            ui.main(["--port", "0"])
        finally:
            __import__("os").environ.clear(); __import__("os").environ.update(old)
    srv = ui.make_server(0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()
    for bad in (-1, 70000, "80"):
        with pytest.raises(ValueError):
            ui.make_server(bad)
    assert "--host" not in subprocess.run([sys.executable, "-m", "portfolio_lab.ui", "--help"], capture_output=True, text=True).stdout


def test_not_wired_into_deployed_runtime():
    from pathlib import Path
    for name in ("app.py", "tma_api.py", "gunicorn.conf.py", "Dockerfile", "docker-compose.oracle.yml", "Caddyfile.oracle", "scheduler.py"):
        path = Path(name)
        if path.exists():
            assert "portfolio_lab" not in path.read_text(encoding="utf-8"), name


def test_charts_numbers_and_table_are_mutually_consistent():
    v = view(years=25, monthly_contribution=7000, initial=20000, strategies=["world_em", "three_funds", "experimental_90_10"],
             crisis={"decline_pct": 30, "year": 4, "recovery": "fast"})
    k, ch = v["kpis"], v["charts"]
    last = ch["growth"]["series"][-1]
    assert (last["year"], last["nominal"], last["real"], last["contributions"]) == (25, k["final_nominal"], k["final_real"], k["contributions"])
    assert ch["strategy_comparison"][v["primary_strategy"]["id"]][-1]["nominal"] == k["final_nominal"]
    for row in v["comparison_table"]:
        s = ch["strategy_comparison"][row["strategy"]][-1]
        assert (s["nominal"], s["real"], s["contributions"]) == (row["final_nominal"], row["final_real"], row["contributions"])
        assert row["net_profit"] == pytest.approx(row["final_nominal"] - row["contributions"])
        # הגרף והשרת מייצרים אותה תוצאה כמו המנוע ישירות
    assert ch["growth"]["crisis"]["series"][-1]["nominal"] == ch["growth"]["crisis"]["final_nominal"]
    assert ch["growth"]["crisis"]["delta_vs_no_crisis"] == pytest.approx(ch["growth"]["crisis"]["final_nominal"] - k["final_nominal"])
    assert ch["growth"]["crisis"]["series"][2] == ch["growth"]["series"][2]  # זהים עד שנת המשבר
    assert ch["growth"]["crisis"]["series"][3]["nominal"] < ch["growth"]["series"][3]["nominal"]
    assert ch["breakdown"]["profit_net"] == pytest.approx(k["nominal_profit"])
    assert ch["breakdown"]["costs"] == pytest.approx(k["total_cost_impact"])
    assert [r["nominal"] for r in ch["growth"]["series"]] == sorted(r["nominal"] for r in ch["growth"]["series"])


def test_strategy_values_independent_of_selection_and_match_engine():
    from portfolio_lab import compare, strategy_assets
    from portfolio_lab.simulator_view import _assumptions, normalize_params
    full = view(years=30)
    subset = view(years=30, strategies=["three_funds"], baseline="global")
    f = {r["strategy"]: r for r in full["comparison_table"]}
    for r in subset["comparison_table"]:
        assert r["final_nominal"] == f[r["strategy"]]["final_nominal"]
    p = normalize_params({"years": 30})
    engine = compare({"world_em": Scenario(years=30, assets=strategy_assets("world_em", _assumptions(p)))})
    assert f["world_em"]["final_nominal"] == engine["strategies"]["world_em"]["final"]["value_after_costs"]


def test_demo_labelling_and_no_parallel_js_engine():
    from pathlib import Path
    html = Path("portfolio_lab/ui_page.html").read_text(encoding="utf-8")
    script = html.split("<script", 1)[1]
    assert "DEMO" in html and "assumption-based" in html and "הדגמה" in html
    # ב-JS אין חישוב פיננסי: אין חזקות/ריבית דריבית/סכימת סדרות; רק עיצוב, סקאלה לצירים ושרטוט
    for needle in ("Math.pow", "**", "reduce(", "1+r", "(1+", "/12", "*12", "annuity", "compound"):
        assert needle not in script, needle
    assert script.count("fetch(") == 1 and "/api/simulate" in script
