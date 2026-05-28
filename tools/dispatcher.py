import os
import logging
import requests

logger = logging.getLogger(__name__)


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


def dispatch_tool(name: str, inputs: dict, tenant_id: str = "boss_hq") -> str:
    match name:

        # ─── Knowledge ───────────────────────────────────────────────────────
        case "add_knowledge":
            from knowledge_engine import knowledge_engine
            ok = knowledge_engine.add_fact(tenant_id, inputs["fact"])
            return "✅ עובדה נוספה" if ok else "❌ שגיאה בשמירה"

        # ─── Airtable ────────────────────────────────────────────────────────
        case "airtable_get":
            creds_err = _airtable_creds_ok()
            if creds_err:
                return creds_err
            table = inputs["table"]
            params: dict = {"maxRecords": inputs.get("max_records", 10)}
            if inputs.get("filter_formula"):
                params["filterByFormula"] = inputs["filter_formula"]
            try:
                r = requests.get(_airtable_url(table), headers=_airtable_headers(),
                                 params=params, timeout=10)
                err = _airtable_check_response(r, table)
                if err:
                    return err
                records = r.json().get("records", [])
                if not records:
                    filter_info = f" (סינון: {inputs['filter_formula']})" if inputs.get("filter_formula") else ""
                    return f"✅ החיפוש הצליח — אין רשומות בטבלה '{table}'{filter_info}. זו תוצאה תקינה, לא שגיאה."
                lines = [f"נמצאו {len(records)} רשומות מטבלה '{table}':"]
                for rec in records:
                    fields  = rec.get("fields", {})
                    rec_id  = rec.get("id", "")
                    fstr    = " | ".join(f"{k}: {v}" for k, v in fields.items())
                    lines.append(f"[{rec_id}] {fstr}")
                return "\n".join(lines)
            except Exception as e:
                logger.error(f"airtable_get error: {e}")
                return f"❌ שגיאה: {e}"

        case "airtable_add":
            creds_err = _airtable_creds_ok()
            if creds_err:
                return creds_err
            table  = inputs["table"]
            fields = inputs.get("fields", {})
            try:
                r = requests.post(_airtable_url(table), headers=_airtable_headers(),
                                  json={"fields": fields}, timeout=10)
                err = _airtable_check_response(r, table)
                if err:
                    return err
                rec_id = r.json().get("id", "")
                return f"✅ רשומה נוצרה בטבלה '{table}' — ID: {rec_id}"
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
                return f"✅ רשומה {record_id} עודכנה בטבלה '{table}'"
            except Exception as e:
                logger.error(f"airtable_update error: {e}")
                return f"❌ שגיאה: {e}"

        # ─── Gmail ───────────────────────────────────────────────────────────
        case "gmail_draft":
            from tools.google_tools import gmail_send
            return gmail_send(inputs["to"], inputs["subject"], inputs["body"])

        case "gmail_send_draft":
            from tools.google_tools import gmail_send_draft
            return gmail_send_draft(inputs["draft_id"])

        case "gmail_read":
            from tools.google_tools import gmail_read
            return gmail_read(inputs.get("max_results", 5))

        # ─── Google Drive ─────────────────────────────────────────────────────
        case "search_drive":
            from tools.google_tools import drive_search
            return drive_search(inputs["query"])

        case "read_drive_file":
            from tools.google_tools import drive_read_file
            return drive_read_file(inputs["file_name"])

        # ─── Google Calendar ──────────────────────────────────────────────────
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

        # ─── Google Sheets ────────────────────────────────────────────────────
        case "sheets_append":
            from tools.google_tools import sheets_append
            return sheets_append(inputs["spreadsheet_name"], inputs["row_data"])

        case _:
            return f"❌ כלי לא מוכר: {name}"
