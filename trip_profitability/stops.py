"""איזו תחנה להקדים: סדר תחנות לפי מטריצת ק"מ/דקות אחת (סטטית).

עד 8 תחנות: בדיקת כל התמורות, ולכן הסדר מיטבי **למטריצה שניתנה**. 9–10 תחנות: היוריסטיקה (השכן הקרוב + 2-opt)
ומסומנת `heuristic`. המנוע לא טוען שהסדר מיטבי תחת תנועה משתנה: המטריצה קבועה לכל היום.
חלונות זמן קבועים אינם נתמכים כאן (שלב נפרד); תחנות עם precedence נתמכות עד 8 תחנות.
"""

from __future__ import annotations

from datetime import timedelta
from itertools import permutations
from decimal import Decimal

from core.trips.provider_factory import select_provider
from core.trips.providers.local_route import LocalRouteProvider
from core.trips.providers.manual import ManualProvider
from core.trips.providers.traffic_aware import TrafficAwareProvider
from core.trips.route_provider import MatrixRequest, RouteProvider

from .models import ENGINE_VERSION, ZERO, Vehicle, dec, km_out, minutes_out, money, parse_departure, parse_place, parse_vehicle

MAX_EXACT_STOPS = 8
MAX_STOPS = 10
OBJECTIVES = ("minutes", "km", "cost")


def _parse(params):
    if not isinstance(params, dict):
        raise ValueError("request body must be an object")
    raw_stops = params.get("stops")
    if not isinstance(raw_stops, list) or not 1 <= len(raw_stops) <= MAX_STOPS:
        raise ValueError(f"stops must be a list of 1-{MAX_STOPS}")
    ids, places, service = [], [], []
    for i, item in enumerate(raw_stops):
        if not isinstance(item, dict):
            raise ValueError(f"stops[{i}] must be an object")
        stop_id = item.get("id")
        if not isinstance(stop_id, str) or not stop_id.strip() or len(stop_id) > 20:
            raise ValueError(f"stops[{i}].id must be a nonempty string up to 20 chars")
        ids.append(stop_id.strip())
        places.append(parse_place(item.get("place"), f"stops[{i}].place"))
        service.append(dec(item.get("service_minutes", 0), f"stops[{i}].service_minutes", 0, 240))
    if len(set(ids)) != len(ids):
        raise ValueError("stops[].id must be unique")
    objective = params.get("objective", "minutes")
    if objective not in OBJECTIVES:
        raise ValueError("objective is not supported")
    vehicle = parse_vehicle(params["vehicle"]) if params.get("vehicle") is not None else None
    if objective == "cost" and vehicle is None:
        raise ValueError("vehicle is required for objective cost")
    index = {stop_id: i for i, stop_id in enumerate(ids)}
    given = params.get("given_order")
    if given is not None and (not isinstance(given, list) or sorted(map(str, given)) != sorted(ids)):
        raise ValueError("given_order must list every stop exactly once")
    precedence = []
    for pair in params.get("precedence") or []:
        if not isinstance(pair, list) or len(pair) != 2 or any(x not in index for x in pair):
            raise ValueError("precedence must be a list of [before, after] stop ids")
        precedence.append((index[pair[0]], index[pair[1]]))
    if precedence and len(ids) > MAX_EXACT_STOPS:
        raise ValueError(f"precedence is supported up to {MAX_EXACT_STOPS} stops")
    end = parse_place(params["end"], "end") if params.get("end") is not None else None
    mode = params.get("routing_mode")
    if mode is not None and not isinstance(mode, str):
        raise ValueError("routing_mode must be a string")
    return {
        "ids": ids, "places": places, "service": service, "objective": objective, "vehicle": vehicle,
        "given": None if given is None else [index[str(x)] for x in given], "precedence": precedence,
        "start": parse_place(params.get("start"), "start"), "end": end,
        "departure": parse_departure(params.get("departure_at")), "mode": mode,
        "traffic_confirm": params.get("traffic_confirm") is True,
    }


def _edge(objective: str, vehicle: Vehicle | None, km: Decimal, minutes: Decimal) -> Decimal:
    if objective == "minutes":
        return minutes
    if objective == "km":
        return km
    return vehicle.fuel(km) + vehicle.wear(km)


def _path_cost(order, km, minutes, objective, vehicle, end_node):
    nodes = [0] + [i + 1 for i in order] + ([end_node] if end_node is not None else [])
    return sum((_edge(objective, vehicle, km[a][b], minutes[a][b]) for a, b in zip(nodes, nodes[1:])), ZERO)


def _exact(n, km, minutes, objective, vehicle, end_node, precedence):
    scored = []
    for order in permutations(range(n)):
        if precedence:
            position = {stop: at for at, stop in enumerate(order)}
            if any(position[a] > position[b] for a, b in precedence):
                continue
        scored.append((_path_cost(order, km, minutes, objective, vehicle, end_node), order))
    if not scored:
        raise ValueError("precedence cannot be satisfied")
    scored.sort(key=lambda item: item[0])      # יציב: שוויון נפתר לפי סדר הקלט
    return [order for _, order in scored[:3]]


