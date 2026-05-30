# dispatcher.py — v2.2
# נקודת כניסה יחידה לכל הכלים.
# v2.2 — תיקון contact_type parameter + identity None guard.
#
# ─── שכבת אבטחה ───────────────────────────────────────
# 1. tool_registry.enforce()                        → הרשאת role (ב-app.py)
# 2. airtable_security.enforce_tenant_scope()       → tenant filter (כאן)
# 3. airtable_security.audit_log_airtable()         → לוג לכל פעולה (כאן)
# 4. gmail_read — owner בלבד (כאן + registry)

from __future__ import annotations
import os
import logging
import requests
from typing import TYPE_CHECKING

from .airtable_security import enforce_tenant_scope, audit_log_airtable, TenantScopeViolation

if TYPE_CHECKING:
    from identity import Identity

logger = logging.getLogger(__name__)

_TENANT_SCOPED_TOOLS = {"airtable_get", "airtable_add", "airtable_update"}

# מיפוי שמות קצרים → שמות מדויקים ב-Airtable
_TABLE_NAME_MAP: dict[str, str] = {
    "משימות":                      "משימות (Tasks)",
    "tasks":                        "משימות (Tasks)",
    "אנשי קשר":                    "אנשי קשר (Contacts)",
    "contacts":                     "אנשי קשר (Contacts)",
    "עסקאות":                      "עסקאות (Deals)",
    "deals":                        "עסקאות (Deals)",
    "תשלומים":                     "תשלומים (Payments)",
    "payments":                     "תשלומים (Payments)",
    "הוצאות":                      "הוצאות (Expenses)",
    "expenses":                     "הוצאות (Expenses)",
    "למידות":                      "למידות ותובנות (Learnings & Insights)",
    "learnings":                    "למידות ותובנות (Learnings & Insights)",
    "insights":                     "למידות ותובנות (Learnings & Insights)",
    "משימות ודד ליינים":           "משימות ודד ליינים",
    "deadlines":                    "משימות ודד ליינים",
}

def _resolve_table(name: str) -> str:
    """ממפה שם קצר/חלקי לשם המדויק ב-Airtable."""
    return _TABLE_NAME_MAP.get(name.strip(), name.strip())


# ──────────────────────────────────────────────────────────────────
# Airtable helpers
# ──────────────────────────────────────────────────────────────────

