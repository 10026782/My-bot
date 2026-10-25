"""חוזי קלט וולידציה למנוע כדאיות הנסיעות. Decimal פנימית; עיגול רק בפלט.

שגיאות ולידציה הן ValueError עם שם השדה בלבד (לעולם לא ערכים או פרטים פנימיים).
סכומים בש"ח, מרחק בק"מ, זמן בדקות, אזור זמן Asia/Jerusalem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

ENGINE_VERSION = "1.0.0"
TZ = ZoneInfo("Asia/Jerusalem")
ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)

MIN_OFFERS = 1
MAX_OFFERS = 5
OBJECTIVES = ("throughput", "contribution", "earliest_arrival", "least_deadhead", "downside")


def dec(value, name: str, minimum=None, maximum=None) -> Decimal:
    """ממיר מספר JSON ל-Decimal; דוחה bool, מחרוזת, NaN/Infinity וחריגה מהטווח."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a finite number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < Decimal(str(minimum)):
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and number > Decimal(str(maximum)):
        raise ValueError(f"{name} must be <= {maximum}")
    return number


def opt_dec(raw: dict, key: str, name: str, minimum=None, maximum=None):
    return None if raw.get(key) is None else dec(raw[key], name, minimum, maximum)


def rnd(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def money(value: Decimal | None):
    return None if value is None else float(rnd(value, 2))


def minutes_out(value: Decimal | None):
    return None if value is None else int(rnd(value, 0))


def km_out(value: Decimal | None):
    return None if value is None else float(rnd(value, 1))


@dataclass(frozen=True)
class Place:
    """נקודה: טקסט חופשי (תווית) או קואורדינטות. ב-C1 אין geocoding; התווית מוצגת בלבד."""
    label: str
    lat: Decimal | None = None
    lng: Decimal | None = None

    def public(self) -> dict:
        return {"label": self.label}


def parse_place(raw, name: str) -> Place:
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be an object")
    text = raw.get("text")
    if text is not None:
        if not isinstance(text, str) or not text.strip() or len(text) > 200:
            raise ValueError(f"{name}.text must be a nonempty string up to 200 chars")
        return Place(text.strip())
    if raw.get("lat") is not None and raw.get("lng") is not None:
        lat, lng = dec(raw["lat"], f"{name}.lat", -90, 90), dec(raw["lng"], f"{name}.lng", -180, 180)
        return Place(f"{rnd(lat, 5)},{rnd(lng, 5)}", lat, lng)
    raise ValueError(f"{name} needs text or lat/lng")


@dataclass(frozen=True)
class Vehicle:
    fuel_price: Decimal      # ש"ח לליטר
    km_per_l: Decimal
    wear_per_km: Decimal     # שחיקה/פחת שולי לק"מ
    fee_pct: Decimal         # עמלת פלטפורמה באחוזים מכל תשלום
    fixed_cost: Decimal      # עלות קבועה לתרחיש (אגרות, חניה וכו')

    def fuel(self, km: Decimal) -> Decimal:
        return km / self.km_per_l * self.fuel_price

    def wear(self, km: Decimal) -> Decimal:
        return km * self.wear_per_km


def parse_vehicle(raw) -> Vehicle:
    if not isinstance(raw, dict):
        raise ValueError("vehicle must be an object")
    return Vehicle(
        fuel_price=dec(raw.get("fuel_price_ils_per_l"), "vehicle.fuel_price_ils_per_l", 1, 30),
        km_per_l=dec(raw.get("km_per_l"), "vehicle.km_per_l", 1, 50),
        wear_per_km=dec(raw.get("wear_ils_per_km", 0), "vehicle.wear_ils_per_km", 0, 10),
        fee_pct=dec(raw.get("platform_fee_pct", 0), "vehicle.platform_fee_pct", 0, 100),
        fixed_cost=dec(raw.get("fixed_cost_ils", 0), "vehicle.fixed_cost_ils", 0, 5000),
    )


@dataclass(frozen=True)
class ReturnPlan:
    probability: Decimal | None        # None = לא הוזן ⇒ חזרה ריקה (p=0)
    fare: Decimal | None
    pickup: Place | None               # None = נקודת הפריקה
    destination: Place | None          # None = היעד הסופי
    wait_success: Decimal
    wait_failure: Decimal


@dataclass(frozen=True)
class OfferInput:
    id: str
    pickup: Place
    dropoff: Place
    fare: Decimal
    service_minutes: Decimal
    extra_costs: Decimal
    ret: ReturnPlan | None

    @property
    def p(self) -> Decimal:
        return ZERO if self.ret is None or self.ret.probability is None else self.ret.probability

    @property
    def has_return_data(self) -> bool:
        return self.ret is not None and self.ret.fare is not None


def parse_offer(raw, index: int) -> OfferInput:
    name = f"offers[{index}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be an object")
    offer_id = raw.get("id")
    if not isinstance(offer_id, str) or not offer_id.strip() or len(offer_id) > 20:
        raise ValueError(f"{name}.id must be a nonempty string up to 20 chars")
    ret_raw = raw.get("return")
    ret = None
    if ret_raw is not None:
        if not isinstance(ret_raw, dict):
            raise ValueError(f"{name}.return must be an object")
        ret = ReturnPlan(
            probability=opt_dec(ret_raw, "probability", f"{name}.return.probability", 0, 1),
            fare=opt_dec(ret_raw, "fare_ils", f"{name}.return.fare_ils", 0, 5000),
            pickup=None if ret_raw.get("pickup") is None else parse_place(ret_raw["pickup"], f"{name}.return.pickup"),
            destination=None if ret_raw.get("destination") is None else parse_place(ret_raw["destination"], f"{name}.return.destination"),
            wait_success=dec(ret_raw.get("wait_minutes_success", 0), f"{name}.return.wait_minutes_success", 0, 720),
            wait_failure=dec(ret_raw.get("wait_minutes_failure", 0), f"{name}.return.wait_minutes_failure", 0, 720),
        )
        if ret.probability is not None and ret.probability > 0 and ret.fare is None:
            raise ValueError(f"{name}.return.fare_ils is required when probability > 0")
    return OfferInput(
        id=offer_id.strip(),
        pickup=parse_place(raw.get("pickup"), f"{name}.pickup"),
        dropoff=parse_place(raw.get("dropoff"), f"{name}.dropoff"),
        fare=dec(raw.get("outbound_fare_ils"), f"{name}.outbound_fare_ils", 0, 5000),
        service_minutes=dec(raw.get("service_minutes", 0), f"{name}.service_minutes", 0, 240),
        extra_costs=dec(raw.get("extra_costs_ils", 0), f"{name}.extra_costs_ils", 0, 5000),
        ret=ret,
    )


