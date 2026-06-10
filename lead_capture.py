# lead_capture.py - W0/N03: WhatsApp Lead Capture + optional live scoring
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


def _is_junk_inbound_text(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    meaningful = [ch for ch in stripped if ch.isalnum()]
    if not meaningful:
        return True
    if len(meaningful) < 2:
        return True
    return False


def _score_inbound_message(message: str, identity=None) -> tuple[int, str, list[str]]:
    text = (message or "").lower()
    score = 0
    why_score: list[str] = []

    project_terms = (
        "פרויקט", "דירה", "נכס", "מגרש", "פנטהאוז", "משרד",
        "ייבוא", "משלוח", "ספק", "project", "apartment", "property",
        "מיטה", "מיטת", "קומותיים", "product",
    )
    price_terms = (
        "מחיר", "כמה עולה", "עלות", "הצעת מחיר", "תמחור",
        "price", "cost", "quote", "pricing",
    )
    budget_terms = (
        "תקציב", "budget", "₪", "שח", "ש\"ח", "nis", "usd", "$",
    )
    urgency_terms = (
        "דחוף", "בהול", "היום", "מחר", "השבוע",
        "urgent", "asap", "today", "tomorrow",
    )

    if any(term in text for term in project_terms):
        score += 20
        why_score.append("project:+20")
    if any(term in text for term in price_terms):
        score += 15
        why_score.append("price:+15")
    if any(term in text for term in budget_terms) or re.search(r"\b\d{4,}\b", text):
        score += 25
        why_score.append("budget:+25")
    if any(term in text for term in urgency_terms) or re.search(r"\b\d{1,2}[./-]\d{1,2}([./-]\d{2,4})?\b", text):
        score += 15
        why_score.append("urgency:+15")

    message_count = int(
        getattr(identity, "message_count", 1)
        or getattr(identity, "messages_before_capture", 1)
        or getattr(identity, "prior_message_count", 1)
        or 1
    )
    if message_count > 1 or "\n" in (message or ""):
        score += 10
        why_score.append("multi_message:+10")

    score = min(score, 100)

    if score >= 50:
        tier = "HOT"
    elif score >= 25:
        tier = "WARM"
    else:
        tier = "COLD"

    return score, tier, why_score


def capture_inbound_lead(identity, message: str) -> None:
    """
    Called from run_agent after resolve_identity, only for identity.role == Role.LEAD.
    Idempotent by memory_key. Existing Leads are not overwritten.
    Never raises: failures here must not break the conversational reply.
    """
    if not is_enabled("LEAD_CAPTURE"):
        return
    if _is_junk_inbound_text(message):
        logger.info("[LeadCapture] junk inbound ignored before Airtable write")
        return

    memory_key = identity.memory_key
    try:
        from tools.airtable_tools import airtable_add, airtable_get, airtable_update

        raw = airtable_get(Tables.LEADS, f"{{{LeadFields.MEMORY_KEY}}}='{memory_key}'")
        rec_m = re.search(r"rec\w+", raw or "")

        if rec_m:
            logger.debug("[LeadCapture] lead already exists, skipping: %s", memory_key)
            return

        fields = {
            LeadFields.NAME: identity.display_name or identity.external_id,
            LeadFields.PHONE: identity.external_id,
            LeadFields.CHANNEL: identity.channel,
            LeadFields.MEMORY_KEY: memory_key,
            LeadFields.SOURCE: "whatsapp_inbound",
            LeadFields.STATUS: "new",
            LeadFields.SUMMARY: (message or "")[:500],
            LeadFields.CREATED_AT: _now_iso(),
        }

        result = airtable_add(Tables.LEADS, fields)
        lead_id_m = re.search(r"rec\w+", result or "")
        lead_id = lead_id_m.group(0) if lead_id_m else "unknown"

        if "✅" in result:
            logger.info("[LeadCapture] created new lead: %s", memory_key)
            if is_enabled("LEAD_SCORING"):
                try:
                    if lead_id == "unknown":
                        raise ValueError("missing Airtable record id after create")
                    score, tier, why_score = _score_inbound_message(message, identity)
                    airtable_update(Tables.LEADS, lead_id, {
                        LeadFields.SCORE: score,
                        LeadFields.TIER: tier,
                    })
                    logger.info(
                        "lead_scored: score=%s tier=%s reasons=%s lead_id=%s",
                        score,
                        tier,
                        why_score,
                        lead_id,
                    )
                except Exception as e:
                    logger.warning("[LeadCapture] scoring failed for %s: %s", lead_id, e)
        else:
            logger.warning("[LeadCapture] create failed for %s: %s", memory_key, result)

    except Exception as e:
        logger.error("[LeadCapture] capture_inbound_lead error for %s: %s", memory_key, e)
