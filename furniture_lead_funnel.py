"""Deterministic Twilio WhatsApp funnel for the active furniture product."""

from __future__ import annotations

import json
import logging
import re

from airtable_schema import LeadFields, Tables

logger = logging.getLogger(__name__)

DOMAIN = "furniture_import"
PRODUCT = "triple_solid_oak_bed"

STEP_0_INTRO = "שלום וברוכים הבאים. תודה שפניתם אלינו בנוגע למיטת השלישייה מעץ מלא. איך נוכל לעזור?"
STEP_1_PRODUCT_INFO = (
    "מיטת השלישייה מיוצרת מעץ אלון מלא, עם דגש על איכות, עמידות וגימור ברמה גבוהה. "
    "זמן האספקה המשוער הוא עד כחודש וחצי."
)
STEP_2_ASK_NAME = "נשמח לחזור אליכם עם פרטים נוספים בצורה מסודרת. מה שמכם?"
STEP_3_ASK_CITY = "תודה. מאיזו עיר אתם?"
STEP_4_ASK_BED_COUNT = "כמה מיטות שלישייה אתם צריכים?"
STEP_5_ASK_NEEDED_DATE = "יש מועד מסוים שבו המיטה נדרשת?"
STEP_6_ASK_CALL_PERMISSION = "האם נוכל ליצור איתכם קשר טלפוני? מתי הזמן הנוח לכם?"
STEP_7_DONE = "תודה רבה! הפרטים נרשמו. ניצור איתכם קשר בהקדם."

_PRICE_DELIVERY_TERMS = (
    "מחיר", "כמה עולה", "עלות", "עולה", "זמינות", "זמין", "מלאי", "אספקה", "משלוח",
    "price", "cost", "available", "availability", "delivery",
)
_URGENT_TERMS = (
    "דחוף", "בהקדם", "היום", "מחר", "השבוע", "שבוע הבא", "לפני החג",
    "urgent", "asap", "today", "tomorrow",
)


def handle_furniture_lead_message(sender: str, message: str, domain: str, destination: str = "") -> str | None:
    """Return a fixed funnel reply for furniture leads, or None for agent fallback."""
    if domain != DOMAIN:
        return None

    try:
        from session_store import lead_sessions

        session = lead_sessions.get_or_create(sender, domain=DOMAIN, channel="whatsapp")
        if destination:
            session["owner_destination"] = destination
        session.setdefault("conversation_step", "step_0_intro")
        session.setdefault("answers", {})
        step = int(session.get("step", 0) or 0)

        text = (message or "").strip()
        answers = session["answers"]
        _append_message(answers, text)

        if step <= 0:
            answers.setdefault("initial_message", text)
            _advance(lead_sessions, sender, session, 1, "initial_message", text, "step_1_product_info")
            _save_lead(sender, session)
            return STEP_0_INTRO

        if step == 1:
            answers["product_interest"] = text
            _advance(lead_sessions, sender, session, 2, "product_interest", text, "step_2_ask_name")
            _save_lead(sender, session)
            return f"{STEP_1_PRODUCT_INFO}\n\n{STEP_2_ASK_NAME}"

        if step == 2:
            answers["name"] = text
            _advance(lead_sessions, sender, session, 3, "name", text, "step_3_ask_city")
            _save_lead(sender, session)
            return STEP_3_ASK_CITY

        if step == 3:
            answers["city"] = text
            _advance(lead_sessions, sender, session, 4, "city", text, "step_4_ask_bed_count")
            _save_lead(sender, session)
            return STEP_4_ASK_BED_COUNT

        if step == 4:
            answers["bed_count"] = text
            _advance(lead_sessions, sender, session, 5, "bed_count", text, "step_5_ask_needed_date")
            _save_lead(sender, session)
            return STEP_5_ASK_NEEDED_DATE

        if step == 5:
            answers["needed_date"] = text
            _advance(lead_sessions, sender, session, 6, "needed_date", text, "step_6_ask_call_permission")
            _save_lead(sender, session)
            return STEP_6_ASK_CALL_PERMISSION

        if step == 6:
            answers["call_permission"] = text
            _advance(lead_sessions, sender, session, 7, "call_permission", text, "step_7_done")
            score = _score_answers(answers)
            lead_sessions.mark_done(sender, score=score, tier=_classify(score))
            _save_lead(sender, session)
            return STEP_7_DONE

        return None
    except Exception as exc:
        logger.warning("[FurnitureFunnel] failed for %s: %s", sender, exc)
        return None


def _advance(store, sender: str, session: dict, step: int, field_name: str, answer: str, label: str) -> None:
    store.update_step(sender, step=step, field_name=field_name, answer=answer)
    session["conversation_step"] = label


def _append_message(answers: dict, text: str) -> None:
    messages = answers.setdefault("messages", [])
    if isinstance(messages, list):
        messages.append(text)


def _score_answers(answers: dict) -> int:
    score = 0
    if (answers.get("name") or "").strip():
        score += 25
    if (answers.get("city") or "").strip():
        score += 15
    if _is_urgent(answers.get("needed_date", "")):
        score += 25
    if _asked_price_delivery_availability(answers):
        score += 20
    if (answers.get("call_permission") or "").strip():
        score += 10
    return score


def _classify(score: int) -> str:
    if score >= 60:
        return "HOT"
    if score >= 30:
        return "WARM"
    return "COLD"


def _is_urgent(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in _URGENT_TERMS) or bool(re.search(r"\b\d{1,2}[./-]\d{1,2}", lowered))


def _asked_price_delivery_availability(answers: dict) -> bool:
    text = " ".join(str(v) for v in answers.get("messages", [])).lower()
    return any(term in text for term in _PRICE_DELIVERY_TERMS)


def _save_lead(sender: str, session: dict) -> None:
    try:
        from core.noninteractive_lead_cutovers import create_furniture_inbound_lead
        answers = session.get("answers", {})
        beds = (answers.get("bed_count") or "").strip()
        summary = f"Furniture lead: triple solid oak bed{f' | מיטות: {beds}' if beds else ''}"
        result = create_furniture_inbound_lead(
            sender, session.get("owner_destination", ""), (answers.get("name") or "").strip(),
            summary, json.dumps(answers, ensure_ascii=False),
            status="waiting_call" if (answers.get("name") or "").strip() else "new",
            score=_score_answers(answers), existing_id=session.get("lead_record_id", ""),
        )
        if not result.ok:
            logger.error("[FurnitureFunnel] canonical lead blocked: %s", result.reason)
        elif result.record_id:
            session["lead_record_id"] = result.record_id
        return
    except Exception as exc:
        logger.warning("[FurnitureFunnel] lead save failed for %s: %s", sender, exc)


def _formula_escape(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("'", "\\'")


__all__ = [
    "DOMAIN",
    "STEP_0_INTRO",
    "STEP_1_PRODUCT_INFO",
    "STEP_2_ASK_NAME",
    "STEP_3_ASK_CITY",
    "STEP_4_ASK_BED_COUNT",
    "STEP_5_ASK_NEEDED_DATE",
    "STEP_6_ASK_CALL_PERMISSION",
    "STEP_7_DONE",
    "handle_furniture_lead_message",
]
