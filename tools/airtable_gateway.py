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
import threading
import urllib.parse
from dataclasses import dataclass

import httpx

import schema_validator as _sv
from airtable_schema import FIELD_ALIASES

logger = logging.getLogger(__name__)

# Bounded observability for RuntimeSchemaProvider's state at the one point
# where "off" bypasses it entirely (see _log_schema_provider_validation_path
# below) — a set of already-logged state strings, not a per-call log. Cardinality
# is bounded by _SCHEMA_PROVIDER_STATES (3: off/shadow/enforce), so this never
# grows unbounded. Lock only guards the log-once check itself; never gates or
# delays the actual validation path.
_schema_provider_states_logged: set[str] = set()
_schema_provider_states_lock = threading.Lock()


def _log_schema_provider_validation_path(state: str) -> None:
    """Emits '[RuntimeSchemaProvider] validation_path state=<off|shadow|enforce>'
    at INFO once per distinct state value observed in this process — proves the
    validation path was reached and which state it saw, without one log line per
    write. Metadata only (the state string itself): no table name, no field
    names/values, no payload. Purely observational — never calls into
    RuntimeSchemaProvider/get_table_contract() itself, so state=="off" still
    means zero provider invocation, unchanged."""
    with _schema_provider_states_lock:
        if state in _schema_provider_states_logged:
            return
        _schema_provider_states_logged.add(state)
    logger.info("[RuntimeSchemaProvider] validation_path state=%s", state)


@dataclass(frozen=True)
class AirtableCreateOutcome:
    """Opt-in POST classification for callers that must preserve uncertainty."""

    status: str  # created | failed | outcome_unknown
    record: dict | None = None
    error: str = ""


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
    _log_schema_provider_validation_path(state)

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
    *,
    timeout: float = 10,
) -> bool:
    """
    PATCH an existing Airtable record.
    normalize → validate → audit → httpx PATCH
    Returns True on success.
    """
    fields = normalize_airtable_fields(table, fields)
    clean, errors = validate_airtable_fields(table, fields)

    # SPEC A1 (Atomic Fail-Closed): a partial write (some fields silently
    # dropped by validate_airtable_fields) must not proceed and report
    # success — the caller/user would have no way to know data was lost.
    # dropped is computed against `fields` (post-normalize, pre-validate),
    # not the original caller payload, because normalize_airtable_fields
    # may rename keys (aliases) — comparing must stay within one namespace.
    # Coercions (e.g. a single "recXXX" string wrapped into ["recXXX"] for
    # a linked-record field) stay under the SAME key in `clean`, so they
    # are correctly NOT counted as dropped.
    dropped = set(fields.keys()) - set(clean.keys())
    if dropped:
        logger.warning(
            "[gateway:%s] PATCH %s/%s — fields dropped, write blocked: %s (all errors: %s)",
            source, table, record_id, sorted(dropped), errors,
        )
        _audit_log(source, table, "patch", record_id, [], ok=False)
        return False

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
            timeout=timeout,
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
    *,
    timeout: float = 10,
    return_outcome: bool = False,
) -> dict | None | AirtableCreateOutcome:
    """
    POST a new Airtable record.
    normalize → validate → audit → httpx POST
    Returns the full Airtable record dict or None.  With return_outcome=True,
    returns an explicit created/failed/outcome_unknown classification.
    """
    def outcome(status: str, record: dict | None = None, error: str = ""):
        return AirtableCreateOutcome(status, record, error) if return_outcome else record

    fields = normalize_airtable_fields(table, fields)
    clean, errors = validate_airtable_fields(table, fields)

    # SPEC A1 (Atomic Fail-Closed) — see identical reasoning in airtable_patch().
    dropped = set(fields.keys()) - set(clean.keys())
    if dropped:
        logger.warning(
            "[gateway:%s] POST %s — fields dropped, write blocked: %s (all errors: %s)",
            source, table, sorted(dropped), errors,
        )
        _audit_log(source, table, "create", "", [], ok=False)
        return outcome("failed")

    if not clean:
        logger.warning(
            "[gateway:%s] POST %s — no valid fields after normalization",
            source, table,
        )
        _audit_log(source, table, "create", "", [], ok=False)
        return outcome("failed")

    logger.debug("[gateway:%s] POST %s keys=%s", source, table, list(clean.keys()))

    try:
        r = httpx.post(
            _at_url(table),
            headers=_at_headers(),
            json={"fields": clean},
            timeout=timeout,
        )
        ok = r.status_code in (200, 201)
        if ok:
            response = r.json()
            rec_id = response.get("id", "?")
            _audit_log(source, table, "create", rec_id, list(clean.keys()), ok=True)
            if return_outcome:
                if not rec_id or rec_id == "?":
                    return AirtableCreateOutcome(
                        "outcome_unknown", response,
                        "provider accepted POST without record id",
                    )
                return AirtableCreateOutcome("created", response)
            return response

        _audit_log(source, table, "create", "", list(clean.keys()), ok=False)
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
        if return_outcome:
            status = "failed" if 400 <= r.status_code < 500 else "outcome_unknown"
            return AirtableCreateOutcome(
                status, error=f"provider returned HTTP {r.status_code}"
            )
        return None
    except Exception as e:
        logger.warning("[gateway:%s] POST %s error: %s", source, table, e)
        _audit_log(source, table, "create", "", [], ok=False)
        if return_outcome:
            return AirtableCreateOutcome("outcome_unknown", error=str(e))
        return None


