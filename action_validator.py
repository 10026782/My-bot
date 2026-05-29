# action_validator.py — v1.1
# Gate לפני dispatch_tool — שלושה שלבים:
# 1. PRESENCE CHECK  — פרמטרים חובה קיימים?
# 2. STRUCTURE CHECK — פורמט תקין? (ISO datetime וכו')
# 3. Unknown tool    — BLOCK קשיח (לא ALLOW שקט)
#
# UX: מציג את כל החסרים מראש — מוריד round-trips

from __future__ import annotations
import re
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Required fields — נגזר מ-schemas.py
# ══════════════════════════════════════════════════

_REQUIRED: dict[str, list[str]] = {
    "add_knowledge":           ["fact"],
    "search_drive":            ["query"],
    "read_drive_file":         ["file_name"],
    "calendar_get_events":     [],
    "calendar_create_event":   ["summary", "start_time"],
    "gmail_draft":             ["to", "subject", "body"],
    "gmail_send_draft":        ["draft_id"],
    "gmail_read":              [],
    "sheets_append":           ["sheet_name", "row_data"],
    "airtable_get":            ["table"],
    "airtable_add":            ["table", "fields"],
    "airtable_update":         ["table", "record_id", "fields"],
    # ─── CRM — אנשי קשר ──────────────────────────
    "crm_add_contact":         ["name"],
    "crm_find_contact":        ["query"],
    "crm_list_contacts":       [],
    "crm_update_last_contact": ["record_id"],
    # ─── CRM — עסקאות ────────────────────────────
    "crm_add_deal":            ["name", "address", "price", "funding_cost_pct"],
    "crm_list_deals":          [],
    "crm_update_deal_status":  ["record_id", "status"],
    # ─── CRM — תשלומים ───────────────────────────
    "crm_add_payment":         ["name", "amount", "due_date"],
    "crm_upcoming_payments":   [],
    "crm_overdue_payments":    [],
    "crm_mark_payment_paid":   ["record_id"],
}

_FIELD_QUESTIONS: dict[str, str] = {
    "query":            "מה לחפש?",
    "file_name":        "מה שם הקובץ לקריאה?",
    "summary":          "מה כותרת הפגישה?",
    "start_time":       "מתי הפגישה? (פורמט: YYYY-MM-DDTHH:MM:SS)",
    "to":               "למי לשלוח את המייל?",
    "subject":          "מה נושא המייל?",
    "body":             "מה תוכן המייל?",
    "draft_id":         "מה מזהה הטיוטה לשליחה?",
    "sheet_name":       "מה שם הגיליון?",
    "row_data":         "מה הנתונים להוספה?",
    "table":            "לאיזו טבלה? (Contacts / Deals / Payments)",
    "fields":           "מה השדות לעדכון?",
    "record_id":        "מה מזהה הרשומה? (מתחיל ב-rec...)",
    "fact":             "מה העובדה לשמירה?",
    # CRM
    "name":             "מה השם?",
    "contact_type":     "מה סוג איש הקשר? (Client / Supplier / Partner / Other)",
    "address":          "מה כתובת הנכס?",
    "price":            "מה מחיר הנכס (₪)?",
    "funding_cost_pct": "מה עלות המימון (%)? מקסימום 9%",
    "amount":           "מה סכום התשלום (₪)?",
    "due_date":         "מה תאריך התשלום? (YYYY-MM-DD)",
    "status":           "מה הסטטוס החדש?",
}

_SENSITIVE_TOOLS = {"gmail_send_draft", "airtable_update", "airtable_add", "crm_mark_payment_paid"}

# כלים עם record_id — חייב להתחיל ב-rec
_RECORD_ID_TOOLS = {
    "airtable_update", "crm_update_last_contact",
    "crm_update_deal_status", "crm_mark_payment_paid",
}

# ISO 8601 datetime — YYYY-MM-DDTHH:MM:SS (עם וריאנטים נפוצים)
_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?([+-]\d{2}:?\d{2}|Z)?$"
)

