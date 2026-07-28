from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from tools.context_librarian import librarian
from tools.context_librarian.librarian import (
    ContextLibrarianError,
    assess_profile_suggestions,
    build_bundle,
    evaluate_workflow_gate,
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
    path = root / "layers/core_reasoning.json"
    data = _read_json(path)
    data["nodes"][0]["status"] = "mystery"
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="unknown status"):
        load_catalog(REPO_ROOT)


def test_unknown_edge_is_rejected(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "layers/tools.json"
    data = _read_json(path)
    data["edges"][0]["type"] = "related_to"
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="unknown edge type"):
        load_catalog(REPO_ROOT)


def test_unknown_node_field_is_rejected(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "layers/rp5.json"
    data = _read_json(path)
    data["nodes"][0]["ad_hoc_field"] = True
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="unknown fields"):
        load_catalog(REPO_ROOT)


def test_schema_can_add_a_seventh_layer_without_code_change(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    source = _read_json(root / "layers/rp5.json")
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
    _write_json(root / "layers/future_observability.json", data)
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
    path = root / "layers/core_reasoning.json"
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


def test_token_estimate_labels_are_honest_about_being_a_char_proxy(catalog):
    # N17 סעיף 1: האומדן לעולם אינו אמור להציג את עצמו כתוצאה של tokenizer
    # אמיתי. זו בכוונה בדיקת ניסוח/תיוג, לא בדיקת דיוק-טוקנים — דיוק דורש
    # את TOKEN_ESTIMATION_BENCHMARK.md.
    bundle = build_bundle(
        catalog,
        task_type="approval_ux",
        query="approval message",
    )
    assert "approximate_char_estimate_budget" in bundle
    assert "NOT a real tokenizer count" in bundle
    assert "TOKEN_ESTIMATION_BENCHMARK.md" in bundle
    assert "referenced_source_to_bundle_char_estimate_savings" in bundle


def test_approximate_char_estimate_matches_chars_divided_by_constant():
    from tools.context_librarian.librarian import (
        _CHARS_PER_APPROXIMATE_TOKEN,
        _approximate_char_estimate,
    )
    import math

    sample = "x" * 37
    assert _approximate_char_estimate(sample) == math.ceil(
        len(sample) / _CHARS_PER_APPROXIMATE_TOKEN
    )


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


# ── N17 סעיף 3: הקשחת בחירת query/profile ───────────────────────────────────
# ה-profile המפורש חייב להישאר המקור היחיד לבחירת primary/required/
# mandatory. טקסט חופשי רשאי רק *להוסיף* conditional evidence שהוגדר
# ב-profile — לעולם לא להשמיט או לדרוס את הבחירה הליבתית. הבדיקות האלו
# הופכות את ההבטחה הזו למפורשת ומוגנת-רגרסיה, במקום שתישאר משתמעת במבנה
# של _select_nodes().

@pytest.mark.parametrize(
    "query",
    ["", "zzz qqq unrelated gibberish 12345", "לא קשור בכלל מילים אקראיות לגמרי"],
)
def test_garbage_query_never_drops_primary_required_or_mandatory_selection(catalog, query):
    for profile_id, profile in catalog.profiles.items():
        bundle = build_bundle(catalog, task_type=profile_id, query=query)
        for layer in profile["primary_layers"]:
            assert f"`{layer}` (primary" in bundle, (
                f"{profile_id}: lost primary layer {layer} for query={query!r}"
            )
        for layer in profile["required_dependency_layers"]:
            assert f"`{layer}` (required_dependency" in bundle, (
                f"{profile_id}: lost required_dependency layer {layer} for query={query!r}"
            )
        for decision in profile["mandatory_canonical_decisions"]:
            assert f"`decision.{decision}`" in bundle, (
                f"{profile_id}: lost mandatory decision {decision} for query={query!r}"
            )


def test_query_cannot_pull_in_an_excluded_layer_via_matching_terms(catalog):
    # core_reasoning_change מחריג approvals/ux_f52/rp5. query עוין הבנוי
    # מ-selection_terms של אותן שכבות עדיין לא אמור לגרום לדליפה שלהן —
    # רק ה-profile המפורש שולט בהחרגות.
    adversarial_query = (
        "approval reject callback pending message rp5 evidence claim "
        "completion mismatch ux formatter wording telegram whatsapp"
    )
    bundle = build_bundle(
        catalog, task_type="core_reasoning_change", query=adversarial_query
    )
    assert "excluded_layer_leakage: 0 []" in bundle
    assert "`approvals` (" not in bundle
    assert "`rp5` (" not in bundle
    assert "`ux_f52` (" not in bundle


def test_conditional_evidence_trigger_is_stable_across_hebrew_and_english_phrasing(catalog):
    english = build_bundle(
        catalog,
        task_type="ux_f52_message",
        query="message wording mismatch with the evidence",
    )
    hebrew = build_bundle(
        catalog,
        task_type="ux_f52_message",
        query="ניסוח ההודעה לא תואם לראיה",
    )
    assert "`rp5` (conditional_evidence" in english
    assert "`rp5` (conditional_evidence" in hebrew


def test_query_only_ranks_never_selects_for_suggest_profile(catalog):
    # suggest-profile הוא דירוג הניתן-להסבר בלבד; build() לעולם לא
    # מתייעץ בו. query זבל לעולם לא אמור להיפתר בשקט ל-automatic_selection.
    ranked = suggest_profiles(catalog, "zzz qqq unrelated gibberish 12345")
    assessment = assess_profile_suggestions(ranked)
    assert assessment["automatic_selection"] is False
    assert assessment["status"] == "no_match"


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


def test_zero_score_is_not_a_valid_recommendation(catalog):
    assessment = assess_profile_suggestions(suggest_profiles(catalog, "fix bug"))
    assert assessment == {
        "status": "no_match",
        "top_score": 0,
        "candidates": [],
        "suggested_profile": None,
        "automatic_selection": False,
    }


def test_tie_is_not_automatically_selected():
    ranked = [
        {"profile_id": "approval_ux", "score": 2, "matched_terms": ["approval"]},
        {"profile_id": "tool_execution", "score": 2, "matched_terms": ["tool"]},
    ]
    assessment = assess_profile_suggestions(ranked)
    assert assessment["status"] == "tie"
    assert assessment["suggested_profile"] is None
    assert assessment["automatic_selection"] is False


def test_explicit_manual_profile_overrides_suggestion(catalog):
    ranked = suggest_profiles(catalog, "approval callback message")
    assert ranked[0]["profile_id"] == "approval_ux"
    bundle = build_bundle(
        catalog,
        task_type="core_reasoning_change",
        query="approval callback message",
    )
    assert bundle.startswith("# BOSS Context Bundle — core_reasoning_change")


def test_stale_node_reports_stop_without_blocking_bundle(catalog, monkeypatch):
    monkeypatch.setattr(
        librarian,
        "_git_changed_paths",
        lambda _root, _commit: {"tools/dispatcher.py"},
    )
    bundle = build_bundle(
        catalog,
        task_type="tool_execution",
        query="dispatcher evidence",
    )
    assert "## Agent Workflow Gate" in bundle
    assert "- status: STOP" in bundle
    assert "- reasons: ['stale_nodes']" in bundle
    assert "- stale_nodes: 1 ['layer.tools']" in bundle


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"mandatory_authority_coverage": 0.75}, "mandatory_authority_incomplete"),
        (
            {"production_claim": True, "qualifying_production_evidence": 0},
            "production_evidence_missing",
        ),
        (
            {"unresolved_conflicts": ["decision.a -> decision.b"]},
            "unresolved_source_conflict",
        ),
        ({"excluded_layer_leakage": ["core_reasoning"]}, "excluded_layer_leakage"),
    ],
)
def test_workflow_gate_stop_conditions_use_fixtures(kwargs, reason):
    gate = evaluate_workflow_gate(**kwargs)
    assert gate["status"] == "STOP"
    assert reason in gate["reasons"]


