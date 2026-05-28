# action_validator.py — ACTION VALIDATOR
# בודק שלמות פרמטרים לפני dispatch_tool.
# זה ה-gate האמיתי: rule-based, לא confidence מ-LLM.
#
# זרימה:
#   Claude מציע tool_use
#   → validate_action(name, inputs)
#   → BLOCK (חסר פרמטר) | ALLOW → dispatch_tool
#
# הודעת BLOCK חוזרת למשתמש כשאלה ישירה — לא שגיאה טכנית.

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Required fields per tool
# נגזר מ-schemas.py "required" — מקור יחיד לאמת
# ══════════════════════════════════════════════════

_REQUIRED: dict[str, list[str]] = {
    "search_drive":         ["query"],
    "read_drive_file":      ["file_name"],
    "calendar_get_events":  [],                            # הכל אופציונלי
    "calendar_create_event":["summary", "start_time"],
    "gmail_draft":          ["to", "subject", "body"],
    "gmail_send_draft":     ["draft_id"],
    "gmail_read":           [],
    "sheets_append":        ["sheet_name", "row_data"],
    "airtable_get":         ["table"],
    "airtable_add":         ["table", "fields"],
    "airtable_update":      ["table", "record_id", "fields"],
}

# הודעות שאלה ידידותיות לכל שדה חסר
_FIELD_QUESTIONS: dict[str, str] = {
    "query":            "מה לחפש ב-Drive?",
    "file_name":        "מה שם הקובץ לקריאה?",
    "summary":          "מה כותרת הפגישה?",
    "start_time":       "מתי הפגישה? (תאריך ושעה)",
    "to":               "למי לשלוח את המייל?",
    "subject":          "מה נושא המייל?",
    "body":             "מה תוכן המייל?",
    "draft_id":         "מה מזהה הטיוטה לשליחה?",
    "sheet_name":       "מה שם הגיליון?",
    "row_data":         "מה הנתונים להוספה?",
    "table":            "לאיזו טבלה? (CRM / Cashflow / Tasks)",
    "fields":           "מה השדות לעדכון?",
    "record_id":        "מה מזהה הרשומה לעדכון?",
}

# כלים שדורשים אישור מפורש — ללא קשר לפרמטרים
_SENSITIVE_TOOLS = {"gmail_send_draft", "airtable_update", "airtable_add"}


# ══════════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════════

class ActionAllowed:
    """הפעולה עברה validation — אפשר לבצע."""
    pass

class ActionBlocked:
    """הפעולה נחסמה — reason הוא מה להחזיר למשתמש."""
    def __init__(self, reason: str):
        self.reason = reason

    def __str__(self) -> str:
        return self.reason


# ══════════════════════════════════════════════════
# Main Validator
# ══════════════════════════════════════════════════

def validate_action(tool_name: str, inputs: dict) -> ActionAllowed | ActionBlocked:
    """
    Gate לפני dispatch_tool.

    בודק:
    1. כלי מוכר?
    2. פרמטרים חובה — כולם קיימים ולא ריקים?
    3. כלי רגיש — סומן להמתנה (event_bus מטפל באישור)

    מחזיר ActionAllowed או ActionBlocked עם הודעה למשתמש.
    """
    # כלי לא מוכר — dispatcher יטפל בזה, לא כאן
    required = _REQUIRED.get(tool_name)
    if required is None:
        logger.warning(f"validate_action: unknown tool {tool_name}")
        return ActionAllowed()

    # בדוק פרמטרים חסרים
    missing = [
        field for field in required
        if inputs.get(field) is None or inputs.get(field) == ""
        # dict/list ריקים ({}, []) — תקינים (Claude ימלא תוכן)
        # None ו-"" בלבד — חסרים אמיתיים
    ]

    if missing:
        # בנה שאלה ידידותית למשתמש
        questions = [
            _FIELD_QUESTIONS.get(f, f"חסר: {f}")
            for f in missing
        ]
        # שאלה אחת בלבד (הראשונה הכי חשובה)
        first_q = questions[0]
        extra = f" (חסרים עוד {len(questions)-1} פרטים)" if len(questions) > 1 else ""
        msg = f"{first_q}{extra}"

        logger.info(f"ActionBlocked: {tool_name} missing {missing}")
        return ActionBlocked(msg)

    # כלי רגיש — אישור מטופל ע"י event_bus (לא כאן)
    # רק לוגים — event_bus.needs_approval יחסום אם צריך
    if tool_name in _SENSITIVE_TOOLS:
        logger.info(f"validate_action: sensitive tool {tool_name} — approval via event_bus")

    return ActionAllowed()


# ══════════════════════════════════════════════════
# Test — python3 action_validator.py
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        ("gmail_draft",    {"to": "a@b.com", "subject": "נושא", "body": "גוף"},   "ALLOW"),
        ("gmail_draft",    {"subject": "נושא", "body": "גוף"},                     "BLOCK"),
        ("gmail_draft",    {"to": "", "subject": "נושא", "body": "גוף"},           "BLOCK"),
        ("airtable_update",{"table": "CRM", "record_id": "rec123", "fields": {}},  "ALLOW"),
        ("airtable_update",{"table": "CRM", "fields": {}},                         "BLOCK"),
        ("calendar_get_events", {},                                                  "ALLOW"),
        ("airtable_get",   {"table": "CRM"},                                        "ALLOW"),
        ("airtable_get",   {},                                                       "BLOCK"),
    ]

    print("=" * 55)
    print("ACTION VALIDATOR — בדיקות")
    print("=" * 55)
    all_pass = True
    for name, inputs, expected in tests:
        result = validate_action(name, inputs)
        actual = "ALLOW" if isinstance(result, ActionAllowed) else "BLOCK"
        ok = actual == expected
        if not ok:
            all_pass = False
        status = "✅" if ok else "❌"
        msg = f" | {result.reason}" if isinstance(result, ActionBlocked) else ""
        print(f"{status} {name:25} → {actual:5} (צפוי: {expected}){msg}")

    print("=" * 55)
    print(f"{'✅ כל הבדיקות עברו' if all_pass else '❌ יש כשלים'}")
