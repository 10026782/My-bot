# tools/schemas.py — v2.0
# הגדרות כלים ל-Claude native tool_use

TOOL_SCHEMAS = [

    # ══════════════════════════════════════════════
    # Knowledge
    # ══════════════════════════════════════════════
    {
        "name": "add_knowledge",
        "description": "הוספת עובדה לzero-shot memory של הבוט",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "העובדה לשמירה"}
            },
            "required": ["fact"]
        }
    },

    # ══════════════════════════════════════════════
    # Google Drive
    # ══════════════════════════════════════════════
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

    # ══════════════════════════════════════════════
    # Calendar
    # ══════════════════════════════════════════════
    {
        "name": "calendar_get_events",
        "description": "קריאת אירועים מ-Google Calendar",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "כמות אירועים (ברירת מחדל: 5)"},
                "days_ahead":  {"type": "integer", "description": "כמה ימים קדימה (ברירת מחדל: 7)"}
            }
        }
    },
    {
        "name": "calendar_create_event",
        "description": "יצירת אירוע ב-Google Calendar — בדוק זמינות קודם",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary":          {"type": "string",  "description": "כותרת הפגישה"},
                "start_time":       {"type": "string",  "description": "ISO 8601: YYYY-MM-DDTHH:MM:SS"},
                "duration_minutes": {"type": "integer", "description": "משך בדקות (ברירת מחדל: 60)"}
            },
            "required": ["summary", "start_time"]
        }
    },

    # ══════════════════════════════════════════════
    # Gmail
    # ══════════════════════════════════════════════
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

    # ══════════════════════════════════════════════
    # Sheets
    # ══════════════════════════════════════════════
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

    # ══════════════════════════════════════════════
    # Airtable (raw)
    # ══════════════════════════════════════════════
    {
        "name": "airtable_get",
        "description": "שליפת רשומות מ-Airtable",
        "input_schema": {
            "type": "object",
            "properties": {
                "table":          {"type": "string",  "description": "שם הטבלה"},
                "filter_formula": {"type": "string",  "description": "filterByFormula (אופציונלי)"},
                "max_records":    {"type": "integer", "description": "מקסימום רשומות (ברירת מחדל: 10)"}
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

    # ══════════════════════════════════════════════
    # CRM — אנשי קשר
    # ══════════════════════════════════════════════
    {
        "name": "crm_add_contact",
        "description": "הוספת איש קשר חדש ל-CRM (לקוח, ספק, שותף וכו')",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":         {"type": "string", "description": "שם מלא"},
                "phone":        {"type": "string", "description": "טלפון (אופציונלי)"},
                "email":        {"type": "string", "description": "מייל (אופציונלי)"},
                "contact_type": {"type": "string", "description": "Client | Supplier | Partner | Other"},
                "company":      {"type": "string", "description": "שם חברה (אופציונלי)"},
                "notes":        {"type": "string", "description": "הערות חופשיות (אופציונלי)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "crm_find_contact",
        "description": "חיפוש איש קשר לפי שם, טלפון או מייל",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "שם / טלפון / מייל לחיפוש"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "crm_list_contacts",
        "description": "רשימת אנשי קשר פעילים, אפשר לסנן לפי סוג",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_type": {"type": "string", "description": "Client | Supplier | Partner | Other — ריק = הכל"}
            }
        }
    },
    {
        "name": "crm_update_last_contact",
        "description": "עדכון תאריך 'יצרתי קשר לאחרונה' לאיש קשר",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "מזהה הרשומה (rec...)"}
            },
            "required": ["record_id"]
        }
    },

    # ══════════════════════════════════════════════
    # CRM — עסקאות
    # ══════════════════════════════════════════════
    {
        "name": "crm_add_deal",
        "description": "הוספת עסקת נדל\"ן חדשה. מימון >9% — חסום אוטומטית (חוק ברזל).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":             {"type": "string", "description": "שם העסקה / פרויקט"},
                "address":          {"type": "string", "description": "כתובת הנכס"},
                "price":            {"type": "number", "description": "מחיר ב-₪"},
                "funding_cost_pct": {"type": "number", "description": "עלות מימון % — מקסימום 9% (חוק ברזל)"},
                "contact_id":       {"type": "string", "description": "record_id של איש קשר (אופציונלי)"},
                "deadline":         {"type": "string", "description": "תאריך סגירה YYYY-MM-DD (אופציונלי)"},
                "notes":            {"type": "string", "description": "הערות (אופציונלי)"}
            },
            "required": ["name", "address", "price", "funding_cost_pct"]
        }
    },
    {
        "name": "crm_list_deals",
        "description": "רשימת עסקאות, אפשר לסנן לפי סטטוס",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Prospect | Due Diligence | Active | Closed | Cancelled — ריק = הכל"}
            }
        }
    },
    {
        "name": "crm_update_deal_status",
        "description": "עדכון סטטוס עסקה קיימת",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "מזהה הרשומה (rec...)"},
                "status":    {"type": "string", "description": "Prospect | Due Diligence | Active | Closed | Cancelled"},
                "notes":     {"type": "string", "description": "הערות לעדכון (אופציונלי)"}
            },
            "required": ["record_id", "status"]
        }
    },

    # ══════════════════════════════════════════════
    # CRM — תשלומים
    # ══════════════════════════════════════════════
    {
        "name": "crm_add_payment",
        "description": "רישום תשלום עתידי / חיוב ל-CRM",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":       {"type": "string", "description": "שם/תיאור התשלום"},
                "amount":     {"type": "number", "description": "סכום ב-₪"},
                "due_date":   {"type": "string", "description": "תאריך יעד YYYY-MM-DD"},
                "deal_id":    {"type": "string", "description": "record_id של עסקה (אופציונלי)"},
                "contact_id": {"type": "string", "description": "record_id של איש קשר (אופציונלי)"},
                "notes":      {"type": "string", "description": "הערות (אופציונלי)"}
            },
            "required": ["name", "amount", "due_date"]
        }
    },
    {
        "name": "crm_upcoming_payments",
        "description": "רשימת תשלומים צפויים בימים הקרובים",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "כמה ימים קדימה (ברירת מחדל: 7)"}
            }
        }
    },
    {
        "name": "crm_overdue_payments",
        "description": "רשימת תשלומים באיחור — מעדכן סטטוס ל-Overdue אוטומטית",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "crm_mark_payment_paid",
        "description": "סימון תשלום כשולם",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "מזהה הרשומה (rec...)"}
            },
            "required": ["record_id"]
        }
    },
]
