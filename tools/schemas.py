TOOL_SCHEMAS = [
    {
        "name": "add_knowledge",
        "description": "הוספת עובדה לzero-shot memory של הבוט",
        "input_schema": {
            "type": "object",
            "properties": {"fact": {"type": "string"}},
            "required": ["fact"],
        },
    },
    # ─── Airtable ────────────────────────────────────────────────────────────
    {
        "name": "airtable_get",
        "description": "שליפת רשומות מ-Airtable. השתמש לקבלת משימות, עסקאות, לידים, מלאי.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table":          {"type": "string",  "description": "שם הטבלה"},
                "filter_formula": {"type": "string",  "description": "נוסחת סינון Airtable (אופציונלי)"},
                "max_records":    {"type": "integer", "description": "מקסימום רשומות (ברירת מחדל: 10)"},
            },
            "required": ["table"],
        },
    },
    {
        "name": "airtable_add",
        "description": "יצירת רשומה חדשה ב-Airtable.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table":  {"type": "string", "description": "שם הטבלה"},
                "fields": {"type": "object", "description": "שדות הרשומה החדשה"},
            },
            "required": ["table", "fields"],
        },
    },
    {
        "name": "airtable_update",
        "description": "עדכון רשומה קיימת ב-Airtable לפי record ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table":     {"type": "string", "description": "שם הטבלה"},
                "record_id": {"type": "string", "description": "ID הרשומה (rec...)"},
                "fields":    {"type": "object", "description": "שדות לעדכון"},
            },
            "required": ["table", "record_id", "fields"],
        },
    },
    # ─── Gmail ───────────────────────────────────────────────────────────────
    {
        "name": "gmail_draft",
        "description": "שמירת טיוטת מייל ב-Gmail — לא שולח ישירות! תמיד טיוטה, אסור לשלוח ישירות.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string"},
                "subject": {"type": "string"},
                "body":    {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "gmail_send_draft",
        "description": "שליחת טיוטה קיימת לפי draft ID (רק אחרי אישור מפורש).",
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "ה-ID של הטיוטה לשליחה"},
            },
            "required": ["draft_id"],
        },
    },
    {
        "name": "gmail_read",
        "description": "קריאת המיילים האחרונים מ-Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "כמות מיילים (ברירת מחדל: 5)"},
            },
            "required": [],
        },
    },
    # ─── Google Drive ─────────────────────────────────────────────────────────
    {
        "name": "search_drive",
        "description": "חיפוש קבצים ב-Google Drive לפי שם.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_drive_file",
        "description": "קריאת תוכן קובץ מ-Google Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string"},
            },
            "required": ["file_name"],
        },
    },
    # ─── Google Calendar ──────────────────────────────────────────────────────
    {
        "name": "calendar_get_events",
        "description": "שליפת אירועים קרובים מ-Google Calendar. השתמש לפני יצירת פגישה.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "כמות אירועים (ברירת מחדל: 5)"},
                "days_ahead":  {"type": "integer", "description": "כמה ימים קדימה (ברירת מחדל: 7)"},
            },
            "required": [],
        },
    },
    {
        "name": "calendar_create_event",
        "description": "קביעת פגישה ב-Google Calendar. בדוק calendar_get_events לפני.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary":          {"type": "string"},
                "start_time":       {"type": "string", "description": "ISO: 2025-06-01T14:00:00"},
                "duration_minutes": {"type": "integer"},
            },
            "required": ["summary", "start_time"],
        },
    },
    # ─── Google Sheets ────────────────────────────────────────────────────────
    {
        "name": "sheets_append",
        "description": "הוספת שורה לגוגל שיטס.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spreadsheet_name": {"type": "string", "description": "שם הקובץ בדרייב"},
                "row_data":         {"type": "array",  "description": "רשימת ערכים לשורה", "items": {"type": "string"}},
            },
            "required": ["spreadsheet_name", "row_data"],
        },
    },
]
