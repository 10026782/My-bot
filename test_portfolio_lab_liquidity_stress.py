"""בדיקות E1a (מבחן לחץ נזילות, כרית בלבד): parity מול המנוע, אורקלים, הפרדת הון ילדים, שלושה אירועים נפרדים. ללא רשת/שירותים."""

import json
import re

import pytest

from portfolio_lab import Asset, Scenario, simulate
from portfolio_lab.liquidity_stress import build_stress_view, normalize_params, run_cushion

CRISIS = {"decline_pct": 40, "start_month": 1, "recovery_years": 2}


def _p(**kw):
    return normalize_params(kw)


# ── parity מול המנוע ──
@pytest.mark.parametrize("crisis", [None, {"decline_pct": 30, "start_month": 7, "recovery_years": 1}])
def test_parity_with_engine_without_outflows(crisis):
    p = _p(fund_value=500_000, monthly_deposit=8000, monthly_support=0, annual_return_pct=7, annual_fee_pct=0.2,
           horizon_months=120, phase="accumulation", cushion_modes=[0], crisis=crisis)
    mine = run_cushion(p, 0)["final_nominal"]
    asset = Asset(annual_return=0.07, annual_fee=0.002)
    if crisis:
        from portfolio_lab.simulator_view import crisis_asset_monthly
        asset = crisis_asset_monthly(asset, 0.3, 1, 7, 1, 10)
    eng = simulate(Scenario(years=10, initial=500_000, monthly_contribution=8000, inflation=0.02, assets=(asset,)))["final"]["value_after_costs"]
    assert mine == pytest.approx(eng, rel=1e-9)


# ── אורקל כרית ──
def test_cushion_funds_burn_until_exhausted_then_sells():
    p = _p(fund_value=1_000_000, monthly_deposit=0, monthly_support=10_000, annual_return_pct=0, annual_fee_pct=0,
           cushion_modes=[0], horizon_months=24)
    run = run_cushion({**p, "net_burn": 10_000}, 5)  # כרית של 5 חודשי תזרים
    assert run["cushion_exhausted_month"] == 5
    assert [e["month"] for e in run["forced"]] == list(range(6, 25))
    assert run["final_nominal"] == pytest.approx(1_000_000 - 24 * 10_000)


def test_net_burn_includes_other_income_and_deposits():
    p = _p(monthly_support=10_000, monthly_deposit=8_000, other_monthly_expenses=1_000, other_monthly_income=500)
    assert p["net_burn"] == pytest.approx(2_500)


def test_months_of_support_covered_vs_net_burn():
    v = build_stress_view({"monthly_support": 10_000, "monthly_deposit": 8_000, "crisis": CRISIS})
    m24 = next(m for m in v["modes"] if m["cushion_months"] == 24)
    assert m24["free_cushion"] == 48_000 and m24["months_of_support_covered"] == pytest.approx(4.8)
    assert v["net_burn"]["net_burn_per_month"] == 2_000


# ── שלושה אירועים נפרדים ──
def test_forced_sale_without_shortfall_and_collateral_not_applicable():
    v = build_stress_view({"crisis": CRISIS, "cushion_modes": [0]})
    ev = v["modes"][0]["events"]
    assert ev["forced_sale"]["count"] > 0 and ev["cash_shortfall"]["count"] == 0
    assert ev["collateral_call"]["status"] == "not_applicable_no_loan"


def test_shortfall_without_cushion_when_fund_runs_out():
    v = build_stress_view({"fund_value": 100_000, "monthly_deposit": 0, "monthly_support": 20_000, "annual_return_pct": 0,
                           "annual_fee_pct": 0, "cushion_modes": [0], "horizon_months": 12})
    ev = v["modes"][0]["events"]
    assert ev["cash_shortfall"]["count"] > 0 and ev["forced_sale"]["count"] > 0
    assert ev["cash_shortfall"]["first_month"] == 6  # 5 חודשים מכוסים במכירה, בשישי נגמר הכסף


def test_no_forced_sale_when_deposits_cover_support():
    v = build_stress_view({"monthly_deposit": 10_000, "monthly_support": 10_000, "crisis": CRISIS, "cushion_modes": [0]})
    m = v["modes"][0]
    assert m["events"]["forced_sale"]["count"] == 0 and m["window_24m"]["forced_sale_free"] is True