class AirtableLookupError(Exception):
    """Raised by at_get_by_field on a network/HTTP failure — distinct from a
    clean "no matching record" result, so callers (esp.
    ActionContractRepository) can fail closed on a store outage instead of
    silently treating "can't reach Airtable" the same as "genuinely not found"."""

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
        status_code: int | None = None,
        response_text: str = "",
        response_url: str = "",
        response_reason: str = "",
    ):
        super().__init__(message)
        self.cause = cause
        self.status_code = status_code
        self.response_text = response_text
        self.response_url = response_url
        self.response_reason = response_reason


def at_get_by_field(table: str, field: str, value: str, *, timeout: float = 10) -> dict | None:
    """
    Finds a single record by an exact field match. Returns the raw Airtable
    record dict ({"id": ..., "fields": {...}}) or None if no match. Raises
    AirtableLookupError on a network/HTTP failure — the caller must not treat
    that the same as "not found" (see ActionContractRepository.get()).
    """
    try:
        r = httpx.get(
            _at_url(table),
            headers=_at_headers(),
            params={
                "filterByFormula": f"{{{field}}}='{_safe_formula_param(str(value))}'",
                "maxRecords": 1,
            },
            timeout=timeout,
        )
    except Exception as e:
        raise AirtableLookupError(f"{table}/{field}={value!r}: {e}") from e

    if r.status_code != 200:
        raise AirtableLookupError(f"{table}/{field}={value!r}: HTTP {r.status_code}")

    records = r.json().get("records", [])
    return records[0] if records else None


def at_get_record(table: str, record_id: str, *, timeout: float = 10) -> dict:
    """Fetch one raw Airtable record by record ID."""
    try:
        r = httpx.get(
            f"{_at_url(table)}/{record_id}",
            headers=_at_headers(),
            timeout=timeout,
        )
    except Exception as e:
        raise AirtableLookupError(f"{table}/{record_id} get error: {e}", cause=e) from e

    if r.status_code != 200:
        raise AirtableLookupError(
            f"{table}/{record_id} get: HTTP {r.status_code}",
            status_code=r.status_code,
            response_text=r.text,
            response_url=str(getattr(r, "url", "")),
            response_reason=str(getattr(r, "reason_phrase", "")),
        )
    return r.json()


def at_list_by_formula(
    table: str,
    formula: str,
    max_records: int | str | None = 100,
    *,
    fields: list[str] | None = None,
    sort: list[dict[str, str]] | None = None,
    paginate: bool = False,
    timeout: float = 10,
) -> list[dict]:
    """
    Lists records matching a caller-built filterByFormula string. The caller
    is responsible for escaping any interpolated values via
    _safe_formula_param() — this function does no escaping of its own (the
    formula may combine multiple conditions with AND()/OR(), which a single
    value-escaping helper can't safely do generically). Raises
    AirtableLookupError on a network/HTTP failure — same fail-closed contract
    as at_get_by_field().
    """
    params: dict[str, object] = {}
    if formula:
        params["filterByFormula"] = formula
    if max_records:
        params["maxRecords"] = max_records
    if fields:
        params["fields[]"] = fields
    if sort:
        for index, item in enumerate(sort):
            if "field" in item:
                params[f"sort[{index}][field]"] = item["field"]
            if "direction" in item:
                params[f"sort[{index}][direction]"] = item["direction"]

    records: list[dict] = []
    while True:
        try:
            r = httpx.get(
                _at_url(table),
                headers=_at_headers(),
                params=params,
                timeout=timeout,
            )
        except Exception as e:
            raise AirtableLookupError(f"{table} list error: {e}", cause=e) from e

        if r.status_code != 200:
            raise AirtableLookupError(
                f"{table} list: HTTP {r.status_code}",
                status_code=r.status_code,
                response_text=r.text,
                response_url=str(getattr(r, "url", "")),
                response_reason=str(getattr(r, "reason_phrase", "")),
            )

        payload = r.json()
        records.extend(payload.get("records", []))
        offset = payload.get("offset")
        if not paginate or not offset:
            return records
        params["offset"] = offset


