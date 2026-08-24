# lead_capture.py - W0/N03: WhatsApp Lead Capture + optional live scoring
# Flags:
# - LEAD_CAPTURE: enables capture, default off
# - LEAD_SCORING: scores first captured message after create, default off

from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING

from airtable_schema import LeadFields, LeadEventFields, LeadEventType, Tables
from feature_flags import is_enabled
from core.action_result import ActionResult, ClaimType
from core.lead_service import LeadPayload, create_lead

logger = logging.getLogger(__name__)


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
        "תשלומים", "מקדמה", "תשלום חודשי", "כמה זה עולה", "מה המחיר",
        "price", "cost", "quote", "pricing", "payment", "installment",
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
        score += 25  # הועלה מ-15 ל-25 כדי שביטוי מחיר בודד יספיק לסף WARM (25) — תיקון לבאג: "כמה עולה?" → score=15 → COLD
        why_score.append("price_intent:+25")
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

    if score >= 70:
        tier = "ULTRA_HOT"   # רותח — מיושר עם formula field (4 טיירים)
    elif score >= 50:
        tier = "HOT"         # לוהט
    elif score >= 25:
        tier = "WARM"        # חם
    else:
        tier = "COLD"        # קר

    return score, tier, why_score


def tier_from_score(score: int) -> str:
    """
    Public export — imported by lead_qualifier.py.
    Thresholds: ULTRA_HOT≥70, HOT≥50, WARM≥25, COLD<25.
    Aligned with _score_inbound_message tier logic above.
    """
    if score >= 70:
        return "ULTRA_HOT"
    if score >= 50:
        return "HOT"
    if score >= 25:
        return "WARM"
    return "COLD"


def capture_lead_event(
    identity,
    message: str,
    lead_record_id: str,
    domain: str = "general",
) -> "ActionResult":
    """
    כותב Lead Event על ליד קיים.
    נקרא כש-capture_inbound_lead מוצא ליד קיים (FOUND) והודעה חדשה.

    לא יוצר ליד חדש. לא מדרס את הליד הקיים.
    כותב רשומה ל-Tables.LEAD_EVENTS עם:
      - קישור לליד המקורי
      - event_type לפי תוכן ההודעה
      - domain שזוהה ע"י Router
      - המסר המלא + תקציר
    """
    if not is_enabled("LEAD_CAPTURE"):
        return ActionResult.failure("LEAD_CAPTURE disabled", source="lead_event")
    if _is_junk_inbound_text(message):
        return ActionResult.failure("junk_inbound", source="lead_event")
    if not lead_record_id or lead_record_id == "existing":
        return ActionResult.failure("no_lead_record_id", source="lead_event")

    try:
        from tools.airtable_tools import airtable_add
        from tma_api import relation_payload as _relation_payload

        # זיהוי event_type לפי תוכן
        msg_lower = (message or "").lower()
        if any(w in msg_lower for w in ("לחזור", "תחזור", "call me", "contact me", "להתקשר", "בדחיפות")):
            event_type = LeadEventType.FOLLOWUP_REQUEST
        elif domain and domain != "general":
            event_type = LeadEventType.INTEREST
        else:
            event_type = LeadEventType.NOTE

        summary = (message or "")[:200]
        title   = f"{event_type} | {domain} | {summary[:60]}"

        fields = {
            LeadEventFields.NAME:       title,
            LeadEventFields.LEAD_LINK:  _relation_payload(lead_record_id),
            LeadEventFields.EVENT_TYPE: event_type,
            LeadEventFields.DOMAIN:     domain,
            LeadEventFields.MESSAGE:    (message or "")[:5000],
            LeadEventFields.SUMMARY:    summary,
            LeadEventFields.CHANNEL:    identity.channel,
        }

        raw_result = airtable_add(Tables.LEAD_EVENTS, fields)
        ar = ActionResult.from_airtable_add(raw_result, source="lead_event")
        ar.claim_type = ClaimType.CREATED

        if ar.business_success:
            logger.info(
                "[LeadEvent] created event: lead=%s event_id=%s type=%s domain=%s",
                lead_record_id, ar.record_id, event_type, domain,
            )
        else:
            logger.warning(
                "[LeadEvent] create failed: lead=%s raw=%s",
                lead_record_id, raw_result,
            )
        return ar

    except Exception as e:
        logger.error("[LeadEvent] capture_lead_event error for %s: %s", lead_record_id, e)
        return ActionResult.failure(str(e), source="lead_event")


