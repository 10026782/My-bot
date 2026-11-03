"""בחירת ספק ניתוב. כללים (חוזה §15.5, §17):

- מצב לא צוין: ROAD_ROUTE אם הוגדר ובריא, אחרת LOCAL_ROUTE אם בריא, אחרת MANUAL.
- TRAFFIC_AWARE רק אם `traffic_confirm` הוא True (הלקוח שולח אותו מלחיצה מפורשת; השרת לא מציב אותו).
- אין שדרוג אוטומטי: כישלון של ספק לא מעביר לספק אחר, ההצעה פשוט לא-שלמה.
"""

from __future__ import annotations

from core.trips.route_provider import RouteMode, RouteProvider


def select_provider(
    mode: str | None,
    *,
    manual: RouteProvider,
    road: RouteProvider | None = None,
    local: RouteProvider | None = None,
    traffic: RouteProvider | None = None,
    traffic_confirm: bool = False,
) -> RouteProvider:
    if mode is None:
        for candidate in (road, local):
            if candidate is not None and candidate.health().ok:
                return candidate
        return manual
    try:
        requested = RouteMode(mode)
    except ValueError:
        raise ValueError("routing_mode must be ROAD_ROUTE, LOCAL_ROUTE, TRAFFIC_AWARE or MANUAL") from None
    if requested is RouteMode.MANUAL:
        return manual
    if requested is RouteMode.ROAD_ROUTE:
        if road is None:
            raise ValueError("road routing is not configured")
        return road
    if requested is RouteMode.LOCAL_ROUTE:
        if local is None:
            raise ValueError("local routing is not configured")
        return local
    if traffic_confirm is not True:
        raise ValueError("traffic_confirm is required for TRAFFIC_AWARE")
    if traffic is None:
        raise ValueError("traffic provider is not configured")
    return traffic
