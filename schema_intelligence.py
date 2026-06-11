# schema_intelligence.py — A38 Schema Intelligence Layer
# Source of Truth: airtable_schema.py
# מטרה: לפני כל כתיבה לAirtable — אמת שדות, הצע תיקונים

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# Schema Registry — טוען מ-airtable_schema.py
# ══════════════════════════════════════════════════

SCHEMA: dict[str, dict] = {
    "משימות (Tasks)": {
        "כותרת המשימה": {"type": "text",   "required": True},
        "תיאור":         {"type": "long",   "required": False},
        "תאריך יעד":     {"type": "date",   "required": False, "format": "YYYY-MM-DD"},
        "סטטוס":         {"type": "select", "required": False,
                          "options": ["ממתין", "בביצוע", "בוצע"]},
        "מקושר לאנשי קשר": {"type": "link", "required": False},
        "מקושר לעסקאות":   {"type": "link", "required": False},
    },
    "משימות ודד ליינים": {
        "שם המשימה":     {"type": "text",   "required": True},
        "סטטוס":         {"type": "select", "required": False,
                          "options": ["לא התחיל", "בתהליך", "הושלם"]},
        "תאריך דדליין":  {"type": "date",   "required": False, "format": "YYYY-MM-DD"},
        "אחראי":         {"type": "text",   "required": False},
        "תיאור המשימה":  {"type": "long",   "required": False},
        "עדיפות":        {"type": "select", "required": False,
                          "options": ["גבוהה", "בינונית", "נמוכה"]},
        "הערות":         {"type": "long",   "required": False},
    },
    "אנשי קשר (Contacts)": {
        "שם":            {"type": "text",   "required": True},
        "חברה":          {"type": "text",   "required": False},
        "אימייל":        {"type": "email",  "required": False},
        "טלפון":         {"type": "phone",  "required": False},
        "תאריך פולו אפ": {"type": "date",   "required": False},
        "סטטוס":         {"type": "select", "required": False,
                          "options": ["חדש", "בתהליכים", "פולו-אפ", "לא רלוונטי"]},
    },
    "עסקאות (Deals)": {
        "שם העסקה":      {"type": "text",   "required": True},
        "סכום":          {"type": "currency","required": False},
        "שלב":           {"type": "select", "required": False,
                          "options": ["הזדמנות", "במשא ומתן", "סגור-ניצחון", "סגור-הפסד"]},
        "תאריך סגירה":   {"type": "date",   "required": False},
    },
    "תשלומים (Payments)": {
        "אסמכתא":        {"type": "text",   "required": True},
        "סכום":          {"type": "currency","required": True},
        "תאריך":         {"type": "date",   "required": False},
        "סטטוס":         {"type": "select", "required": False,
                          "options": ["התקבל", "בתהליך", "בוטל"]},
    },
    "הוצאות (Expenses)": {
        "שם ההוצאה":     {"type": "text",   "required": True},
        "סכום":          {"type": "currency","required": True},
        "קטגוריה":       {"type": "select", "required": False,
                          "options": ["שיווק", "משרד", "נסיעות", "תפעול", "אחר"]},
        "תאריך":         {"type": "date",   "required": False},
    },
    "Leads": {
        "Name":          {"type": "text",   "required": True},
        "phone":         {"type": "text",   "required": False},
        "status":        {"type": "text",   "required": False,
                          "options": ["new", "qualified", "hot", "cold", "converted",
                                      "NEW", "QUALIFIED", "HOT", "COLD"]},
        "score":         {"type": "number", "required": False},
        "tier":          {"type": "text",   "required": False,
                          "options": ["HOT", "WARM", "COLD"]},
        "summary":       {"type": "long",   "required": False},
        "answers":       {"type": "long",   "required": False},
        "domain":        {"type": "text",   "required": False,
                          "options": ["real_estate", "import", "recruitment", "saas",
                                      "finance", "general"]},
        "channel":       {"type": "text",   "required": False},
        "source":        {"type": "text",   "required": False},
        "created_at":    {"type": "text",   "required": False},
        "memory_key":    {"type": "text",   "required": False},
        "tenant_id":     {"type": "text",   "required": False},
        "updated_at":    {"type": "text",   "required": False},
        "converted_at":  {"type": "text",   "required": False},
    },
    "Projects": {
        "Project Name":  {"type": "text",   "required": True},
        "Location":      {"type": "text",   "required": False},
        "Status":        {"type": "select", "required": False,
                          "options": ["Planning","Active","Completed","On Hold","Cancelled","In Progress"]},
        "Total Units":   {"type": "number", "required": False},
        "Start Date":    {"type": "date",   "required": False},
        "End Date":      {"type": "date",   "required": False},
        "Notes":         {"type": "long",   "required": False},
    },
    "למידות ותובנות": {
        "כותרת התובנה":  {"type": "text",   "required": True},
        "תיאור":         {"type": "long",   "required": False},
        "תאריך יצירה":   {"type": "date",   "required": False},
    },
    "Roadmap_Tasks": {
        "Task":             {"type": "text",   "required": True},
        "World":            {"type": "link",   "required": False, "linked_table": "Worlds"},
        "Quest":            {"type": "link",   "required": False, "linked_table": "Quests"},
        "Owner":            {"type": "select", "required": False,
                             "options": ["אליהו", "קלוד קוד", "אורי", "אהרן", "אח"]},
        "Priority":         {"type": "select", "required": False,
                             "options": ["P0", "P1", "P2", "P3"]},
        "Status":           {"type": "select", "required": False,
                             "options": ["Todo", "In Progress", "Done", "Blocked"]},
        "Due_Date":         {"type": "date",   "required": False, "format": "YYYY-MM-DD"},
        "Estimated_Hours":  {"type": "number", "required": False},
        "Coins":            {"type": "number", "required": False},
        "Blocker":          {"type": "bool",   "required": False},
        "Notes":            {"type": "long",   "required": False},
    },
    "Weekly_Goals": {
        "Goal":        {"type": "text",   "required": True},
        "World":       {"type": "link",   "required": False, "linked_table": "Worlds"},
        "Target_Date": {"type": "date",   "required": False, "format": "YYYY-MM-DD"},
        "Status":      {"type": "select", "required": False,
                        "options": ["Todo", "Done", "Missed"]},
    },
    "Boss_Battles": {
        "Week":         {"type": "text",   "required": False},
        "Week_Start":   {"type": "date",   "required": False, "format": "YYYY-MM-DD"},
        "Question":     {"type": "long",   "required": False},
        "Answer":       {"type": "long",   "required": False},
        "Status":       {"type": "select", "required": False,
                         "options": ["Boss Defeated", "Boss Won"]},
        "Coins_Earned": {"type": "number", "required": False},
    },
}