def at_list_page(
    table: str,
    formula: str = "",
    *,
    page_size: int | None = None,
    offset: str = "",
    max_records: int | str | None = None,
    timeout: float = 10,
) -> tuple[list[dict], str | None]:
    """Fetch one Airtable records page and return its records and next offset."""
    params: dict[str, object] = {}
    if formula:
        params["filterByFormula"] = formula
    if page_size is not None:
        params["pageSize"] = page_size
    if max_records:
        params["maxRecords"] = max_records
    if offset:
        params["offset"] = offset

    try:
        r = httpx.get(
            _at_url(table),
            headers=_at_headers(),
            params=params,
            timeout=timeout,
        )
    except Exception as e:
        raise AirtableLookupError(f"{table} page error: {e}", cause=e) from e

    if r.status_code != 200:
        raise AirtableLookupError(
            f"{table} page: HTTP {r.status_code}",
            status_code=r.status_code,
            response_text=r.text,
            response_url=str(getattr(r, "url", "")),
            response_reason=str(getattr(r, "reason_phrase", "")),
        )

    payload = r.json()
    records = payload.get("records")
    if not isinstance(records, list):
        raise AirtableLookupError(f"{table} records response is not a list")
    next_offset = payload.get("offset")
    if next_offset is not None and not isinstance(next_offset, str):
        raise AirtableLookupError(f"{table} pagination returned an invalid offset")
    return records, next_offset


def at_upsert(
    table: str,
    fields: dict,
    match_field: str,
    source: str = "unknown",
    fail_closed_on_lookup_error: bool = False,
) -> bool:
    """
    Create-or-update by match_field's value (e.g. contract_id). Intended for
    core/action_gateway.py's ExecutionLedger to persist ActionContracts.

    KNOWN LIMITATION — not safe under concurrent calls for the same
    match_field value: the lookup-then-write here is not atomic (classic
    TOCTOU), so two near-simultaneous at_upsert() calls for a brand-new
    contract_id could both see "no existing record" and both create one
    (duplicate rows), and two racing writes for an existing record could
    apply out of order (a stale status could overwrite a newer one — last
    HTTP call to land wins, not last logical call). There is no
    concurrency-safe alternative in this codebase yet for status transitions
    — a genuinely atomic coordination primitive outside Airtable is tracked
    separately as Phase 4B0.1. This function remains a plain best-effort
    upsert. Returns True on success.

    ``fail_closed_on_lookup_error`` is intentionally opt-in for compatibility
    with legacy callers. When enabled, an unavailable/error lookup returns
    False without attempting a create. Durable ActionContract callers enable
    it explicitly so an Airtable read failure can never become a duplicate
    row.
    """
    match_value = fields.get(match_field)
    if not match_value:
        logger.warning(
            "[gateway:%s] at_upsert %s — match_field '%s' missing/empty in fields",
            source, table, match_field,
        )
        return False

    try:
        existing = at_get_by_field(table, match_field, str(match_value))
    except AirtableLookupError as e:
        logger.warning("[gateway:%s] at_upsert %s lookup error: %s", source, table, e)
        if fail_closed_on_lookup_error:
            return False
        existing = None

    if existing:
        return airtable_patch(table, existing["id"], fields, source=source)
    return airtable_create(table, fields, source=source) is not None


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


def get_table_schema(table_name: str, *, timeout: float = 15) -> dict | None:
    """
    Fetch one table's live schema via the Meta API — same endpoint as
    resolve_table_and_field_ids(), but returns the whole table dict
    ({"id", "name", "fields": [{"id", "name", "type", ...}, ...]}) instead
    of resolving a single field ID, for callers that need to validate field
    *types*, not just existence (e.g. core/emergency_stop_preflight.py).

    Returns None if no table with this name exists in the base — a clean,
    non-error "not found" signal, distinct from a network failure. Raises
    AirtableLookupError on a network/HTTP failure — same fail-closed
    contract as at_get_by_field()/at_list_by_formula(). Read-only.
    """
    try:
        r = httpx.get(
            f"https://api.airtable.com/v0/meta/bases/{_at_base()}/tables",
            headers={"Authorization": f"Bearer {_at_key()}"},
            timeout=timeout,
        )
    except Exception as e:
        raise AirtableLookupError(f"meta schema fetch for table={table_name!r}: {e}") from e

    if r.status_code != 200:
        raise AirtableLookupError(
            f"meta schema fetch for table={table_name!r}: HTTP {r.status_code}"
        )

    for t in r.json().get("tables", []):
        if t.get("name") == table_name:
            return t
    return None


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
