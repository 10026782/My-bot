"""POST /api/portfolio-lab/simulate: gate (FCC flag+canary AND owner), limits, errors, read-only. No network/Airtable/LLM."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

import tma_api
from portfolio_lab import Asset, Scenario, simulate

H = {"X-Telegram-Init-Data": "valid"}
URL = "/api/portfolio-lab/simulate"
OWNER = SimpleNamespace(user_id="eliyahu", is_owner=True)
PARTNER = SimpleNamespace(user_id="avi", is_owner=False)


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(tma_api, "_PL_LIMITER", None)


def client(monkeypatch, who=OWNER, gate=True, valid_init=True):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", (lambda _: {"id": getattr(who, "user_id", "x")}) if valid_init else (lambda _: None))
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: gate)
    return app.test_client()


def post(c, body, headers=H, ctype="application/json"):
    data = body if isinstance(body, (bytes, str)) else json.dumps(body)
    return c.post(URL, data=data, headers=headers, content_type=ctype)


def test_requires_valid_telegram_auth(monkeypatch):
    assert post(client(monkeypatch), {}, headers={}).status_code == 401
    assert post(client(monkeypatch, valid_init=False), {}).status_code == 401


def test_gate_flag_canary_and_owner(monkeypatch):
    assert post(client(monkeypatch, gate=False), {}).status_code == 404            # flag/canary off
    assert post(client(monkeypatch, who=PARTNER, gate=True), {}).status_code == 404  # canary ok but not owner
    assert post(client(monkeypatch, who=None, gate=True), {}).status_code == 404     # unresolved identity
    assert post(client(monkeypatch), {}).status_code == 200


def test_real_fcc_gate_is_used_not_a_copy(monkeypatch):
    import feature_flags
    monkeypatch.setattr(feature_flags, "is_enabled", lambda n, *a, **k: n == "FEATURE_FINANCIAL_CONTROL_CENTER")
    monkeypatch.setenv("FCC_CANARY_USER_IDS", "eliyahu")
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": "x"})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: OWNER)
    assert post(app.test_client(), {}).status_code == 200
    monkeypatch.delenv("FCC_CANARY_USER_IDS")
    assert post(app.test_client(), {}).status_code == 404                           # flag alone exposes nothing


def test_only_post_and_preflight(monkeypatch):
    c = client(monkeypatch)
    assert c.get(URL, headers=H).status_code == 405
    assert c.open(URL, method="OPTIONS").status_code == 204


def test_numbers_come_from_the_engine(monkeypatch):
    body = post(client(monkeypatch), {"years": 20, "monthly_contribution": 5000, "annual_return_pct": 7, "annual_fee_pct": 0.2,
                                      "inflation_pct": 2.5, "initial": 10000}).get_json()
    engine = simulate(Scenario(years=20, initial=10000, monthly_contribution=5000, inflation=0.025,
                               assets=(Asset(annual_return=0.07, annual_fee=0.002),)))["final"]
    assert body["source"] == "portfolio_lab"
    assert body["kpis"]["final_nominal"] == engine["value_after_costs"]
    assert body["kpis"]["after_tax"]["display"] == "לא מחושב"


def test_limits_and_errors(monkeypatch):
    c = client(monkeypatch)
    assert post(c, {}, ctype="text/plain").status_code == 415
    assert post(c, b"x" * (64 * 1024 + 1)).status_code == 413
    assert post(c, b"").status_code in (411, 413)                                     # empty body
    assert post(c, b"{not json").status_code == 400
    assert post(c, {"years": 3}).status_code == 400
    assert post(c, {"surprise": 1}).status_code == 400
    r = post(c, [])
    assert r.status_code == 400 and "Traceback" not in r.get_data(as_text=True)


@pytest.mark.parametrize("payload", [
    {"strategies": [[1]]}, {"baseline": ["x"]}, {"initial": 10 ** 400}, {"initial": 1e300, "monthly_contribution": 1e300},
    {"years": 100, "annual_return_pct": 50, "initial": 1e200}, {"strategies": ["global"] * 5000}, None, 5, "x",
])
def test_hostile_payloads_never_500(monkeypatch, payload):
    r = post(client(monkeypatch), payload)
    assert r.status_code in (200, 400)
    assert "Traceback" not in r.get_data(as_text=True)


def test_unexpected_exception_is_generic_500(monkeypatch):
    import portfolio_lab.simulator_view as sv
    monkeypatch.setattr(sv, "build_simulator_view", lambda p: (_ for _ in ()).throw(RuntimeError("secret internals")))
    r = post(client(monkeypatch), {})
    assert r.status_code == 500 and r.get_json() == {"error": "internal error"}


def test_rate_limit_per_user(monkeypatch):
    c = client(monkeypatch)
    codes = [post(c, {"years": 10}).status_code for _ in range(14)]
    assert codes[:12] == [200] * 12 and codes[12:] == [429, 429]


def test_concurrency_gate_returns_503_when_busy(monkeypatch):
    class Busy:
        def acquire(self, timeout=None): return False
        def release(self): raise AssertionError("must not release an unacquired slot")
    monkeypatch.setattr(tma_api, "_PL_COMPUTE", Busy())
    assert post(client(monkeypatch), {}).status_code == 503


def test_read_only_and_only_the_pure_view_is_imported():
    text = Path("tma_api.py").read_text(encoding="utf-8")
    imports = re.findall(r"^\s*(?:from|import)\s+(portfolio_lab[\w.]*)", text, re.M)
    # the pure edges, nothing else: the simulator view, (D1 step 7 / A1) the pure per-account forecast assembly and
    # (Goal Funding Planner step 1) the pure funding-option comparison — each reached only by an owner-gated read-only endpoint
    # and (funding sources step 1) the pure per-goal candidate list, attached to the same funding endpoint
    # (a module may be imported in several routes — the guard is about WHICH modules, hence set())
    assert sorted(set(imports)) == ["portfolio_lab.accounts_forecast", "portfolio_lab.funding_plan", "portfolio_lab.funding_sources",
                               "portfolio_lab.pace_tracker", "portfolio_lab.simulator_view"]
    assert "portfolio_lab.ui" not in text                                            # the local server is never served from here
    block = text.split("# Portfolio Lab", 1)[1]
    for forbidden in ("airtable", "_queue_or_owner_execute", "dispatch_tool", "call_anthropic", "filter_records", "_gw_create", "_gw_patch"):
        assert forbidden not in block, forbidden
