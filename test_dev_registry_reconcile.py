from pathlib import Path
import json

import pytest

from tools.dev_registry_reconcile import (
    EvidenceRecord,
    JsonEvidenceAdapter,
    ReconciliationError,
    atomic_write,
    reconcile_file,
    reconcile_text,
    validate_evidence_record,
)
from tools.dev_registry_validator import REQUIRED_COLUMNS, RegistryValidationError


ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md"


def _fixture(**overrides):
    values = {
        "Initiative Key": "EXAMPLE_INITIATIVE",
        "Initiative / Document": "Example",
        "Scope": "Testing",
        "Horizon": "H0",
        "Work State": "ACTIVE",
        "Current Stage": "Owner stage",
        "Evidence State": "CODE_DONE",
        "Next Decided Step": "Review",
        "Needs Verification": "true",
        "Blocked": "false",
        "Owner Decision Required": "false",
        "Last Reconciled": "2026-08-16T00:00:00Z",
        "Evidence Source": "migration-explicit-status",
    }
    values.update(overrides)
    return "\n".join([
        "## 3.5 רישום עבודה חי (Active Work Registry)",
        "| " + " | ".join(REQUIRED_COLUMNS) + " |",
        "|" + "|".join("---" for _ in REQUIRED_COLUMNS) + "|",
        "| " + " | ".join(values[column] for column in REQUIRED_COLUMNS) + " |",
        "### 3.5 Runtime Capability Status",
    ])


def _record(state, evidence_type="git_main", source_ref="git:main:abc123", **kwargs):
    return EvidenceRecord(
        "EXAMPLE_INITIATIVE", evidence_type, state, source_ref,
        "2026-08-16T12:00:00Z", version_ref="abc123", **kwargs,
    )


def test_code_done_promotes_to_merged_from_explicit_main_evidence():
    result, report = reconcile_text(_fixture(), [_record("MERGED")], reconciled_at="2026-08-16T13:00:00Z")
    assert "| MERGED |" in result
    assert report.changed_keys == ("EXAMPLE_INITIATIVE",)


def test_commit_subject_cannot_prove_deployment_or_runtime():
    adapter = JsonEvidenceAdapter()
    with pytest.raises(ReconciliationError):
        _write_manifest_and_read(adapter, {"initiative_key": "EXAMPLE_INITIATIVE", "evidence_type": "git_main", "evidence_state": "DEPLOYED", "source_ref": "git:main:abc", "observed_at": "2026-08-16T12:00:00Z"})
    with pytest.raises(ReconciliationError):
        _write_manifest_and_read(adapter, {"initiative_key": "EXAMPLE_INITIATIVE", "evidence_type": "git_main", "evidence_state": "RUNTIME_VERIFIED", "source_ref": "git:main:abc", "observed_at": "2026-08-16T12:00:00Z"})


def _write_manifest_and_read(adapter, record):
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "evidence.json"
        path.write_text(json.dumps({"records": [record]}), encoding="utf-8")
        return adapter.read(path)


def test_deployed_does_not_become_runtime_verified_without_scoped_runtime_evidence():
    result, _ = reconcile_text(
        _fixture(**{"Evidence State": "CODE_DONE"}),
        [_record("DEPLOYED", evidence_type="deployment", source_ref="deployment:release-1")],
        reconciled_at="2026-08-16T13:00:00Z",
    )
    assert "| DEPLOYED |" in result
    assert "| RUNTIME_VERIFIED |" not in result


def test_explicit_runtime_evidence_promotes_and_clears_verification():
    result, _ = reconcile_text(
        _fixture(**{"Evidence State": "DEPLOYED", "Needs Verification": "true"}),
        [_record("RUNTIME_VERIFIED", evidence_type="runtime", source_ref="runtime-evidence:release-1")],
        reconciled_at="2026-08-16T13:00:00Z",
    )
    assert "| RUNTIME_VERIFIED | Review | false |" in result


def test_stronger_registry_state_is_not_downgraded_by_weaker_evidence():
    result, report = reconcile_text(
        _fixture(**{"Evidence State": "MERGED"}),
        [_record("CODE_DONE")],
        reconciled_at="2026-08-16T13:00:00Z",
    )
    assert "| MERGED |" in result
    assert report.changed_keys == ()


def test_unknown_or_unmapped_evidence_does_not_alter_registry():
    record = EvidenceRecord("NOT_REGISTERED", "git_main", "MERGED", "git:main:abc", "2026-08-16T12:00:00Z")
    result, report = reconcile_text(_fixture(), [record], reconciled_at="2026-08-16T13:00:00Z")
    assert result == _fixture()
    assert report.unmapped_evidence == ("git:main:abc:NOT_REGISTERED",)


def test_same_adapter_conflict_leaves_row_unchanged():
    records = [_record("CODE_DONE"), _record("MERGED", source_ref="git:main:def456")]
    result, report = reconcile_text(_fixture(), records, reconciled_at="2026-08-16T13:00:00Z")
    assert result == _fixture()
    assert report.conflicts