# שמות קצרים → שמות מלאים (לחיפוש חכם)
TABLE_ALIASES: dict[str, str] = {
    "tasks":        "משימות (Tasks)",
    "משימות":       "משימות (Tasks)",
    "deadlines":    "משימות ודד ליינים",
    "ודד":          "משימות ודד ליינים",
    "דדליינים":     "משימות ודד ליינים",
    "contacts":     "אנשי קשר (Contacts)",
    "אנשי קשר":    "אנשי קשר (Contacts)",
    "קשר":          "אנשי קשר (Contacts)",
    "deals":        "עסקאות (Deals)",
    "עסקאות":       "עסקאות (Deals)",
    "payments":     "תשלומים (Payments)",
    "תשלומים":      "תשלומים (Payments)",
    "expenses":     "הוצאות (Expenses)",
    "הוצאות":       "הוצאות (Expenses)",
    "leads":        "Leads",
    "לידים":        "Leads",
    "projects":     "Projects",
    "פרויקטים":     "Projects",
    "learnings":    "למידות ותובנות",
    "תובנות":       "למידות ותובנות",
    "roadmap":      "Roadmap_Tasks",
    "roadmap_tasks":"Roadmap_Tasks",
    "weekly_goals": "Weekly_Goals",
    "boss_battles": "Boss_Battles",
}


