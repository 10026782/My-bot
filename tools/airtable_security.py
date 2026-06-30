# airtable_security.py
# Central enforcement layer for all Airtable tools.
#
# כלל ברזל: כל external identity (client/supplier) רואה
# רק רשומות שה-tenant_id שלהן תואם ל-identity.tenant_id.
#
# owner/staff — עוברים ללא סינון (אבל מלוגגים).
# unknown tenant → PermissionError קשיח (לא fallback שקט).

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from identity import Identity

logger = logging.getLogger(__name__)


class TenantScopeViolation(PermissionError):
    """זריקה כשיש ניסיון גישה ללא tenant context תקין."""


# ══════════════════════════════════════════════════
# Leads Write Gate — BUG-B FIX
# כתיבה ישירה ל-Leads מה-Agent אסורה.
# Lead inbound נוצר רק דרך capture_inbound_lead().
# Lead Events נכתבים רק דרך capture_lead_event().
# ══════════════════════════════════════════════════

_LEADS_WRITE_OPS = {"airtable_add", "airtable_update", "airtable_patch"}
_LEADS_TABLE_NAMES = {"Leads", "leads"}  # aliases שה-gateway מכיר


class LeadsDirectWriteBlocked(PermissionError):
    """זריקה כשה-Agent מנסה לכתוב ל-Leads ישירות."""


def enforce_leads_write_gate(
    tool_name: str,
    params: dict,
    source: str = "agent",
) -> None:
    """
    חוסם כתיבה ישירה ל-Leads מה-Agent.

    מותר:
      - source="lead_capture"  → capture_inbound_lead
      - source="lead_event"    → capture_lead_event
      - source="lead_scoring"  → scoring update

    חסום:
      - source="agent" + airtable_add/update/patch + table=Leads

    קוראים: dispatcher.py לפני כל write tool.
    """
    if tool_name not in _LEADS_WRITE_OPS:
        return  # לא פעולת כתיבה — לא רלוונטי

    table = params.get("table", "") or params.get("fields", {})
    table_name = table if isinstance(table, str) else ""

    if table_name not in _LEADS_TABLE_NAMES:
        return  # לא טבלת Leads

    if source in ("lead_capture", "lead_event", "lead_scoring", "crm"):
        return  # מקור מורשה

    # source="agent" + Leads write → חסום
    logger.error(
        f"[LeadsWriteGate] BLOCKED direct Leads write | "
        f"tool={tool_name} source={source} table={table_name}"
    )
    raise LeadsDirectWriteBlocked(
        f"❌ כתיבה ישירה ל-Leads חסומה. "
        f"השתמש ב-capture_inbound_lead() בלבד. "
        f"(tool={tool_name} source={source})"
    )


def enforce_tenant_scope(
    tool_name: str,
    identity: "Identity",
    params: dict,
) -> dict:
    """
    Central enforcement for all tenant-scoped Airtable tools.

    מה שעושה:
    - owner/staff  → עובר, רק log
    - client/supplier → מוסיף filterByFormula לפי tenant_id
    - אין tenant_id  → PermissionError קשיח (לא fallback שקט)

    עקרון: AND() עם filter קיים — לא מחליף, משלב.
    זה מונע מצב שבו Claude שולח filter "חכם" שעוקף את tenant.
    """
    params = dict(params)  # לא מוטציה של המקור

    # ── owner / staff — מותר הכל, רק log ───────────
    if identity.is_internal:
        logger.debug(f"[airtable_security] internal access | tool={tool_name} | {identity.memory_key}")
        return params

    # ── external: client / supplier ─────────────────
    tenant_id = getattr(identity, "tenant_id", None)

    if not tenant_id or tenant_id == "unknown":
        logger.error(
            f"[airtable_security] BLOCKED: no valid tenant_id | "
            f"tool={tool_name} | role={identity.role} | chat={identity.user_id}"
        )
        raise TenantScopeViolation(
            f"❌ גישה נחסמה: אין הקשר tenant תקין עבור '{tool_name}'."
        )

    # בנה tenant filter
    tenant_filter = f"{{tenant_id}}='{tenant_id}'"

    existing = params.get("filterByFormula", "").strip()
    if existing:
        # AND() — לא מחליפים filter קיים, משלבים
        params["filterByFormula"] = f"AND({existing}, {tenant_filter})"
        logger.info(
            f"[airtable_security] tenant filter merged | "
            f"tool={tool_name} | tenant={tenant_id} | formula={params['filterByFormula']}"
        )
    else:
        params["filterByFormula"] = tenant_filter
        logger.info(
            f"[airtable_security] tenant filter applied | "
            f"tool={tool_name} | tenant={tenant_id}"
        )

    return params


def audit_log_airtable(
    tool_name: str,
    identity: "Identity",
    params: dict,
    result_snippet: object = "",   # BUG-A FIX: מקבל כל טיפוס — dict, str, None
) -> None:
    """
    Audit log לכל פעולת Airtable — read ו-write כאחד.
    לא חוסם, רק מתעד. עתידי: ישלח ל-DB / Sentry.

    BUG-A FIX: result_snippet הוגדר כ-str, אבל dispatcher מעביר
    את result כמו שהוא (dict). dict[:60] → TypeError: unhashable type: 'slice'.
    תיקון: המרה ל-str לפני slicing. Audit לעולם לא שובר פעולה עסקית.
    """
    try:
        safe_result = str(result_snippet)[:60]  # בטוח לכל טיפוס
        logger.info(
            f"[AUDIT] airtable | tool={tool_name} | "
            f"tenant={identity.tenant_id} | user={identity.user_id} | "
            f"role={identity.role} | "
            f"table={params.get('table','?')} | "
            f"result={safe_result}"
        )
    except Exception as _audit_err:
        # Audit failure לעולם לא זורק החוצה — רק מתועד
        logger.warning(f"[AUDIT] log failed for {tool_name}: {_audit_err}")
