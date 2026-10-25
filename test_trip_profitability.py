"""Smart Trips C1: מנוע כדאיות, ספקי ניתוב (MANUAL + stubs) וסדר תחנות. חישוב טהור: בלי רשת/Airtable/LLM.

המספרים ב-GOLDEN הם הדוגמה של SMART_TRIPS_P0_CALCULATION_CONTRACT.md §10 (להמחשה בלבד, לא מחיר שוק).
"""

import copy
import itertools
from decimal import Decimal

import pytest

from core.trips.provider_factory import select_provider
from core.trips.providers.local_route import LocalRouteProvider
from core.trips.providers.manual import ManualProvider
from core.trips.providers.traffic_aware import TrafficAwareProvider
from core.trips.route_provider import LegRequest, LegStatus, MatrixRequest, RouteMode
from trip_profitability import compare, order_stops
from trip_profitability import economics as eco

VEHICLE = {"fuel_price_ils_per_l": 7.5, "km_per_l": 12, "wear_ils_per_km": 0.30}
KM_COST = 7.5 / 12 + 0.30   # 0.925 ש"ח לק"מ


def leg(km, minutes):
    return {"km": km, "minutes": minutes}


def offer_a(p=0.3, **over):
    base = {
        "id": "A", "pickup": {"text": "איסוף"}, "dropoff": {"text": "אשדוד"}, "outbound_fare_ils": 230, "service_minutes": 15,
        "return": {"probability": p, "fare_ils": 200, "wait_minutes_success": 40, "wait_minutes_failure": 30},
        "manual_legs": {"to_pickup": leg(10, 15), "outbound": leg(40, 40), "home_empty": leg(40, 40), "return_loaded": leg(40, 40)},
    }
    base.update(over)
    return base


def offer_b(p=0.5):
    return {
        "id": "B", "pickup": {"text": "איסוף"}, "dropoff": {"text": "ירושלים"}, "outbound_fare_ils": 150, "service_minutes": 15,
        "return": {"probability": p, "fare_ils": 120, "wait_minutes_success": 25, "wait_minutes_failure": 20},
        "manual_legs": {"to_pickup": leg(10, 15), "outbound": leg(65, 60), "home_empty": leg(65, 60), "return_loaded": leg(65, 60)},
    }


def request(*offers, **over):
    body = {"vehicle": VEHICLE, "origin": {"text": "מוצא"}, "final_destination": {"text": "בית"},
            "opportunity_cost_ils_per_h": 40, "offers": list(offers)}
    body.update(over)
    return body


def by_id(result, offer_id):
    return next(o for o in result["offers"] if o["id"] == offer_id)


# ── דוגמת golden (§10) ───────────────────────────────────────────────────────────────────────

def test_golden_two_offers():
    result = compare(request(offer_a(), offer_b()))
    a, b = by_id(result, "A"), by_id(result, "B")
    assert a["expected"] == {"contribution": 206.75, "minutes": 143, "throughput": 86.75, "per_hour_avg": 85.64,
                             "deadhead_km": 38.0, "arrival_at": None}
    assert (b["expected"]["contribution"], b["expected"]["throughput"], b["expected"]["per_hour_avg"]) == (80.5, 28.0, 27.7)
    assert result["ranking"]["order"] == ["A", "B"]
    scenarios = {s["name"]: s for s in a["scenarios"]}
    assert (scenarios["empty"]["contribution"], scenarios["empty"]["total_minutes"], scenarios["empty"]["km"]) == (146.75, 140, 90.0)
    assert (scenarios["return"]["contribution"], scenarios["return"]["total_minutes"]) == (346.75, 150)
    assert a["downside"] == {"scenario": "empty", "contribution": 146.75, "per_hour": 62.89}


def test_golden_wait_decision_and_sensitivity():
    a = by_id(compare(request(offer_a(), offer_b())), "A")
    decision = a["wait_decision"]
    assert decision["verdict"] == "WAIT_IF_P_ABOVE"
    assert decision["p_break_even"] == 0.1034
    assert decision["min_return_fare"] == 73.33
    assert decision["wait_beats_leave_at_entered_p"] is True
    grid = {row["p"]: row["throughput"] for row in a["sensitivity"]}
    assert (grid[0.0], grid[0.1], grid[0.3], grid[0.5], grid[1.0]) == (62.89, 70.96, 86.75, 102.1, 138.7)


