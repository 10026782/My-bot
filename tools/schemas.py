TOOL_SCHEMAS = [
    {
        "name": "add_knowledge",
        "description": "הוספת עובדה לzero-shot memory של הבוט (business_memory)",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "העובדה לשמירה"}
            },
            "required": ["fact"],
        },
    },
    {
        "name": "airtable_get_records",
        "description": (
            "שליפת רשומות מ-Airtable. השתמש כדי לקבל משימות, עסקאות, לידים, "
            "קשרי לקוחות, מלאי — כל מידע שמור ב-Airtable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "שם הטבלה ב-Airtable (למשל: Tasks, Leads, Deals)",
                },
                "filter_formula": {
                    "type": "string",
                    "description": "נוסחת סינון אופציונלית בפורמט Airtable (למשל: {Status}='Open')",
                },
                "max_records": {
                    "type": "integer",
                    "description": "מקסימום רשומות לשליפה (ברירת מחדל: 10)",
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "airtable_create_record",
        "description": "יצירת רשומה חדשה ב-Airtable (משימה, ליד, עסקה וכו').",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "שם הטבלה ב-Airtable",
                },
                "fields": {
                    "type": "object",
                    "description": "שדות הרשומה החדשה — מפתח: שם שדה, ערך: תוכן",
                },
            },
            "required": ["table", "fields"],
        },
    },
    {
        "name": "gmail_send",
        "description": "שמירת טיוטת מייל ב-Gmail — לא שולח ישירות! תמיד צור טיוטה ואמור למשתמש שהיא ממתינה לאישורו.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "כתובת המייל של הנמען"},
                "subject": {"type": "string", "description": "נושא המייל"},
                "body":    {"type": "string", "description": "תוכן המייל"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "gmail_read",
        "description": "קריאת המיילים האחרונים מ-Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "כמות מיילים לשליפה (ברירת מחדל: 5)"},
            },
            "required": [],
        },
    },
    {
        "name": "drive_search",
        "description": "חיפוש קבצים ב-Google Drive לפי שם.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "מה לחפש בשם הקובץ"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "drive_read_file",
        "description": "קריאת תוכן קובץ מ-Google Drive (Docs, טקסט, וכו').",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "שם הקובץ לקריאה"},
            },
            "required": ["file_name"],
        },
    },
    {
        "name": "calendar_create_event",
        "description": "קביעת פגישה או אירוע ב-Google Calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary":          {"type": "string", "description": "שם הפגישה/אירוע"},
                "start_time":       {"type": "string", "description": "תאריך ושעה ב-ISO: 2025-06-01T14:00:00"},
                "duration_minutes": {"type": "integer", "description": "משך בדקות (ברירת מחדל: 60)"},
            },
            "required": ["summary", "start_time"],
        },
    },
    {
        "name": "airtable_update_record",
        "description": "עדכון רשומה קיימת ב-Airtable לפי record ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "שם הטבלה ב-Airtable",
                },
                "record_id": {
                    "type": "string",
                    "description": "ה-ID של הרשומה לעדכון (מתחיל ב-rec...)",
                },
                "fields": {
                    "type": "object",
                    "description": "השדות לעדכון — רק שדות שצריך לשנות",
                },
            },
            "required": ["table", "record_id", "fields"],
        },
    },
]
