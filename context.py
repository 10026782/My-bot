# context.py — Context Builder v2
# הלב של המערכת — בונה AgentContext מלא לפי Identity.
#
# אותו Agent. אותם Tools. אותו LLM.
# Context אחר = תוצאה אחרת לחלוטין.
#
# זרימה: Identity → build_context() → AgentContext → run_agent

from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from identity import Identity

from identity import Role, Domain
from core_knowledge import STATIC_MANIFEST, dynamic_context
from tools.schemas import TOOL_SCHEMAS

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# AgentContext — פלט build_context
# ══════════════════════════════════════════════════

@dataclass
class AgentContext:
    system_prompt:  str
    allowed_tools:  list
    memory_key:     str
    max_tokens:     int
    model:          str
    identity_label: str


# ══════════════════════════════════════════════════
# Tool Filter — לפי role
# ══════════════════════════════════════════════════

_ROLE_TOOLS: dict[str, set[str]] = {
    Role.OWNER: {
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_send_draft", "gmail_read",
        "sheets_append",
        "airtable_get", "airtable_add", "airtable_update", "airtable_get_schema",
    },
    Role.PARTNER: {
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_read",
        "sheets_append",
        "airtable_get", "airtable_add", "airtable_update",
    },
    Role.MANAGER: {
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_read",
        "airtable_get", "airtable_add", "airtable_update",
    },
    Role.EMPLOYEE: {
        "calendar_get_events",
        "airtable_get",        # קריאה בלבד
    },
    Role.LEAD: {
        "airtable_get",        # רק נתוני עצמו — filter ב-dispatcher
    },
    Role.GUEST:    set(),
    Role.READONLY: set(),
}


def _filter_tools(role: str) -> list:
    allowed = _ROLE_TOOLS.get(role, set())
    return [t for t in TOOL_SCHEMAS if t["name"] in allowed]


# ══════════════════════════════════════════════════
# System Prompts — אחד לכל role
# ══════════════════════════════════════════════════

def _prompt_owner(identity: "Identity", research_mode: bool) -> str:
    base = STATIC_MANIFEST + dynamic_context.get()
    base += (
        "\n\nאתה עוזר אסטרטגי חד ומדויק של אליהו חזן. "
        "גישה מלאה לכל הכלים והנתונים. "
        f"דומיין פעיל: {identity.domain_id}.\n"
        "📧 מיילים: תמיד gmail_draft — לעולם אל תשלח ישירות. "
        "📅 פגישות: calendar_get_events לפני calendar_create_event. "
        "תמיד סכם ב'הצעד הבא המומלץ'.\n"
        "⚠️=הפרת חוק | 💡=הזדמנות | 🚨=סיכון מיידי"
    )
    if research_mode:
        base += "\n\n🔬 מצב מחקר — נתח לעומק, ענה בהרחבה אסטרטגית."
    return base


def _prompt_partner(identity: "Identity") -> str:
    domains_str = ", ".join(identity.allowed_domains) or identity.domain_id
    return (
        f"אתה עוזר לשותף עסקי: {identity.display_name or identity.user_id}\n"
        f"tenant: {identity.tenant_id} | דומיינים: {domains_str}\n"
        f"גישה לכלים תפעוליים בדומיינים המורשים בלבד.\n"
        f"אין גישה להגדרות מערכת או נתונים פיננסיים רגישים.\n"
        f"פעולה בלתי הפיכה — בקש אישור תחילה."
    )


def _prompt_manager(identity: "Identity") -> str:
    return (
        f"אתה עוזר למנהל תפעולי: {identity.display_name or identity.user_id}\n"
        f"tenant: {identity.tenant_id} | דומיין: {identity.domain_id}\n"
        f"גישה ל-CRM, Tasks, Calendar, Drive.\n"
        f"אין גישה לנתונים פיננסיים רגישים או הגדרות מערכת.\n"
        f"כל פעולה בלתי הפיכה — בקש אישור תחילה."
    )


def _prompt_employee(identity: "Identity") -> str:
    return (
        f"אתה עוזר לעובד: {identity.display_name or identity.user_id}\n"
        f"גישה מוגבלת: Tasks + עדכון סטטוס + קריאת יומן.\n"
        f"אין גישה למיילים, קבצים, או נתונים פיננסיים."
    )


def _prompt_lead(identity: "Identity") -> str:
    name = identity.display_name or "שלום"
    return (
        f"אתה עוזר אישי חם ומקצועי של גימי — העוזר האישי של אליהו חזן.\n"
        f"אתה מדבר עם {name}, לקוח/ה פוטנציאל/ית.\n\n"
        f"המטרה שלך: לעזור, ליצור קשר חיובי, ולהשאיר רושם מצוין.\n"
        f"ענה על כל שאלה בחום ובמקצועיות. אם שואלים על שירותים, הסבר בקצרה ושאל מה מעניין.\n"
        f"אל תחשוף נתונים פנימיים של העסק (מחירים, לקוחות, פיננסים).\n"
        f"אם יש בקשה שמעבר ליכולתך — הצע להעביר לאליהו ישירות."
    )


