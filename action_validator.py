# action_validator.py — v2.0
# Gate לפני dispatch_tool — שלושה שלבים + חוק ה-9%:
# 1. UNKNOWN TOOL  — BLOCK קשיח
# 2. PRESENCE CHECK — פרמטרים חובה קיימים?
# 3. STRUCTURE CHECK — פורמט תקין + חוק ה-9%

from __future__ import annotations
import re
import logging

logger = logging.getLogger(__name__)

_REQUIRED: dict[str, list[str]] = {
    # Google
    "search_drive":              ["query"],
    "read_drive_file":           ["file_name"],
    "calendar_get_events":       [],
    "calendar_create_event":     ["summary", "start_time"],
    "gmail_draft":               ["to", "subject", "body"],
    "gmail_send_draft":          ["draft_id"],
    "gmail_read":                [],
    "sheets_append":             ["sheet_name", "row_data"],
    # Airtable Generic
    "airtable_get":              ["table"],
    "airtable_add":              ["table", "fields"],
    "airtable_update":           ["table", "record_id", "fields"],
    "airtable_get_schema":       [],
    # CRM - Contacts
    "crm_add_contact":           ["name"],
    "crm_find_contact":          ["query"],
    "crm_list_contacts":         [],
    "crm_update_last_contact":   ["record_id"],
    # CRM - Deals
    "crm_add_deal":              ["name", "address", "price", "funding_cost_pct"],
    "crm_update_deal_status":    ["record_id", "status"],
    "crm_list_deals":            [],
    # CRM - Payments
    "crm_add_payment":           ["name", "amount", "due_date"],
    "crm_upcoming_payments":     [],
    "crm_mark_payment_paid":     ["record_id"],
    "crm_overdue_payments":      [],
    # Knowledge
    "add_knowledge":             ["key", "value"],
    # Contact Resolver / Business Memory / Daily Report
    "resolve_contact":           ["name_query"],
    "search_business_memory":    ["query"],
    "get_daily_report":          [],
    # PR-0C — ActionGateway adapters (former event_bus custom actions)
    "media_save_to_memory":      ["transcript"],
    "send_followup":             ["chat_id"],
    "send_recovery":             ["chat_id"],
    # Phase 4B-2 wiring — TMA write-through-approval adapter. op/table
    # presence only; allowlist + op-specific shape (fields vs record_id) is
    # validated inside tools/approval_actions.py::tma_write() itself.
    "tma_write":                 ["op", "table"],
}

_FIELD_QUESTIONS: dict[str, str] = {
    "query": "מה לחפש?", "file_name": "מה שם הקובץ?",
    "summary": "מה כותרת הפגישה?", "start_time": "מתי? (YYYY-MM-DDTHH:MM:SS)",
    "to": "למי לשלוח?", "subject": "מה נושא המייל?", "body": "מה תוכן המייל?",
    "draft_id": "מה מזהה הטיוטה?", "sheet_name": "מה שם הגיליון?",
    "row_data": "מה הנתונים?", "table": "לאיזו טבלה?", "fields": "מה השדות?",
    "record_id": "מה מזהה הרשומה? (rec...)", "name": "מה השם?",
    "address": "מה הכתובת?", "price": "מה המחיר? (₪)",
    "funding_cost_pct": "מה עלות המימון? (%)", "status": "מה הסטטוס?",
    "amount": "מה הסכום? (₪)", "due_date": "מתי תאריך התשלום? (YYYY-MM-DD)",
    "key": "מה המפתח?", "value": "מה הערך?",
}

_SENSITIVE_TOOLS = {
    "gmail_send_draft", "airtable_update", "airtable_add",
    "crm_add_contact", "crm_add_deal", "crm_add_payment",
    "crm_update_deal_status", "crm_mark_payment_paid",
}

_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?([+-]\d{2}:?\d{2}|Z)?$")
_ISO_DATE_RE     = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_RE        = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RECORD_ID_RE    = re.compile(r"^rec[A-Za-z0-9]{14,}$")

_TOOLS_WITH_RECORD_ID = {
    "airtable_update", "crm_update_last_contact",
    "crm_update_deal_status", "crm_mark_payment_paid",
}

MAX_FUNDING_PCT = 9.0


class ActionAllowed:
    pass

class ActionBlocked:
    def __init__(self, reason: str):
        self.reason = reason
    def __str__(self) -> str:
        return self.reason


