"""FCC commute income — pure, read-only (no I/O, no writes, no model).

Two kinds of paid rides, both in the owner's two tables (Commute Routes, Commute Trips):

* a RECURRING route (e.g. 6 days a week): every day the owner answers "is there a ride tomorrow?" and, if so, with how many stops (2 or 3);
* a ONE-OFF trip: the owner types what he was paid, where it went, the price class charged (a customer who needs less pays the regular price, a customer who needs the
  6-seater pays the large price), the km and minutes of one way and what happens on the way back. There is no price list: every price is typed.

This module only *derives*:

* the month's income = the days answered "yes" × the route's day price (the price is stored on the trip row, so a later price change never rewrites history) plus the
  one-off trips' typed prices; the stops count is only tracked (it does not change the price);
* what to collect at the end of the month, week by week;
* the economics of every ride — km, minutes, ₪ per hour and per km, gross and (with the owner's cost per km) net — where the way back decides what was really driven:
    ``empty``        the price covers the return too (there and back, the return is empty);
    ``waited``       the price covers the return and the waiting at the destination (there and back + the waiting minutes);
    ``continuation`` a paid ride back / onward exists: this price covers ONE way only (the return is another ride, with its own price);
* the leased car's free monthly allowance (km and fuel ₪, entered once): what is left of it this month, and which rides use it best — inside the allowance a km costs nothing, so
  the ride's gross IS its profit and the scarce thing is the km (₪ per allowance-km); beyond it a km costs the owner's cost per km;
* a ride "on the way" of one of the owner's OWN weekly drives (a delivery counts the same): only the km and minutes it ADDED count (``Extra Km`` / ``Extra Minutes``);
* WHERE: a city's profitability is not another's, and inside Jerusalem the entrance to the city is not a remote neighbourhood — a trip carries its city and area, and the profitability
  and the way-back history are read per area (else per city);
* EXTRA STOPS: a stop on the way is not a stop from one end of the city to the other in the rush hour — a trip carries how many stops, the surcharge for them and the km and minutes THEY
  added, so the stops' own ₪ per hour (and what they did to the whole ride) is visible, per band of the day;
* TWO LEGS A DAY: a recurring day has an outbound leg (say 07:30) and a return leg (say 15:00), each with its own start time, km, minutes and load (full / empty), and the unpaid km and
  minutes around each (home to the pickup, the drop-off back home). The price is per DAY, so the decision is made on the day (and the month) as a whole — both legs and the unpaid driving
  summed — while every leg stays visible beside it, so the slow leg shows. The time BETWEEN the legs is free (the owner is not tied up) and is not counted;
* the time of day: what traffic does to a ride's length — the same destination compared across bands of the day (minutes, ₪ per hour); a fact is said only with a real sample;
* the profitability by destination, by price class and by kind (ride / delivery) — which rides were worth it — as numbers and a comparison with the average, never a verdict by a threshold;
* income entries (``cashflow.Txn``) for the monthly income model — the SAME numbers, no second formula.

Unknown stays unknown: a missing km / minutes / cost is None and the figure that needs it is None.
"""

from __future__ import annotations

from datetime import date, timedelta

from core.financial_control import cashflow as fcc_cashflow

WEEKDAYS_HE = ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")      # date.weekday(): Monday = 0
STOP_CHOICES = (2, 3)
WEEKS_PER_MONTH = 52 / 12
MIN_STOPS_SAMPLE = 10         # rides with a recorded stops count before "most are 3 stops" is worth saying
THREE_STOPS_SHARE = 0.5
WINDOW_BACK, WINDOW_FORWARD = 6, 1       # the days the owner can answer: the last week and tomorrow
SATURDAY = 5                              # date.weekday(): a route of up to 6 days a week rests on Saturday (Friday is a ride day)
MIN_RETURN_SAMPLE = 5         # known way-back outcomes at ONE destination before that destination's own history weights the expected return
MIN_OVERALL_SAMPLE = 10       # ... or across all the owner's one-off trips before the overall history is used instead
ONE_OFF_SOURCE = "נסיעות נוספות"
CLASS_LABEL = {"regular": "רגיל", "large": "גדול"}
KIND_LABEL = {"ride": "נסיעה", "delivery": "משלוח"}
RETURN_LABEL = {"empty": "חזרה ריקה", "waited": "המתנה", "continuation": "יש נסיעת המשך"}
DEFAULT_RETURN = "empty"
# time-of-day bands (start hour, end hour exclusive, key, label): the rush hours are separate bands because that is where a ride's length changes
BANDS = ((0.0, 6.0, "night", "לילה ובוקר מוקדם"), (6.0, 9.5, "morning_rush", "בוקר (שעת עומס)"), (9.5, 15.0, "midday", "צהריים"), (15.0, 19.5, "evening_rush", "אחה״צ (שעת עומס)"),
         (19.5, 24.0, "evening", "ערב"))
BAND_LABEL = {key: label for _, _, key, label in BANDS}
MIN_BAND_RIDES = 2            # rides in EACH band before the length of a ride is compared across bands
MIN_BAND_GAP = 0.2            # a difference of at least 20% in minutes is "a difference" worth saying


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _sel(v):
    return v.get("name") if isinstance(v, dict) else v