# כתובת מייל בסיסית
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ══════════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════════

class ActionAllowed:
    pass

class ActionBlocked:
    def __init__(self, reason: str):
        self.reason = reason
    def __str__(self) -> str:
        return self.reason


# ══════════════════════════════════════════════════
# STEP 1 — Presence Check
# ══════════════════════════════════════════════════

def _check_presence(tool_name: str, inputs: dict) -> list[str]:
    """מחזיר רשימת שדות חסרים (ריקים או None)."""
    required = _REQUIRED.get(tool_name, [])
    return [
        field for field in required
        if inputs.get(field) is None or inputs.get(field) == ""
        # dict/list ריקים ({}, []) — תקינים, Claude ימלא תוכן
    ]


# ══════════════════════════════════════════════════
# STEP 2 — Structure Check
# פורמט נתונים — לא רק שהשדה קיים
# ══════════════════════════════════════════════════

def _check_structure(tool_name: str, inputs: dict) -> list[str]:
    """
    מחזיר רשימת שגיאות פורמט.
    רק שדות שכבר קיימים (presence check קדם).
    """
    errors = []

    # calendar_create_event: start_time חייב להיות ISO datetime
    if tool_name == "calendar_create_event":
        st = inputs.get("start_time", "")
        if st and not _ISO_DATETIME_RE.match(str(st)):
            errors.append(
                f"start_time '{st}' אינו פורמט תקין. "
                "נדרש: YYYY-MM-DDTHH:MM:SS (למשל 2025-06-01T14:00:00)"
            )

    # gmail_draft: to חייב להיות כתובת מייל תקינה
    if tool_name == "gmail_draft":
        to = inputs.get("to", "")
        if to and not _EMAIL_RE.match(str(to)):
            errors.append(
                f"כתובת המייל '{to}' אינה תקינה. "
                "נדרש: name@domain.com"
            )

    # כלים עם record_id — חייב להתחיל ב-rec
    if tool_name in _RECORD_ID_TOOLS:
        rid = inputs.get("record_id", "")
        if rid and not str(rid).startswith("rec"):
            errors.append(
                f"record_id '{rid}' אינו תקין. "
                "מזהה Airtable תמיד מתחיל ב-rec (למשל recXXXXXXXXXXXXXX)"
            )

    # crm_add_deal: חוק ברזל — מימון >9% חסום
    if tool_name == "crm_add_deal":
        pct = inputs.get("funding_cost_pct")
        if pct is not None:
            try:
                if float(pct) > 9:
                    errors.append(
                        f"funding_cost_pct {pct}% חורג מהמותר. "
                        "🔴 חוק ברזל: מימון >9% חסום אוטומטית."
                    )
            except (ValueError, TypeError):
                errors.append(f"funding_cost_pct '{pct}' אינו מספר תקין.")

    return errors


# ══════════════════════════════════════════════════
# Main Validator
# ══════════════════════════════════════════════════

def validate_action(tool_name: str, inputs: dict) -> ActionAllowed | ActionBlocked:
    """
    שלושה שלבים:
    1. Unknown tool → BLOCK קשיח (לא ALLOW שקט)
    2. Presence check → כל החסרים מוצגים מראש
    3. Structure check → פורמט תקין?

    UX: מציג את כל החסרים — מוריד round-trips.
    """

    # ── שלב 0: כלי לא מוכר → BLOCK קשיח ─────────
    # ALLOW שקט = דלת פתוחה ל-typo injection
    if tool_name not in _REQUIRED:
        logger.error(f"Unknown tool blocked: {tool_name}")
        return ActionBlocked(f"⚠️ כלי '{tool_name}' אינו מוכר במערכת. אנא פנה לתמיכה.")

    # ── שלב 1: Presence check ─────────────────────
    missing = _check_presence(tool_name, inputs)
    if missing:
        questions = [_FIELD_QUESTIONS.get(f, f"חסר: {f}") for f in missing]
        if len(questions) == 1:
            msg = questions[0]
        else:
            # הצג את כל החסרים — מוריד round-trips
            all_q  = " | ".join(f"({i+1}) {q}" for i, q in enumerate(questions))
            msg = f"חסרים {len(questions)} פרטים: {all_q}"
        logger.info(f"ActionBlocked (presence): {tool_name} missing {missing}")
        return ActionBlocked(msg)

    # ── שלב 2: Structure check ────────────────────
    struct_errors = _check_structure(tool_name, inputs)
    if struct_errors:
        msg = " | ".join(struct_errors)
        logger.info(f"ActionBlocked (structure): {tool_name} — {msg}")
        return ActionBlocked(msg)

    # ── כלים רגישים: רק log — event_bus מטפל באישור
    if tool_name in _SENSITIVE_TOOLS:
        logger.info(f"validate_action: sensitive tool {tool_name} → approval via event_bus")

    return ActionAllowed()