def _heuristic(n, km, minutes, objective, vehicle, end_node):
    remaining, order, node = set(range(n)), [], 0
    while remaining:
        nearest = min(sorted(remaining), key=lambda s: _edge(objective, vehicle, km[node][s + 1], minutes[node][s + 1]))
        order.append(nearest)
        remaining.discard(nearest)
        node = nearest + 1
    best = _path_cost(order, km, minutes, objective, vehicle, end_node)
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                candidate = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                cost = _path_cost(candidate, km, minutes, objective, vehicle, end_node)
                if cost < best:
                    order, best, improved = candidate, cost, True
    return [tuple(order)]


def _route(order, parsed, km, minutes, end_node):
    nodes = [0] + [i + 1 for i in order] + ([end_node] if end_node is not None else [])
    moment, legs = parsed["departure"], []
    total_km = total_minutes = total_service = total_cost = ZERO
    for a, b in zip(nodes, nodes[1:]):
        leg_km, leg_minutes = km[a][b], minutes[a][b]
        is_end = end_node is not None and b == end_node
        service = ZERO if is_end else parsed["service"][b - 1]
        arrive = None if moment is None else moment + timedelta(minutes=float(leg_minutes))
        legs.append({
            "from": (parsed["start"] if a == 0 else parsed["places"][a - 1]).label,
            "to": parsed["end"].label if is_end else parsed["places"][b - 1].label,
            "stop_id": None if is_end else parsed["ids"][b - 1],
            "km": km_out(leg_km), "minutes": minutes_out(leg_minutes), "service_minutes": minutes_out(service),
            "depart_at": moment.isoformat() if moment else None, "arrive_at": arrive.isoformat() if arrive else None,
        })
        moment = None if arrive is None else arrive + timedelta(minutes=float(service))
        total_km += leg_km
        total_minutes += leg_minutes
        total_service += service
        if parsed["vehicle"] is not None:
            total_cost += parsed["vehicle"].fuel(leg_km) + parsed["vehicle"].wear(leg_km)
    return {
        "order": [parsed["ids"][i] for i in order], "legs": legs,
        "totals": {"km": km_out(total_km), "travel_minutes": minutes_out(total_minutes),
                   "service_minutes": minutes_out(total_service), "total_minutes": minutes_out(total_minutes + total_service),
                   "travel_cost": money(total_cost) if parsed["vehicle"] is not None else None},
    }, (total_km, total_minutes + total_service, total_cost)


def order_stops(params, *, provider: RouteProvider | None = None) -> dict:
    """מסדר תחנות לפי יעד (דקות / ק"מ / עלות נסיעה). ValueError עם שם שדה בלבד על קלט לא תקין."""
    parsed = _parse(params)
    n = len(parsed["ids"])
    nodes = (parsed["start"], *parsed["places"], *([parsed["end"]] if parsed["end"] else []))
    end_node = n + 1 if parsed["end"] else None
    if provider is None:
        manual = ManualProvider(matrix=params.get("manual_matrix") if params.get("manual_matrix") is not None else None)
        provider = select_provider(parsed["mode"], manual=manual, local=LocalRouteProvider(),
                                   traffic=TrafficAwareProvider(), traffic_confirm=parsed["traffic_confirm"])
    result = provider.matrix(MatrixRequest(nodes, parsed["departure"]))
    base = {"engine_version": ENGINE_VERSION, "timezone": "Asia/Jerusalem",
            "provider": {"name": provider.mode.value, "requests_used": provider.requests_used}}
    if not result.ok:
        return {**base, "complete": False,
                "warnings": [{"code": "MATRIX_UNAVAILABLE", "text": result.reason or "לא ניתן לחשב מטריצה"}]}

    km, minutes = result.km, result.minutes
    if n <= MAX_EXACT_STOPS:
        candidates, method = _exact(n, km, minutes, parsed["objective"], parsed["vehicle"], end_node, parsed["precedence"]), "exact"
    else:
        candidates, method = _heuristic(n, km, minutes, parsed["objective"], parsed["vehicle"], end_node), "heuristic"

    best, best_totals = _route(candidates[0], parsed, km, minutes, end_node)
    out = {
        **base, "complete": True, "objective": parsed["objective"], "method": method,
        "optimal_for_matrix": method == "exact",
        "basis": "מטריצה אחת קבועה (ללא שינוי תנועה לאורך היום)",
        "best": best,
        "alternatives": [_route(order, parsed, km, minutes, end_node)[0] for order in candidates[1:]],
        "provenance": result.provenance,
        "warnings": [] if method == "exact" else [{"code": "HEURISTIC_ORDER", "text": "יותר מ-8 תחנות: הסדר היוריסטי ולא מובטח מיטבי"}],
    }
    if parsed["given"] is not None:
        given_route, given_totals = _route(tuple(parsed["given"]), parsed, km, minutes, end_node)
        given_cost = _path_cost(tuple(parsed["given"]), km, minutes, parsed["objective"], parsed["vehicle"], end_node)
        best_cost = _path_cost(candidates[0], km, minutes, parsed["objective"], parsed["vehicle"], end_node)
        out["given"] = given_route
        out["saving"] = {
            "objective_value": float(round(given_cost - best_cost, 2)),
            "km": km_out(given_totals[0] - best_totals[0]),
            "total_minutes": minutes_out(given_totals[1] - best_totals[1]),
        }
    return out
