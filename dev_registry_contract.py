"""Neutral, pure parser and validator for the canonical §3.5 Registry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


REGISTRY_PATH = Path("docs/governance/BOSS_UNIFIED_MASTER_PLAN.md")
WORK_STATES = frozenset({"PLANNED", "ACTIVE", "BLOCKED", "OWNER_DECISION", "CLOSED", "UNKNOWN"})
EVIDENCE_STATES = frozenset({"PLANNED", "CODE_DONE", "MERGED", "WIRED", "DEPLOYED", "RUNTIME_VERIFIED", "UNKNOWN"})
HORIZONS = frozenset({f"H{i}" for i in range(8)})
REQUIRED_COLUMNS = (
    "Initiative Key", "Initiative / Document", "Scope", "Horizon", "Work State",
    "Current Stage", "Evidence State", "Next Decided Step", "Needs Verification",
    "Blocked", "Owner Decision Required", "Last Reconciled", "Evidence Source",
)
KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]+$")


class RegistryValidationError(ValueError):
    """Raised when §3.5 is missing or malformed."""


@dataclass(frozen=True)
class RegistryRow:
    line_number: int
    values: dict[str, str]


def _section_lines(text: str) -> tuple[int, list[tuple[int, str]]]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## 3.5 רישום עבודה חי")), None)
    if start is None:
        raise RegistryValidationError("Active Work Registry section 3.5 not found")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("### 3.5 Runtime Capability Status")), None)
    if end is None:
        raise RegistryValidationError("section 3.5 runtime boundary not found")
    return start + 1, list(enumerate(lines[start + 1:end], start + 2))


def _cells(line: str) -> list[str]:
    if not line.startswith("|") or not line.rstrip().endswith("|"):
        raise RegistryValidationError("malformed Registry table row")
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_registry(text: str) -> tuple[RegistryRow, ...]:
    _, section = _section_lines(text)
    header_index = next((i for i, line in section if line.startswith("| Initiative Key |")), None)
    if header_index is None:
        raise RegistryValidationError("required Registry header not found")
    header_line = next(line for i, line in section if i == header_index)
    header = tuple(_cells(header_line))
    if header != REQUIRED_COLUMNS:
        raise RegistryValidationError(f"required columns/order mismatch: expected {REQUIRED_COLUMNS!r}, got {header!r}")
    section_position = next(pos for pos, (i, _) in enumerate(section) if i == header_index)
    if section_position + 1 >= len(section):
        raise RegistryValidationError("Registry separator row missing")
    separator_index, separator_line = section[section_position + 1]
    separator = _cells(separator_line)
    if len(separator) != len(REQUIRED_COLUMNS) or any(set(value) - {"-"} or not value for value in separator):
        raise RegistryValidationError(f"malformed Registry separator at line {separator_index}")
    rows: list[RegistryRow] = []
    for line_number, line in section[section_position + 2:]:
        if not line.strip():
            continue
        if not line.startswith("|"):
            break
        values = _cells(line)
        if len(values) != len(REQUIRED_COLUMNS):
            raise RegistryValidationError(f"malformed Registry row at line {line_number}: expected {len(REQUIRED_COLUMNS)} cells, got {len(values)}")
        rows.append(RegistryRow(line_number, dict(zip(REQUIRED_COLUMNS, values))))
    if not rows:
        raise RegistryValidationError("Registry has no data rows")
    return tuple(rows)


def _valid_timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return True


def validate_registry_text(text: str) -> tuple[RegistryRow, ...]:
    rows = parse_registry(text)
    seen_keys: set[str] = set()
    for row in rows:
        values = row.values
        key = values["Initiative Key"]
        if not KEY_PATTERN.fullmatch(key):
            raise RegistryValidationError(f"invalid Initiative Key at line {row.line_number}: {key!r}")
        if key in seen_keys:
            raise RegistryValidationError(f"duplicate Initiative Key at line {row.line_number}: {key!r}")
        seen_keys.add(key)
        for column in REQUIRED_COLUMNS:
            if not values[column]:
                raise RegistryValidationError(f"missing required field {column!r} at line {row.line_number}")
        if values["Horizon"] not in HORIZONS:
            raise RegistryValidationError(f"invalid Horizon at line {row.line_number}: {values['Horizon']!r}")
        if values["Work State"] not in WORK_STATES:
            raise RegistryValidationError(f"invalid Work State at line {row.line_number}: {values['Work State']!r}")
        if values["Evidence State"] not in EVIDENCE_STATES:
            raise RegistryValidationError(f"invalid Evidence State at line {row.line_number}: {values['Evidence State']!r}")
        for column in ("Needs Verification", "Blocked", "Owner Decision Required"):
            if values[column] not in {"true", "false"}:
                raise RegistryValidationError(f"invalid boolean {column!r} at line {row.line_number}: {values[column]!r}")
        if values["Work State"] == "BLOCKED" and values["Blocked"] != "true":
            raise RegistryValidationError(f"BLOCKED Work State requires Blocked=true at line {row.line_number}")
        if values["Work State"] == "OWNER_DECISION" and values["Owner Decision Required"] != "true":
            raise RegistryValidationError(f"OWNER_DECISION Work State requires Owner Decision Required=true at line {row.line_number}")
        if values["Work State"] == "CLOSED" and values["Blocked"] == "true":
            raise RegistryValidationError(f"CLOSED Work State cannot have Blocked=true at line {row.line_number}")
        if values["Work State"] == "CLOSED" and values["Owner Decision Required"] == "true":
            raise RegistryValidationError(f"CLOSED Work State cannot have Owner Decision Required=true at line {row.line_number}")
        if values["Evidence State"] == "RUNTIME_VERIFIED" and values["Needs Verification"] != "false":
            raise RegistryValidationError(f"RUNTIME_VERIFIED Evidence State requires Needs Verification=false at line {row.line_number}")
        if not _valid_timestamp(values["Last Reconciled"]):
            raise RegistryValidationError(f"invalid Last Reconciled at line {row.line_number}: {values['Last Reconciled']!r}")
        source = values["Evidence Source"]
        if values["Evidence State"] == "UNKNOWN" and not re.search(r"unknown|no-explicit-evidence|migration", source, re.IGNORECASE):
            raise RegistryValidationError(f"UNKNOWN Evidence State requires fail-closed provenance at line {row.line_number}")
    return rows


def validate_registry_file(path: Path = REGISTRY_PATH) -> tuple[RegistryRow, ...]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RegistryValidationError(f"cannot read Registry file {path}: {exc}") from exc
    return validate_registry_text(text)
