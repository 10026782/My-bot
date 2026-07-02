# tool_registry.py — Tool Registry Layer v2
# מטא-דאטה ומדיניות לכל כלי: הרשאות, אישור, סיכון.
#
# כלל ברזל: אין Tool בלי בדיקת הרשאה.
# dispatcher מבצע. registry מחליט אם מותר.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from identity import Identity


# ══════════════════════════════════════════════════
# Tool Metadata
# ══════════════════════════════════════════════════

@dataclass
class ToolMeta:
    name:              str
    roles_allowed:     set[str]       # roles שמורשים
    tenant_scoped:     bool = False   # מסנן לפי tenant אוטומטית
    requires_approval: bool = False   # דורש אישור אנושי לפני ביצוע
    blocked_by_emergency: bool = False  # נחסם על ידי EMERGENCY_STOP_ALL
    high_risk:         bool = False   # פעולה בלתי הפיכה
    read_only:         bool = False   # לא משנה נתונים
    description_he:    str  = ""


# ── Shortcuts לקבוצות roles ──────────────────────
_INTERNAL      = {"owner", "partner", "manager", "employee"}
_MANAGEMENT    = {"owner", "partner", "manager"}
_SENIOR        = {"owner", "partner"}
_OWNER_ONLY    = {"owner"}
_ALL_EXTERNAL  = {"owner", "partner", "manager", "employee", "lead"}


# ══════════════════════════════════════════════════
# C83: approval and emergency blocking are separate policy dimensions.
# Derived policy sets are defined after _REGISTRY below.
# ══════════════════════════════════════════════════


# ══════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════

_REGISTRY: dict[str, ToolMeta] = {

    # ── Google Drive ─────────────────────────────
    "search_drive": ToolMeta(
        name="search_drive",
        roles_allowed=_MANAGEMENT,
        read_only=True,
        description_he="חיפוש קבצים ב-Drive"
    ),
    "read_drive_file": ToolMeta(
        name="read_drive_file",
        roles_allowed=_MANAGEMENT,
        read_only=True,
        description_he="קריאת תוכן קובץ מ-Drive"
    ),

    # ── Calendar ─────────────────────────────────
    "calendar_get_events": ToolMeta(
        name="calendar_get_events",
        roles_allowed=_INTERNAL,
        read_only=True,
        description_he="קריאת אירועים מהיומן"
    ),
    "calendar_create_event": ToolMeta(
        name="calendar_create_event",
        roles_allowed=_MANAGEMENT,
        requires_approval=True,
        blocked_by_emergency=True,
        description_he="יצירת אירוע ביומן — דורש אישור, בודק חפיפות, force=true לקבוע בכל זאת"
    ),

    # ── Gmail ────────────────────────────────────
    "gmail_draft": ToolMeta(
        name="gmail_draft",
        roles_allowed=_MANAGEMENT,
        requires_approval=True,
        blocked_by_emergency=True,
        description_he="יצירת טיוטת מייל — דורש אישור (לא שולח)"
    ),
    "gmail_send_draft": ToolMeta(
        name="gmail_send_draft",
        roles_allowed=_SENIOR,
        requires_approval=True,
        blocked_by_emergency=True,
        high_risk=True,
        description_he="שליחת טיוטה — דורש אישור owner/partner"
    ),
    "gmail_read": ToolMeta(
        name="gmail_read",
        roles_allowed=_OWNER_ONLY,
        read_only=True,
        description_he="קריאת מיילים אחרונים"
    ),

    # ── Sheets ───────────────────────────────────
    "sheets_append": ToolMeta(
        name="sheets_append",
        roles_allowed=_MANAGEMENT,
        requires_approval=True,
        blocked_by_emergency=True,
        description_he="הוספת שורה לגיליון — דורש אישור"
    ),

    # ── Airtable ─────────────────────────────────
    "airtable_get": ToolMeta(
        name="airtable_get",
        roles_allowed=_ALL_EXTERNAL,   # lead רואה רק נתוני עצמו (filter ב-tool)
        tenant_scoped=True,
        read_only=True,
        description_he="שליפת רשומות מ-Airtable"
    ),
    "airtable_add": ToolMeta(
        name="airtable_add",
        roles_allowed=_INTERNAL,
        tenant_scoped=True,
        requires_approval=True,
        blocked_by_emergency=True,
        high_risk=True,
        description_he="הוספת רשומה ל-Airtable — דורש אישור"
    ),
    "airtable_update": ToolMeta(
        name="airtable_update",
        roles_allowed=_MANAGEMENT,
        tenant_scoped=True,
        requires_approval=True,
        blocked_by_emergency=True,
        high_risk=True,
        description_he="עדכון רשומה ב-Airtable — דורש אישור"
    ),
    "airtable_get_schema": ToolMeta(
        name="airtable_get_schema",
        roles_allowed=_SENIOR,
        read_only=True,
        description_he="קריאת כל הטבלאות והשדות מ-Airtable בזמן אמת"
    ),

    # ── Lead Search ───────────────────────────────
    "search_lead": ToolMeta(
        name             = "search_lead",
        roles_allowed    = _MANAGEMENT,
        read_only        = True,
        description_he   = "חיפוש ליד לפי שם חלקי בטבלת Leads",
    ),

    # ── Contact Resolver (N03) ────────────────────
    "resolve_contact": ToolMeta(
        name             = "resolve_contact",
        roles_allowed    = _MANAGEMENT,
        read_only        = True,
        description_he   = "חיפוש fuzzy של איש קשר לפי שם — מחזיר פרטים או רשימה לבחירה",
    ),

    # ── Daily Digest on-demand ────────────────────
    "get_daily_report": ToolMeta(
        name           = "get_daily_report",
        roles_allowed  = _MANAGEMENT,
        read_only      = True,
        description_he = "דוח יומי מלא — לידים חמים, פולו-אפ, משימות, עסקאות, תשלומים",
    ),

    # ── D06 — Business Memory ─────────────────────
    "search_business_memory": ToolMeta(
        name             = "search_business_memory",
        roles_allowed    = _MANAGEMENT,
        read_only        = True,
        description_he   = "חיפוש בזיכרון עסקי — 'מה סיכמנו עם ספק X?' / 'החלטות מהפגישה עם Y'",
    ),

    # ── CRM — Payments ─────────────────────────────
    "crm_mark_payment_paid": ToolMeta(
        name             = "crm_mark_payment_paid",
        roles_allowed    = _SENIOR,
        tenant_scoped    = True,
        requires_approval= True,
        blocked_by_emergency=True,
        high_risk        = True,
        description_he   = "סימון תשלום כ-שולם — דורש אישור owner/partner",
    ),
}


