# tools/dispatcher.py — Tool Dispatcher v2
# נקודת כניסה יחידה לכל הכלים.
#
# זרימה: enforce(tool, identity) → dispatch_tool(tool, inputs, identity)

from __future__ import annotations
import logging
import os
import urllib.parse
from typing import TYPE_CHECKING

import httpx

from action_validator import ActionBlocked, validate_action

from .drive_tools    import search_drive, read_drive_file
from .calendar_tools import calendar_get_events, calendar_create_event
from .gmail_tools    import gmail_draft, gmail_send_draft, gmail_read
from .sheets_tools   import sheets_append
from .airtable_tools    import airtable_get, airtable_add, airtable_update, airtable_get_schema, search_lead
from .airtable_security import TenantScopeViolation, audit_log_airtable, enforce_tenant_scope
from .contact_resolver  import resolve_contact

if TYPE_CHECKING:
    from identity import Identity

logger = logging.getLogger(__name__)


# שדות dedup לפי טבלה — מונע כתיבה כפולה
_DEDUP_FIELDS: dict[str, str] = {
    "משימות (Tasks)":    "כותרת המשימה",
    "Tasks":             "כותרת המשימה",
    "משימות ודד ליינים": "שם המשימה",
    "Deadlines":         "שם המשימה",
    "Leads":             "phone",
}

# מיפוי alias → שם אמיתי (mirrors airtable_tools._TABLE_ALIAS_MAP)
_ALIAS_MAP: dict[str, str] = {
    "Tasks":    "משימות (Tasks)",
    "Contacts": "אנשי קשר (Contacts)",
    "Deals":    "עסקאות (Deals)",
    "Expenses": "הוצאות (Expenses)",
    "Payments": "תשלומים (Payments)",
}


def _check_duplicate(real_table: str, field: str, value: str) -> dict | None:
    """מחזיר רשומה קיימת אם יש כפילות, אחרת None."""
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    key  = os.environ.get("AIRTABLE_API_KEY", "")
    if not base or not key:
        return None
    safe = str(value).replace("'", "\\'")
    try:
        r = httpx.get(
            f"https://api.airtable.com/v0/{base}/{urllib.parse.quote(real_table, safe='')}",
            headers={"Authorization": f"Bearer {key}"},
            params={"filterByFormula": f"{{{field}}}='{safe}'", "maxRecords": 1},
            timeout=5,
        )
        if r.status_code == 200:
            recs = r.json().get("records", [])
            return recs[0] if recs else None
    except Exception as e:
        logger.warning(f"[Dedup] {real_table}/{field}: {e}")
    return None


