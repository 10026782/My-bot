# tools/airtable_gateway.py — Single Airtable Write Path
#
# ALL writes go through here: normalize → validate → audit → httpx PATCH/POST.
# Callers pass a source tag ("tma", "agent", "lead_capture") for audit trails.
#
# כלל ברזל: שכבה זו היא ה-gate היחיד לכתיבה ל-Airtable.
# אין לקרוא ל-httpx.patch/post על Airtable מחוץ לקובץ זה.

from __future__ import annotations

import logging
import os
import urllib.parse

import httpx

import schema_validator as _sv
from airtable_schema import FIELD_ALIASES

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Configuration — per-table aliases and read-only fields
# ══════════════════════════════════════════════════════════════════

# FIELD_ALIASES imported from airtable_schema — single source of truth

# Formula / computed fields that Airtable will reject if we try to write them.
# Writing a formula field causes a 422 from Airtable.
READ_ONLY_FIELDS: dict[str, set[str]] = {
    "Leads": {
        "tier", "Tier", "טמפרטורה",                       # formula: lead temperature
        "אימוג'י טמפרטורה", "מד ציון", "עדיפות",          # formula: display helpers
        "תצוגת ליד", "המלצת מעקב",                        # formula: computed display
        "updated_at", "Updated At",                        # non-existent in schema — no-op safe
        "created_at", "Created At",                        # createdTime — Airtable fills automatically
        "converted_at",                                    # non-existent in live schema (app4bcgoX7t0HUVnm)
        "notes",                                           # non-existent in Leads (voice_adapter writes it)
        "Suggested Follwup", "Suggested Followup",         # formula (typo in Airtable name) — both spellings
    },
    "Assets": {
        "Equity", "My Equity",                             # formula fields — Airtable auto-calculates
    },
    "משימות ודד ליינים": {
        "תאריך יצירה", "תאריך עדכון אחרון",               # createdTime + lastModifiedTime
    },
    "Blue View Buyers": {
        "Created At", "Last Updated",                      # createdTime + lastModifiedTime
    },
}

# Airtable multipleRecordLinks fields — value must be a list of rec IDs, never a bare string.
# Gateway coerces a bare "recXXX" string → ["recXXX"] and drops anything else (prevents 422).
LINKED_RECORD_FIELDS: dict[str, set[str]] = {
    "Leads": {"Owner"},
}

# Fields the agent should never write — security layer
_ALWAYS_FORBIDDEN: frozenset[str] = frozenset({"tenant", "owner_id", "user_id", "chat_id"})


# ══════════════════════════════════════════════════════════════════
# Core normalise / validate
# ══════════════════════════════════════════════════════════════════

def normalize_airtable_fields(table: str, fields: dict) -> dict:
    """Apply per-table FIELD_ALIASES → canonical Airtable field names."""
    aliases = FIELD_ALIASES.get(table, {})
    result: dict = {}
    for k, v in fields.items():
        canonical = aliases.get(k, k)
        result[canonical] = v
    return result


def validate_airtable_fields(table: str, fields: dict) -> tuple[dict, list[str]]:
    """
    Validate fields against schema_cache.json, strip read-only and forbidden fields.
    Returns (clean_fields, list_of_error_strings).
    clean_fields is safe to write; errors are warnings only (caller logs them).
    """
    errors: list[str] = []
    clean: dict = {}

    ro = READ_ONLY_FIELDS.get(table, set())

    for k, v in fields.items():
        # 1. key must be a non-empty string
        if not isinstance(k, str) or not k.strip():
            errors.append(f"invalid field key {repr(k)}")
            continue
        k = k.strip()

        # 2. forbidden security fields
        if k in _ALWAYS_FORBIDDEN:
            errors.append(f"forbidden field '{k}'")
            continue

        # 3. sentinel "none" — UI placeholder, not a valid Airtable select value
        if isinstance(v, str) and v.strip() == "none":
            errors.append(f"sentinel 'none' value for field '{k}'")
            continue

        # 4. read-only formula fields
        if k in ro:
            errors.append(f"read-only field '{k}' in {table}")
            continue

        # 5. multipleRecordLinks coercion — Airtable requires a list of rec IDs.
        #    Wrap a bare "recXXX" string; drop anything else (plain names → 422).
        lr_fields = LINKED_RECORD_FIELDS.get(table, set())
        if k in lr_fields:
            if isinstance(v, list):
                pass  # already correct format
            elif isinstance(v, str) and __import__("re").match(r"^rec\w+$", v):
                v = [v]
                errors.append(f"linked-record field '{k}' coerced string→list")
            else:
                errors.append(
                    f"linked-record field '{k}'={repr(v)} is not a rec ID or list — dropped"
                )
                continue

        clean[k] = v

    # (final) schema_cache.json guard — drop fields Airtable doesn't know about
    unknown = _sv.validate_fields(table, clean)
    for u in unknown:
        errors.append(f"unknown field '{u}' in {table} (not in schema_cache)")
        del clean[u]

    return clean, errors


# ══════════════════════════════════════════════════════════════════
# HTTP helpers
# ══════════════════════════════════════════════════════════════════

def _at_key() -> str:
    return os.environ.get("AIRTABLE_API_KEY", "")


def _at_base() -> str:
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    if not base:
        raise RuntimeError("AIRTABLE_BASE_ID not set")
    return base


