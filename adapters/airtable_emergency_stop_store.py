# adapters/airtable_emergency_stop_store.py — PATCH 3B Step 2
#
# Concrete EmergencyStopStore (core/emergency_stop.py Protocol) backed by
# Tables.EMERGENCY_STOP_FLAGS, via tools/airtable_gateway.py — the sole
# sanctioned Airtable I/O path in this codebase (CLAUDE.md "Iron rule").
#
# Wired by core.emergency_stop_bootstrap at runtime. No network call happens
# at import time — Airtable I/O occurs only at read()/write() call time.
#
# core/emergency_stop.py does not import this module (dependency points one
# way: adapter -> core, never core -> adapter).

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from airtable_schema import EmergencyStopFlagFields, Tables
from core.emergency_stop import (
    KNOWN_EMERGENCY_STOP_FLAG_NAMES,
    FlagRecord,
    ReadResult,
    WriteResult,
)
from tools.airtable_gateway import (
    AirtableLookupError,
    airtable_create,
    airtable_patch,
    at_get_by_field,
    at_list_by_formula,
)

logger = logging.getLogger(__name__)

_F = EmergencyStopFlagFields


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AirtableEmergencyStopStore:
    """EmergencyStopStore backed by Tables.EMERGENCY_STOP_FLAGS.

    One record per flag name (primary field Flag Name, plain singleLineText —
    not singleSelect). `known_flag_names` defaults to
    core.emergency_stop.KNOWN_EMERGENCY_STOP_FLAG_NAMES (never imported from
    feature_flags.py here — this module stays decoupled from the flag
    registry) and must never be empty: an empty set would silently skip the
    missing-record integrity check entirely, which is never a valid
    configuration (see EmergencyStopManager.__init__ for the same rule).

    read() fetches every record in the table in a single call and validates
    the whole set's shape before returning status="ok" — a partial/best-effort
    result is never returned, so a caller (core.emergency_stop.EmergencyStopManager)
    can never mistake a malformed durable state for a trustworthy one:
      - AirtableLookupError (network/HTTP failure/timeout) -> status="unavailable"
      - missing / duplicate Flag Name, or a non-boolean
        Enabled value, anywhere in the read set             -> status="invalid"
      - a genuinely unexpected exception (a bug, not a
        documented failure mode) is never reported as
        "unavailable" — that would tell a caller "retry
        later, this is transient" about something that is
        not transient at all, and the manager's own
        _safe_read_locked() fallback would collapse it back
        into "unavailable" a second time regardless. Instead
        it comes back as status="invalid" with an
        "internal_error: " prefixed diagnostic naming the
        exception type, so it stays distinguishable in logs
        and assertable in tests instead of being silently
        indistinguishable from an ordinary network blip.

    write() creates-or-updates a single flag's record, then performs an
    independent readback to populate WriteResult.verified — ok=True does not
    imply verified=True (see WriteResult's own docstring in core/emergency_stop.py).
    This class holds no cache of its own; verified=False changes nothing here
    to "un-do" — it is purely a signal for the (future) caller to decide
    whether to trust/apply the write, matching core/emergency_stop.py's rule
    that only a verified "ok" read result may ever replace a cache.
    """

    def __init__(
        self,
        known_flag_names: Iterable[str] = KNOWN_EMERGENCY_STOP_FLAG_NAMES,
        *,
        timeout: float = 10.0,
        source: str = "emergency_stop",
    ) -> None:
        self._known_flag_names = frozenset(known_flag_names)
        if not self._known_flag_names:
            # Default is always non-empty (KNOWN_EMERGENCY_STOP_FLAG_NAMES) — the
            # only way to land here is an explicit empty override.
            raise ValueError(
                "known_flag_names must not be empty — omit the argument to use "
                "KNOWN_EMERGENCY_STOP_FLAG_NAMES, the canonical default."
            )
        self._timeout = timeout
        self._source = source

    # ── EmergencyStopStore.read() ─────────────────────────────────────

    def read(self) -> ReadResult:
        try:
            records = at_list_by_formula(
                Tables.EMERGENCY_STOP_FLAGS,
                formula="TRUE()",
                max_records=100,  # table holds one record per known flag — a handful, not a scan
                timeout=self._timeout,
            )
        except AirtableLookupError as e:
            return ReadResult(status="unavailable", error=f"read failed: {e}")
        except Exception as e:  # noqa: BLE001 — Protocol contract: never raise (see class docstring)
            return ReadResult(
                status="invalid",
                error=f"internal_error: unexpected {type(e).__name__} fetching records: {e}",
            )

        try:
            return self._parse_records(records)
        except Exception as e:  # noqa: BLE001 — malformed/unexpected record shape is a bug, not a network blip
            return ReadResult(
                status="invalid",
                error=f"internal_error: unexpected {type(e).__name__} parsing records: {e}",
            )

    def _parse_records(self, records: list[dict]) -> ReadResult:
        flags: dict[str, FlagRecord] = {}
        duplicates: set[str] = set()
        invalid: list[str] = []

        for rec in records:
            fields = rec.get("fields", {})
            name = fields.get(_F.FLAG_NAME)
            if not isinstance(name, str) or not name.strip():
                invalid.append(f"record {rec.get('id', '?')}: missing/blank {_F.FLAG_NAME!r}")
                continue
            name = name.strip()

            # Airtable omits an unchecked checkbox key entirely — absence
            # means False, not "field missing". Only a present-but-non-bool
            # value is a real data error.
            enabled = fields.get(_F.ENABLED, False)
            if not isinstance(enabled, bool):
                invalid.append(f"{name}: {_F.ENABLED!r}={enabled!r} is not a boolean")
                continue

            if name in flags:
                duplicates.add(name)
                continue

            # Operation ID is metadata, not part of the integrity check
            # below — a flag record that was never written yet may
            # legitimately have no Operation ID (None), unlike a missing or
            # non-boolean Enabled value, which IS a data error.
            operation_id = fields.get(_F.OPERATION_ID)
            flags[name] = FlagRecord(enabled=enabled, operation_id=operation_id)

        if invalid:
            return ReadResult(status="invalid", error=f"invalid records: {invalid}")
        if duplicates:
            return ReadResult(
                status="invalid",
                error=f"duplicate {_F.FLAG_NAME!r} records: {sorted(duplicates)}",
            )

        missing = sorted(self._known_flag_names - flags.keys())
        if missing:
            return ReadResult(status="invalid", error=f"missing flag records: {missing}")

        return ReadResult(status="ok", flags=flags)

    # ── EmergencyStopStore.write() ────────────────────────────────────

    def write(
        self,
        flag_name: str,
        enabled: bool,
        *,
        operation_id: str,
        updated_by: str,
        source: str,
        reason: str,
        expected_operation_id: Optional[str] = None,
    ) -> WriteResult:
        try:
            existing = at_get_by_field(
                Tables.EMERGENCY_STOP_FLAGS, _F.FLAG_NAME, flag_name, timeout=self._timeout
            )
        except AirtableLookupError as e:
            return WriteResult(ok=False, verified=False, error=f"pre-write lookup failed: {e}")
        except Exception as e:  # noqa: BLE001 — Protocol contract: never raise (see class docstring)
            return WriteResult(
                ok=False,
                verified=False,
                error=f"internal_error: unexpected {type(e).__name__} in pre-write lookup: {e}",
            )

        if expected_operation_id is not None and existing is not None:
            current_op = existing.get("fields", {}).get(_F.OPERATION_ID)
            if current_op != expected_operation_id:
                return WriteResult(
                    ok=False,
                    verified=False,
                    conflict=True,
                    error=(
                        f"expected_operation_id={expected_operation_id!r} "
                        f"but record has {current_op!r}"
                    ),
                )

        fields = {
            _F.FLAG_NAME: flag_name,
            _F.ENABLED: enabled,
            _F.OPERATION_ID: operation_id,
            _F.UPDATED_AT: _now_iso(),
            _F.UPDATED_BY: updated_by,
            _F.SOURCE: source,
            _F.REASON: reason,
        }

        try:
            if existing is not None:
                write_ok = airtable_patch(
                    Tables.EMERGENCY_STOP_FLAGS,
                    existing["id"],
                    fields,
                    source=self._source,
                    timeout=self._timeout,
                )
            else:
                created = airtable_create(
                    Tables.EMERGENCY_STOP_FLAGS,
                    fields,
                    source=self._source,
                    timeout=self._timeout,
                )
                write_ok = created is not None
        except Exception as e:  # noqa: BLE001 — Protocol contract: never raise (see class docstring)
            return WriteResult(
                ok=False,
                verified=False,
                error=f"internal_error: unexpected {type(e).__name__} during write: {e}",
            )

        if not write_ok:
            return WriteResult(ok=False, verified=False, error="gateway write returned failure")

        return self._verify_write(flag_name, enabled, operation_id)

    def _verify_write(self, flag_name: str, enabled: bool, operation_id: str) -> WriteResult:
        try:
            record = at_get_by_field(
                Tables.EMERGENCY_STOP_FLAGS, _F.FLAG_NAME, flag_name, timeout=self._timeout
            )
        except AirtableLookupError as e:
            return WriteResult(ok=True, verified=False, error=f"readback failed: {e}")
        except Exception as e:  # noqa: BLE001 — Protocol contract: never raise (see class docstring)
            return WriteResult(
                ok=True,
                verified=False,
                error=f"internal_error: unexpected {type(e).__name__} during readback: {e}",
            )

        if record is None:
            return WriteResult(ok=True, verified=False, error="readback found no record")

        readback_fields = record.get("fields", {})
        if readback_fields.get(_F.ENABLED, False) != enabled:
            return WriteResult(ok=True, verified=False, error="readback mismatch: Enabled")
        if readback_fields.get(_F.OPERATION_ID) != operation_id:
            return WriteResult(ok=True, verified=False, error="readback mismatch: Operation ID")

        return WriteResult(ok=True, verified=True)