def test_more_cushion_never_increases_forced_sales_in_window():
    v = build_stress_view({"crisis": CRISIS})
    totals = [m["events"]["forced_sale"]["total_amount"] for m in v["modes"]]
    assert totals == sorted(totals, reverse=True)


# ── sequence ──
def test_sequence_matters_only_with_net_outflows():
    def final(start, **kw):
        p = _p(crisis={"decline_pct": 40, "start_month": start, "recovery_years": 2}, cushion_modes=[0], **kw)
        return run_cushion(p, 0)["final_nominal"]
    flat = dict(monthly_deposit=0, monthly_support=0)
    assert final(1, **flat) == pytest.approx(final(61, **flat))  # בלי תזרים: חזרה לנתיב המגמה, סדר לא משנה
    out = dict(monthly_deposit=0, monthly_support=15_000)
    assert final(1, **out) != pytest.approx(final(61, **out))  # עם משיכות: סדר התשואות משנה


def test_no_crisis_delta_zero():
    v = build_stress_view({"cushion_modes": [0, 12]})
    assert all(m["delta_vs_no_crisis"] == 0 and m["window_24m"] is None for m in v["modes"])


def test_crisis_lowers_final_value():
    v = build_stress_view({"crisis": CRISIS})
    deltas = [m["delta_vs_no_crisis"] for m in v["modes"]]
    assert deltas[0] < 0 and deltas == sorted(deltas)  # כרית מקטינה את הנזק
    assert deltas[-1] == pytest.approx(0, abs=0.01)  # 24 חודשי תזרים מכסים את חלון ההתאוששות: אין מכירה במחירי שפל, חזרה לנתיב המגמה


# ── הפרדת הון ילדים וקופות מזומן ──
@pytest.mark.parametrize("bad", [{"in_collateral": True}, {"amount": 100, "in_collateral": False}, {"amount": 1, "pledged": True}])
def test_protected_capital_cannot_be_pledged_or_extended(bad):
    with pytest.raises(ValueError):
        normalize_params({"protected_capital": bad})


def test_protected_capital_untouched_by_any_scenario():
    a = build_stress_view({"crisis": CRISIS, "protected_capital": {"amount": 500_000}})
    b = build_stress_view({"crisis": {**CRISIS, "decline_pct": 80}, "protected_capital": {"amount": 500_000}})
    assert a["protected_capital"] == b["protected_capital"] and a["protected_capital"]["separation"] == "hard"
    assert [m["final_net_value"] for m in build_stress_view({"crisis": CRISIS})["modes"]] == [m["final_net_value"] for m in a["modes"]]


def test_reserved_cash_never_funds_flows():
    base = {"fund_value": 1_000_000, "monthly_deposit": 0, "monthly_support": 10_000, "annual_return_pct": 0, "annual_fee_pct": 0,
            "cushion_modes": [0], "horizon_months": 12}
    plain = build_stress_view(base)["modes"][0]
    held = build_stress_view({**base, "cash_buckets": {"pledged": 200_000, "family_earmarked": 100_000}})["modes"][0]
    assert held["series"][-1]["reserved_cash"] == 300_000
    assert held["final_net_value"] == plain["final_net_value"]  # שמור, לא מושקע ולא מוצא
    assert held["events"]["forced_sale"]["count"] == plain["events"]["forced_sale"]["count"]


def test_free_bucket_is_derived_not_input():
    with pytest.raises(ValueError):
        normalize_params({"cash_buckets": {"free": 10}})


# ── ולידציה ──
@pytest.mark.parametrize("bad", [
    {"loan": {"amount": 1}}, {"cushion_basis": "support_only"}, {"unknown": 1},
    {"fund_value": float("nan")}, {"fund_value": True}, {"monthly_deposit": -1},
    {"phase": "x"}, {"crisis": {"start_month": 1}}, {"crisis": {"decline_pct": 95}},
    {"crisis": {"decline_pct": 40, "start_month": 999}}, {"cushion_modes": []}, {"cushion_modes": [12, 12]},
    {"cushion_modes": [True]}, {"horizon_months": 0}, {"horizon_months": 10_000},
    {"fund_value": 100_000, "cushion_modes": [60]},
])
def test_invalid_inputs_rejected(bad):
    with pytest.raises(ValueError):
        build_stress_view(bad)