def test_dry_run_performs_no_write(tmp_path):
    path = tmp_path / "BOSS.md"
    path.write_text(_fixture(), encoding="utf-8")
    before = path.read_bytes()
    report = reconcile_file(path, records=[_record("MERGED")], apply=False, reconciled_at="2026-08-16T13:00:00Z")
    assert report.changed_keys == ("EXAMPLE_INITIATIVE",)
    assert path.read_bytes() == before


def test_apply_updates_only_intended_fields(tmp_path):
    path = tmp_path / "BOSS.md"
    path.write_text(_fixture(), encoding="utf-8")
    reconcile_file(path, records=[_record("MERGED")], apply=True, reconciled_at="2026-08-16T13:00:00Z")
    text = path.read_text(encoding="utf-8")
    assert "| Example | Testing | H0 | ACTIVE | Owner stage | MERGED | Review | true | false | false | 2026-08-16T13:00:00Z | git:main:abc123 |" in text


def test_invalid_result_aborts_before_write(tmp_path):
    path = tmp_path / "BOSS.md"
    original = _fixture()
    path.write_text(original, encoding="utf-8")
    with pytest.raises(ReconciliationError):
        reconcile_file(path, records=[], apply=True, reconciled_at="not-a-timestamp")
    assert path.read_text(encoding="utf-8") == original


def test_atomic_write_failure_leaves_original(monkeypatch, tmp_path):
    path = tmp_path / "BOSS.md"
    original = "original"
    path.write_text(original, encoding="utf-8")
    def fail_replace(_source, _target):
        raise OSError("simulated replace failure")
    monkeypatch.setattr("tools.dev_registry_reconcile.os.replace", fail_replace)
    with pytest.raises(OSError):
        atomic_write(path, "new")
    assert path.read_text(encoding="utf-8") == original


def test_post_write_validation_failure_restores_original(monkeypatch, tmp_path):
    path = tmp_path / "BOSS.md"
    original = _fixture()
    path.write_text(original, encoding="utf-8")
    real_validate = __import__("tools.dev_registry_reconcile", fromlist=["validate_registry_text"]).validate_registry_text
    calls = {"count": 0}

    def fail_after_write(text):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RegistryValidationError("simulated post-write validation failure")
        return real_validate(text)

    monkeypatch.setattr("tools.dev_registry_reconcile.validate_registry_text", fail_after_write)
    with pytest.raises(RegistryValidationError):
        reconcile_file(path, records=[_record("MERGED")], apply=True, reconciled_at="2026-08-16T13:00:00Z")
    assert path.read_text(encoding="utf-8") == original


def test_last_reconciled_changes_only_on_successful_reconciliation():
    result, _ = reconcile_text(_fixture(), [_record("MERGED")], reconciled_at="2026-08-16T13:00:00Z")
    assert "2026-08-16T13:00:00Z" in result


def test_manifest_adapter_requires_explicit_keyed_records(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({"records": [{"evidence_state": "MERGED"}]}), encoding="utf-8")
    with pytest.raises(ReconciliationError, match="missing initiative_key"):
        JsonEvidenceAdapter().read(path)


@pytest.mark.parametrize(
    "record",
    [
        _record("RUNTIME_VERIFIED"),
        _record("DEPLOYED"),
        EvidenceRecord("EXAMPLE_INITIATIVE", "runtime", "RUNTIME_VERIFIED", "runtime-evidence:x", "2026-08-16T12:00:00Z"),
        EvidenceRecord("EXAMPLE_INITIATIVE", "git_main", "MERGED", "wrong:x", "2026-08-16T12:00:00Z", version_ref="abc", confidence="reviewed"),
    ],
)
def test_direct_evidence_records_cannot_bypass_validation(record):
    with pytest.raises(ReconciliationError):
        validate_evidence_record(record)


def test_valid_direct_runtime_evidence_is_accepted():
    record = EvidenceRecord(
        "EXAMPLE_INITIATIVE", "runtime", "RUNTIME_VERIFIED", "runtime-evidence:release-1",
        "2026-08-16T12:00:00Z", version_ref="release-1",
    )
    assert validate_evidence_record(record) == record


def test_rejected_direct_record_does_not_write_or_update_provenance(tmp_path):
    path = tmp_path / "BOSS.md"
    original = _fixture()
    path.write_text(original, encoding="utf-8")
    rejected = EvidenceRecord("EXAMPLE_INITIATIVE", "git_main", "RUNTIME_VERIFIED", "git:main:abc", "2026-08-16T12:00:00Z")
    with pytest.raises(ReconciliationError):
        reconcile_file(path, records=[rejected], apply=True, reconciled_at="2026-08-16T13:00:00Z")
    assert path.read_text(encoding="utf-8") == original
    assert "2026-08-16T00:00:00Z" in original
    assert "migration-explicit-status" in original


def test_conflicting_runtime_policy_values_leave_row_unchanged():
    records = [
        _record("MERGED", requires_runtime_verification=True),
        _record("MERGED", source_ref="git:main:def456", requires_runtime_verification=False),
    ]
    result, report = reconcile_text(_fixture(), records, reconciled_at="2026-08-16T13:00:00Z")
    assert result == _fixture()
    assert report.conflicts == ("EXAMPLE_INITIATIVE: conflicting requires_runtime_verification policy values",)
