# daily_collector.py — המאסף היומי
# רץ בסוף כל יום, עובר על שיחות היום,
# מזהה נתונים עסקיים שהוזכרו ולא אושר שנשמרו,
# ושולח סיכום לאליהו בטלגרם עם כפתורי אישור.
#
# הרעיון: כמו מאסף בטיול — אחרי הכל, סורק שאף אחד לא אבד.

import os
import logging
import anthropic

logger = logging.getLogger(__name__)

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

def collect_daily(memory_key: str) -> dict:
    """
    שולף את היסטוריית היום, שולח ל-Claude לניתוח,
    מחזיר dict עם items שעלולים להיות חסרים.
    """
    from memory_store import memory

    history = memory.get_for_claude(memory_key)
    if not history:
        logger.info("collect_daily: אין היסטוריה להיום")
        return {"items": [], "all_clear": True}

    # בנה טקסט שיחה קריא
    convo_text = "\n".join(
        f"[{m['role'].upper()}]: {m['content'][:300]}"
        for m in history
    )

    if len(convo_text) < 50:
        return {"items": [], "all_clear": True}

    try:
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            timeout=30,
        )
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",   # זול ומהיר — מספיק לסריקה
            max_tokens=800,
            temperature=0.1,
            messages=[{
                "role": "user",
                "content": _COLLECTOR_PROMPT + convo_text
            }]
        )

        raw = response.content[0].text.strip()
        # נקה ```json אם יש
        raw = raw.replace("```json", "").replace("```", "").strip()

        import json
        result = json.loads(raw)
        logger.info(f"collect_daily: {len(result.get('items',[]))} פריטים זוהו")
        return result

    except Exception as e:
        logger.error(f"collect_daily error: {e}")
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

    lines.append("\nענה במספר לאישור שמירה, או 'הכל בסדר' אם כבר טופל.")
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# Send — שלח לטלגרם
# ══════════════════════════════════════════════════

def send_daily_collector(bot, chat_id: str, memory_key: str):
    """
    נקודת הכניסה מ-scheduler.
    שולף, מנתח, ושולח אם יש משהו.
    """
    logger.info(f"🔍 מאסף יומי מתחיל | {memory_key}")

    result  = collect_daily(memory_key)
    message = format_collector_message(result)

    if message is None:
        logger.info("✅ מאסף יומי: הכל תקין, אין מה לדווח")
        return

    try:
        bot.send_message(
            chat_id,
            message,
            parse_mode="Markdown"
        )
        logger.info(f"✅ מאסף יומי נשלח | {len(result['items'])} פריטים")
    except Exception as e:
        logger.error(f"מאסף יומי — שגיאת שליחה: {e}")
