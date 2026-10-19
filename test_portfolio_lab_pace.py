"""C4 — קצב צבירה בפועל מול התוכנית (Portfolio Lab, נתיב 1ד): מודול טהור, קריאת השרת (owner-scoped) ו-endpoint. ללא רשת/Airtable/LLM."""

import json
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

import tma_api
from airtable_schema import FinAccountFields as ACF, FinEventFields as EF, Tables
from core.financial_control import accounts as fcc_accounts, service
from portfolio_lab import Asset, Scenario, simulate
from portfolio_lab.pace_tracker import EXTRAPOLATION_LABEL, build_pace_view, normalize_params

TODAY = date(2026, 10, 19)


def acct(aid="recA", **kw):
    return {"id": aid, "name": kw.pop("name", aid), "status": kw.pop("status", "active"), "planned_monthly_deposit": kw.pop("planned", 3000),
            "expected_return_pct": kw.pop("ret", 6), "management_fee_pct": kw.pop("fee", 0.5), **kw}


def ev(eid, kind, amount, day, account="recA", counter=None):
    return {"id": eid, "kind": kind, "amount": amount, "day": day, "account": account, "counter": counter}


def snap(eid, amount, day, account="recA"):
    return ev(eid, "balance_snapshot", amount, day, account)


def view(accounts, events, history=None, **params):
    return build_pace_view({"accounts": accounts, "events": events, "savings_history": history, "as_of": TODAY.isoformat()}, params, TODAY)


BASE_EVENTS = [snap("s1", 100000, date(2026, 1, 10)), snap("s2", 150000, date(2026, 9, 10)),
               ev("d1", "deposit", 20000, date(2026, 4, 1)), ev("d2", "deposit", 20000, date(2026, 7, 1))]


# ── מודול טהור ──
def test_planned_value_matches_independent_engine_run_and_deposits_only_formula():
    a = view([acct()], BASE_EVENTS)["accounts"][0]
    months = 8                                     # ינואר -> ספטמבר
    sim = simulate(Scenario(years=10, initial=100000.0, monthly_contribution=3000.0, inflation=0.02, start_date="2026-01-01",
                            assets=(Asset(annual_return=0.06, annual_fee=0.005),)), monthly=True)["monthly"]
    assert a["status"] == "compared" and a["window"]["months"] == months
    assert a["planned"]["value_at_comparison"] == pytest.approx(sim[months - 1]["value_after_costs"], abs=0.01)
    assert a["planned"]["value_deposits_only"] == 100000 + 3000 * months and a["planned"]["deposits_total"] == 3000 * months
    months_today = 9                                # ינואר -> אוקטובר 2026
    assert a["planned"]["value_to_date"] == pytest.approx(sim[months_today - 1]["value_after_costs"], abs=0.01) and a["planned"]["to_date"] == TODAY.isoformat()
    assert a["planned"]["return_source"] == "account" and a["planned"]["fee_source"] == "account"


def test_deviation_and_deposit_gap_signs():
    a = view([acct()], BASE_EVENTS)["accounts"][0]
    assert a["deviation"]["vs_plan"] == pytest.approx(150000 - a["planned"]["value_at_comparison"], abs=0.01)
    assert a["deviation"]["vs_deposits_only"] == 150000 - (100000 + 3000 * 8)
    assert a["deviation"]["deposits_gap"] == 40000 - 24000
    behind = view([acct(planned=9000)], BASE_EVENTS)["accounts"][0]
    assert behind["deviation"]["vs_deposits_only"] < 0 and behind["deviation"]["deposits_gap"] < 0


def test_three_things_are_kept_apart_flows_value_change_unexplained():
    a = view([acct()], BASE_EVENTS)["accounts"][0]
    assert a["flows"]["deposits"] == 40000 and a["flows"]["net_documented"] == 40000
    assert a["value_change"] == {**a["value_change"], "total": 50000, "documented_flows": 40000, "unexplained": 10000}
    w = view([acct()], BASE_EVENTS + [ev("w1", "withdrawal", 5000, date(2026, 5, 1)), ev("f1", "fee", 100, date(2026, 6, 1))])["accounts"][0]
    assert w["flows"]["net_documented"] == 40000 - 5000 - 100 and w["value_change"]["unexplained"] == 50000 - 34900


