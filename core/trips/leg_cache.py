"""cache בזיכרון לרגלי ניתוב, כדי שלא לשלוח בקשה חוזרת כשמשנים רק מחיר, הסתברות או זמני המתנה.

המפתח הוא זוג קואורדינטות מעוגלות בלבד: לא כולל תשלום, הסתברות, רכב או סדר הצעות.
TTL קצר ובזיכרון בלבד (בלי שמירה מתמשכת) עד שסעיף ה-caching בתנאי השימוש של הספק יאומת.
אין רישום קואורדינטות ללוג.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

DEFAULT_TTL_SECONDS = 24 * 3600
MAX_ENTRIES = 5000


class LegCache:
    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._items: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        """(value, stored_at) או None אם חסר/פג תוקף."""
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            value, stored_at, ttl = entry
            if self._clock() - stored_at > ttl:
                del self._items[key]
                return None
            return value, stored_at

    def put(self, key, value, ttl_seconds: float | None = None) -> None:
        with self._lock:
            if len(self._items) >= MAX_ENTRIES:
                self._items.clear()      # מגבלת זיכרון פשוטה; הנתונים ניתנים לשחזור בבקשה חדשה
            self._items[key] = (value, self._clock(), self._ttl if ttl_seconds is None else ttl_seconds)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