def test_qualifying_production_evidence_allows_explicit_claim_gate():
    gate = evaluate_workflow_gate(
        production_claim=True,
        qualifying_production_evidence=1,
    )
    assert gate["status"] == "PROCEED"
    assert gate["reasons"] == []


def test_production_evidence_requires_exact_manual_attestation():
    reference = {
        "path": "evidence/live-check.md",
        "status": "production_verified",
        "scope": "production state for the selected layer and claim",
    }
    assert librarian._qualifies_as_production_evidence(reference, None) is False
    assert (
        librarian._qualifies_as_production_evidence(reference, "evidence/other.md")
        is False
    )
    assert (
        librarian._qualifies_as_production_evidence(
            reference, "evidence/live-check.md"
        )
        is True
    )


def test_verified_production_evidence_requires_claim_mode(catalog):
    with pytest.raises(ContextLibrarianError, match="requires --production-claim"):
        build_bundle(
            catalog,
            task_type="rp5_evidence_mismatch",
            query="evidence",
            verified_production_evidence="evidence/live-check.md",
        )


def test_suggestion_assessment_is_deterministic(catalog):
    query = "dispatcher approval evidence message"
    first = suggest_profiles(catalog, query)
    second = suggest_profiles(catalog, query)
    assert first == second
    assert assess_profile_suggestions(first) == assess_profile_suggestions(second)


def test_phase0_cli_commands_remain_compatible(capsys):
    from tools.context_librarian.__main__ import main

    assert main(["suggest-profile", "--query", "approval callback"]) == 0
    suggestion_output = capsys.readouterr().out
    assert "approval_ux\tscore=" in suggestion_output
    assert "Suggestion only: pass an explicit --task-type to build." in suggestion_output

    assert (
        main(
            [
                "build",
                "--task-type",
                "core_reasoning_change",
                "--query",
                "lead state",
            ]
        )
        == 0
    )
    build_output = capsys.readouterr().out
    assert build_output.startswith("# BOSS Context Bundle — core_reasoning_change")


def test_agent_bootstrap_is_canonical_and_claude_only_references_it():
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "## CONTEXT LIBRARIAN BOOTSTRAP" in agents
    assert "suggest-profile --query \"<task>\" --all" in agents
    assert "Selected profile: <profile_id>" in agents
    assert "mandatory minimum context" in agents
    assert "context expansion" in agents
    assert "A stale STOP permits only direct source re-verification" in agents

    assert "canonical Context Librarian bootstrap in `AGENTS.md`" in claude
    assert "suggest-profile" not in claude
    assert "**Before doing anything else**, read `AI_CONTEXT.md`" not in claude
