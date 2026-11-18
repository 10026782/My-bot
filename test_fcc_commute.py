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
    assert v["unanswered_past"] == 4                                           # the six past days minus the answered 16th and the resting Saturday (14th); Friday is a ride day


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
    state = {"routes": [ROUTE], "trips": [], "settings": []}
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    who = ident("eliyahu", Role.OWNER)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": who.user_id})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: True)
    monkeypatch.setattr(service, "my_commute_routes", lambda identity: state["routes"])
    monkeypatch.setattr(service, "my_commute_trips", lambda identity, since=None: state["trips"])
    monkeypatch.setattr(service, "my_commute_settings", lambda identity: state["settings"])
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


# ── one-off trips, the way back, the leased car's allowance, "on the way", deliveries ───────────────────────────────
SETTINGS = {"id": "recSETTINGSAAAAAA", "fields": {"Free Km Monthly": 1000, "Free Fuel Monthly": 300, "Fuel Cost Per Km": 0.5, "Cost Per Km": 0.8, "Other Km Used": 400, "Other Km Month": "2026-11"}}


FIELD = {"km_one_way": "Km One Way", "minutes_one_way": "Minutes One Way", "return_status": "Return Status", "vehicle_class": "Vehicle Class", "kind": "Kind",
         "extra_km": "Extra Km", "extra_minutes": "Extra Minutes", "on_the_way_of": "On The Way Of", "waiting_minutes": "Waiting Minutes", "start_time": "Start Time"}


def one_off(day: date, price, destination="נתב\"ג", tid=None, **extra):
    f = {"Trip Date": day.isoformat(), "Outcome": "yes", "Amount": price, "Destination": destination, **{FIELD[k]: v for k, v in extra.items()}}
    return {"id": tid or f"recO{destination[:3]}{day.isoformat()}", "fields": f}


def test_the_way_back_decides_what_was_really_driven():
    e = C.ride_economics
    empty = e(220, 50, 40, "empty", 0.0, 0.8)
    assert empty["km"] == 100 and empty["minutes"] == 80 and empty["legs"] == 2 and empty["vehicle_cost"] == 80.0 and empty["net"] == 140.0 and empty["gross_per_km"] == 2.2
    waited = e(220, 50, 40, "waited", 120.0, 0.8)
    assert waited["km"] == 100 and waited["minutes"] == 200 and waited["gross_per_hour"] == 66.0
    cont = e(220, 50, 40, "continuation", 0.0, 0.8)
    assert cont["km"] == 50 and cont["minutes"] == 40 and cont["legs"] == 1 and cont["net"] == 180.0
    assert e(220, None, 40, "empty", 0.0, 0.8)["gross_per_hour"] == 165.0 and e(220, None, 40, "empty", 0.0, 0.8)["gross_per_km"] is None


def test_a_ride_on_the_way_counts_only_what_it_added():
    e = C.ride_economics(150, 30, 25, "empty", 0.0, 0.8, extra_km=6.0, extra_minutes=10.0)
    assert e["km"] == 6.0 and e["minutes"] == 10.0 and e["on_the_way"] and e["gross_per_km"] == 25.0 and e["vehicle_cost"] == 4.8 and e["net"] == 145.2


def test_one_off_trips_are_income_with_their_typed_price_and_profitability_ranks_by_price_per_allowance_km():
    today = date(2026, 11, 17)
    trips = [one_off(date(2026, 11, 3), 220, "נתב\"ג", km_one_way=50, minutes_one_way=40, return_status="empty", vehicle_class="large"),
             one_off(date(2026, 11, 5), 150, "ירושלים", km_one_way=60, minutes_one_way=55, return_status="continuation", vehicle_class="regular"),
             one_off(date(2026, 11, 6), 80, "משלוח חיפה", km_one_way=40, minutes_one_way=40, return_status="empty", kind="delivery"),
             one_off(date(2026, 11, 9), 120, "קיסריה", extra_km=5, extra_minutes=12, on_the_way_of="עבודה", tid="recWAYAAAAAAAAAAA")]
    v = C.build([ROUTE], trips, today, 6, [SETTINGS])
    assert v["one_off"] == {"month": "2026-11", "trips": 4, "income": 570.0} and v["income_this_month"] == 570.0
    rows = {r["destination"]: r for r in v["profitability"]["by_destination"]}
    assert v["profitability"]["by_destination"][0]["destination"] == "קיסריה" and rows["קיסריה"]["gross_per_km"] == 24.0       # on the way: 120 for the 5 added km
    assert rows["נתב\"ג"]["gross_per_km"] == 2.2 and rows["נתב\"ג"]["net_per_hour"] == 105.0 and rows["ירושלים"]["gross_per_km"] == 2.5          # the paid return makes it ONE way
    assert [c["class"] for c in v["profitability"]["by_class"]] == ["regular", "large"] and {k["kind"] for k in v["profitability"]["by_kind"]} == {"ride", "delivery"}
    assert [w["on_the_way"] for w in v["profitability"]["by_way"]] == [True, False]
    assert {t["one_off"] for t in v["trips"]} == {True} and v["trips"][0]["on_the_way_of"] == "עבודה"
    srcs = C.income_sources([ROUTE], [one_off(date(2026, 11, 3), 220)], set())
    assert [s.name for s in srcs] == ["נסיעות נוספות"] and srcs[0].gross[0].amount == 220