# ══════════════════════════════════════════════════
# Core Functions
# ══════════════════════════════════════════════════

def resolve_table(name: str) -> str | None:
    """מחזיר שם טבלה מלא — תומך בכינויים."""
    n = name.strip().lower()
    if n in TABLE_ALIASES:
        return TABLE_ALIASES[n]
    # exact match
    for t in SCHEMA:
        if t.lower() == n:
            return t
    return None


def validate_fields(table: str, fields: dict) -> tuple[bool, str]:
    """
    מאמת שדות לפני כתיבה לAirtable.
    מחזיר (ok, message).
    אם שדה לא קיים — מציע תיקון.
    """
    full_table = resolve_table(table) or table
    schema = SCHEMA.get(full_table)

    if not schema:
        logger.warning(f"[Schema] Unknown table: {table}")
        return True, ""  # טבלה לא מוכרת — תן לעבור

    errors = []
    for field, value in fields.items():
        if field not in schema:
            suggestion = _find_similar(field, list(schema.keys()))
            if suggestion:
                errors.append(
                    f"השדה \"{field}\" לא קיים ב-{full_table}.\n"
                    f"האם התכוונת ל-\"{suggestion}\"?"
                )
            else:
                errors.append(
                    f"השדה \"{field}\" לא קיים ב-{full_table}.\n"
                    f"השדות הזמינים: {', '.join(list(schema.keys())[:5])}"
                )

        # בדיקת ערכי select
        elif schema[field].get("options") and value:
            opts = schema[field]["options"]
            if str(value) not in opts:
                errors.append(
                    f"הערך \"{value}\" לא חוקי לשדה \"{field}\".\n"
                    f"ערכים מותרים: {', '.join(opts)}"
                )

    if errors:
        return False, "\n".join(errors)
    return True, ""


def format_table_schema(table: str) -> str:
    """פורמט סכמה לתצוגה בטלגרם — לפקודת /schema."""
    full_table = resolve_table(table) or table
    schema = SCHEMA.get(full_table)

    if not schema:
        available = "\n".join(f"• {t}" for t in SCHEMA.keys())
        return f"❌ טבלה \"{table}\" לא נמצאה.\n\nטבלאות זמינות:\n{available}"

    lines = [f"📋 *{full_table}*\n"]
    for field, meta in schema.items():
        type_str = meta.get("type", "")
        opts = meta.get("options", [])
        req = " ✱" if meta.get("required") else ""
        if opts:
            lines.append(f"• *{field}*{req} — {' | '.join(opts)}")
        else:
            lines.append(f"• *{field}*{req} — {type_str}")
    return "\n".join(lines)


def format_all_tables() -> str:
    """רשימת כל הטבלאות — לפקודת /tables."""
    lines = [f"📊 *טבלאות Airtable — {len(SCHEMA)} טבלאות*\n"]
    for table in SCHEMA:
        fields = list(SCHEMA[table].keys())
        lines.append(f"*{table}*")
        lines.append(f"  {', '.join(fields[:4])}{'...' if len(fields)>4 else ''}")
    return "\n".join(lines)


# ── Utils ─────────────────────────────────────────

def _find_similar(field: str, candidates: list[str]) -> str | None:
    """מוצא שדה דומה — fuzzy match פשוט."""
    field_l = field.lower()
    for c in candidates:
        if field_l in c.lower() or c.lower() in field_l:
            return c
    # common mistakes
    TYPOS = {
        "name": ["שם", "שם המשימה", "כותרת המשימה", "Name"],
        "title": ["כותרת המשימה", "שם המשימה"],
        "status": ["סטטוס", "Status", "שלב"],
        "date": ["תאריך", "תאריך יעד", "תאריך דדליין"],
        "priority": ["עדיפות"],
        "notes": ["הערות", "תיאור", "Notes"],
        "deadline": ["תאריך דדליין", "תאריך יעד"],
    }
    for typo, fixes in TYPOS.items():
        if typo in field_l:
            for fix in fixes:
                if fix in candidates:
                    return fix
    return None


