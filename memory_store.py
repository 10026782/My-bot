# memory_store.py — v2.2 Multi-Tenant + TTL (באגים מתוקנים)
# תיקונים:
# • באג #1: _read מאפסת state לפני return [] כשTTL פג
#   (בלי זה, _write ימחק את ההודעה הנוכחית מיד אחרי שנשמרה)
# • backward compatible לחלוטין

from datetime import datetime, date, timedelta
from collections import defaultdict
from threading import Lock
import logging

logger = logging.getLogger(__name__)

MAX_MESSAGES     = 50
AVG_TOKENS       = 150
TOKEN_LIMIT      = 80_000
MEMORY_TTL_HOURS = 4   # שיחה פגה אחרי 4 שעות חוסר פעילות


class MemoryStore:
    def __init__(self):
        self._store: dict = defaultdict(lambda: {
            "date":        None,
            "messages":    [],
            "last_active": None,
        })
        self._lock = Lock()

    # ══════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════

    def add(self, uid: str, role: str, content: str, channel: str = "telegram"):
        """שמירת הודעה. uid = memory_key (tenant:user)."""
        with self._lock:
            self._write(uid, role, content, channel)

    def get_for_claude(self, uid: str) -> list[dict]:
        """מחזיר היסטוריה נקייה ל-Claude API. uid = memory_key."""
        with self._lock:
            return self._read(uid)

    def clear(self, uid: str):
        with self._lock:
            if uid in self._store:
                del self._store[uid]
                logger.info(f"🗑️ זיכרון נמחק: {uid}")

    def is_fresh(self, uid: str) -> bool:
        """האם השיחה עדיין בתוך חלון הTTL?"""
        with self._lock:
            return self._check_ttl_raw(self._store[uid], datetime.now())

    # ══════════════════════════════════════════════
    # Internal
    # ══════════════════════════════════════════════

    def _write(self, key: str, role: str, content: str, channel: str):
        now   = datetime.now()
        today = date.today()
        s     = self._store[key]

        # איפוס ביום חדש
        if s["date"] != today:
            if s["date"] is not None:
                logger.info(f"🔄 יום חדש — מאפס זיכרון: {key}")
            s["date"]        = today
            s["messages"]    = []
            s["last_active"] = None

        # איפוס TTL — שיחה ישנה
        # הערה: אם _read כבר אפסה, last_active=None, _check_ttl_raw מחזיר True — בטוח
        if not self._check_ttl_raw(s, now):
            logger.info(f"⏰ TTL פג ({MEMORY_TTL_HOURS}ש') — מאפס זיכרון: {key}")
            s["messages"]    = []
            s["last_active"] = None

        s["messages"].append({
            "role":     role,
            "content":  content,
            "_channel": channel,
            "_ts":      now.isoformat(),
        })
        s["last_active"] = now

        # Trim
        if len(s["messages"]) > MAX_MESSAGES:
            s["messages"] = s["messages"][-MAX_MESSAGES:]

    def _read(self, key: str) -> list[dict]:
        now = datetime.now()
        s   = self._store[key]

        # יום שעבר — היסטוריה ריקה
        if s["date"] != date.today():
            return []

        # ── תיקון באג #1 ────────────────────────────────
        # TTL פג: חייבים לאפס state לפני return [].
        # בלי האיפוס: _write תבדוק last_active הישן,
        # תזהה TTL פג שוב, ותמחק את ההודעה שהרגע נשמרה.
        # ──────────────────────────────────────────────────
        if not self._check_ttl_raw(s, now):
            logger.info(f"⏰ TTL פג — מאפס state ומחזיר היסטוריה ריקה: {key}")
            s["messages"]    = []
            s["last_active"] = None   # ← קריטי: _write תראה חדש ולא תמחק
            return []

        msgs = s["messages"]

        # Token overflow guard
        if len(msgs) * AVG_TOKENS > TOKEN_LIMIT:
            safe = TOKEN_LIMIT // AVG_TOKENS
            msgs = msgs[-safe:]
            logger.warning(f"⚠️ Token overflow — נחתך ל-{safe} הודעות ({key})")

        clean = [{"role": m["role"], "content": m["content"]} for m in msgs]

        # חובה: הודעה ראשונה = user (Anthropic 400 guard)
        while clean and clean[0]["role"] != "user":
            clean.pop(0)

        return clean

    @staticmethod
    def _check_ttl_raw(s: dict, now: datetime) -> bool:
        """
        True  = שיחה בחיים (בתוך TTL)
        False = TTL פג (עברו יותר מ-MEMORY_TTL_HOURS)
        None last_active = שיחה חדשה / לאחר איפוס → True (בטוח)
        """
        last = s.get("last_active")
        if last is None:
            return True
        return (now - last) < timedelta(hours=MEMORY_TTL_HOURS)


# Singleton
memory = MemoryStore()