def test_no_exact_return_when_flows_exist_only_a_marked_range():
    r = view([acct()], BASE_EVENTS)["accounts"][0]["return"]
    assert r["exact"] is None and r["status"] == "approximate_range" and r["undocumented_flows_possible"] is True
    # change=10000, מכנים: 100000 (כל התנועות בסוף) ו-140000 (כולן בהתחלה)
    assert r["range"]["low"] == pytest.approx(10000 / 140000) and r["range"]["high"] == pytest.approx(10000 / 100000)
    assert r["annualized_range"]["low"] < r["annualized_range"]["high"]


def test_range_handles_withdrawals_and_negative_change():
    r = view([acct()], [snap("s1", 100000, date(2026, 1, 10)), snap("s2", 60000, date(2026, 9, 10)),
                        ev("w", "withdrawal", 30000, date(2026, 4, 1))])["accounts"][0]["return"]
    # change = 60000-100000+30000 = -10000; מכנים: 70000 (משיכה בהתחלה) ו-100000 (בסוף)
    assert r["exact"] is None and r["range"]["low"] == pytest.approx(-10000 / 70000) and r["range"]["high"] == pytest.approx(-10000 / 100000)


@pytest.mark.parametrize("first,last,expected", [
    (date(2026, 9, 1), date(2026, 9, 20), "period_too_short"),
])
def test_short_period_has_no_return(first, last, expected):
    a = view([acct()], [snap("s1", 1000, first), snap("s2", 1100, last)])["accounts"][0]
    assert a["return"]["status"] == expected and a["return"]["range"] is None and a["status"] == "short_period"


def test_zero_start_balance_and_nonpositive_denominator():
    zero = view([acct()], [snap("s1", 0, date(2026, 1, 10)), snap("s2", 5000, date(2026, 9, 10))])["accounts"][0]["return"]
    assert zero["status"] == "start_balance_not_positive" and zero["range"] is None
    big_out = view([acct()], [snap("s1", 1000, date(2026, 1, 10)), snap("s2", 100, date(2026, 9, 10)),
                              ev("w", "withdrawal", 5000, date(2026, 4, 1))])["accounts"][0]["return"]
    assert big_out["status"] == "undefined_denominator" and big_out["range"] is None


def test_missing_is_missing_never_zero():
    plain = view([acct(planned=None, ret=None, fee=None)], [snap("s1", 100000, date(2026, 1, 10)), snap("s2", 120000, date(2026, 9, 10))])
    a = plain["accounts"][0]
    assert a["planned"] is None and a["deviation"] is None
    assert {"planned_monthly_deposit", "expected_return", "management_fee", "deposit_events"} <= set(a["missing"])
    assert a["flows"]["deposits"] is None and a["flows"]["deposit_count"] == 0           # אין אירועי הפקדה = חסר, לא 0
    assert plain["consolidated"]["deviation"] is None and plain["consolidated"]["accounts_without_plan"] == 1


def test_return_and_fee_default_to_screen_assumptions_and_are_labelled():
    a = view([acct(ret=None, fee=None)], BASE_EVENTS, annual_return_pct=5, annual_fee_pct=0.3)["accounts"][0]
    assert a["planned"]["return_source"] == "default" and a["planned"]["return_pct"] == pytest.approx(5)
    assert a["planned"]["fee_source"] == "default" and "expected_return" in a["missing"]


def test_same_day_events_do_not_count_and_are_reported():
    a = view([acct()], BASE_EVENTS + [ev("x", "deposit", 7777, date(2026, 9, 10)), ev("y", "deposit", 8888, date(2026, 1, 10))])["accounts"][0]
    assert a["flows"]["deposits"] == 40000 and a["flows"]["same_day_events"] == 2


