# llm_fallback.py — OpenAI fallback wrapper
# כל מודול שצריך Claude text-only (ללא tools) מייבא מכאן.
# אם Claude נכשל עם שגיאה חולפת (timeout / 429 / 529 / credit) →
#   fallback אוטומטי ל-OpenAI, כשהדגל OPENAI_FALLBACK_ENABLED=true.
#
# שני ממשקים:
#   call_anthropic_text() — לקריאות רגילות (lead_qualifier, tma_api וכו')
#   agent_fallback_text() — לrun_agent בלבד: מוסיף הנחיה "אל תטען ביצוע פעולות"

import logging
import os

from feature_flags import is_enabled

logger = logging.getLogger(__name__)

# הנחיה שמוסיפים לsystem_prompt של הAgent כשאנחנו ב-fallback
_NO_ACTION_INSTRUCTION = (
    "\n\n---\nחשוב: תן תשובה טקסטואלית בלבד. "
    "אל תטען שביצעת פעולות כגון כתיבה למסד נתונים, שליחת הודעות, "
    "יצירת אירועים, עדכון תשלומים, או כל פעולה אחרת — "
    "כעת אינך מחובר לכלים ואינך יכול לבצע פעולות."
)


# ── ממשק ציבורי ─────────────────────────────────────────────────

def call_anthropic_text(
    messages: list[dict],
    *,
    system: str = "",
    model: str = "claude-haiku-4-5",
    max_tokens: int = 1024,
) -> str:
    """
    קורא Claude text-only (ללא tools).
    על שגיאה חולפת → fallback ל-OpenAI אם OPENAI_FALLBACK_ENABLED=true.
    על שגיאה קשה (401, 413...) — זורק.
    """
    try:
        import anthropic as _anthropic
        _client = _anthropic.Anthropic(
            api_key = os.environ.get("ANTHROPIC_API_KEY", ""),
            timeout  = 25,
        )
        resp = _client.messages.create(
            model      = model,
            max_tokens = max_tokens,
            system     = system,
            messages   = messages,
        )
        return (resp.content[0].text if resp.content else "").strip()

    except Exception as e:
        if _is_transient(e):
            logger.warning(f"[LLMFallback] Claude failed ({type(e).__name__}) — trying OpenAI")
            return _openai_text(system, messages, max_tokens)
        raise


def agent_fallback_text(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1024,
    caller: str = "",
) -> str:
    """
    Fallback לrun_agent בלבד — קורא ישירות ל-OpenAI (Claude כבר נכשל).
    מוסיף הנחיה לא לטעון ביצוע פעולות.
    לעולם לא זורק.
    """
    try:
        full_system = system_prompt + _NO_ACTION_INSTRUCTION
        result = _openai_text(
            full_system,
            [{"role": "user", "content": user_message}],
            max_tokens,
        )
        logger.info(f"[LLMFallback] agent fallback OK for {caller}")
        return result
    except Exception as e:
        logger.error(f"[LLMFallback] agent_fallback_text failed: {e}")
        return "⚠️ השרת עמוס כרגע. נסה שוב בעוד דקה."


# ── פנימי ───────────────────────────────────────────────────────

def _is_transient(e: Exception) -> bool:
    """מחזיר True לשגיאות חולפות שמצדיקות fallback."""
    try:
        import anthropic as _anthropic
        if isinstance(e, _anthropic.APITimeoutError):
            return True
        if isinstance(e, _anthropic.APIStatusError):
            if e.status_code in (429, 500, 502, 503, 529):
                return True
            _text = ((getattr(e, "message", "") or "") + str(e.body or "")).lower()
            if "credit balance" in _text or "insufficient_credits" in _text:
                return True
    except Exception:
        pass
    return False


def _openai_text(system: str, messages: list[dict], max_tokens: int) -> str:
    """מבצע את קריאת ה-OpenAI בפועל. זורק אם נכשל."""
    if not is_enabled("OPENAI_FALLBACK_ENABLED"):
        logger.warning("[LLMFallback] OPENAI_FALLBACK_ENABLED=false — fallback מושבת")
        return "⚠️ השרת עמוס כרגע. נסה שוב בעוד דקה."

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        logger.error("[LLMFallback] OPENAI_API_KEY חסר")
        return "⚠️ השרת עמוס כרגע. נסה שוב בעוד דקה."

    try:
        import openai as _openai
    except ImportError:
        logger.error("[LLMFallback] openai package לא מותקן")
        return "⚠️ השרת עמוס כרגע. נסה שוב בעוד דקה."

    model = os.environ.get("OPENAI_FALLBACK_MODEL", "gpt-4o-mini")
    oa = _openai.OpenAI(api_key=key, timeout=20)
    oa_messages = ([{"role": "system", "content": system}] if system else []) + messages
    resp = oa.chat.completions.create(
        model       = model,
        messages    = oa_messages,
        max_tokens  = max_tokens,
        temperature = 0.2,
    )
    text = (resp.choices[0].message.content or "").strip()
    return text if text else "⚠️ לא התקבלה תשובה."
