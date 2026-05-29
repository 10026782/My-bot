# guards/idempotency.py
# מונע עיבוד כפול של אותה הודעה (Telegram retries, WhatsApp duplicates)

import hashlib
import time
import logging
from threading import Lock

logger = logging.getLogger(__name__)

TTL_SECONDS = 300  # 5 דקות — מספיק לכיסוי retries של Telegram/WhatsApp


class IdempotencyStore:
    def __init__(self):
        self._seen: dict[str, float] = {}
        self._lock = Lock()

    def is_duplicate(self, channel: str, sender: str, content: str) -> bool:
        key = self._hash(channel, sender, content)
        with self._lock:
            self._cleanup()
            if key in self._seen:
                logger.info(f"🔁 Duplicate blocked: {channel}/{sender[:8]}")
                return True
            self._seen[key] = time.time()
            return False

    def _hash(self, channel: str, sender: str, content: str) -> str:
        raw = f"{channel}:{sender}:{content}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _cleanup(self):
        now = time.time()
        expired = [k for k, t in self._seen.items() if now - t > TTL_SECONDS]
        for k in expired:
            del self._seen[k]


# singleton — backward compat עם app.py
idempotency = IdempotencyStore()
