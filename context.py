# context.py — Context Builder (Tier-1 Module)
# Pipeline: Identity → Policy+Truth+Tool+Interp+Interaction+UX → Context Layer → Assembly

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
    system_prompt:  str
    allowed_tools:  list
    memory_key:     str
    max_tokens:     int
    model:          str
    identity_label: str


# ══════════════════════════════════════════════════
# Tool Permission Map
# ══════════════════════════════════════════════════

_ROLE_TOOLS: dict = {
    Role.OWNER: {
        "add_knowledge",
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_send_draft", "gmail_read",
        "sheets_append",
        "airtable_get", "airtable_add", "airtable_update",
        # CRM — גישה מלאה
        "crm_add_contact", "crm_find_contact", "crm_list_contacts", "crm_update_last_contact",
        "crm_add_deal", "crm_list_deals", "crm_update_deal_status",
        "crm_add_payment", "crm_upcoming_payments", "crm_overdue_payments", "crm_mark_payment_paid",
    },
    Role.STAFF: {
        "search_drive", "read_drive_file",
        "calendar_get_events", "calendar_create_event",
        "gmail_draft", "gmail_read",
        "sheets_append",
        "airtable_get", "airtable_add", "airtable_update",
        # CRM — גישה מלאה (crm_mark_payment_paid דורש אישור — נשלט ע"י registry)
        "crm_add_contact", "crm_find_contact", "crm_list_contacts", "crm_update_last_contact",
        "crm_add_deal", "crm_list_deals", "crm_update_deal_status",
        "crm_add_payment", "crm_upcoming_payments", "crm_overdue_payments", "crm_mark_payment_paid",
    },
    Role.CLIENT: {
        "airtable_get",
    },
    Role.SUPPLIER: {
        "airtable_get",
    },
    Role.READONLY: set(),
}


def _filter_tools(role) -> list:
    allowed = _ROLE_TOOLS.get(role, set())
    return [t for t in TOOL_SCHEMAS if t["name"] in allowed]


# ══════════════════════════════════════════════════
# Airtable Schema Injection (Layer 8 supplement)
# ══════════════════════════════════════════════════

def _airtable_schema_block() -> str:
    try:
        from airtable_schema import format_schema_for_prompt
        schema = format_schema_for_prompt()
        if schema:
            return f"\n{schema}"
    except Exception:
        pass
    return ""


# ══════════════════════════════════════════════════
# System Prompt Assembly
# ══════════════════════════════════════════════════

def _assemble_prompt_owner(research_mode: bool) -> str:
    prompt = (
        STATIC_MANIFEST
        + build_context_layer()
        + dynamic_context.get()
        + _airtable_schema_block()
    )
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
        + f"\n═══════════════════════════════════════\n"
        f"ROLE — Staff: {identity.display_name or identity.user_id}\n"
        f"═══════════════════════════════════════\n"
        f"גישה לכלים תפעוליים. אין גישה לנתונים פיננסיים.\n"
        f"כל פעולה בלתי הפיכה — בקש אישור תחילה.\n"
    )


def _assemble_prompt_client(identity: "Identity") -> str:
    return (
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


def _select_model(identity: "Identity", text: str) -> tuple[str, int]:
    if identity.is_owner:
        if text.startswith("#"):
            return "claude-sonnet-4-6", 2000
        return "claude-haiku-4-5-20251001", 1000
    return "claude-haiku-4-5-20251001", 700


def build_context(identity: "Identity", user_text: str = "") -> AgentContext:
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

    logger.info(
        f"Context built | {identity.tenant_id}/{identity.user_id}/{identity.role} "
        f"| {model} | {max_tokens}tok | tools={len(allowed_tools)}"
    )

    return AgentContext(
        system_prompt  = system,
        allowed_tools  = allowed_tools,
        memory_key     = identity.memory_key,
        max_tokens     = max_tokens,
        model          = model,
        identity_label = f"{identity.tenant_id}/{identity.user_id}/{identity.role}",
    )


__all__ = ["AgentContext", "build_context", "check_tool_results"]
