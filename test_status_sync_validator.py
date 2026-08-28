from pathlib import Path

import pytest

from tools.status_sync_validator import validate_status_sync


ROOT = Path(__file__).resolve().parent


def _roadmap(rows: str, *, date_marker: str = "עודכן: 28/08/2026") -> str:
    return f"""# ROADMAP\n\n{date_marker}\n\n## 2. Active Programs\n\n| ID | Canonical Name | Status | Evidence | Next | Canonical Source |\n|---|---|---|---|---|---|\n{rows}\n\n## 3. Open Architecture / Owner Decisions\n"""


def _row(pid="CHILD", status="PLANNED", evidence="Evidence", next_step="Review", source="ROADMAP.md"):
    return f"| {pid} | Example | {status} | {evidence} | {next_step} | [`source`]({source}) |"


def test_duplicate_program_id_blocks():
    text = _roadmap(_row() + "\n" + _row())
    assert any("DUPLICATE_PROGRAM_ID" in item for item in validate_status_sync(text, repo_root=ROOT))


def test_invalid_status_blocks():
    findings = validate_status_sync(_roadmap(_row(status="RESOLVED")), repo_root=ROOT)
    assert any("INVALID_STATUS" in item for item in findings)


def test_missing_canonical_source_blocks():
    findings = validate_status_sync(_roadmap(_row(source="docs/missing-plan.md")), repo_root=ROOT)
    assert any("MISSING_CANONICAL_SOURCE" in item for item in findings)


def test_stale_next_already_merged_blocks():
    text = _roadmap(_row(status="IN_PROGRESS", next_step="R3.2 — NEXT") + "\n\nR3.2 — MERGED / STATIC VERIFIED")
    assert any("STALE_NEXT_STEP" in item for item in validate_status_sync(text, repo_root=ROOT))


def test_planned_parent_and_active_child_without_justification_blocks():
    text = _roadmap(
        _row("PARENT", "PLANNED")
        + "\n"
        + _row("CHILD", "IN_PROGRESS", "IMPLEMENTATION_OF: PARENT")
    )
    assert any("PARENT_CHILD_STATUS_DRIFT" in item for item in validate_status_sync(text, repo_root=ROOT))


def test_stale_blocker_after_merged_dependency_blocks():
    text = _roadmap(
        _row("A", "IN_PROGRESS", "BLOCKED_BY: B")
        + "\n"
        + _row("B", "MERGED_STATIC")
    )
    assert any("STALE_BLOCKER" in item for item in validate_status_sync(text, repo_root=ROOT))


def test_merged_into_missing_target_blocks():
    findings = validate_status_sync(_roadmap(_row("A", "MERGED_STATIC", "MERGED_INTO: B")), repo_root=ROOT)
    assert any("UNKNOWN_RELATION_TARGET" in item for item in findings)


def test_merged_into_cycle_blocks():
    text = _roadmap(_row("A", "MERGED_STATIC", "MERGED_INTO: B") + "\n" + _row("B", "MERGED_STATIC", "MERGED_INTO: A"))
    assert any("MERGED_INTO_CYCLE" in item for item in validate_status_sync(text, repo_root=ROOT))


def test_resolved_program_cannot_block_dependent():
    text = _roadmap(_row("A", "IN_PROGRESS", "BLOCKED_BY: B") + "\n" + _row("B", "MERGED_STATIC", "RESOLVED: true"))
    assert any("RESOLVED_BLOCKER" in item for item in validate_status_sync(text, repo_root=ROOT))


def test_explicit_pr_sha_evidence_not_on_main_blocks(tmp_path, monkeypatch):
    text = _roadmap(_row("A", "MERGED_STATIC", "merge deadbeef1234567"))
    monkeypatch.setattr("tools.status_sync_validator._commit_exists", lambda *_: False)
    assert any("UNREACHABLE_MERGE_EVIDENCE" in item for item in validate_status_sync(text, repo_root=tmp_path, main_ref="main"))


def test_in_progress_parent_with_merged_child_phase_is_allowed():
    text = _roadmap(_row("PARENT", "IN_PROGRESS") + "\n" + _row("CHILD", "MERGED_STATIC", "IMPLEMENTATION_OF: PARENT"))
    assert not any("PARENT_CHILD_STATUS_DRIFT" in item for item in validate_status_sync(text, repo_root=ROOT))


def test_planned_program_without_started_implementation_is_allowed():
    assert validate_status_sync(_roadmap(_row("A", "PLANNED")), repo_root=ROOT) == []


def test_valid_merged_into_target_is_allowed():
    text = _roadmap(_row("A", "MERGED_STATIC", "MERGED_INTO: B", "Follow parent program") + "\n" + _row("B", "IN_PROGRESS"))
    assert not any("MERGED_INTO" in item or "UNKNOWN_RELATION" in item for item in validate_status_sync(text, repo_root=ROOT))


def test_historical_archive_text_is_not_scanned():
    assert validate_status_sync(_roadmap(_row("A", "PLANNED", "Historical archive says R3.2 MERGED")), repo_root=ROOT) == []


def test_material_implementation_without_status_doc_blocks():
    findings = validate_status_sync(_roadmap(_row()), repo_root=ROOT, changed_paths=["core/example.py"])
    assert any("STATUS_DOCUMENT_UPDATE_REQUIRED" in item for item in findings)


def test_unrelated_asset_does_not_require_status_doc():
    assert validate_status_sync(_roadmap(_row()), repo_root=ROOT, changed_paths=["assets/logo.svg"]) == []
