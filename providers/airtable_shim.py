# providers/airtable_shim.py
# F13 — AirtableStorageProvider shim
# עוטף את tools/airtable_gateway.py + tools/airtable_tools.py ללא שינוין.
#
# הערה (SPEC-001): airtable_get() הקיים מחזיר string מפורמט, לא list[dict],
# ואין לו max_records — לכן get() כאן עושה קריאת REST גולמית ישירות (כמו
# airtable_get עושה internally), אבל דרך _resolve_table() כדי לשמר את
# alias resolution הקיים. אין delete() אמיתי בגרסה הנוכחית של ה-gateway —
# stub כן מצהיר NotImplementedError במקום להעמיד פנים שהוא עובד.

from __future__ import annotations
from typing import Any
import urllib.parse

import httpx

from tools.airtable_gateway import airtable_create, airtable_patch
from tools.airtable_tools import _resolve_table, _base, _headers
from guards.circuit_breaker import with_airtable_breaker


class AirtableStorageProvider:
    def get(self, table: str, formula: str = "", max_records: int = 100,
            fields: list[str] | None = None) -> list[dict[str, Any]]:
        real_table = _resolve_table(table)
        with with_airtable_breaker():
            params: dict[str, Any] = {"pageSize": min(max_records, 100)}
            if formula:
                params["filterByFormula"] = formula
            if fields:
                params["fields[]"] = fields
            encoded = urllib.parse.quote(real_table, safe="")
            r = httpx.get(f"https://api.airtable.com/v0/{_base()}/{encoded}",
                          headers=_headers(), params=params, timeout=10)
            if r.status_code != 200:
                return []
            return r.json().get("records", [])[:max_records]

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
