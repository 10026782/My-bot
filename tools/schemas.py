# tools/schemas.py
# הגדרות כלים ל-Claude native tool_use

TOOL_SCHEMAS = [
    {
        "name": "search_drive",
        "description": "חיפוש קבצים ב-Google Drive לפי שם",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "שם הקובץ או מילת חיפוש"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_drive_file",
        "description": "קריאת תוכן קובץ מ-Google Drive",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "שם הקובץ לקריאה"}
            },
            "required": ["file_name"]
        }
    },
    {
        "name": "calendar_get_events",
        "description": "קריאת אירועים מ-Google Calendar",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "כמה ימים קדימה (ברירת מחדל: 7)"}
            }
        }
    },
    {
        "name": "calendar_create_event",
        "description": "יצירת אירוע ב-Google Calendar. בודק חפיפות אוטומטית — אם יש, מחזיר ⚠️ ושואל. לקבוע בכל זאת → force=true.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary":          {"type": "string",  "description": "כותרת הפגישה"},
                "start_time":       {"type": "string",  "description": "ISO 8601: YYYY-MM-DDTHH:MM:SS"},
                "duration_minutes": {"type": "integer", "description": "משך בדקות (ברירת מחדל: 60)"},
                "force":            {"type": "boolean", "description": "true = קבע גם אם יש חפיפה ביומן"}
            },
            "required": ["summary", "start_time"]
        }
    },
    {
        "name": "gmail_draft",
        "description": "יצירת טיוטת מייל — לעולם אל תשלח ישירות",
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "כתובת הנמען"},
                "subject": {"type": "string", "description": "נושא"},
                "body":    {"type": "string", "description": "גוף המייל"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "gmail_send_draft",
        "description": "שליחת טיוטה קיימת לאחר אישור המשתמש",
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "מזהה הטיוטה לשליחה"}
            },
            "required": ["draft_id"]
        }
    },
    {
        "name": "gmail_read",
        "description": "קריאת מיילים אחרונים מהתיבה",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "מספר מיילים (ברירת מחדל: 3)"}
            }
        }
    },
    {
        "name": "sheets_append",
        "description": "הוספת שורה ל-Google Sheets",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string", "description": "שם הגיליון ב-Drive"},
                "row_data":   {"type": "array",  "items": {"type": "string"}}
            },
            "required": ["sheet_name", "row_data"]
        }
    },
    {
        "name": "airtable_get",
        "description": "שליפת רשומות מ-Airtable",
        "input_schema": {
            "type": "object",
            "properties": {
                "table":  {"type": "string", "description": "שם הטבלה"},
                "filter": {"type": "string", "description": "filterByFormula (אופציונלי)"}
            },
            "required": ["table"]
        }
    },
    {
        "name": "airtable_add",
        "description": "הוספת רשומה חדשה ל-Airtable",
        "input_schema": {
            "type": "object",
            "properties": {
                "table":  {"type": "string", "description": "שם הטבלה"},
                "fields": {"type": "object", "description": "שדות הרשומה"}
            },
            "required": ["table", "fields"]
        }
    },
    {
        "name": "airtable_update",
        "description": "עדכון רשומה קיימת ב-Airtable",
        "input_schema": {
            "type": "object",
            "properties": {
                "table":     {"type": "string", "description": "שם הטבלה"},
                "record_id": {"type": "string", "description": "מזהה הרשומה (rec...)"},
                "fields":    {"type": "object", "description": "שדות לעדכון"}
            },
            "required": ["table", "record_id", "fields"]
        }
    },
    {
        "name": "airtable_get_schema",
        "description": "קריאת כל הטבלאות והשדות מ-Airtable בזמן אמת. השתמש בכלי זה לפני כל פעולה על טבלה שאינך בטוח בשמה המדויק.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "resolve_contact",
        "description": (
            "חיפוש איש קשר לפי שם (fuzzy). "
            "השתמש כשהמשתמש כותב 'שלח מייל לדניאל' / 'תזמן פגישה עם רחל'. "
            "מחזיר פרטי קשר (מייל, טלפון, ID) אם נמצא קשר ברור, "
            "או רשימת אפשרויות לבחירה אם יש כפילות."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name_query": {
                    "type": "string",
                    "description": "שם איש הקשר לחיפוש (חלקי או מלא)"
                }
            },
            "required": ["name_query"]
        }
    },
    {
        "name": "search_business_memory",
        "description": (
            "חיפוש בזיכרון העסקי. "
            "השתמש כשנשאלים 'מה סיכמנו עם X?' / 'מה הוחלט בפגישה עם Y?'. "
            "מחפש בשדה summary של טבלת Business Memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "מילות חיפוש"},
                "domain": {"type": "string", "description": "סינון לפי תחום (אופציונלי)"}
            },
            "required": ["query"]
        }
    },
]
