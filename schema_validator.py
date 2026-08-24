# schema_validator.py
# שמירת ידע על שמות שדות Airtable — guard לפני כל כתיבה.
# טוען schema_cache.json (seed מ-airtable_schema.py, מתעדכן ע"י schema_audit.py).
# לא חוסם כשה-cache חסר — רק מלוגג אזהרה.

from __future__ import annotations
import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).parent / "schema_cache.json"
_cache: dict[str, set[str]] | None = None  # None = לא נטען


def _load_cache() -> dict[str, set[str]]:
    global _cache
    if _cache is not None:
        return _cache
    if not _CACHE_PATH.exists():
        logger.warning("schema_validator: schema_cache.json לא נמצא — validation מושבת")
        _cache = {}
        return _cache
    try:
        raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        _cache = {tbl: set(fields) for tbl, fields in raw.get("tables", {}).items()}
        logger.debug(f"schema_validator: טעון — {len(_cache)} טבלאות")
    except Exception as exc:
        logger.warning(f"schema_validator: שגיאה בטעינת cache — {exc}")
        _cache = {}
    return _cache


def validate_fields(table_name: str, fields: dict) -> list[str]:
    """מחזיר רשימת מפתחות לא-ידועים בטבלה. רשימה ריקה = הכל תקין."""
    cache = _load_cache()
    if not cache or table_name not in cache:
        return []  # אין מידע על הטבלה — לא חוסמים
    known = cache[table_name]
    return [k for k in fields if k not in known]


def get_known_fields(table_name: str) -> set[str]:
    """מחזיר סט שמות שדות ידועים לטבלה (ריק אם אין cache)."""
    return _load_cache().get(table_name, set())


def refresh_cache() -> dict[str, list[str]]:
    """
    שולף schema חי מ-Airtable Metadata API ושומר ב-schema_cache.json.
    מחזיר dict של table -> [field_names].
    """
    key  = os.environ.get("AIRTABLE_API_KEY", "")
    base = os.environ.get("AIRTABLE_BASE_ID", "")

    if not key or not base:
        raise EnvironmentError("AIRTABLE_API_KEY / AIRTABLE_BASE_ID חסרים")

    from tools.airtable_gateway import AirtableLookupError, get_base_metadata

    try:
        metadata = get_base_metadata(timeout=20)
    except AirtableLookupError as exc:
        if exc.status_code is not None:
            request = httpx.Request(
                "GET", exc.response_url or f"https://api.airtable.com/v0/meta/bases/{base}/tables"
            )
            response = httpx.Response(
                exc.status_code,
                text=exc.response_text,
                request=request,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as status_error:
                raise status_error from exc
        if exc.cause is not None:
            raise exc.cause from exc
        raise

    tables: dict[str, list[str]] = {}
    for tbl in metadata.get("tables", []):
        tables[tbl["name"]] = [f["name"] for f in tbl.get("fields", [])]

    payload = {
        "tables": tables,
        "fetched_at": __import__("datetime").date.today().isoformat(),
        "note": "auto-fetched by schema_audit.py",
    }
    _CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    global _cache
    _cache = {tbl: set(fields) for tbl, fields in tables.items()}
    logger.info(f"schema_validator: cache רוענן — {len(tables)} טבלאות")
    return tables
