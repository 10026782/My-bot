# core/emergency_stop_preflight.py — PATCH 3B Step 4
#
# Read-only CLI: verifies the live Airtable "Emergency Stop Flags" table
# (schema + data) is ready for the Emergency Stop durable store to be
# switched on. It NEVER creates the table, NEVER creates/updates a record,
# NEVER bootstraps anything, and NEVER touches feature_flags.py or
# EmergencyStopManager — this module is a diagnostic gate, not a wiring
# step. See core/predeploy.py for the wrapper that runs this after database
# migrations.
#
# All I/O happens only inside run_preflight()/main() — importing this
# module performs none. Uses only tools/airtable_gateway.py (the sole
# sanctioned Airtable I/O layer — see CLAUDE.md "Iron rule") and
# adapters/airtable_emergency_stop_store.py; adds no new direct
# httpx/requests calls of its own (the one new Meta API call this step
# needed — field-type introspection — lives in
# tools.airtable_gateway.get_table_schema(), not here).
#
# CLI usage:
#   python -m core.emergency_stop_preflight
#
# Exit codes:
#   0  ok             — schema and data are both valid; safe to proceed.
#   1  internal_error — an unexpected exception in the preflight itself
#                       (never treated as success — a bug here must fail
#                       loudly, not silently pass).
#   2  unavailable     — Airtable could not be reached (network/HTTP/timeout).
#   3  invalid         — table/field schema is wrong, or the durable data is
#                        malformed (missing/duplicate flag, bad Enabled type).
#
# Every diagnostic line is a short, categorized string (missing field
# names, type mismatches, flag names, counts) — never a raw Airtable
# payload, never a secret/token. This mirrors
# adapters/airtable_emergency_stop_store.py's own ReadResult.error style,
# which already avoids dumping raw records.

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_INTERNAL_ERROR = 1
EXIT_UNAVAILABLE = 2
EXIT_INVALID = 3

# Critical field types only — not every column in EmergencyStopFlagFields
# needs a type assertion, only the ones whose wrong type would silently
# corrupt read()/write() (a checkbox misconfigured as a select, a text
# field misconfigured as a number, etc.). Meta API type strings, matching
# the format already used by tools/airtable_gateway.py's
# _SELECT_FIELD_TYPES.
_CRITICAL_FIELD_TYPES = {
    "Flag Name":    "singleLineText",
    "Enabled":      "checkbox",
    "Operation ID": "singleLineText",
}


def _check_schema(table_name: str, required_field_names: frozenset) -> tuple[bool, str]:
    """
    Returns (ok, message) for the SCHEMA check only (table exists, required
    fields exist, critical field types are correct). Never returns an
    "unavailable" outcome itself — the caller wraps this call to translate
    a raised AirtableLookupError into that exit path; this function's
    return value is only ever about schema being valid or invalid.
    """
    from tools.airtable_gateway import get_table_schema

    table = get_table_schema(table_name)
    if table is None:
        return False, f"table {table_name!r} does not exist in the base"

    fields_by_name = {f.get("name"): f for f in table.get("fields", [])}

    missing = sorted(required_field_names - fields_by_name.keys())
    if missing:
        return False, f"missing required fields: {missing}"

    type_errors = []
    for name, expected_type in _CRITICAL_FIELD_TYPES.items():
        actual_type = fields_by_name[name].get("type")
        if actual_type != expected_type:
            type_errors.append(f"{name!r} expected type {expected_type!r}, got {actual_type!r}")
    if type_errors:
        return False, f"invalid field types: {type_errors}"

    return True, "schema ok"


def run_preflight() -> int:
    """
    The actual check, importable/callable directly (used by
    core/predeploy.py — no subprocess spawning, matching how predeploy
    calls core.database_migrations.run_migrations() directly). main() is a
    thin CLI wrapper around this.
    """
    try:
        from adapters.airtable_emergency_stop_store import AirtableEmergencyStopStore
        from airtable_schema import EmergencyStopFlagFields, Tables
        from core.emergency_stop import KNOWN_EMERGENCY_STOP_FLAG_NAMES
        from tools.airtable_gateway import AirtableLookupError

        required_field_names = frozenset({
            EmergencyStopFlagFields.FLAG_NAME,
            EmergencyStopFlagFields.ENABLED,
            EmergencyStopFlagFields.OPERATION_ID,
            EmergencyStopFlagFields.UPDATED_AT,
            EmergencyStopFlagFields.UPDATED_BY,
            EmergencyStopFlagFields.SOURCE,
            EmergencyStopFlagFields.REASON,
        })

        try:
            schema_ok, schema_message = _check_schema(
                Tables.EMERGENCY_STOP_FLAGS, required_field_names
            )
        except AirtableLookupError as e:
            logger.error(f"[emergency_stop_preflight] unavailable: {e}")
            return EXIT_UNAVAILABLE

        if not schema_ok:
            logger.error(f"[emergency_stop_preflight] invalid schema: {schema_message}")
            return EXIT_INVALID

        store = AirtableEmergencyStopStore(known_flag_names=KNOWN_EMERGENCY_STOP_FLAG_NAMES)
        result = store.read()

        if result.status == "ok":
            logger.info(
                "[emergency_stop_preflight] ok — schema valid, all %d canonical flags present",
                len(KNOWN_EMERGENCY_STOP_FLAG_NAMES),
            )
            return EXIT_OK

        if result.status == "unavailable":
            logger.error(f"[emergency_stop_preflight] unavailable: {result.error}")
            return EXIT_UNAVAILABLE

        # status == "invalid" — the adapter's own ReadResult.error already
        # distinguishes missing/duplicate/non-boolean-Enabled/internal_error
        # (see adapters/airtable_emergency_stop_store.py) and is already
        # free of raw payloads/secrets; surface it as-is rather than
        # re-deriving the same classification here.
        logger.error(f"[emergency_stop_preflight] invalid data: {result.error}")
        return EXIT_INVALID

    except Exception as e:  # noqa: BLE001 — top-level guard: a bug here must never read as success
        logger.error(f"[emergency_stop_preflight] internal_error: unexpected {type(e).__name__}: {e}")
        return EXIT_INTERNAL_ERROR


def main() -> int:
    logger.info("Emergency Stop Preflight — PATCH 3B Step 4 (read-only)")
    return run_preflight()


if __name__ == "__main__":
    sys.exit(main())