# ── דטרמיניזם וניסוח ──
def test_deterministic_and_digest():
    a, b = build_stress_view({"crisis": CRISIS}), build_stress_view({"crisis": CRISIS})
    assert a == b and a["replay_digest"] == b["replay_digest"]
    assert a["result_type"] == "stress_scenario_under_stated_assumptions"


def test_no_forbidden_wording_in_output():
    text = json.dumps(build_stress_view({"crisis": CRISIS}), ensure_ascii=False).lower()
    assert not re.search(r"probabilit|success_rate|chance|recommend|\bsafe\b|סיכוי להצליח|הסתברות", text)


# ── E1b: הלוואה, LTV, דרישת בטוחות ──
LOAN = {"amount": 900_000, "annual_rate_pct": 7, "max_ltv_pct": 45}
FLAT = {"annual_return_pct": 0, "annual_fee_pct": 0}  # מחיר 1, ירידה 40% נקייה: 0.6
RES = {"crisis": {"decline_pct": 40, "start_month": 1, "recovery_years": 2}, "horizon_months": 12, **FLAT}


def _mode(view, months):
    return next(m for m in view["modes"] if m["cushion_months"] == months)


def test_spec_example_numbers():
    v = build_stress_view({**RES, "loan": LOAN})
    m0 = _mode(v, 0)
    assert m0["initial_ltv"] == pytest.approx(0.3) and m0["initial_collateral"] == 3_000_000
    assert v["loan"]["first_month_interest"] == pytest.approx(5250)
    assert v["net_burn"]["net_burn_per_month"] == pytest.approx(7250)  # 10,000 + 5,250 − 8,000
    assert m0["trigger_decline_pct"] == pytest.approx(33.33)
    assert _mode(v, 24)["initial_collateral"] == pytest.approx(3_000_000 - 24 * 7_250)  # כרית חופשית אינה בטוחה
    assert v["loan"]["max_ltv_source"] == "owner_entered" and v["loan"]["terms_verified"] is False


def test_collateral_call_math_no_cushion():
    m = _mode(build_stress_view({**RES, "loan": LOAN, "cushion_modes": [0]}), 0)
    call = m["events"]["collateral_call"]["events"][0]
    units = 3_000_000 - 7_250 / 0.6  # תזרים חודש 1 נמכר במחיר 0.6
    coll = units * 0.6
    gap = 900_000 - 0.45 * coll
    assert call["month"] == 1 and call["ltv"] == pytest.approx(900_000 / coll, abs=1e-4)
    assert call["cured_from_risky_sale"] == pytest.approx(gap / 0.55, abs=0.01) and call["cured_from_free_cash"] == 0
    assert m["forced_sale_by_cause"]["collateral_call"] == pytest.approx(gap / 0.55, abs=0.01)


def test_cure_from_free_cash_first_does_not_shrink_collateral():
    m = _mode(build_stress_view({**RES, "loan": LOAN, "cushion_modes": [24]}), 24)
    ev = m["events"]
    assert ev["collateral_call"]["count"] == 1
    assert ev["collateral_call"]["events"][0]["cured_from_free_cash"] > 0
    assert ev["collateral_call"]["events"][0]["cured_from_risky_sale"] == 0
    # התיקון לא גרם למכירה, ואין מחסור; הכרית שנצרכה בתיקון מותירה מכירות תזרים מאוחרות — אירוע נפרד
    assert m["forced_sale_by_cause"]["collateral_call"] == 0 and ev["cash_shortfall"]["count"] == 0
    assert all(e["cause"] == "cashflow" for e in ev["forced_sale"]["events"]) and ev["forced_sale"]["count"] > 0
    assert m["window_24m"]["collateral_call_free"] is False


def test_cure_order_risky_sale_first_leaves_cushion():
    v = build_stress_view({**RES, "loan": {**LOAN, "cure_order": ["risky_sale"]}, "cushion_modes": [24]})
    call = _mode(v, 24)["events"]["collateral_call"]["events"][0]
    assert call["cured_from_free_cash"] == 0 and call["cured_from_risky_sale"] > 0


