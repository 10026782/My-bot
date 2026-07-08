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
        "טמפרטורה",                                        # formula: lead temperature (Hebrew)
        "אימוג'י טמפרטורה", "מד ציון", "עדיפות",          # formula: display helpers
        "תצוגת ליד", "המלצת מעקב",                        # formula: computed display
        "updated_at", "Updated At",                        # non-existent in schema — no-op safe
        "created_at", "Created At",                        # createdTime — Airtable fills automatically
        "Suggested Follwup", "Suggested Followup",         # formula (typo fixed 2026-06-15, keep both)
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
    "Media Files": {"Linked Lead"},
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


def _safe_formula_param(value: str) -> str:
    """
    Escape a value for safe interpolation into an Airtable filterByFormula
    string literal. Single quotes are the field delimiter in Airtable
    formulas — backslash-escape them.

    This is the ONLY sanctioned way to interpolate user-controlled text into
    a filterByFormula string anywhere in the codebase (BUG-DH-03/04). Any
    code building filterByFormula with a raw f-string/format on unescaped
    input is a bug — route it through this function instead.
    """
    return value.replace("'", "\\'")


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


def airtable_delete(table: str, record_id: str, source: str = "unknown") -> bool:
    """DELETE an existing Airtable record. Returns True on success."""
    try:
        r = httpx.delete(
            f"{_at_url(table)}/{record_id}",
            headers=_at_headers(),
            timeout=10,
        )
        ok = r.status_code == 200
        _audit_log(source, table, "delete", record_id, [], ok=ok)
        if not ok:
            logger.warning(
                "[gateway:%s] DELETE %s/%s → %d: %s",
                source, table, record_id, r.status_code, r.text[:200],
            )
        return ok
    except Exception as e:
        logger.warning("[gateway:%s] DELETE %s/%s error: %s", source, table, record_id, e)
        _audit_log(source, table, "delete", record_id, [], ok=False)
        return False


# ══════════════════════════════════════════════════════════════════
# PR3A — Native attachment upload (Meta API ID resolution + uploadAttachment)
# ══════════════════════════════════════════════════════════════════
#
# Airtable's regular record PATCH/POST does not accept raw bytes for
# attachment fields — only {"url": ...} pointing at an already-public file.
# Uploading bytes we generated internally (no public URL) requires the
# dedicated binary upload endpoint below, which lives on a different host
# (content.airtable.com, not api.airtable.com) and needs the *field ID*,
# not the field name. Table/field name != table/field ID — always resolve
# via the Meta API rather than assuming they match.

def resolve_table_and_field_ids(table_name: str, field_name: str) -> tuple[str, str]:
    """
    Resolve Airtable's internal tableId/fieldId for (table_name, field_name)
    via the Meta API. Raises RuntimeError if either cannot be found —
    callers must fail closed, never guess an ID.
    """
    r = httpx.get(
        f"https://api.airtable.com/v0/meta/bases/{_at_base()}/tables",
        headers={"Authorization": f"Bearer {_at_key()}"},
        timeout=15,
    )
    r.raise_for_status()
    for t in r.json().get("tables", []):
        if t.get("name") == table_name:
            table_id = t["id"]
            for f in t.get("fields", []):
                if f.get("name") == field_name:
                    return table_id, f["id"]
            raise RuntimeError(
                f"field '{field_name}' not found in table '{table_name}' via Meta API"
            )
    raise RuntimeError(f"table '{table_name}' not found via Meta API")


def airtable_upload_attachment(
    record_id: str,
    field_id: str,
    filename: str,
    content_bytes: bytes,
    content_type: str,
    source: str = "unknown",
) -> dict:
    """
    Upload raw bytes as a native Airtable attachment on an existing record.
    This is a new write path inside the Gateway, not a bypass of it.
    Returns {"ok": bool, "error": str|None, "raw": dict}.
    """
    import base64

    b64 = base64.b64encode(content_bytes).decode("ascii")
    try:
        r = httpx.post(
            f"https://content.airtable.com/v0/{_at_base()}/{record_id}/{field_id}/uploadAttachment",
            headers={
                "Authorization": f"Bearer {_at_key()}",
                "Content-Type": "application/json",
            },
            json={"contentType": content_type, "filename": filename, "file": b64},
            timeout=30,
        )
        ok = r.status_code == 200
        _audit_log(source, "attachment_upload", "upload", record_id, [field_id], ok=ok)
        if ok:
            return {"ok": True, "error": None, "raw": r.json()}
        body = r.text[:300]
        logger.warning(
            "[gateway:%s] uploadAttachment %s/%s → %d: %s",
            source, record_id, field_id, r.status_code, body,
        )
        return {"ok": False, "error": f"HTTP {r.status_code}: {body}", "raw": {}}
    except Exception as e:
        logger.warning(
            "[gateway:%s] uploadAttachment %s/%s error: %s", source, record_id, field_id, e
        )
        _audit_log(source, "attachment_upload", "upload", record_id, [field_id], ok=False)
        return {"ok": False, "error": str(e), "raw": {}}


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
