# context.py — Context Builder (Tier-1 Module)
# הלב של המערכת — בונה context שלם לפי Identity.
#
# Pipeline: Identity → Policy+Truth+Tool+Interp+Interaction+UX → Context Layer → Assembly
#
# אותו Agent. אותם Tools. אותו LLM.
# Context אחר = תוצאה אחרת לחלוטין.

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from identity import Identity

from identity import Role
from core_knowledge import (
    STATIC_MANIFEST,
    build_context_layer,
    dynamic_context,
    check_tool_results,
)
from tools.schemas import TOOL_SCHEMAS

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Context Output
# ══════════════════════════════════════════════════

@dataclass
class AgentContext:
    system_prompt:      str
    allowed_tools:      list       # schemas מסוננים לפי role
    memory_key:         str        # מפתח לשליפת היסטוריה
    max_tokens:         int
    model:              str
    identity_label:     str        # לlog בלבד
    user_context_hint:  str = ""   # שורת הקשר דינמי לתחילת הודעת המשתמש


# ══════════════════════════════════════════════════
# Tool Permission Map
# ══════════════════════════════════════════════════

_CRM_TOOLS = {
    "crm_add_contact", "crm_find_contact",
    "crm_list_contacts", "crm_update_last_contact",
    "crm_add_deal", "crm_update_deal_status", "crm_list_deals",
    "crm_add_payment", "crm_upcoming_payments",
    "crm_mark_payment_paid", "crm_overdue_payments",
}

_ROLE_TOOLS: dict[str, set[str]] = {
    Role.OWNER: {
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_send_draft", "gmail_read",
        "sheets_append",
        "airtable_get", "airtable_add", "airtable_update",
        "add_knowledge",
        *_CRM_TOOLS,
    },
    Role.STAFF: {
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_read",
        "sheets_append",
        "airtable_get", "airtable_add", "airtable_update",
        # CRM — קריאה + עדכון בסיסי בלבד (לא יצירה/מחיקה)
        "crm_find_contact", "crm_list_contacts",
        "crm_update_last_contact", "crm_list_deals",
        "crm_upcoming_payments", "crm_overdue_payments",
    },
    Role.CLIENT: {
        "airtable_get",
        "crm_find_contact",
    },
    Role.SUPPLIER: {
        "airtable_get",
    },
    Role.READONLY: set(),
}


def _filter_tools(role: str) -> list:
    allowed = _ROLE_TOOLS.get(role, set())
    return [t for t in TOOL_SCHEMAS if t["name"] in allowed]


# ══════════════════════════════════════════════════
# System Prompt Assembly — Layer 8
# STATIC (1-6) + CONTEXT (7) + DYNAMIC (8) + ROLE
# ══════════════════════════════════════════════════

def _airtable_schema_hint() -> str:
    """שמות טבלאות מדויקים להזרקה לsystem prompt."""
    from airtable_schema import Tables
    return (
        "\n═══════════════════════════════════════\n"
        "שמות טבלאות Airtable (השתמש בשמות המדויקים האלה בלבד):\n"
        f"• אנשי קשר → \"{Tables.CONTACTS}\"\n"
        f"• עסקאות   → \"{Tables.DEALS}\"\n"
        f"• תשלומים  → \"{Tables.PAYMENTS}\"\n"
        f"• משימות   → \"{Tables.TASKS}\"\n"
        f"• הוצאות   → \"{Tables.EXPENSES}\"\n"
        f"• למידות   → \"{Tables.LEARNINGS}\"\n"
        "═══════════════════════════════════════\n"
    )


def _assemble_prompt_owner(research_mode: bool) -> str:
    """
    OWNER — גישה מלאה.
    Assembly: Layers 1-6 (static) + Layer 7 (datetime) + Layer 8 (dynamic data) + role addendum
    """
    prompt = (
        STATIC_MANIFEST          # Layers 1-6
        + build_context_layer()  # Layer 7 — זמן אמת (לא cached)
        + dynamic_context.get()  # Layer 8 — נתונים דינמיים
        + _airtable_schema_hint()  # שמות טבלאות מדויקים
    )

    # Role addendum
    prompt += (
        "\n═══════════════════════════════════════\n"
        "ROLE — Owner (אליהו חזן)\n"
        "═══════════════════════════════════════\n"
        "גישה מלאה לכל הכלים והנתונים.\n"
        "תמיד סיים ב: ➡️ הצעד הבא המומלץ\n"
    )

    if research_mode:
        prompt += "\n🔬 מצב מחקר — נתח לעומק, ענה בהרחבה אסטרטגית."

    return prompt