def test_the_free_allowance_is_what_is_left_after_other_driving_and_the_rides():
    today = date(2026, 11, 17)
    trips = [one_off(date(2026, 11, 3), 220, "נתב\"ג", km_one_way=50, minutes_one_way=40, return_status="empty"), one_off(date(2026, 11, 4), 90, "בלי ק\"מ")]
    q = C.build([ROUTE], trips, today, 6, [SETTINGS])["quota"]
    assert q["allowed_km"] == 600.0 and q["fuel_km"] == 600.0 and q["free_km"] == 1000                # the fuel allowance (300 / 0.5) is the tighter one
    assert q["other_km"] == 400.0 and q["rides_km"] == 100.0 and q["used_km"] == 500.0 and q["remaining_km"] == 100.0 and q["over_km"] == 0.0
    assert q["rides_without_km"] == 1 and q["avg_per_km"] == 2.2 and q["worth_of_remaining"] == 220.0 and q["days_left"] == 14
    stale = C.build([ROUTE], [], today, 6, [{**SETTINGS, "fields": {**SETTINGS["fields"], "Other Km Month": "2026-10"}}])["quota"]
    assert stale["other_km"] == 0.0 and stale["other_km_stale"] is True and stale["remaining_km"] == 600.0     # a new month starts from zero
    assert C.build([ROUTE], [], today, 6, [])["quota"] is None
    noconv = C.build([ROUTE], [], today, 6, [{"id": "r", "fields": {"Free Fuel Monthly": 300}}])["quota"]
    assert noconv["allowed_km"] is None and "עלות דלק" in noconv["fuel_note"]


def test_own_weekly_drives_are_listed_apart_and_are_never_income_or_a_paid_route():
    own = {"id": "recOWNAAAAAAAAAAA", "fields": {"Name": "עבודה", "Route Kind": "own", "Weekdays": ["ראשון", "שלישי"], "Km One Way": 30, "Minutes One Way": 25}}
    v = C.build([ROUTE, own], [], date(2026, 11, 17), 6, [])
    assert [r["name"] for r in v["routes"]] == ["נסיעה"] and v["own_trips"] == [{"id": own["id"], "name": "עבודה", "weekdays": ["ראשון", "שלישי"], "km_one_way": 30.0, "minutes_one_way": 25.0}]


def test_the_new_shapes_pass_the_guard_and_bad_ones_do_not():
    ok = aa.validate_commute_write
    base = {"Name": "x", "Trip Date": "2026-11-18", "Outcome": "yes", "Amount": 220.0, "Destination": "נתב\"ג", "Idempotency Key": "oneoff:0123456789abcdef"}
    assert ok("Commute Trips", "post", base) is None and ok("Commute Trips", "post", {**base, "Kind": "delivery", "Extra Km": 5.0, "Extra Minutes": 12.0, "On The Way Of": "עבודה", "Return Status": "waited", "Waiting Minutes": 90.0}) is None
    assert ok("Commute Trips", "post", {**base, "Kind": "taxi"}) and ok("Commute Trips", "post", {**base, "Idempotency Key": "oneoff:xyz"}) and ok("Commute Trips", "post", {**base, "Return Status": "later"})
    assert ok("Commute Trips", "post", {**base, "Outcome": "no"}) and ok("Commute Trips", "post", {k: v for k, v in base.items() if k != "Amount"})
    assert ok("Commute Trips", "patch", {"Amount": 200.0, "Extra Km": 4.0}) is None
    assert ok("Commute Routes", "post", {"Name": "עבודה", "Route Kind": "own", "Weekdays": ["ראשון"], "Km One Way": 30}) is None and ok("Commute Routes", "post", {"Name": "x", "Weekdays": ["monday"]})
    assert ok("Commute Settings", "post", {"Name": "הגדרות רכב", "Free Km Monthly": 1000, "Other Km Used": 400, "Other Km Month": "2026-11"}) is None
    assert ok("Commute Settings", "post", {"Name": "x", "Other Km Month": "2026-13"}) and ok("Commute Settings", "patch", {"Owner": "x"}) and ok("Commute Settings", "patch", {"Free Km Monthly": -5})
    assert policy.is_owner_scoped("Commute Settings")