def test_no_call_below_trigger_decline():
    v = build_stress_view({**RES, "crisis": {"decline_pct": 30, "start_month": 1, "recovery_years": 2}, "loan": LOAN, "cushion_modes": [0, 24]})
    assert _mode(v, 0)["events"]["collateral_call"]["count"] == 0
    assert _mode(v, 24)["trigger_decline_pct"] == pytest.approx(29.2, abs=0.1)  # כרית חופשית מקטינה את הבטוחה
    assert _mode(v, 24)["events"]["collateral_call"]["count"] == 1


def test_call_distinct_from_shortfall_and_forced_sale():
    base = {**RES, "loan": LOAN, "cushion_modes": [0]}
    ev = _mode(build_stress_view(base), 0)["events"]
    assert ev["collateral_call"]["count"] == 1 and ev["forced_sale"]["count"] > 0 and ev["cash_shortfall"]["count"] == 0
    causes = {e["cause"] for e in ev["forced_sale"]["events"]}
    assert causes == {"cashflow", "collateral_call"}


def test_unresolved_call_when_collateral_exhausted():
    v = build_stress_view({"fund_value": 1_000_000, "cash_buckets": {"family_earmarked": 600_000}, "monthly_deposit": 0,
                           "monthly_support": 0, "cushion_modes": [0], "horizon_months": 6, **FLAT,
                           "loan": {"amount": 500_000, "annual_rate_pct": 0, "max_ltv_pct": 45}})
    call = _mode(v, 0)["events"]["collateral_call"]
    assert call["unresolved_count"] > 0 and call["events"][0]["unresolved"] == pytest.approx(100_000)


def test_interest_only_oracle_net_worth():
    v = build_stress_view({"fund_value": 1_000_000, "monthly_deposit": 0, "monthly_support": 0, "cushion_modes": [0],
                           "horizon_months": 12, **FLAT, "loan": {"amount": 100_000, "annual_rate_pct": 12, "max_ltv_pct": 90}})
    m = _mode(v, 0)
    assert m["final_debt"] == 100_000 and m["final_net_value"] == pytest.approx(1_000_000 - 12 * 1_000)
    assert m["final_net_worth"] == pytest.approx(1_000_000 - 12 * 1_000 - 100_000)


def test_amortizing_loan_fully_repaid_and_cash_flows_match():
    v = build_stress_view({"fund_value": 1_000_000, "monthly_deposit": 0, "monthly_support": 0, "cushion_modes": [0],
                           "horizon_months": 24, **FLAT,
                           "loan": {"amount": 120_000, "annual_rate_pct": 12, "interest_only": False, "term_months": 12, "max_ltv_pct": 90}})
    m = _mode(v, 0)
    i = 0.01
    pmt = 120_000 * i / (1 - (1 + i) ** -12)
    assert m["final_debt"] == pytest.approx(0, abs=0.01)
    assert m["final_net_value"] == pytest.approx(1_000_000 - 12 * pmt, abs=0.05)
    assert v["net_burn"]["components"]["loan_repayments"] == pytest.approx(pmt - 1_200, abs=0.01)


def test_asset_income_reduces_burn_and_adds_asset_to_net_worth():
    plain = build_stress_view({**FLAT, "loan": LOAN})
    inc = build_stress_view({**FLAT, "loan": {**LOAN, "use_proceeds": {"kind": "asset_income", "monthly_income": 3_000, "asset_value": 900_000}}})
    assert inc["net_burn"]["net_burn_per_month"] == plain["net_burn"]["net_burn_per_month"] - 3_000
    assert _mode(inc, 0)["final_net_worth"] > _mode(plain, 0)["final_net_worth"] + 900_000
    assert "ללא תשואה" in plain["loan"]["proceeds"]["note"]


def test_pledged_cash_counts_as_collateral_but_free_cash_does_not():
    kw = {**RES, "loan": LOAN, "cushion_modes": [0]}
    without = _mode(build_stress_view(kw), 0)["events"]["collateral_call"]["events"][0]["collateral"]
    with_pledged = _mode(build_stress_view({**kw, "cash_buckets": {"pledged": 300_000}}), 0)["events"]["collateral_call"]
    only = _mode(build_stress_view({**kw, "cash_buckets": {"pledged": 300_000}, "loan": {**LOAN, "collateral": "risky_only"}}), 0)["events"]["collateral_call"]
    assert with_pledged["count"] <= 1 and only["events"][0]["collateral"] < without
    assert _mode(build_stress_view({**kw, "cash_buckets": {"pledged": 300_000}}), 0)["initial_collateral"] == 3_000_000
    assert _mode(build_stress_view({**kw, "cash_buckets": {"pledged": 300_000}, "loan": {**LOAN, "collateral": "risky_only"}}), 0)["initial_collateral"] == 2_700_000


