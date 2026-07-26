from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from tools.context_librarian import librarian
from tools.context_librarian.librarian import (
    ContextLibrarianError,
    build_bundle,
    load_catalog,
    suggest_profiles,
)


REPO_ROOT = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(REPO_ROOT)


def _isolated_catalog(tmp_path: Path, monkeypatch) -> Path:
    source = REPO_ROOT / "docs/context_librarian"
    target = tmp_path / "catalog"
    shutil.copytree(source, target)
    monkeypatch.setattr(librarian, "CATALOG_RELATIVE_ROOT", target)
    return target


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_catalog_and_all_seven_profiles_validate(catalog):
    assert len(catalog.layer_nodes) == 6
    assert set(catalog.profiles) == {
        "approval_ux",
        "tool_execution",
        "turn_coordinator_routing",
        "core_reasoning_change",
        "rp5_evidence_mismatch",
        "ux_f52_message",
        "cross_layer_architecture",
    }


def test_unknown_status_is_rejected(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "layers/core_reasoning.yaml"
    data = _read_json(path)
    data["nodes"][0]["status"] = "mystery"
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="unknown status"):
        load_catalog(REPO_ROOT)


def test_unknown_edge_is_rejected(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "layers/tools.yaml"
    data = _read_json(path)
    data["edges"][0]["type"] = "related_to"
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="unknown edge type"):
        load_catalog(REPO_ROOT)


def test_unknown_node_field_is_rejected(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "layers/rp5.yaml"
    data = _read_json(path)
    data["nodes"][0]["ad_hoc_field"] = True
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="unknown fields"):
        load_catalog(REPO_ROOT)


