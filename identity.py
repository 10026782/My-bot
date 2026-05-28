import os
from enum import Enum
from dataclasses import dataclass, field


class Role(Enum):
    OWNER = "owner"
    STAFF = "staff"
    CLIENT = "client"


@dataclass
class Identity:
    sender: str
    channel: str
    role: Role
    tenant_id: str = "boss_hq"

    @property
    def is_internal(self) -> bool:
        return self.role in (Role.OWNER, Role.STAFF)


def resolve_identity(channel: str, sender: str) -> Identity:
    """
    מזהה תפקיד לפי ערוץ (whatsapp/telegram) ומזהה שולח.
    WhatsApp: sender = "whatsapp:+972XXXXXXXXX" או "+972XXXXXXXXX"
    Telegram: sender = chat_id (מספר שלם כמחרוזת)

    env variables נדרשים:
      OWNER_PHONES         — מספרי WhatsApp של הבעלים (מופרדים בפסיקים)
      STAFF_PHONES         — מספרי WhatsApp של הצוות
      OWNER_TELEGRAM_IDS   — chat_id של הבעלים בטלגרם
      STAFF_TELEGRAM_IDS   — chat_id של הצוות בטלגרם
    """
    normalized = _normalize(channel, sender)

    if channel == "whatsapp":
        owners = _load_set("OWNER_PHONES")
        staff = _load_set("STAFF_PHONES")
    else:
        owners = _load_set("OWNER_TELEGRAM_IDS")
        staff = _load_set("STAFF_TELEGRAM_IDS")

    if normalized in owners:
        role = Role.OWNER
    elif normalized in staff:
        role = Role.STAFF
    else:
        role = Role.CLIENT

    return Identity(sender=normalized, channel=channel, role=role)


def _normalize(channel: str, sender: str) -> str:
    if channel == "whatsapp":
        return sender.replace("whatsapp:", "").strip()
    return str(sender).strip()


def _load_set(env_key: str) -> set[str]:
    raw = os.environ.get(env_key, "")
    return {v.strip() for v in raw.split(",") if v.strip()}