def _at_url(table: str) -> str:
    return f"https://api.airtable.com/v0/{_at_base()}/{urllib.parse.quote(table, safe='')}"


def _at_headers() -> dict:
    return {
        "Authorization": f"Bearer {_at_key()}",
        "Content-Type":  "application/json",
    }


# ══════════════════════════════════════════════════════════════════
# Audit
# ══════════════════════════════════════════════════════════════════

def _audit_log(
    source: str, table: str, op: str,
    record_id: str, keys: list[str], ok: bool,
) -> None:
    level = logging.INFO if ok else logging.WARNING
    logger.log(
        level,
        "[AUDIT:gateway] source=%s op=%s table=%s record=%s keys=%s ok=%s",
        source, op, table, record_id or "-", keys, ok,
    )


# ══════════════════════════════════════════════════════════════════
# Public write API
# ══════════════════════════════════════════════════════════════════

def airtable_patch(
    table: str,
    record_id: str,
    fields: dict,
    source: str = "unknown",
) -> bool:
    """
    PATCH an existing Airtable record.
    normalize → validate → audit → httpx PATCH
    Returns True on success.
    """
    fields = normalize_airtable_fields(table, fields)
    clean, errors = validate_airtable_fields(table, fields)

    if errors:
        logger.warning(
            "[gateway:%s] PATCH %s/%s — dropped fields: %s",
            source, table, record_id, errors,
        )
    if not clean:
        logger.warning(
            "[gateway:%s] PATCH %s/%s — no valid fields after normalization",
            source, table, record_id,
        )
        _audit_log(source, table, "patch", record_id, [], ok=False)
        return False

    logger.debug(
        "[gateway:%s] PATCH %s/%s keys=%s",
        source, table, record_id, list(clean.keys()),
    )

    try:
        r = httpx.patch(
            f"{_at_url(table)}/{record_id}",
            headers=_at_headers(),
            json={"fields": clean},
            timeout=10,
        )
        ok = r.status_code == 200
        _audit_log(source, table, "patch", record_id, list(clean.keys()), ok=ok)
        if not ok:
            body = r.text[:300]
            if r.status_code == 422:
                try:
                    body = str(r.json())[:400]
                except Exception:
                    pass
            logger.warning(
                "[gateway:%s] PATCH %s/%s → %d: %s",
                source, table, record_id, r.status_code, body,
            )
        return ok
    except Exception as e:
        logger.warning("[gateway:%s] PATCH %s/%s error: %s", source, table, record_id, e)
        _audit_log(source, table, "patch", record_id, list(clean.keys()), ok=False)
        return False


def airtable_create(
    table: str,
    fields: dict,
    source: str = "unknown",
) -> dict | None:
    """
    POST a new Airtable record.
    normalize → validate → audit → httpx POST
    Returns the full Airtable record dict {"id": "recXXX", "fields": {...}} or None.
    """
    fields = normalize_airtable_fields(table, fields)
    clean, errors = validate_airtable_fields(table, fields)

    if errors:
        logger.warning(
            "[gateway:%s] POST %s — dropped fields: %s",
            source, table, errors,
        )
    if not clean:
        logger.warning(
            "[gateway:%s] POST %s — no valid fields after normalization",
            source, table,
        )
        _audit_log(source, table, "create", "", [], ok=False)
        return None

    logger.debug("[gateway:%s] POST %s keys=%s", source, table, list(clean.keys()))

    try:
        r = httpx.post(
            _at_url(table),
            headers=_at_headers(),
            json={"fields": clean},
            timeout=10,
        )
        ok = r.status_code in (200, 201)
        rec_id = r.json().get("id", "?") if ok else ""
        _audit_log(source, table, "create", rec_id, list(clean.keys()), ok=ok)
        if ok:
            return r.json()
        body = r.text[:300]
        if r.status_code == 422:
            try:
                body = str(r.json())[:400]
            except Exception:
                pass
        logger.warning(
            "[gateway:%s] POST %s → %d: %s",
            source, table, r.status_code, body,
        )
        return None
    except Exception as e:
        logger.warning("[gateway:%s] POST %s error: %s", source, table, e)
        _audit_log(source, table, "create", "", [], ok=False)
        return None


# ══════════════════════════════════════════════════════════════════
# Step 5 — Startup consistency check
# ══════════════════════════════════════════════════════════════════

def check_alias_consistency() -> list[str]:
    """
    Compare FIELD_ALIASES targets against schema_cache.json.
    Returns list of mismatch strings (empty = all OK).
    Call from app.py startup; logs CRITICAL on any mismatch.
    """
    mismatches: list[str] = []
    cache = _sv.get_known_fields  # callable: table → set[str]

    for table, aliases in FIELD_ALIASES.items():
        known = _sv.get_known_fields(table)
        if not known:
            # table not in cache — skip (cache may not be seeded yet)
            continue
        for variant, canonical in aliases.items():
            # read-only fields may not be writable but should still appear in schema
            if canonical not in known and canonical not in READ_ONLY_FIELDS.get(table, set()):
                msg = (
                    f"FIELD_ALIASES mismatch: {table}.{repr(canonical)} "
                    f"(alias for {repr(variant)}) not in schema_cache"
                )
                mismatches.append(msg)
                logger.critical("[gateway] %s", msg)

    return mismatches