def test_schema_can_add_a_seventh_layer_without_code_change(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    source = _read_json(root / "layers/rp5.yaml")
    node = copy.deepcopy(source["nodes"][0])
    node.update(
        {
            "id": "layer.future_observability",
            "name": "Future Observability Layer",
            "owner": "future_observability",
            "extensions": {"example.namespace": {"version": 1}},
        }
    )
    data = {
        "schema_version": "1.0",
        "layer_id": "future_observability",
        "nodes": [node],
        "edges": [],
    }
    _write_json(root / "layers/future_observability.yaml", data)
    loaded = load_catalog(REPO_ROOT)
    assert loaded.layer_nodes["future_observability"] == "layer.future_observability"


def test_status_filter_excludes_historical_and_superseded(catalog):
    bundle = build_bundle(
        catalog,
        task_type="tool_execution",
        query="dispatcher evidence",
    )
    assert "F52_CURRENT_TOOL_MAP.md" not in bundle
    assert "F52_BYPASS_MAP.md" not in bundle
    assert "[historical]" not in bundle


def test_superseded_document_is_excluded(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "layers/core_reasoning.yaml"
    data = _read_json(path)
    superseded_path = data["nodes"][0]["canonical_docs"][1]["path"]
    data["nodes"][0]["canonical_docs"][1]["status"] = "superseded"
    _write_json(path, data)
    isolated = load_catalog(REPO_ROOT)
    bundle = build_bundle(
        isolated,
        task_type="core_reasoning_change",
        query="lead reasoning",
    )
    assert superseded_path not in bundle


def test_stale_detection_uses_code_diffs_not_path_existence(catalog, monkeypatch):
    node = catalog.nodes["layer.tools"]
    monkeypatch.setattr(
        librarian,
        "_git_changed_paths",
        lambda _root, _commit: {"tools/dispatcher.py", "README.md"},
    )
    state = librarian._freshness(catalog, [node])[node["id"]]
    assert state["stale"] is True
    assert state["code_changes"] == ["tools/dispatcher.py"]


def test_test_only_change_is_reported_without_marking_code_stale(catalog, monkeypatch):
    node = catalog.nodes["layer.tools"]
    monkeypatch.setattr(
        librarian,
        "_git_changed_paths",
        lambda _root, _commit: {"test_tool_registry_invariants.py"},
    )
    state = librarian._freshness(catalog, [node])[node["id"]]
    assert state["stale"] is False
    assert state["test_changes"] == ["test_tool_registry_invariants.py"]


def test_output_is_deterministic(catalog):
    kwargs = {
        "task_type": "approval_ux",
        "query": "repeated approval returns wrong message",
        "max_tokens": 4000,
    }
    assert build_bundle(catalog, **kwargs) == build_bundle(catalog, **kwargs)


def test_token_budget_fails_closed(catalog):
    with pytest.raises(ContextLibrarianError, match="exceeding"):
        build_bundle(
            catalog,
            task_type="approval_ux",
            query="approval message",
            max_tokens=100,
        )


def test_document_budget_is_enforced(catalog):
    bundle = build_bundle(
        catalog,
        task_type="core_reasoning_change",
        query="lead reasoning",
        max_documents=3,
    )
    assert "document_budget: 3/3" in bundle


def test_mandatory_decisions_are_included(catalog):
    bundle = build_bundle(
        catalog,
        task_type="rp5_evidence_mismatch",
        query="evidence mismatch",
    )
    for decision in catalog.profiles["rp5_evidence_mismatch"][
        "mandatory_canonical_decisions"
    ]:
        assert f"`decision.{decision}`" in bundle


def test_approval_profile_includes_actioncontracts_and_turn_coordinator(catalog):
    bundle = build_bundle(
        catalog,
        task_type="approval_ux",
        query="repeated approval returns wrong message",
    )
    assert "`approvals` (primary" in bundle
    assert "`turn_coordinator` (required_dependency" in bundle
    assert "ActionContracts remains the sole source of truth" in bundle


def test_ux_profile_adds_rp5_only_for_evidence_claims(catalog):
    ordinary = build_bundle(
        catalog,
        task_type="ux_f52_message",
        query="change Telegram button wording",
    )
    evidence = build_bundle(
        catalog,
        task_type="ux_f52_message",
        query="change verified completion claim wording",
    )
    assert "`rp5` (" not in ordinary
    assert "`rp5` (conditional_evidence" in evidence


def test_core_reasoning_does_not_load_approval_history(catalog):
    bundle = build_bundle(
        catalog,
        task_type="core_reasoning_change",
        query="BUG-104 business outcome mapping",
    )
    assert "`core_reasoning` (primary" in bundle
    assert "`approvals` (" not in bundle
    assert "STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md" not in bundle


def test_no_excluded_layer_leakage(catalog):
    for profile_id in catalog.profiles:
        bundle = build_bundle(catalog, task_type=profile_id, query="ordinary task")
        assert "excluded_layer_leakage: 0 []" in bundle


def test_code_tests_and_production_evidence_are_separate(catalog):
    bundle = build_bundle(
        catalog,
        task_type="tool_execution",
        query="tool execution evidence",
    )
    code_index = bundle.index("## Code")
    tests_index = bundle.index("## Tests")
    evidence_index = bundle.index("## Production Evidence")
    assert code_index < tests_index < evidence_index


def test_agent_contract_and_safety_sections_are_always_present(catalog):
    bundle = build_bundle(
        catalog,
        task_type="core_reasoning_change",
        query="lead state",
    )
    assert "## Agent Consumption Contract" in bundle
    assert "## Do Not Assume" in bundle
    assert "## Out of Scope" in bundle
    assert "main overrides planning documents" in bundle


def test_quality_metrics_go_beyond_token_savings(catalog):
    bundle = build_bundle(
        catalog,
        task_type="approval_ux",
        query="approval message",
    )
    assert "required_layer_coverage:" in bundle
    assert "mandatory_authority_coverage:" in bundle
    assert "freshness_ratio:" in bundle
    assert "provenance_completeness:" in bundle
    assert "excluded_layer_leakage:" in bundle
    assert "query_match_precision_proxy:" in bundle


def test_profile_suggestion_is_explainable_and_does_not_build(catalog):
    ranked = suggest_profiles(catalog, "approval callback message")
    assert ranked[0]["profile_id"] == "approval_ux"
    assert ranked[0]["score"] > 0
    assert "approval" in ranked[0]["matched_terms"]


def test_unknown_profile_is_rejected(catalog):
    with pytest.raises(ContextLibrarianError, match="unknown task type"):
        build_bundle(catalog, task_type="automatic_magic", query="anything")