def test_throughput_and_average_per_hour_are_distinct_numbers():
    expected = by_id(compare(request(offer_a(), offer_b())), "A")["expected"]
    assert expected["throughput"] != expected["per_hour_avg"]


# ── תרחישי §10 ────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("p,expected_names", [(0, ["empty"]), (0.3, ["empty", "return"]), (1, ["return"])])
def test_return_probability_zero_thirty_hundred(p, expected_names):
    scenarios = by_id(compare(request(offer_a(p))), "A")["scenarios"]
    assert [s["name"] for s in scenarios] == expected_names
    assert abs(sum(s["probability"] for s in scenarios) - 1) < 1e-9


def test_failed_wait_is_counted_in_time_and_empty_drive_in_cost():
    scenarios = {s["name"]: s for s in by_id(compare(request(offer_a(0.3))), "A")["scenarios"]}
    empty = scenarios["empty"]
    assert empty["wait_minutes"] == 30
    assert empty["total_minutes"] == 15 + 40 + 40 + 15 + 30                      # רגליים + שירות + המתנה כושלת
    assert empty["contribution"] == round(230 - 90 * KM_COST, 2)                # כולל הנסיעה הריקה הביתה
    assert empty["deadhead_km"] == 50.0


def test_successful_return_counts_wait_second_fare_and_return_drive():
    ret = {s["name"]: s for s in by_id(compare(request(offer_a(0.3))), "A")["scenarios"]}["return"]
    assert ret["wait_minutes"] == 40
    assert ret["revenue"] == 430.0
    assert ret["total_minutes"] == 15 + 40 + 40 + 15 + 40
    assert ret["contribution"] == round(430 - 90 * KM_COST, 2)


def test_partial_return_adds_empty_legs_before_and_after():
    offer = offer_a(1.0)
    offer["return"].update({"pickup": {"text": "נקודת איסוף חזרה"}, "destination": {"text": "יעד חזרה"}})
    offer["manual_legs"].update({"to_return_pickup": leg(5, 10), "return_loaded": leg(30, 30), "to_final_after_return": leg(12, 15)})
    ret = by_id(compare(request(offer)), "A")["scenarios"][0]
    assert [l["key"] for l in ret["legs"]] == ["to_pickup", "outbound", "to_return_pickup", "return_loaded", "to_final_after_return"]
    assert ret["total_minutes"] == 15 + 40 + 10 + 30 + 15 + 15 + 40                  # +שירות +המתנה
    assert ret["deadhead_km"] == 10 + 5 + 12


def test_identical_endpoints_need_no_leg():
    # return.pickup / return.destination חסרים ⇒ אין רגלי to_return_pickup / to_final_after_return, והן לא נדרשות
    legs = by_id(compare(request(offer_a(1.0))), "A")["scenarios"][0]["legs"]
    assert [l["key"] for l in legs] == ["to_pickup", "outbound", "return_loaded"]


def test_zero_total_time_is_invalid_not_a_division():
    offer = offer_a(0, service_minutes=0)
    offer["return"].update({"wait_minutes_failure": 0})
    offer["manual_legs"] = {"to_pickup": leg(0, 0), "outbound": leg(0, 0), "home_empty": leg(0, 0)}
    result = compare(request(offer))
    a = by_id(result, "A")
    assert a["complete"] is False
    assert a["warnings"][0]["code"] == "TIME_INVALID"
    assert result["ranking"]["order"] == []


def test_missing_manual_leg_is_incomplete_without_invented_values():
    offer = offer_a()
    del offer["manual_legs"]["outbound"]
    result = compare(request(offer, offer_b()))
    a = by_id(result, "A")
    assert a["complete"] is False and "scenarios" not in a and "expected" not in a
    assert a["warnings"][0]["code"] == "LEG_MISSING"
    assert result["ranking"]["order"] == ["B"]
    assert result["ranking"]["incomplete"] == ["A"]


