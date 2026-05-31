# tools/airtable_tools.py
import os
import httpx
import logging
from guards.circuit_breaker import with_airtable_breaker

logger = logging.getLogger(__name__)

_AIRTABLE_FORBIDDEN_FIELDS = {"tenant_id", "tenant", "owner_id"}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('AIRTABLE_API_KEY', '')}",
        "Content-Type":  "application/json"
    }

def _base() -> str:
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    if not base:
        raise RuntimeError("AIRTABLE_BASE_ID לא מוגדר")
    return base


def airtable_get(table: str, filter_formula: str = "") -> str:
    with with_airtable_breaker():
        params = {}
        if filter_formula:
            params["filterByFormula"] = filter_formula
        r = httpx.get(f"https://api.airtable.com/v0/{_base()}/{table}",
                      headers=_headers(), params=params, timeout=10)
        if r.status_code != 200:
            return f"❌ Airtable error {r.status_code}: {r.text[:150]}"
        records = r.json().get("records", [])
        if not records:
            return f"📭 אין רשומות בטבלה '{table}'."
        result = f"📊 {table} — {len(records)} רשומות:\n"
        for rec in records[:15]:
            fields = " | ".join(f"{k}: {v}" for k, v in rec.get("fields", {}).items())
            result += f"• [{rec['id']}] {fields}\n"
        return result


def airtable_add(table: str, fields: dict) -> str:
    fields = {k: v for k, v in fields.items() if k not in _AIRTABLE_FORBIDDEN_FIELDS}
    with with_airtable_breaker():
        r = httpx.post(f"https://api.airtable.com/v0/{_base()}/{table}",
                       headers=_headers(), json={"fields": fields}, timeout=10)
        if r.status_code in [200, 201]:
            return f"✅ רשומה נוספה | ID: {r.json().get('id','?')}"
        return f"❌ Airtable error {r.status_code}: {r.text[:150]}"


def airtable_get_schema() -> str:
    """קורא את כל הטבלאות והשדות מ-Airtable Meta API בזמן אמת."""
    with with_airtable_breaker():
        base = _base()
        r = httpx.get(
            f"https://api.airtable.com/v0/meta/bases/{base}/tables",
            headers=_headers(),
            timeout=10
        )
        if r.status_code != 200:
            return f"❌ Meta API error {r.status_code}: {r.text[:150]}"

        tables = r.json().get("tables", [])
        if not tables:
            return "📭 לא נמצאו טבלאות בבסיס הנתונים."

        result = f"📊 נמצאו {len(tables)} טבלאות:\n\n"
        for t in tables:
            fields = [f["name"] for f in t.get("fields", [])]
            result += f"• {t['name']}\n"
            result += f"  שדות: {', '.join(fields)}\n\n"

        return result.strip()


def airtable_update(table: str, record_id: str, fields: dict) -> str:
    fields = {k: v for k, v in fields.items() if k not in _AIRTABLE_FORBIDDEN_FIELDS}
    with with_airtable_breaker():
        r = httpx.patch(f"https://api.airtable.com/v0/{_base()}/{table}/{record_id}",
                        headers=_headers(), json={"fields": fields}, timeout=10)
        if r.status_code == 200:
            return f"✅ רשומה {record_id} עודכנה."
        return f"❌ Airtable error {r.status_code}: {r.text[:150]}"