def test_one_off_trip_endpoint_one_write_edit_and_refusals(api):
    app, state = api
    out = post(app, "/api/fcc/commute/trip", {"destination": "נתב\"ג", "price": "220", "vehicle_class": "large", "km_one_way": 50, "minutes_one_way": 40, "return_status": "empty"})
    assert out.status_code == 200 and len(WRITES) == 1
    w = WRITES[0]
    assert w["op"] == "post" and w["fields"]["Amount"] == 220.0 and w["fields"]["Outcome"] == "yes" and w["fields"]["Idempotency Key"].startswith("oneoff:") and "Route" not in w["fields"]
    assert aa.validate_commute_write(w["table"], w["op"], w["fields"]) is None
    post(app, "/api/fcc/commute/trip", {"destination": "משלוח", "price": 80, "kind": "delivery", "extra_km": 4, "extra_minutes": 9, "on_the_way_of": "עבודה"})
    assert WRITES[1]["fields"]["Kind"] == "delivery" and WRITES[1]["fields"]["Extra Km"] == 4.0 and WRITES[1]["fields"]["On The Way Of"] == "עבודה"
    state["trips"] = [one_off(date.today(), 100, "ישן", tid="recMINEAAAAAAAAAA"), trip(date.today(), tid="recROUTEDAYAAAAAA")]
    post(app, "/api/fcc/commute/trip", {"trip_id": "recMINEAAAAAAAAAA", "price": 120})
    assert WRITES[2]["op"] == "patch" and WRITES[2]["fields"] == {"Amount": 120.0}
    for body, code in (({"destination": "x"}, 400), ({"price": 5}, 400), ({"destination": "x", "price": "abc"}, 400), ({"destination": "x", "price": 5, "date": "2020-01-01"}, 400),
                       ({"destination": "x", "price": 5, "kind": "taxi"}, 400), ({"trip_id": "recROUTEDAYAAAAAA", "price": 5}, 404), ({"trip_id": "recNOTMINEAAAAAAA", "price": 5}, 404)):
        assert post(app, "/api/fcc/commute/trip", body).status_code == code, body
    assert len(WRITES) == 3


def test_settings_endpoint_creates_then_patches_and_stamps_the_month(api):
    app, state = api
    post(app, "/api/fcc/commute/settings", {"free_km": 1000, "free_fuel": 300, "fuel_cost_per_km": "0.5", "other_km_used": 400})
    w = WRITES[0]
    assert w["op"] == "post" and w["table"] == "Commute Settings" and w["fields"]["Free Km Monthly"] == 1000.0 and w["fields"]["Other Km Month"] == date.today().strftime("%Y-%m")
    assert aa.validate_commute_write(w["table"], w["op"], w["fields"]) is None
    state["settings"] = [SETTINGS]
    post(app, "/api/fcc/commute/settings", {"cost_per_km": 0.9})
    assert WRITES[1]["op"] == "patch" and WRITES[1]["record_id"] == SETTINGS["id"] and WRITES[1]["fields"] == {"Cost Per Km": 0.9}
    assert post(app, "/api/fcc/commute/settings", {}).status_code == 400 and post(app, "/api/fcc/commute/settings", {"free_km": -1}).status_code == 400


def test_an_own_weekly_drive_is_created_without_a_price_and_cannot_be_answered_as_a_ride(api):
    app, state = api
    post(app, "/api/fcc/commute/route", {"name": "עבודה", "route_kind": "own", "weekdays": ["ראשון", "שלישי"], "km_one_way": 30, "minutes_one_way": 25})
    w = WRITES[0]
    assert w["op"] == "post" and w["fields"]["Route Kind"] == "own" and w["fields"]["Weekdays"] == ["ראשון", "שלישי"] and "Day Price" not in w["fields"]
    assert aa.validate_commute_write(w["table"], w["op"], w["fields"]) is None
    state["routes"] = [{"id": "recOWNAAAAAAAAAAA", "fields": {"Name": "עבודה", "Route Kind": "own"}}]
    assert post(app, "/api/fcc/commute/day", {"route_id": "recOWNAAAAAAAAAAA", "date": (date.today() + timedelta(days=1)).isoformat(), "outcome": "no"}).status_code == 404


