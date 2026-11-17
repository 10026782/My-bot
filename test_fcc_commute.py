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
         "extra_km": "Extra Km", "extra_minutes": "Extra Minutes", "on_the_way_of": "On The Way Of", "waiting_minutes": "Waiting Minutes"}


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