def _assemble_prompt_staff(identity: "Identity") -> str:
    return (
        STATIC_MANIFEST
        + build_context_layer()
        + _airtable_schema_hint()
        + f"\n═══════════════════════════════════════\n"
        f"ROLE — Staff: {identity.display_name or identity.user_id}\n"
        f"═══════════════════════════════════════\n"
        f"גישה לכלים תפעוליים. אין גישה לנתונים פיננסיים.\n"
        f"כל פעולה בלתי הפיכה — בקש אישור תחילה.\n"
    )


def _assemble_prompt_client(identity: "Identity") -> str:
    return (
        # לקוח — חלק מהשכבות בלבד (UX + Truth)
        "אתה נציג שירות מקצועי ומנומס של Boss HQ.\n"
        f"לקוח: {identity.display_name or identity.user_id} | "
        f"tenant: {identity.tenant_id}\n"
        "הצג רק מידע הרלוונטי ללקוח זה בלבד. "
        "אל תחשוף מידע על לקוחות אחרים.\n"
        "ענה בעברית, בצורה עניינית וחיובית. "
        "אל תמציא נתונים — אם אין מידע, אמור זאת.\n"
        + build_context_layer()
    )


def _assemble_prompt_supplier(identity: "Identity") -> str:
    return (
        f"אתה ממשק תפעולי מול ספק: {identity.display_name or identity.user_id}\n"
        f"הצג רק הזמנות ו-PO הרלוונטיים לספק זה.\n"
        "אל תמציא נתונים — אם אין מידע, אמור זאת.\n"
        + build_context_layer()
    )


def _assemble_prompt_readonly(_: "Identity") -> str:
    return "אתה יכול לקרוא מידע כללי בלבד. לא ניתן לבצע פעולות."


# ══════════════════════════════════════════════════
# Model / Token Selection
# ══════════════════════════════════════════════════

def _select_model(identity: "Identity", text: str) -> tuple[str, int]:
    if identity.is_owner:
        if text.startswith("#"):
            return "claude-sonnet-4-6", 2000
        return "claude-haiku-4-5-20251001", 1000
    return "claude-haiku-4-5-20251001", 700


# ══════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════

def build_context(identity: "Identity", user_text: str = "") -> AgentContext:
    """
    בונה AgentContext מלא לפי Identity.
    מממש את ה-8 שכבות:
    1-6 (STATIC_MANIFEST) + 7 (datetime) + 8 (dynamic+role)
    """
    research_mode = user_text.startswith("#") and identity.is_owner
    model, max_tokens = _select_model(identity, user_text)

    match identity.role:
        case Role.OWNER:
            system = _assemble_prompt_owner(research_mode)
        case Role.STAFF:
            system = _assemble_prompt_staff(identity)
        case Role.CLIENT:
            system = _assemble_prompt_client(identity)
        case Role.SUPPLIER:
            system = _assemble_prompt_supplier(identity)
        case _:
            system = _assemble_prompt_readonly(identity)

    allowed_tools = _filter_tools(identity.role)

    # build dynamic hint from core_knowledge (injected as user message prefix)
    hint_parts = []
    try:
        from core_knowledge import build_context_layer, dynamic_context
        ctx_line  = build_context_layer()
        data_line = dynamic_context.get()
        hint_parts = [p for p in [ctx_line, data_line] if p]
    except Exception:
        pass
    user_context_hint = "\n".join(hint_parts)

    logger.info(
        f"Context built | {identity.tenant_id}/{identity.user_id}/{identity.role} "
        f"| {model} | {max_tokens}tok | tools={len(allowed_tools)}"
    )

    return AgentContext(
        system_prompt     = system,
        allowed_tools     = allowed_tools,
        memory_key        = identity.memory_key,
        max_tokens        = max_tokens,
        model             = model,
        identity_label    = f"{identity.tenant_id}/{identity.user_id}/{identity.role}",
        user_context_hint = user_context_hint,
    )


# ══════════════════════════════════════════════════
# Re-export Grounding Validator לשימוש ב-app.py
# ══════════════════════════════════════════════════

__all__ = ["AgentContext", "build_context", "check_tool_results"]
