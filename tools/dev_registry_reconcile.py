#!/usr/bin/env python3
"""Bounded reconciliation for the canonical §3.5 Active Work Registry.

This module consumes only explicitly keyed, structured evidence manifests.  It
does not search repository prose, infer initiative identity, call a network
service, or change Work State.  Dry-run is the normal safe mode; writes require
``--apply`` and are atomic.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.dev_registry_validator import (
    EVIDENCE_STATES,
    REGISTRY_PATH,
    RegistryRow,
    RegistryValidationError,
    validate_registry_text,
)


EVIDENCE_ORDER = {
    "PLANNED": 0,
    "CODE_DONE": 1,
    "MERGED": 2,
    "WIRED": 3,
    "DEPLOYED": 4,
    "RUNTIME_VERIFIED": 5,
}
EVIDENCE_TYPES = frozenset({
    "planning",
    "code",
    "git_main",
    "merged_pr",
    "wiring",
    "deployment",
    "runtime",
})
SOURCE_PREFIXES = {
    "planning": "roadmap:",
    "code": "code:",
    "git_main": "git:main:",
    "merged_pr": "pr:",
    "wiring": "wiring:",
    "deployment": "deployment:",
    "runtime": "runtime-evidence:",
}
ISO_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


class ReconciliationError(ValueError):
    """Raised for malformed evidence or an invalid proposed Registry."""


@dataclass(frozen=True)
class EvidenceRecord:
    initiative_key: str
    evidence_type: str
    evidence_state: str
    source_ref: str
    observed_at: str
    version_ref: str | None = None
    confidence: str = "explicit"
    requires_runtime_verification: bool | None = None


@dataclass(frozen=True)
class ReconciliationReport:
    initiatives_inspected: int
    changed_keys: tuple[str, ...]
    unchanged_keys: tuple[str, ...]
    unmapped_evidence: tuple[str, ...]
    conflicts: tuple[str, ...]
    downgrades: tuple[str, ...]
    invalid_evidence: tuple[str, ...]


def _timestamp(value: str, field: str) -> str:
    if not isinstance(value, str) or not ISO_TIMESTAMP.fullmatch(value):
        raise ReconciliationError(f"invalid {field}: {value!r}")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReconciliationError(f"invalid {field}: {value!r}") from exc
    return value


def validate_evidence_record(record: EvidenceRecord) -> EvidenceRecord:
    """Validate the evidence contract at every caller boundary.

    JSON parsing and programmatic callers intentionally share this function;
    constructing a dataclass directly does not confer authority.
    """
    if not isinstance(record, EvidenceRecord):
        raise ReconciliationError(f"expected EvidenceRecord, got {type(record).__name__}")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]+", record.initiative_key):
        raise ReconciliationError(f"invalid initiative_key: {record.initiative_key!r}")
    if record.evidence_type not in EVIDENCE_TYPES:
        raise ReconciliationError(f"unsupported evidence_type: {record.evidence_type!r}")
    if record.evidence_state not in EVIDENCE_STATES:
        raise ReconciliationError(f"unsupported evidence_state: {record.evidence_state!r}")
    if record.confidence != "explicit":
        raise ReconciliationError("confidence must be explicit")
    _timestamp(record.observed_at, "observed_at")
    prefix = SOURCE_PREFIXES[record.evidence_type]
    if not isinstance(record.source_ref, str) or not record.source_ref.startswith(prefix) or record.source_ref == prefix:
        raise ReconciliationError(f"invalid source_ref for {record.evidence_type}: {record.source_ref!r}")
    if record.evidence_state == "RUNTIME_VERIFIED" and record.evidence_type != "runtime":
        raise ReconciliationError("RUNTIME_VERIFIED requires evidence_type=runtime")
    if record.evidence_state == "DEPLOYED" and record.evidence_type not in {"deployment", "runtime"}:
        raise ReconciliationError("DEPLOYED requires deployment/runtime evidence")
    if record.evidence_type in {"deployment", "runtime"} and not isinstance(record.version_ref, str):
        raise ReconciliationError(f"{record.evidence_type} evidence requires an explicit version_ref")
    if record.evidence_type == "git_main" and record.evidence_state not in {"CODE_DONE", "MERGED"}:
        raise ReconciliationError("git_main evidence may establish only CODE_DONE or MERGED")
    if record.requires_runtime_verification is not None and not isinstance(record.requires_runtime_verification, bool):
        raise ReconciliationError("malformed requires_runtime_verification")
    return record


def _record_from_mapping(raw: object, *, index: int) -> EvidenceRecord:
    if not isinstance(raw, dict):
        raise ReconciliationError(f"evidence record {index} must be an object")
    required = ("initiative_key", "evidence_type", "evidence_state", "source_ref", "observed_at")
    missing = [field for field in required if not raw.get(field)]
    if missing:
        raise ReconciliationError(f"evidence record {index} missing {', '.join(missing)}")
    record = EvidenceRecord(
        initiative_key=raw["initiative_key"],
        evidence_type=raw["evidence_type"],
        evidence_state=raw["evidence_state"],
        source_ref=raw["source_ref"],
        observed_at=raw["observed_at"],
        version_ref=raw.get("version_ref"),
        confidence=raw.get("confidence", "explicit"),
        requires_runtime_verification=raw.get("requires_runtime_verification"),
    )
    try:
        return validate_evidence_record(record)
    except ReconciliationError as exc:
        raise ReconciliationError(f"evidence record {index}: {exc}") from exc


class JsonEvidenceAdapter:
    """Read an explicit, keyed JSON evidence manifest; never parse prose."""

    def read(self, path: Path) -> tuple[EvidenceRecord, ...]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ReconciliationError(f"cannot read evidence manifest {path}: {exc}") from exc
        records = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ReconciliationError("evidence manifest must be a list or an object with records")
        parsed: list[EvidenceRecord] = []
        for index, raw in enumerate(records, start=1):
            parsed.append(_record_from_mapping(raw, index=index))
        return tuple(parsed)


def _registry_line(row: RegistryRow) -> str:
    return "| " + " | ".join(row.values[column] for column in row.values) + " |"


def _source_for(records: Iterable[EvidenceRecord]) -> str:
    refs = sorted({record.source_ref for record in records})
    return ";".join(refs)


def _same_evidence_type_conflict(records: list[EvidenceRecord]) -> str | None:
    by_type: dict[str, set[str]] = {}
    for record in records:
        by_type.setdefault(record.evidence_type, set()).add(record.evidence_state)
    for evidence_type, states in sorted(by_type.items()):
        if len(states) > 1:
            return f"{evidence_type}: conflicting states {sorted(states)}"
    return None


def _policy_conflict(records: list[EvidenceRecord]) -> str | None:
    values = {record.requires_runtime_verification for record in records if record.requires_runtime_verification is not None}
    if len(values) > 1:
        return "conflicting requires_runtime_verification policy values"
    return None


def reconcile_text(
    text: str,
    records: Iterable[EvidenceRecord],
    *,
    reconciled_at: str,
) -> tuple[str, ReconciliationReport]:
    _timestamp(reconciled_at, "reconciled_at")
    rows = validate_registry_text(text)
    by_key = {row.values["Initiative Key"]: row for row in rows}
    grouped: dict[str, list[EvidenceRecord]] = {}
    unmapped: list[str] = []
    invalid: list[str] = []
    for record in records:
        # This is deliberately before grouping, ranking, conflict detection,
        # and any proposed Registry mutation.  Direct dataclass callers get
        # exactly the same contract as JSON adapter callers.
        validate_evidence_record(record)
        if record.initiative_key not in by_key:
            unmapped.append(f"{record.source_ref}:{record.initiative_key}")
        else:
            grouped.setdefault(record.initiative_key, []).append(record)

    proposed = [dict(row.values) for row in rows]
    changed: list[str] = []
    unchanged: list[str] = []
    conflicts: list[str] = []
    downgrades: list[str] = []
    for values in proposed:
        key = values["Initiative Key"]
        evidence = grouped.get(key, [])
        if not evidence:
            unchanged.append(key)
            continue
        conflict = _same_evidence_type_conflict(evidence)
        if conflict:
            conflicts.append(f"{key}: {conflict}")
            unchanged.append(key)
            continue
        policy_conflict = _policy_conflict(evidence)
        if policy_conflict:
            conflicts.append(f"{key}: {policy_conflict}")
            unchanged.append(key)
            continue
        strongest = max(evidence, key=lambda item: EVIDENCE_ORDER.get(item.evidence_state, -1))
        current = values["Evidence State"]
        if current != "UNKNOWN" and strongest.evidence_state != "UNKNOWN":
            current_rank = EVIDENCE_ORDER.get(current, -1)
            new_rank = EVIDENCE_ORDER.get(strongest.evidence_state, -1)
            if new_rank < current_rank:
                unchanged.append(key)
                continue
            if new_rank == current_rank and strongest.evidence_state == current:
                # Still record a successful reconciliation only when explicit evidence exists.
                pass
        if strongest.evidence_state == "UNKNOWN":
            unchanged.append(key)
            continue
        if current != "UNKNOWN" and EVIDENCE_ORDER.get(strongest.evidence_state, -1) < EVIDENCE_ORDER.get(current, -1):
            downgrades.append(f"{key}: {current} -> {strongest.evidence_state}")
            unchanged.append(key)
            continue
        values["Evidence State"] = strongest.evidence_state
        values["Evidence Source"] = _source_for(evidence)
        values["Last Reconciled"] = reconciled_at
        if strongest.evidence_state == "RUNTIME_VERIFIED":
            values["Needs Verification"] = "false"
        elif strongest.requires_runtime_verification is True:
            values["Needs Verification"] = "true"
        elif strongest.evidence_state == "PLANNED":
            values["Needs Verification"] = "false"
        if values != next(row.values for row in rows if row.values["Initiative Key"] == key):
            changed.append(key)
        else:
            unchanged.append(key)

    line_map = {row.line_number: values for row, values in zip(rows, proposed)}
    lines = text.splitlines(keepends=True)
    for line_number, values in line_map.items():
        original = lines[line_number - 1]
        newline = "\n" if original.endswith("\n") else ""
        lines[line_number - 1] = _registry_line(type("Row", (), {"values": values})()) + newline
    result = "".join(lines)
    validate_registry_text(result)
    return result, ReconciliationReport(
        initiatives_inspected=len(rows),
        changed_keys=tuple(changed),
        unchanged_keys=tuple(unchanged),
        unmapped_evidence=tuple(unmapped),
        conflicts=tuple(conflicts),
        downgrades=tuple(downgrades),
        invalid_evidence=tuple(invalid),
    )


def atomic_write(path: Path, text: str) -> None:
    """Replace a validated document atomically, leaving the original on failure."""
    directory = path.parent
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=directory)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def reconcile_file(
    registry_path: Path = REGISTRY_PATH,
    *,
    records: Iterable[EvidenceRecord] = (),
    apply: bool = False,
    reconciled_at: str | None = None,
) -> ReconciliationReport:
    text = registry_path.read_text(encoding="utf-8")
    now = reconciled_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    proposed, report = reconcile_text(text, records, reconciled_at=now)
    if apply:
        atomic_write(registry_path, proposed)
        try:
            validate_registry_text(registry_path.read_text(encoding="utf-8"))
        except Exception:
            # A post-write read/validation failure must not leave a partial
            # Registry update behind.  Restore the exact original document.
            atomic_write(registry_path, text)
            raise
    return report


def _print_report(report: ReconciliationReport, *, apply: bool) -> None:
    print(json.dumps({
        "mode": "apply" if apply else "dry-run",
        "initiatives_inspected": report.initiatives_inspected,
        "proposed_changes": list(report.changed_keys),
        "unchanged_rows": list(report.unchanged_keys),
        "unmapped_evidence": list(report.unmapped_evidence),
        "conflicts": list(report.conflicts),
        "downgrades_requiring_review": list(report.downgrades),
        "invalid_evidence": list(report.invalid_evidence),
    }, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--evidence-file", type=Path)
    parser.add_argument("--reconciled-at")
    args = parser.parse_args(argv)
    try:
        records = JsonEvidenceAdapter().read(args.evidence_file) if args.evidence_file else ()
        report = reconcile_file(
            args.registry,
            records=records,
            apply=args.apply,
            reconciled_at=args.reconciled_at,
        )
    except (OSError, ReconciliationError, RegistryValidationError) as exc:
        print(f"DEV-REG RECONCILIATION FAILED: {exc}")
        return 1
    _print_report(report, apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
