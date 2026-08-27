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
from datetime import datetime, timezone

from airtable_schema import LeadFields, Tables, InteractionLogFields
from feature_flags import is_enabled
from tools.airtable_gateway import escape_formula_value

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _is_junk(text: str) -> bool:
    stripped = (text or "").strip()
    meaningful = [ch for ch in stripped if ch.isalnum()]
    return len(meaningful) < 2


def _airtable_get(structured=False):
    from tools.airtable_tools import airtable_get, airtable_get_records
    return airtable_get_records if structured else airtable_get


# ── Find helpers ──────────────────────────────────────────────────────────────

def _find_by_external_id(external_id: str) -> str | None:
    """מחזיר record_id אם external_id קיים. None אחרת."""
    if not external_id:
        return None
    try:
        get_records = _airtable_get(structured=True)
        safe_external_id = escape_formula_value(external_id)
        records = get_records(
            Tables.LEADS, f"{{{LeadFields.EXTERNAL_ID}}}='{safe_external_id}'", max_records=1
        )
        if not records or not isinstance(records[0], dict):
            return None
        return records[0].get("id") or None
    except Exception as e:
        logger.warning("[InboundHandler] find_by_external_id error: %s", e)
        return None


def _find_by_sender(sender_id: str) -> str | None:
    """מחזיר record_id לפי sender_id. None אחרת."""
    if not sender_id:
        return None
    try:
        get_records = _airtable_get(structured=True)
        safe_sender_id = escape_formula_value(sender_id)
        records = get_records(
            Tables.LEADS, f"{{{LeadFields.SENDER_ID}}}='{safe_sender_id}'", max_records=1
        )
        if not records or not isinstance(records[0], dict):
            return None
        return records[0].get("id") or None
    except Exception as e:
        logger.warning("[InboundHandler] find_by_sender error: %s", e)
        return None


# ── Update ────────────────────────────────────────────────────────────────────

def _update_existing(record_id: str, message: str, external_id: str, sender_id: str, channel: str, domain: str, identity=None) -> None:
    """שולח מוכר — עדכון summary + log interaction."""
    try:
        from core.lead_service import LeadPayload, create_lead
        from identity import resolve_identity
        lead_identity = identity or resolve_identity(channel, sender_id)
        result = create_lead(
            lead_identity,
            LeadPayload(
                name=sender_id,
                phone=sender_id,
                domain=domain,
                source=f"{channel}_inbound",
                channel=channel,
                summary=(message or "")[:500],
                external_id=external_id,
            ),
            source_module="inbound_handler",
            existing_id=record_id,
        )
        if not result.ok:
            logger.error("[InboundHandler] canonical lead update blocked: %s", result.reason)
            return
        _log_interaction(record_id, message)
        logger.info("[InboundHandler] updated existing lead %s", record_id)
    except Exception as e:
        logger.error("[InboundHandler] update_existing error %s: %s", record_id, e)


def _log_interaction(record_id: str, message: str) -> None:
    """תועד אינטראקציה ב-Interaction Log. Best-effort — לא חוסם, אבל לא שקט על כשלון."""
    try:
        from tools.airtable_tools import airtable_add
        result = airtable_add(Tables.INTERACTION_LOG, {
            InteractionLogFields.TITLE:     "email inbound",
            InteractionLogFields.SUMMARY:   (message or "")[:500],
            InteractionLogFields.TIMESTAMP: _now_iso(),
        })
        if not result.get("ok"):
            logger.warning("[InboundHandler] log_interaction not ok: %s", result.get("user_message", result))
    except Exception as e:
        logger.warning("[InboundHandler] log_interaction error: %s", e)


# ── Create (email-only path) ──────────────────────────────────────────────────

def _create_email_lead(
    sender_id: str,
    display_name: str,
    domain: str,
    message: str,
    external_id: str,
    recipient: str = "",
) -> None:
    """
    יוצר ליד חדש ממייל.
    WhatsApp ממשיך להשתמש ב-lead_capture.capture_inbound_lead() — לא נוגעים.
    """
    try:
        from core.noninteractive_lead_cutovers import create_email_inbound_lead
        result = create_email_inbound_lead(sender_id, recipient, display_name, message, domain, external_id)
        if not result.ok:
            logger.error("[InboundHandler] canonical email lead blocked: %s", result.reason)
        return
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
    recipient: str = "",
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
            _update_existing(existing, message, external_id, sender_id, channel, domain, identity)
            return

        # 3. ליד חדש
        if channel == "email":
            _create_email_lead(sender_id, display_name, domain, message, external_id, recipient)
        else:
            # עתידי: WhatsApp + channels נוספים
            # identity קיים כאן → delegate ל-lead_capture הקיים
            if identity is not None:
                from lead_capture import capture_inbound_lead
                capture_inbound_lead(identity, message)

    except Exception as e:
        logger.error("[InboundHandler] handle_inbound error: %s", e)