def test_no_return_probability_defaults_to_empty_return():
    offer = offer_a()
    del offer["return"]
    a = by_id(compare(request(offer)), "A")
    assert [s["name"] for s in a["scenarios"]] == ["empty"]
    assert "RETURN_DEFAULT_EMPTY" in [w["code"] for w in a["warnings"]]


def test_zero_opportunity_cost_warns():
    a = by_id(compare(request(offer_a(), opportunity_cost_ils_per_h=0)), "A")
    assert "OPPORTUNITY_COST_ZERO" in [w["code"] for w in a["warnings"]]


# ── ולידציה (שם שדה בלבד) ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mutate,field", [
    (lambda r: r["offers"][0]["return"].update(probability=1.2), "probability"),
    (lambda r: r["offers"][0]["return"].update(probability=-0.1), "probability"),
    (lambda r: r["offers"][0].update(outbound_fare_ils=-5), "outbound_fare_ils"),
    (lambda r: r["offers"][0].update(outbound_fare_ils=True), "outbound_fare_ils"),
    (lambda r: r["offers"][0].update(outbound_fare_ils=float("nan")), "outbound_fare_ils"),
    (lambda r: r["offers"][0].update(outbound_fare_ils="230"), "outbound_fare_ils"),
    (lambda r: r.pop("origin"), "origin"),
    (lambda r: r.pop("final_destination"), "final_destination"),
    (lambda r: r["vehicle"].update(km_per_l=0), "km_per_l"),
    (lambda r: r.update(objective="best"), "objective"),
    (lambda r: r.update(offers=[]), "offers"),
    (lambda r: r.update(offers=[offer_a()] * 6), "offers"),
    (lambda r: r["offers"][0]["return"].pop("fare_ils"), "fare_ils"),
    (lambda r: r.update(departure_at="2026-10-26T08:00:00"), "departure_at"),
])
def test_invalid_input_names_the_field_only(mutate, field):
    body = copy.deepcopy(request(offer_a()))
    mutate(body)
    with pytest.raises(ValueError) as error:
        compare(body)
    assert field in str(error.value)


def test_duplicate_offer_ids_rejected():
    with pytest.raises(ValueError):
        compare(request(offer_a(), offer_a()))


def test_manual_leg_values_are_validated():
    offer = offer_a()
    offer["manual_legs"]["outbound"] = leg(-1, 10)
    with pytest.raises(ValueError):
        compare(request(offer))


# ── עמלה, מזומן מול כלכלי, שחיקה ─────────────────────────────────────────────────────────────

def test_platform_fee_and_fixed_cost_and_cash_contribution():
    vehicle = dict(VEHICLE, platform_fee_pct=10, fixed_cost_ils=20)
    offer = offer_a(0, extra_costs_ils=5)
    scenario = by_id(compare(request(offer, vehicle=vehicle)), "A")["scenarios"][0]
    wear = 90 * 0.30
    assert scenario["fees"] == 23.0
    assert scenario["costs"] == round(90 / 12 * 7.5 + wear + 20 + 5, 2)
    assert scenario["contribution"] == round(230 - 23 - scenario["costs"], 2)
    assert scenario["cash_contribution"] == round(scenario["contribution"] + wear, 2)


# ── דירוג, הסבר והיפוך ───────────────────────────────────────────────────────────────────────

def test_high_fare_does_not_win_automatically():
    expensive = offer_a(0)
    expensive["outbound_fare_ils"] = 230
    expensive["manual_legs"]["outbound"] = leg(80, 160)          # הלוך ארוך מאוד
    expensive["manual_legs"]["home_empty"] = leg(80, 160)
    cheap = offer_b(0)
    cheap["outbound_fare_ils"] = 150
    cheap["manual_legs"].update({"outbound": leg(15, 20), "home_empty": leg(15, 20)})
    result = compare(request(expensive, cheap))
    assert result["ranking"]["order"] == ["B", "A"]


@pytest.mark.parametrize("objective,winner", [
    ("throughput", "A"), ("contribution", "A"), ("earliest_arrival", "A"), ("least_deadhead", "A"), ("downside", "A"),
])
def test_objectives_all_supported(objective, winner):
    result = compare(request(offer_a(), offer_b(), objective=objective))
    assert result["ranking"]["objective"] == objective
    assert result["ranking"]["order"][0] == winner