def _airtable_headers() -> dict:
    token = os.environ.get("AIRTABLE_API_KEY", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _airtable_url(table: str) -> str:
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    return f"https://api.airtable.com/v0/{base}/{requests.utils.quote(table)}"


def _airtable_creds_ok() -> str | None:
    if not os.environ.get("AIRTABLE_API_KEY") or not os.environ.get("AIRTABLE_BASE_ID"):
        return "❌ AIRTABLE_API_KEY או AIRTABLE_BASE_ID לא מוגדרים"
    return None


def _airtable_check_response(r, table: str) -> str | None:
    if r.status_code in (200, 201):
        return None
    if r.status_code == 403:
        return (
            f"❌ Airtable 403 — אין הרשאה לטבלה '{table}'.\n"
            f"ודא שה-Token כולל scope: data.records:read/write ואת ה-Base הספציפי.\n"
            f"AIRTABLE_BASE_ID = {os.environ.get('AIRTABLE_BASE_ID') or '(ריק!)'}"
        )
    if r.status_code == 401:
        return "❌ Airtable 401 — ה-AIRTABLE_API_KEY לא תקין או פג תוקף."
    if r.status_code == 404:
        return f"❌ Airtable 404 — טבלה '{table}' לא נמצאה."
    return f"❌ Airtable שגיאה {r.status_code}: {r.text[:200]}"


# ──────────────────────────────────────────────────────────────────
# Main dispatcher
# ──────────────────────────────────────────────────────────────────

def dispatch_tool(name: str, inputs: dict, identity: "Identity") -> str:
    """
    מקבל שם כלי + inputs + identity ומחזיר תוצאה כטקסט.
    identity חובה — לא optional.
    """
    if identity is None:
        logger.error(f"dispatch_tool called without identity: {name}")
        raise RuntimeError("identity required for all tool execution")

    try:
        # ── Tenant Scope Enforcement ────────────────────────────────
        if name in _TENANT_SCOPED_TOOLS:
            try:
                inputs = enforce_tenant_scope(name, identity, inputs)
            except TenantScopeViolation as e:
                logger.error(f"TenantScopeViolation: {name} | {identity.memory_key}")
                return str(e)

        # ── Dispatch ────────────────────────────────────────────────
        match name:

            # ─── Knowledge ─────────────────────────────────────────
            case "add_knowledge":
                from knowledge_engine import knowledge_engine
                fact = f"{inputs['key']}: {inputs['value']}"
                ok = knowledge_engine.add_fact(identity.tenant_id, fact)
                return "✅ עובדה נוספה" if ok else "❌ שגיאה בשמירה"

            # ─── Airtable ──────────────────────────────────────────
            case "airtable_get":
                creds_err = _airtable_creds_ok()
                if creds_err:
                    return creds_err
                table = _resolve_table(inputs["table"])
                params: dict = {"maxRecords": inputs.get("max_records", 10)}
                if inputs.get("filterByFormula"):
                    params["filterByFormula"] = inputs["filterByFormula"]
                elif inputs.get("filter_formula"):
                    params["filterByFormula"] = inputs["filter_formula"]
                try:
                    r = requests.get(_airtable_url(table), headers=_airtable_headers(),
                                     params=params, timeout=10)
                    err = _airtable_check_response(r, table)
                    if err:
                        return err
                    records = r.json().get("records", [])
                    if not records:
                        filter_info = f" (סינון: {params.get('filterByFormula','')})" if params.get("filterByFormula") else ""
                        return f"✅ החיפוש הצליח — אין רשומות בטבלה '{table}'{filter_info}. זו תוצאה תקינה, לא שגיאה."
                    lines = [f"נמצאו {len(records)} רשומות מטבלה '{table}':"]
                    for rec in records:
                        fields = rec.get("fields", {})
                        rec_id = rec.get("id", "")
                        fstr   = " | ".join(f"{k}: {v}" for k, v in fields.items())
                        lines.append(f"[{rec_id}] {fstr}")
                    result = "\n".join(lines)
                    audit_log_airtable(name, identity, inputs, result)
                    return result
                except Exception as e:
                    logger.error(f"airtable_get error: {e}")
                    return f"❌ שגיאה: {e}"

            case "airtable_add":
                creds_err = _airtable_creds_ok()
                if creds_err:
                    return creds_err
                table  = inputs["table"]
                fields = dict(inputs.get("fields", {}))
                if not identity.is_internal:
                    fields.setdefault("tenant_id", identity.tenant_id)
                try:
                    r = requests.post(_airtable_url(table), headers=_airtable_headers(),
                                      json={"fields": fields}, timeout=10)
                    err = _airtable_check_response(r, table)
                    if err:
                        return err
                    rec_id = r.json().get("id", "")
                    result = f"✅ רשומה נוצרה בטבלה '{table}' — ID: {rec_id}"
                    audit_log_airtable(name, identity, inputs, result)
                    return result
                except Exception as e:
                    logger.error(f"airtable_add error: {e}")
                    return f"❌ שגיאה: {e}"

            case "airtable_update":
                creds_err = _airtable_creds_ok()
                if creds_err:
                    return creds_err
                table     = inputs["table"]
                record_id = inputs["record_id"]
                fields    = inputs.get("fields", {})
                try:
                    r = requests.patch(f"{_airtable_url(table)}/{record_id}",
                                       headers=_airtable_headers(),
                                       json={"fields": fields}, timeout=10)
                    err = _airtable_check_response(r, table)
                    if err:
                        return err
                    result = f"✅ רשומה {record_id} עודכנה בטבלה '{table}'"
                    audit_log_airtable(name, identity, inputs, result)
                    return result
                except Exception as e:
                    logger.error(f"airtable_update error: {e}")
                    return f"❌ שגיאה: {e}"

            case "airtable_get_schema":
                creds_err = _airtable_creds_ok()
                if creds_err:
                    return creds_err
                base = os.environ.get("AIRTABLE_BASE_ID", "")
                try:
                    r = requests.get(
                        f"https://api.airtable.com/v0/meta/bases/{base}/tables",
                        headers=_airtable_headers(),
                        timeout=10,
                    )
                    if r.status_code != 200:
                        return f"❌ Meta API error {r.status_code}: {r.text[:150]}"
                    tables = r.json().get("tables", [])
                    if not tables:
                        return "📭 לא נמצאו טבלאות בבסיס הנתונים."
                    result = f"📊 נמצאו {len(tables)} טבלאות:\n\n"
                    for t in tables:
                        fields = [f["name"] for f in t.get("fields", [])]
                        result += f"• {t['name']}\n  שדות: {', '.join(fields)}\n\n"
                    return result.strip()
                except Exception as e:
                    logger.error(f"airtable_get_schema error: {e}")
                    return f"❌ שגיאה בקריאת סכמה: {e}"

            # ─── Gmail ─────────────────────────────────────────────
            case "gmail_draft":
                from tools.google_tools import gmail_send
                return gmail_send(inputs["to"], inputs["subject"], inputs["body"])

            case "gmail_send_draft":
                from tools.google_tools import gmail_send_draft
                return gmail_send_draft(inputs["draft_id"])

            case "gmail_read":
                if not identity.is_owner:
                    logger.warning(f"gmail_read blocked for role={identity.role}")
                    return "❌ gmail_read — מורשה לבעלים בלבד."
                from tools.google_tools import gmail_read
                return gmail_read(inputs.get("max_results", 3))

            # ─── Google Drive ───────────────────────────────────────
            case "search_drive":
                from tools.google_tools import drive_search
                return drive_search(inputs["query"])

            case "read_drive_file":
                from tools.google_tools import drive_read_file
                return drive_read_file(inputs["file_name"])

            # ─── Google Calendar ────────────────────────────────────
            case "calendar_get_events":
                from tools.google_tools import calendar_get_events
                return calendar_get_events(
                    inputs.get("max_results", 5),
                    inputs.get("days_ahead", 7),
                )

            case "calendar_create_event":
                from tools.google_tools import calendar_create_event
                return calendar_create_event(
                    inputs["summary"],
                    inputs["start_time"],
                    inputs.get("duration_minutes", 60),
                )

            # ─── Google Sheets ──────────────────────────────────────
            case "sheets_append":
                from tools.google_tools import sheets_append
                return sheets_append(inputs["sheet_name"], inputs["row_data"])

            # ─── CRM — Contacts ────────────────────────────────────
            case "crm_add_contact":
                from crm import crm_add_contact
                return crm_add_contact(
                    inputs["name"],
                    inputs.get("phone", ""),
                    inputs.get("email", ""),
                    inputs.get("contact_type", "Client"),   # ← contact_type (לא "type")
                    inputs.get("company", ""),
                    inputs.get("notes", ""),
                )

            case "crm_find_contact":
                from crm import crm_find_contact
                return crm_find_contact(inputs["query"], identity=identity)

            case "crm_list_contacts":
                from crm import crm_list_contacts
                return crm_list_contacts(inputs.get("contact_type", ""), identity=identity)

            case "crm_update_last_contact":
                from crm import crm_update_last_contact
                return crm_update_last_contact(inputs["record_id"])

            # ─── CRM — Deals ───────────────────────────────────────
            case "crm_add_deal":
                from crm import crm_add_deal
                return crm_add_deal(
                    inputs["name"],
                    inputs["address"],
                    float(inputs["price"]),
                    float(inputs["funding_cost_pct"]),
                    inputs.get("contact_id", ""),
                    inputs.get("deadline", ""),
                    inputs.get("notes", ""),
                )

            case "crm_update_deal_status":
                from crm import crm_update_deal_status
                return crm_update_deal_status(
                    inputs["record_id"],
                    inputs["status"],
                    inputs.get("notes", ""),
                )

            case "crm_list_deals":
                from crm import crm_list_deals
                return crm_list_deals(inputs.get("status", ""), identity=identity)

            # ─── CRM — Payments ────────────────────────────────────
            case "crm_add_payment":
                from crm import crm_add_payment
                return crm_add_payment(
                    inputs["name"],
                    float(inputs["amount"]),
                    inputs["due_date"],
                    inputs.get("deal_id", ""),
                    inputs.get("contact_id", ""),
                    inputs.get("notes", ""),
                )

            case "crm_upcoming_payments":
                from crm import crm_upcoming_payments
                return crm_upcoming_payments(inputs.get("days_ahead", 7), identity=identity)

            case "crm_mark_payment_paid":
                from crm import crm_mark_payment_paid
                return crm_mark_payment_paid(inputs["record_id"])

            case "crm_overdue_payments":
                from crm import crm_overdue_payments
                return crm_overdue_payments(identity=identity)

            case _:
                logger.error(f"Unknown tool called: {name}")
                return f"⚠️ כלי לא מוכר: {name}"

    except KeyError as e:
        logger.error(f"Tool {name} missing param: {e}")
        return f"❌ פרמטר חסר בכלי {name}: {e}"
    except RuntimeError as e:
        logger.error(f"Tool {name} auth/config error: {e}")
        return f"❌ {e}"
    except Exception as e:
        logger.error(f"Tool {name} error: {e}", exc_info=True)
        return f"❌ שגיאה בכלי {name}: {e}"
