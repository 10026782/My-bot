import os
import logging
from enum import Enum
from collections import defaultdict
from anthropic import Anthropic
from feature_flags import is_enabled

logger = logging.getLogger(__name__)

QUALIFICATION_SYSTEM = """
אתה מנתח לידים מקצועי עבור עסקי נדל"ן וייבוא סחורה מסין.
תפקידך לנתח כל ליד בקפדנות ולתת ציון מ-0 עד 100.

קריטריוני ניקוד:
- תקציב ורצינות פיננסית (25 נקודות)
- התאמה לתחומי הפעילות: נדל"ן / ייבוא רהיטים (25 נקודות)
- דחיפות ולוח זמנים ריאלי (20 נקודות)
- אמינות ונסיון קודם (20 נקודות)
- פוטנציאל לעסקאות חוזרות (10 נקודות)

החזר תמיד בפורמט:
ציון: [0-100]
סיווג: [HOT/WARM/COLD]
סיכום: [2-3 שורות]
סיכון עיקרי: [משפט אחד]
צעד הבא: [פעולה ספציפית אחת]
"""

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _client


def qualify_lead(lead_info: str, tenant_id: str = "default") -> dict:
    """מנתח ליד ומחזיר ציון, סיווג והמלצה לצעד הבא."""
    if not is_enabled("LEAD_QUALIFIER"):
        return _mock_qualify(lead_info)

    try:
        response = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=QUALIFICATION_SYSTEM,
            messages=[{"role": "user", "content": f"נתח את הליד הבא:\n{lead_info}"}],
        )
        return _parse_response(response.content[0].text)
    except Exception as e:
        logger.error(f"qualify_lead error: {e}")
        return {"score": 0, "tier": "COLD", "summary": "שגיאה בניתוח הליד.", "risk": str(e), "next_step": "נסה שנית"}


def batch_qualify(leads: list[str], tenant_id: str = "default") -> list[dict]:
    """מנתח רשימת לידים ומחזיר אותם מסודרים לפי ציון יורד."""
    results = []
    for lead in leads:
        result = qualify_lead(lead, tenant_id)
        result["raw"] = lead
        results.append(result)
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def format_lead_report(qualification: dict) -> str:
    """ממיר תוצאת ניתוח לליד לטקסט מוכן לשליחה בטלגרם."""
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
    INTRO = "intro"
    BUDGET = "budget"
    TIMELINE = "timeline"
    DONE = "done"


_FLOW = [
    (LeadState.INTRO,    'מה אתה מחפש? נדל"ן / ייבוא / אחר?'),
    (LeadState.BUDGET,   "מה התקציב שלך? (₪ / $)"),
    (LeadState.TIMELINE, "מה לוח הזמנים שלך? (מיידי / חודש / גמיש)"),
]


def _new_session() -> dict:
    return {"state": LeadState.INTRO, "answers": {}}


lead_sessions: dict = defaultdict(_new_session)


def handle_lead_message(sender: str, message: str) -> str | None:
    """מנהל שיחת כישור ליד ב-WhatsApp. מחזיר שאלה הבאה, או None כשהסתיים."""
    session = lead_sessions[sender]
    state = session["state"]

    if state == LeadState.DONE:
        return None

    step_index = next((i for i, (s, _) in enumerate(_FLOW) if s == state), 0)
    session["answers"][state.value] = message

    if step_index + 1 < len(_FLOW):
        next_state, next_question = _FLOW[step_index + 1]
        session["state"] = next_state
        return next_question

    session["state"] = LeadState.DONE
    lead_info = "\n".join(f"{k}: {v}" for k, v in session["answers"].items())
    result = qualify_lead(lead_info, sender)
    return format_lead_report(result)
