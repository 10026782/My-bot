# tools/airtable_tools.py
import os
import logging
from typing import Any
from guards.circuit_breaker import with_airtable_breaker

logger = logging.getLogger(__name__)


def _tool_result(
    *,
    ok: bool,
    tool: str,
    external_id: str = "",
    evidence: dict[str, Any] | None = None,
    user_message: str = "",
) -> dict:
    """Structured C53-A result contract for Airtable write tools."""
    return {
        "ok": ok,
        "tool": tool,
        "external_id": external_id or "",
        "evidence": evidence or {},
        "user_message": user_message,
    }


def _audit(tool_name: str, table: str, record_id: str = "", result: str = "") -> None:
    """לוג audit לכל פעולת Airtable — לא חוסם אם נכשל."""
    try:
        logger.info(
            "[AUDIT:airtable] tool=%s table=%s record=%s result=%s",
            tool_name, table, record_id or "-", (result or "")[:80],
        )
    except Exception:
        pass

# _TABLE_ALIAS_MAP מיובא מ-airtable_schema — מקור אמת יחיד
from airtable_schema import TABLE_ALIASES as _TABLE_ALIAS_MAP


def _resolve_table(table: str) -> str:
    """מתרגם alias אנגלי לשם הטבלה האמיתי ב-Airtable."""
    return _TABLE_ALIAS_MAP.get(table, table)


# שדות linked-record לפי טבלה: field_name → linked_table_name
_LINKED_RECORD_FIELDS: dict[str, dict[str, str]] = {
    "Roadmap_Tasks": {
        "World": "Worlds",
        "Quest": "Quests",
    },
    "Weekly_Goals": {
        "World": "Worlds",
    },
    "Daily_Tasks": {
        "Quest": "Quests",
    },
    "Quests": {
        "World": "Worlds",
    },
    "Coins_Log": {
        "Quest": "Quests",
    },
}


def _lookup_record_id(linked_table: str, name: str) -> str | None:
    """
    מחפש רשומה לפי שם ב-linked_table.
    מחזיר record_id ("recXXX") אם נמצא, אחרת None.
    """
    try:
        from tools.airtable_read_adapter import list_records_page

        safe = name.replace("'", "\\'")
        records, _ = list_records_page(
            linked_table,
            f"{{Name}}='{safe}'",
            max_records=1,
            timeout=10,
        )
        return records[0]["id"] if records else None
    except Exception as e:
        status_code = getattr(e, "status_code", None)
        if status_code is not None:
            logger.warning(f"airtable: lookup failed [{linked_table}] {status_code}")
        else:
            logger.warning(f"airtable: lookup exception [{linked_table}/{name}]: {e}")
        return None


def _resolve_linked_fields(table: str, fields: dict) -> dict:
    """
    עבור טבלאות עם שדות linked-record:
    אם הערך הוא string (שם תצוגה) במקום ["recXXX"] — מבצע חיפוש ומחליף.
    שדות שלא נמצאו מוסרים כדי למנוע INVALID_RECORD_ID.
    """
    link_map = _LINKED_RECORD_FIELDS.get(table)
    if not link_map:
        return fields

    result = dict(fields)
    for field, linked_table in link_map.items():
        val = result.get(field)
        if val is None:
            continue
        # כבר בפורמט נכון — list של IDs
        if isinstance(val, list):
            continue
        # ערך string — צריך לחפש
        if isinstance(val, str):
            rec_id = _lookup_record_id(linked_table, val)
            if rec_id:
                result[field] = [rec_id]
                logger.info(f"airtable: resolved {field}='{val}' → {rec_id}")
            else:
                logger.warning(
                    f"airtable: '{val}' לא נמצא ב-{linked_table} — שדה {field} הוסר"
                )
                del result[field]
    return result


def _base() -> str:
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    if not base:
        raise RuntimeError("AIRTABLE_BASE_ID לא מוגדר")
    return base


def airtable_get_records(
    table: str, filter_formula: str = "", max_records: int | None = None,
) -> list[dict]:
    """Return matching records, optionally bounded by max_records.

    Unbounded reads follow Airtable pagination; bounded reads stop once the
    requested number of records is collected. Contract and HTTP failures raise.
    """
    if max_records is not None:
        if max_records < 0:
            raise ValueError("max_records cannot be negative")
        if max_records == 0:
            return []
    real_table = _resolve_table(table)
    records: list[dict] = []
    offset = ""
    seen_offsets: set[str] = set()

    with with_airtable_breaker():
        while True:
            remaining = None if max_records is None else max_records - len(records)
            page_size = min(100, remaining) if remaining is not None else 100
            try:
                from tools.airtable_read_adapter import list_records_page

                page, next_offset = list_records_page(
                    real_table,
                    filter_formula,
                    page_size=page_size,
                    offset=offset,
                    timeout=10,
                )
            except Exception as exc:
                status_code = getattr(exc, "status_code", None)
                if status_code is not None:
                    response_text = getattr(exc, "response_text", "")
                    raise RuntimeError(
                        f"Airtable error {status_code}: {response_text[:150]}"
                    ) from exc
                cause = getattr(exc, "cause", None)
                if cause is not None:
                    raise cause from exc
                raise RuntimeError(str(exc)) from exc

            records.extend(page if max_records is None else page[:remaining])
            if max_records is not None and len(records) >= max_records:
                break

            if not next_offset:
                break
            if next_offset in seen_offsets:
                raise RuntimeError("Airtable pagination returned an invalid offset")
            seen_offsets.add(next_offset)
            offset = next_offset

    from tools.airtable_read_adapter import render_query
    _audit(
        "airtable_get_records", table,
        result=f"{len(records)} records | filter={render_query(filter_formula)[:40]}",
    )
    return records


