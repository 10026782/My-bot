"""
config.py — Channel → Domain Mapping
מיפוי מספרי WhatsApp לדומיינים עסקיים.
להוסיף מספרים כאן בלבד — שאר הקוד לא נוגעים.
"""

import logging

logger = logging.getLogger(__name__)

# ─── Channel → Domain Mapping ────────────────────────────────────────────────
# מפתח: "whatsapp:+972XXXXXXXXX" (המספר שהבוט מקבל הודעות אליו)
# ערך:   שם הדומיין (real_estate | import | media | saas | finance | general)

CHANNEL_DOMAINS: dict[str, str] = {
    # דוגמה — להחליף במספרים האמיתיים:
    # "whatsapp:+972501234567": "real_estate",
    # "whatsapp:+972507654321": "import",
}

# דומיין ברירת מחדל כשאין מיפוי מוגדר
DEFAULT_DOMAIN = "general"


# ─── Helper ──────────────────────────────────────────────────────────────────

def get_domain(to_number: str) -> str:
    """
    מחזיר את הדומיין לפי מספר היעד של WhatsApp.
    to_number: "whatsapp:+972XXXXXXXXX"
    """
    domain = CHANNEL_DOMAINS.get(to_number, DEFAULT_DOMAIN)
    if domain != DEFAULT_DOMAIN:
        logger.debug(f"[Config] Domain mapped: {to_number} → {domain}")
    else:
        logger.debug(f"[Config] No domain mapping for {to_number!r} — using {DEFAULT_DOMAIN}")
    return domain