def test_unpaid_loan_payment_capitalises_into_debt():
    v = build_stress_view({"fund_value": 1_100_000, "cash_buckets": {"pledged": 1_000_000}, "monthly_deposit": 0, "monthly_support": 50_000,
                           "cushion_modes": [0], "horizon_months": 6, **FLAT,
                           "loan": {"amount": 50_000, "annual_rate_pct": 12, "max_ltv_pct": 95}})
    m = _mode(v, 0)
    assert m["events"]["cash_shortfall"]["count"] > 0 and m["final_debt"] > 50_000


@pytest.mark.parametrize("bad", [
    {"annual_rate_pct": 7, "max_ltv_pct": 45}, {"amount": 1, "max_ltv_pct": 45}, {"amount": 1_000, "annual_rate_pct": 7},
    {**LOAN, "term_months": 12}, {**LOAN, "interest_only": False}, {**LOAN, "interest_only": "yes"}, {**LOAN, "terms_verified": 1},
    {**LOAN, "collateral": "children_capital"}, {**LOAN, "cure_order": ["children_capital"]}, {**LOAN, "cure_order": []},
    {**LOAN, "unknown": 1}, {**LOAN, "amount": 5_000_000}, {**LOAN, "max_ltv_pct": 99}, {**LOAN, "use_proceeds": {"kind": "none", "monthly_income": 5}},
    {**LOAN, "use_proceeds": {"kind": "bonus"}},
])
def test_invalid_loan_rejected(bad):
    with pytest.raises(ValueError):
        build_stress_view({"loan": bad})


def test_loan_run_deterministic_and_wording_clean():
    a, b = build_stress_view({**RES, "loan": LOAN}), build_stress_view({**RES, "loan": LOAN})
    assert a == b
    text = json.dumps(a, ensure_ascii=False).lower()
    assert not re.search(r"probabilit|success_rate|chance|recommend|\bsafe\b|הסתברות", text)


# ── E1c: POST /api/portfolio-lab/liquidity-stress (שער, מגבלות, שגיאות; קריאה בלבד) ──
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

import tma_api

_URL = "/api/portfolio-lab/liquidity-stress"
_H = {"X-Telegram-Init-Data": "valid"}
_OWNER = SimpleNamespace(user_id="eliyahu", is_owner=True)
_PARTNER = SimpleNamespace(user_id="avi", is_owner=False)


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(tma_api, "_PL_LIMITER", None)


def _client(monkeypatch, who=_OWNER, gate=True, valid_init=True):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", (lambda _: {"id": getattr(who, "user_id", "x")}) if valid_init else (lambda _: None))
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: gate)
    return app.test_client()


def _post(c, body, headers=_H, ctype="application/json"):
    data = body if isinstance(body, (bytes, str)) else json.dumps(body)
    return c.post(_URL, data=data, headers=headers, content_type=ctype)


def test_api_requires_valid_telegram_auth(monkeypatch):
    assert _post(_client(monkeypatch), {}, headers={}).status_code == 401
    assert _post(_client(monkeypatch, valid_init=False), {}).status_code == 401


def test_api_gate_flag_canary_and_owner(monkeypatch):
    assert _post(_client(monkeypatch, gate=False), {}).status_code == 404
    assert _post(_client(monkeypatch, who=_PARTNER), {}).status_code == 404
    assert _post(_client(monkeypatch, who=None), {}).status_code == 404
    assert _post(_client(monkeypatch), {}).status_code == 200


def test_api_real_fcc_gate_is_used_not_a_copy(monkeypatch):
    import feature_flags
    monkeypatch.setattr(feature_flags, "is_enabled", lambda n, *a, **k: n == "FEATURE_FINANCIAL_CONTROL_CENTER")
    monkeypatch.setenv("FCC_CANARY_USER_IDS", "eliyahu")
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": "x"})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: _OWNER)
    assert _post(app.test_client(), {}).status_code == 200
    monkeypatch.delenv("FCC_CANARY_USER_IDS")
    assert _post(app.test_client(), {}).status_code == 404  # הדגל לבדו לא חושף דבר