def test_account_without_snapshot_single_snapshot_and_closed():
    v = view([acct("recA"), acct("recB"), acct("recC"), acct("recD", status="closed")],
             BASE_EVENTS + [snap("s9", 5000, date(2026, 5, 1), "recB")])
    statuses = {r["id"]: r["status"] for r in v["accounts"]}
    assert statuses == {"recA": "compared", "recB": "single_snapshot", "recC": "no_snapshot"} and v["closed_accounts"] == 1
    assert v["consolidated"]["accounts_without_snapshot"] == 1 and v["consolidated"]["accounts_single_snapshot"] == 1


def test_transfers_are_flows_between_own_accounts_never_deposits():
    v = view([acct("recA"), acct("recB")], BASE_EVENTS + [snap("t1", 10000, date(2026, 1, 10), "recB"), snap("t2", 22000, date(2026, 9, 10), "recB"),
                                                              ev("tr", "transfer", 3000, date(2026, 5, 5), "recA", "recB")])
    a, b = v["accounts"]
    assert a["flows"]["transfers_out"] == 3000 and a["flows"]["deposits"] == 40000
    assert b["flows"]["transfers_in"] == 3000 and b["flows"]["deposits"] is None and "deposit_events" in b["missing"]


def test_consolidated_sums_compared_accounts_and_has_no_pooled_return():
    v = view([acct("recA"), acct("recB", planned=1000)],
             BASE_EVENTS + [snap("t1", 10000, date(2026, 1, 10), "recB"), snap("t2", 22000, date(2026, 9, 10), "recB"), ev("t3", "deposit", 8000, date(2026, 5, 1), "recB")])
    c = v["consolidated"]
    assert c["start_balance"] == 110000 and c["latest_balance"] == 172000 and c["accounts_with_plan"] == 2
    assert c["deviation"]["vs_plan"] == pytest.approx(sum(r["deviation"]["vs_plan"] for r in v["accounts"]), abs=0.02)
    assert c["return"]["exact"] is None and c["return"]["status"] == "not_computed_consolidated"
    assert c["value_change"]["documented_flows"] == 48000 and c["value_change"]["unexplained"] == 14000


def test_forecast_lines_assumptions_and_label():
    v = view([acct()], BASE_EVENTS, {"monthly_average": 2500, "ytd": 1, "ytd_plan": 2, "ytd_gap": 1, "months_elapsed": 9, "streak": 3})
    f = v["forecast"]
    assert f["label"] == EXTRAPOLATION_LABEL == "אקסטרפולציה של הקצב בפועל — לא תחזית"
    assert f["starting_value"] == 150000 and f["horizon_years"] == 10
    pace = 40000 / 8
    assert f["lines"]["actual_pace"]["monthly_deposit"] == pace and f["lines"]["planned_pace"]["monthly_deposit"] == 3000
    assert f["lines"]["goal_history_pace"]["monthly_deposit"] == 2500
    oracle = simulate(Scenario(years=10, initial=150000.0, monthly_contribution=pace, inflation=0.02,
                               assets=(Asset(annual_return=0.06, annual_fee=0.0015),)))["final"]["value_after_costs"]
    assert f["lines"]["actual_pace"]["final_nominal"] == pytest.approx(oracle)
    assert f["gaps"]["actual_pace_vs_planned_pace"] == pytest.approx(oracle - f["lines"]["planned_pace"]["final_nominal"])
    assert f["assumptions"]["annual_return_pct"] == 6.0 and f["coverage"]["planned_missing_is_not_zero"] is True
    assert v["goal_level_history"]["monthly_average"] == 2500


def test_missing_pace_means_no_line_not_a_zero_line():
    v = view([acct(planned=None)], [snap("s1", 100000, date(2026, 1, 10)), snap("s2", 120000, date(2026, 9, 10))])
    assert v["forecast"]["lines"]["actual_pace"] is None and v["forecast"]["lines"]["planned_pace"] is None
    assert v["course_correction"] == {"applied": False, "reason": "no_documented_flows"}
    assert v["forecast"]["actual_pace_unavailable_reason"] == "no_documented_flows"


