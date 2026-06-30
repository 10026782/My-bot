# event_bus.py
# מנתב אירועים מרכזי — Event Bus + Pending Actions Store
# כל פעולה שדורשת אישור עוברת דרך כאן לפני ביצוע
#
# C52: handlers הרשומים ל-"{action}.confirmed" (למשל send_followup.confirmed
# ב-app.py) ששולחים ללקוח חייבים לעבור core.output_gateway.send_outbound() —
# לא לקרוא ל-Send Adapter ישירות. event_bus עצמו לא שולח דבר — הוא רק מנתב.

import uuid
import time
import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Callable, Any

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# Pending Actions Store
# שמירת פעולות שממתינות לאישור המשתמש
# ══════════════════════════════════════════════════

PENDING_TTL_MINUTES = 30  # פעולה ממתינה פגה אחרי 30 דקות

class PendingActionsStore:
    """
    מאחסן פעולות שממתינות לאישור.
    מבנה: { action_id: { "action": ..., "payload": ..., "chat_id": ..., "expires": ... } }
    """
    def __init__(self):
        self._store: dict[str, dict] = {}
        # LL-13: guards get-then-delete sequences below — without this,
        # two near-simultaneous confirm() calls for the same action_id can
        # both observe a live entry before either removes it, causing the
        # underlying action to execute twice.
        self._lock = threading.Lock()

    def add(self, chat_id: str, action: str, payload: dict, label: str = "") -> str:
        """
        רושם פעולה ממתינה.
        מחזיר action_id ייחודי לשימוש בכפתור האישור.
        """
        action_id = str(uuid.uuid4())[:8]  # קצר יותר לכפתורי טלגרם
        self._store[action_id] = {
            "action":   action,
            "payload":  payload,
            "chat_id":  chat_id,
            "label":    label or action,
            "created":  datetime.now().isoformat(),
            "expires":  (datetime.now() + timedelta(minutes=PENDING_TTL_MINUTES)).isoformat(),
        }
        logger.info(f"📥 Pending action registered: {action_id} | {action} | chat={chat_id}")
        return action_id

    def get(self, action_id: str) -> dict | None:
        """שולף פעולה ממתינה — בודק תפוגה"""
        item = self._store.get(action_id)
        if not item:
            return None
        if datetime.now() > datetime.fromisoformat(item["expires"]):
            del self._store[action_id]
            logger.info(f"⏰ Pending action expired: {action_id}")
            return None
        return item

    def pop(self, action_id: str) -> dict | None:
        """שולף ומוחק — לאחר אישור או ביטול. בודק TTL באופן עצמאי.
        LL-13: get+delete is a single atomic critical section — a concurrent
        pop() for the same action_id will see nothing left to take."""
        with self._lock:
            item = self._store.pop(action_id, None)
        if not item:
            return None
        if datetime.now() > datetime.fromisoformat(item["expires"]):
            logger.info(f"⏰ Pending action expired at pop: {action_id}")
            return None
        return item

    def cancel(self, action_id: str) -> bool:
        """מבטל פעולה ממתינה"""
        with self._lock:
            existed = self._store.pop(action_id, None) is not None
        if existed:
            logger.info(f"🚫 Pending action cancelled: {action_id}")
        return existed

    def list_for_chat(self, chat_id: str) -> list[dict]:
        """מחזיר כל הפעולות הממתינות לצ'אט מסוים"""
        now = datetime.now()
        result = []
        expired = []
        for aid, item in self._store.items():
            if now > datetime.fromisoformat(item["expires"]):
                expired.append(aid)
                continue
            if item["chat_id"] == chat_id:
                result.append({"id": aid, **item})
        for aid in expired:
            del self._store[aid]
        return result

    # ── BUG-V1-CROSS-CHANNEL-FINGERPRINT-SPLIT (Stage A) — additive methods ──
    # לא נוגעים ב-pop/emit/confirm הקיימים. רק מוסיפים חיפוש קנוני.

    @staticmethod
    def _normalize_inputs(tool_inputs: dict) -> tuple:
        return tuple(sorted((str(k), str(v)) for k, v in (tool_inputs or {}).items()))

    def find_pending_by_business_fingerprint(
        self, canonical_user_id: str, tool_name: str, normalized_inputs: dict
    ) -> dict | None:
        """
        מחפש pending action חי לפי זהות קנונית + tool_name + normalized_inputs.
        מפתח dedup: canonical_user_id (identity.memory_key) + tool_name + inputs.
        לא chat_id גולמי — שני ערוצים לאותו אדם מקבלים fingerprint זהה.
        """
        norm = self._normalize_inputs(normalized_inputs)
        expired = []
        for aid, item in self._store.items():
            if datetime.now() > datetime.fromisoformat(item["expires"]):
                expired.append(aid)
                continue
            payload = item.get("payload", {})
            if (
                payload.get("canonical_user_id") == canonical_user_id
                and payload.get("tool_name") == tool_name
                and self._normalize_inputs(payload.get("tool_inputs", {})) == norm
            ):
                for eid in expired:
                    self._store.pop(eid, None)
                return {"action_id": aid, "origin_channel": payload.get("origin_channel", ""), **item}
        for eid in expired:
            self._store.pop(eid, None)
        return None

    def find_pending_tool_approval(self, canonical_user_id: str) -> dict | None:
        """מחפש pending tool approval חי לזהות קנונית — לבדיקת "מאשר" חופשי."""
        for aid, item in self._store.items():
            if datetime.now() > datetime.fromisoformat(item["expires"]):
                continue
            payload = item.get("payload", {})
            if payload.get("canonical_user_id") == canonical_user_id and payload.get("tool_name"):
                return {"action_id": aid, "label": item.get("label", payload.get("tool_name", "")), **item}
        return None

    def has_pending_for(self, canonical_user_id: str) -> bool:
        return self.find_pending_tool_approval(canonical_user_id) is not None

    def mark_equivalent_pending_completed(
        self, canonical_user_id: str, tool_name: str, tool_inputs: dict
    ) -> None:
        """מוחק כל pending action עם אותה fingerprint קנונית — למנוע re-queue מ-channel שני."""
        norm = self._normalize_inputs(tool_inputs)
        to_remove = [
            aid for aid, item in self._store.items()
            if item.get("payload", {}).get("canonical_user_id") == canonical_user_id
            and item.get("payload", {}).get("tool_name") == tool_name
            and self._normalize_inputs(item.get("payload", {}).get("tool_inputs", {})) == norm
        ]
        for aid in to_remove:
            with self._lock:
                self._store.pop(aid, None)
            logger.info(f"[Approval] mark_equivalent_completed: removed {aid} for {canonical_user_id}")

    def cleanup(self):
        """מנקה פעולות פגות — קרא מהשדלר"""
        now = datetime.now()
        expired = [
            aid for aid, item in self._store.items()
            if now > datetime.fromisoformat(item["expires"])
        ]
        for aid in expired:
            del self._store[aid]
        if expired:
            logger.info(f"🧹 Cleaned {len(expired)} expired pending actions")


