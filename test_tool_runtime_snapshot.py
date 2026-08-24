import copy
import json
from dataclasses import replace

import pytest

import business_tool_registry
from business_tool_registry import find_recommended_tools, get_playbook, list_tools, maybe_recommend
from tools import tool_runtime_snapshot
from tools.tool_runtime_snapshot import (
    LegacySnapshotWriteBlocked,
    SnapshotLoadError,
    SnapshotValidationError,
    generate_snapshot,
    load_tool_runtime_snapshot,
    validate_snapshot,
    write_snapshot,
)


def test_valid_snapshot_loads_and_has_stable_records():
    snapshot = load_tool_runtime_snapshot()
    assert snapshot["schema_version"] == "1"
    assert len(snapshot["tools"]) == 19
    bentopdf = next(item for item in snapshot["tools"] if item["tool_id"] == "bentopdf")
    assert bentopdf["playbook"]["privacy_guidance"] == "עבוד על עותק של הקובץ; שמור את המקור אצלך."
    assert tool_runtime_snapshot.normalize_capability_id("merge") == "pdf_merge"
    assert len({item["tool_id"] for item in snapshot["tools"]}) == len(snapshot["tools"])


@pytest.mark.parametrize("mutate, message", [
    (lambda s: s.update(schema_version="999"), "schema_version"),
    (lambda s: s["tools"].append(copy.deepcopy(s["tools"][0])), "duplicate tool"),
    (lambda s: s["capabilities"].append(copy.deepcopy(s["capabilities"][0])), "duplicate capability"),
    (lambda s: s["tool_capabilities"].append(copy.deepcopy(s["tool_capabilities"][0])), "duplicate relation"),
    (lambda s: s["tool_capabilities"][0].update(tool_id="missing"), "broken relation"),
    (lambda s: s["tools"][0].update(canonical_url="not-a-url"), "malformed URL"),
])
def test_validator_rejects_corruption(mutate, message):
    snapshot = load_tool_runtime_snapshot()
    mutate(snapshot)
    with pytest.raises(SnapshotValidationError, match=message):
        validate_snapshot(snapshot)


def test_ineligible_records_cannot_be_runtime_visible():
    snapshot = load_tool_runtime_snapshot()
    tool = next(item for item in snapshot["tools"] if item["tool_class"] == "infrastructure_candidate")
    tool["runtime_visible"] = True
    with pytest.raises(SnapshotValidationError):
        validate_snapshot(snapshot)


def test_generation_is_deterministic_except_timestamp():
    first = generate_snapshot(source_revision="test", generated_at="2026-01-01T00:00:00Z")
    second = generate_snapshot(source_revision="test", generated_at="2026-02-01T00:00:00Z")
    first["generated_at"] = second["generated_at"] = ""
    assert first == second


def test_runtime_matching_uses_capabilities_and_keeps_current_ux():
    assert find_recommended_tools("אני צריך לאחד כמה קבצי PDF")[0].tool_id == "bentopdf"
    assert find_recommended_tools("יש לי CSV שבור")[0].tool_id == "csv-repair"
    assert "[BentoPDF](https://bentopdf.com/)" in (maybe_recommend("אני צריך לאחד PDF") or "")
    assert get_playbook("איך משתמשים ב-BentoPDF?").tool_id == "bentopdf"
    assert len(list_tools()) == 13


def test_operator_and_deferred_tools_are_not_business_results():
    assert find_recommended_tools("monitor endpoint") == []
    assert find_recommended_tools("test api") == []
    assert find_recommended_tools("scan dependencies") == []
    assert maybe_recommend("אני צריך מערכת לניהול משמרות") is None


def test_missing_or_malformed_snapshot_fails_closed(tmp_path):
    with pytest.raises(SnapshotLoadError):
        load_tool_runtime_snapshot(tmp_path / "missing.json")
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"schema_version": "999"}), encoding="utf-8")
    with pytest.raises(SnapshotLoadError):
        load_tool_runtime_snapshot(path)


def test_runtime_records_come_from_snapshot_not_seed():
    seed = business_tool_registry.TOOL_REGISTRY
    try:
        bentopdf = next(tool for tool in seed if tool.tool_id == "bentopdf")
        business_tool_registry.TOOL_REGISTRY = tuple(
            replace(
                tool,
                name="Seed-only name",
                url="https://seed-only.invalid/",
                playbook=replace(tool.playbook, privacy_guidance="seed-only guidance"),
            ) if tool.tool_id == "bentopdf" else tool
            for tool in seed
        )
        reply = maybe_recommend("אני צריך לאחד PDF")
        assert "[BentoPDF](https://bentopdf.com/)" in reply
        assert "Seed-only" not in reply
        assert "seed-only guidance" not in reply
    finally:
        business_tool_registry.TOOL_REGISTRY = seed


def test_regenerating_snapshot_changes_runtime_output(tmp_path):
    seed = business_tool_registry.TOOL_REGISTRY
    original_path = tool_runtime_snapshot.DEFAULT_PATH
    runtime_path = tmp_path / "runtime_snapshot.json"
    try:
        bentopdf = next(tool for tool in seed if tool.tool_id == "bentopdf")
        business_tool_registry.TOOL_REGISTRY = tuple(
            replace(
                tool,
                name="BentoPDF Regenerated",
                url="https://bentopdf.example/",
                playbook=replace(tool.playbook, privacy_guidance="regenerated guidance"),
            ) if tool.tool_id == "bentopdf" else tool
            for tool in seed
        )
        tool_runtime_snapshot.write_snapshot(runtime_path, source_revision="test-regeneration")
        tool_runtime_snapshot.DEFAULT_PATH = runtime_path
        reply = maybe_recommend("אני צריך לאחד PDF")
        assert "[BentoPDF Regenerated](https://bentopdf.example/)" in reply
        assert "regenerated guidance" in reply
    finally:
        business_tool_registry.TOOL_REGISTRY = seed
        tool_runtime_snapshot.DEFAULT_PATH = original_path


def test_legacy_generator_cannot_silently_overwrite_canonical_artifact():
    """tools/generate_tool_runtime_snapshot_from_db.py is the sole canonical
    generator for DEFAULT_PATH (Track #7 generator-authority remediation).
    This module's write_snapshot() must fail closed, not silently write,
    when its target resolves to the canonical artifact -- whether reached
    via the default argument or an explicit equal path."""
    canonical = tool_runtime_snapshot.DEFAULT_PATH
    before = canonical.read_bytes()
    with pytest.raises(LegacySnapshotWriteBlocked):
        write_snapshot(source_revision="working-tree")
    with pytest.raises(LegacySnapshotWriteBlocked):
        write_snapshot(canonical, source_revision="working-tree")
    assert canonical.read_bytes() == before


def test_legacy_generator_still_writes_non_canonical_paths(tmp_path):
    target = tmp_path / "runtime_snapshot.json"
    write_snapshot(target, source_revision="test-legacy-non-canonical")
    assert target.exists()
