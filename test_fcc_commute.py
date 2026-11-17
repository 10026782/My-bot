"""FCC commute income: the pure engine, the day-answer / route endpoints (owner only, ONE write each), the guard of the two tables and the monthly income."""
from __future__ import annotations

import os
from datetime import date, timedelta

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-cm-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:CM_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patCmTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCmTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import pytest
from flask import Flask

import tma_api
from core import data_access_policy as policy
from core.financial_control import cashflow, commute as C, service
from identity import Domain, Identity, Role
from tools import approval_actions as aa

H = {"X-Telegram-Init-Data": "valid"}
ROUTE = {"id": "recROUTEAAAAAAAAA", "fields": {"Name": "נסיעה", "Day Price": 130, "Km One Way": 22, "Minutes One Way": 35, "Cost Per Km": 0.7, "Planned Days Per Week": 6, "Status": "active"}}


def trip(day: date, outcome="yes", stops=3, amount=130, tid=None):
    return {"id": tid or f"recT{day.isoformat()}", "fields": {"Route": [ROUTE["id"]], "Trip Date": day.isoformat(), "Outcome": outcome, "Stops": stops, "Amount": amount}}


def test_economics_one_trip_day_and_unknown_stays_unknown():
    e = C.economics(C.parse_route(ROUTE))
    assert e["km_per_day"] == 44 and e["minutes_per_day"] == 70 and e["gross_per_hour"] == 111.43 and e["gross_per_km"] == 2.95
    assert e["vehicle_cost_per_day"] == 30.8 and e["net_per_day"] == 99.2 and e["monthly_potential"] == 3380.0
    bare = C.economics(C.parse_route({"id": "r", "fields": {"Name": "x", "Day Price": 100}}))
    assert bare["gross_per_hour"] is None and bare["net_per_day"] is None and bare["price"] == 100


def test_week_income_is_days_times_price_and_stops_are_only_tracked():
    today = date(2026, 11, 17)
    week = [date(2026, 11, d) for d in (8, 9, 10, 11, 12)]                    # Sun-Thu: five rides
    trips = [trip(d, stops=2 + (i % 2), amount=130) for i, d in enumerate(week)] + [trip(date(2026, 11, 13), "no", None, 0)]
    v = C.build([ROUTE], trips, today)
    m = v["routes"][0]["this_month"]
    assert m["yes_days"] == 5 and m["no_days"] == 1 and m["income"] == 650.0 and m["weeks"] == [{"week_start": "2026-11-08", "yes_days": 5, "income": 650.0}]
    assert m["stops"] == {"2": 3, "3": 2} and v["income_this_month"] == 650.0


def test_stops_note_needs_a_real_sample_and_says_a_fact():
    day = date(2026, 11, 1)
    few = [C.parse_trip(trip(day + timedelta(days=i), stops=3)) for i in range(9)]
    assert C.stops_note(few) is None
    many = [C.parse_trip(trip(day + timedelta(days=i), stops=3 if i < 6 else 2)) for i in range(11)]
    assert "3 תחנות" in C.stops_note(many)
    mostly_two = [C.parse_trip(trip(day + timedelta(days=i), stops=2)) for i in range(12)]
    assert C.stops_note(mostly_two) is None


def test_window_is_the_last_week_and_tomorrow_and_a_missing_day_is_not_income():
    today = date(2026, 11, 17)
    v = C.build([ROUTE], [trip(date(2026, 11, 16)), trip(date(2026, 11, 18), tid="recTOMORROW")], today)
    days = v["routes"][0]["days"]
    assert [d["date"] for d in days][0] == "2026-11-18" and days[0]["is_tomorrow"] and days[0]["outcome"] == "yes" and len(days) == 8
    assert v["routes"][0]["this_month"]["income"] == 260.0                     # a "yes" for tomorrow already counts; unanswered days add nothing
    assert v["unanswered_past"] == 5                                           # the six past days minus the answered 16th