def _prompt_guest(_identity: "Identity") -> str:
    return (
        "אתה עוזר אישי חם ומקצועי של גימי — העוזר האישי של אליהו חזן.\n"
        "אתה מדבר עם מתעניין/ת חדש/ה.\n\n"
        "המטרה: לענות בחיוב, להסביר במה אפשר לעזור, וליצור קשר.\n"
        "אל תחשוף מידע פנימי. אם יש שאלה מורכבת — הצע להעביר לאליהו."
    )


def _prompt_readonly(_identity: "Identity") -> str:
    return (
        "אתה עוזר אישי חם של גימי.\n"
        "ענה בקצרה ובנימוס. אם צריך פעולה ספציפית — הצע ליצור קשר ישיר."
    )


# ══════════════════════════════════════════════════
# Model / Token Selection
# ══════════════════════════════════════════════════

def _select_model(identity: "Identity", text: str) -> tuple[str, int]:
    if identity.is_owner:
        if text.startswith("#"):
            return "claude-sonnet-4-6", 2000
        return "claude-haiku-4-5-20251001", 1000
    if identity.role in (Role.PARTNER, Role.MANAGER):
        return "claude-haiku-4-5-20251001", 800
    # employee / lead / guest / readonly
    return "claude-haiku-4-5-20251001", 500


# ══════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════

def build_context(
    identity: "Identity",
    user_text: str = "",
    domain: str = "",
    handler: str = "",
    intent: str = "",
) -> AgentContext:
    """
    בונה AgentContext מלא לפי Identity.

    domain:  אם מועבר (מהראוטר) — מעדכן את identity.domain_id.
    handler: החלטת הראוטר — מוזרקת כהוראת הקשר לפרומפט.
             הAgent תמיד עונה; הוא זה שמנסח את התגובה לאדם.
    intent:  intent שזוהה (לשימוש בהוראת ה-BLOCK/APPROVAL).
    """
    # עדכון domain מהראוטר אם הגיע
    if domain and domain != identity.domain_id:
        identity.domain_id = domain
        logger.info(f"[Context] Domain override: {domain} for {identity}")

    research_mode = user_text.startswith("#") and identity.is_owner
    model, max_tokens = _select_model(identity, user_text)

    match identity.role:
        case Role.OWNER:
            system = _prompt_owner(identity, research_mode)
        case Role.PARTNER:
            system = _prompt_partner(identity)
        case Role.MANAGER:
            system = _prompt_manager(identity)
        case Role.EMPLOYEE:
            system = _prompt_employee(identity)
        case Role.LEAD:
            system = _prompt_lead(identity)
        case Role.GUEST:
            system = _prompt_guest(identity)
        case _:
            system = _prompt_readonly(identity)

    # ── Router hint injection (invisible to user) ──
    from core.router.route_decision import Handler as H
    if handler == H.BLOCK:
        system += (
            f"\n\n[הוראת מערכת: הפעולה '{intent}' אינה זמינה למשתמש זה. "
            "ענה בנימוס וקצרה שלא ניתן לבצע את הבקשה, "
            "ללא ⛔ ובלי מינוח טכני. הצע חלופה או להעביר לאליהו.]"
        )
    elif handler == H.APPROVAL:
        system += (
            f"\n\n[הוראת מערכת: הפעולה '{intent}' דורשת אישור לפני ביצוע. "
            "הסבר למשתמש מה עומד לקרות ובקש אישור: ✅ כן / ❌ לא. "
            "אל תבצע את הפעולה עד לאישור.]"
        )
    elif handler == H.CLARIFY:
        system += (
            "\n\n[הוראת מערכת: הכוונה לא ברורה לחלוטין. "
            "בקש הבהרה קצרה ואחת בלבד.]"
        )

    # ── Israel date/time injection ────────────────────
    _il_offset = 3 if 4 <= datetime.utcnow().month <= 10 else 2  # DST approximation
    _now_il    = datetime.now(tz=timezone(timedelta(hours=_il_offset)))
    _date_line = _now_il.strftime("📅 היום: %A %d/%m/%Y | שעה: %H:%M (ישראל)")
    system     = _date_line + "\n\n" + system

    allowed_tools = _filter_tools(identity.role)

    logger.info(
        f"[Context] tenant={identity.tenant_id} user={identity.user_id} "
        f"role={identity.role} domain={identity.domain_id} "
        f"model={model} tools={len(allowed_tools)}"
    )

    return AgentContext(
        system_prompt  = system,
        allowed_tools  = allowed_tools,
        memory_key     = identity.memory_key,
        max_tokens     = max_tokens,
        model          = model,
        identity_label = str(identity),
    )