def _check_presence(tool_name: str, inputs: dict) -> list[str]:
    required = _REQUIRED.get(tool_name, [])
    return [f for f in required if inputs.get(f) is None or inputs.get(f) == ""]


def _check_structure(tool_name: str, inputs: dict) -> list[str]:
    errors = []

    if tool_name == "calendar_create_event":
        st = inputs.get("start_time", "")
        if st and not _ISO_DATETIME_RE.match(str(st)):
            errors.append(f"start_time '{st}' לא תקין — נדרש: YYYY-MM-DDTHH:MM:SS")

    if tool_name == "gmail_draft":
        to = inputs.get("to", "")
        if to and not _EMAIL_RE.match(str(to)):
            errors.append(f"כתובת מייל '{to}' לא תקינה")

    if tool_name in _TOOLS_WITH_RECORD_ID:
        rid = inputs.get("record_id", "")
        if rid and not _RECORD_ID_RE.match(str(rid)):
            errors.append(f"record_id '{rid}' לא תקין — חייב להתחיל ב-rec")

    if tool_name == "crm_add_payment":
        dd = inputs.get("due_date", "")
        if dd and not _ISO_DATE_RE.match(str(dd)):
            errors.append(f"due_date '{dd}' לא תקין — נדרש: YYYY-MM-DD")

    if tool_name == "crm_add_deal":
        pct = inputs.get("funding_cost_pct")
        if pct is not None:
            try:
                pct_float = float(pct)
                if pct_float > MAX_FUNDING_PCT:
                    errors.append(
                        f"🔴 חוק ברזל #1: עלות מימון {pct_float}% "
                        f"> {MAX_FUNDING_PCT}% המקסימום. "
                        "העסקה חסומה — נדרש אישור מפורש של אליהו."
                    )
            except (ValueError, TypeError):
                errors.append(f"funding_cost_pct '{pct}' חייב להיות מספר")

    return errors


def validate_action(tool_name: str, inputs: dict) -> ActionAllowed | ActionBlocked:
    """
    שלושה שלבים:
    1. Unknown tool → BLOCK קשיח
    2. Presence check → כל החסרים מוצגים מראש
    3. Structure check → פורמט תקין + חוק ה-9%
    """
    if tool_name not in _REQUIRED:
        logger.error(f"Unknown tool blocked: {tool_name}")
        return ActionBlocked(f"⚠️ כלי '{tool_name}' אינו מוכר במערכת.")

    missing = _check_presence(tool_name, inputs)
    if missing:
        questions = [_FIELD_QUESTIONS.get(f, f"חסר: {f}") for f in missing]
        msg = questions[0] if len(questions) == 1 else \
              f"חסרים {len(questions)} פרטים: " + " | ".join(f"({i+1}) {q}" for i, q in enumerate(questions))
        logger.info(f"ActionBlocked (presence): {tool_name} missing {missing}")
        return ActionBlocked(msg)

    struct_errors = _check_structure(tool_name, inputs)
    if struct_errors:
        msg = " | ".join(struct_errors)
        logger.info(f"ActionBlocked (structure): {tool_name}")
        return ActionBlocked(msg)

    if tool_name in _SENSITIVE_TOOLS:
        logger.info(f"validate_action: sensitive={tool_name}")

    return ActionAllowed()


def assert_schema_sync(tool_schemas: list[dict]) -> None:
    """בדיקה שכל כלי בschemas קיים גם ב-validator ולהיפך."""
    schema_names = {t["name"] for t in tool_schemas}
    missing_in_v = schema_names - set(_REQUIRED.keys())
    missing_in_s = set(_REQUIRED.keys()) - schema_names
    if missing_in_v: logger.warning(f"⚠️ לא ב-validator: {missing_in_v}")
    if missing_in_s: logger.warning(f"⚠️ לא ב-schemas: {missing_in_s}")


