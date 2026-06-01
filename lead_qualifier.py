"""
lead_qualifier.py — Lead Qualification Engine (MADS CORE)
שינויים מ-v2:
- QUALIFICATION_SYSTEM נטען לפי דומיין (לא קשיח)
- _FLOW נטען לפי דומיין (לא קשיח)
- שאר הקוד זהה לחלוטין — backward compatible
"""

import os
import logging
from enum import Enum
from anthropic import Anthropic
from feature_flags import is_enabled
from domain_prompts import get_qualification_prompt, get_flow, get_domain_config
from config import get_domain
from session_store import lead_sessions

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _client


# ─── Lead Qualification ───────────────────────────────────────────────────────

def qualify_lead(lead_info: str, domain: str = "realestate") -> dict:
    if not is_enabled("LEAD_QUALIFIER"):
        return _mock_qualify(lead_info)
    system_prompt = get_qualification_prompt(domain)
    try:
        response = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": f"נתח את הליד הבא:\n{lead_info}"}],
        )
        return _parse_response(response.content[0].text)
    except Exception as e:
        logger.error(f"qualify_lead error: {e}")
        return {"score": 0, "tier": "COLD", "summary": "שגיאה בניתוח הליד.", "risk": str(e), "next_step": "נסה שנית"}


def batch_qualify(leads: list[str], domain: str = "realestate") -> list[dict]:
    results = []
    for lead in leads:
        result = qualify_lead(lead, domain)
        result["raw"] = lead
        results.append(result)
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def format_lead_report(qualification: dict) -> str:
    tier_emoji = {"HOT": "🔥", "WARM": "🟡", "COLD": "🧊"}.get(qualification.get("tier", ""), "❓")
    score = qualification.get("score", 0)
    return (
        f"{tier_emoji} *ציון ליד: {score}/100*\n"
        f"📋 {qualification.get('summary', '')}\n"
        f"⚠️ סיכון: {qualification.get('risk', '')}\n"
        f"➡️ צעד הבא: {qualification.get('next_step', '')}"
    )


def _parse_response(text: str) -> dict:
    result = {"score": 0, "tier": "COLD", "summary": "", "risk": "", "next_step": ""}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("ציון:"):
            try:
                result["score"] = int("".join(filter(str.isdigit, line.split(":", 1)[1])))
            except ValueError:
                pass
        elif line.startswith("סיווג:"):
            raw = line.split(":", 1)[1].strip().upper()
            result["tier"] = raw if raw in ("HOT", "WARM", "COLD") else "COLD"
        elif line.startswith("סיכום:"):
            result["summary"] = line.split(":", 1)[1].strip()
        elif line.startswith("סיכון עיקרי:"):
            result["risk"] = line.split(":", 1)[1].strip()
        elif line.startswith("צעד הבא:"):
            result["next_step"] = line.split(":", 1)[1].strip()
    return result


def _mock_qualify(lead_info: str) -> dict:
    return {
        "score": 50,
        "tier": "WARM",
        "summary": f"ניתוח מקדים (מצב ללא API): {lead_info[:80]}...",
        "risk": "LEAD_QUALIFIER לא מופעל בסביבה זו.",
        "next_step": "הפעל LEAD_QUALIFIER=true ב-env variables.",
    }


# ─── WhatsApp Lead Session State Machine ─────────────────────────────────────

class LeadState(Enum):
    DONE = "done"


_RESET_KEYWORDS = {"איפוס", "reset", "restart", "התחל מחדש"}


def _new_session(domain: str = "realestate") -> dict:
    get_flow(domain)  # validate domain exists
    return {
        "domain": domain,
        "step": 0,
        "answers": {},
        "done": False,
    }


def handle_lead_message(sender: str, message: str, channel: str = "whatsapp") -> str | None:
    """
    מנהל שיחת ליד לפי State Machine דינמי לפי דומיין.
    מחזיר את התשובה הבאה, או None כשהשיחה הסתיימה.
    """
    # איפוס
    if message.strip() in _RESET_KEYWORDS:
        lead_sessions.delete(sender)
        domain = get_domain(channel, sender)
        flow = get_flow(domain)
        return flow[0][1]

    # get existing or create new session with correct domain + channel
    session = lead_sessions.get(sender)
    if session is None:
        domain = get_domain(channel, sender)
        session = lead_sessions.get_or_create(sender, domain, channel)

    # שיחה הסתיימה
    if session["done"]:
        return None

    domain = session["domain"]
    flow = get_flow(domain)
    step = session["step"]

    # שמור תשובה לשלב הנוכחי
    field_name = flow[step][0]
    next_step = step + 1
    lead_sessions.update_step(sender, next_step, field_name, message.strip())

    # יש עוד שאלות
    if next_step < len(flow):
        return flow[next_step][1]

    # סיימנו — מנתחים
    lead_info = "\n".join(f"{k}: {v}" for k, v in session["answers"].items())
    result = qualify_lead(lead_info, domain)
    lead_sessions.mark_done(sender, score=result.get("score", 0), tier=result.get("tier", "COLD"))
    return format_lead_report(result)


def init_lead_session(sender: str, channel: str = "whatsapp") -> str:
    """
    יוצר session חדש לליד ומחזיר את שאלת הפתיחה.
    קורא לזה מ-app.py כשליד חדש נכנס.
    """
    lead_sessions.delete(sender)  # איפוס session קיים אם יש
    domain = get_domain(channel, sender)
    lead_sessions.get_or_create(sender, domain, channel)
    flow = get_flow(domain)
    return flow[0][1]
