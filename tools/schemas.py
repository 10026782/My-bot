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
]

# ══════════════════════════════════════════════════
# CRM Tools — Contacts, Deals, Payments
# ══════════════════════════════════════════════════

TOOL_SCHEMAS += [
    # ── Contacts ──────────────────────────────────
    {
        "name": "crm_add_contact",
        "description": "הוספת איש קשר חדש ל-CRM",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":         {"type": "string", "description": "שם מלא (חובה)"},
                "phone":        {"type": "string", "description": "מספר טלפון"},
                "email":        {"type": "string", "description": "כתובת מייל"},
                "contact_type": {"type": "string", "description": "Client | Supplier | Partner | Lawyer | Accountant"},
                "company":      {"type": "string", "description": "שם חברה"},
                "notes":        {"type": "string", "description": "הערות"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "crm_find_contact",
        "description": "חיפוש איש קשר לפי שם או חברה",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "שם או חברה לחיפוש"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "crm_list_contacts",
        "description": "רשימת אנשי קשר פעילים, אופציונלי לפי סוג",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_type": {"type": "string", "description": "Client | Supplier | Partner (אופציונלי)"}
            }
        }
    },
    {
        "name": "crm_update_last_contact",
        "description": "עדכון תאריך קשר אחרון לאיש קשר",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "מזהה הרשומה (rec...)"}
            },
            "required": ["record_id"]
        }
    },
    # ── Deals ─────────────────────────────────────
    {
        "name": "crm_add_deal",
        "description": "הוספת עסקת נדל\"ן חדשה — בודק חוק 9% אוטומטית",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":              {"type": "string",  "description": "שם הנכס / העסקה"},
                "address":           {"type": "string",  "description": "כתובת הנכס"},
                "price":             {"type": "number",  "description": "מחיר ₪"},
                "funding_cost_pct":  {"type": "number",  "description": "עלות מימון % (חוק ברזל: מקסימום 9%)"},
                "contact_id":        {"type": "string",  "description": "record_id של איש קשר (אופציונלי)"},
                "deadline":          {"type": "string",  "description": "תאריך סגירה YYYY-MM-DD (אופציונלי)"},
                "notes":             {"type": "string",  "description": "הערות"}
            },
            "required": ["name", "address", "price", "funding_cost_pct"]
        }
    },
    {
        "name": "crm_update_deal_status",
        "description": "עדכון סטטוס עסקה",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "מזהה העסקה (rec...)"},
                "status":    {"type": "string", "description": "Prospect | Due Diligence | Active | Closed | Cancelled"},
                "notes":     {"type": "string", "description": "הערות לשינוי (אופציונלי)"}
            },
            "required": ["record_id", "status"]
        }
    },
    {
        "name": "crm_list_deals",
        "description": "רשימת עסקאות, אופציונלי לפי סטטוס",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Prospect | Active | Closed | Cancelled (אופציונלי)"}
            }
        }
    },
    # ── Payments ──────────────────────────────────
    {
        "name": "crm_add_payment",
        "description": "רישום תשלום עתידי עם תזכורת אוטומטית 3 ימים מראש",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":       {"type": "string", "description": "שם / תיאור התשלום"},
                "amount":     {"type": "number", "description": "סכום ₪"},
                "due_date":   {"type": "string", "description": "תאריך לתשלום YYYY-MM-DD"},
                "deal_id":    {"type": "string", "description": "record_id עסקה (אופציונלי)"},
                "contact_id": {"type": "string", "description": "record_id איש קשר (אופציונלי)"},
                "notes":      {"type": "string", "description": "הערות"}
            },
            "required": ["name", "amount", "due_date"]
        }
    },
    {
        "name": "crm_upcoming_payments",
        "description": "תשלומים קרובים בX ימים הבאים",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "כמה ימים קדימה (ברירת מחדל: 7)"}
            }
        }
    },
    {
        "name": "crm_mark_payment_paid",
        "description": "סימון תשלום כשולם",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "מזהה התשלום (rec...)"}
            },
            "required": ["record_id"]
        }
    },
    {
        "name": "crm_overdue_payments",
        "description": "בדיקת תשלומים שעברו מועד ועדכונם ל-Overdue",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    # ── Knowledge ─────────────────────────────────
    {
        "name": "add_knowledge",
        "description": "שמירת מידע עסקי חשוב לזיכרון ארוך-טווח",
        "input_schema": {
            "type": "object",
            "properties": {
                "key":   {"type": "string", "description": "מפתח / נושא"},
                "value": {"type": "string", "description": "המידע לשמירה"}
            },
            "required": ["key", "value"]
        }
    },
]
