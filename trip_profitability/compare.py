"""השוואת הצעות נסיעה: הרכבת תרחישים מרגליים של RouteProvider, חישוב, דירוג והסבר בעברית.

קלט/פלט לפי SMART_TRIPS_P0_CALCULATION_CONTRACT.md §3, §7, §15.5. אין IO: הספק מוזרק ומחזיר ק"מ ודקות,
והמנוע לא ממציא אף ערך. הצעה שחסר לה נתון נחשבת לא-שלמה ולא מדורגת.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from core.trips.provider_factory import select_provider
from core.trips.providers.local_route import LocalRouteProvider
from core.trips.providers.manual import ManualProvider
from core.trips.providers.traffic_aware import TrafficAwareProvider
from core.trips.route_provider import LegRequest, LegStatus, RouteProvider

from . import economics as eco
from .models import (
    ENGINE_VERSION, ONE, TZ, ZERO, CompareRequest, OfferInput, Place,
    km_out, minutes_out, money, parse_compare_request,
)

SENSITIVITY_STEPS = tuple(Decimal(i) / 10 for i in range(11))

_OBJECTIVE_LABEL = {
    "throughput": "תפוקה לשעה",
    "contribution": "תרומה צפויה",
    "earliest_arrival": "זמן כולל קצר",
    "least_deadhead": "פחות נסיעה ריקה",
    "downside": "תרומה במקרה הגרוע",
}
_HIGHER_IS_BETTER = {"throughput": True, "contribution": True, "downside": True,
                     "earliest_arrival": False, "least_deadhead": False}
_LEG_LABEL = {
    "to_pickup": "נסיעה לאיסוף", "outbound": "נסיעה טעונה", "home_empty": "חזרה ריקה ליעד הסופי",
    "to_return_pickup": "נסיעה לאיסוף החזרה", "return_loaded": "נסיעת חזרה עם נוסע",
    "to_final_after_return": "נסיעה ליעד הסופי אחרי החזרה",
}


class _Incomplete(Exception):
    def __init__(self, code: str, text: str):
        super().__init__(code)
        self.code, self.text = code, text


def _leg(provider: RouteProvider, offer: OfferInput, key: str, origin: Place, dest: Place, loaded: bool,
         depart_at: datetime | None) -> eco.LegCalc:
    result = provider.leg(LegRequest(origin, dest, depart_at, key, offer.id))
    if not result.ok:
        if result.status is LegStatus.MISSING_INPUT:
            raise _Incomplete("LEG_MISSING", f"חסר נתון לרגל: {_LEG_LABEL.get(key, key)}")
        raise _Incomplete("ROUTE_UNAVAILABLE", result.reason or "לא ניתן לחשב מסלול")
    return eco.LegCalc(key, origin.label, dest.label, loaded, result.km, result.minutes, depart_at, result.provenance)


def _steps(kind: str, offer: OfferInput, req: CompareRequest):
    """רגלי התרחיש: (key, מוצא, יעד, טעונה, השהיה לפני היציאה). שירות והמתנה נספרים לפני הרגל שאחרי הפריקה."""
    ret = offer.ret
    steps = [("to_pickup", req.origin, offer.pickup, False, ZERO), ("outbound", offer.pickup, offer.dropoff, True, ZERO)]
    if kind in ("empty", "leave"):
        wait = ZERO if kind == "leave" or ret is None else ret.wait_failure
        steps.append(("home_empty", offer.dropoff, req.final, False, offer.service_minutes + wait))
        return steps, wait
    wait = ret.wait_success
    delay = offer.service_minutes + wait
    destination = ret.destination or req.final
    if ret.pickup is not None:
        steps.append(("to_return_pickup", offer.dropoff, ret.pickup, False, delay))
        steps.append(("return_loaded", ret.pickup, destination, True, ZERO))
    else:
        steps.append(("return_loaded", offer.dropoff, destination, True, delay))
    if ret.destination is not None:
        steps.append(("to_final_after_return", ret.destination, req.final, False, ZERO))
    return steps, wait


def _scenario(kind: str, offer: OfferInput, req: CompareRequest, provider: RouteProvider) -> eco.ScenarioCalc:
    steps, wait = _steps(kind, offer, req)
    moment = req.departure
    legs = []
    for key, origin, dest, loaded, delay in steps:
        if moment is not None:
            moment = moment + timedelta(minutes=float(delay))
        leg = _leg(provider, offer, key, origin, dest, loaded, moment)
        legs.append(leg)
        if moment is not None:
            moment = moment + timedelta(minutes=float(leg.minutes))
    revenue = offer.fare + (offer.ret.fare if kind == "return" else ZERO)
    return eco.compute_scenario(kind, legs, wait, offer.service_minutes, revenue, req.vehicle, offer.extra_costs)


def _soft(kind: str, offer: OfferInput, req: CompareRequest, provider: RouteProvider):
    try:
        return _scenario(kind, offer, req, provider)
    except _Incomplete:
        return None


def _warning(code: str, text: str) -> dict:
    return {"code": code, "text": text}


def _scenario_out(s: eco.ScenarioCalc, probability: Decimal) -> dict:
    return {
        "name": s.name, "probability": float(probability),
        "revenue": money(s.revenue), "fees": money(s.fees), "costs": money(s.costs),
        "contribution": money(s.contribution), "cash_contribution": money(s.cash_contribution),
        "total_minutes": minutes_out(s.total_minutes), "wait_minutes": minutes_out(s.wait),
        "km": km_out(s.km), "deadhead_km": km_out(s.deadhead_km),
        "per_hour": money(s.per_hour),
        "legs": [{
            "key": leg.key, "from": leg.origin, "to": leg.dest, "loaded": leg.loaded,
            "km": km_out(leg.km), "minutes": minutes_out(leg.minutes),
            "depart_at": leg.depart_at.isoformat() if leg.depart_at else None,
            "provenance": leg.provenance,
        } for leg in s.legs],
    }


def _evaluate(offer: OfferInput, req: CompareRequest, provider: RouteProvider) -> dict:
    out: dict = {"id": offer.id, "pickup": offer.pickup.public(), "dropoff": offer.dropoff.public(),
                 "complete": False, "warnings": []}
    p = offer.p
    fail = succ = None
    try:
        if p < 1:
            fail = _scenario("empty", offer, req, provider)
        if p > 0:
            succ = _scenario("return", offer, req, provider)
    except _Incomplete as problem:
        out["warnings"].append(_warning(problem.code, problem.text))
        return out
    if fail is None:
        fail = _soft("empty", offer, req, provider)
    if succ is None and offer.has_return_data:
        succ = _soft("return", offer, req, provider)

    weighted = [(w, s) for w, s in ((ONE - p, fail if p < 1 else None), (p, succ if p > 0 else None)) if s is not None and w > 0]
    if any(not s.valid for _, s in weighted):
        out["warnings"].append(_warning("TIME_INVALID", "זמן כולל אפס או שלילי, לא ניתן לחשב"))
        return out

    ex = eco.expected(weighted)
    worst = eco.downside(weighted)
    first_leg = weighted[0][1].legs[0]
    out.update({
        "complete": True,
        "scenarios": [_scenario_out(s, w) for w, s in weighted],
        "pickup_arrival": {
            "minutes": minutes_out(first_leg.minutes),
            "at": (req.departure + timedelta(minutes=float(first_leg.minutes))).isoformat() if req.departure else None,
        },
        "expected": {
            "contribution": money(ex.contribution), "minutes": minutes_out(ex.minutes),
            "throughput": money(ex.throughput), "per_hour_avg": money(ex.per_hour_avg),
            "deadhead_km": km_out(ex.deadhead_km),
            "arrival_at": (req.departure + timedelta(minutes=float(ex.minutes))).isoformat() if req.departure else None,
        },
        "downside": {"scenario": worst.name, "contribution": money(worst.contribution), "per_hour": money(worst.per_hour)},
        "wait_decision": None,
        "sensitivity": None,
        "_metrics": {"throughput": ex.throughput, "contribution": ex.contribution, "earliest_arrival": ex.minutes,
                     "least_deadhead": ex.deadhead_km, "downside": worst.contribution},
        "_line": eco.Line.of(fail, succ) if fail is not None and succ is not None else None,
    })
    if p == 0 and offer.ret is None:
        out["warnings"].append(_warning("RETURN_DEFAULT_EMPTY", "לא הוזנה הסתברות חזרה: מחושב חזרה ריקה (ברירת מחדל שמרנית)"))
    if offer.ret is not None and offer.ret.probability is None:
        out["warnings"].append(_warning("RETURN_DEFAULT_EMPTY", "לא הוזנה הסתברות חזרה: מחושב חזרה ריקה (ברירת מחדל שמרנית)"))
    if p > 0:
        out["warnings"].append(_warning("PROBABILITY_IS_USER_ESTIMATE", "הסתברות החזרה היא הערכת משתמש, לא נתון מוכח"))

    line = out["_line"]
    if line is not None:
        out["sensitivity"] = [{"p": float(step), "throughput": money(line.throughput(step)),
                               "expected_contribution": money(line.contribution(step)),
                               "expected_minutes": minutes_out(line.minutes(step))} for step in SENSITIVITY_STEPS]
        leave = _soft("leave", offer, req, provider)
        if leave is not None and leave.valid:
            decision = eco.wait_decision(fail, succ, leave, p, req.opportunity_cost, req.vehicle.fee_pct)
            out["wait_decision"] = {
                "verdict": decision["verdict"],
                "p_break_even": None if decision["p_break_even"] is None else float(round(decision["p_break_even"], 4)),
                "min_return_fare": money(decision["min_return_fare"]),
                "wait_beats_leave_at_entered_p": decision["wait_beats_leave_at_p"],
                "opportunity_cost_ils_per_h": money(req.opportunity_cost),
            }
            if req.opportunity_cost == 0:
                out["warnings"].append(_warning("OPPORTUNITY_COST_ZERO", "ללא עלות הזדמנות, המתנה נראית חינמית"))
    return out


def _explain(objective: str, order: list[str], by_id: dict) -> dict:
    label = _OBJECTIVE_LABEL[objective]
    if len(order) < 2:
        return {"text": "הצעה שלמה אחת בלבד, אין מה להשוות", "tradeoffs": []}
    winner = order[0]
    tradeoffs = []
    for metric, higher in _HIGHER_IS_BETTER.items():
        if metric == objective:
            continue
        best = max(order, key=lambda i: by_id[i]["_metrics"][metric] * (1 if higher else -1))
        mine, best_value = by_id[winner]["_metrics"][metric], by_id[best]["_metrics"][metric]
        if best != winner and mine != best_value:
            tradeoffs.append({"metric": metric, "better_offer": best})
    text = f"{winner} מוביל לפי {label}."
    for item in tradeoffs[:3]:
        text += f" {item['better_offer']} עדיף ב{_OBJECTIVE_LABEL[item['metric']]}."
    return {"text": text, "tradeoffs": tradeoffs}


def compare(params, *, provider: RouteProvider | None = None, now: datetime | None = None) -> dict:
    """משווה 1–5 הצעות. ValueError עם שם שדה בלבד על קלט לא תקין; הצעה עם נתון חסר מוחזרת complete=False."""
    req: CompareRequest = parse_compare_request(params)
    if provider is None:
        manual = ManualProvider(legs={o["id"].strip(): o["manual_legs"] for o in params["offers"]
                                      if isinstance(o.get("id"), str) and o.get("manual_legs") is not None})
        provider = select_provider(req.routing_mode, manual=manual, local=LocalRouteProvider(),
                                   traffic=TrafficAwareProvider(), traffic_confirm=req.traffic_confirm)
    results = [_evaluate(offer, req, provider) for offer in req.offers]
    complete = [r for r in results if r["complete"]]
    by_id = {r["id"]: r for r in complete}

    higher = _HIGHER_IS_BETTER[req.objective]
    order = [r["id"] for r in sorted(complete, key=lambda r: r["_metrics"][req.objective] * (-1 if higher else 1))]

    crossovers = []
    for subject in complete:
        line = subject["_line"]
        if line is None:
            continue
        for other in complete:
            if other["id"] == subject["id"] or other["_metrics"]["throughput"] is None:
                continue
            p_cross = eco.crossover(line, other["_metrics"]["throughput"])
            if p_cross is not None:
                crossovers.append({"vary": subject["id"], "against": other["id"], "p": float(round(p_cross, 4))})

    assumptions = [{"code": "BEFORE_TAX", "text": "הסכומים לפני מס"}]
    if provider.mode.value == "MANUAL":
        assumptions.append({"code": "MANUAL_LEGS", "text": "הק\"מ והדקות הוזנו ידנית, ללא נתוני תנועה"})
    if req.opportunity_cost > 0:
        assumptions.append({"code": "OPPORTUNITY_COST_USER_INPUT", "text": "עלות ההזדמנות לשעה היא קלט משתמש, לא שער שוק"})

    for r in results:
        r.pop("_line", None)
    ranking_metrics = {i: by_id[i]["_metrics"] for i in order}
    for r in results:
        r.pop("_metrics", None)
    explanation = _explain(req.objective, order, {i: {"_metrics": m} for i, m in ranking_metrics.items()})
    moment = now or datetime.now(TZ)
    return {
        "engine_version": ENGINE_VERSION,
        "computed_at": moment.astimezone(TZ).isoformat(),
        "timezone": "Asia/Jerusalem",
        "assumptions": assumptions,
        "offers": results,
        "ranking": {"objective": req.objective, "order": order, "explanation": explanation["text"],
                    "tradeoffs": explanation["tradeoffs"],
                    "incomplete": [r["id"] for r in results if not r["complete"]]},
        "crossovers": crossovers,
        "provider": {"name": provider.mode.value, "requests_used": provider.requests_used, "budget_remaining": None},
    }