def airtable_get(table: str, filter_formula: str = "") -> str:
    """Return an agent-facing summary; never parse this in application code."""
    try:
        records = airtable_get_records(table, filter_formula)
    except Exception as exc:
        return f"❌ {exc}"
    if not records:
        from tools.airtable_read_adapter import render_query
        _audit("airtable_get", table, result=f"0 records | filter={render_query(filter_formula)[:40]}")
        return f"📭 אין רשומות בטבלה '{table}'."
    result = f"📊 {table} — {len(records)} רשומות:\n"
    for rec in records[:15]:
        fields = " | ".join(f"{k}: {v}" for k, v in rec.get("fields", {}).items())
        result += f"• [{rec['id']}] {fields}\n"
    from tools.airtable_read_adapter import render_query
    _audit("airtable_get", table, result=f"{len(records)} records | filter={render_query(filter_formula)[:40]}")
    return result


def airtable_add(table: str, fields: dict) -> dict:
    fields = _resolve_linked_fields(_resolve_table(table), fields)
    from tools.airtable_gateway import airtable_create
    rec = airtable_create(_resolve_table(table), fields, source="agent")
    if rec:
        rec_id = rec.get("id", "?")
        _audit("airtable_add", table, record_id=rec_id, result="created")
        return _tool_result(
            ok=bool(rec_id and rec_id != "?"),
            tool="airtable_add",
            external_id=rec_id if rec_id != "?" else "",
            evidence={"record_id": rec_id, "table": table, "fields": rec.get("fields", {})},
            user_message=f"✅ רשומה נוספה | ID: {rec_id}" if rec_id != "?" else "❌ Airtable לא החזיר record_id.",
        )
    _audit("airtable_add", table, result="error")
    return _tool_result(
        ok=False,
        tool="airtable_add",
        evidence={"table": table},
        user_message="❌ לא נשארו שדות תקינים לשמירה — בדוק שמות השדות.",
    )


def airtable_get_schema() -> str:
    """קורא את כל הטבלאות והשדות מ-Airtable Meta API בזמן אמת."""
    with with_airtable_breaker():
        from tools.airtable_gateway import AirtableLookupError, get_base_metadata

        try:
            payload = get_base_metadata(timeout=10)
        except AirtableLookupError as exc:
            if exc.status_code is None and exc.cause is not None:
                raise exc.cause from exc
            if exc.status_code is None:
                raise
            _audit("airtable_get_schema", "meta", result=f"error {exc.status_code}")
            return f"❌ Meta API error {exc.status_code}: {exc.response_text[:150]}"
        tables = payload.get("tables", [])
        if not tables:
            return "📭 לא נמצאו טבלאות בבסיס הנתונים."
        result = f"📊 נמצאו {len(tables)} טבלאות:\n\n"
        for t in tables:
            fields = [f["name"] for f in t.get("fields", [])]
            result += f"• {t['name']}\n"
            result += f"  שדות: {', '.join(fields)}\n\n"
        _audit("airtable_get_schema", "meta", result=f"{len(tables)} tables fetched")
        return result.strip()


def airtable_update(table: str, record_id: str, fields: dict) -> dict:
    fields = _resolve_linked_fields(_resolve_table(table), fields)
    from tools.airtable_gateway import airtable_patch
    ok = airtable_patch(_resolve_table(table), record_id, fields, source="agent")
    if ok:
        _audit("airtable_update", table, record_id=record_id, result="updated")
        return _tool_result(
            ok=bool(record_id),
            tool="airtable_update",
            external_id=record_id,
            evidence={"record_id": record_id, "table": table, "fields": fields},
            user_message=f"✅ רשומה {record_id} עודכנה.",
        )
    _audit("airtable_update", table, record_id=record_id, result="error")
    return _tool_result(
        ok=False,
        tool="airtable_update",
        external_id=record_id,
        evidence={"record_id": record_id, "table": table},
        user_message="❌ שגיאה בעדכון — בדוק שמות השדות.",
    )


def search_lead(name: str) -> str:
    """חיפוש ליד לפי שם חלקי — SEARCH formula של Airtable."""
    safe = name.replace("'", "\\'")
    return airtable_get("Leads", f"SEARCH('{safe}', {{Name}})")
