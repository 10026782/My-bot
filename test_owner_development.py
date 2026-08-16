from pathlib import Path

from core.owner_development import build_owner_development_status, generate_owner_development_status
from dev_registry_contract import REQUIRED_COLUMNS


def _registry(rows):
    lines = [
        "## 3.5 רישום עבודה חי (Active Work Registry)",
        "| " + " | ".join(REQUIRED_COLUMNS) + " |",
        "|" + "|".join("---" for _ in REQUIRED_COLUMNS) + "|",
    ]
    for row in rows:
        values = {
            "Initiative Key": "EXAMPLE_INITIATIVE",
            "Initiative / Document": "Example",
            "Scope": "Testing",
            "Horizon": "H0",
            "Work State": "PLANNED",
            "Current Stage": "Owner stage",
            "Evidence State": "UNKNOWN",
            "Next Decided Step": "Review",
            "Needs Verification": "false",
            "Blocked": "false",
            "Owner Decision Required": "false",
            "Last Reconciled": "2026-08-16T00:00:00Z",
            "Evidence Source": "migration-no-explicit-evidence",
        }
        values.update(row)
        lines.append("| " + " | ".join(values[column] for column in REQUIRED_COLUMNS) + " |")
    lines.append("### 3.5 Runtime Capability Status")
    return "\n".join(lines)


def test_valid_registry_projection_and_direct_field_classification():
    result = build_owner_development_status(_registry([
        {"Initiative Key": "ACTIVE_ITEM", "Work State": "ACTIVE", "Evidence State": "UNKNOWN"},
        {"Initiative Key": "BLOCKED_ITEM", "Blocked": "true", "Current Stage": "any prose"},
        {"Initiative Key": "DECISION_ITEM", "Owner Decision Required": "true"},
        {"Initiative Key": "VERIFY_ITEM", "Needs Verification": "true"},
        {"Initiative Key": "CLOSED_ITEM", "Work State": "CLOSED", "Evidence State": "UNKNOWN", "Next Decided Step": "—"},
    ]), checked_at="2026-08-16T12:00:00Z")
    assert result.projection_state == "CURRENT"
    assert result.current_focus[0].initiative_key == "ACTIVE_ITEM"
    assert result.blocked[0].initiative_key == "BLOCKED_ITEM"
    assert result.owner_decisions[0].initiative_key == "DECISION_ITEM"
    assert result.needs_verification[0].initiative_key == "VERIFY_ITEM"
    assert result.recently_closed[0].initiative_key == "CLOSED_ITEM"


def test_next_step_and_current_stage_are_preserved_without_parsing():
    result = build_owner_development_status(_registry([{
        "Initiative Key": "STAGE_PROSE",
        "Work State": "PLANNED",
        "Current Stage": "BLOCKED and owner decision language is only explanation",
        "Next Decided Step": " preserve this exact next step ",
        "Evidence State": "MERGED",
    }]), checked_at="2026-08-16T12:00:00Z")
    item = result.next_actions[0]
    assert item.work_state == "PLANNED"
    assert item.evidence_state == "MERGED"
    assert item.current_stage == "BLOCKED and owner decision language is only explanation"
    assert item.next_step == "preserve this exact next step"


def test_unknown_evidence_stays_unknown_and_does_not_make_work_blocked():
    result = build_owner_development_status(_registry([{
        "Initiative Key": "UNKNOWN_ITEM", "Evidence State": "UNKNOWN", "Work State": "ACTIVE",
    }]), checked_at="2026-08-16T12:00:00Z")
    item = result.current_focus[0]
    assert item.evidence_state == "UNKNOWN"
    assert item.work_state == "ACTIVE"
    assert result.blocked == ()


def test_deterministic_ordering_prefers_horizon_then_gate_then_key():
    result = build_owner_development_status(_registry([
        {"Initiative Key": "Z_ACTIVE", "Work State": "ACTIVE", "Horizon": "H1"},
        {"Initiative Key": "A_ACTIVE", "Work State": "ACTIVE", "Horizon": "H0"},
        {"Initiative Key": "G_BLOCKED", "Blocked": "true", "Horizon": "H0"},
    ]), checked_at="2026-08-16T12:00:00Z")
    assert [item.initiative_key for item in result.next_actions] == ["G_BLOCKED", "A_ACTIVE", "Z_ACTIVE"]