if __name__ == "__main__":
    tests = [
        ("gmail_draft",             {"to":"a@b.com","subject":"נושא","body":"גוף"},        "ALLOW", "gmail מלא"),
        ("gmail_draft",             {"subject":"נושא","body":"גוף"},                        "BLOCK", "gmail ללא to"),
        ("gmail_draft",             {"to":"לא-מייל","subject":"נושא","body":"גוף"},         "BLOCK", "gmail מייל לא תקין"),
        ("calendar_create_event",   {"summary":"פגישה","start_time":"2025-06-01T14:00:00"}, "ALLOW", "calendar ISO תקין"),
        ("calendar_create_event",   {"summary":"פגישה","start_time":"מחר ב-14"},            "BLOCK", "calendar ISO לא תקין"),
        ("calendar_get_events",     {},                                                      "ALLOW", "get_events ריק"),
        ("airtable_get",            {"table":"CRM"},                                        "ALLOW", "airtable_get תקין"),
        ("airtable_get",            {},                                                      "BLOCK", "airtable_get ללא table"),
        ("airtable_update",         {"table":"CRM","record_id":"rec1234567890123456","fields":{"x":1}}, "ALLOW", "update record_id תקין"),
        ("airtable_update",         {"table":"CRM","record_id":"WRONG","fields":{"x":1}},  "BLOCK", "update record_id לא תקין"),
        ("crm_add_contact",         {"name":"יוסי כהן"},                                   "ALLOW", "add_contact תקין"),
        ("crm_add_contact",         {},                                                      "BLOCK", "add_contact ללא name"),
        ("crm_find_contact",        {"query":"כהן"},                                        "ALLOW", "find_contact תקין"),
        ("crm_find_contact",        {},                                                      "BLOCK", "find_contact ללא query"),
        ("crm_list_contacts",       {},                                                      "ALLOW", "list_contacts ריק"),
        ("crm_update_last_contact", {"record_id":"rec1234567890123456"},                    "ALLOW", "update_last_contact תקין"),
        ("crm_update_last_contact", {"record_id":"WRONG"},                                  "BLOCK", "update_last_contact record_id רע"),
        ("crm_add_deal",            {"name":"דירה","address":"רח א","price":1500000,"funding_cost_pct":7.5}, "ALLOW", "deal תקין"),
        ("crm_add_deal",            {"name":"דירה","address":"רח א","price":1000000,"funding_cost_pct":10.0},"BLOCK", "deal מימון > 9%"),
        ("crm_add_deal",            {"address":"רח א","price":1000000,"funding_cost_pct":7},"BLOCK", "deal ללא name"),
        ("crm_update_deal_status",  {"record_id":"rec1234567890123456","status":"Active"},  "ALLOW", "update_deal תקין"),
        ("crm_list_deals",          {},                                                      "ALLOW", "list_deals ריק"),
        ("crm_add_payment",         {"name":"שכירות","amount":5000,"due_date":"2025-06-01"}, "ALLOW", "add_payment תקין"),
        ("crm_add_payment",         {"name":"שכירות","amount":5000,"due_date":"01/06/25"},  "BLOCK", "add_payment due_date לא ISO"),
        ("crm_add_payment",         {"name":"שכירות","due_date":"2025-06-01"},              "BLOCK", "add_payment ללא amount"),
        ("crm_upcoming_payments",   {},                                                      "ALLOW", "upcoming_payments ריק"),
        ("crm_mark_payment_paid",   {"record_id":"rec1234567890123456"},                    "ALLOW", "mark_paid תקין"),
        ("crm_overdue_payments",    {},                                                      "ALLOW", "overdue ריק"),
        ("add_knowledge",           {"key":"מפתח","value":"ערך"},                           "ALLOW", "add_knowledge תקין"),
        ("add_knowledge",           {"key":"מפתח"},                                          "BLOCK", "add_knowledge ללא value"),
        ("hack_tool",               {},                                                      "BLOCK", "כלי לא מוכר"),
        ("send_email",              {"to":"a@b.com"},                                        "BLOCK", "typo"),
    ]

    print("=" * 70)
    print("ACTION VALIDATOR v2.0 — בדיקות")
    print("=" * 70)
    passed = 0
    for tool, inputs, expected, label in tests:
        result = validate_action(tool, inputs)
        actual = "ALLOW" if isinstance(result, ActionAllowed) else "BLOCK"
        ok = actual == expected
        passed += ok
        icon = "✅" if ok else "❌"
        suffix = f" → {result.reason[:50]}" if isinstance(result, ActionBlocked) else ""
        print(f"{icon} {label:42} {actual:5}{suffix}")
    print("=" * 70)
    total = len(tests)
    print(f"{'✅ כל הבדיקות עברו' if passed == total else f'❌ {passed}/{total} עברו'}")