def capture_inbound_lead(
    identity, message: str, domain: str = "general", write_event: bool = True,
) -> "ActionResult":
    """
    Called from run_agent after resolve_identity, only for identity.role == Role.LEAD.
    Idempotent by memory_key. Existing Leads are not overwritten.
    Never raises: failures here must not break the conversational reply.

    write_event=False (BUG-NEW-13): כשנקרא לפני שה-Router פתר domain אמיתי,
    הקריאה הזו עדיין רצה ב-"general" (כדי לשמר memory_key תאימות-לאחור —
    ראה הערה למטה), אבל לא כותבת Lead Event עם domain שגוי. הקורא (app.py)
    אחראי לכתוב את ה-Lead Event בנפרד אחרי שה-Router פתר domain אמיתי.
    """
    if not is_enabled("LEAD_CAPTURE"):
        return ActionResult.failure("LEAD_CAPTURE disabled", source="lead_capture")
    if _is_junk_inbound_text(message):
        logger.info("[LeadCapture] junk inbound ignored before Airtable write")
        return ActionResult.failure("junk_inbound", source="lead_capture")

    # CXX: phone + domain = זהות ייחודית לליד עבור דומיינים עסקיים נפרדים.
    # תיקון תאימות לאחור (BUG-NEW-07): domain="general" (הברירת מחדל — כל
    # קריאה קיימת מ-app.py היום) חייב להישאר עם memory_key הישן (ללא סיומת),
    # אחרת:
    #   1. כל ליד קיים ב-Airtable (memory_key בלי סיומת) הופך ל"לא נמצא" —
    #      כל הודעה חוזרת מאותו איש קשר יוצרת ליד כפול חדש במקום להידחות.
    #   2. ad_attribution.py._inject_utm (app.py:1651-1654) מחפש/כותב לפי
    #      identity.memory_key הטהור — ישבר אם lead_capture כותב מפתח אחר.
    # רק domain אמיתי שונה מ-general מקבל סיומת — ליד אותו טלפון בדומיין
    # עסקי שונה (לדוגמה real_estate) הוא ליד נפרד לגמרי, owner/pipeline שונה.
    _domain_key = domain if (domain and domain != "general") else "general"
    memory_key = (
        identity.memory_key if _domain_key == "general"
        else f"{identity.memory_key}:{_domain_key}"
    )
    try:
        from tools.airtable_tools import airtable_get

        # airtable_get מחזיר str — re.search תקין כאן
        raw = airtable_get(Tables.LEADS, f"{{{LeadFields.MEMORY_KEY}}}='{memory_key}'")
        if isinstance(raw, str):
            existing_m = re.search(r"\[([^\]]+)\]", raw)
            if existing_m:
                logger.debug("[LeadCapture] lead already exists, skipping: %s", memory_key)
                # תיקון: claim_type=FOUND, לא CREATED — שום דבר לא נוצר כאן, רק
                # חיפוש שמצא רשומה קיימת. record_id האמיתי (לא placeholder
                # "existing") כדי שכל קוד עתידי שיכתוב Lead Event/Note יקבל ID
                # תקין. tool_called/tool_http_ok=True כדי ש-ClaimGate._check_found
                # (tool_called and tool_http_ok) יאשר את הclaim הזה כראוי —
                # ה-airtable_get באמת רץ ובאמת הצליח.
                existing_id = existing_m.group(0)
                found_ar = ActionResult(
                    tool_called=True,
                    tool_http_ok=True,
                    business_success=True,
                    record_id=existing_id,
                    claim_type=ClaimType.FOUND,
                    source="lead_capture",
                )
                # N-LEAD-EVENT: ליד קיים + הודעה חדשה → כתוב Lead Event
                # לא יוצרים ליד שני — רושמים את הנושא החדש כאירוע
                # BUG-NEW-13: רק אם write_event=True — אחרת הקורא יכתוב את
                # האירוע בעצמו, אחרי שה-Router פתר domain אמיתי.
                if write_event:
                    try:
                        _ev = capture_lead_event(identity, message, existing_id, domain=domain)
                        if _ev.business_success:
                            logger.info("[LeadCapture] lead event written: rec=%s", _ev.record_id)
                            found_ar.post_success = True
                    except Exception as e:
                        logger.warning("[LeadCapture] lead event failed for %s: %s", existing_id, e)
                return found_ar

        _lead_name = identity.display_name or identity.external_id or "unknown"
        result = create_lead(
            identity,
            LeadPayload(
                name=_lead_name,
                phone=identity.external_id,
                domain=_domain_key,
                source="whatsapp_inbound",
                channel=identity.channel,
                summary=(message or "")[:500],
                score=0,
                memory_key=memory_key,
            ),
            source_module="lead_capture",
            write_event=write_event,
        )
        ar = ActionResult(
            tool_called=bool(result.evidence.get("contract_id")),
            tool_http_ok=result.ok,
            business_success=result.ok,
            record_id=result.record_id,
            affected_records=1 if result.ok else 0,
            claim_type=ClaimType.CREATED if result.action == "created" else None,
            fatal_error=result.reason if not result.ok else "",
            source="lead_capture",
        )
        if not ar.business_success:
            logger.warning("[LeadCapture] canonical create failed for %s: %s", memory_key, result.reason)
        return ar

    except Exception as e:
        logger.error("[LeadCapture] capture_inbound_lead error for %s: %s", memory_key, e)
        return ActionResult.failure(str(e), source="lead_capture")
    return ar
