import os
import logging
import requests

logger = logging.getLogger(__name__)

_AIRTABLE_BASE = os.environ.get("AIRTABLE_BASE_ID", "")
_AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")


def _airtable_headers() -> dict:
    return {
        "Authorization": f"Bearer {_AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def _airtable_url(table: str) -> str:
    return f"https://api.airtable.com/v0/{_AIRTABLE_BASE}/{requests.utils.quote(table)}"


def dispatch_tool(name: str, inputs: dict, tenant_id: str = "boss_hq") -> str:
    match name:

        case "add_knowledge":
            from knowledge_engine import knowledge_engine
            ok = knowledge_engine.add_fact(tenant_id, inputs["fact"])
            return "✅ עובדה נוספה" if ok else "❌ שגיאה בשמירה"

        case "airtable_get_records":
            if not _AIRTABLE_TOKEN or not _AIRTABLE_BASE:
                return "❌ AIRTABLE_TOKEN או AIRTABLE_BASE_ID לא מוגדרים"
            table = inputs["table"]
            params: dict = {"maxRecords": inputs.get("max_records", 10)}
            if inputs.get("filter_formula"):
                params["filterByFormula"] = inputs["filter_formula"]
            try:
                r = requests.get(
                    _airtable_url(table),
                    headers=_airtable_headers(),
                    params=params,
                    timeout=10,
                )
                if r.status_code != 200:
                    return f"❌ Airtable שגיאה {r.status_code}: {r.text[:200]}"
                records = r.json().get("records", [])
                if not records:
                    return f"לא נמצאו רשומות בטבלה '{table}'."
                lines = [f"נמצאו {len(records)} רשומות מטבלה '{table}':"]
                for rec in records:
                    fields = rec.get("fields", {})
                    rec_id = rec.get("id", "")
                    field_str = " | ".join(f"{k}: {v}" for k, v in fields.items())
                    lines.append(f"[{rec_id}] {field_str}")
                return "\n".join(lines)
            except Exception as e:
                logger.error(f"airtable_get_records error: {e}")
                return f"❌ שגיאה: {e}"

        case "airtable_create_record":
            if not _AIRTABLE_TOKEN or not _AIRTABLE_BASE:
                return "❌ AIRTABLE_TOKEN או AIRTABLE_BASE_ID לא מוגדרים"
            table = inputs["table"]
            fields = inputs.get("fields", {})
            try:
                r = requests.post(
                    _airtable_url(table),
                    headers=_airtable_headers(),
                    json={"fields": fields},
                    timeout=10,
                )
                if r.status_code not in (200, 201):
                    return f"❌ Airtable שגיאה {r.status_code}: {r.text[:200]}"
                rec_id = r.json().get("id", "")
                return f"✅ רשומה נוצרה בטבלה '{table}' — ID: {rec_id}"
            except Exception as e:
                logger.error(f"airtable_create_record error: {e}")
                return f"❌ שגיאה: {e}"

        case "airtable_update_record":
            if not _AIRTABLE_TOKEN or not _AIRTABLE_BASE:
                return "❌ AIRTABLE_TOKEN או AIRTABLE_BASE_ID לא מוגדרים"
            table = inputs["table"]
            record_id = inputs["record_id"]
            fields = inputs.get("fields", {})
            try:
                url = f"{_airtable_url(table)}/{record_id}"
                r = requests.patch(
                    url,
                    headers=_airtable_headers(),
                    json={"fields": fields},
                    timeout=10,
                )
                if r.status_code != 200:
                    return f"❌ Airtable שגיאה {r.status_code}: {r.text[:200]}"
                return f"✅ רשומה {record_id} עודכנה בטבלה '{table}'"
            except Exception as e:
                logger.error(f"airtable_update_record error: {e}")
                return f"❌ שגיאה: {e}"

        case _:
            return f"❌ כלי לא מוכר: {name}"
