# lead_scoring.py — N02: Live Lead Scoring
# מריץ qualify_lead על שיחות נכנסות מ-WhatsApp ממספרים לא מוכרים (Role.LEAD)
# וכותב score/tier/summary חזרה לרשומת ה-Lead (search-then-update לפי memory_key —
# אותו דפוס כמו ad_attribution / lead_capture / voice_adapter).
# flag: LEAD_SCORING_LIVE (env: LEAD_SCORING_LIVE=true), כבוי כברירת מחדל.
#
# Debounce עצמאי (counter פר memory_key, in-memory) — N03 עדיין לא חיבר את
# מנוע ה-debounce של lead_memory לזרימה החיה, אז לא תלויים בו כאן.

import re
import logging

from feature_flags import is_enabled
from airtable_schema import Tables, LeadFields
from lead_qualifier import qualify_lead

logger = logging.getLogger(__name__)

SCORE_EVERY = 3

# memory_key -> {"messages": [...], "count": int}
_buffers: dict[str, dict] = {}


def score_inbound_lead(identity, message: str) -> None:
    """
    קורא לזה מ-run_agent מיד אחרי capture_inbound_lead, כש-identity.role == Role.LEAD.
    צובר הודעות, וכל SCORE_EVERY הודעות מריץ qualify_lead וכותב score/tier/summary.
    לעולם לא זורק — כשל כאן לא יפגע בתשובת השיחה.
    """
    if not is_enabled("LEAD_SCORING_LIVE"):
        return

    memory_key = identity.memory_key
    try:
        buf = _buffers.setdefault(memory_key, {"messages": [], "count": 0})
        buf["messages"].append(message)
        buf["count"] += 1

        if buf["count"] % SCORE_EVERY != 0:
            return

        lead_info = "\n".join(buf["messages"][-10:])
        result = qualify_lead(lead_info, identity.domain_id)
        _write_score(memory_key, result)

    except Exception as e:
        logger.error(f"[LeadScoring] score_inbound_lead error for {memory_key}: {e}")


def _write_score(memory_key: str, result: dict) -> None:
    from tools.airtable_tools import airtable_get, airtable_update

    raw = airtable_get(Tables.LEADS, f"{{{LeadFields.MEMORY_KEY}}}='{memory_key}'")
    rec_m = re.search(r'rec\w+', raw or "")
    if not rec_m:
        logger.warning(f"[LeadScoring] no Leads record found for {memory_key} — skipping write")
        return

    fields = {
        LeadFields.SCORE:   result.get("score", 0),
        LeadFields.TIER:    result.get("tier", "COLD"),
        LeadFields.SUMMARY: result.get("summary", ""),
    }
    update_result = airtable_update(Tables.LEADS, rec_m.group(0), fields)
    if "✅" in update_result:
        logger.info(f"[LeadScoring] scored lead {memory_key}: {fields[LeadFields.TIER]} ({fields[LeadFields.SCORE]})")
    else:
        logger.warning(f"[LeadScoring] write failed for {memory_key}: {update_result}")
