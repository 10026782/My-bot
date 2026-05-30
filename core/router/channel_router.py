# core/router/channel_router.py — CORE_02_ROUTER
# זיהוי ערוץ התקשורת והתאמת פעולות לערוץ.

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Channel Catalog
# ══════════════════════════════════════════════════

class Channel:
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    EMAIL    = "email"
    PHONE    = "phone"
    WEB      = "web"
    API      = "api"
    UNKNOWN  = "unknown"

    # ערוצים פנימיים — מורשים לפעולות רגישות יותר
    INTERNAL = {TELEGRAM, API}
    # ערוצים חיצוניים — leads/guests מגיעים מכאן
    EXTERNAL = {WHATSAPP, WEB, EMAIL, PHONE}


# ══════════════════════════════════════════════════
# Tool Override Map
# intent → {channel: tool_name}
# ══════════════════════════════════════════════════

CHANNEL_TOOL_OVERRIDE: dict[str, dict[str, str]] = {
    "send_message": {
        Channel.WHATSAPP: "whatsapp_send",
        Channel.TELEGRAM: "telegram_send",
        Channel.EMAIL:    "gmail_send_draft",
    },
    "draft_message": {
        Channel.WHATSAPP: "whatsapp_draft",
        Channel.TELEGRAM: "telegram_draft",
        Channel.EMAIL:    "gmail_draft",
    },
    "send_email": {
        Channel.WHATSAPP: "gmail_send_draft",   # מוואטסאפ → תמיד draft קודם
        Channel.TELEGRAM: "gmail_send_draft",
        Channel.EMAIL:    "gmail_send_draft",
    },
}

# ערוצים שדורשים risk גבוה יותר לפעולות שליחה
HIGH_RISK_CHANNELS_FOR_SEND = {Channel.EMAIL, Channel.WHATSAPP}


# ══════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════

def detect_channel(channel_raw: str) -> str:
    """מנרמל את שם הערוץ."""
    normalized = channel_raw.lower().strip()

    mapping = {
        "whatsapp":    Channel.WHATSAPP,
        "telegram":    Channel.TELEGRAM,
        "email":       Channel.EMAIL,
        "gmail":       Channel.EMAIL,
        "phone":       Channel.PHONE,
        "web":         Channel.WEB,
        "api":         Channel.API,
    }

    result = mapping.get(normalized, Channel.UNKNOWN)
    if result == Channel.UNKNOWN:
        logger.warning(f"[Channel] Unknown channel: {channel_raw!r}")
    return result


def resolve_tool_for_channel(intent: str, channel: str) -> str:
    """
    מחזיר את שם הכלי המתאים לintent + channel.
    אם אין override → מחזיר "" (dispatcher ישתמש בברירת מחדל).
    """
    override = CHANNEL_TOOL_OVERRIDE.get(intent, {})
    tool = override.get(channel, "")
    if tool:
        logger.debug(f"[Channel] Override: intent={intent} channel={channel} → tool={tool}")
    return tool


def is_external_channel(channel: str) -> bool:
    return channel in Channel.EXTERNAL