# ══════════════════════════════════════════════════
# Tests — python3 action_validator.py
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # (tool, inputs, expected, label)
        # ── Presence ──────────────────────────────
        ("gmail_draft",    {"to":"a@b.com","subject":"נושא","body":"גוף"},        "ALLOW", "gmail מלא"),
        ("gmail_draft",    {"subject":"נושא","body":"גוף"},                        "BLOCK", "gmail ללא to"),
        ("gmail_draft",    {"to":"","subject":"נושא","body":"גוף"},                "BLOCK", "gmail to ריק"),
        ("airtable_update",{"table":"CRM","record_id":"rec123","fields":{"x":1}},  "ALLOW", "update מלא"),
        ("airtable_update",{"table":"CRM","fields":{"x":1}},                       "BLOCK", "update ללא record_id"),
        ("airtable_update",{"table":"CRM","record_id":"rec1","fields":{}},          "ALLOW", "update fields ריק"),
        ("calendar_get_events", {},                                                  "ALLOW", "get_events ריק"),
        ("airtable_get",   {"table":"CRM"},                                         "ALLOW", "get עם table"),
        ("airtable_get",   {},                                                       "BLOCK", "get ללא table"),
        # ── Structure ─────────────────────────────
        ("calendar_create_event",{"summary":"פגישה","start_time":"2025-06-01T14:00:00"},"ALLOW","calendar ISO תקין"),
        ("calendar_create_event",{"summary":"פגישה","start_time":"מחר ב-14"},            "BLOCK","calendar start_time לא ISO"),
        ("gmail_draft",    {"to":"לא-מייל","subject":"נושא","body":"גוף"},          "BLOCK", "gmail to לא מייל"),
        ("airtable_update",{"table":"CRM","record_id":"rec123","fields":{"x":1}},   "ALLOW", "update record_id תקין"),
        ("airtable_update",{"table":"CRM","record_id":"WRONG_ID","fields":{"x":1}},"BLOCK", "update record_id לא rec"),
        # ── Unknown tool ──────────────────────────
        ("hack_tool",      {},                                                       "BLOCK", "כלי לא מוכר"),
        ("send_email",     {"to":"a@b.com"},                                        "BLOCK", "typo — לא בschema"),
    ]

    print("=" * 65)
    print("ACTION VALIDATOR v1.1 — בדיקות")
    print("=" * 65)
    passed = 0
    for tool, inputs, expected, label in tests:
        result = validate_action(tool, inputs)
        actual = "ALLOW" if isinstance(result, ActionAllowed) else "BLOCK"
        ok = actual == expected
        passed += ok
        icon = "✅" if ok else "❌"
        suffix = f" → {result.reason[:55]}" if isinstance(result, ActionBlocked) else ""
        print(f"{icon} {label:35} {actual:5}{suffix}")

    print("=" * 65)
    print(f"{'✅ כל הבדיקות עברו' if passed == len(tests) else f'❌ {passed}/{len(tests)} עברו'}")
