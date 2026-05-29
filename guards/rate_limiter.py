# guards/rate_limiter.py
import time
import logging
from collections import defaultdict, deque
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimiter:
    """מגביל קצב — 20 בקשות לדקה לכל משתמש."""

    def __init__(self, max_per_minute: int = 20):
        self._windows: dict = defaultdict(deque)
        self._lock = Lock()
        self._max  = max_per_minute

    def is_allowed(self, key: str) -> bool:
        now    = time.time()
        cutoff = now - 60
        with self._lock:
            dq = self._windows[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self._max:
                return False
            dq.append(now)
            return True


def validate_tool_output(tool_name: str, raw) -> str:
    """מוודא שפלט כלי הוא string תקין ומוגבל באורך."""
    if not isinstance(raw, str):
        raw = str(raw)
    if len(raw) > 4000:
        raw = raw[:4000] + "\n...[נחתך]"
    return raw


# singleton — backward compat עם app.py
rate_limiter = RateLimiter()
