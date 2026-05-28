# guards.py — Rate Limiting, Idempotency, Output Validation

import time
import hashlib
import logging
from collections import defaultdict, deque
from threading import Lock

logger = logging.getLogger(__name__)


class _IdempotencyStore:
    """מונע עיבוד כפול של אותה הודעה (30 שניות TTL)."""

    def __init__(self, ttl: int = 30, maxsize: int = 5000):
        self._seen: dict = {}
        self._lock = Lock()
        self._ttl  = ttl
        self._max  = maxsize

    def is_duplicate(self, channel: str, sender: str, content: str) -> bool:
        key = hashlib.md5(f"{channel}:{sender}:{content}".encode()).hexdigest()
        now = time.time()
        with self._lock:
            if len(self._seen) > self._max:
                cutoff = now - self._ttl
                self._seen = {k: v for k, v in self._seen.items() if v > cutoff}
            if key in self._seen and (now - self._seen[key]) < self._ttl:
                logger.info(f"Duplicate message dropped: {channel}/{sender}")
                return True
            self._seen[key] = now
            return False


class _RateLimiter:
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


idempotency  = _IdempotencyStore()
rate_limiter = _RateLimiter()
