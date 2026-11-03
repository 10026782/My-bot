"""Smart Trips: OrsProvider (OpenRouteService) עם transport מדומה. אין רשת, אין מפתח אמיתי, אין חיוב.

מכסה: פורמט הבקשה, המרת יחידות, בקשת Matrix אחת לכל הרגליים, cache (שינוי מחיר/הסתברות לא שולח בקשה),
429/403/timeout/circuit breaker, מגביל קצב, חלוקה ל-batches, ו-provenance. הנוסחאות הכלכליות לא נבדקות כאן (ראו test_trip_profitability.py).
"""

import logging

import pytest

from core.trips.provider_factory import select_provider
from core.trips.providers.manual import ManualProvider
from core.trips.providers.ors import DEFAULT_BASE_URL, MAX_PAIRS, OrsProvider, TransportError, TransportResponse
from core.trips.route_provider import LegRequest, LegStatus, MatrixRequest, RouteMode
from trip_profitability import compare, order_stops
from trip_profitability.models import Place
from decimal import Decimal

KEY = "test-key-123"


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


def fake_matrix(body):
    """ק"מ = |Δרוחב|+|Δאורך| כפול 100; שניות = ק"מ·36 (מהירות 100 קמ"ש). null לצמד שבו היעד הוא נקודה 0.0,0.0."""
    locations = body["locations"]
    km, seconds = [], []
    for s in body["sources"]:
        row_km, row_sec = [], []
        for d in body["destinations"]:
            (lng1, lat1), (lng2, lat2) = locations[int(s)], locations[int(d)]
            if (lng2, lat2) == (0.0, 0.0):
                row_km.append(None)
                row_sec.append(None)
                continue
            distance = (abs(lat1 - lat2) + abs(lng1 - lng2)) * 100
            row_km.append(round(distance, 3))
            row_sec.append(round(distance * 36, 1))
        km.append(row_km)
        seconds.append(row_sec)
    return {"distances": km, "durations": seconds}


class Transport:
    def __init__(self, handler=None):
        self.calls = []
        self.handler = handler or (lambda body: TransportResponse(200, fake_matrix(body)))

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        return self.handler(body)


def provider(transport=None, clock=None, **kwargs):
    clock = clock or Clock()
    transport = transport or Transport()
    return OrsProvider(KEY, transport=transport, sleep=clock.sleep, clock=clock, **kwargs), transport, clock


def place(lat, lng, label="x"):
    return Place(label, Decimal(str(lat)), Decimal(str(lng)))


def req(a, b, key="outbound", offer="A"):
    return LegRequest(a, b, None, key, offer)


A, B, C = place(31.9, 35.0), place(32.0, 35.1), place(32.6, 35.3)


def offer(oid, pickup, dropoff, fare=450, **extra):
    base = {"id": oid, "pickup": {"lat": float(pickup.lat), "lng": float(pickup.lng)},
            "dropoff": {"lat": float(dropoff.lat), "lng": float(dropoff.lng)}, "outbound_fare_ils": fare}
    base.update(extra)
    return base


def request(*offers, **over):
    body = {"vehicle": {"fuel_price_ils_per_l": 8, "km_per_l": 11}, "origin": {"lat": 31.9, "lng": 35.0},
            "final_destination": {"lat": 31.9, "lng": 35.0}, "offers": list(offers)}
    body.update(over)
    return body


# ── הגדרה ובטיחות ────────────────────────────────────────────────────────────────────────────

def test_without_key_nothing_is_sent():
    transport = Transport()
    ors = OrsProvider(None, transport=transport)
    assert ors.health().ok is False
    assert ors.leg(req(A, B)).status is LegStatus.NOT_CONFIGURED
    assert ors.matrix(MatrixRequest((A, B), None)).status is LegStatus.NOT_CONFIGURED
    ors.prefetch([req(A, B)])
    assert transport.calls == [] and ors.requests_used == 0