def test_explanation_names_tradeoff_when_winner_loses_on_another_metric():
    short = offer_b(0)
    short["outbound_fare_ils"] = 60
    short["manual_legs"].update({"outbound": leg(10, 10), "home_empty": leg(10, 10), "to_pickup": leg(2, 3)})
    result = compare(request(offer_a(0), short, objective="contribution"))
    assert result["ranking"]["order"][0] == "A"
    assert any(t["better_offer"] == "B" for t in result["ranking"]["tradeoffs"])
    assert "B" in result["ranking"]["explanation"]


def test_crossover_is_exact_and_flips_the_order():
    # A תחרות מול B קבוע; מחפשים p של A שבו התפוקות שוות
    a = offer_a(0.0)
    b = offer_b(0.0)
    b["outbound_fare_ils"] = 250                                      # B חזק יותר כשאין חזרה
    b["manual_legs"].update({"outbound": leg(20, 20), "home_empty": leg(20, 20)})
    result = compare(request(a, b))
    cross = next(c for c in result["crossovers"] if c["vary"] == "A" and c["against"] == "B")
    p = Decimal(str(cross["p"]))
    below = compare(request(offer_a(float(p) - 0.05), copy.deepcopy(b)))
    above = compare(request(offer_a(min(1.0, float(p) + 0.05)), copy.deepcopy(b)))
    assert below["ranking"]["order"][0] != above["ranking"]["order"][0]


def test_crossover_function_solves_equal_throughput():
    fail = eco.compute_scenario("empty", [_leg_calc(40, 40)], Decimal(0), Decimal(0), Decimal(100), _vehicle(), Decimal(0))
    succ = eco.compute_scenario("return", [_leg_calc(40, 40)], Decimal(30), Decimal(0), Decimal(300), _vehicle(), Decimal(0))
    line = eco.Line.of(fail, succ)
    target = Decimal(120)
    p = eco.crossover(line, target)
    assert p is not None
    assert abs(line.throughput(p) - target) < Decimal("1e-9")


def _vehicle():
    from trip_profitability.models import parse_vehicle
    return parse_vehicle(VEHICLE)


def _leg_calc(km, minutes):
    return eco.LegCalc("outbound", "a", "b", True, Decimal(km), Decimal(minutes), None, {})


# ── זמנים, ספקים ופרובננס ────────────────────────────────────────────────────────────────────

def test_departure_time_timeline_and_pickup_arrival():
    result = compare(request(offer_a(0.3), departure_at="2026-10-26T08:00:00+02:00"))
    a = by_id(result, "A")
    assert a["pickup_arrival"]["minutes"] == 15
    assert a["pickup_arrival"]["at"].startswith("2026-10-26T08:15:00")
    empty = next(s for s in a["scenarios"] if s["name"] == "empty")
    starts = [l["depart_at"][11:16] for l in empty["legs"]]
    assert starts == ["08:00", "08:15", "09:40"]       # 08:55 סוף הנסיעה הטעונה + שירות 15 + המתנה כושלת 30
    assert by_id(result, "A")["expected"]["arrival_at"].startswith("2026-10-26T10:")


def test_every_leg_carries_provenance_and_no_invented_traffic():
    result = compare(request(offer_a()))
    assert result["provider"] == {"name": "MANUAL", "requests_used": 0, "budget_remaining": None}
    for scenario in by_id(result, "A")["scenarios"]:
        for item in scenario["legs"]:
            assert item["provenance"]["source"] == "manual"
            assert item["provenance"]["time_basis"] == "manual"
            assert item["provenance"]["accuracy_class"] == "user_input"
    assert {"BEFORE_TAX", "MANUAL_LEGS"} <= {a["code"] for a in result["assumptions"]}


def test_manual_provider_never_defaults():
    provider = ManualProvider(legs={"A": {"outbound": leg(5, 6)}})
    ok = provider.leg(LegRequest(None, None, None, "outbound", "A"))
    assert ok.ok and (ok.km, ok.minutes) == (Decimal(5), Decimal(6))
    for missing in (LegRequest(None, None, None, "to_pickup", "A"), LegRequest(None, None, None, "outbound", "Z")):
        assert provider.leg(missing).status is LegStatus.MISSING_INPUT


