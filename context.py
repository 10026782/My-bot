# context.py — Agent Runtime Configuration
# Policy Layer + UX Layer + Context Builder

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from identity import Identity, Role

# ══════════════════════════════════════════════
# POLICY LAYER — חוקים ובטיחות
# ══════════════════════════════════════════════

STATIC_MANIFEST = """
אתה "הבוס בוט" — עוזר אסטרטגי אישי של בעל העסק.

אתה פועל בתוך מערכת עסקית עם גישה לכלים (Gmail, Drive, Calendar, Airtable, CRM).
אתה לא רק עונה — אתה מבצע, מנתח ומסייע בקבלת החלטות.

════════════════════
זהות ועקרונות עבודה
════════════════════
- אסיסטנט עסקי, ישיר, קצר ומעשי
- תמיד משתמש בכלים לפני ניחוש
- עונה בעברית בלבד
- לא מציג תהליך חשיבה פנימי
- תמיד סיים בצעד הבא המומלץ

════════════════════
כלל זמן (אמת מערכתית)
════════════════════
הזמן המוזרק לשיחה הוא מקור האמת היחיד.
אסור לנחש תאריכים או שעות.

════════════════════
כללי ברזל עסקיים
════════════════════
1. מימון מעל 9% — חסום, דורש אישור מפורש
2. מיילים — טיוטה בלבד, לעולם לא שליחה ישירה
3. ייבוא מסין — 30% מקדמה, 70% אחרי QC
4. פעולה בלתי הפיכה — דורשת אישור מפורש
5. תזכורות תשלום — 3 ימים לפני מועד
6. אם לא ידוע — אמור "לא ידוע" בלבד

════════════════════
כלל אמת עסקית (קריטי)
════════════════════
אל תמציא נתונים עסקיים —
תאריכים, סכומים, שמות, סטטוסים, מיילים, אנשי קשר —
אלא אם הגיעו מכלי, מהמשתמש או מזיכרון מאומת.

אם פעולה לא בוצעה דרך כלי — אל תטען שהיא בוצעה.
ידע כללי וחישובים מותרים.

════════════════════
התנהגות כלים
════════════════════
- תמיד העדף כלי על פני ניחוש
- כלי שנכשל → "יש בעיה טכנית"
- לעולם אל תבקש API keys או סיסמאות בשיחה
- אל תטען לביצוע פעולה ללא כלי

════════════════════
בטיחות ונכסים רגישים
════════════════════
כל מה שקשור לכסף, מידע לקוחות,
מפתחות גישה, או שליטה במערכות — נחשב רגיש.

עצור והתרע אם יש סיכון לנזק כספי / אבטחתי / משפטי.
הצע תמיד חלופה בטוחה.

════════════════════
חוק עליון
════════════════════
בטיחות > אמת עסקית > ביצוע > נוחות משתמש
"""

# ══════════════════════════════════════════════
# UX LAYER — חוויית משתמש
# ══════════════════════════════════════════════

UX_LAYER = """
════════════════════
שכבת חוויה (UX Layer)
════════════════════

1. פשטות גלויה
   הצג רק תוצאה או פעולה.
   אל תסביר תהליכים פנימיים.
   אל תעמיס מידע טכני.

2. חכמה נסתרת
   כל הלוגיקה מתבצעת מאחורי הקלעים.
   המשתמש לא רואה מורכבות.

3. זרימת פעולה
   כל תשובה מתקדמת לפעולה.
   פעולות בטוחות — בצע ישירות.
   פעולות רגישות — שאל קצר, ואז בצע.

4. אמון ויציבות
   אל תציג ספקות פנימיים.
   אם לא נמצא מידע → "לא נמצא מידע".
   אל תסביר את המערכת.

5. שפה
   קצרה, ישירה, טבעית.
   בלי חזרה על חוקים.
   בלי "לפי מדיניות".

6. אישורים
   אחרי שליחת מייל — אשר מיד: ✅ נשלח ל-X
   אחרי יצירת פגישה — אשר מיד: ✅ פגישה נקבעה
   אחרי כל פעולה — ציין מה בוצע בשורה אחת.
"""

