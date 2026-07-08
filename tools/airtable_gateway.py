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

# PR2 rev.2 — Airtable Meta API field type strings for select fields.
# Same two literal values already used independently by tools/schema_governance.py.
_SELECT_FIELD_TYPES: frozenset[str] = frozenset({"singleSelect", "multipleSelects"})


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

    # (final) unknown-field guard — drop fields Airtable doesn't know about.
    # PR3B (rev.2): reads through RuntimeSchemaProvider.get_table_contract()
    # in shadow/enforce state instead of schema_validator directly. "off"
    # (default) preserves prior behavior exactly — the provider is never
    # even called. Do not reintroduce ad-hoc schema validation outside
    # RuntimeSchemaProvider going forward.
    from feature_flags import get_runtime_schema_provider_state
    state = get_runtime_schema_provider_state()

    legacy_unknown = _sv.validate_fields(table, clean)

    if state == "off":
        unknown = legacy_unknown
    else:
        provider_unknown = _provider_unknown_fields(table, clean)
        if state == "shadow":
            unknown = legacy_unknown
            if set(provider_unknown) != set(legacy_unknown):
                logger.warning(
                    "[RuntimeSchemaProvider:SHADOW] discrepancy table=%s legacy_unknown=%s "
                    "provider_unknown=%s (not blocking — shadow state)",
                    table, legacy_unknown, provider_unknown,
                )
        else:  # "enforce"
            unknown = provider_unknown

    for u in unknown:
        errors.append(f"unknown field '{u}' in {table} (not in schema_cache)")
        del clean[u]

    # (PR2 rev.2) select-value validation — reads through the same
    # RuntimeSchemaProvider contract, but only ever runs when
    # contract["mode"] == "full" (never during "name_only" seed fallback —
    # schema_cache.json has no choices to check against, so it must not
    # produce false positives; see core/runtime_schema_provider.py).
    # Independent flag/state from the unknown-field guard above — a table
    # can be enforce for one and shadow/off for the other.
    from feature_flags import get_select_value_validation_state
    value_state = get_select_value_validation_state()

    if value_state != "off":
        invalid = _provider_invalid_select_values(table, clean)
        for field, (value, allowed) in invalid.items():
            if value_state == "shadow":
                logger.warning(
                    "[SelectValueValidation:SHADOW] invalid value table=%s field=%s "
                    "value=%r allowed=%s (not blocking — shadow state)",
                    table, field, value, allowed,
                )
            else:  # "enforce"
                errors.append(
                    f"Airtable value validation failed: table={table} field={field} "
                    f"value={value!r} allowed={allowed}"
                )
                del clean[field]

    return clean, errors


def _provider_unknown_fields(table: str, fields: dict) -> list[str]:
    """Unknown-field list per RuntimeSchemaProvider.get_table_contract()."""
    from core.runtime_schema_provider import get_provider
    contract = get_provider().get_table_contract(table)
    known = contract["fields"].keys()
    return [k for k in fields if k not in known]


def _provider_invalid_select_values(table: str, fields: dict) -> dict[str, tuple[object, list[str]]]:
    """
    Returns {field_name: (offending_value, allowed_choices)} for every
    singleSelect/multipleSelects field in `fields` whose value(s) aren't in
    RuntimeSchemaProvider's live choices for this table.

    Only runs when the provider's contract for this table is mode="full" —
    mode="name_only" (seed fallback) never has choices, so it's always
    skipped here rather than risk a false-positive block. A multipleSelects
    field with any invalid entry is reported (and, in enforce, dropped) as
    a whole — no partial-list filtering (PR2 rev.2 scope decision).
    """
    from core.runtime_schema_provider import get_provider
    contract = get_provider().get_table_contract(table)
    if contract["mode"] != "full":
        return {}

    invalid: dict[str, tuple[object, list[str]]] = {}
    for field, value in fields.items():
        info = contract["fields"].get(field)
        if not info or info["type"] not in _SELECT_FIELD_TYPES:
            continue
        choices = info["choices"]
        if not choices:
            continue  # select field with no configured options yet — nothing to check against

        if info["type"] == "multipleSelects":
            if not isinstance(value, list):
                continue  # not our shape to validate — leave to existing coercion/validation
            if any(v not in choices for v in value):
                invalid[field] = (value, choices)
        else:  # singleSelect
            if not isinstance(value, str):
                continue
            if value not in choices:
                invalid[field] = (value, choices)

    return invalid


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
