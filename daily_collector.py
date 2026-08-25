# daily_collector.py — המאסף היומי
# רץ בסוף כל יום, עובר על שיחות היום,
# מזהה נתונים עסקיים שהוזכרו ולא אושר שנשמרו,
# ושולח סיכום לאליהו בטלגרם עם כפתורי אישור.
#
# הרעיון: כמו מאסף בטיול — אחרי הכל, סורק שאף אחד לא אבד.

import os
import json
import logging
from core import create_execution_context, create_operation
from core.turn_coordinator_runtime import resolve_daily_persistence_gap_capability
from llm_fallback import call_anthropic_text

logger = logging.getLogger(__name__)

# BUG-066 (BUG-DAILY-01): bounds bot.send_message so a network stall can't
# freeze the single scheduler thread (schedule runs jobs sequentially — a
# hanging call here would stall every other due job behind it, not just this one).
_SEND_TIMEOUT = 15

# ══════════════════════════════════════════════════
# Prompt למאסף
# ══════════════════════════════════════════════════

_COLLECTOR_PROMPT = """עבור על שיחות היום הבאות.

זהה כל נתון עסקי שהוזכר ועלול לא להיות שמור במערכת.

חפש:
- סכומי כסף ("שרפנו", "שילמנו", "קיבלנו", "עולה", "₪")
- לידים/לקוחות ("מעוניין", "רוצה", "פנה", "מחכה לתשובה")
- פגישות/תאריכים ("נפגש", "ביום", "בשעה", "קבענו")
- משימות/החלטות ("צריך ל", "חייבים", "תזכיר לי", "נחליט")
- עסקאות ("סגרנו", "חתמנו", "אישר", "ביטל")

לכל נתון שזיהית — קבע:
✅ נשמר — אם ראית בשיחה אישור מפורש שנשמר ב-Airtable/Calendar/Drive
❓ לא ברור — אם הוזכר אבל לא ראית אישור שמירה

החזר JSON בלבד, ללא טקסט נוסף:
{
  "items": [
    {
      "text": "תיאור קצר של הנתון",
      "category": "cashflow | crm | calendar | task",
      "status": "saved | unclear",
      "suggested_action": "מה לעשות אם לא נשמר"
    }
  ],
  "all_clear": true/false
}

אם אין כלום שעלול לאבד — החזר {"items": [], "all_clear": true}

שיחות היום:
"""

# ══════════════════════════════════════════════════
# Collect — לוגיקה ראשית
# ══════════════════════════════════════════════════

_ALLOWED_CATEGORIES = frozenset({"cashflow", "crm", "calendar", "task"})
_ALLOWED_STATUSES = frozenset({"saved", "unclear"})


def verify_daily_collector_result(result: object) -> dict:
    """Accept only the collector's bounded structural result contract."""
    if not isinstance(result, dict):
        raise ValueError("collector result must be an object")
    if not isinstance(result.get("items"), list):
        raise ValueError("collector result items must be a list")
    if not isinstance(result.get("all_clear"), bool):
        raise ValueError("collector result all_clear must be a bool")
    for item in result["items"]:
        if not isinstance(item, dict):
            raise ValueError("collector result item must be an object")
        if item.get("category") not in _ALLOWED_CATEGORIES:
            raise ValueError("collector result item category is invalid")
        if item.get("status") not in _ALLOWED_STATUSES:
            raise ValueError("collector result item status is invalid")
        if not isinstance(item.get("text"), str):
            raise ValueError("collector result item text must be a string")
        if not isinstance(item.get("suggested_action"), str):
            raise ValueError("collector result item suggested_action must be a string")
    return result