def test_income_sources_feed_the_monthly_income_without_a_second_formula():
    today = date(2026, 11, 17)
    srcs = C.income_sources([ROUTE], [trip(date(2026, 11, 9)), trip(date(2026, 11, 10)), trip(date(2026, 11, 11), "no", None, 0)], {"נסיעה"})
    assert [s.name for s in srcs] == ["נסיעה (מדווח יומי)"] and sum(t.amount for t in srcs[0].gross) == 260
    view = cashflow.build(srcs, [], today, 1)
    assert view["months"][-1]["income"]["net"] == 260.0


def test_a_price_change_does_not_rewrite_history():
    route = {**ROUTE, "fields": {**ROUTE["fields"], "Day Price": 150}}
    v = C.build([route], [trip(date(2026, 11, 9), amount=130)], date(2026, 11, 17))
    assert v["routes"][0]["this_month"]["income"] == 130.0


# ── the guard of the two tables ──────────────────────────────────────────────────────────────────────────────────
def test_commute_writes_are_range_checked_and_closed():
    ok = aa.validate_commute_write
    assert ok("Commute Routes", "post", {"Name": "נסיעה", "Day Price": 130, "Status": "active"}) is None
    assert ok("Commute Routes", "post", {"Name": "x"}) and ok("Commute Routes", "patch", {"Day Price": -1}) and ok("Commute Routes", "patch", {"Owner": "x"})
    assert ok("Commute Routes", "patch", {"Planned Days Per Week": 9})
    key = "recAAAAAAAAAAAAAA"
    post = {"Name": "n", "Route": [key], "Trip Date": "2026-11-18", "Outcome": "yes", "Stops": 3, "Amount": 130.0, "Idempotency Key": f"{key}:2026-11-18"}
    assert ok("Commute Trips", "post", post) is None
    assert ok("Commute Trips", "post", {**post, "Idempotency Key": "x"}) and ok("Commute Trips", "post", {**post, "Route": [key, key]}) and ok("Commute Trips", "post", {**post, "Stops": None})
    assert ok("Commute Trips", "patch", {"Outcome": "no", "Amount": 0.0}) is None and ok("Commute Trips", "patch", {"Trip Date": "2026-11-18"})
    assert ok("Commute Trips", "patch", {"Outcome": "maybe"})


def test_both_tables_are_owner_scoped():
    assert policy.is_owner_scoped("Commute Routes") and policy.is_owner_scoped("Commute Trips")


# ── endpoints ────────────────────────────────────────────────────────────────────────────────────────────────────
WRITES: list = []


def ident(uid, role):
    return Identity(user_id=uid, role=role, display_name=uid, tenant_id="boss_hq", domain_id=Domain.GENERAL, allowed_domains=[], channel="telegram", external_id=f"tg-{uid}")


@pytest.fixture
def api(monkeypatch):
    WRITES.clear()
    state = {"routes": [ROUTE], "trips": []}
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    who = ident("eliyahu", Role.OWNER)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": who.user_id})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: True)
    monkeypatch.setattr(service, "my_commute_routes", lambda identity: state["routes"])
    monkeypatch.setattr(service, "my_commute_trips", lambda identity, since=None: state["trips"])
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", lambda action, payload, identity, label: (WRITES.append(payload) or ("a", {"ok": True}, 200)))
    return app, state


def post(app, path, body):
    return app.test_client().post(path, json=body, headers=H)


def test_answering_tomorrow_writes_one_post_with_the_day_price(api):
    app, _ = api
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = post(app, "/api/fcc/commute/day", {"route_id": ROUTE["id"], "date": tomorrow, "outcome": "yes", "stops": 3})
    assert r.status_code == 200 and r.get_json()["state"] == "done" and len(WRITES) == 1
    w = WRITES[0]
    assert w["op"] == "post" and w["table"] == "Commute Trips" and w["fields"]["Amount"] == 130.0 and w["fields"]["Stops"] == 3
    assert w["fields"]["Route"] == [ROUTE["id"]] and w["fields"]["Idempotency Key"] == f"{ROUTE['id']}:{tomorrow}"
    assert aa.validate_commute_write(w["table"], w["op"], w["fields"]) is None


