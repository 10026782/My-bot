"""
config.py — Channel → Domain Mapping
מיפוי מספרי WhatsApp לדומיינים עסקיים.
להוסיף מספרים כאן בלבד — שאר הקוד לא נוגעים.
"""

import json
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
# Missing entries are intentional: the resolver fails closed
# (core/source_owner_mapping.py::resolve_owner_user_id()).
#
# Populated via the OWNER_USER_ID_MAPPINGS env var (Render) — same
# env-JSON-first, hardcoded-fallback pattern as IDENTITY_MAP
# (see identity.py::_load_registry()). Shape:
#   {"whatsapp_destination": {"whatsapp:+972...": "<user_id>"},
#    "email_recipient":      {"leads@example.com": "<user_id>"},
#    "voice_destination":    {"+972...": "<user_id>"}}
# No code change is needed to populate real values — only the env var.
_OWNER_USER_ID_MAPPING_SOURCES = ("whatsapp_destination", "email_recipient", "voice_destination")


def _load_owner_user_id_mappings() -> dict[str, dict[str, str]]:
    defaults: dict[str, dict[str, str]] = {source: {} for source in _OWNER_USER_ID_MAPPING_SOURCES}

    raw = os.environ.get("OWNER_USER_ID_MAPPINGS", "").strip()
    if not raw:
        return defaults

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[Config] OWNER_USER_ID_MAPPINGS parse error: {e} — falling back to empty (fail-closed)")
        return defaults

    if not isinstance(parsed, dict):
        logger.error("[Config] OWNER_USER_ID_MAPPINGS must be a JSON object — falling back to empty (fail-closed)")
        return defaults

    for source in _OWNER_USER_ID_MAPPING_SOURCES:
        value = parsed.get(source)
        if value is None:
            continue
        if isinstance(value, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            defaults[source] = value
        else:
            logger.error(
                f"[Config] OWNER_USER_ID_MAPPINGS[{source!r}] must be an object of "
                "string→string — ignoring, this source stays empty (fail-closed)"
            )

    unknown_keys = set(parsed) - set(_OWNER_USER_ID_MAPPING_SOURCES)
    if unknown_keys:
        logger.warning(f"[Config] OWNER_USER_ID_MAPPINGS has unrecognized keys, ignored: {sorted(unknown_keys)}")

    return defaults


OWNER_USER_ID_MAPPINGS: dict[str, dict[str, str]] = _load_owner_user_id_mappings()

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