def dispatch_tool(name: str, inputs: dict, identity: "Identity | None" = None) -> str:
    """
    מקבל שם כלי + inputs + identity ומחזיר תוצאה כטקסט.

    identity מועברת לכלים שצריכים לסנן לפי tenant/user.
    כלים שלא צריכים אותה — מתעלמים ממנה.
    """
    tenant_id = identity.tenant_id if identity else "unknown"
    user_id   = identity.user_id   if identity else "unknown"

    logger.info(f"[Dispatch] {name} | tenant={tenant_id} user={user_id} | inputs={str(inputs)[:80]}")

    validation = validate_action(name, inputs)
    if isinstance(validation, ActionBlocked):
        logger.warning(
            f"[Dispatch] blocked by action_validator | "
            f"tool={name} tenant={tenant_id} user={user_id} reason={validation.reason}"
        )
        return validation.reason

    try:
        match name:

            # ── Drive ────────────────────────────────
            case "search_drive":
                return search_drive(inputs["query"])
            case "read_drive_file":
                return read_drive_file(inputs["file_name"])

            # ── Calendar ─────────────────────────────
            case "calendar_get_events":
                return calendar_get_events(inputs.get("days_ahead", 7))
            case "calendar_create_event":
                return calendar_create_event(
                    inputs["summary"],
                    inputs["start_time"],
                    inputs.get("duration_minutes", 60),
                    inputs.get("force", False),
                )

            # ── Gmail ─────────────────────────────────
            case "gmail_draft":
                return gmail_draft(inputs["to"], inputs["subject"], inputs["body"])
            case "gmail_send_draft":
                logger.warning(
                    f"[Dispatch] gmail_send_draft | "
                    f"tenant={tenant_id} user={user_id} draft_id={inputs.get('draft_id')}"
                )
                return gmail_send_draft(inputs["draft_id"])
            case "gmail_read":
                return gmail_read(inputs.get("max_results", 3))

            # ── Sheets ────────────────────────────────
            case "sheets_append":
                return sheets_append(inputs["sheet_name"], inputs["row_data"])

            # ── Airtable ─────────────────────────────
            case "airtable_get":
                if not identity:
                    logger.warning("[Dispatch] blocked airtable_get: missing identity")
                    return "❌ גישה נחסמה: אין זהות תקינה לקריאת Airtable."

                table = inputs["table"]
                filter_formula = inputs.get("filter", "").strip()
                params = {"table": table}

                if identity.is_external:
                    user_filter = f"{{user_id}}='{identity.user_id}'"
                    filter_formula = (
                        f"AND({filter_formula}, {user_filter})"
                        if filter_formula else user_filter
                    )

                if filter_formula:
                    params["filterByFormula"] = filter_formula

                try:
                    secured_params = enforce_tenant_scope("airtable_get", identity, params)
                except TenantScopeViolation as e:
                    audit_log_airtable("airtable_get", identity, params, f"blocked: {e}")
                    return str(e)

                secured_filter = secured_params.get("filterByFormula", "")
                result = airtable_get(table, secured_filter)
                audit_log_airtable("airtable_get", identity, secured_params, result)
                return result

            case "airtable_add":
                table  = inputs["table"]
                fields = dict(inputs["fields"])

                # Fix 1: dedup — מניעת רשומות כפולות
                real_t      = _ALIAS_MAP.get(table, table)
                dedup_field = _DEDUP_FIELDS.get(real_t) or _DEDUP_FIELDS.get(table)
                if dedup_field:
                    dedup_val = fields.get(dedup_field, "")
                    if dedup_val:
                        existing = _check_duplicate(real_t, dedup_field, str(dedup_val))
                        if existing:
                            f_data = existing.get("fields", {})
                            status = f_data.get("סטטוס", f_data.get("status", "?"))
                            return (
                                f"✋ כבר קיים: {dedup_field}='{dedup_val}' ב-{table}.\n"
                                f"סטטוס: {status} | ID: {existing.get('id','?')}\n"
                                f"לא נוצרה רשומה כפולה."
                            )

                # בלוק external users מכתיבה לטבלאות שאינן Leads
                if identity and identity.is_external and table != "Leads":
                    audit_log_airtable("airtable_add", identity, {"table": table}, "blocked: external write to non-lead table")
                    return f"❌ גישה נחסמה: אין הרשאה לכתוב לטבלה '{table}'."

                # הזרקת tenant_id רק לטבלאות שמכירות את השדה
                _TENANT_AWARE = {
                    "Leads",
                    "אנשי קשר (Contacts)", "Contacts",
                    "עסקאות (Deals)",       "Deals",
                    "תשלומים (Payments)",   "Payments",
                }
                if identity and table in _TENANT_AWARE:
                    fields.setdefault("tenant_id", tenant_id)
                    if table == "Leads" and identity.domain_id:
                        fields.setdefault("domain", identity.domain_id)

                try:
                    enforce_tenant_scope("airtable_add", identity, {"table": table})
                except TenantScopeViolation as e:
                    audit_log_airtable("airtable_add", identity, {"table": table}, f"blocked: {e}")
                    return str(e)

                result = airtable_add(table, fields)
                audit_log_airtable("airtable_add", identity, {"table": table, "fields_keys": list(fields.keys())}, result)
                return result

            case "airtable_update":
                table     = inputs["table"]
                record_id = inputs["record_id"]
                fields    = dict(inputs["fields"])

                # בלוק external users מעדכון רשומות
                if identity and identity.is_external:
                    audit_log_airtable("airtable_update", identity, {"table": table, "record_id": record_id}, "blocked: external update")
                    return "❌ גישה נחסמה: אין הרשאה לעדכן רשומות."

                try:
                    enforce_tenant_scope("airtable_update", identity, {"table": table, "record_id": record_id})
                except TenantScopeViolation as e:
                    audit_log_airtable("airtable_update", identity, {"table": table, "record_id": record_id}, f"blocked: {e}")
                    return str(e)

                result = airtable_update(table, record_id, fields)
                audit_log_airtable("airtable_update", identity, {"table": table, "record_id": record_id}, result)
                return result

            case "airtable_get_schema":
                return airtable_get_schema()

            case "search_lead":
                return search_lead(inputs["name"])

            # ── Contact Resolver (N03) ────────────────
            case "resolve_contact":
                return resolve_contact(inputs["name_query"], identity)

            # ── D06 — Business Memory ─────────────────
            case "search_business_memory":
                from interaction_engine import search_business_memory  # type: ignore
                return search_business_memory(
                    inputs.get("query", ""),
                    domain=inputs.get("domain", ""),
                )

            # ── Unknown ───────────────────────────────
            case _:
                logger.warning(f"[Dispatch] Unknown tool: {name}")
                return f"⚠️ כלי לא מוכר: {name}"

    except KeyError as e:
        logger.error(f"[Dispatch] {name} missing param: {e}")
        return f"❌ פרמטר חסר בכלי {name}: {e}"
    except RuntimeError as e:
        logger.error(f"[Dispatch] {name} config error: {e}")
        return f"❌ {e}"
    except Exception as e:
        logger.error(f"[Dispatch] {name} error: {e}", exc_info=True)
        return f"❌ שגיאה בכלי {name}: {e}"
