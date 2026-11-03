"""OrsProvider — OpenRouteService (HeiGIT) כספק כבישים מנוהל, ללא נתוני פקקים.

מצב ROAD_ROUTE: ק"מ ודקות בזרימה חופשית לפי נתוני OpenStreetMap. אין תנועה חיה ואין נתון שלא נמדד.
כל בקשה היא Matrix אחד שמכסה את כל הרגליים (prefetch); Directions אינו בשימוש.
ראו SMART_TRIPS_P0_CALCULATION_CONTRACT.md §17.

בטיחות:
- בלי `ORS_API_KEY` הספק "לא מוגדר": אין קריאה לרשת.
- מפתח בצד שרת בלבד; לא נרשם ללוג. קואורדינטות לא נרשמות ללוג.
- מגביל קצב מתחת למכסה (28 לדקה, תקרה יומית רכה), 429 עם backoff, 403 חוסם את הספק עד חלון חדש,
  תקלות רצופות פותחות circuit breaker. אין מעבר לספק אחר: כישלון = הצעה לא-שלמה.
- ה-transport מוזרק, ולכן הבדיקות לא פונות לרשת.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

from core.trips.leg_cache import LegCache
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

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.heigit.org/openrouteservice"   # ה-host הישן api.openrouteservice.org מוצא משימוש
PROFILE = "driving-car"
MAX_PAIRS = 3500                                               # מגבלת ה-Matrix הציבורי לבקשה
DAY_SECONDS = 86400
# נוסח הייחוס לאימות מול תנאי השימוש לפני שחרור
ATTRIBUTION = "© OpenStreetMap contributors · openrouteservice (HeiGIT)"
_NOTE = "זרימה חופשית לפי נתוני OpenStreetMap, ללא פקקים; לא מכויל"


@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: dict | None = None
    headers: dict = field(default_factory=dict)


class TransportError(Exception):
    """timeout / שגיאת חיבור. ללא פרטים רגישים."""


Transport = Callable[[str, dict, dict, float], TransportResponse]


def httpx_transport(url: str, headers: dict, body: dict, timeout: float) -> TransportResponse:
    import httpx  # noqa: PLC0415 — ייבוא עצל: הבדיקות לא תלויות ברשת
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.HTTPError:
        raise TransportError from None
    try:
        data = response.json()
    except ValueError:
        data = None
    return TransportResponse(response.status_code, data if isinstance(data, dict) else None,
                             {k.lower(): v for k, v in response.headers.items()})


class _OrsError(Exception):
    def __init__(self, status: LegStatus, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


class _Limiter:
    """חלון גולש: מכסה דקתית, ותקרה יומית רכה (24 שעות גולשות)."""

    def __init__(self, per_minute: int, daily_cap: int, clock: Callable[[], float]):
        self._per_minute, self._daily_cap, self._clock = per_minute, daily_cap, clock
        self._minute: deque = deque()
        self._day: deque = deque()

    def _prune(self, now: float) -> None:
        while self._minute and now - self._minute[0] >= 60:
            self._minute.popleft()
        while self._day and now - self._day[0] >= DAY_SECONDS:
            self._day.popleft()

    def daily_exhausted(self) -> bool:
        self._prune(self._clock())
        return len(self._day) >= self._daily_cap

    def wait_needed(self) -> float:
        now = self._clock()
        self._prune(now)
        if len(self._minute) < self._per_minute:
            return 0.0
        return max(0.0, 60 - (now - self._minute[0]))

    def record(self) -> None:
        now = self._clock()
        self._minute.append(now)
        self._day.append(now)


def _coord(place):
    lat, lng = getattr(place, "lat", None), getattr(place, "lng", None)
    if lat is None or lng is None:
        return None
    return (round(Decimal(lat), 5), round(Decimal(lng), 5))


class OrsProvider:
    mode = RouteMode.ROAD_ROUTE

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] | None = None,
        timeout: float = 5.0,
        per_minute: int = 28,
        daily_soft_cap: int = 400,
        max_wait_seconds: float = 2.0,
        max_retries_429: int = 2,
        cache: LegCache | None = None,
    ):
        self.requests_used = 0
        self._key = api_key or None
        self._base = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._transport = transport or httpx_transport
        self._sleep, self._clock = sleep, clock
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._timeout, self._max_wait, self._max_429 = timeout, max_wait_seconds, max_retries_429
        self._limiter = _Limiter(per_minute, daily_soft_cap, clock)
        self._cache = cache or LegCache(clock=clock)
        self._lock = threading.Lock()          # בקשה אחת בכל רגע: מגן על המכסה ומאחד בקשות זהות
        self._failures = 0
        self._open_until = 0.0                 # circuit breaker
        self._blocked_until = 0.0              # אחרי 403 (מכסה יומית/מפתח)
        self._computed_at: dict = {}

    @classmethod
    def from_env(cls, **kwargs) -> "OrsProvider":
        return cls(os.environ.get("ORS_API_KEY"), base_url=os.environ.get("ORS_BASE_URL"), **kwargs)

    # ── בריאות ───────────────────────────────────────────────────────────────────────────────
    def health(self) -> ProviderHealth:
        now = self._clock()
        if not self._key:
            return ProviderHealth(False, "ספק הכבישים לא מוגדר")
        if now < self._blocked_until:
            return ProviderHealth(False, "מכסת הניתוב היומית נגמרה")
        if now < self._open_until:
            return ProviderHealth(False, "ספק הכבישים אינו זמין כרגע")
        return ProviderHealth(True)

    # ── ממשק RouteProvider ───────────────────────────────────────────────────────────────────
    def prefetch(self, requests: list[LegRequest]) -> None:
        """בקשת Matrix אחת לכל הרגליים החסרות. כישלון נרשם כשלילי קצר (cache שלילי) ומוצג בכל רגל."""
        if not self.health().ok:
            return
        needed = []
        for request in requests:
            pair = (_coord(request.origin), _coord(request.dest))
            if None in pair or pair[0] == pair[1] or self._cached(pair) is not None or self._cache.get(("err", *pair)) is not None:
                continue
            needed.append(pair)
        if not needed:
            return
        with self._lock:
            needed = [pair for pair in dict.fromkeys(needed) if self._cached(pair) is None]
            if not needed:
                return
            origins = list(dict.fromkeys(a for a, _ in needed))
            dests = list(dict.fromkeys(b for _, b in needed))
            per_batch = max(1, MAX_PAIRS // len(dests))
            for start in range(0, len(origins), per_batch):
                batch = origins[start:start + per_batch]
                try:
                    km, minutes = self._matrix(batch, dests)
                except _OrsError as problem:
                    for a in batch:
                        for b in dests:
                            self._cache.put(("err", a, b), (problem.status, problem.reason), ttl_seconds=30)
                    continue
                stamp = self._now()
                for i, a in enumerate(batch):
                    for j, b in enumerate(dests):
                        if km[i][j] is None or minutes[i][j] is None:
                            self._cache.put(("err", a, b), (LegStatus.NO_ROUTE, "לא נמצא מסלול בין הנקודות"), ttl_seconds=3600)
                        else:
                            self._cache.put(("leg", a, b), (km[i][j], minutes[i][j], stamp))

    def leg(self, request: LegRequest) -> LegResult:
        if not self._key:
            return LegResult(LegStatus.NOT_CONFIGURED, reason="ספק הכבישים לא מוגדר")
        a, b = _coord(request.origin), _coord(request.dest)
        if a is None or b is None:
            return LegResult(LegStatus.MISSING_INPUT, reason="חסרות קואורדינטות לנקודה")
        if a == b:
            return LegResult(LegStatus.OK, Decimal(0), Decimal(0), self._provenance(self._now()))
        if self._cached((a, b)) is None and self._cache.get(("err", a, b)) is None:
            self.prefetch([request])
        hit = self._cached((a, b))
        if hit is not None:
            km, minutes, stamp = hit
            return LegResult(LegStatus.OK, km, minutes, self._provenance(stamp))
        error = self._cache.get(("err", a, b))
        if error is not None:
            return LegResult(error[0][0], reason=error[0][1])
        health = self.health()
        return LegResult(LegStatus.UNAVAILABLE, reason=health.reason or "הניתוב לא זמין")

    def matrix(self, request: MatrixRequest) -> MatrixResult:
        if not self._key:
            return MatrixResult(LegStatus.NOT_CONFIGURED, reason="ספק הכבישים לא מוגדר")
        coords = [_coord(node) for node in request.nodes]
        if None in coords:
            return MatrixResult(LegStatus.MISSING_INPUT, reason="חסרות קואורדינטות לנקודה")
        if len(coords) ** 2 > MAX_PAIRS:
            return MatrixResult(LegStatus.UNAVAILABLE, reason="יותר מדי נקודות לחישוב")
        if not self.health().ok:
            return MatrixResult(LegStatus.UNAVAILABLE, reason=self.health().reason)
        with self._lock:
            try:
                km, minutes = self._matrix(coords, coords)
            except _OrsError as problem:
                return MatrixResult(problem.status, reason=problem.reason)
        if any(value is None for row in km + minutes for value in row):
            return MatrixResult(LegStatus.NO_ROUTE, reason="לא נמצא מסלול בין חלק מהנקודות")
        return MatrixResult(LegStatus.OK, tuple(tuple(r) for r in km), tuple(tuple(r) for r in minutes),
                            self._provenance(self._now()))

    # ── פנימי ────────────────────────────────────────────────────────────────────────────────
    def _cached(self, pair):
        found = self._cache.get(("leg", pair[0], pair[1]))
        return None if found is None else found[0]

    def _provenance(self, stamp: datetime) -> dict:
        return make_provenance(
            "openrouteservice", "free_flow", AccuracyClass.ROAD_FREE_FLOW_UNCALIBRATED, _NOTE,
            provider_host=self._base.split("//")[-1].split("/")[0], attribution=ATTRIBUTION,
            computed_at=stamp.isoformat(),
        )

    def _matrix(self, sources: list, destinations: list):
        """Matrix אחד: מחזיר (km, דקות) כרשימות של Decimal/None. זורק _OrsError על כל כשל."""
        locations = list(dict.fromkeys([*sources, *destinations]))
        index = {coord: i for i, coord in enumerate(locations)}
        body = {
            "locations": [[float(lng), float(lat)] for lat, lng in locations],    # ORS: [קו אורך, קו רוחב]
            "sources": [str(index[c]) for c in sources],
            "destinations": [str(index[c]) for c in destinations],
            "metrics": ["distance", "duration"],
            "units": "km",
        }
        data = self._post(f"/v2/matrix/{PROFILE}", body)
        distances, durations = data.get("distances"), data.get("durations")
        if not _is_grid(distances, len(sources), len(destinations)) or not _is_grid(durations, len(sources), len(destinations)):
            raise _OrsError(LegStatus.UNAVAILABLE, "תשובת הניתוב לא תקינה")
        km = [[None if v is None else Decimal(str(v)) for v in row] for row in distances]
        minutes = [[None if v is None else Decimal(str(v)) / 60 for v in row] for row in durations]    # ORS: שניות
        return km, minutes

    def _post(self, path: str, body: dict) -> dict:
        url = self._base + path
        headers = {"Authorization": self._key, "Content-Type": "application/json", "Accept": "application/json"}
        attempt_429 = attempt_5xx = 0
        while True:
            if self._limiter.daily_exhausted():
                raise _OrsError(LegStatus.BUDGET_EXCEEDED, "מכסת הניתוב היומית הרכה נגמרה")
            wait = self._limiter.wait_needed()
            if wait > self._max_wait:
                raise _OrsError(LegStatus.BUDGET_EXCEEDED, "הניתוב עמוס, נסה בעוד רגע")
            if wait > 0:
                self._sleep(wait)
            self._limiter.record()
            self.requests_used += 1
            try:
                response = self._transport(url, headers, body, self._timeout)
            except TransportError:
                self._register_failure()
                if attempt_5xx < 1:
                    attempt_5xx += 1
                    continue
                raise _OrsError(LegStatus.UNAVAILABLE, "הניתוב לא זמין (תקלת חיבור)") from None
            status = response.status
            if status == 200 and isinstance(response.body, dict):
                self._failures = 0
                return response.body
            if status == 429:
                if attempt_429 < self._max_429:
                    self._sleep(min(2 ** attempt_429, 5))
                    attempt_429 += 1
                    continue
                raise _OrsError(LegStatus.UNAVAILABLE, "הניתוב עמוס, נסה בעוד רגע")
            if status == 403:
                self._blocked_until = self._clock() + 3600
                raise _OrsError(LegStatus.BUDGET_EXCEEDED, "מכסת הניתוב היומית נגמרה או שהמפתח לא מורשה")
            if status == 401:
                self._blocked_until = self._clock() + 3600
                raise _OrsError(LegStatus.NOT_CONFIGURED, "מפתח הניתוב לא תקין")
            if status in (400, 404):
                raise _OrsError(LegStatus.NO_ROUTE, "לא ניתן לחשב מסלול (נקודה רחוקה מכביש או בקשה לא תקינה)")
            self._register_failure()
            if status >= 500 and attempt_5xx < 1:
                attempt_5xx += 1
                self._sleep(0.5)
                continue
            raise _OrsError(LegStatus.UNAVAILABLE, "הניתוב לא זמין כרגע")

    def _register_failure(self) -> None:
        self._failures += 1
        if self._failures >= 3:
            self._open_until = self._clock() + 60
            self._failures = 0
            logger.warning("[trips] routing provider circuit opened for 60s")


def _is_grid(value, rows: int, cols: int) -> bool:
    if not isinstance(value, list) or len(value) != rows:
        return False
    for row in value:
        if not isinstance(row, list) or len(row) != cols:
            return False
        if any(v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or v != v) for v in row):
            return False
    return True
