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
        "description": "הוספת שורה ל-Google Sheets. ליצירת משימה עדיף להשתמש ב-airtable_add; אם נשלחת שורת Tasks דרך Sheets, היא חייבת להכיל כותרת בלבד או כותרת ותאריך יעד בפורמט YYYY-MM-DD בלבד.",
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
    {
        "name": "crm_create_deal",
        "description": (
            "יצירת עסקה (Deal) חדשה. השתמש כשהמשתמש מבקש לפתוח עסקה/הזדמנות חדשה "
            "— 'תפתח עסקה עם X' / 'יש לנו הזדמנות חדשה ב-Y'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":           {"type": "string", "description": "שם העסקה"},
                "domain":         {"type": "string", "description": "דומיין עסקי (real_estate/import/media/saas/finance/general)"},
                "owner_id":       {"type": "string", "description": "מזהה record של הבעלים העסקי (rec...)"},
                "origin_lead_id": {"type": "string", "description": "מזהה ליד המקור, אם רלוונטי (rec...)"},
                "contact_ids":    {"type": "array", "items": {"type": "string"}, "description": "מזהי אנשי קשר מקושרים (rec...)"},
                "amount":         {"type": "number", "description": "סכום העסקה"},
                "stage":          {"type": "string", "description": "שלב העסקה (ברירת מחדל: הזדמנות)"},
                "notes":          {"type": "string", "description": "הערות חופשיות"}
            },
            "required": ["name", "domain", "owner_id"]
        }
    },
    {
        "name": "crm_create_payment_term",
        "description": (
            "יצירת תנאי תשלום (Payment Term) לעסקה קיימת — כלל חישוב חוזר "
            "(סכום קבוע או אחוז מבסיס). תמיד מקושר ל-deal_id קיים."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id":      {"type": "string", "description": "מזהה העסקה (rec...) — חובה"},
                "name":         {"type": "string", "description": "שם תנאי התשלום"},
                "calc_type":    {"type": "string", "enum": ["fixed", "percentage"], "description": "שיטת חישוב"},
                "fixed_amount": {"type": "number", "description": "סכום קבוע — חובה כש-calc_type=fixed"},
                "rate_pct":     {"type": "number", "description": "אחוז — חובה כש-calc_type=percentage"},
                "calc_basis":   {"type": "string", "description": "בסיס לחישוב אחוז (deal_amount/monthly_salary/first_salary) — חובה כש-calc_type=percentage"},
                "trigger_type": {"type": "string", "enum": ["immediate", "specific_date", "after_period", "event_based"], "description": "מתי התשלום מופעל"},
                "trigger_date": {"type": "string", "description": "תאריך הפעלה, אם trigger_type=specific_date"},
                "cadence":      {"type": "string", "enum": ["once", "monthly"], "description": "תדירות"},
                "vat_rule":     {"type": "string", "enum": ["none", "add", "included"], "description": "טיפול במע\"מ"},
                "notes":        {"type": "string", "description": "הערות חופשיות"}
            },
            "required": ["deal_id", "calc_type"]
        }
    },
    {
        "name": "crm_create_payment",
        "description": (
            "יצירת תשלום (Payment) חדש. יכול להיות מקושר לעסקה/תנאי תשלום, "
            "או עצמאי (אינו חייב עסקה)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount":          {"type": "number", "description": "סכום סופי לתשלום"},
                "domain":          {"type": "string", "description": "דומיין עסקי"},
                "owner_id":        {"type": "string", "description": "מזהה record של הבעלים העסקי (rec...)"},
                "deal_id":         {"type": "string", "description": "מזהה עסקה מקושרת, אם קיימת (rec...)"},
                "payment_term_id": {"type": "string", "description": "מזהה תנאי תשלום מקושר, אם קיים (rec...)"},
                "origin_lead_id":  {"type": "string", "description": "מזהה ליד המקור, אם רלוונטי (rec...)"},
                "reference":       {"type": "string", "description": "מספר אסמכתא/הפניה"},
                "due_date":        {"type": "string", "description": "תאריך יעד לתשלום"},
                "vat_rule":        {"type": "string", "enum": ["none", "add", "included"], "description": "טיפול במע\"מ"},
                "notes":           {"type": "string", "description": "הערות חופשיות"}
            },
            "required": ["amount", "domain", "owner_id"]
        }
    },
]

# ══════════════════════════════════════════════════
# CRM Tools — not yet fully implemented in dispatcher/registry.
# Hidden from Claude (not in TOOL_SCHEMAS) until ready.
# Kept in action_validator for defense-in-depth validation.
# ══════════════════════════════════════════════════

_CRM_SCHEMAS_HIDDEN = []

# ══════════════════════════════════════════════════
# PR-0C — ActionGateway adapters for former event_bus custom actions.
# Fully implemented in tool_registry/dispatcher, but deliberately NOT in
# TOOL_SCHEMAS: these are internal-execution-only tools, proposed exclusively
# by trusted Python callers (media_handler.py, followup_engine.py,
# core/lead_recovery.py) via ActionGateway.propose_action(trusted_source=...),
# never by the Agent tool_use loop directly.
# ══════════════════════════════════════════════════

_APPROVAL_ACTION_SCHEMAS_HIDDEN = [
    {
        "name": "media_save_to_memory",
        "description": "שמירת תמלול הודעה קולית ל-Business Memory — לאחר אישור בעלים",
        "input_schema": {
            "type": "object",
            "properties": {
                "transcript": {"type": "string", "description": "תמליל ההודעה הקולית"},
                "domain":     {"type": "string", "description": "דומיין עסקי (ברירת מחדל: general)"},
                "source":     {"type": "string", "description": "מקור הבקשה (ברירת מחדל: media_handler)"},
            },
            "required": ["transcript"],
        },
    },
    {
        "name": "send_followup",
        "description": "הצגת טיוטת פולואפ מאושרת לבעלים להעברה ידנית (N05-B)",
        "input_schema": {
            "type": "object",
            "properties": {
                "chat_id":      {"type": "string", "description": "chat_id של הבעלים לשליחת הטיוטה"},
                "draft":        {"type": "string", "description": "טיוטת ההודעה"},
                "contact_name": {"type": "string", "description": "שם איש הקשר"},
                "channel":      {"type": "string", "description": "ערוץ (whatsapp/telegram/...)"},
                "memory_key":   {"type": "string", "description": "מפתח זיכרון הליד"},
            },
            "required": ["chat_id"],
        },
    },
    {
        "name": "send_recovery",
        "description": "הצגת טיוטת recovery מאושרת לבעלים להעברה ידנית (C53 FIX-1)",
        "input_schema": {
            "type": "object",
            "properties": {
                "chat_id":      {"type": "string", "description": "chat_id של הבעלים לשליחת הטיוטה"},
                "draft":        {"type": "string", "description": "טיוטת ההודעה"},
                "contact_name": {"type": "string", "description": "שם איש הקשר"},
                "channel":      {"type": "string", "description": "ערוץ (whatsapp/telegram/...)"},
                "memory_key":   {"type": "string", "description": "מפתח זיכרון הליד"},
                "tier":         {"type": "string", "description": "tier ה-recovery"},
            },
            "required": ["chat_id"],
        },
    },
]


# PR-RP1: fail import/startup on duplicate schema names or registry/schema
# drift. This validates declarations only; it does not filter schemas or alter
# dispatch/runtime behavior when the declarations are valid.
from tool_registry import validate_tool_invariants as _validate_tool_invariants

_validate_tool_invariants(TOOL_SCHEMAS)