def collect_daily(memory_key: str) -> dict:
    """
    שולף את היסטוריית היום, שולח ל-Claude לניתוח,
    מחזיר dict עם items שעלולים להיות חסרים.

    BUG-066 (BUG-DAILY-01): כל שלב מבודד בנפרד (fetch history / LLM+parse)
    עם logging מפורש (start/success/error) — כשל בשלב אחד לא מתפשט כחריגה
    בלתי-מטופלת; הפונקציה תמיד מחזירה fallback בטוח
    ({"items": [], "all_clear": True}) ולעולם לא raise.
    """
    logger.info("collect_daily: start — fetch history")
    try:
        from memory_store import memory
        history = memory.get_for_claude(memory_key)
    except Exception as e:
        logger.error(f"collect_daily: fetch history failed — {e}")
        return {"items": [], "all_clear": True}

    if not history:
        logger.info("collect_daily: אין היסטוריה להיום — skip")
        return {"items": [], "all_clear": True}

    # בנה טקסט שיחה קריא
    convo_text = "\n".join(
        f"[{m['role'].upper()}]: {m['content'][:300]}"
        for m in history
    )

    if len(convo_text) < 50:
        logger.info("collect_daily: היסטוריה קצרה מדי לניתוח — skip")
        return {"items": [], "all_clear": True}

    logger.info("collect_daily: fetch history done — start LLM analysis")
    try:
        capability = resolve_daily_persistence_gap_capability()
        operation = create_operation(capability)
        execution_context = create_execution_context(capability, operation)
        raw = call_anthropic_text(
            source="daily_collector.collect_daily",
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            temperature=0.1,
            timeout=30,
            messages=[{
                "role": "user",
                "content": _COLLECTOR_PROMPT + convo_text
            }],
            execution_context=execution_context,
        ).strip()

        # נקה ```json אם יש
        raw = raw.replace("```json", "").replace("```", "").strip()

        result = verify_daily_collector_result(json.loads(raw))
        logger.info(f"collect_daily: LLM analysis done — {len(result.get('items', []))} פריטים זוהו")
        return result

    except Exception as e:
        logger.error(f"collect_daily: LLM analysis failed — {e}")
        return {"items": [], "all_clear": True}


# ══════════════════════════════════════════════════
# Format — בנה הודעת טלגרם
# ══════════════════════════════════════════════════

_CATEGORY_LABELS = {
    "cashflow": "💸 תזרים",
    "crm":      "👤 CRM",
    "calendar": "📅 יומן",
    "task":     "📋 משימה",
}

def format_collector_message(result: dict) -> str | None:
    """
    מחזיר הודעת טלגרם מפורמטת, או None אם הכל תקין.
    """
    if result.get("all_clear") or not result.get("items"):
        return None

    unclear = [i for i in result["items"] if i.get("status") == "unclear"]
    if not unclear:
        return None

    lines = ["🔍 *מאסף יומי — נתונים שאולי לא נשמרו:*\n"]
    for i, item in enumerate(unclear, 1):
        cat   = _CATEGORY_LABELS.get(item.get("category", ""), "📌")
        text  = item.get("text", "")
        action = item.get("suggested_action", "")
        lines.append(f"{i}. {cat} — {text}")
        if action:
            lines.append(f"   ↳ {action}")

    # BUG-070 gap #3: אין handler שמפרסר תגובה ממוספרת לפריטי המאסף היומי
    # (אין contract/state שמייצג אותם) — אין להבטיח יכולת שלא קיימת.
    lines.append("\nכדי לשמור פריט — עדכן אותו ידנית או שלח לי אותו כליד/משימה בנפרד.")
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# Send — שלח לטלגרם
# ══════════════════════════════════════════════════

def send_daily_collector(bot, chat_id: str, memory_key: str):
    """
    נקודת הכניסה מ-scheduler.
    שולף, מנתח, ושולח אם יש משהו.

    BUG-066 (BUG-DAILY-01): כל שלב (fetch+analyze / format / send) מתועד
    בנפרד (start/done/error) ומבודד — כשל בפורמט או בשליחה לא מתפשט,
    נרשם ומחזיר בשקט. collect_daily() עצמה כבר לא raise-ת (ראה שם).
    """
    logger.info(f"🔍 מאסף יומי מתחיל | {memory_key}")

    result = collect_daily(memory_key)

    logger.info("מאסף יומי: start — format message")
    try:
        message = format_collector_message(result)
    except Exception as e:
        logger.error(f"מאסף יומי: format נכשל — {e}")
        return

    if message is None:
        logger.info("✅ מאסף יומי: הכל תקין, אין מה לדווח")
        return

    logger.info("מאסף יומי: format done — start send")
    try:
        bot.send_message(
            chat_id,
            message,
            parse_mode="Markdown",
            timeout=_SEND_TIMEOUT,
        )
        logger.info(f"✅ מאסף יומי נשלח | {len(result['items'])} פריטים")
    except Exception as e:
        logger.error(f"מאסף יומי — שגיאת שליחה: {e}")
