"""
config.py — Channel → Domain Mapping
מיפוי מספרי WhatsApp לדומיינים עסקיים.
להוסיף מספרים כאן בלבד — שאר הקוד לא נוגעים.
"""

import logging
import os

logger = logging.getLogger(__name__)

# ─── Channel → Domain Mapping ────────────────────────────────────────────────
# מפתח: "whatsapp:+972XXXXXXXXX" (המספר שהבוט מקבל הודעות אליו)
# ערך:   שם הדומיין (real_estate | furniture_import | import | media | saas | finance | general)

CHANNEL_DOMAINS: dict[str, str] = {
    # דוגמה — להחליף במספרים האמיתיים:
    # "whatsapp:+972501234567": "real_estate",
    # "whatsapp:+972507654321": "import",
}

# ─── Inbound source → canonical Owner mapping ───────────────────────────────
# Values are canonical identity user_ids, never Airtable Profile record IDs.
# Missing entries are intentional: the resolver fails closed.
OWNER_USER_ID_MAPPINGS: dict[str, dict[str, str]] = {
    "whatsapp_destination": {},
    "email_recipient": {},
    "voice_destination": {},
}

# דומיין ברירת מחדל כשאין מיפוי מוגדר
DEFAULT_DOMAIN = "general"


# ─── Helper ──────────────────────────────────────────────────────────────────

def get_domain(to_number: str) -> str:
    """
    מחזיר את הדומיין לפי מספר היעד של WhatsApp.
    to_number: "whatsapp:+972XXXXXXXXX"
    """
    furniture_number = os.environ.get("FURNITURE_TWILIO_WHATSAPP_NUMBER", "").strip()
    if furniture_number and to_number == f"whatsapp:{furniture_number.removeprefix('whatsapp:')}":
        return "furniture_import"

    domain = CHANNEL_DOMAINS.get(to_number, DEFAULT_DOMAIN)
    if domain != DEFAULT_DOMAIN:
        logger.debug(f"[Config] Domain mapped: {to_number} → {domain}")
    else:
        logger.debug(f"[Config] No domain mapping for {to_number!r} — using {DEFAULT_DOMAIN}")
    return domain