# ── time of day: the same ride at different hours ─────────────────────────────────────────────────────────────────
def test_start_time_falls_in_a_band_and_a_bad_time_is_none():
    assert C.band_of("07:30") == "morning_rush" and C.band_of("06:00") == "morning_rush" and C.band_of("09:29") == "morning_rush" and C.band_of("09:30") == "midday"
    assert C.band_of("17:45") == "evening_rush" and C.band_of("23:59") == "evening" and C.band_of("00:00") == "night" and C.band_of("5") is None and C.band_of(None) is None and C.band_of("24:00") is None


def test_the_same_destination_is_compared_across_the_hours_and_a_thin_sample_says_nothing():
    today = date(2026, 11, 17)
    def ride(day, price, minutes, start, dest="תל אביב"):
        return one_off(date(2026, 11, day), price, dest, km_one_way=30, minutes_one_way=minutes, return_status="continuation", start_time=start)
    trips = [ride(2, 150, 30, "11:00"), ride(3, 150, 28, "11:30"), ride(4, 150, 60, "08:00"), ride(5, 150, 66, "07:45"), ride(6, 150, 40, "20:00", "חיפה")]
    p = C.build([ROUTE], trips, today, 6, [SETTINGS])["profitability"]
    assert [t["label"] for t in p["by_time"]] == ["בוקר (שעת עומס)", "צהריים", "ערב"] and p["by_time"][0]["avg_minutes"] == 63.0 and p["without_time"] == 0
    (ins,) = p["time_insights"]                                                # חיפה has one ride in one band: nothing to compare
    assert ins["destination"] == "תל אביב" and ins["fastest"] == "midday" and ins["slowest"] == "morning_rush" and ins["extra_minutes"] == 34.0
    by = {b["band"]: b for b in ins["bands"]}
    assert by["midday"]["gross_per_hour"] == 310.34 and by["morning_rush"]["gross_per_hour"] == 142.86           # 150 / 29 min vs 150 / 63 min
    one_each = C.build([ROUTE], [ride(2, 150, 30, "11:00"), ride(4, 150, 60, "08:00")], today, 6, [])["profitability"]
    assert one_each["time_insights"] == []                                      # one ride per band is an anecdote, not a pattern
    flat = C.build([ROUTE], [ride(2, 150, 30, "11:00"), ride(3, 150, 31, "11:10"), ride(4, 150, 32, "08:00"), ride(5, 150, 33, "08:30")], today, 6, [])["profitability"]
    assert flat["time_insights"] == []                                          # a difference of under 20% is not worth saying


def test_start_time_is_validated_and_travels_through_the_endpoints(api):
    app, _ = api
    ok = aa.validate_commute_write
    assert ok("Commute Trips", "patch", {"Start Time": "07:45"}) is None and ok("Commute Trips", "patch", {"Start Time": "7:45"}) and ok("Commute Routes", "patch", {"Start Time": "25:00"})
    assert ok("Commute Routes", "patch", {"Start Time": "06:30"}) is None
    post(app, "/api/fcc/commute/trip", {"destination": "תל אביב", "price": 150, "start_time": "07:45", "km_one_way": 30, "minutes_one_way": 60})
    assert WRITES[0]["fields"]["Start Time"] == "07:45"
    assert post(app, "/api/fcc/commute/trip", {"destination": "x", "price": 1, "start_time": "7pm"}).status_code == 400
    post(app, "/api/fcc/commute/route", {"route_id": ROUTE["id"], "start_time": "06:30"})
    assert WRITES[1]["fields"] == {"Start Time": "06:30"}


# ── an offer, priced before it is taken; what happened on the way back, learned over time ─────────────────────────
def known(day, dest, status, wait=0, price=150, km=30, minutes=40, **extra):
    return one_off(date(2026, 11, day), price, dest, km_one_way=km, minutes_one_way=minutes, return_status=status, waiting_minutes=wait, **extra)


def test_return_stats_count_only_what_the_owner_recorded_and_pending_trips_wait_for_him():
    trips = [C.parse_trip(t) for t in (known(2, "נתב\"ג", "empty"), known(3, "נתב\"ג", "continuation"), known(4, "נתב\"ג", "waited", 120), known(5, "נתב\"ג", "waited", 60),
                                       one_off(date(2026, 11, 6), 200, "נתב\"ג", km_one_way=50, minutes_one_way=40, tid="recPENDINGAAAAAAA"))]
    st = C.return_stats(trips)
    assert st["overall"] == {"known": 4, "empty": 1, "continuation": 1, "waited": 2, "avg_wait_minutes": 90.0}
    assert st["by_destination"]["נתב\"ג"]["known"] == 4
    pend = C.pending_updates(trips, date(2026, 11, 17))
    assert [p["id"] for p in pend] == ["recPENDINGAAAAAAA"] and pend[0]["price"] == 200 and C.pending_updates(trips, date(2027, 3, 1)) == []


