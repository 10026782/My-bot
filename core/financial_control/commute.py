"""FCC commute income — pure, read-only (no I/O, no writes, no model).

A recurring paid ride (e.g. 6 days a week): every day the owner answers "is there a ride tomorrow?" and, if so, with how many stops (2 or 3). This module only
*derives* from the owner's two tables (Commute Routes, Commute Trips):

* the month's income = the days answered "yes" × the route's day price (the price is stored on the trip row on the day it is answered, so a later price change never
  rewrites history); the stops count is only tracked (it does not change the price) so the owner can see whether most rides have 3 stops;
* what to collect at the end of the month, week by week;
* the economics of one trip day: km, minutes, ₪ per hour, ₪ per km — gross, and net of the owner's own cost per km when he entered one (never a guess);
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


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _sel(v):
    return v.get("name") if isinstance(v, dict) else v


def _day(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def parse_route(rec: dict) -> dict:
    f = rec.get("fields") or {}
    return {"id": rec.get("id"), "name": str(f.get("Name") or "").strip() or "נסיעה", "price": _num(f.get("Day Price")),
            "km_one_way": _num(f.get("Km One Way")), "minutes_one_way": _num(f.get("Minutes One Way")), "cost_per_km": _num(f.get("Cost Per Km")),
            "planned_days": _num(f.get("Planned Days Per Week")), "active": _sel(f.get("Status")) != "paused", "notes": f.get("Notes") or None}


def parse_trip(rec: dict) -> dict | None:
    f = rec.get("fields") or {}
    route = f.get("Route")
    route_id = route[0] if isinstance(route, list) and route else None
    day = _day(f.get("Trip Date"))
    if not route_id or day is None:
        return None
    outcome = _sel(f.get("Outcome"))
    stops = _num(f.get("Stops"))
    return {"id": rec.get("id"), "route_id": route_id, "date": day, "outcome": outcome if outcome in ("yes", "no") else None,
            "stops": int(stops) if stops else None, "amount": _num(f.get("Amount"))}


def _amount(trip: dict, route: dict | None) -> float:
    """What a "yes" day is worth: the amount stored on the row, else the route's current day price (a row edited by hand)."""
    if trip["amount"] is not None:
        return trip["amount"]
    return (route or {}).get("price") or 0.0


def economics(route: dict) -> dict:
    """One trip day (there and back). Gross = price only; net also takes the owner's cost per km. Every figure is None while an input is missing."""
    price, km1, min1, cost = route["price"], route["km_one_way"], route["minutes_one_way"], route["cost_per_km"]
    km = round(km1 * 2, 2) if km1 is not None else None
    minutes = round(min1 * 2, 2) if min1 is not None else None
    hours = minutes / 60 if minutes else None
    fuel = round(km * cost, 2) if km is not None and cost is not None else None
    net = round(price - fuel, 2) if price is not None and fuel is not None else None
    r = lambda x: None if x is None else round(x, 2)
    return {"price": price, "km_per_day": km, "minutes_per_day": minutes, "hours_per_day": r(hours),
            "gross_per_hour": r(price / hours) if price is not None and hours else None,
            "gross_per_km": r(price / km) if price is not None and km else None,
            "vehicle_cost_per_day": fuel, "net_per_day": net,
            "net_per_hour": r(net / hours) if net is not None and hours else None,
            "net_per_km": r(net / km) if net is not None and km else None,
            "monthly_potential": r(price * route["planned_days"] * WEEKS_PER_MONTH) if price is not None and route["planned_days"] else None}


