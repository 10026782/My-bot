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

# Hardcoded, not env-configurable — MEMORY_MAX_MESSAGES/MEMORY_TTL_HOURS env
# vars exist but only feed the unwired core/tenant_config.py, not this module.
MAX_MESSAGES     = 50
AVG_TOKENS       = 150
TOKEN_LIMIT      = 80_000
MEMORY_TTL_HOURS = 12  # שיחה פגה אחרי 12 שעות חוסר פעילות
MAX_CONTEXT_EVENTS = 10  # BUG-149: distinct action-state context channel, kept small — recent-outcome corrections, not a growing log


class MemoryStore:
    """NON-DURABLE, PROCESS-LOCAL. Everything here — ordinary conversation
    history AND the BUG-149 context-event channel below — lives only in this
    process's memory, with a 12h TTL. A restart or redeploy loses it all.
    This is fine for its actual purpose (shaping what the SAME process's
    NEXT same-session model call sees) but it must never be treated as a
    durable record of anything — ActionContract/ExecutionLedger/
    ActionContractRepository (core/action_gateway.py) remain the sole
    durable lifecycle source of truth, unaffected by whether anything here
    is ever written, delayed, or lost."""

    def __init__(self):
        self._store: dict = defaultdict(lambda: {
            "date":              None,
            "messages":          [],
            "last_active":       None,
            # BUG-149: distinct from "messages" above on purpose — see
            # add_context_event()/get_context_events_for_claude(). Never
            # merged into the ordinary user/assistant conversation history;
            # injected into the system prompt separately (app.py's
            # _build_action_resolution_context()).
            "context_events":    [],
            "context_event_ids": set(),
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

    def add_context_event(self, uid: str, event_id: str, text: str) -> bool:
        """BUG-149: a distinct, explicitly-typed action-state context
        channel — NOT part of the ordinary user/assistant conversation
        history get_for_claude() returns, and never injected into the
        messages[] array (see app.py's _build_action_resolution_context(),
        which reads get_context_events_for_claude() into the system prompt
        instead). This keeps memory_store's strict role-alternation
        invariant (get_for_claude()'s "first message must be user" guard)
        entirely untouched by this feature.

        Idempotent by event_id — a repeated call with the same event_id for
        the same uid is a no-op. Returns True if newly recorded, False if
        it was already present (e.g. a retried callback re-emitting the
        same terminal transition). uid = memory_key, same key space as
        add()/get_for_claude() — see core/action_resolution_event.py's
        ActionResolutionEvent.routing_key docstring for why this is proven
        to line up with identity.memory_key, not assumed.

        NON-DURABLE — see class docstring. A restart loses these events the
        same as ordinary history; that's an accepted, documented tradeoff
        (the deterministic MULTI_MUTATION_CONTEXT_MISMATCH guard in
        app.py's tool loop is what actually protects the system, not this
        best-effort context)."""
        with self._lock:
            s = self._store[uid]
            if event_id in s["context_event_ids"]:
                return False
            s["context_event_ids"].add(event_id)
            s["context_events"].append(text)
            if len(s["context_events"]) > MAX_CONTEXT_EVENTS:
                s["context_events"] = s["context_events"][-MAX_CONTEXT_EVENTS:]
            return True

    def get_context_events_for_claude(self, uid: str) -> list[str]:
        """Returns the pending action-state context blocks for this uid, for
        injection into the system prompt (not into messages[] — see
        add_context_event()). Does not clear them — they age out with the
        rest of this uid's memory via the same 12h TTL (see _read()/
        _write()'s TTL-reset blocks, which clear context_events/
        context_event_ids alongside messages)."""
        with self._lock:
            # Route through _read()'s TTL check so a stale conversation's
            # leftover context events don't attach to a brand-new one days
            # later — _read() already resets both on expiry.
            self._read(uid)
            return list(self._store[uid]["context_events"])

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

        if s["date"] is None:
            s["date"] = today

        # איפוס TTL — שיחה ישנה
        # הערה: אם _read כבר אפסה, last_active=None, _check_ttl_raw מחזיר True — בטוח
        if not self._check_ttl_raw(s, now):
            logger.info(f"⏰ TTL פג ({MEMORY_TTL_HOURS}ש') — מאפס זיכרון: {key}")
            s["messages"]          = []
            s["last_active"]       = None
            # BUG-149: a stale context-event note (e.g. "the CANONICAL task
            # was rejected") must not survive into what is, semantically, a
            # brand-new conversation once TTL has reset the rest of memory.
            s["context_events"]    = []
            s["context_event_ids"] = set()

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

        # ── תיקון באג #1 ────────────────────────────────
        # TTL פג: חייבים לאפס state לפני return [].
        # בלי האיפוס: _write תבדוק last_active הישן,
        # תזהה TTL פג שוב, ותמחק את ההודעה שהרגע נשמרה.
        # ──────────────────────────────────────────────────
        if not self._check_ttl_raw(s, now):
            logger.info(f"⏰ TTL פג — מאפס state ומחזיר היסטוריה ריקה: {key}")
            s["messages"]          = []
            s["last_active"]       = None   # ← קריטי: _write תראה חדש ולא תמחק
            s["context_events"]    = []     # BUG-149: same reset, see _write()'s matching block
            s["context_event_ids"] = set()
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