def test_api_only_post_and_preflight(monkeypatch):
    c = _client(monkeypatch)
    assert c.get(_URL, headers=_H).status_code == 405
    assert c.open(_URL, method="OPTIONS").status_code == 204


def test_api_returns_the_pure_view(monkeypatch):
    body = {"crisis": CRISIS, "loan": LOAN}
    r = _post(_client(monkeypatch), body)
    assert r.status_code == 200
    expected = build_stress_view(body)
    assert r.get_json()["replay_digest"] == expected["replay_digest"]
    assert r.get_json()["result_type"] == "stress_scenario_under_stated_assumptions"


def test_api_limits_and_errors(monkeypatch):
    c = _client(monkeypatch)
    assert _post(c, {}, ctype="text/plain").status_code == 415
    assert _post(c, b"x" * (64 * 1024 + 1)).status_code == 413
    assert _post(c, b"").status_code in (411, 413)
    assert _post(c, b"{not json").status_code == 400
    assert _post(c, {"surprise": 1}).status_code == 400
    assert _post(c, {"loan": {"amount": 1}}).status_code == 400
    r = _post(c, [])
    assert r.status_code == 400 and "Traceback" not in r.get_data(as_text=True)


def test_api_child_capital_cannot_be_pledged_through_the_endpoint(monkeypatch):
    r = _post(_client(monkeypatch), {"protected_capital": {"amount": 1, "in_collateral": True}})
    assert r.status_code == 400 and "in_collateral" in r.get_json()["error"]


@pytest.mark.parametrize("payload", [
    {"fund_value": 10 ** 400}, {"fund_value": 1e300, "monthly_support": 1e9}, {"annual_return_pct": 100, "horizon_months": 360},
    {"cushion_modes": [0] * 5000}, {"loan": {"amount": 1, "annual_rate_pct": 100, "max_ltv_pct": 5}}, {"crisis": [1]},
    {"loan": "x"}, {"cash_buckets": []}, None, 5, "x",
])
def test_api_hostile_payloads_never_500(monkeypatch, payload):
    r = _post(_client(monkeypatch), payload)
    assert r.status_code in (200, 400)
    assert "Traceback" not in r.get_data(as_text=True)


def test_api_unexpected_exception_is_generic_500(monkeypatch):
    import portfolio_lab.liquidity_stress as ls
    monkeypatch.setattr(ls, "build_stress_view", lambda p: (_ for _ in ()).throw(RuntimeError("secret internals")))
    r = _post(_client(monkeypatch), {})
    assert r.status_code == 500 and r.get_json() == {"error": "internal error"}


def test_api_rate_limit_per_user_separate_from_simulate(monkeypatch):
    c = _client(monkeypatch)
    codes = [_post(c, {"horizon_months": 12}).status_code for _ in range(14)]
    assert codes[:12] == [200] * 12 and codes[12:] == [429, 429]
    assert tma_api._PL_LIMITER.is_allowed("portfolio_lab:eliyahu")  # מפתח נפרד מ-/simulate


def test_api_concurrency_gate_returns_503_when_busy(monkeypatch):
    class Busy:
        def acquire(self, timeout=None): return False
        def release(self): raise AssertionError("must not release an unacquired slot")
    monkeypatch.setattr(tma_api, "_PL_COMPUTE", Busy())
    assert _post(_client(monkeypatch), {}).status_code == 503


def test_api_worst_case_is_fast_and_bounded(monkeypatch):
    import time
    body = {"horizon_months": 360, "cushion_modes": [0, 6, 12, 24, 36], "crisis": CRISIS, "loan": {**LOAN, "interest_only": False, "term_months": 360}}
    t = time.perf_counter()
    r = _post(_client(monkeypatch), body)
    assert r.status_code == 200 and time.perf_counter() - t < 3
    assert len(r.get_data()) < 4 * 1024 * 1024


def test_api_block_is_read_only():
    text = Path("tma_api.py").read_text(encoding="utf-8")
    block = text.split("# ── E1c: liquidity stress test", 1)[1].split("\n@tma_api.route", 3)
    code = "\n".join(block[:3])
    for forbidden in ("airtable", "_queue_or_owner_execute", "dispatch_tool", "call_anthropic", "filter_records", "_gw_create", "_gw_patch"):
        assert forbidden not in code, forbidden
