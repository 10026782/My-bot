"""
airtable_schema.py — טוען סכמת טבלאות מ-Airtable ומזריק לsystem prompt.
דורש scope: schema.bases:read בPersonal Access Token.
"""

import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

_cache: dict = {"schema": None, "ts": 0}
_CACHE_TTL = 600  # 10 דקות


def fetch_schema() -> list[dict]:
    """שולף את כל הטבלאות והשדות מה-base דרך Airtable Metadata API."""
    if _cache["schema"] and (time.time() - _cache["ts"]) < _CACHE_TTL:
        return _cache["schema"]

    token = os.environ.get("AIRTABLE_API_KEY", "")
    base_id = os.environ.get("AIRTABLE_BASE_ID", "")

    if not token or not base_id:
        logger.warning("AIRTABLE_API_KEY or AIRTABLE_BASE_ID missing — schema unavailable")
        return []

    try:
        r = requests.get(
            f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning(f"Airtable schema fetch failed: {r.status_code} {r.text[:200]}")
            return []

        tables = r.json().get("tables", [])
        _cache["schema"] = tables
        _cache["ts"] = time.time()
        logger.info(f"Airtable schema loaded: {len(tables)} tables")
        return tables

    except Exception as e:
        logger.error(f"fetch_schema error: {e}")
        return []


def format_schema_for_prompt() -> str:
    """מחזיר מחרוזת קריאה של הסכמה להזרקה לsystem prompt."""
    tables = fetch_schema()
    if not tables:
        return ""

    lines = ["מבנה הטבלאות ב-Airtable (שמות מדויקים — השתמש בהם בדיוק):"]
    for table in tables:
        name = table.get("name", "")
        fields = [f.get("name", "") for f in table.get("fields", [])]
        fields_str = " | ".join(fields)
        lines.append(f"• {name}: {fields_str}")

    return "\n".join(lines)


def invalidate_cache():
    """מרוקן את הcache — לקריאה מחדש בבקשה הבאה."""
    _cache["schema"] = None
    _cache["ts"] = 0


# ══════════════════════════════════════════════════
# Schema constants — שמות טבלאות ושדות ב-Airtable
# crm.py מייבא מכאן — מקור יחיד לאמת
# ══════════════════════════════════════════════════

class Tables:
    CONTACTS = "Contacts"
    DEALS    = "Deals"
    PAYMENTS = "Payments"


class ContactFields:
    NAME         = "Name"
    PHONE        = "Phone"
    EMAIL        = "Email"
    COMPANY      = "Company"
    TYPE         = "Type"
    STATUS       = "Status"
    LAST_CONTACT = "Last Contact"
    NOTES        = "Notes"


class ContactType:
    CLIENT   = "Client"
    SUPPLIER = "Supplier"
    PARTNER  = "Partner"
    OTHER    = "Other"


class ContactStatus:
    ACTIVE   = "Active"
    INACTIVE = "Inactive"


class DealFields:
    NAME         = "Name"
    ADDRESS      = "Address"
    STATUS       = "Status"
    PRICE        = "Price"
    FUNDING_COST = "Funding Cost %"
    ROI          = "ROI %"
    RISK_LEVEL   = "Risk Level"
    CONTACT      = "Contact"
    DEADLINE     = "Deadline"
    NOTES        = "Notes"


class DealStatus:
    PROSPECT      = "Prospect"
    DUE_DILIGENCE = "Due Diligence"
    ACTIVE        = "Active"
    CLOSED        = "Closed"
    CANCELLED     = "Cancelled"


class RiskLevel:
    LOW    = "Low"
    MEDIUM = "Medium"
    HIGH   = "High"


class PaymentFields:
    NAME     = "Name"
    AMOUNT   = "Amount"
    DUE_DATE = "Due Date"
    STATUS   = "Status"
    DEAL     = "Deal"
    CONTACT  = "Contact"
    NOTES    = "Notes"


class PaymentStatus:
    PENDING  = "Pending"
    PAID     = "Paid"
    OVERDUE  = "Overdue"


def validate_funding_cost(pct: float) -> tuple[bool, str]:
    """
    חוק ברזל: מימון מעל 9% — חסום אוטומטית.
    מחזיר (ok, warning_message).
    """
    if pct > 9:
        return False, (
            f"⚠️ עלות מימון {pct}% חורגת מהמותר (9%).\n"
            "🔴 חוק ברזל: עסקאות עם מימון >9% — חסומות אוטומטית."
        )
    return True, ""