def test_traffic_and_local_stubs_never_return_values_or_use_network():
    for stub in (TrafficAwareProvider(), LocalRouteProvider()):
        assert stub.health().ok is False
        assert stub.leg(LegRequest(None, None, None, "outbound", "A")).ok is False
        assert stub.matrix(MatrixRequest((1, 2), None)).ok is False
        assert stub.requests_used == 0
    assert TrafficAwareProvider().leg(LegRequest(None, None, None, "x", "A")).status is LegStatus.NOT_CONFIGURED
    assert LocalRouteProvider().leg(LegRequest(None, None, None, "x", "A")).status is LegStatus.UNAVAILABLE


def test_factory_default_is_manual_and_never_escalates_silently():
    manual, local, traffic = ManualProvider(), LocalRouteProvider(), TrafficAwareProvider()
    assert select_provider(None, manual=manual, local=local, traffic=traffic).mode is RouteMode.MANUAL
    assert select_provider("MANUAL", manual=manual, local=local, traffic=traffic).mode is RouteMode.MANUAL
    # LOCAL מפורש אך לא בריא: מוחזר הספק עצמו (תוצאה לא-שלמה), לא Google ולא MANUAL
    assert select_provider("LOCAL_ROUTE", manual=manual, local=local, traffic=traffic).mode is RouteMode.LOCAL_ROUTE
    with pytest.raises(ValueError):
        select_provider("TRAFFIC_AWARE", manual=manual, local=local, traffic=traffic)
    with pytest.raises(ValueError):
        select_provider("TRAFFIC_AWARE", manual=manual, local=local, traffic=traffic, traffic_confirm=False)
    assert select_provider("TRAFFIC_AWARE", manual=manual, local=local, traffic=traffic, traffic_confirm=True).mode is RouteMode.TRAFFIC_AWARE
    with pytest.raises(ValueError):
        select_provider("GOOGLE", manual=manual)


def test_healthy_local_provider_is_default_when_available():
    class Healthy(LocalRouteProvider):
        def health(self):
            from core.trips.route_provider import ProviderHealth
            return ProviderHealth(True)
    assert select_provider(None, manual=ManualProvider(), local=Healthy()).mode is RouteMode.LOCAL_ROUTE


def test_compare_with_unconfigured_provider_is_incomplete_not_estimated():
    body = request(offer_a(), routing_mode="LOCAL_ROUTE")
    result = compare(body)
    assert result["provider"]["name"] == "LOCAL_ROUTE"
    assert by_id(result, "A")["complete"] is False
    assert by_id(result, "A")["warnings"][0]["code"] == "ROUTE_UNAVAILABLE"
    traffic = compare(request(offer_a(), routing_mode="TRAFFIC_AWARE", traffic_confirm=True))
    assert by_id(traffic, "A")["complete"] is False
    with pytest.raises(ValueError):
        compare(request(offer_a(), routing_mode="TRAFFIC_AWARE"))                 # בלי אישור מפורש


def test_compare_does_not_mutate_input():
    body = request(offer_a(), offer_b())
    snapshot = copy.deepcopy(body)
    compare(body)
    assert body == snapshot


# ── סדר תחנות ─────────────────────────────────────────────────────────────────────────────────

def stops_request(n, matrix_minutes, matrix_km=None, **over):
    size = len(matrix_minutes)
    km = matrix_km or [[float(c) for c in row] for row in matrix_minutes]
    body = {"start": {"text": "התחלה"}, "stops": [{"id": f"s{i}", "place": {"text": f"תחנה {i}"}, "service_minutes": 5} for i in range(1, n + 1)],
            "manual_matrix": {"km": km, "minutes": matrix_minutes}}
    assert size == n + 1 + (1 if over.get("end") else 0)
    body.update(over)
    return body


