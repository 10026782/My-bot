"""בחירת ספק ניתוב. כללים (חוזה §15.5):

- מצב לא צוין: LOCAL_ROUTE אם הוגדר ובריא, אחרת MANUAL.
- TRAFFIC_AWARE רק אם `traffic_confirm` הוא True (הלקוח שולח אותו מלחיצה מפורשת; השרת לא מציב אותו).
- אין שדרוג אוטומטי: כישלון של ספק לא מעביר לספק אחר, ההצעה פשוט לא-שלמה.
"""

from __future__ import annotations

from core.trips.route_provider import RouteMode, RouteProvider


def select_provider(
    mode: str | None,
    *,
    manual: RouteProvider,
    local: RouteProvider | None = None,
    traffic: RouteProvider | None = None,
    traffic_confirm: bool = False,
) -> RouteProvider:
    if mode is None:
        if local is not None and local.health().ok:
            return local
        return manual
    try:
        requested = RouteMode(mode)
    except ValueError:
        raise ValueError("routing_mode must be LOCAL_ROUTE, TRAFFIC_AWARE or MANUAL") from None
    if requested is RouteMode.MANUAL:
        return manual
    if requested is RouteMode.LOCAL_ROUTE:
        if local is None:
            raise ValueError("local routing is not configured")
        return local
    if traffic_confirm is not True:
        raise ValueError("traffic_confirm is required for TRAFFIC_AWARE")
    if traffic is None:
        raise ValueError("traffic provider is not configured")
    return traffic