def test_from_env_reads_key_and_is_unconfigured_without_it(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    assert OrsProvider.from_env().health().ok is False
    monkeypatch.setenv("ORS_API_KEY", KEY)
    assert OrsProvider.from_env().health().ok is True


def test_mode_is_road_route():
    assert OrsProvider(None).mode is RouteMode.ROAD_ROUTE


# ── פורמט בקשה ותשובה ────────────────────────────────────────────────────────────────────────

def test_request_format_and_unit_conversion():
    ors, transport, _ = provider()
    result = ors.leg(req(A, B))
    url, headers, body, timeout = transport.calls[0]
    assert url == DEFAULT_BASE_URL + "/v2/matrix/driving-car" and "api.heigit.org" in url
    assert headers["Authorization"] == KEY and timeout == 5.0
    assert body["locations"][0] == [35.0, 31.9]                       # [קו אורך, קו רוחב]
    assert body["units"] == "km" and body["metrics"] == ["distance", "duration"]
    assert all(isinstance(i, str) for i in body["sources"] + body["destinations"])
    assert result.ok
    assert result.km == Decimal("20.0")                                # (0.1+0.1)*100
    assert result.minutes == Decimal("12")                             # 20 ק"מ * 36 שניות = 720 שניות = 12 דקות


def test_provenance_states_source_and_no_traffic_and_never_leaks_key():
    ors, _, _ = provider()
    meta = ors.leg(req(A, B)).provenance
    assert meta["source"] == "openrouteservice" and meta["time_basis"] == "free_flow"
    assert meta["accuracy_class"] == "road_free_flow_uncalibrated"
    assert "ללא פקקים" in meta["accuracy_note"] and "OpenStreetMap" in meta["attribution"]
    assert meta["provider_host"] == "api.heigit.org"
    assert KEY not in repr(meta)


def test_identical_points_need_no_request():
    ors, transport, _ = provider()
    result = ors.leg(req(A, A))
    assert result.ok and result.km == 0 and transport.calls == []


def test_text_place_without_coordinates_is_missing_input():
    ors, transport, _ = provider()
    result = ors.leg(req(Place("רב ושמואל"), B))
    assert result.status is LegStatus.MISSING_INPUT and transport.calls == []


# ── בקשה אחת לכל הבדיקה, ו-cache ─────────────────────────────────────────────────────────────

def test_compare_uses_a_single_matrix_request_for_all_legs():
    ors, transport, _ = provider()
    body = request(offer("A", B, C, **{"return": {"probability": 0.3, "fare_ils": 200}}), offer("B", A, C))
    result = compare(body, provider=ors)
    assert ors.requests_used == 1 and len(transport.calls) == 1
    assert all(o["complete"] for o in result["offers"])
    assert result["provider"]["name"] == "ROAD_ROUTE"
    leg = result["offers"][0]["scenarios"][0]["legs"][0]
    assert leg["provenance"]["source"] == "openrouteservice"


def test_changing_price_probability_or_waits_sends_no_new_request():
    ors, transport, _ = provider()
    first = request(offer("A", B, C, **{"return": {"probability": 0.2, "fare_ils": 200, "wait_minutes_success": 10}}))
    compare(first, provider=ors)
    used = ors.requests_used
    changed = request(offer("A", B, C, fare=900, **{"return": {"probability": 0.8, "fare_ils": 50, "wait_minutes_success": 40,
                                                                 "wait_minutes_failure": 25}}),
                      opportunity_cost_ils_per_h=30, vehicle={"fuel_price_ils_per_l": 9, "km_per_l": 8, "wear_ils_per_km": 0.3})
    result = compare(changed, provider=ors)
    assert ors.requests_used == used == 1
    assert result["offers"][0]["complete"] is True


def test_new_point_triggers_a_new_request():
    ors, _, _ = provider()
    compare(request(offer("A", B, C)), provider=ors)
    compare(request(offer("A", B, place(32.5, 35.2))), provider=ors)
    assert ors.requests_used == 2


def test_cache_expires_after_ttl():
    clock = Clock()
    ors, transport, _ = provider(clock=clock)
    ors.leg(req(A, B))
    clock.t += 24 * 3600 + 1
    ors.leg(req(A, B))
    assert len(transport.calls) == 2


def test_batches_never_exceed_pair_limit():
    ors, transport, _ = provider(per_minute=1000, daily_soft_cap=1000)
    origins = [place(31 + i * 0.01, 35.0) for i in range(80)]
    dests = [place(32 + i * 0.01, 35.5) for i in range(80)]
    ors.prefetch([req(a, b) for a in origins for b in dests])
    assert len(transport.calls) >= 2
    for _, _, body, _ in transport.calls:
        assert len(body["sources"]) * len(body["destinations"]) <= MAX_PAIRS
    assert ors.leg(req(origins[79], dests[79])).ok


# ── כשלים ─────────────────────────────────────────────────────────────────────────────────────

def test_429_retries_with_backoff_then_succeeds():
    answers = iter([TransportResponse(429), TransportResponse(429)])

    def handler(body):
        return next(answers, None) or TransportResponse(200, fake_matrix(body))

    ors, transport, clock = provider(Transport(handler))
    assert ors.leg(req(A, B)).ok
    assert len(transport.calls) == 3 and clock.sleeps[:2] == [1, 2]


def test_429_exhausted_is_unavailable_not_estimated():
    ors, transport, _ = provider(Transport(lambda body: TransportResponse(429)))
    result = ors.leg(req(A, B))
    assert result.status is LegStatus.UNAVAILABLE and result.km is None
    assert len(transport.calls) == 3


def test_403_blocks_provider_and_stops_sending():
    ors, transport, clock = provider(Transport(lambda body: TransportResponse(403)))
    first = ors.leg(req(A, B))
    assert first.status is LegStatus.BUDGET_EXCEEDED
    assert ors.health().ok is False
    calls = len(transport.calls)
    assert ors.leg(req(A, C)).status is LegStatus.UNAVAILABLE
    assert len(transport.calls) == calls
    clock.t += 3601
    assert ors.health().ok is True


def test_timeout_retries_once_then_unavailable():
    def handler(body):
        raise TransportError

    ors, transport, _ = provider(Transport(handler))
    assert ors.leg(req(A, B)).status is LegStatus.UNAVAILABLE
    assert len(transport.calls) == 2


def test_circuit_breaker_opens_after_repeated_failures_and_recovers():
    state = {"fail": True}

    def handler(body):
        if state["fail"]:
            return TransportResponse(503)
        return TransportResponse(200, fake_matrix(body))

    clock = Clock()
    ors, transport, _ = provider(Transport(handler), clock=clock)
    ors.leg(req(A, B))
    ors.leg(req(A, C))
    assert ors.health().ok is False
    sent = len(transport.calls)
    assert ors.leg(req(B, C)).status is LegStatus.UNAVAILABLE
    assert len(transport.calls) == sent                       # circuit פתוח: אין שליחה
    state["fail"] = False
    clock.t += 61
    assert ors.health().ok is True
    assert ors.leg(req(B, C)).ok


def test_null_cell_is_no_route_for_that_leg_only():
    ors, _, _ = provider()
    zero = place(0.0, 0.0)
    ors.prefetch([req(A, B), req(A, zero)])
    assert ors.leg(req(A, B)).ok
    assert ors.leg(req(A, zero)).status is LegStatus.NO_ROUTE


@pytest.mark.parametrize("payload", [{"distances": [[1]], "durations": [[1, 2]]}, {"distances": "x"}, {}, {"distances": [[-1]], "durations": [[1]]}])
def test_malformed_response_is_unavailable(payload):
    ors, _, _ = provider(Transport(lambda body: TransportResponse(200, payload)))
    result = ors.leg(req(A, B))
    assert result.status is LegStatus.UNAVAILABLE and result.km is None


def test_bad_request_is_no_route():
    ors, _, _ = provider(Transport(lambda body: TransportResponse(404)))
    assert ors.leg(req(A, B)).status is LegStatus.NO_ROUTE


def test_failure_is_negative_cached_so_legs_do_not_resend():
    ors, transport, _ = provider(Transport(lambda body: TransportResponse(404)))
    compare(request(offer("A", B, C)), provider=ors)
    calls = len(transport.calls)
    assert calls == 1                                         # בקשה אחת, לא בקשה לכל רגל


# ── מגביל קצב ────────────────────────────────────────────────────────────────────────────────

def test_per_minute_limiter_does_not_send_over_budget():
    ors, transport, clock = provider(per_minute=2, max_wait_seconds=0)
    for dest in (B, C):
        assert ors.leg(req(A, dest)).ok
    third = ors.leg(req(B, C))
    assert third.status is LegStatus.BUDGET_EXCEEDED and len(transport.calls) == 2
    clock.t += 61
    assert ors.leg(req(B, C)).ok


def test_limiter_waits_when_short_wait_is_allowed():
    ors, transport, clock = provider(per_minute=1, max_wait_seconds=70)
    assert ors.leg(req(A, B)).ok
    assert ors.leg(req(A, C)).ok
    assert len(transport.calls) == 2 and any(s > 0 for s in clock.sleeps)


def test_daily_soft_cap_blocks_without_sending():
    ors, transport, _ = provider(daily_soft_cap=1, per_minute=1000)
    assert ors.leg(req(A, B)).ok
    result = ors.leg(req(A, C))
    assert result.status is LegStatus.BUDGET_EXCEEDED and len(transport.calls) == 1


# ── בחירת ספק ו-compare ──────────────────────────────────────────────────────────────────────

def test_factory_prefers_healthy_road_provider_and_never_escalates():
    manual, healthy, broken = ManualProvider(), OrsProvider(KEY), OrsProvider(None)
    assert select_provider(None, manual=manual, road=healthy).mode is RouteMode.ROAD_ROUTE
    assert select_provider(None, manual=manual, road=broken).mode is RouteMode.MANUAL
    assert select_provider("ROAD_ROUTE", manual=manual, road=broken).mode is RouteMode.ROAD_ROUTE   # מפורש ולא בריא: תוצאה לא-שלמה
    with pytest.raises(ValueError):
        select_provider("ROAD_ROUTE", manual=manual)
    with pytest.raises(ValueError):
        select_provider("TRAFFIC_AWARE", manual=manual, road=healthy)


def test_manual_legs_win_over_configured_road_provider(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", KEY)
    manual_offer = offer("A", B, C, manual_legs={"to_pickup": {"km": 5, "minutes": 7}, "outbound": {"km": 50, "minutes": 40},
                                                  "home_empty": {"km": 50, "minutes": 40}})
    result = compare(request(manual_offer))
    assert result["provider"]["name"] == "MANUAL" and result["offers"][0]["complete"] is True


def test_explicit_road_route_without_key_is_incomplete_not_estimated(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    result = compare(request(offer("A", B, C), routing_mode="ROAD_ROUTE"))
    assert result["provider"]["name"] == "ROAD_ROUTE"
    assert result["offers"][0]["complete"] is False
    assert result["offers"][0]["warnings"][0]["code"] == "ROUTE_UNAVAILABLE"


def test_default_without_key_and_without_manual_legs_falls_back_to_manual_incomplete(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    result = compare(request(offer("A", B, C)))
    assert result["provider"]["name"] == "MANUAL"
    assert result["offers"][0]["complete"] is False


def test_order_stops_with_road_provider_uses_one_matrix_request():
    ors, transport, _ = provider()
    body = {"start": {"lat": 31.9, "lng": 35.0},
            "stops": [{"id": "s1", "place": {"lat": 32.5, "lng": 35.2}}, {"id": "s2", "place": {"lat": 31.95, "lng": 35.05}},
                      {"id": "s3", "place": {"lat": 32.2, "lng": 35.1}}]}
    result = order_stops(body, provider=ors)
    assert result["complete"] is True and result["provider"]["name"] == "ROAD_ROUTE"
    assert result["best"]["order"] == ["s2", "s3", "s1"]       # לפי הקרבה לאורך הציר
    assert len(transport.calls) == 1


def test_logs_never_contain_key_or_coordinates(caplog):
    caplog.set_level(logging.DEBUG)
    ors, _, _ = provider(Transport(lambda body: TransportResponse(503)))
    for _ in range(3):
        ors.leg(req(A, B))
        ors.leg(req(A, C))
    text = caplog.text
    assert KEY not in text and "35.1" not in text and "31.9" not in text
