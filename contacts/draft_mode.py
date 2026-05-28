# contacts/draft_mode.py
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
DRAFT_TTL = 30  # דקות

class DraftStore:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def save(self, chat_id, recipient_id, recipient_name, message, channel, address="") -> str:
        self._store[chat_id] = {
            "recipient_id": recipient_id, "recipient_name": recipient_name,
            "message": message, "channel": channel, "address": address,
            "expires_at": datetime.now() + timedelta(minutes=DRAFT_TTL),
        }
        emoji = {"email":"✉️","whatsapp":"📱","telegram":"💬"}.get(channel,"📨")
        return (
            f"📝 *טיוטה נשמרה*\n"
            f"נמען: {recipient_name} | ערוץ: {emoji} {channel}\n"
            f"הודעה: {message[:100]}{'...' if len(message)>100 else ''}\n\n"
            f"שלח 'שלח' לביצוע | 'בטל' לביטול"
        )

    def get(self, chat_id) -> dict | None:
        d = self._store.get(chat_id)
        if not d: return None
        if datetime.now() > d["expires_at"]:
            del self._store[chat_id]
            return None
        return d

    def clear(self, chat_id) -> bool:
        if chat_id in self._store:
            del self._store[chat_id]
            return True
        return False

    def has_draft(self, chat_id) -> bool:
        return self.get(chat_id) is not None

draft_store = DraftStore()
