# inbound_handler.py — F06: Inbound Lead Gate
# Gate בלבד — מחליט מה לעשות, לא מחליף את lead_capture.
#
# לוגיקה:
#   1. external_id קיים → skip (כפילות מדויקת)
#   2. sender_id קיים → update + log_interaction
#   3. חדש → delegate ל-lead_capture._create_lead_direct()
#
# flag: LEAD_CAPTURE (אותו flag כמו lead_capture)
# לא נוגע ב: lead_capture.py, app.py, airtable_gateway.py

from __future__ import annotations
import logging
import re
from datetime import datetime, timezone

from airtable_schema import LeadFields, Tables, InteractionLogFields
from feature_flags import is_enabled

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _is_junk(text: str) -> bool:
    stripped = (text or "").strip()
    meaningful = [ch for ch in stripped if ch.isalnum()]
    return len(meaningful) < 2


def _airtable_get():
    from tools.airtable_tools import airtable_get
    return airtable_get


def _gw_patch(table, record_id, fields):
    from tools.airtable_gateway import airtable_patch
    airtable_patch(table, record_id, fields, source="inbound_handler")


# ── Find helpers ──────────────────────────────────────────────────────────────

def _find_by_external_id(external_id: str) -> str | None:
    """מחזיר record_id אם external_id קיים. None אחרת."""
    if not external_id:
        return None
    try:
        get = _airtable_get()
        raw = get(Tables.LEADS, f"{{{LeadFields.EXTERNAL_ID}}}='{external_id}'")
        m = re.search(r"rec\w+", raw or "")
        return m.group(0) if m else None
    except Exception as e:
        logger.warning("[InboundHandler] find_by_external_id error: %s", e)
        return None


def _find_by_sender(sender_id: str) -> str | None:
    """מחזיר record_id לפי sender_id. None אחרת."""
    if not sender_id:
        return None
    try:
        get = _airtable_get()
        raw = get(Tables.LEADS, f"{{{LeadFields.SENDER_ID}}}='{sender_id}'")
        m = re.search(r"rec\w+", raw or "")
        return m.group(0) if m else None
    except Exception as e:
        logger.warning("[InboundHandler] find_by_sender error: %s", e)
        return None


# ── Update ────────────────────────────────────────────────────────────────────

def _update_existing(record_id: str, message: str, external_id: str) -> None:
    """שולח מוכר — עדכון summary + log interaction."""
    try:
        _gw_patch(Tables.LEADS, record_id, {
            LeadFields.SUMMARY:     (message or "")[:500],
            LeadFields.EXTERNAL_ID: external_id,
        })
        _log_interaction(record_id, message)
        logger.info("[InboundHandler] updated existing lead %s", record_id)
    except Exception as e:
        logger.error("[InboundHandler] update_existing error %s: %s", record_id, e)


def _log_interaction(record_id: str, message: str) -> None:
    """תועד אינטראקציה ב-Interaction Log."""
    try:
        from tools.airtable_tools import airtable_add
        airtable_add(Tables.INTERACTION_LOG, {
            InteractionLogFields.TITLE:     "email inbound",
            InteractionLogFields.SUMMARY:   (message or "")[:500],
            InteractionLogFields.TIMESTAMP: _now_iso(),
        })
    except Exception as e:
        logger.warning("[InboundHandler] log_interaction error: %s", e)


# ── Create (email-only path) ──────────────────────────────────────────────────

def _create_email_lead(
    sender_id: str,
    display_name: str,
    domain: str,
    message: str,
    external_id: str,
) -> None:
    """
    יוצר ליד חדש ממייל.
    WhatsApp ממשיך להשתמש ב-lead_capture.capture_inbound_lead() — לא נוגעים.
    """
    try:
        from tools.airtable_tools import airtable_add
        fields = {
            LeadFields.NAME:        display_name or sender_id,
            LeadFields.CHANNEL:     "email",
            LeadFields.DOMAIN:      domain,
            LeadFields.SOURCE:      "email_inbound",
            LeadFields.STATUS:      "new",
            LeadFields.SUMMARY:     (message or "")[:500],
            LeadFields.CREATED_AT:  _now_iso(),
            LeadFields.EXTERNAL_ID: external_id,
            LeadFields.SENDER_ID:   sender_id,
            LeadFields.MEMORY_KEY:  f"email:{sender_id}",
        }
        result = airtable_add(Tables.LEADS, fields)
        m = re.search(r"rec\w+", result or "")
        record_id = m.group(0) if m else "unknown"
        logger.info("[InboundHandler] created email lead %s domain=%s", record_id, domain)
    except Exception as e:
        logger.error("[InboundHandler] create_email_lead error: %s", e)


# ── Main Gate ─────────────────────────────────────────────────────────────────

def handle_inbound(
    sender_id: str,        # כתובת מייל (email) / טלפון (whatsapp — עתידי)
    message: str,
    channel: str,          # "email" | "whatsapp" (עתידי)
    domain: str,
    external_id: str = "", # gmail:<msg_id>
    display_name: str = "",
    identity=None,         # קיים ב-WhatsApp, None ב-Email
) -> None:
    """
    Gate אחיד לכל הודעה נכנסת.
    לעולם לא זורק — כשל כאן לא שובר תשובת שיחה.

    שלב 1 (עכשיו): email בלבד.
    שלב 2 (עתידי): WhatsApp מחובר דרך app.py.
    """
    if not is_enabled("LEAD_CAPTURE"):
        return
    if _is_junk(message):
        logger.info("[InboundHandler] junk ignored channel=%s", channel)
        return

    try:
        # 1. skip — כפילות מדויקת
        if external_id and _find_by_external_id(external_id):
            logger.debug("[InboundHandler] duplicate external_id skip: %s", external_id)
            return

        # 2. שולח מוכר → עדכן
        existing = _find_by_sender(sender_id)
        if existing:
            _update_existing(existing, message, external_id)
            return

        # 3. ליד חדש
        if channel == "email":
            _create_email_lead(sender_id, display_name, domain, message, external_id)
        else:
            # עתידי: WhatsApp + channels נוספים
            # identity קיים כאן → delegate ל-lead_capture הקיים
            if identity is not None:
                from lead_capture import capture_inbound_lead
                capture_inbound_lead(identity, message)

    except Exception as e:
        logger.error("[InboundHandler] handle_inbound error: %s", e)