def week_start(d: date) -> date:
    """Sunday of the week of ``d`` (the Israeli week)."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def route_month(route: dict, trips: list[dict], month: str) -> dict:
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
    return {"month": month, "yes_days": len(yes), "no_days": len(no), "income": income, "stops": {str(n): c for n, c in stops.items()},
            "stops_recorded": known, "three_share": round(stops[3] / known, 4) if known else None,
            "weeks": [{"week_start": w.isoformat(), "yes_days": c[0], "income": round(c[1], 2)} for w, c in sorted(weeks.items())]}


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
    """The days the owner can answer for ONE route: the last week and tomorrow, each with its current answer (None = not answered)."""
    by_day = {t["date"]: t for t in trips if t["route_id"] == route["id"]}
    out = []
    for back in range(-WINDOW_FORWARD, WINDOW_BACK + 1):
        d = today - timedelta(days=back)
        t = by_day.get(d)
        out.append({"date": d.isoformat(), "weekday": WEEKDAYS_HE[d.weekday()], "is_tomorrow": d == today + timedelta(days=1), "is_today": d == today,
                    "outcome": t["outcome"] if t else None, "stops": t["stops"] if t else None, "trip_id": t["id"] if t else None})
    return out


def income_txns(routes: list[dict], trips: list[dict]) -> dict[str, list[fcc_cashflow.Txn]]:
    """Route name -> its income entries (one per "yes" day) for the monthly income model."""
    by_id = {r["id"]: r for r in routes}
    out: dict[str, list[fcc_cashflow.Txn]] = {}
    for t in trips:
        route = by_id.get(t["route_id"])
        if route is None or t["outcome"] != "yes":
            continue
        amount = _amount(t, route)
        if amount > 0:
            out.setdefault(route["name"], []).append(fcc_cashflow.Txn(amount=amount, occurred=t["date"], ref=t["id"], label=f"{route['name']} · {t['date'].isoformat()}"))
    return out


def income_sources(route_records: list[dict], trip_records: list[dict], taken_names: set[str] = frozenset()) -> list[fcc_cashflow.IncomeSource]:
    """The monthly income model's view of the rides: one VARIABLE source per route, from the days answered "yes". A name an income goal already uses gets a suffix, so
    the two are never merged (no double counting of the same ride)."""
    routes = [parse_route(r) for r in route_records]
    trips = [t for t in (parse_trip(r) for r in trip_records) if t]
    sources = []
    for name, txns in sorted(income_txns(routes, trips).items()):
        sources.append(fcc_cashflow.IncomeSource(f"{name} (מדווח יומי)" if name in taken_names else name, fcc_cashflow.VARIABLE, tuple(txns)))
    return sources


def build(route_records: list[dict], trip_records: list[dict], today: date, months: int = 6) -> dict:
    routes = [parse_route(r) for r in route_records]
    trips = [t for t in (parse_trip(r) for r in trip_records) if t]
    by_id = {r["id"]: r for r in routes}
    this_month = month_key(today)
    keys = [m[0] for m in fcc_cashflow.month_windows(today, months)]
    rows = []
    for route in routes:
        yes = [t for t in trips if t["route_id"] == route["id"] and t["outcome"] == "yes"]
        history = [route_month(route, trips, m) for m in keys]
        rows.append({**route, "economics": economics(route), "days": days_window(route, trips, today) if route["active"] else [],
                     "this_month": route_month(route, trips, this_month), "history": history, "stops_note": stops_note(yes)})
    recent = sorted((t for t in trips if t["date"] >= today - timedelta(days=62)), key=lambda t: t["date"], reverse=True)
    table = [{"id": t["id"], "date": t["date"].isoformat(), "weekday": WEEKDAYS_HE[t["date"].weekday()], "route": by_id[t["route_id"]]["name"] if t["route_id"] in by_id else None,
              "outcome": t["outcome"], "stops": t["stops"], "amount": _amount(t, by_id.get(t["route_id"])) if t["outcome"] == "yes" else 0.0}
             for t in recent if t["outcome"]]
    return {"month": this_month, "today": today.isoformat(), "routes": rows, "trips": table[:120],
            "income_this_month": round(sum(r["this_month"]["income"] for r in rows), 2),
            # past days (not today / tomorrow) still without an answer: a missing day is never counted as "no ride" or as income
            "unanswered_past": sum(1 for r in rows if r["active"] for d in r["days"] if d["outcome"] is None and d["date"] < today.isoformat())}
