from pathlib import Path

import pytest

from tools.dev_registry_validator import (
    REQUIRED_COLUMNS,
    RegistryValidationError,
    validate_registry_file,
    validate_registry_text,
)


ROOT = Path(__file__).resolve().parent


def test_valid_migrated_registry_has_all_rows_and_keys():
    rows = validate_registry_file(ROOT / "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md")
    assert len(rows) == 31
    assert len({row.values["Initiative Key"] for row in rows}) == 31
    assert all(":migration-" in row.values["Evidence Source"] for row in rows)
    assert all(row.values["Evidence State"] == "UNKNOWN" or row.values["Evidence Source"] for row in rows)


def _fixture(**overrides):
    values = {
        "Initiative Key": "EXAMPLE_INITIATIVE",
        "Initiative / Document": "Example",
        "Scope": "Testing",
        "Horizon": "H0",
        "Work State": "PLANNED",
        "Current Stage": "Short owner explanation",
        "Evidence State": "UNKNOWN",
        "Next Decided Step": "Review",
        "Needs Verification": "false",
        "Blocked": "false",
        "Owner Decision Required": "false",
        "Last Reconciled": "2026-08-16T00:00:00Z",
        "Evidence Source": "migration-no-explicit-evidence",
    }
    values.update(overrides)
    return "\n".join([
        "## 3.5 רישום עבודה חי (Active Work Registry)",
        "| " + " | ".join(REQUIRED_COLUMNS) + " |",
        "|" + "|".join("---" for _ in REQUIRED_COLUMNS) + "|",
        "| " + " | ".join(values[column] for column in REQUIRED_COLUMNS) + " |",
        "### 3.5 Runtime Capability Status",
    ])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("Initiative Key", "EXAMPLE_INITIATIVE", "duplicate"),
        ("Horizon", "H9", "Horizon"),
        ("Work State", "IN_PROGRESS", "Work State"),
        ("Evidence State", "DEPLOYMENT_CONFIRMED", "Evidence State"),
        ("Needs Verification", "yes", "boolean"),
        ("Initiative / Document", "", "required field"),
    ],
)
def test_invalid_registry_values_fail_closed(field, value, message):
    if field == "Initiative Key":
        row = _fixture().splitlines()[3]
        text = _fixture().replace("\n### 3.5", "\n" + row + "\n### 3.5")
    else:
        text = _fixture(**{field: value})
    with pytest.raises(RegistryValidationError, match=message):
        validate_registry_text(text)


def test_unknown_evidence_is_accepted_with_explicit_fail_closed_provenance():
    rows = validate_registry_text(_fixture())
    assert rows[0].values["Evidence State"] == "UNKNOWN"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"Work State": "BLOCKED", "Blocked": "false"}, "BLOCKED Work State"),
        ({"Work State": "OWNER_DECISION", "Owner Decision Required": "false"}, "OWNER_DECISION Work State"),
        ({"Work State": "CLOSED", "Blocked": "true"}, "CLOSED Work State"),
        ({"Work State": "CLOSED", "Owner Decision Required": "true"}, "CLOSED Work State"),
        ({"Evidence State": "RUNTIME_VERIFIED", "Needs Verification": "true"}, "RUNTIME_VERIFIED Evidence State"),
    ],
)
def test_cross_field_invariants_fail_closed(overrides, message):
    with pytest.raises(RegistryValidationError, match=message):
        validate_registry_text(_fixture(**overrides))


def test_planned_owner_decision_gate_is_allowed_without_inverse_rule():
    rows = validate_registry_text(_fixture(**{"Owner Decision Required": "true"}))
    assert rows[0].values["Work State"] == "PLANNED"


def test_active_without_blocker_is_allowed_without_inverse_rule():
    rows = validate_registry_text(_fixture(**{"Work State": "ACTIVE", "Blocked": "false"}))
    assert rows[0].values["Work State"] == "ACTIVE"


def test_malformed_row_fails_validation():
    text = _fixture().replace("| EXAMPLE_INITIATIVE |", "| EXAMPLE_INITIATIVE | extra |")
    with pytest.raises(RegistryValidationError, match="malformed Registry row"):
        validate_registry_text(text)
