"""LocalRouteProvider — stub כבוי. ספק ניתוב מקומי (OSRM) יוגדר רק אחרי M1, בדיקת משאבים ומדידה (G1).

C1: אין שירות, אין קריאה, אין התקנה. כל קריאה מחזירה UNAVAILABLE, ולכן אין מעבר שקט לספק בתשלום.
"""

from __future__ import annotations

from core.trips.route_provider import (
    LegRequest,
    LegResult,
    LegStatus,
    MatrixRequest,
    MatrixResult,
    ProviderHealth,
    RouteMode,
)

_REASON = "ניתוב מקומי לא הוגדר"


class LocalRouteProvider:
    mode = RouteMode.LOCAL_ROUTE

    def __init__(self):
        self.requests_used = 0

    def leg(self, request: LegRequest) -> LegResult:
        return LegResult(LegStatus.UNAVAILABLE, reason=_REASON)

    def matrix(self, request: MatrixRequest) -> MatrixResult:
        return MatrixResult(LegStatus.UNAVAILABLE, reason=_REASON)

    def health(self) -> ProviderHealth:
        return ProviderHealth(False, _REASON)
