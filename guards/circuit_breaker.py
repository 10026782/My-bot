# guards/circuit_breaker.py
# Circuit breaker stubs — מוכן להרחבה עתידית
import time
import logging
from contextlib import contextmanager
from threading import Lock

logger = logging.getLogger(__name__)

_FAILURE_THRESHOLD = 5
_RECOVERY_TIMEOUT  = 60  # שניות


class _CircuitBreaker:
    """Circuit breaker פשוט: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def __init__(self, name: str):
        self._name     = name
        self._failures = 0
        self._opened   = 0.0  # timestamp שנפתח
        self._lock     = Lock()

    @contextmanager
    def __call__(self):
        with self._lock:
            now = time.time()
            if self._failures >= _FAILURE_THRESHOLD:
                if now - self._opened < _RECOVERY_TIMEOUT:
                    logger.warning(f"Circuit OPEN for {self._name} — skipping call")
                    raise RuntimeError(f"שירות {self._name} לא זמין כרגע (circuit open)")
                # HALF_OPEN: מנסים שוב
                self._failures = 0
        try:
            yield
            with self._lock:
                self._failures = 0  # הצלחה — אפס מונה
        except Exception:
            with self._lock:
                self._failures += 1
                if self._failures >= _FAILURE_THRESHOLD:
                    self._opened = time.time()
                    logger.error(f"Circuit OPENED for {self._name} after {self._failures} failures")
            raise


_google_breaker   = _CircuitBreaker("Google API")
_airtable_breaker = _CircuitBreaker("Airtable API")


def with_google_breaker():
    return _google_breaker()

def with_airtable_breaker():
    return _airtable_breaker()