def test_an_offer_is_priced_under_each_way_back_with_no_invented_expectation_on_a_thin_history():
    today = date(2026, 11, 17)
    r = C.evaluate_offer({"price": 220, "km_one_way": 50, "minutes_one_way": 40, "destination": "נתב\"ג", "waiting_minutes": 120}, [ROUTE], [], today, [SETTINGS])
    by = {s["key"]: s for s in r["scenarios"]}
    assert by["empty"]["km"] == 100 and by["empty"]["gross_per_km"] == 2.2 and by["continuation"]["km"] == 50 and by["continuation"]["gross_per_km"] == 4.4
    assert by["waited"]["minutes"] == 200 and by["waited"]["gross_per_hour"] == 66.0 and by["empty"]["net"] == 140.0
    assert r["expected"] is None and r["basis"]["used"] is None and any("אין מספיק היסטוריה" in n for n in r["notes"])


def test_the_expected_figure_comes_from_the_destinations_own_history_else_the_overall_one():
    today = date(2026, 11, 17)
    hist = [known(d, "נתב\"ג", st, 60 if st == "waited" else 0) for d, st in zip(range(1, 11), ["empty", "empty", "empty", "continuation", "continuation", "waited", "empty", "continuation", "empty", "waited"])]
    r = C.evaluate_offer({"price": 200, "km_one_way": 50, "minutes_one_way": 40, "destination": "נתב\"ג"}, [ROUTE], hist, today, [SETTINGS])
    assert r["basis"]["used"] == "destination" and r["basis"]["destination_sample"] == 10 and r["basis"]["weights"] == {"empty": 0.5, "continuation": 0.3, "waited": 0.2}
    e = r["expected"]
    assert e["km"] == 0.5 * 100 + 0.3 * 50 + 0.2 * 100 == 85.0 and e["minutes"] == round(0.5 * 80 + 0.3 * 40 + 0.2 * 140, 2) and e["gross_per_km"] == round(200 / 85, 2)
    assert r["average"]["rides"] == 10 and r["vs_average"]["per_km"] is not None
    other = C.evaluate_offer({"price": 200, "km_one_way": 50, "minutes_one_way": 40, "destination": "מקום חדש"}, [ROUTE], hist, today, [SETTINGS])
    assert other["basis"]["used"] == "overall" and other["basis"]["destination_sample"] == 0 and other["expected"] is not None          # 10 known outcomes overall


def test_an_offer_shows_what_it_uses_of_the_allowance_and_the_part_beyond_it():
    today = date(2026, 11, 17)
    settings = [{"id": "r", "fields": {**SETTINGS["fields"], "Other Km Used": 560, "Free Fuel Monthly": None}}]            # 1000 allowed, 560 used -> 440 left
    r = C.evaluate_offer({"price": 300, "km_one_way": 300, "minutes_one_way": 200}, [ROUTE], [], today, settings)
    empty = {s["key"]: s for s in r["scenarios"]}["empty"]
    assert r["allowance_remaining_km"] == 440.0 and empty["km"] == 600 and empty["free_km"] == 440.0 and empty["beyond_km"] == 160.0 and empty["cost_beyond"] == 128.0 and empty["net_after_allowance"] == 172.0
    cont = {s["key"]: s for s in r["scenarios"]}["continuation"]
    assert cont["beyond_km"] == 0.0 and cont["net_after_allowance"] == 300.0                                                  # a paid way back: 300 km all inside the allowance


def test_a_detour_offer_counts_only_what_it_adds_and_the_typical_minutes_at_the_hour_are_shown_when_known():
    today = date(2026, 11, 17)
    r = C.evaluate_offer({"price": 120, "extra_km": 5, "extra_minutes": 12, "km_one_way": 30, "minutes_one_way": 25}, [ROUTE], [], today, [SETTINGS])
    (sc,) = r["scenarios"]
    assert sc["key"] == "on_the_way" and sc["km"] == 5 and sc["gross_per_km"] == 24.0 and r["expected"] == sc
    hist = [known(2, "ת\"א", "empty", minutes=60, start_time="07:45"), known(3, "ת\"א", "empty", minutes=70, start_time="08:00"), known(4, "ת\"א", "empty", minutes=30, start_time="11:00")]
    t = C.evaluate_offer({"price": 150, "km_one_way": 30, "minutes_one_way": 40, "destination": "ת\"א", "start_time": "07:30"}, [ROUTE], hist, today, [SETTINGS])
    assert t["typical_at_this_hour"] == {"band": "בוקר (שעת עומס)", "rides": 2, "avg_minutes_one_way": 65.0}


