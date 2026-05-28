"""
config.py — MADS CORE Configuration
מיפוי ערוצים לדומיינים + הגדרות גלובליות.
להוסיף מספרי וואטסאפ כאן בלבד — שאר הקוד לא נוגעים.
"""

# ─── Channel → Domain Mapping ─────────────────────────────────────────────────
# מפתח: "whatsapp:+972XXXXXXXXX"
# ערך:   שם הדומיין (חייב להתאים למפתח ב-DOMAIN_CONFIG ב-domain_prompts.py)

CHANNEL_DOMAINS: dict[str, str] = {
    # דוגמה — להחליף במספרים האמיתיים:
    # "whatsapp:+972501234567": "realestate",
    # "whatsapp:+972507654321": "recruitment",
}

# דומיין ברירת מחדל כשאין מיפוי מוגדר
DEFAULT_DOMAIN = "realestate"

# ─── Global Feature Flags ──────────────────────────────────────────────────────
FEATURES = {
    "LEAD_QUALIFIER":    True,
    "CREATIVE_GENERATOR": True,
    "DOMAIN_ROUTING":    True,   # False = הכל הולך ל-DEFAULT_DOMAIN
}

# ─── Helper ───────────────────────────────────────────────────────────────────

def get_domain(channel: str, sender: str) -> str:
    """
    מחזיר את הדומיין לפי ערוץ ושולח.
    channel: "whatsapp" / "telegram" / "web"
    sender:  מספר טלפון או chat_id
    """
    if not FEATURES.get("DOMAIN_ROUTING"):
        return DEFAULT_DOMAIN

    key = f"{channel}:{sender}"
    return CHANNEL_DOMAINS.get(key, DEFAULT_DOMAIN)
