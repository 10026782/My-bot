# tools/schemas.py
# הגדרות כלים ל-Claude native tool_use

TOOL_SCHEMAS = [
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
        "name": "search_lead",
        "description": (
            "חיפוש ליד לפי שם חלקי בטבלת Leads. "
            "השתמש כשהמשתמש מבקש 'תחפש את הליד X' / 'מה הסטטוס של X' / 'תראה לי את הפרטים של X'. "
            "מחזיר שם, טלפון, סטטוס, ציון (score), ערוץ ומזהה הרשומה."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "שם הליד לחיפוש (חלקי או מלא)"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "get_daily_report",
        "description": (
            "דוח יומי מלא — לידים חמים, פולו-אפ להיום, משימות דחופות, "
            "עסקאות פתוחות, תשלומים קרובים, שינויים מאתמול. "
            "קרא כלי זה כשהמשתמש מבקש 'דוח יומי' / 'תן לי סיכום' / 'מה יש היום'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "search_business_memory",
        "description": (
            "חיפוש בזיכרון עסקי — 'מה סיכמנו עם ספק X?' / 'החלטות מהפגישה עם Y'. "
            "מחזיר תוצאות רלוונטיות מהיסטוריית השיחות."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "שאלת חיפוש"},
                "domain": {"type": "string", "description": "דומיין (אופציונלי)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "crm_mark_payment_paid",
        "description": (
            "סימון תשלום כ-'שולם' בטבלת התשלומים. "
            "השתמש כשהמשתמש מאשר שתשלום התקבל/בוצע — 'שלמו לי על X' / 'תשלום Y בוצע'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "string",
                    "description": "מזהה הרשומה בטבלת תשלומים (rec...)"
                }
            },
            "required": ["record_id"]
        }
    },
]

# ══════════════════════════════════════════════════
# CRM Tools — not yet fully implemented in dispatcher/registry.
# Hidden from Claude (not in TOOL_SCHEMAS) until ready.
# Kept in action_validator for defense-in-depth validation.
# ══════════════════════════════════════════════════

_CRM_SCHEMAS_HIDDEN = []