def test_the_build_lists_the_trips_waiting_for_an_update_and_the_return_history(api):
    app, state = api
    state["trips"] = [known(d, "נתב\"ג", "empty") for d in (1, 2)] + [one_off(date.today(), 100, "ממתין", km_one_way=20, minutes_one_way=20, tid="recWAITINGAAAAAAA")]
    v = app.test_client().get("/api/fcc/commute", headers=H).get_json()
    assert [p["id"] for p in v["pending_updates"]] == ["recWAITINGAAAAAAA"] and v["return_stats"]["overall"]["known"] == 2 and v["return_stats"]["by_destination"][0]["destination"] == "נתב\"ג"


def test_evaluate_endpoint_is_read_only_validated_and_owner_only(api, monkeypatch):
    app, state = api
    state["trips"] = [known(d, "נתב\"ג", "empty") for d in range(1, 8)]
    ok = post(app, "/api/fcc/commute/evaluate", {"price": "220", "km_one_way": 50, "minutes_one_way": 40, "destination": "נתב\"ג", "start_time": "07:30"})
    body = ok.get_json()
    assert ok.status_code == 200 and not WRITES and [s["key"] for s in body["scenarios"]][:2] == ["empty", "continuation"] and body["basis"]["destination_sample"] == 7
    for bad in ({}, {"price": 0}, {"price": "x"}, {"price": 5, "km_one_way": -1}, {"price": 5, "start_time": "7pm"}, {"price": 5, "minutes_one_way": 99999}):
        assert post(app, "/api/fcc/commute/evaluate", bad).status_code == 400, bad
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: ident("avi", Role.PARTNER))
    assert post(app, "/api/fcc/commute/evaluate", {"price": 5}).status_code == 404 and not WRITES


# ── where (city / area) and extra stops ───────────────────────────────────────────────────────────────────────────
def trip_at(day, price, city, area, km=20, minutes=25, status="empty", **fields):
    t = one_off(date(2026, 11, day), price, f"{city} {area or ''}".strip(), km_one_way=km, minutes_one_way=minutes, return_status=status)
    t["fields"].update({"City": city, **({"Area": area} if area else {}), **fields})
    return t


def test_a_cities_and_areas_profitability_are_read_apart():
    today = date(2026, 11, 17)
    trips = [trip_at(1, 120, "ירושלים", "כניסה לעיר", 15, 20), trip_at(2, 130, "ירושלים", "כניסה לעיר", 15, 20), trip_at(3, 160, "ירושלים", "הר חומה", 40, 55), trip_at(4, 150, "תל אביב", None, 30, 40)]
    p = C.build([ROUTE], trips, today, 6, [SETTINGS])["profitability"]
    cities = {r["city"]: r for r in p["by_city"]}
    areas = {(r["city"], r["area"]): r for r in p["by_area"]}
    assert cities["ירושלים"]["rides"] == 3 and cities["תל אביב"]["rides"] == 1 and set(areas) == {("ירושלים", "כניסה לעיר"), ("ירושלים", "הר חומה")}
    assert areas[("ירושלים", "כניסה לעיר")]["gross_per_km"] == 4.17 and areas[("ירושלים", "הר חומה")]["gross_per_km"] == 2.0           # 250 / 60 km vs 160 / 80 km
    assert p["by_area"][0]["area"] == "כניסה לעיר" and p["without_place"] == 0


def test_the_way_back_is_read_from_the_area_then_the_city_then_the_overall_history():
    today = date(2026, 11, 17)
    entrance = [trip_at(d, 100, "ירושלים", "כניסה לעיר", status="continuation") for d in range(1, 7)]
    remote = [trip_at(d, 100, "ירושלים", "הר חומה", status="empty") for d in range(7, 13)]
    hist = entrance + remote
    area = C.evaluate_offer({"price": 200, "km_one_way": 20, "minutes_one_way": 25, "city": "ירושלים", "area": "כניסה לעיר"}, [ROUTE], hist, today, [SETTINGS])
    assert area["basis"]["used"] == "area" and area["basis"]["sample"] == 6 and area["basis"]["weights"]["continuation"] == 1.0
    far = C.evaluate_offer({"price": 200, "km_one_way": 20, "minutes_one_way": 25, "city": "ירושלים", "area": "הר חומה"}, [ROUTE], hist, today, [SETTINGS])
    assert far["basis"]["used"] == "area" and far["basis"]["weights"]["empty"] == 1.0
    city = C.evaluate_offer({"price": 200, "km_one_way": 20, "minutes_one_way": 25, "city": "ירושלים", "area": "שכונה חדשה"}, [ROUTE], hist, today, [SETTINGS])
    assert city["basis"]["used"] == "city" and city["basis"]["sample"] == 12 and city["basis"]["weights"] == {"empty": 0.5, "continuation": 0.5, "waited": 0.0}
    assert area["place"]["level"] == "area" and area["place"]["rides"] == 6 and city["place"]["level"] == "city" and city["place"]["rides"] == 12     # an area with no rides falls back to the city