def test_changing_an_answer_patches_the_same_row_and_keeps_the_old_price(api):
    app, state = api
    day = date.today() + timedelta(days=1)
    state["trips"] = [trip(day, "yes", 2, 120, tid="recEXISTINGAAAAAAA")]
    post(app, "/api/fcc/commute/day", {"route_id": ROUTE["id"], "date": day.isoformat(), "outcome": "yes", "stops": 3})
    assert WRITES[0]["op"] == "patch" and WRITES[0]["record_id"] == "recEXISTINGAAAAAAA" and WRITES[0]["fields"]["Amount"] == 120.0 and WRITES[0]["fields"]["Stops"] == 3
    post(app, "/api/fcc/commute/day", {"route_id": ROUTE["id"], "date": day.isoformat(), "outcome": "no"})
    assert WRITES[1]["fields"] == {"Outcome": "no", "Amount": 0.0}


def test_bad_answers_are_refused_before_any_write(api):
    app, state = api
    d = (date.today() + timedelta(days=1)).isoformat()
    for body in ({"route_id": ROUTE["id"], "date": d, "outcome": "yes"}, {"route_id": ROUTE["id"], "date": d, "outcome": "yes", "stops": 5},
                 {"route_id": ROUTE["id"], "date": d, "outcome": "maybe"}, {"route_id": ROUTE["id"], "date": "nope", "outcome": "no"},
                 {"route_id": ROUTE["id"], "date": (date.today() + timedelta(days=3)).isoformat(), "outcome": "no"},
                 {"route_id": ROUTE["id"], "date": (date.today() - timedelta(days=30)).isoformat(), "outcome": "no"}):
        assert post(app, "/api/fcc/commute/day", body).status_code == 400
    assert post(app, "/api/fcc/commute/day", {"route_id": "recSOMEONEELSEAAA", "date": d, "outcome": "no"}).status_code == 404
    state["routes"] = [{**ROUTE, "fields": {**ROUTE["fields"], "Status": "paused"}}]
    assert post(app, "/api/fcc/commute/day", {"route_id": ROUTE["id"], "date": d, "outcome": "no"}).status_code == 404
    assert not WRITES


def test_route_create_and_edit_one_write_each_and_non_owner_gets_404(api, monkeypatch):
    app, _ = api
    assert post(app, "/api/fcc/commute/route", {"name": "נסיעה חדשה", "price": "130", "km_one_way": 22, "minutes_one_way": 35, "planned_days": 6}).get_json()["state"] == "done"
    w = WRITES[0]
    assert w["op"] == "post" and w["fields"]["Day Price"] == 130.0 and w["fields"]["Status"] == "active" and aa.validate_commute_write(w["table"], w["op"], w["fields"]) is None
    post(app, "/api/fcc/commute/route", {"route_id": ROUTE["id"], "cost_per_km": "0.8"})
    assert WRITES[1]["op"] == "patch" and WRITES[1]["fields"] == {"Cost Per Km": 0.8}
    assert post(app, "/api/fcc/commute/route", {"name": "x"}).status_code == 400 and post(app, "/api/fcc/commute/route", {"route_id": "recNOTMINEAAAAAA", "price": 1}).status_code == 404
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: ident("avi", Role.PARTNER))
    assert post(app, "/api/fcc/commute/route", {"name": "x", "price": 1}).status_code == 404
    assert app.test_client().get("/api/fcc/commute", headers=H).status_code == 404
    assert len(WRITES) == 2


def test_the_view_endpoint_returns_routes_days_and_the_month(api):
    app, state = api
    state["trips"] = [trip(date.today(), "yes", 3, 130)]
    v = app.test_client().get("/api/fcc/commute", headers=H).get_json()
    assert v["routes"][0]["economics"]["gross_per_hour"] == 111.43 and len(v["routes"][0]["days"]) == 8 and v["income_this_month"] >= 130.0
