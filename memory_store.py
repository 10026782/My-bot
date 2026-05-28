# memory_store.py — v2.2 Multi-Tenant + TTL (באגים מתוקנים)
# תיקונים:
# • באג #1: _read מאפסת state לפני return [] כשTTL פג
# • backward compatible לחלוטין

from datetime import datetime, date, timedelta
from collections import defaultdict
from threading import Lock
import logging

logger = logging.getLogger(__name__)

MAX_MESSAGES     = 50
AVG_TOKENS       = 150
TOKEN_LIMIT      = 80_000
MEMORY_TTL_HOURS = 4


class MemoryStore:
    def __init__(self):
        self._store: dict = defaultdict(lambda: {
            "date":        None,
            "messages":    [],
            "last_active": None,
        })
        self._lock = Lock()

    def add(self, uid: str, role: str, content: str, channel: str = "telegram"):
        with self._lock:
            self._write(uid, role, content, channel)

    def get_for_claude(self, uid: str) -> list[dict]:
        with self._lock:
            return self._read(uid)

    def clear(self, uid: str):
        with self._lock:
            if uid in self._store:
                del self._store[uid]

    def is_fresh(self, uid: str) -> bool:
        with self._lock:
            return self._check_ttl_raw(self._store[uid], datetime.now())

    def _write(self, key: str, role: str, content: str, channel: str):
        now   = datetime.now()
        today = date.today()
        s     = self._store[key]

        if s["date"] != today:
            s["date"]        = today
            s["messages"]    = []
            s["last_active"] = None

        if not self._check_ttl_raw(s, now):
            logger.info(f"TTL פג — מאפס זיכרון: {key}")
            s["messages"]    = []
            s["last_active"] = None

        s["messages"].append({
            "role":     role,
            "content":  content,
            "_channel": channel,
            "_ts":      now.isoformat(),
        })
        s["last_active"] = now

        if len(s["messages"]) > MAX_MESSAGES:
            s["messages"] = s["messages"][-MAX_MESSAGES:]

    def _read(self, key: str) -> list[dict]:
        now = datetime.now()
        s   = self._store[key]

        if s["date"] != date.today():
            return []

        if not self._check_ttl_raw(s, now):
            logger.info(f"TTL פג — מאפס state: {key}")
            s["messages"]    = []
            s["last_active"] = None
            return []

        msgs = s["messages"]

        if len(msgs) * AVG_TOKENS > TOKEN_LIMIT:
            safe = TOKEN_LIMIT // AVG_TOKENS
            msgs = msgs[-safe:]

        clean = [{"role": m["role"], "content": m["content"]} for m in msgs]

        while clean and clean[0]["role"] != "user":
            clean.pop(0)

        return clean

    @staticmethod
    def _check_ttl_raw(s: dict, now: datetime) -> bool:
        last = s.get("last_active")
        if last is None:
            return True
        return (now - last) < timedelta(hours=MEMORY_TTL_HOURS)


memory = MemoryStore()