def test_extra_stops_add_their_own_km_and_minutes_and_show_what_they_earned_on_their_own():
    e = C.ride_economics(200, 20, 25, "empty", 0.0, 0.8, None, None, stops_km=8.0, stops_minutes=30.0, stops_price=40.0)
    assert e["km"] == 48.0 and e["minutes"] == 80.0                                             # 40 km + 8, 50 min + 30
    assert e["stops_per_hour"] == 80.0 and e["stops_per_km"] == 5.0                              # 40 / 0.5 h, 40 / 8 km
    assert e["base_gross_per_hour"] == 192.0 and e["gross_per_hour"] == 150.0                    # without the stops 160 / (50/60) h; with them 200 / (80/60) h
    plain = C.ride_economics(200, 20, 25, "empty", 0.0, 0.8)
    assert plain["stops_per_hour"] is None and plain["base_gross_per_hour"] == plain["gross_per_hour"]


def test_a_stop_in_the_rush_hour_is_compared_with_a_stop_at_other_times():
    today = date(2026, 11, 17)
    def stopped(day, start, minutes):
        return trip_at(day, 200, "ירושלים", "מרכז", 20, 25, **{"Added Stops": 1, "Stops Price": 30, "Stops Km": 5, "Stops Minutes": minutes, "Start Time": start})
    trips = [stopped(1, "08:00", 40), stopped(2, "07:45", 36), stopped(3, "11:00", 15), stopped(4, "12:00", 17)]
    st = C.build([ROUTE], trips, today, 6, [SETTINGS])["profitability"]["stops"]
    assert st["rides"] == 4 and st["stops"] == 4 and st["avg_price"] == 30.0 and st["avg_minutes_per_stop"] == 27.0
    by = {b["band"]: b for b in st["by_band"]}
    assert by["morning_rush"]["avg_minutes_per_stop"] == 38.0 and by["midday"]["avg_minutes_per_stop"] == 16.0 and by["morning_rush"]["per_hour"] == 47.37
    assert st["note"] == "תחנה בשעת עומס לוקחת בממוצע 38.0 דק׳ לעומת 16.0 דק׳ בשעות אחרות"
    assert C.build([ROUTE], [trip_at(1, 100, "חיפה", None)], today, 6, [])["profitability"]["stops"] is None


def test_an_offer_with_stops_shows_the_stops_on_their_own_and_the_whole_ride_with_and_without_them():
    today = date(2026, 11, 17)
    r = C.evaluate_offer({"price": 200, "km_one_way": 20, "minutes_one_way": 25, "added_stops": 1, "stops_price": 40, "stops_km": 8, "stops_minutes": 30, "start_time": "08:00"}, [ROUTE], [], today, [SETTINGS])
    s = r["stops"]
    assert s["added"] == 1 and s["per_hour"] == 80.0 and s["per_km"] == 5.0 and s["base_gross_per_hour"] == 192.0 and s["total_gross_per_hour"] == 150.0 and s["band"] == "בוקר (שעת עומס)"
    assert C.evaluate_offer({"price": 200, "km_one_way": 20, "minutes_one_way": 25}, [ROUTE], [], today, [SETTINGS])["stops"] is None


def test_where_and_stops_pass_the_guard_and_travel_through_the_endpoints(api):
    app, _ = api
    ok = aa.validate_commute_write
    base = {"Name": "x", "Trip Date": "2026-11-18", "Outcome": "yes", "Amount": 200.0, "Destination": "ירושלים", "Idempotency Key": "oneoff:0123456789abcdef"}
    assert ok("Commute Trips", "post", {**base, "City": "ירושלים", "Area": "הר חומה", "Added Stops": 2, "Stops Price": 40.0, "Stops Km": 8.0, "Stops Minutes": 30.0}) is None
    assert ok("Commute Trips", "post", {**base, "Stops Price": 250.0}) and ok("Commute Trips", "post", {**base, "Added Stops": 50}) and ok("Commute Trips", "post", {**base, "City": "  "})
    post(app, "/api/fcc/commute/trip", {"destination": "ירושלים", "price": 200, "city": "ירושלים", "area": "הר חומה", "added_stops": 1, "stops_price": 40, "stops_km": 8, "stops_minutes": 30})
    f = WRITES[0]["fields"]
    assert f["City"] == "ירושלים" and f["Area"] == "הר חומה" and f["Added Stops"] == 1.0 and f["Stops Price"] == 40.0 and aa.validate_commute_write("Commute Trips", "post", f) is None
    assert post(app, "/api/fcc/commute/trip", {"destination": "x", "price": 100, "stops_price": 150}).status_code == 400
    ev = post(app, "/api/fcc/commute/evaluate", {"price": 200, "km_one_way": 20, "minutes_one_way": 25, "city": "ירושלים", "area": "הר חומה", "added_stops": 1, "stops_price": 40, "stops_km": 8, "stops_minutes": 30})
    assert ev.status_code == 200 and ev.get_json()["stops"]["per_hour"] == 80.0 and not WRITES[1:]
    assert post(app, "/api/fcc/commute/evaluate", {"price": 100, "stops_price": 150}).status_code == 400


