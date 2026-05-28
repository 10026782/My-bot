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