def test_net_withdrawals_are_not_extrapolated_as_a_negative_deposit():
    v = view([acct()], [snap("s1", 100000, date(2026, 1, 10)), snap("s2", 60000, date(2026, 9, 10)), ev("w", "withdrawal", 30000, date(2026, 4, 1))])
    assert v["forecast"]["lines"]["actual_pace"] is None and v["forecast"]["actual_pace_unavailable_reason"] == "negative_net_flow_not_modelled"
    assert v["forecast"]["lines"]["planned_pace"] is not None and v["course_correction"]["reason"] == "negative_net_flow_not_modelled"


def test_no_balances_at_all():
    v = view([acct()], [])
    assert v["forecast"] == {"applied": False, "reason": "no_balances"} and v["accounts"][0]["status"] == "no_snapshot"


def test_course_correction_is_linear_neutral_and_matches_engine():
    v = view([acct()], BASE_EVENTS)
    cc, f = v["course_correction"], v["forecast"]
    base = f["lines"]["actual_pace"]["final_nominal"]
    for row in cc["rows"]:
        oracle = simulate(Scenario(years=10, initial=150000.0, monthly_contribution=row["monthly_deposit"], inflation=0.02,
                                   assets=(Asset(annual_return=0.06, annual_fee=0.0015),)))["final"]["value_after_costs"]
        assert row["final_nominal"] == pytest.approx(oracle) and row["delta_vs_updated_forecast"] == pytest.approx(oracle - base)
    needed = cc["monthly_change_to_match_planned_end"]
    hit = simulate(Scenario(years=10, initial=150000.0, monthly_contribution=5000 + needed, inflation=0.02,
                            assets=(Asset(annual_return=0.06, annual_fee=0.0015),)))["final"]["value_after_costs"]
    assert hit == pytest.approx(f["lines"]["planned_pace"]["final_nominal"], rel=1e-9)
    assert needed < 0                                                   # בקצב בפועל כבר מעל התוכנית: שינוי שלילי, נאמר בלי "המלצה"
    assert "אינה המלצה" in cc["note"]


def test_deterministic_and_no_ranking_or_probabilities():
    a, b = view([acct()], BASE_EVENTS), view([acct()], BASE_EVENTS)
    assert a == b
    text = json.dumps(a, ensure_ascii=False).lower()
    assert "probab" not in text and "rank" not in text and "success" not in text and "best" not in text


@pytest.mark.parametrize("bad", [{"years": 9}, {"years": 51}, {"years": True}, {"annual_return_pct": 99}, {"annual_fee_pct": -1},
                                 {"inflation_pct": float("nan")}, {"surprise": 1}, [], "x"])
def test_invalid_params_rejected(bad):
    with pytest.raises(ValueError):
        normalize_params(bad)


# ── קריאת השרת: owner-scoped ──
ELI, AVI = "recELI", "recAVI"


def _row(rid, owner, **extra):
    return {"id": rid, "fields": {ACF.NAME: rid, ACF.ACCOUNT_TYPE: "study_fund", ACF.STATUS: "active", ACF.FINANCIAL_OWNER: [owner],
                                  ACF.PLANNED_MONTHLY_DEPOSIT: 3000, **extra}}


def _event(eid, kind, amount, day, account, owner=ELI):
    return {"id": eid, "fields": {EF.KIND: kind, EF.AMOUNT: amount, EF.OCCURRED_AT: day, EF.ACCOUNT: [account], EF.FINANCIAL_OWNER: [owner]}}