# ── a recurring-route day timed afterwards: when it left and how long one way took that day ───────────────────────
def timed_day(day, minutes, start, stops=2):
    t = trip(day, "yes", stops, 130)
    t["fields"].update({"Minutes One Way": minutes, "Start Time": start})
    return t


def test_a_route_day_uses_its_own_minutes_and_hour_and_the_route_compares_the_hours():
    today = date(2026, 11, 18)
    days = [timed_day(date(2026, 11, 1), 60, "07:30"), timed_day(date(2026, 11, 2), 66, "07:45"), timed_day(date(2026, 11, 3), 30, "11:00"), timed_day(date(2026, 11, 4), 28, "11:15"),
            trip(date(2026, 11, 5), "yes", 3, 130)]
    v = C.build([ROUTE], days, today, 6, [SETTINGS])
    month = v["routes"][0]["this_month"]
    assert month["timed_days"] == 4 and month["avg_minutes_one_way"] == 46.0 and month["yes_days"] == 5
    (ins,) = v["profitability"]["time_insights"]
    assert ins["destination"] == "נסיעה" and ins["slowest"] == "morning_rush" and ins["fastest"] == "midday" and ins["extra_minutes"] == 68.0      # the whole ride (there and back): 126 vs 58 minutes
    by = {t["date"]: t for t in v["trips"]}
    assert by["2026-11-01"]["minutes"] == 120 and by["2026-11-03"]["minutes"] == 60 and by["2026-11-05"]["minutes"] == 70          # a day without a time keeps the route's 35 x 2
    day1 = next(d for d in C.build([ROUTE], days, date(2026, 11, 3), 6, [SETTINGS])["routes"][0]["days"] if d["date"] == "2026-11-03")
    assert day1["start_time"] == "11:00" and day1["minutes_one_way"] == 30.0


def test_the_day_endpoint_takes_the_hour_and_minutes_for_a_ride_that_happened_and_keeps_the_answer(api):
    app, state = api
    day = date.today() - timedelta(days=1)
    state["trips"] = [trip(day, "yes", 2, 120, tid="recEXISTINGAAAAAAA")]
    ok = post(app, "/api/fcc/commute/day", {"route_id": ROUTE["id"], "date": day.isoformat(), "outcome": "yes", "stops": 2, "start_time": "07:45", "minutes_one_way": "55"})
    assert ok.status_code == 200
    w = WRITES[0]
    assert w["op"] == "patch" and w["fields"] == {"Outcome": "yes", "Stops": 2, "Amount": 120.0, "Start Time": "07:45", "Minutes One Way": 55.0}
    assert aa.validate_commute_write(w["table"], w["op"], w["fields"]) is None
    new_day = date.today() - timedelta(days=2)
    post(app, "/api/fcc/commute/day", {"route_id": ROUTE["id"], "date": new_day.isoformat(), "outcome": "yes", "stops": 3, "minutes_one_way": 40})
    assert WRITES[1]["op"] == "post" and WRITES[1]["fields"]["Minutes One Way"] == 40.0 and "Start Time" not in WRITES[1]["fields"] and aa.validate_commute_write("Commute Trips", "post", WRITES[1]["fields"]) is None
    for bad in ({"start_time": "7pm"}, {"start_time": "7:45"}, {"minutes_one_way": 0}, {"minutes_one_way": "x"}, {"minutes_one_way": 5000}):
        assert post(app, "/api/fcc/commute/day", {"route_id": ROUTE["id"], "date": day.isoformat(), "outcome": "yes", "stops": 2, **bad}).status_code == 400, bad
    post(app, "/api/fcc/commute/day", {"route_id": ROUTE["id"], "date": day.isoformat(), "outcome": "no", "start_time": "07:45", "minutes_one_way": 55})
    assert WRITES[2]["fields"] == {"Outcome": "no", "Amount": 0.0}              # a day without a ride has no hour or minutes
    assert len(WRITES) == 3
