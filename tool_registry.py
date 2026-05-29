# tool_registry.py — Tool Registry Layer
# מטא-דאטה ומדיניות לכל כלי: הרשאות, אישור, סיכון.
#
# לא מחליף את dispatcher — רק מוסיף שכבת policy מעליו.
# dispatcher.py עדיין מבצע. registry.py מחליט אם מותר.

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
    roles_allowed:     set[str]
    tenant_scoped:     bool = False
    requires_approval: bool = False
    high_risk:         bool = False
    read_only:         bool = False
    description_he:    str  = ""


# ══════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════

_REGISTRY: dict[str, ToolMeta] = {

    # ── Knowledge ────────────────────────────────
    "add_knowledge": ToolMeta(
        name="add_knowledge",
        roles_allowed={"owner", "staff"},
        description_he="הוספת עובדה לזיכרון הבוט"
    ),

    # ── Google Drive ─────────────────────────────
    "search_drive": ToolMeta(
        name="search_drive",
        roles_allowed={"owner", "staff"},
        read_only=True,
        description_he="חיפוש קבצים ב-Drive"
    ),
    "read_drive_file": ToolMeta(
        name="read_drive_file",
        roles_allowed={"owner", "staff"},
        read_only=True,
        description_he="קריאת תוכן קובץ מ-Drive"
    ),

    # ── Calendar ─────────────────────────────────
    "calendar_get_events": ToolMeta(
        name="calendar_get_events",
        roles_allowed={"owner", "staff"},
        read_only=True,
        description_he="קריאת אירועים מהיומן"
    ),
    "calendar_create_event": ToolMeta(
        name="calendar_create_event",
        roles_allowed={"owner", "staff"},
        description_he="יצירת אירוע ביומן"
    ),

    # ── Gmail ────────────────────────────────────
    "gmail_draft": ToolMeta(
        name="gmail_draft",
        roles_allowed={"owner", "staff"},
        description_he="יצירת טיוטת מייל (לא שולח)"
    ),
    "gmail_send_draft": ToolMeta(
        name="gmail_send_draft",
        roles_allowed={"owner", "staff"},
        requires_approval=True,
        high_risk=True,
        description_he="שליחת טיוטה לאחר אישור"
    ),
    "gmail_read": ToolMeta(
        name="gmail_read",
        roles_allowed={"owner"},          # owner בלבד — dispatcher מאכף גם
        read_only=True,
        description_he="קריאת מיילים אחרונים"
    ),

    # ── Sheets ───────────────────────────────────
    "sheets_append": ToolMeta(
        name="sheets_append",
        roles_allowed={"owner", "staff"},
        description_he="הוספת שורה לגיליון"
    ),

    # ── Airtable ─────────────────────────────────
    "airtable_get": ToolMeta(
        name="airtable_get",
        roles_allowed={"owner", "staff", "client", "supplier"},
        tenant_scoped=True,
        read_only=True,
        description_he="שליפת רשומות מ-Airtable"
    ),
    "airtable_add": ToolMeta(
        name="airtable_add",
        roles_allowed={"owner", "staff"},
        tenant_scoped=True,
        description_he="הוספת רשומה ל-Airtable"
    ),
    "airtable_update": ToolMeta(
        name="airtable_update",
        roles_allowed={"owner", "staff"},
        tenant_scoped=True,
        description_he="עדכון רשומה ב-Airtable"
    ),

    # ── CRM — אנשי קשר ───────────────────────────
    "crm_add_contact": ToolMeta(
        name="crm_add_contact",
        roles_allowed={"owner", "staff"},
        description_he="הוספת איש קשר חדש"
    ),
    "crm_find_contact": ToolMeta(
        name="crm_find_contact",
        roles_allowed={"owner", "staff"},
        read_only=True,
        description_he="חיפוש איש קשר"
    ),
    "crm_list_contacts": ToolMeta(
        name="crm_list_contacts",
        roles_allowed={"owner", "staff"},
        read_only=True,
        description_he="רשימת אנשי קשר"
    ),
    "crm_update_last_contact": ToolMeta(
        name="crm_update_last_contact",
        roles_allowed={"owner", "staff"},
        description_he="עדכון תאריך יצירת קשר"
    ),

    # ── CRM — עסקאות ─────────────────────────────
    "crm_add_deal": ToolMeta(
        name="crm_add_deal",
        roles_allowed={"owner", "staff"},
        description_he="הוספת עסקה חדשה"
    ),
    "crm_list_deals": ToolMeta(
        name="crm_list_deals",
        roles_allowed={"owner", "staff"},
        read_only=True,
        description_he="רשימת עסקאות"
    ),
    "crm_update_deal_status": ToolMeta(
        name="crm_update_deal_status",
        roles_allowed={"owner", "staff"},
        description_he="עדכון סטטוס עסקה"
    ),

    # ── CRM — תשלומים ────────────────────────────
    "crm_add_payment": ToolMeta(
        name="crm_add_payment",
        roles_allowed={"owner", "staff"},
        description_he="הוספת תשלום צפוי"
    ),
    "crm_upcoming_payments": ToolMeta(
        name="crm_upcoming_payments",
        roles_allowed={"owner", "staff"},
        read_only=True,
        description_he="תשלומים קרובים"
    ),
    "crm_overdue_payments": ToolMeta(
        name="crm_overdue_payments",
        roles_allowed={"owner", "staff"},
        read_only=True,
        description_he="תשלומים באיחור"
    ),
    "crm_mark_payment_paid": ToolMeta(
        name="crm_mark_payment_paid",
        roles_allowed={"owner", "staff"},
        requires_approval=True,
        description_he="סימון תשלום כשולם"
    ),
}


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
    """זורק ToolDenied אם identity לא מורשה."""
    meta = _REGISTRY.get(tool_name)
    if not meta:
        raise ToolDenied(f"כלי לא קיים ב-Registry: {tool_name}")
    if identity.role not in meta.roles_allowed:
        raise ToolDenied(f"❌ {identity.role} אינו מורשה להפעיל '{tool_name}'")
    return meta


def needs_approval(tool_name: str) -> bool:
    meta = _REGISTRY.get(tool_name)
    return meta.requires_approval if meta else False


def is_high_risk(tool_name: str) -> bool:
    meta = _REGISTRY.get(tool_name)
    return meta.high_risk if meta else False


def all_tools_for_role(role: str) -> list[str]:
    return [name for name, meta in _REGISTRY.items() if role in meta.roles_allowed]