def _day(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def band_of(start_time: str | None) -> str | None:
    """The band of the day for an "HH:MM" start time; None when there is no (valid) time."""
    try:
        hh, mm = str(start_time).split(":")
        hour = int(hh) + int(mm) / 60
    except (ValueError, AttributeError):
        return None
    return next((key for lo, hi, key, _ in BANDS if lo <= hour < hi), None)


def _time(v) -> str | None:
    v = str(v or "").strip()
    return v if band_of(v) else None


def _load(v):
    v = _sel(v)
    return v if v in ("full", "empty") else None


def _cls(v):
    v = _sel(v)
    return v if v in CLASS_LABEL else None


def _ret(v, default=None):
    v = _sel(v)
    return v if v in RETURN_LABEL else default


def parse_route(rec: dict) -> dict:
    f = rec.get("fields") or {}
    kind = _sel(f.get("Route Kind"))
    weekdays = [_sel(x) for x in (f.get("Weekdays") or []) if _sel(x)]
    return {"id": rec.get("id"), "kind": "own" if kind == "own" else "paid", "weekdays": weekdays, "name": str(f.get("Name") or "").strip() or "נסיעה", "price": _num(f.get("Day Price")),
            "km_one_way": _num(f.get("Km One Way")), "minutes_one_way": _num(f.get("Minutes One Way")), "cost_per_km": _num(f.get("Cost Per Km")),
            "planned_days": _num(f.get("Planned Days Per Week")), "active": _sel(f.get("Status")) != "paused", "notes": f.get("Notes") or None,
            "vehicle_class": _cls(f.get("Vehicle Class")), "return_status": _ret(f.get("Return Status"), DEFAULT_RETURN), "waiting_minutes": _num(f.get("Waiting Minutes")) or 0.0,
            "start_time": _time(f.get("Start Time")), "return_start_time": _time(f.get("Return Start Time")), "return_km": _num(f.get("Return Km")), "return_minutes": _num(f.get("Return Minutes")),
            "outbound_load": _load(f.get("Outbound Load")), "return_load": _load(f.get("Return Load")), "out_unpaid_km": _num(f.get("Out Unpaid Km")) or 0.0,
            "out_unpaid_minutes": _num(f.get("Out Unpaid Minutes")) or 0.0, "ret_unpaid_km": _num(f.get("Ret Unpaid Km")) or 0.0, "ret_unpaid_minutes": _num(f.get("Ret Unpaid Minutes")) or 0.0}


def parse_trip(rec: dict) -> dict | None:
    """A route day (it has a route) or a one-off trip (it has a destination); anything else is not a trip."""
    f = rec.get("fields") or {}
    route = f.get("Route")
    route_id = route[0] if isinstance(route, list) and route else None
    destination = str(f.get("Destination") or "").strip() or None
    day = _day(f.get("Trip Date"))
    if day is None or (not route_id and not destination):
        return None
    outcome = _sel(f.get("Outcome"))
    stops = _num(f.get("Stops"))
    return {"id": rec.get("id"), "route_id": route_id, "destination": destination, "date": day, "outcome": outcome if outcome in ("yes", "no") else None,
            "stops": int(stops) if stops else None, "amount": _num(f.get("Amount")), "vehicle_class": _cls(f.get("Vehicle Class")),
            "km_one_way": _num(f.get("Km One Way")), "minutes_one_way": _num(f.get("Minutes One Way")), "return_status": _ret(f.get("Return Status")),
            "waiting_minutes": _num(f.get("Waiting Minutes")) or 0.0, "kind": "delivery" if _sel(f.get("Kind")) == "delivery" else "ride",
            "extra_km": _num(f.get("Extra Km")), "extra_minutes": _num(f.get("Extra Minutes")), "on_the_way_of": str(f.get("On The Way Of") or "").strip() or None,
            "start_time": _time(f.get("Start Time")), "return_start_time": _time(f.get("Return Start Time")), "return_minutes": _num(f.get("Return Minutes")),
            "city": str(f.get("City") or "").strip() or None, "area": str(f.get("Area") or "").strip() or None,
            "added_stops": int(_num(f.get("Added Stops")) or 0), "stops_price": _num(f.get("Stops Price")) or 0.0, "stops_km": _num(f.get("Stops Km")) or 0.0,
            "stops_minutes": _num(f.get("Stops Minutes")) or 0.0}


def parse_settings(records: list[dict]) -> dict | None:
    """The owner's allowance row (the first one; the table holds one per owner)."""
    if not records:
        return None
    f = records[0].get("fields") or {}
    return {"id": records[0].get("id"), "free_km": _num(f.get("Free Km Monthly")), "free_fuel": _num(f.get("Free Fuel Monthly")), "fuel_cost_per_km": _num(f.get("Fuel Cost Per Km")),
            "cost_per_km": _num(f.get("Cost Per Km")), "other_km_used": _num(f.get("Other Km Used")), "other_km_month": str(f.get("Other Km Month") or "") or None}


def _amount(trip: dict, route: dict | None) -> float:
    """What a "yes" day is worth: the amount stored on the row, else the route's current day price (a row edited by hand)."""
    if trip["amount"] is not None:
        return trip["amount"]
    return (route or {}).get("price") or 0.0


def default_cost_per_km(routes: list[dict], settings: dict | None = None) -> float | None:
    """The owner has one vehicle: the cost per km beyond the free allowance he entered in his settings (else on a route, an active one first) is the cost of every ride."""
    if settings and settings["cost_per_km"] is not None:
        return settings["cost_per_km"]
    for r in sorted(routes, key=lambda r: not r["active"]):
        if r["cost_per_km"] is not None:
            return r["cost_per_km"]
    return None


def ride_economics(price: float | None, km_one_way: float | None, minutes_one_way: float | None, return_status: str | None, waiting_minutes: float,
                   cost_per_km: float | None, extra_km: float | None = None, extra_minutes: float | None = None, stops_km: float = 0.0, stops_minutes: float = 0.0,
                   stops_price: float = 0.0, total_km: float | None = None, total_minutes: float | None = None) -> dict:
    """One ride. A ride with a paid continuation counts ONE way; every other ride is there and back, plus the waiting minutes. A ride fitted on the way of the owner's own
    drive counts only what it ADDED (``extra_km`` / ``extra_minutes`` replace the one-way based figures). EXTRA STOPS add their own km and minutes on top, and their surcharge is part
    of the price: ``stops_*`` shows what the stops earned on their own and ``base_*`` what the ride would have earned without them. Every figure is None while an input is missing.
    ``gross_*`` is what the ride earns while the km are free (inside the allowance); ``net_*`` also takes the cost per km (beyond it)."""
    legs = 1 if return_status == "continuation" else 2
    km = extra_km if extra_km is not None else (round(km_one_way * legs, 2) if km_one_way is not None else None)
    if extra_minutes is not None:
        minutes = extra_minutes
    else:
        minutes = round(minutes_one_way * legs + (waiting_minutes or 0.0), 2) if minutes_one_way is not None else None
    if total_km is not None or total_minutes is not None:        # a recurring day: the km and minutes of both legs plus the unpaid driving, summed by ``route_day``
        km, minutes = total_km, total_minutes
    base_km, base_minutes = km, minutes
    if km is not None:
        km = round(km + (stops_km or 0.0), 2)
    if minutes is not None:
        minutes = round(minutes + (stops_minutes or 0.0), 2)
    hours = minutes / 60 if minutes else None
    vehicle = round(km * cost_per_km, 2) if km is not None and cost_per_km is not None else None
    net = round(price - vehicle, 2) if price is not None and vehicle is not None else None
    r = lambda x: None if x is None else round(x, 2)
    base_price = price - (stops_price or 0.0) if price is not None else None
    stops_hours = (stops_minutes or 0.0) / 60
    return {"price": price, "legs": legs, "km": km, "minutes": minutes, "hours": r(hours), "on_the_way": extra_km is not None,
            "gross_per_hour": r(price / hours) if price is not None and hours else None, "gross_per_km": r(price / km) if price is not None and km else None,
            "vehicle_cost": vehicle, "net": net, "net_per_hour": r(net / hours) if net is not None and hours else None, "net_per_km": r(net / km) if net is not None and km else None,
            "stops_price": stops_price or 0.0, "stops_km": stops_km or 0.0, "stops_minutes": stops_minutes or 0.0,
            "stops_per_hour": r(stops_price / stops_hours) if stops_price and stops_hours else None, "stops_per_km": r(stops_price / stops_km) if stops_price and stops_km else None,
            "base_gross_per_hour": r(base_price / (base_minutes / 60)) if base_price is not None and base_minutes else None,
            "base_gross_per_km": r(base_price / base_km) if base_price is not None and base_km else None}


def route_day(route: dict, trip: dict | None = None) -> dict:
    """ONE day of a recurring route: the outbound leg and the return leg (each with its start time, km, minutes and load), the unpaid km and minutes around each, and the day's totals —
    the figures the day's price is weighed against. A day the owner timed afterwards uses that day's minutes for each leg (else the route's usual); a route with no separate return leg
    values drives the same km and minutes back. The return leg is not driven when the route's way back is a paid continuation; waiting minutes (``waited``) count, the free time between the
    legs does not. A figure the route has no km / minutes for is None."""
    t = trip or {}
    legs = []
    out_minutes = t.get("minutes_one_way") or route["minutes_one_way"]
    legs.append({"key": "out", "label": "הלוך", "start": t.get("start_time") or route["start_time"], "km": route["km_one_way"], "minutes": out_minutes, "load": route["outbound_load"],
                 "unpaid_km": route["out_unpaid_km"], "unpaid_minutes": route["out_unpaid_minutes"], "timed": bool(t.get("minutes_one_way"))})
    if route["return_status"] != "continuation":
        ret_km = route["return_km"] if route["return_km"] is not None else route["km_one_way"]
        ret_minutes = t.get("return_minutes") or route["return_minutes"] or route["minutes_one_way"]
        legs.append({"key": "ret", "label": "חזור", "start": t.get("return_start_time") or route["return_start_time"], "km": ret_km, "minutes": ret_minutes, "load": route["return_load"],
                     "unpaid_km": route["ret_unpaid_km"], "unpaid_minutes": route["ret_unpaid_minutes"], "timed": bool(t.get("return_minutes"))})
    waiting = route["waiting_minutes"] if route["return_status"] == "waited" else 0.0
    known = all(l["km"] is not None and l["minutes"] is not None for l in legs)
    total_km = round(sum(l["km"] + l["unpaid_km"] for l in legs), 2) if known else None
    total_minutes = round(sum(l["minutes"] + l["unpaid_minutes"] for l in legs) + waiting, 2) if known else None
    unpaid_km = round(sum(l["unpaid_km"] for l in legs), 2)
    empty_km = round(unpaid_km + sum(l["km"] for l in legs if l["load"] == "empty" and l["km"] is not None), 2) if known else None
    for l in legs:
        l["band"] = band_of(l["start"])
        l["total_minutes"] = round(l["minutes"] + l["unpaid_minutes"], 2) if l["minutes"] is not None else None
    return {"legs": legs, "total_km": total_km, "total_minutes": total_minutes, "unpaid_km": unpaid_km, "unpaid_minutes": round(sum(l["unpaid_minutes"] for l in legs), 2),
            "empty_km": empty_km, "empty_share": round(empty_km / total_km, 4) if empty_km is not None and total_km else None, "waiting_minutes": waiting}


def economics(route: dict) -> dict:
    """One trip day of a route (the same ``ride_economics`` over the day's two legs and the unpaid driving), with the planned monthly potential. The field names are the screen's."""
    day = route_day(route)
    e = ride_economics(route["price"], route["km_one_way"], route["minutes_one_way"], route["return_status"], route["waiting_minutes"], route["cost_per_km"],
                       total_km=day["total_km"], total_minutes=day["total_minutes"])
    price, planned = route["price"], route["planned_days"]
    return {"price": price, "km_per_day": e["km"], "minutes_per_day": e["minutes"], "hours_per_day": e["hours"], "gross_per_hour": e["gross_per_hour"],
            "gross_per_km": e["gross_per_km"], "vehicle_cost_per_day": e["vehicle_cost"], "net_per_day": e["net"], "net_per_hour": e["net_per_hour"], "net_per_km": e["net_per_km"],
            "monthly_potential": round(price * planned * WEEKS_PER_MONTH, 2) if price is not None and planned else None,
            "return_status": route["return_status"], "vehicle_class": route["vehicle_class"], "legs": day["legs"], "unpaid_km": day["unpaid_km"], "unpaid_minutes": day["unpaid_minutes"],
            "empty_km": day["empty_km"], "empty_share": day["empty_share"]}


def week_start(d: date) -> date:
    """Sunday of the week of ``d`` (the Israeli week)."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def route_decision(route: dict, yes: list[dict], cost: float | None) -> dict:
    """The month of a recurring route, for the decision "do I keep it": over the days that had a ride, the income against BOTH legs and the unpaid driving summed — ₪ per hour, ₪ per km
    (net of the cost per km when known), how much of the km was empty — and each leg's average minutes, so the slow leg shows. The free time between the legs is not counted."""
    days = [(t, route_day(route, t)) for t in yes]
    known = [(t, d) for t, d in days if d["total_km"] is not None and d["total_minutes"]]
    income = round(sum(_amount(t, route) for t, _ in known), 2)
    km = round(sum(d["total_km"] for _, d in known), 1)
    minutes = round(sum(d["total_minutes"] for _, d in known), 1)
    hours = minutes / 60 if minutes else None
    net = round(income - km * cost, 2) if cost is not None else None
    empty = [d["empty_km"] for _, d in known if d["empty_km"] is not None]
    legs = []
    for key, label in (("out", "הלוך"), ("ret", "חזור")):
        part = [leg for _, d in known for leg in d["legs"] if leg["key"] == key and leg["minutes"]]
        if part:
            legs.append({"key": key, "label": label, "avg_minutes": round(sum(l["minutes"] for l in part) / len(part), 1), "avg_total_minutes": round(sum(l["total_minutes"] for l in part) / len(part), 1),
                         "timed_days": sum(1 for l in part if l["timed"])})
    slowest = max(legs, key=lambda l: l["avg_minutes"])["key"] if len(legs) == 2 and legs[0]["avg_minutes"] != legs[1]["avg_minutes"] else None
    return {"days": len(known), "unknown_days": len(days) - len(known), "income": income, "km": km, "minutes": minutes, "gross_per_hour": round(income / hours, 2) if hours else None,
            "gross_per_km": round(income / km, 2) if km else None, "net": net, "net_per_hour": round(net / hours, 2) if net is not None and hours else None,
            "empty_km": round(sum(empty), 1) if empty else None, "empty_share": round(sum(empty) / km, 4) if empty and km else None, "legs": legs, "slowest": slowest}


def route_month(route: dict, trips: list[dict], month: str, cost: float | None = None) -> dict:
    mine = [t for t in trips if t["route_id"] == route["id"] and month_key(t["date"]) == month]
    yes = [t for t in mine if t["outcome"] == "yes"]
    no = [t for t in mine if t["outcome"] == "no"]
    stops = {n: sum(1 for t in yes if t["stops"] == n) for n in STOP_CHOICES}
    known = sum(stops.values())
    weeks: dict[date, list[float]] = {}
    for t in yes:
        cell = weeks.setdefault(week_start(t["date"]), [0, 0.0])
        cell[0] += 1
        cell[1] += _amount(t, route)
    income = round(sum(c[1] for c in weeks.values()), 2)
    timed = [t["minutes_one_way"] for t in yes if t["minutes_one_way"]]
    timed_return = [t["return_minutes"] for t in yes if t["return_minutes"]]
    return {"month": month, "yes_days": len(yes), "no_days": len(no), "income": income, "timed_days": len(timed), "avg_minutes_one_way": round(sum(timed) / len(timed), 1) if timed else None,
            "timed_return_days": len(timed_return), "avg_return_minutes": round(sum(timed_return) / len(timed_return), 1) if timed_return else None, "decision": route_decision(route, yes, cost), "stops": {str(n): c for n, c in stops.items()},
            "stops_recorded": known, "three_share": round(stops[3] / known, 4) if known else None,
            "weeks": [{"week_start": w.isoformat(), "yes_days": c[0], "income": round(c[1], 2)} for w, c in sorted(weeks.items())]}


def one_off_month(trips: list[dict], month: str) -> dict:
    """The one-off trips of a month: how many, and what they were paid."""
    yes = [t for t in trips if t["route_id"] is None and t["outcome"] == "yes" and month_key(t["date"]) == month]
    return {"month": month, "trips": len(yes), "income": round(sum(t["amount"] or 0.0 for t in yes), 2)}


def stops_note(trips_yes: list[dict]) -> str | None:
    """A FACT about the stops, never a price decision: said only with a real sample."""
    recorded = [t for t in trips_yes if t["stops"] in STOP_CHOICES]
    if len(recorded) < MIN_STOPS_SAMPLE:
        return None
    share = sum(1 for t in recorded if t["stops"] == 3) / len(recorded)
    if share >= THREE_STOPS_SHARE:
        return f"ב-{round(share * 100)}% מהנסיעות ({len(recorded)} נסיעות שנרשמו) היו 3 תחנות — אולי כדאי לבדוק מחיר"
    return None


def days_window(route: dict, trips: list[dict], today: date) -> list[dict]:
    """The days the owner can answer for ONE route: the last week and tomorrow, each with its current answer (None = not answered). A route of up to 6 days a week
    rests on Saturday (``rest_day``): the day can still be answered, but an empty Saturday is not a missing answer. Friday is a ride day like any other."""
    by_day = {t["date"]: t for t in trips if t["route_id"] == route["id"]}
    rests = (route["planned_days"] or 6) <= 6
    out = []
    for back in range(-WINDOW_FORWARD, WINDOW_BACK + 1):
        d = today - timedelta(days=back)
        t = by_day.get(d)
        out.append({"date": d.isoformat(), "weekday": WEEKDAYS_HE[d.weekday()], "is_tomorrow": d == today + timedelta(days=1), "is_today": d == today,
                    "rest_day": rests and d.weekday() == SATURDAY, "outcome": t["outcome"] if t else None, "stops": t["stops"] if t else None, "trip_id": t["id"] if t else None,
                    "start_time": t["start_time"] if t else None, "minutes_one_way": t["minutes_one_way"] if t else None,
                    "return_start_time": t["return_start_time"] if t else None, "return_minutes": t["return_minutes"] if t else None})
    return out


def _trip_ride(trip: dict, routes_by_id: dict, cost: float | None) -> tuple[str, dict, dict | None]:
    """(destination key / label, the ride's economics, its route) for one "yes" trip. A route day uses the route's km / minutes / return status; a one-off trip its own."""
    route = routes_by_id.get(trip["route_id"]) if trip["route_id"] else None
    price = _amount(trip, route)
    if route is not None:
        day = route_day(route, trip)                      # both legs of THAT day (its own minutes when the owner timed it — traffic — else the route's usual) and the unpaid driving
        e = ride_economics(price, route["km_one_way"], route["minutes_one_way"], route["return_status"], route["waiting_minutes"], route["cost_per_km"] if route["cost_per_km"] is not None else cost,
                           total_km=day["total_km"], total_minutes=day["total_minutes"])
        return route["name"], e, route
    return trip["destination"] or ONE_OFF_SOURCE, ride_economics(price, trip["km_one_way"], trip["minutes_one_way"], trip["return_status"], trip["waiting_minutes"], cost,
                                                                 trip["extra_km"], trip["extra_minutes"], trip["stops_km"], trip["stops_minutes"], trip["stops_price"]), None


def _sum(values: list[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return round(sum(known), 2) if known and len(known) == len(values) else None


def _stats(group: list[dict]) -> dict:
    """Counts, average price and the figures WEIGHTED over the rides whose km and minutes are known: gross (km inside the allowance cost nothing) and net (beyond it —
    only when every measured ride has a cost per km)."""
    have = [g for g in group if g["e"]["hours"] and g["e"]["km"]]
    net_ok = bool(have) and all(g["e"]["net"] is not None for g in have)
    price, net = _sum([g["e"]["price"] for g in have]), _sum([g["e"]["net"] for g in have]) if net_ok else None
    minutes, km = _sum([g["e"]["minutes"] for g in have]), _sum([g["e"]["km"] for g in have])
    hours = minutes / 60 if minutes else None                 # from the minutes, not from the rounded per-ride hours
    div = lambda a, b: round(a / b, 2) if a is not None and b else None
    share = lambda key, value: round(sum(1 for g in group if g[key] == value) / len(group), 4) if group else None
    return {"rides": len(group), "avg_price": round(sum(g["price"] for g in group) / len(group), 2) if group else None, "measured_rides": len(have),
            "gross_per_hour": div(price, hours), "gross_per_km": div(price, km), "net_per_hour": div(net, hours), "net_per_km": div(net, km),
            "empty_return_share": share("return", "empty"), "continuation_share": share("return", "continuation"), "waited_share": share("return", "waited"),
            "on_the_way_share": round(sum(1 for g in group if g["e"]["on_the_way"]) / len(group), 4) if group else None}


def _avg_minutes(group: list[dict]) -> float | None:
    known = [g["e"]["minutes"] for g in group if g["e"]["minutes"]]
    return round(sum(known) / len(known), 1) if known else None


def _time_insights(groups: dict[str, list[dict]]) -> list[dict]:
    """The same destination at different hours: for every destination with at least ``MIN_BAND_RIDES`` rides in two or more bands of the day, the average minutes and the gross ₪ per hour
    of each band, and — when the slowest band takes at least ``MIN_BAND_GAP`` more minutes than the fastest — the facts. No verdict on whether to drive at that hour."""
    out = []
    for group in groups.values():
        bands = []
        for _, _, key, label in BANDS:
            part = [g for g in group if g["band"] == key and g["e"]["minutes"]]
            if len(part) >= MIN_BAND_RIDES:
                st = _stats(part)
                bands.append({"band": key, "label": label, "rides": len(part), "avg_minutes": _avg_minutes(part), "gross_per_hour": st["gross_per_hour"], "gross_per_km": st["gross_per_km"],
                              "avg_price": st["avg_price"]})
        if len(bands) < 2:
            continue
        fast, slow = min(bands, key=lambda b: b["avg_minutes"]), max(bands, key=lambda b: b["avg_minutes"])
        if slow["avg_minutes"] >= fast["avg_minutes"] * (1 + MIN_BAND_GAP):
            out.append({"destination": group[0]["name"], "fastest": fast["band"], "slowest": slow["band"], "bands": bands,
                        "extra_minutes": round(slow["avg_minutes"] - fast["avg_minutes"], 1)})
    return sorted(out, key=lambda x: -x["extra_minutes"])


def _profit_rides(routes: list[dict], trips: list[dict], settings: dict | None) -> list[dict]:
    """Every "yes" ride with its economics and the facts the profitability groups by."""
    cost = default_cost_per_km(routes, settings)
    by_id = {r["id"]: r for r in routes}
    rides = []
    for t in trips:
        if t["outcome"] != "yes":
            continue
        name, e, route = _trip_ride(t, by_id, cost)
        start = t["start_time"] or (route or {}).get("start_time")
        rides.append({"name": name.strip(), "key": name.strip().casefold(), "class": t["vehicle_class"] or (route or {}).get("vehicle_class"), "kind": t["kind"],
                      "return": t["return_status"] or (route or {}).get("return_status"), "e": e, "price": e["price"], "band": band_of(start), "city": t["city"], "area": t["area"],
                      "added": t["added_stops"]})
    return rides


def _stops_view(rides: list[dict]) -> dict | None:
    """What the extra stops were worth: on their own (the surcharge against the km and minutes THEY added) and what they did to the whole ride (₪ per hour with them vs without), and by
    band of the day — a stop on the way is not a stop across the city in the rush hour. Facts and numbers only."""
    withs = [g for g in rides if g["added"] or g["e"]["stops_price"] or g["e"]["stops_km"] or g["e"]["stops_minutes"]]
    if not withs:
        return None
    timed = [g for g in withs if g["e"]["stops_minutes"] and g["e"]["minutes"]]
    div = lambda a, b: round(a / b, 2) if a is not None and b else None
    sp, sm, sk = sum(g["e"]["stops_price"] for g in timed), sum(g["e"]["stops_minutes"] for g in timed), sum(g["e"]["stops_km"] for g in timed)
    count = sum(g["added"] for g in timed if g["added"])
    total_price, total_min = sum(g["e"]["price"] or 0.0 for g in timed), sum(g["e"]["minutes"] for g in timed)
    base_price, base_min = total_price - sp, total_min - sm
    bands = []
    for _, _, key, label in BANDS:
        part = [g for g in timed if g["band"] == key]
        if part:
            minutes = sum(g["e"]["stops_minutes"] for g in part)
            n = sum(g["added"] for g in part if g["added"])
            bands.append({"band": key, "label": label, "rides": len(part), "avg_minutes_per_stop": div(minutes, n), "per_hour": div(sum(g["e"]["stops_price"] for g in part), minutes / 60)})
    rush = [b for b in bands if "rush" in b["band"] and b["avg_minutes_per_stop"] is not None]
    calm = [b for b in bands if "rush" not in b["band"] and b["avg_minutes_per_stop"] is not None]
    note = None
    if rush and calm and sum(b["rides"] for b in rush) >= MIN_BAND_RIDES and sum(b["rides"] for b in calm) >= MIN_BAND_RIDES:
        r_avg = sum(b["avg_minutes_per_stop"] * b["rides"] for b in rush) / sum(b["rides"] for b in rush)
        c_avg = sum(b["avg_minutes_per_stop"] * b["rides"] for b in calm) / sum(b["rides"] for b in calm)
        if r_avg >= c_avg * (1 + MIN_BAND_GAP):
            note = f"תחנה בשעת עומס לוקחת בממוצע {round(r_avg, 1)} דק׳ לעומת {round(c_avg, 1)} דק׳ בשעות אחרות"
    return {"rides": len(withs), "measured_rides": len(timed), "stops": count, "avg_price": round(sum(g["e"]["stops_price"] for g in withs) / len(withs), 2),
            "avg_minutes_per_stop": div(sm, count), "avg_km_per_stop": div(sk, count), "per_hour": div(sp, sm / 60) if sm else None, "per_km": div(sp, sk),
            "ride_per_hour_with": div(total_price, total_min / 60) if total_min else None, "ride_per_hour_without": div(base_price, base_min / 60) if base_min else None, "by_band": bands, "note": note}


def profitability(routes: list[dict], trips: list[dict], settings: dict | None = None) -> dict:
    """Which rides were worth it: per destination (a route or a one-off destination, by name), per CITY and per AREA (the entrance to a city is not a remote neighbourhood), per price class,
    per kind (ride / delivery) and "on the way" vs not — plus what the extra stops were worth. The owner's constraint is the free km of the leased car, so the destinations are ranked by
    ₪ per allowance-km (gross per km); the ₪ per hour sits beside it, and the net figures (beyond the allowance) when a cost per km is known. Where each stands against the average is a
    number, never a verdict by a threshold: the owner decides."""
    cost = default_cost_per_km(routes, settings)
    rides = _profit_rides(routes, trips, settings)
    overall = _stats(rides) if rides else None
    base = overall["gross_per_km"] if overall else None
    vs = lambda row: round(row["gross_per_km"] - base, 2) if row["gross_per_km"] is not None and base is not None else None
    groups: dict[str, list[dict]] = {}
    for g in rides:
        groups.setdefault(g["key"], []).append(g)
    rows = []
    for group in groups.values():
        row = {"destination": group[0]["name"], **_stats(group), "classes": sorted({g["class"] for g in group if g["class"]}), "kinds": sorted({g["kind"] for g in group})}
        row["vs_average_per_km"] = vs(row)
        rows.append(row)
    rows.sort(key=lambda r: (r["gross_per_km"] is None, -(r["gross_per_km"] or 0), r["destination"]))

    cities: dict[str, list[dict]] = {}
    areas: dict[str, list[dict]] = {}
    for g in rides:
        if g["city"]:
            cities.setdefault(_place_key(g["city"]), []).append(g)
            if g["area"]:
                areas.setdefault(_place_key(g["city"], g["area"]), []).append(g)
    def place_rows(groups_: dict[str, list[dict]]) -> list[dict]:
        out = []
        for group in groups_.values():
            row = {"city": group[0]["city"], "area": group[0]["area"] if group[0]["area"] and groups_ is areas else None, **_stats(group)}
            row["vs_average_per_km"] = vs(row)
            out.append(row)
        return sorted(out, key=lambda r: (r["gross_per_km"] is None, -(r["gross_per_km"] or 0), r["city"], r["area"] or ""))

    def split(field, labels):
        out = []
        for value, label in labels.items():
            group = [g for g in rides if g[field] == value]
            if group:
                out.append({field: value, "label": label, **_stats(group)})
        return out
    on_way = [g for g in rides if g["e"]["on_the_way"]]
    off_way = [g for g in rides if not g["e"]["on_the_way"]]
    by_time = [{"band": key, "label": label, **_stats(g), "avg_minutes": _avg_minutes(g)} for _, _, key, label in BANDS if (g := [x for x in rides if x["band"] == key])]
    return {"time_insights": _time_insights(groups), "by_time": by_time, "without_time": sum(1 for g in rides if g["band"] is None), "cost_per_km": cost, "overall": overall,
            "by_destination": rows, "by_city": place_rows(cities), "by_area": place_rows(areas), "without_place": sum(1 for g in rides if not g["city"]),
            "stops": _stops_view(rides),
            "by_class": split("class", CLASS_LABEL), "by_kind": split("kind", KIND_LABEL),
            "by_way": ([{"on_the_way": True, "label": "על הדרך", **_stats(on_way)}] if on_way else []) + ([{"on_the_way": False, "label": "נסיעה ייעודית", **_stats(off_way)}] if off_way else [])}


def quota_view(settings: dict | None, rides: list[dict], today: date) -> dict | None:
    """The free allowance this month: what is allowed, what the owner's other driving and the rides used, what is left — and what the rest is worth at this month's ₪ per
    allowance-km (an estimate, only when rides with a known km exist). None until the owner has entered an allowance."""
    if not settings or (settings["free_km"] is None and settings["free_fuel"] is None):
        return None
    month = month_key(today)
    fuel_km = settings["free_fuel"] / settings["fuel_cost_per_km"] if settings["free_fuel"] is not None and settings["fuel_cost_per_km"] else None
    allowed_options = [x for x in (settings["free_km"], fuel_km) if x is not None]
    allowed = round(min(allowed_options), 1) if allowed_options else None
    fresh = settings["other_km_month"] == month
    other = (settings["other_km_used"] or 0.0) if fresh else 0.0
    this = [g for g in rides if g["month"] == month]
    known = [g for g in this if g["e"]["km"] is not None]
    rides_km = round(sum(g["e"]["km"] for g in known), 1)
    used = round(other + rides_km, 1)
    days_left = calendar_days_left(today)
    remaining = round(max(allowed - used, 0.0), 1) if allowed is not None else None
    priced = [g for g in known if g["e"]["price"] is not None and g["e"]["km"]]
    per_km = round(sum(g["e"]["price"] for g in priced) / sum(g["e"]["km"] for g in priced), 2) if priced else None
    return {"month": month, "allowed_km": allowed, "free_km": settings["free_km"], "fuel_km": round(fuel_km, 1) if fuel_km is not None else None,
            "other_km": round(other, 1), "other_km_stale": settings["other_km_used"] is not None and not fresh, "rides_km": rides_km, "rides_without_km": len(this) - len(known),
            "used_km": used, "remaining_km": remaining, "over_km": round(max(used - allowed, 0.0), 1) if allowed is not None else None, "days_left": days_left,
            "km_per_day_left": round(remaining / days_left, 1) if remaining is not None and days_left else None, "avg_per_km": per_km,
            "worth_of_remaining": round(remaining * per_km, 2) if remaining is not None and per_km is not None else None,
            "fuel_note": None if settings["free_fuel"] is None or fuel_km is not None else "יש מכסת דלק אבל חסרה עלות דלק לק״מ — היא לא נכנסה לחישוב"}


def calendar_days_left(today: date) -> int:
    import calendar
    return calendar.monthrange(today.year, today.month)[1] - today.day + 1


def income_txns(routes: list[dict], trips: list[dict]) -> dict[str, list[fcc_cashflow.Txn]]:
    """Route name (or the one-off source) -> its income entries (one per "yes" day / trip) for the monthly income model."""
    by_id = {r["id"]: r for r in routes}
    out: dict[str, list[fcc_cashflow.Txn]] = {}
    for t in trips:
        if t["outcome"] != "yes":
            continue
        route = by_id.get(t["route_id"]) if t["route_id"] else None
        if t["route_id"] and route is None:
            continue
        amount = _amount(t, route)
        if amount > 0:
            name = route["name"] if route else ONE_OFF_SOURCE
            label = f"{name} · {t['date'].isoformat()}" + ("" if route else f" · {t['destination']}")
            out.setdefault(name, []).append(fcc_cashflow.Txn(amount=amount, occurred=t["date"], ref=t["id"], label=label))
    return out


def income_sources(route_records: list[dict], trip_records: list[dict], taken_names: set[str] = frozenset()) -> list[fcc_cashflow.IncomeSource]:
    """The monthly income model's view of the rides: one VARIABLE source per route and one for the one-off trips, from the days answered "yes". A name an income goal
    already uses gets a suffix, so the two are never merged (no double counting of the same ride)."""
    routes = [r for r in (parse_route(x) for x in route_records) if r["kind"] == "paid"]
    trips = [t for t in (parse_trip(r) for r in trip_records) if t]
    sources = []
    for name, txns in sorted(income_txns(routes, trips).items()):
        sources.append(fcc_cashflow.IncomeSource(f"{name} (מדווח יומי)" if name in taken_names else name, fcc_cashflow.VARIABLE, tuple(txns)))
    return sources


def _place_key(city: str | None, area: str | None = None) -> str:
    return f"{(city or '').strip().casefold()}|{(area or '').strip().casefold()}"


def return_stats(trips: list[dict]) -> dict:
    """What happened on the way back of the owner's ONE-OFF trips, where he recorded it: per area, per city, per destination and overall — the counts of ``empty`` /
    ``continuation`` / ``waited`` and the average minutes waited. A trip whose way back is not recorded yet (``return_status`` empty) is not in these numbers — it waits for the owner
    and does not hold the engine back. The history is random and has competition: this is what happened, with its sample size, never a promise."""
    def block(group: list[dict]) -> dict:
        known = [t for t in group if t["return_status"]]
        waited = [t["waiting_minutes"] for t in known if t["return_status"] == "waited"]
        return {"known": len(known), "empty": sum(1 for t in known if t["return_status"] == "empty"), "continuation": sum(1 for t in known if t["return_status"] == "continuation"),
                "waited": len(waited), "avg_wait_minutes": round(sum(waited) / len(waited), 1) if waited else None}
    one_off = [t for t in trips if t["route_id"] is None and t["outcome"] == "yes"]
    by_dest: dict[str, list[dict]] = {}
    by_city: dict[str, list[dict]] = {}
    by_area: dict[str, list[dict]] = {}
    for t in one_off:
        by_dest.setdefault((t["destination"] or "").strip().casefold(), []).append(t)
        if t["city"]:
            by_city.setdefault(_place_key(t["city"]), []).append(t)
            if t["area"]:
                by_area.setdefault(_place_key(t["city"], t["area"]), []).append(t)
    known_only = lambda groups, label: {k: {**label(g[0]), **block(g)} for k, g in groups.items() if any(t["return_status"] for t in g)}
    return {"overall": block(one_off), "by_destination": known_only(by_dest, lambda t: {"destination": t["destination"]}),
            "by_city": known_only(by_city, lambda t: {"city": t["city"]}), "by_area": known_only(by_area, lambda t: {"city": t["city"], "area": t["area"]})}


def _return_view(stats: dict) -> dict:
    """The return statistics for the screen: overall and per destination / city / area (most known outcomes first)."""
    rows = lambda d, key: sorted(d.values(), key=lambda r: (-r["known"], str(r.get(key))))
    return {"overall": stats["overall"], "by_destination": rows(stats["by_destination"], "destination"), "by_city": rows(stats["by_city"], "city"), "by_area": rows(stats["by_area"], "area"),
            "min_destination": MIN_RETURN_SAMPLE, "min_overall": MIN_OVERALL_SAMPLE}


def pending_updates(trips: list[dict], today: date) -> list[dict]:
    """One-off trips taken in the last two months whose way back the owner has not recorded yet: they wait for him (a conservative there-and-back is assumed meanwhile)."""
    out = [t for t in trips if t["route_id"] is None and t["outcome"] == "yes" and not t["return_status"] and t["date"] >= today - timedelta(days=62)]
    return [{"id": t["id"], "date": t["date"].isoformat(), "weekday": WEEKDAYS_HE[t["date"].weekday()], "destination": t["destination"], "price": t["amount"], "km_one_way": t["km_one_way"],
             "minutes_one_way": t["minutes_one_way"], "start_time": t["start_time"], "kind": t["kind"]} for t in sorted(out, key=lambda t: t["date"], reverse=True)]


def _expected_weights(destination: str | None, city: str | None, area: str | None, stats: dict) -> tuple[dict[str, float] | None, str | None, int, int, float]:
    """(weights over the three ways back, which history was used, its sample, overall sample, average wait). The most specific history that has at least ``MIN_RETURN_SAMPLE`` known
    outcomes — the AREA, else the CITY, else the destination typed — else the overall history when it has ``MIN_OVERALL_SAMPLE``, else None: no number is invented."""
    overall = stats["overall"]
    levels = []
    if city and area:
        levels.append(("area", stats["by_area"].get(_place_key(city, area))))
    if city:
        levels.append(("city", stats["by_city"].get(_place_key(city))))
    if destination:
        levels.append(("destination", stats["by_destination"].get(destination.strip().casefold())))
    best = max((x for _, x in levels if x), key=lambda x: x["known"], default=None)
    for name, pick in levels:
        if pick and pick["known"] >= MIN_RETURN_SAMPLE:
            used, chosen = name, pick
            break
    else:
        used, chosen = (("overall", overall) if overall["known"] >= MIN_OVERALL_SAMPLE else (None, None))
    sample = chosen["known"] if chosen else (best["known"] if best else 0)
    if chosen is None:
        return None, None, sample, overall["known"], 0.0
    n = chosen["known"]
    return {"empty": chosen["empty"] / n, "continuation": chosen["continuation"] / n, "waited": chosen["waited"] / n}, used, sample, overall["known"], chosen["avg_wait_minutes"] or 0.0


def evaluate_offer(offer: dict, route_records: list[dict], trip_records: list[dict], today: date, settings_records: list[dict] | None = None) -> dict:
    """A ride offer, BEFORE it is taken: the owner types the price, the km and minutes of one way (and the start time), and this answers whether it is worth it — read-only, nothing is saved.
    The way back is not known yet, so the offer is priced under each of the three ways back; when the owner's history has enough known outcomes (this destination's, else all of them) the
    scenarios are also weighted into an EXPECTED figure and the sample is shown. Beside it: the free allowance this ride would use (and what part would be beyond it), the owner's average
    ₪ per km / per hour for comparison, and what a ride to this destination usually takes at this hour when he has recorded that. Unknown stays unknown."""
    routes = [r for r in (parse_route(x) for x in route_records) if r["kind"] == "paid"]
    trips = [t for t in (parse_trip(r) for r in trip_records) if t]
    settings = parse_settings(settings_records or [])
    by_id = {r["id"]: r for r in routes}
    cost = default_cost_per_km(routes, settings)
    price = _num(offer.get("price"))
    km1, min1 = _num(offer.get("km_one_way")), _num(offer.get("minutes_one_way"))
    extra_km, extra_min = _num(offer.get("extra_km")), _num(offer.get("extra_minutes"))
    destination = str(offer.get("destination") or "").strip() or None
    city, area = str(offer.get("city") or "").strip() or None, str(offer.get("area") or "").strip() or None
    start = _time(offer.get("start_time"))
    stops_price, stops_km, stops_min = _num(offer.get("stops_price")) or 0.0, _num(offer.get("stops_km")) or 0.0, _num(offer.get("stops_minutes")) or 0.0
    added = int(_num(offer.get("added_stops")) or 0)
    stats = return_stats(trips)
    weights, used, sample_n, overall_n, hist_wait = _expected_weights(destination, city, area, stats)
    typed_wait = _num(offer.get("waiting_minutes"))
    wait = typed_wait if typed_wait is not None else hist_wait

    rides = [{"month": month_key(t["date"]), "e": _trip_ride(t, by_id, cost)[1]} for t in trips if t["outcome"] == "yes" and (t["route_id"] is None or t["route_id"] in by_id)]
    quota = quota_view(settings, rides, today)
    remaining = quota["remaining_km"] if quota else None

    def scenario(key: str, label: str, e: dict) -> dict:
        km = e["km"]
        free = round(min(km, remaining), 1) if km is not None and remaining is not None else None
        beyond = round(km - free, 1) if free is not None else None
        paid = round(beyond * cost, 2) if beyond is not None and cost is not None else None
        return {"key": key, "label": label, "km": km, "minutes": e["minutes"], "gross_per_hour": e["gross_per_hour"], "gross_per_km": e["gross_per_km"], "net_per_hour": e["net_per_hour"],
                "net_per_km": e["net_per_km"], "net": e["net"], "free_km": free, "beyond_km": beyond, "cost_beyond": paid, "stops_per_hour": e["stops_per_hour"], "stops_per_km": e["stops_per_km"],
                "base_gross_per_hour": e["base_gross_per_hour"],
                "net_after_allowance": round(price - paid, 2) if paid is not None and price is not None else None}
    notes: list[str] = []
    if extra_km is not None:                                   # fitted on the way of an own drive: only the detour counts, the way back does not matter
        scenarios = [scenario("on_the_way", "על הדרך (רק העיקוף)", ride_economics(price, km1, min1, "empty", 0.0, cost, extra_km, extra_min, stops_km, stops_min, stops_price))]
        expected = scenarios[0]
    else:
        scenarios = [scenario("empty", RETURN_LABEL["empty"], ride_economics(price, km1, min1, "empty", 0.0, cost, None, None, stops_km, stops_min, stops_price)),
                     scenario("continuation", RETURN_LABEL["continuation"] + " (המחיר לכיוון אחד)", ride_economics(price, km1, min1, "continuation", 0.0, cost, None, None, stops_km, stops_min, stops_price))]
        if wait:
            scenarios.append(scenario("waited", f"המתנה של {round(wait)} דק׳", ride_economics(price, km1, min1, "waited", wait, cost, None, None, stops_km, stops_min, stops_price)))
        else:
            notes.append("לא חושב תרחיש המתנה: הזינו דקות המתנה אפשריות")
        expected = None
        by_key = {sc["key"]: sc for sc in scenarios}
        if weights and all(by_key.get(k) or weights[k] == 0 for k in weights):
            parts = [(weights[k], by_key[k]) for k in weights if weights[k] > 0]
            if all(sc["km"] is not None and sc["minutes"] is not None for _, sc in parts):
                e_km, e_min = sum(w * sc["km"] for w, sc in parts), sum(w * sc["minutes"] for w, sc in parts)
                free = round(min(e_km, remaining), 1) if remaining is not None else None
                paid = round((e_km - free) * cost, 2) if free is not None and cost is not None else None
                r = lambda x: None if x is None else round(x, 2)
                expected = {"key": "expected", "label": "צפוי (לפי ההיסטוריה שלך)", "km": r(e_km), "minutes": r(e_min), "gross_per_hour": r(price / (e_min / 60)) if price is not None and e_min else None,
                            "gross_per_km": r(price / e_km) if price is not None and e_km else None, "net_per_hour": r((price - e_km * cost) / (e_min / 60)) if price is not None and cost is not None and e_min else None,
                            "net_per_km": r((price - e_km * cost) / e_km) if price is not None and cost is not None and e_km else None, "net": r(price - e_km * cost) if price is not None and cost is not None else None,
                            "free_km": free, "beyond_km": r(e_km - free) if free is not None else None, "cost_beyond": paid, "net_after_allowance": r(price - paid) if paid is not None and price is not None else None}
        if expected is None and weights is None:
            notes.append(f"עוד אין מספיק היסטוריה על הדרך חזרה ({sample_n} נסיעות לאזור/עיר/יעד הזה, {overall_n} בסך הכול; נדרשות {MIN_RETURN_SAMPLE} או {MIN_OVERALL_SAMPLE} בסך הכול) — מוצגים שלושת התרחישים בלי ממוצע משוקלל")
    stats_all = profitability(routes, trips, settings)["overall"]
    average = {"gross_per_km": stats_all["gross_per_km"], "gross_per_hour": stats_all["gross_per_hour"], "rides": stats_all["rides"]} if stats_all else None
    vs = None
    if average and expected:
        diff = lambda a, b: round(a - b, 2) if a is not None and b is not None else None
        vs = {"per_km": diff(expected["gross_per_km"], average["gross_per_km"]), "per_hour": diff(expected["gross_per_hour"], average["gross_per_hour"])}
    typical = None
    if (destination or city) and start:
        def same_place(t):
            if city and area and t["city"] and t["area"]:
                return _place_key(t["city"], t["area"]) == _place_key(city, area)
            if city and t["city"]:
                return _place_key(t["city"]) == _place_key(city)
            return bool(destination) and (t["destination"] or "").strip().casefold() == destination.casefold()
        same = [t for t in trips if t["route_id"] is None and t["outcome"] == "yes" and same_place(t) and band_of(t["start_time"]) == band_of(start) and t["minutes_one_way"]]
        if len(same) >= MIN_BAND_RIDES:
            typical = {"band": BAND_LABEL[band_of(start)], "rides": len(same), "avg_minutes_one_way": round(sum(t["minutes_one_way"] for t in same) / len(same), 1)}
    if price is None:
        notes.append("חסר מחיר")
    if km1 is None and extra_km is None:
        notes.append('חסר ק"מ — בלעדיו אין חישוב לק"מ ולמכסה')
    place = None
    if city:
        mine_rides = _profit_rides(routes, trips, settings)
        in_area = [g for g in mine_rides if area and g["city"] and g["area"] and _place_key(g["city"], g["area"]) == _place_key(city, area)]
        in_city = [g for g in mine_rides if g["city"] and _place_key(g["city"]) == _place_key(city)]
        level, mine = ("area", in_area) if in_area else ("city", in_city)       # the area when he has rides there, else the whole city
        if mine:
            st = _stats(mine)
            place = {"level": level, "label": f"{city} · {area}" if level == "area" else city, "rides": st["rides"], "avg_price": st["avg_price"], "gross_per_km": st["gross_per_km"],
                     "gross_per_hour": st["gross_per_hour"]}
    first = scenarios[0]
    stops = None
    if added or stops_price or stops_km or stops_min:
        owner_stops = profitability(routes, trips, settings)["stops"]
        stops = {"added": added, "price": stops_price, "km": stops_km, "minutes": stops_min, "per_hour": first["stops_per_hour"], "per_km": first["stops_per_km"], "base_gross_per_hour": first["base_gross_per_hour"],
                 "total_gross_per_hour": first["gross_per_hour"], "owner_per_hour": owner_stops["per_hour"] if owner_stops else None, "owner_rides": owner_stops["rides"] if owner_stops else 0,
                 "band": BAND_LABEL.get(band_of(start)) if start else None}
    return {"offer": {"destination": destination, "city": city, "area": area, "price": price, "km_one_way": km1, "minutes_one_way": min1, "start_time": start, "on_the_way": extra_km is not None},
            "scenarios": scenarios, "expected": expected,
            "basis": {"used": used, "sample": sample_n, "destination_sample": (stats["by_destination"].get(destination.casefold()) or {}).get("known", 0) if destination else 0,
                      "overall_sample": overall_n, "weights": weights},
            "average": average, "vs_average": vs, "typical_at_this_hour": typical, "place": place, "stops": stops, "allowance_remaining_km": remaining, "cost_per_km": cost, "notes": notes}


def build(route_records: list[dict], trip_records: list[dict], today: date, months: int = 6, settings_records: list[dict] | None = None) -> dict:
    all_routes = [parse_route(r) for r in route_records]
    routes = [r for r in all_routes if r["kind"] == "paid"]
    own = [r for r in all_routes if r["kind"] == "own"]
    trips = [t for t in (parse_trip(r) for r in trip_records) if t]
    settings = parse_settings(settings_records or [])
    by_id = {r["id"]: r for r in routes}
    this_month = month_key(today)
    keys = [m[0] for m in fcc_cashflow.month_windows(today, months)]
    cost = default_cost_per_km(routes, settings)
    rows = []
    for route in routes:
        yes = [t for t in trips if t["route_id"] == route["id"] and t["outcome"] == "yes"]
        history = [route_month(route, trips, m, cost) for m in keys]
        rows.append({**route, "economics": economics(route), "days": days_window(route, trips, today) if route["active"] else [],
                     "this_month": route_month(route, trips, this_month, cost), "history": history, "stops_note": stops_note(yes)})
    recent = sorted((t for t in trips if t["date"] >= today - timedelta(days=62)), key=lambda t: t["date"], reverse=True)
    table, rides = [], []
    for t in trips:                                           # every "yes" ride, with its economics: the allowance this month and the profitability read from the same list
        if t["outcome"] == "yes" and (t["route_id"] is None or t["route_id"] in by_id):
            rides.append({"month": month_key(t["date"]), "e": _trip_ride(t, by_id, cost)[1]})
    for t in recent:
        if not t["outcome"] or (t["route_id"] is not None and t["route_id"] not in by_id):
            continue
        name, e, route = _trip_ride(t, by_id, cost) if t["outcome"] == "yes" else ((by_id[t["route_id"]]["name"] if t["route_id"] in by_id else (t["destination"] or "")), None, None)
        table.append({"id": t["id"], "date": t["date"].isoformat(), "weekday": WEEKDAYS_HE[t["date"].weekday()], "route": name or None, "one_off": t["route_id"] is None,
                      "kind": t["kind"], "outcome": t["outcome"], "stops": t["stops"], "amount": _amount(t, by_id.get(t["route_id"])) if t["outcome"] == "yes" else 0.0,
                      "vehicle_class": t["vehicle_class"] or (route or {}).get("vehicle_class"), "return_status": (t["return_status"] or (route or {}).get("return_status")) if e else None,
                      "city": t["city"], "area": t["area"], "added_stops": t["added_stops"], "stops_price": t["stops_price"], "stops_minutes": t["stops_minutes"],
                      "on_the_way_of": t["on_the_way_of"], "start_time": (t["start_time"] or (route or {}).get("start_time")), "band": band_of(t["start_time"] or (route or {}).get("start_time")),
                      "km": e["km"] if e else None, "minutes": e["minutes"] if e else None,
                      "gross_per_hour": e["gross_per_hour"] if e else None, "gross_per_km": e["gross_per_km"] if e else None, "net_per_hour": e["net_per_hour"] if e else None})
    one_off = one_off_month(trips, this_month)
    return {"month": this_month, "today": today.isoformat(), "routes": rows, "own_trips": [{"id": r["id"], "name": r["name"], "weekdays": r["weekdays"], "km_one_way": r["km_one_way"],
                                                                                       "minutes_one_way": r["minutes_one_way"]} for r in own],
            "trips": table[:120], "one_off": one_off, "pending_updates": pending_updates(trips, today), "return_stats": _return_view(return_stats(trips)), "profitability": profitability(routes, trips, settings), "quota": quota_view(settings, rides, today),
            "settings": {k: settings[k] for k in ("free_km", "free_fuel", "fuel_cost_per_km", "cost_per_km", "other_km_used", "other_km_month")} if settings else None,
            "income_this_month": round(sum(r["this_month"]["income"] for r in rows) + one_off["income"], 2), "default_cost_per_km": cost,
            # past days (not today / tomorrow, not a resting Saturday) still without an answer: a missing day is never counted as "no ride" or as income
            "unanswered_past": sum(1 for r in rows if r["active"] for d in r["days"] if d["outcome"] is None and d["date"] < today.isoformat() and not d["rest_day"])}