# C83: single policy source. Consumers import these derived views instead of
# maintaining independent tool-name lists.
TOOLS_REQUIRING_APPROVAL: frozenset[str] = frozenset(
    name for name, meta in _REGISTRY.items() if meta.requires_approval
)
TOOLS_BLOCKED_BY_EMERGENCY: frozenset[str] = frozenset(
    name for name, meta in _REGISTRY.items() if meta.blocked_by_emergency
)


# ══════════════════════════════════════════════════
# Policy Checks
# ══════════════════════════════════════════════════

class ToolDenied(Exception):
    """כלי לא מורשה לזהות זו."""


def get(tool_name: str) -> ToolMeta | None:
    return _REGISTRY.get(tool_name)


def check_allowed(tool_name: str, identity: "Identity") -> bool:
    meta = _REGISTRY.get(tool_name)
    if not meta:
        return False
    return identity.role in meta.roles_allowed


def enforce(tool_name: str, identity: "Identity") -> ToolMeta:
    """
    זורק ToolDenied אם לא מורשה.
    כלל ברזל: נקרא לפני כל dispatch.
    """
    meta = _REGISTRY.get(tool_name)
    if not meta:
        raise ToolDenied(f"כלי לא קיים ב-Registry: {tool_name}")
    if identity.role not in meta.roles_allowed:
        raise ToolDenied(
            f"❌ {identity.role} אינו מורשה להפעיל '{tool_name}'"
        )
    return meta


def needs_approval(tool_name: str) -> bool:
    meta = _REGISTRY.get(tool_name)
    return meta.requires_approval if meta else False


def is_blocked_by_emergency(tool_name: str) -> bool:
    meta = _REGISTRY.get(tool_name)
    return meta.blocked_by_emergency if meta else False


def is_high_risk(tool_name: str) -> bool:
    meta = _REGISTRY.get(tool_name)
    return meta.high_risk if meta else False


def all_tools_for_role(role: str) -> list[str]:
    return [name for name, meta in _REGISTRY.items() if role in meta.roles_allowed]
