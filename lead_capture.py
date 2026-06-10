# lead_capture.py - W0/N03: WhatsApp Lead Capture + optional live scoring
# Captures inbound WhatsApp leads from unknown numbers (Role.LEAD).
# Flags:
# - LEAD_CAPTURE: enables capture, default off
# - LEAD_SCORING: scores first captured message after create, default off

import logging
import re
from datetime import datetime, timezone

from airtable_schema import LeadFields, Tables
from feature_flags import is_enabled

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def capture_inbound_lead(identity, message: str) -> None:
    """
    קורא לזה מ-run_agent מיד אחרי resolve_identity, כש-identity.role == Role.LEAD.
    Idempotent לפי memory_key — יוצר רשומה חדשה בפנייה ראשונה, מרענן status/updated_at בפניות הבאות.
    לעולם לא זורק — כשל כאן לא יפגע בתשובת השיחה.
    """
    if not is_enabled("LEAD_CAPTURE"):
        return

    if not message or message.strip() in _SKIP_MESSAGES:
        logger.debug(f"[LeadCapture] skipping empty/emoji-only message for {identity.memory_key}")
        return

    memory_key = identity.memory_key
    try:
        from tools.airtable_tools import airtable_get, airtable_add, airtable_update

        raw = airtable_get(Tables.LEADS, f"{{{LeadFields.MEMORY_KEY}}}='{memory_key}'")
        rec_m = re.search(r'rec\w+', raw or "")

        if rec_m:
            # פנייה חוזרת — הרשומה כבר קיימת, לא נוגעים בה (לא דורסים שדות שנכתבו ע"י מערכות אחרות)
            logger.debug(f"[LeadCapture] lead already exists, skipping: {memory_key}")
            return

        # פנייה ראשונה — יוצרים רשומה חדשה עם שדות מינימליים בלבד
        fields = {
            LeadFields.NAME:       identity.display_name or identity.external_id,
            LeadFields.PHONE:      identity.external_id,
            LeadFields.CHANNEL:    identity.channel,
            LeadFields.MEMORY_KEY: memory_key,
            LeadFields.SOURCE:     "whatsapp_inbound",
            LeadFields.STATUS:     "new",
            LeadFields.SUMMARY:    message[:500],
            LeadFields.CREATED_AT: _now_iso(),
        }
        result = airtable_add(Tables.LEADS, fields)
        if "✅" in result:
            logger.info(f"[LeadCapture] created new lead: {memory_key}")
        else:
            logger.warning(f"[LeadCapture] create failed for {memory_key}: {result}")

    except Exception as e:
        logger.error(f"[LeadCapture] capture_inbound_lead error for {memory_key}: {e}")

    """
    קורא לזה מ-run_agent מיד אחרי resolve_identity, כש-identity.role == Role.LEAD.
    Idempotent לפי memory_key — יוצר רשומה חדשה בפנייה ראשונה, מרענן status/updated_at בפניות הבאות.
    לעולם לא זורק — כשל כאן לא יפגע בתשובת השיחה.
    """
    if not is_enabled("LEAD_CAPTURE"):
        return

    memory_key = identity.memory_key
    try:
        from tools.airtable_tools import airtable_get, airtable_add, airtable_update

        raw = airtable_get(Tables.LEADS, f"{{{LeadFields.MEMORY_KEY}}}='{memory_key}'")
        rec_m = re.search(r'rec\w+', raw or "")

        if rec_m:
            # פנייה חוזרת — הרשומה כבר קיימת, לא נוגעים בה (לא דורסים שדות שנכתבו ע"י מערכות אחרות)
            logger.debug(f"[LeadCapture] lead already exists, skipping: {memory_key}")
            return

        # פנייה ראשונה — יוצרים רשומה חדשה עם שדות מינימליים בלבד
        fields = {
            LeadFields.NAME:       identity.display_name or identity.external_id,
            LeadFields.PHONE:      identity.external_id,
            LeadFields.CHANNEL:    identity.channel,
            LeadFields.MEMORY_KEY: memory_key,
            LeadFields.SOURCE:     "whatsapp_inbound",
            LeadFields.STATUS:     "new",
            LeadFields.SUMMARY:    message[:500],
            LeadFields.CREATED_AT: _now_iso(),
        }
        result = airtable_add(Tables.LEADS, fields)
        if "✅" in result:
            logger.info(f"[LeadCapture] created new lead: {memory_key}")
        else:
            logger.warning(f"[LeadCapture] create failed for {memory_key}: {result}")

    except Exception as e:
        logger.error(f"[LeadCapture] capture_inbound_lead error for {memory_key}: {e}")
