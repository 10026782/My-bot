# providers/airtable_shim.py
# F13 — AirtableStorageProvider shim
# עוטף את tools/airtable_gateway.py + tools/airtable_read_adapter.py
# + tools/airtable_tools.py ללא שינוי public API.
#
# הערה (SPEC-001): airtable_get() הקיים מחזיר string מפורמט, לא list[dict],
# ואין לו max_records — לכן get() כאן משתמש ב-one-page primitive של read adapter
# ושומר את alias resolution הקיים דרך _resolve_table(). אין delete() אמיתי
# בגרסה הנוכחית של ה-gateway —
# stub כן מצהיר NotImplementedError במקום להעמיד פנים שהוא עובד.

from __future__ import annotations
from typing import Any

from tools.airtable_gateway import airtable_create, airtable_patch
from tools.airtable_read_adapter import AirtableReadError, list_records_page
from tools.airtable_tools import _resolve_table
from guards.circuit_breaker import with_airtable_breaker


class AirtableStorageProvider:
    def get(self, table: str, formula: str = "", max_records: int = 100,
            fields: list[str] | None = None) -> list[dict[str, Any]]:
        real_table = _resolve_table(table)
        with with_airtable_breaker():
            try:
                records, _ = list_records_page(
                    real_table,
                    formula,
                    page_size=min(max_records, 100),
                    fields=fields,
                    timeout=10,
                )
            except AirtableReadError as exc:
                if exc.status_code is not None:
                    return []
                if exc.cause is not None:
                    raise exc.cause from exc
                raise
            return records[:max_records]

    def add(self, table: str, fields: dict[str, Any]) -> dict[str, Any]:
        return airtable_create(_resolve_table(table), fields, source="provider:airtable_shim") or {}

    def update(self, table: str, record_id: str,
               fields: dict[str, Any]) -> dict[str, Any]:
        ok = airtable_patch(_resolve_table(table), record_id, fields, source="provider:airtable_shim")
        return {"id": record_id, "ok": ok}

    def delete(self, table: str, record_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "tools/airtable_gateway.py has no delete function — "
            "Airtable record deletion is not implemented in this codebase (SPEC-001)."
        )
