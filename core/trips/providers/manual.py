"""ManualProvider — המשתמש מקליד ק"מ ודקות לכל רגל (או מטריצה בין תחנות).

אין ערכי ברירת מחדל: רגל שלא הוזנה ⇒ MISSING_INPUT (ההצעה תסומן לא-שלמה), לא ניחוש.
"""

from __future__ import annotations

import math
from decimal import Decimal

from core.trips.route_provider import (
    AccuracyClass,
    LegRequest,
    LegResult,
    LegStatus,
    MatrixRequest,
    MatrixResult,
    ProviderHealth,
    RouteMode,
    make_provenance,
)

MAX_LEG_KM = Decimal(1000)
MAX_LEG_MINUTES = Decimal(1440)
_NOTE = "קלט ידני של המשתמש, ללא תנועה"


def _num(value, name: str, maximum: Decimal) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a finite number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    number = Decimal(str(value))
    if number < 0 or number > maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")
    return number


def _pair(raw, name: str) -> tuple[Decimal, Decimal]:
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be an object")
    return _num(raw.get("km"), f"{name}.km", MAX_LEG_KM), _num(raw.get("minutes"), f"{name}.minutes", MAX_LEG_MINUTES)


class ManualProvider:
    mode = RouteMode.MANUAL

    def __init__(self, legs: dict | None = None, matrix: dict | None = None):
        """legs: {offer_id: {leg_key: {"km":.., "minutes":..}}}; matrix: {"km": [[..]], "minutes": [[..]]}."""
        self.requests_used = 0
        self._legs: dict[str, dict[str, tuple[Decimal, Decimal]]] = {}
        for offer_id, by_key in (legs or {}).items():
            if not isinstance(by_key, dict):
                raise ValueError(f"manual_legs.{offer_id} must be an object")
            self._legs[str(offer_id)] = {key: _pair(raw, f"manual_legs.{offer_id}.{key}") for key, raw in by_key.items()}
        self._matrix = self._parse_matrix(matrix) if matrix is not None else None

    @staticmethod
    def _parse_matrix(raw):
        if not isinstance(raw, dict):
            raise ValueError("manual_matrix must be an object")
        km, minutes = raw.get("km"), raw.get("minutes")
        if not isinstance(km, list) or not isinstance(minutes, list) or not km or len(km) != len(minutes):
            raise ValueError("manual_matrix needs km and minutes as equal-size square lists")
        size = len(km)
        for name, table in (("km", km), ("minutes", minutes)):
            if any(not isinstance(row, list) or len(row) != size for row in table):
                raise ValueError(f"manual_matrix.{name} must be square")
        maxima = {"km": MAX_LEG_KM, "minutes": MAX_LEG_MINUTES}
        return (
            tuple(tuple(_num(v, f"manual_matrix.km[{i}][{j}]", maxima["km"]) for j, v in enumerate(row)) for i, row in enumerate(km)),
            tuple(tuple(_num(v, f"manual_matrix.minutes[{i}][{j}]", maxima["minutes"]) for j, v in enumerate(row)) for i, row in enumerate(minutes)),
        )

    def leg(self, request: LegRequest) -> LegResult:
        pair = self._legs.get(request.offer_id, {}).get(request.key)
        if pair is None:
            return LegResult(LegStatus.MISSING_INPUT, reason=f"missing manual leg {request.key}")
        km, minutes = pair
        return LegResult(LegStatus.OK, km, minutes, make_provenance("manual", "manual", AccuracyClass.USER_INPUT, _NOTE))

    def matrix(self, request: MatrixRequest) -> MatrixResult:
        if self._matrix is None:
            return MatrixResult(LegStatus.MISSING_INPUT, reason="missing manual matrix")
        size = len(self._matrix[0])
        if size != len(request.nodes):
            return MatrixResult(LegStatus.MISSING_INPUT, reason="manual matrix size does not match the stops")
        return MatrixResult(LegStatus.OK, self._matrix[0], self._matrix[1],
                            make_provenance("manual", "manual", AccuracyClass.USER_INPUT, _NOTE))

    def health(self) -> ProviderHealth:
        return ProviderHealth(True)