def test_section_bounds_are_deterministic():
    rows = [{"Initiative Key": f"ACTIVE_{index:02d}", "Work State": "ACTIVE"} for index in range(10)]
    rows += [{"Initiative Key": f"NEXT_{index:02d}", "Work State": "PLANNED", "Next Decided Step": "do"} for index in range(10)]
    result = build_owner_development_status(_registry(rows), checked_at="2026-08-16T12:00:00Z")
    assert len(result.current_focus) == 8
    assert len(result.next_actions) == 5


def test_freshness_current_and_stale_use_last_reconciled():
    result = build_owner_development_status(_registry([
        {"Initiative Key": "CURRENT_ITEM", "Last Reconciled": "2026-08-15T00:00:00Z"},
        {"Initiative Key": "STALE_ITEM", "Last Reconciled": "2026-08-01T00:00:00Z"},
    ]), checked_at="2026-08-16T12:00:00Z")
    by_key = {item.initiative_key: item for item in result.next_actions}
    assert by_key["CURRENT_ITEM"].freshness == "CURRENT"
    assert by_key["STALE_ITEM"].freshness == "STALE"


def test_all_current_projected_rows_make_projection_current():
    result = build_owner_development_status(_registry([
        {"Initiative Key": "CURRENT_ACTIVE", "Work State": "ACTIVE"},
        {"Initiative Key": "CURRENT_NEXT", "Work State": "PLANNED"},
    ]), checked_at="2026-08-16T12:00:00Z")
    assert result.projection_state == "CURRENT"


def test_stale_projected_row_makes_projection_partial():
    result = build_owner_development_status(_registry([
        {"Initiative Key": "STALE_ACTIVE", "Work State": "ACTIVE", "Last Reconciled": "2026-08-01T00:00:00Z"},
        {"Initiative Key": "CURRENT_NEXT", "Work State": "PLANNED"},
    ]), checked_at="2026-08-16T12:00:00Z")
    assert result.projection_state == "PARTIAL"


def test_invalid_registry_fails_closed_without_fallback():
    result = build_owner_development_status("ROADMAP says everything is complete", checked_at="2026-08-16T12:00:00Z")
    assert result.projection_state == "UNKNOWN"
    assert result.current_focus == ()
    assert result.next_actions == ()


def test_duplicate_key_fails_closed():
    result = build_owner_development_status(_registry([
        {"Initiative Key": "DUPLICATE_KEY"}, {"Initiative Key": "DUPLICATE_KEY"},
    ]), checked_at="2026-08-16T12:00:00Z")
    assert result.projection_state == "UNKNOWN"


def test_consumer_is_read_only(tmp_path):
    path = tmp_path / "BOSS_UNIFIED_MASTER_PLAN.md"
    original = _registry([{"Initiative Key": "READ_ONLY_ITEM", "Work State": "ACTIVE"}])
    path.write_text(original, encoding="utf-8")
    result = generate_owner_development_status(path, checked_at="2026-08-16T12:00:00Z")
    assert result.projection_state == "CURRENT"
    assert path.read_text(encoding="utf-8") == original


def test_closed_next_step_is_not_an_active_next_action():
    result = build_owner_development_status(_registry([
        {"Initiative Key": "CLOSED_ITEM", "Work State": "CLOSED", "Next Decided Step": "archive"},
        {"Initiative Key": "ACTIVE_ITEM", "Work State": "ACTIVE", "Next Decided Step": "continue"},
        {"Initiative Key": "PLANNED_ITEM", "Work State": "PLANNED", "Next Decided Step": "start"},
    ]), checked_at="2026-08-16T12:00:00Z")
    next_keys = [item.initiative_key for item in result.next_actions]
    assert "CLOSED_ITEM" not in next_keys
    assert "ACTIVE_ITEM" in next_keys
    assert "PLANNED_ITEM" in next_keys
    assert result.recently_closed[0].initiative_key == "CLOSED_ITEM"