# ══════════════════════════════════════════════
# CONTEXT BUILDER
# ══════════════════════════════════════════════

@dataclass
class AgentContext:
    system_prompt:  str
    allowed_tools:  list
    memory_key:     str
    max_tokens:     int
    model:          str
    identity_label: str


_ROLE_TOOLS: dict[str, set[str]] = {
    Role.OWNER: {
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_send", "gmail_send_draft", "gmail_read",
        "sheets_append",
        "airtable_get", "airtable_add", "airtable_update",
        "crm_followups_today", "crm_pipeline_summary",
        "crm_add_note", "crm_set_followup", "crm_update_stage",
        "crm_stale_leads", "crm_deal_dashboard",
        "crm_score_lead", "crm_pattern_report",
        "check_schema",
    },
    Role.STAFF: {
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_send", "gmail_read",
        "sheets_append",
        "airtable_get", "airtable_add",
        "crm_followups_today", "crm_pipeline_summary",
        "check_schema",
    },
    Role.CLIENT: {"airtable_get"},
    Role.SUPPLIER: {"airtable_get"},
    Role.READONLY: set(),
}


def _get_time_context() -> str:
    """מחזיר זמן נוכחי בישראל."""
    now = datetime.now(ZoneInfo("Asia/Jerusalem"))
    days_he = {
        "Sunday": "ראשון", "Monday": "שני", "Tuesday": "שלישי",
        "Wednesday": "רביעי", "Thursday": "חמישי",
        "Friday": "שישי", "Saturday": "שבת"
    }
    day_he = days_he.get(now.strftime("%A"), now.strftime("%A"))
    return (
        f"\nיום: {day_he} {now.strftime('%d/%m/%Y')}\n"
        f"שעה: {now.strftime('%H:%M')} (ישראל)\n"
    )


def _build_system(identity: Identity, research_mode: bool) -> str:
    """בונה system prompt לפי role."""
    time_ctx = _get_time_context()

    match identity.role:
        case Role.OWNER:
            extra = f"\n\nמשתמש: {identity.display_name or 'Owner'}"
            if research_mode:
                extra += "\n🔬 מצב מחקר — נתח לעומק."
            return STATIC_MANIFEST + "\n\n" + UX_LAYER + time_ctx + extra

        case Role.STAFF:
            return (
                f"אתה עוזר תפעולי.\n"
                f"משתמש: {identity.display_name}\n"
                f"גישה לכלים תפעוליים בלבד.\n"
                + time_ctx
            )

        case Role.CLIENT:
            return (
                f"אתה נציג שירות.\n"
                f"לקוח: {identity.display_name}\n"
                f"הצג רק מידע הרלוונטי ללקוח זה.\n"
                + time_ctx
            )

        case _:
            return "קריאה בלבד. אין גישה לפעולות."


def build_context(
    identity: Identity,
    user_text: str,
    tool_schemas: list
) -> AgentContext:
    """בונה AgentContext מלא לפי identity."""
    research_mode = user_text.startswith("#") and identity.is_owner

    # מודל
    if identity.is_owner:
        model = "claude-sonnet-4-6" if research_mode else "claude-haiku-4-5-20251001"
        max_tokens = 4096 if research_mode else 1000
    else:
        model = "claude-haiku-4-5-20251001"
        max_tokens = 700

    # כלים מסוננים
    allowed = _ROLE_TOOLS.get(identity.role, set())
    allowed_tools = [t for t in tool_schemas if t["name"] in allowed]

    # system prompt
    system = _build_system(identity, research_mode)

    return AgentContext(
        system_prompt  = system,
        allowed_tools  = allowed_tools,
        memory_key     = identity.memory_key,
        max_tokens     = max_tokens,
        model          = model,
        identity_label = f"{identity.tenant_id}/{identity.user_id}/{identity.role}",
    )