def test_stops_exact_matches_brute_force():
    minutes = [[0, 10, 40, 25], [10, 0, 15, 30], [40, 15, 0, 12], [25, 30, 12, 0]]
    result = order_stops(stops_request(3, minutes))
    best = min(itertools.permutations([1, 2, 3]), key=lambda order: sum(minutes[a][b] for a, b in zip([0, *order], order)))
    assert result["best"]["order"] == [f"s{i}" for i in best]
    assert result["method"] == "exact" and result["optimal_for_matrix"] is True
    assert result["best"]["totals"]["travel_minutes"] == sum(minutes[a][b] for a, b in zip([0, *best], best))
    assert result["best"]["totals"]["service_minutes"] == 15
    assert result["provider"]["name"] == "MANUAL"


def test_stops_given_order_comparison_and_saving():
    minutes = [[0, 10, 40, 25], [10, 0, 15, 30], [40, 15, 0, 12], [25, 30, 12, 0]]
    result = order_stops(stops_request(3, minutes, given_order=["s3", "s2", "s1"]))
    assert result["given"]["order"] == ["s3", "s2", "s1"]
    assert result["saving"]["total_minutes"] == result["given"]["totals"]["total_minutes"] - result["best"]["totals"]["total_minutes"]
    assert result["saving"]["total_minutes"] > 0


def test_stops_end_point_and_eta():
    minutes = [[0, 10, 20, 5], [10, 0, 8, 30], [20, 8, 0, 25], [5, 30, 25, 0]]
    body = stops_request(2, minutes, end={"text": "בית"}, departure_at="2026-10-26T08:00:00+02:00")
    result = order_stops(body)
    legs = result["best"]["legs"]
    assert legs[-1]["to"] == "בית" and legs[-1]["stop_id"] is None
    assert legs[0]["depart_at"].startswith("2026-10-26T08:00")
    assert legs[1]["depart_at"] > legs[0]["arrive_at"]           # שירות 5 דקות אחרי ההגעה לתחנה


def test_stops_precedence_is_respected():
    minutes = [[0, 5, 50, 20], [5, 0, 10, 30], [50, 10, 0, 6], [20, 30, 6, 0]]
    free = order_stops(stops_request(3, minutes))
    constrained = order_stops(stops_request(3, minutes, precedence=[["s3", "s1"]]))
    assert constrained["best"]["order"].index("s3") < constrained["best"]["order"].index("s1")
    assert constrained["best"]["totals"]["travel_minutes"] >= free["best"]["totals"]["travel_minutes"]


def test_stops_objective_km_and_cost_need_data():
    minutes = [[0, 10, 40], [10, 0, 15], [40, 15, 0]]
    km = [[0, 30, 5], [30, 0, 40], [5, 40, 0]]
    by_km = order_stops(stops_request(2, minutes, km, objective="km"))
    assert by_km["best"]["order"] == ["s2", "s1"]
    with pytest.raises(ValueError):
        order_stops(stops_request(2, minutes, km, objective="cost"))
    cost = order_stops(stops_request(2, minutes, km, objective="cost", vehicle=VEHICLE))
    assert cost["best"]["order"] == ["s2", "s1"]
    assert cost["best"]["totals"]["travel_cost"] == pytest.approx(45 * KM_COST, abs=0.011)     # 5 + 40 ק"מ


def test_stops_many_stops_is_labelled_heuristic():
    n = 9
    size = n + 1
    minutes = [[0 if i == j else abs(i - j) * 7 + 3 for j in range(size)] for i in range(size)]
    result = order_stops(stops_request(n, minutes))
    assert result["method"] == "heuristic" and result["optimal_for_matrix"] is False
    assert sorted(result["best"]["order"]) == sorted(f"s{i}" for i in range(1, n + 1))
    assert result["warnings"][0]["code"] == "HEURISTIC_ORDER"


def test_stops_input_limits_and_missing_matrix():
    minutes = [[0, 1], [1, 0]]
    with pytest.raises(ValueError):
        order_stops(stops_request(1, minutes, stops=[{"id": f"s{i}", "place": {"text": "x"}} for i in range(11)]))
    result = order_stops({"start": {"text": "a"}, "stops": [{"id": "s1", "place": {"text": "b"}}]})
    assert result["complete"] is False and result["warnings"][0]["code"] == "MATRIX_UNAVAILABLE"
    with pytest.raises(ValueError):
        order_stops(stops_request(1, minutes, given_order=["zz"]))
