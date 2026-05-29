# guards/idempotency.py
import time
import hashlib
import logging
from threading import Lock

logger = logging.getLogger(__name__)


class IdempotencyStore:
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


# singleton — backward compat עם app.py
idempotency = IdempotencyStore()