@pytest.fixture
def seeded(monkeypatch):
    rows = {Tables.FIN_ACCOUNTS: [_row("recAE", ELI), _row("recAA", AVI)]}
    events = [_event("e1", "balance_snapshot", 100000, "2026-01-10", "recAE"), _event("e2", "balance_snapshot", 150000, "2026-09-10", "recAE"),
              _event("e3", "deposit", 40000, "2026-04-01", "recAE"),
              _event("x1", "balance_snapshot", 777777, "2026-01-10", "recAA", AVI), _event("x2", "balance_snapshot", 888888, "2026-09-10", "recAA", AVI)]
    monkeypatch.setattr(service, "_read", lambda table, formula="": rows.get(table, []))
    monkeypatch.setattr(service.policy, "filter_records", lambda table, records, identity: records)        # סינון המדיניות מדומה: ההגנה בעומק היא שנבדקת
    monkeypatch.setattr(service.policy, "resolve_actor", lambda identity: SimpleNamespace(resolved=getattr(identity, "resolved", True), profile_id=ELI))
    monkeypatch.setattr(service, "my_events", lambda identity: events)
    monkeypatch.setattr(service, "my_goals", lambda identity: [])
    return SimpleNamespace(events=events)


def test_pace_inputs_is_owner_scoped_defence_in_depth(seeded):
    inputs = service.pace_inputs(SimpleNamespace(user_id="eliyahu"), TODAY)
    assert [a["id"] for a in inputs["accounts"]] == ["recAE"] and {e["account"] for e in inputs["events"]} == {"recAE"}
    assert "777777" not in str(inputs) and "888888" not in str(inputs) and inputs["savings_history"] is None
    out = build_pace_view(inputs, {})
    assert out["accounts"][0]["status"] == "compared" and out["accounts"][0]["flows"]["deposits"] == 40000
    assert "777777" not in json.dumps(out)


def test_pace_inputs_unresolved_identity_is_denied(seeded):
    with pytest.raises(service.policy.PersonalDataAccessDenied):
        service.pace_inputs(SimpleNamespace(user_id="nobody", resolved=False), TODAY)


def test_account_events_drops_malformed_and_foreign_rows():
    accounts = [_row("recAE", ELI)]
    good = _event("g", "deposit", 10, "2026-05-01", "recAE")
    bad = [_event("b1", "deposit", -5, "2026-05-01", "recAE"), _event("b2", "deposit", 5, "not-a-date", "recAE"),
           _event("b3", "deposit", 5, "2026-05-01", "recZZ"), _event("b4", "deposit", 5, "2026-05-01", "recAE", AVI),
           _event("b5", "transfer", 5, "2026-05-01", "recAE")]
    assert [e["id"] for e in fcc_accounts.account_events(accounts, [good, *bad], ELI)] == ["g"]


# ── endpoint ──
H = {"X-Telegram-Init-Data": "valid"}
URL = "/api/fcc/pace"
OWNER = SimpleNamespace(user_id="eliyahu", is_owner=True)
PARTNER = SimpleNamespace(user_id="avi", is_owner=False)


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(tma_api, "_PL_LIMITER", None)


def client(monkeypatch, who=OWNER, gate=True):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": getattr(who, "user_id", "x")})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: gate)
    return app.test_client()


def post(c, body, headers=H, ctype="application/json"):
    data = body if isinstance(body, (bytes, str)) else json.dumps(body)
    return c.post(URL, data=data, headers=headers, content_type=ctype)


def test_http_gate_flag_canary_owner_and_auth(monkeypatch, seeded):
    assert post(client(monkeypatch, gate=False), {}).status_code == 404
    assert post(client(monkeypatch, who=PARTNER), {}).status_code == 404
    assert post(client(monkeypatch, who=None), {}).status_code == 404
    assert post(client(monkeypatch), {}, headers={}).status_code == 401
    assert post(client(monkeypatch), {}).status_code == 200


def test_http_returns_pure_view_for_own_data_only(monkeypatch, seeded):
    body = post(client(monkeypatch), {"years": 12}).get_json()
    assert body["forecast"]["horizon_years"] == 12 and [a["id"] for a in body["accounts"]] == ["recAE"]
    assert "777777" not in json.dumps(body)


def test_http_limits_errors_and_read_only(monkeypatch, seeded):
    c = client(monkeypatch)
    assert post(c, {}, ctype="text/plain").status_code == 415
    assert post(c, "{not json").status_code == 400
    assert post(c, {"years": 5}).status_code == 400
    assert post(c, {"surprise": 1}).status_code == 400
    assert post(c, b"x" * (65 * 1024)).status_code == 413
    for method in ("get", "put", "patch", "delete"):
        assert getattr(c, method)(URL, headers=H).status_code in (404, 405)