# ══════════════════════════════════════════════════
# Telegram Commands
# ══════════════════════════════════════════════════

def handle_schema_command(args: str) -> str:
    """
    /schema [טבלה]
    ללא args → רשימת כל הטבלאות
    עם args → סכמה של טבלה ספציפית
    """
    if not args.strip():
        return format_all_tables()
    return format_table_schema(args.strip())


# ══════════════════════════════════════════════════
# Integration — airtable_tools.py
# ══════════════════════════════════════════════════

def validate_before_write(table: str, fields: dict) -> tuple[bool, str]:
    """
    Entry point — קרא לפני כל airtable_add / airtable_update.
    
    שימוש ב-airtable_tools.py:
        from schema_intelligence import validate_before_write
        ok, err = validate_before_write(table, fields)
        if not ok:
            return f"❌ שגיאת סכמה: {err}"
    """
    return validate_fields(table, fields)


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    # resolve_table
    chk("resolve tasks HE",    resolve_table("משימות") == "משימות (Tasks)")
    chk("resolve tasks EN",    resolve_table("tasks")   == "משימות (Tasks)")
    chk("resolve contacts",    resolve_table("קשר")     == "אנשי קשר (Contacts)")
    chk("resolve leads",       resolve_table("לידים")   == "Leads")
    chk("resolve deadlines",   resolve_table("ודד")     == "משימות ודד ליינים")
    chk("unknown → None",      resolve_table("banana")  is None)

    # validate_fields — valid
    ok, err = validate_fields("משימות", {"כותרת המשימה": "בדיקה", "סטטוס": "ממתין"})
    chk("valid fields → ok",   ok is True)
    chk("valid fields → no err", err == "")

    # validate_fields — wrong field name
    ok, err = validate_fields("משימות", {"Name": "test"})
    chk("wrong field → not ok",  ok is False)
    chk("suggests כותרת המשימה", "כותרת המשימה" in err)

    # validate_fields — wrong select value
    ok, err = validate_fields("משימות", {"סטטוס": "Active"})
    chk("wrong select → not ok", ok is False)
    chk("shows valid options",    "ממתין" in err)

    # validate_fields — unknown table → pass through
    ok, err = validate_fields("UnknownTable", {"field": "val"})
    chk("unknown table → ok",    ok is True)

    # validate_fields — Deals
    ok, err = validate_fields("עסקאות", {"שלב": "Active"})
    chk("Deals wrong stage",      ok is False)
    ok, err = validate_fields("עסקאות", {"שלב": "במשא ומתן"})
    chk("Deals correct stage",    ok is True)

    # format_table_schema
    fmt = format_table_schema("משימות")
    chk("format has table name",  "משימות (Tasks)" in fmt)
    chk("format has כותרת",       "כותרת המשימה" in fmt)
    chk("format has status opts", "ממתין" in fmt)

    fmt_bad = format_table_schema("banana")
    chk("unknown table shows list", "Leads" in fmt_bad)

    # format_all_tables
    all_t = format_all_tables()
    chk("all tables has tables",   "Roadmap_Tasks" in all_t and "Boss_Battles" in all_t)

    # handle_schema_command
    r1 = handle_schema_command("")
    chk("empty → all tables",     "Leads" in r1)
    r2 = handle_schema_command("tasks")
    chk("tasks → schema",         "כותרת המשימה" in r2)

    print(f"\n{'='*40}")
    print(f"A38 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok = _run_tests()
    if ok:
        print("\n" + "─"*40)
        print("SAMPLE /schema משימות:")
        print(format_table_schema("משימות"))
        print("\n" + "─"*40)
        print("SAMPLE validate wrong field:")
        _, err = validate_fields("משימות", {"Name": "test", "סטטוס": "Active"})
        print(err)
    exit(0 if ok else 1)