# ══════════════════════════════════════════════════
# Event Bus
# מנתב אירועים — subscribe / emit
# ══════════════════════════════════════════════════

# C53 FIX-3: מקור אחד ב-tool_registry — אין רשימה מקומית.
from tool_registry import TOOLS_REQUIRING_APPROVAL
ACTIONS_REQUIRING_APPROVAL = TOOLS_REQUIRING_APPROVAL

class EventBus:
    """
    מנתב אירועים מרכזי.

    שימוש:
        bus.subscribe("email.confirmed", my_handler)
        bus.emit("email.confirmed", payload, chat_id)

    פעולות שדורשות אישור:
        bus.request_approval("send_email", payload, chat_id)
        → מחזיר (action_id, label) לשימוש ב-Inline Keyboard

        bus.confirm(action_id)   → מפעיל את הפעולה
        bus.reject(action_id)    → מבטל
    """

    def __init__(self, pending_store: PendingActionsStore):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._pending  = pending_store

    # ── Subscribe ──────────────────────────────────

    def subscribe(self, event: str, handler: Callable):
        """רישום handler לאירוע"""
        self._handlers[event].append(handler)
        logger.info(f"🔌 Subscribed: {event} → {handler.__name__}")

    # ── Emit ───────────────────────────────────────

    def emit(self, event: str, payload: dict = None, chat_id: str = "") -> Any:
        """
        שולח אירוע לכל ה-handlers הרשומים.
        מחזיר את תוצאת ה-handler הראשון (לנוחות).
        """
        handlers = self._handlers.get(event, [])
        if not handlers:
            logger.warning(f"⚠️ No handler for event: {event}")
            return None

        results = []
        for handler in handlers:
            try:
                result = handler(payload or {}, chat_id)
                results.append(result)
            except Exception as e:
                logger.error(f"❌ Handler error [{event}]: {e}")
                results.append(f"❌ שגיאה בטיפול באירוע {event}: {e}")

        return results[0] if results else None

    # ── Approval Flow ──────────────────────────────

    def request_approval(self, action: str, payload: dict, chat_id: str,
                         label: str = "") -> tuple[str, str]:
        """
        רושם פעולה שדורשת אישור.
        מחזיר (action_id, label_for_button).
        """
        if not label:
            label = _default_label(action, payload)
        action_id = self._pending.add(chat_id, action, payload, label)
        return action_id, label

    def confirm(self, action_id: str) -> str:
        """
        אישור פעולה ממתינה — מפעיל emit.
        מחזיר תוצאת הביצוע.
        """
        item = self._pending.pop(action_id)
        if not item:
            return "⚠️ הפעולה פגה או לא נמצאה."
        action  = item["action"]
        payload = item["payload"]
        chat_id = item["chat_id"]
        result = self.emit(f"{action}.confirmed", payload, chat_id)
        if result is None:
            logger.error(
                f"[EventBus] confirm: no handler for '{action}.confirmed' — "
                f"action NOT executed (action_id={action_id})"
            )
            return f"⚠️ אין handler לפעולה זו — הפעולה לא בוצעה."
        logger.info(f"✅ Confirmed and executed: {action_id} | {action}")
        return result

    def reject(self, action_id: str) -> str:
        """ביטול פעולה ממתינה"""
        item = self._pending.pop(action_id)
        if not item:
            return "⚠️ הפעולה כבר לא קיימת."
        label = item.get("label", item["action"])
        logger.info(f"🚫 Rejected: {action_id} | {label}")
        return f"🚫 הפעולה בוטלה: {label}"

    def pop(self, action_id: str) -> dict | None:
        """שולף ומוחק פעולה ממתינה — ממשק ציבורי ל-PendingActionsStore.pop."""
        return self._pending.pop(action_id)

    def needs_approval(self, action: str) -> bool:
        """האם הפעולה דורשת אישור?"""
        return action in ACTIONS_REQUIRING_APPROVAL

    # ── BUG-V1-CROSS-CHANNEL-FINGERPRINT-SPLIT (Stage A) — delegates ──

    def find_pending_by_business_fingerprint(
        self, canonical_user_id: str, tool_name: str, normalized_inputs: dict
    ) -> dict | None:
        return self._pending.find_pending_by_business_fingerprint(
            canonical_user_id, tool_name, normalized_inputs
        )

    def find_pending_tool_approval(self, canonical_user_id: str) -> dict | None:
        return self._pending.find_pending_tool_approval(canonical_user_id)

    def has_pending_for(self, canonical_user_id: str) -> bool:
        return self._pending.has_pending_for(canonical_user_id)

    def mark_equivalent_pending_completed(
        self, canonical_user_id: str, tool_name: str, tool_inputs: dict
    ) -> None:
        self._pending.mark_equivalent_pending_completed(canonical_user_id, tool_name, tool_inputs)


