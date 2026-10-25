"""TrafficAwareProvider — stub כבוי. Google Routes ייכנס בשלב נפרד (C3) באישור מפורש.

C1: אין קריאה לרשת, אין מפתח, אין חיוב. כל קריאה מחזירה NOT_CONFIGURED.
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

_REASON = "ספק התנועה (Google) לא מוגדר"


class TrafficAwareProvider:
    mode = RouteMode.TRAFFIC_AWARE

    def __init__(self):
        self.requests_used = 0

    def leg(self, request: LegRequest) -> LegResult:
        return LegResult(LegStatus.NOT_CONFIGURED, reason=_REASON)

    def matrix(self, request: MatrixRequest) -> MatrixResult:
        return MatrixResult(LegStatus.NOT_CONFIGURED, reason=_REASON)

    def health(self) -> ProviderHealth:
        return ProviderHealth(False, _REASON)