def parse_departure(raw) -> datetime | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("departure_at must be an ISO-8601 string")
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError("departure_at must be an ISO-8601 string") from None
    if moment.tzinfo is None:
        raise ValueError("departure_at must include a timezone offset")
    return moment.astimezone(TZ)


@dataclass(frozen=True)
class CompareRequest:
    vehicle: Vehicle
    origin: Place
    final: Place
    departure: datetime | None
    objective: str
    opportunity_cost: Decimal
    offers: tuple[OfferInput, ...]
    routing_mode: str | None
    traffic_confirm: bool


def parse_compare_request(params) -> CompareRequest:
    if not isinstance(params, dict):
        raise ValueError("request body must be an object")
    offers_raw = params.get("offers")
    if not isinstance(offers_raw, list) or not MIN_OFFERS <= len(offers_raw) <= MAX_OFFERS:
        raise ValueError(f"offers must be a list of {MIN_OFFERS}-{MAX_OFFERS}")
    offers = tuple(parse_offer(item, i) for i, item in enumerate(offers_raw))
    if len({offer.id for offer in offers}) != len(offers):
        raise ValueError("offers[].id must be unique")
    objective = params.get("objective", "throughput")
    if objective not in OBJECTIVES:
        raise ValueError("objective is not supported")
    mode = params.get("routing_mode")
    if mode is not None and not isinstance(mode, str):
        raise ValueError("routing_mode must be a string")
    return CompareRequest(
        vehicle=parse_vehicle(params.get("vehicle")),
        origin=parse_place(params.get("origin"), "origin"),
        final=parse_place(params.get("final_destination"), "final_destination"),
        departure=parse_departure(params.get("departure_at")),
        objective=objective,
        opportunity_cost=dec(params.get("opportunity_cost_ils_per_h", 0), "opportunity_cost_ils_per_h", 0, 2000),
        offers=offers,
        routing_mode=mode,
        traffic_confirm=params.get("traffic_confirm") is True,
    )