# ── Helper ─────────────────────────────────────────

def _default_label(action: str, payload: dict) -> str:
    """תווית ברירת מחדל לכפתורי אישור"""
    labels = {
        "gmail_send_draft":       f"📧 שלח מייל ל-{payload.get('to', '?')}",
        "calendar_create_event":  f"📅 קבע: {payload.get('summary', '?')}",
        "airtable_add":           f"➕ הוסף ל-{payload.get('table', '?')}",
        "airtable_update":        f"✏️ עדכן ב-{payload.get('table', '?')}",
        "airtable_delete":        f"🗑️ מחק מ-{payload.get('table', '?')}",
        "sheets_append":          f"📊 כתוב ל-{payload.get('sheet_name', '?')}",
    }
    return labels.get(action, f"⚡ {action}")


# ══════════════════════════════════════════════════
# Executed-Action Fingerprint Cache
# BUG-V1-APPROVAL-REQUEUE-AFTER-CONFIRM
#
# Blocks re-queuing an identical write action within a TTL window.
# Fingerprint = sha1(chat_id | tool_name | sorted_inputs)[:16].
# Checked BEFORE queuing; recorded AFTER successful execution.
# ══════════════════════════════════════════════════

_EXECUTED_FINGERPRINT_TTL = 600  # 10 minutes — same as approval button TTL


class ExecutedActionCache:
    """TTL-keyed set of write-action fingerprints."""

    def __init__(self):
        self._cache: dict[str, float] = {}
        self._lock  = threading.Lock()

    @staticmethod
    def compute(chat_id: str, tool_name: str, inputs: dict) -> str:
        normalized = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
        raw = f"{chat_id}|{tool_name}|{normalized}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def is_recently_executed(self, fingerprint: str) -> bool:
        now = time.time()
        with self._lock:
            self._cache = {k: v for k, v in self._cache.items() if v > now}
            return fingerprint in self._cache

    def mark_executed(self, fingerprint: str) -> None:
        with self._lock:
            self._cache[fingerprint] = time.time() + _EXECUTED_FINGERPRINT_TTL


# ══════════════════════════════════════════════════
# Singletons
# ══════════════════════════════════════════════════

pending                = PendingActionsStore()
bus                    = EventBus(pending)
executed_action_cache  = ExecutedActionCache()