def test_http_denied_identity_403_and_unexpected_error_is_generic(monkeypatch, seeded):
    monkeypatch.setattr(service, "pace_inputs", lambda identity: (_ for _ in ()).throw(service.policy.PersonalDataAccessDenied("x")))
    assert post(client(monkeypatch), {}).status_code == 403
    monkeypatch.setattr(service, "pace_inputs", lambda identity: (_ for _ in ()).throw(RuntimeError("secret internals")))
    r = post(client(monkeypatch), {})
    assert r.status_code == 500 and "secret" not in r.get_data(as_text=True)


def test_http_rate_limit_per_user(monkeypatch, seeded):
    c = client(monkeypatch)
    codes = [post(c, {}).status_code for _ in range(14)]
    assert codes[:12] == [200] * 12 and codes[12] == 429


def test_pace_module_is_pure_and_endpoint_block_is_read_only():
    text = Path("portfolio_lab/pace_tracker.py").read_text(encoding="utf-8")
    for forbidden in ("airtable", "requests", "urllib", "open(", "anthropic", "dispatch", "write"):
        assert forbidden not in text.replace("`writes`", ""), forbidden
    api = Path("tma_api.py").read_text(encoding="utf-8")
    block = api.split("def fcc_pace(identity):", 1)[1].split("def _funding_body", 1)[0]
    for forbidden in ("_queue_or_owner_execute", "dispatch_tool", "call_anthropic", "_gw_create", "_gw_patch", "airtable"):
        assert forbidden not in block, forbidden
    assert re.findall(r"from portfolio_lab[\w.]* import", block) == ["from portfolio_lab.pace_tracker import"]


@pytest.mark.parametrize("exc", [KeyError("secret-key"), TypeError("secret type"), OverflowError("secret overflow"), RuntimeError("secret runtime")])
def test_http_non_validation_errors_in_the_view_are_generic_500(monkeypatch, seeded, exc):
    import portfolio_lab.pace_tracker as pt
    monkeypatch.setattr(pt, "build_pace_view", lambda *a, **k: (_ for _ in ()).throw(exc))
    r = post(client(monkeypatch), {})
    assert r.status_code == 500 and r.get_json() == {"error": "internal error"} and "secret" not in r.get_data(as_text=True)


@pytest.mark.parametrize("exc", [KeyError("secret-key"), TypeError("secret type"), OverflowError("secret overflow"), ValueError("secret read value")])
def test_http_non_validation_errors_in_the_read_are_generic_500(monkeypatch, seeded, exc):
    monkeypatch.setattr(service, "pace_inputs", lambda identity: (_ for _ in ()).throw(exc))
    r = post(client(monkeypatch), {})
    assert r.status_code == 500 and r.get_json() == {"error": "internal error"} and "secret" not in r.get_data(as_text=True)


def test_http_validation_messages_may_be_returned_but_only_validation(monkeypatch, seeded):
    r = post(client(monkeypatch), {"years": 5})
    assert r.status_code == 400 and r.get_json() == {"error": "years must be an integer from 10 to 50"}
    import portfolio_lab.pace_tracker as pt
    monkeypatch.setattr(pt, "build_pace_view", lambda *a, **k: (_ for _ in ()).throw(ValueError("inputs must be an object")))
    r = post(client(monkeypatch), {})
    assert r.status_code == 400 and r.get_json() == {"error": "inputs must be an object"}


def test_current_planned_deposit_assumption_is_visible_on_the_card_and_in_the_assumptions():
    card = Path("tma-frontend/src/components/PaceTrackerPanel.tsx").read_text(encoding="utf-8")
    assert "הפקדה המתוכננת <strong>הנוכחית</strong>" in card and "לא התוכנית המקורית" in card
    assert any("הנוכחית" in a and "הפקדה חודשית מתוכננת" in a for a in view([acct()], BASE_EVENTS)["assumptions"])
