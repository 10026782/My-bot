"""חוזה RouteProvider של Smart Trips: מקור אחיד לק"מ ולדקות של רגל נסיעה.

שלושה מצבים (SMART_TRIPS_P0_CALCULATION_CONTRACT.md §14.4/§15.5):
  LOCAL_ROUTE   — ניתוב מקומי (עתידי; אין מימוש חי)
  TRAFFIC_AWARE — Google, רק בפעולה מפורשת של המשתמש (עתידי; stub כבוי)
  MANUAL        — המשתמש מקליד ק"מ ודקות

כלל ברזל: אין המצאת מרחק, זמן או עומס. ספק שאין לו תשובה מחזיר סטטוס שאינו OK ולא ערך.
מודול טהור: בלי רשת, בלי Airtable, בלי קריאה לספק בתשלום.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol


class RouteMode(str, Enum):
    LOCAL_ROUTE = "LOCAL_ROUTE"
    TRAFFIC_AWARE = "TRAFFIC_AWARE"
    MANUAL = "MANUAL"


class LegStatus(str, Enum):
    OK = "ok"
    NO_ROUTE = "no_route"                # הספק ענה שאין מסלול
    UNAVAILABLE = "unavailable"          # ספק לא זמין/לא בריא
    NOT_CONFIGURED = "not_configured"    # ספק כבוי או בלי הגדרה
    MISSING_INPUT = "missing_input"      # מצב ידני: המשתמש לא הזין את הרגל
    BUDGET_EXCEEDED = "budget_exceeded"


class AccuracyClass(str, Enum):
    USER_INPUT = "user_input"
    ROAD_FREE_FLOW_UNCALIBRATED = "road_free_flow_uncalibrated"
    ROAD_FREE_FLOW_MEASURED = "road_free_flow_measured"
    TRAFFIC_FORECAST = "traffic_forecast"


@dataclass(frozen=True)
class LegRequest:
    """בקשה לרגל אחת. `key` הוא תפקיד הרגל (to_pickup / outbound / ...), `offer_id` ההצעה שאליה היא שייכת."""
    origin: Any
    dest: Any
    depart_at: datetime | None
    key: str
    offer_id: str


@dataclass(frozen=True)
class LegResult:
    status: LegStatus
    km: Decimal | None = None
    minutes: Decimal | None = None
    provenance: dict = field(default_factory=dict)
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status is LegStatus.OK and self.km is not None and self.minutes is not None


@dataclass(frozen=True)
class MatrixRequest:
    """מטריצה בין צמתים לפי סדר `nodes` (צומת 0 = נקודת ההתחלה)."""
    nodes: tuple
    depart_at: datetime | None
    key: str = "stops"


@dataclass(frozen=True)
class MatrixResult:
    status: LegStatus
    km: tuple | None = None          # km[i][j], Decimal
    minutes: tuple | None = None     # minutes[i][j], Decimal
    provenance: dict = field(default_factory=dict)
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status is LegStatus.OK and self.km is not None and self.minutes is not None


@dataclass(frozen=True)
class ProviderHealth:
    ok: bool
    reason: str = ""


class RouteProvider(Protocol):
    mode: RouteMode
    requests_used: int

    def leg(self, request: LegRequest) -> LegResult: ...

    def matrix(self, request: MatrixRequest) -> MatrixResult: ...

    def health(self) -> ProviderHealth: ...


def make_provenance(source: str, time_basis: str, accuracy_class: AccuracyClass, note: str, **extra) -> dict:
    """ה-provenance שמוצג לכל רגל: מקור, בסיס זמן, רמת דיוק והסבר בעברית."""
    out = {
        "source": source,
        "time_basis": time_basis,
        "accuracy_class": accuracy_class.value,
        "accuracy_note": note,
    }
    out.update(extra)
    return out
