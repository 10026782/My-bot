# event_bus.py
# מנתב אירועים מרכזי — Event Bus + Pending Actions Store
# כל פעולה שדורשת אישור עוברת דרך כאן לפני ביצוע

import uuid
import logging
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
        """שולף ומוחק — לאחר אישור או ביטול. בודק TTL באופן עצמאי."""
        item = self._store.get(action_id)
        if not item:
            return None
        if datetime.now() > datetime.fromisoformat(item["expires"]):
            del self._store[action_id]
            logger.info(f"⏰ Pending action expired at pop: {action_id}")
            return None
        del self._store[action_id]
        return item

    def cancel(self, action_id: str) -> bool:
        """מבטל פעולה ממתינה"""
        if action_id in self._store:
            del self._store[action_id]
            logger.info(f"🚫 Pending action cancelled: {action_id}")
            return True
        return False

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

# פעולות שדורשות אישור לפני ביצוע
# שמות חייבים להתאים בדיוק לשמות בtool_registry.py ובdispatcher.py
ACTIONS_REQUIRING_APPROVAL = {
    "calendar_create_event",  # קביעת אירוע — ייצור בלתי הפיך
    "sheets_append",          # כתיבה לשיט — ייצור בלתי הפיך
    "airtable_delete",        # מחיקה — בלתי הפיכה
    "gmail_send_draft",       # שליחת מייל — בלתי הפיכה
}

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

    def needs_approval(self, action: str) -> bool:
        """האם הפעולה דורשת אישור?"""
        return action in ACTIONS_REQUIRING_APPROVAL


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
# Singletons
# ══════════════════════════════════════════════════

pending = PendingActionsStore()
bus     = EventBus(pending)
