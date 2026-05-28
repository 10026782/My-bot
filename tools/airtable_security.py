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
    result_snippet: str = "",
) -> None:
    """
    Audit log לכל פעולת Airtable — read ו-write כאחד.
    לא חוסם, רק מתעד. עתידי: ישלח ל-DB / Sentry.
    """
    logger.info(
        f"[AUDIT] airtable | tool={tool_name} | "
        f"tenant={identity.tenant_id} | user={identity.user_id} | "
        f"role={identity.role} | "
        f"table={params.get('table','?')} | "
        f"result={result_snippet[:60]}"
    )
