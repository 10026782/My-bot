from __future__ import annotations

import copy
import json
import math
import re
import shutil
from pathlib import Path

import pytest

from tools.context_librarian import librarian
from tools.context_librarian import budget_preflight
from tools.context_librarian import budget_history
from tools.context_librarian.librarian import (
    BundleEstimate,
    ContextLibrarianError,
    assess_profile_suggestions,
    build_bundle,
    classify_new_sources,
    consumption_checklist,
    discover_new_sources,
    estimate_all_profiles,
    estimate_bundle,
    evaluate_workflow_gate,
    load_catalog,
    refresh_after_merge,
    refresh_proposal,
    suggest_profiles,
    verify_consumption,
)
from tools.context_librarian.budget_preflight import (
    ESTIMATOR_ID,
    build_budget_preflight,
    canonical_profile_queries,
    classify_health,
    format_budget_preflight_json,
)
from tools.context_librarian.budget_history import record_budget_snapshot
from tools.context_librarian.token_budget_policy import calibration_summary


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


_FIXED_PROVENANCE = {
    "commit": "deadbee",
    "branch": "claude/test-branch",
    "on_main": "yes",
    "on_main_history": "yes",
    "at_origin_main_tip": "yes",
}


_UNSET = object()


def _path_for_item_id(item_id: str) -> str | None:
    prefix, _, rest = item_id.partition(":")
    if prefix == "decision":
        return None
    if prefix == "expansion":
        return rest.partition("#")[0]
    return rest


def _receipt(
    item_id: str,
    *,
    commit: str,
    branch: str,
    profile: str,
    query: str,
    path=_UNSET,
    reason: str | None = None,
    evidence_reference: str | None = None,
) -> dict:
    return {
        "item_id": item_id,
        "path": _path_for_item_id(item_id) if path is _UNSET else path,
        "commit": commit,
        "branch": branch,
        "profile": profile,
        "query": query,
        "reviewed_by": "claude-sonnet-5 / session-test",
        "reviewed_at": "2026-07-28T20:00:00Z",
        "reason": reason or f"reviewed {item_id} directly",
        "evidence_reference": evidence_reference or f"inspected {item_id}",
    }


def _waiver(
    item_id: str,
    *,
    commit: str,
    branch: str,
    profile: str,
    query: str,
    path=_UNSET,
    reviewed_by: str = "claude-sonnet-5 / session-test",
    approved_by: str = "independent-reviewer-agent / session-test",
    reason: str | None = None,
    evidence_reference: str | None = None,
) -> dict:
    entry = _receipt(
        item_id,
        commit=commit,
        branch=branch,
        profile=profile,
        query=query,
        path=path,
        reason=reason,
        evidence_reference=evidence_reference,
    )
    entry["reviewed_by"] = reviewed_by
    entry["approved_by"] = approved_by
    entry["approved_at"] = "2026-07-28T20:05:00Z"
    return entry


def _ledger(
    *,
    task_type: str,
    profile: str,
    query: str,
    commit: str,
    branch: str,
    required_sources: list,
    production_claim: bool = False,
    review_receipts: list | None = None,
    waived_sources: list | None = None,
) -> dict:
    return {
        "schema_version": "1.0",
        "task_type": task_type,
        "profile": profile,
        "query": query,
        "production_claim": production_claim,
        "bundle_generated_commit": commit,
        "bundle_generated_branch": branch,
        "required_sources": list(required_sources),
        "review_receipts": list(review_receipts or []),
        "waived_sources": list(waived_sources or []),
    }


def _fully_reviewed_ledger(
    catalog, task_type: str, query: str, *,
    commit: str = "deadbee", branch: str = "claude/test-branch", production_claim: bool = False,
) -> dict:
    profile = catalog.profiles[task_type]
    items = consumption_checklist(catalog, profile, production_claim=production_claim)
    receipts = [
        _receipt(item_id, commit=commit, branch=branch, profile=task_type, query=query)
        for item_id in items
    ]
    return _ledger(
        task_type=task_type,
        profile=task_type,
        query=query,
        commit=commit,
        branch=branch,
        production_claim=production_claim,
        required_sources=items,
        review_receipts=receipts,
    )


def test_catalog_and_all_eight_profiles_validate(catalog):
    assert len(catalog.layer_nodes) == 8
    assert set(catalog.profiles) == {
        "approval_ux",
        "tool_execution",
        "turn_coordinator_routing",
        "core_reasoning_change",
        "rp5_evidence_mismatch",
        "ux_f52_message",
        "cross_layer_architecture",
        "marketing_change",
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
    }
    assert build_bundle(catalog, **kwargs) == build_bundle(catalog, **kwargs)


def test_token_budget_fails_closed(catalog):
    with pytest.raises(ContextLibrarianError, match="estimated_tokens=.*budget=.*overflow="):
        build_bundle(
            catalog,
            task_type="approval_ux",
            query="approval message",
            max_tokens=100,
        )


def test_estimate_bundle_matches_build_bundle_when_it_fits(catalog):
    kwargs = {"task_type": "approval_ux", "query": "approval message"}
    bundle = build_bundle(catalog, **kwargs)
    result = estimate_bundle(catalog, **kwargs)
    assert result.fits is True
    assert result.actual_tokens == math.ceil(len(bundle) / 4)
    assert result.task_type == "approval_ux"
    assert result.query == "approval message"


def test_estimate_bundle_reports_overflow_without_raising(catalog):
    result = estimate_bundle(
        catalog, task_type="approval_ux", query="approval message", max_tokens=100
    )
    assert result.fits is False
    assert result.token_budget == 100
    assert result.actual_tokens > 100


def test_estimate_bundle_actual_tokens_matches_build_bundle_raised_value(catalog):
    with pytest.raises(ContextLibrarianError) as excinfo:
        build_bundle(
            catalog, task_type="approval_ux", query="approval message", max_tokens=100
        )
    raised_tokens = int(
        re.search(r"estimated_tokens=(\d+)", str(excinfo.value)).group(1)
    )
    result = estimate_bundle(
        catalog, task_type="approval_ux", query="approval message", max_tokens=100
    )
    assert result.actual_tokens == raised_tokens


def test_estimate_bundle_still_raises_on_structural_errors(catalog):
    with pytest.raises(ContextLibrarianError, match="unknown task type"):
        estimate_bundle(catalog, task_type="not_a_real_profile")


def test_estimate_bundle_ignores_off_main_state_unlike_assert_on_main_history(
    catalog, monkeypatch
):
    off_main = {
        "commit": "abc1234",
        "branch": "feature-x",
        "on_main": "no",
        "on_main_history": "no",
        "at_origin_main_tip": "no",
    }
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: off_main)

    with pytest.raises(ContextLibrarianError, match="assert-main"):
        build_bundle(
            catalog,
            task_type="approval_ux",
            query="approval message",
            assert_on_main_history=True,
        )

    # ל-estimate_bundle אין פרמטר assert_on_main_history/assert_main בכלל —
    # החלטת provenance אורתוגונלית ל"האם זה נכנס בתקציב."
    result = estimate_bundle(catalog, task_type="approval_ux", query="approval message")
    assert isinstance(result, BundleEstimate)


def test_estimate_all_profiles_covers_every_profile_sorted(catalog):
    results = estimate_all_profiles(catalog, query="approval message")
    assert [r.task_type for r in results] == sorted(catalog.profiles)
    assert len(results) == len(catalog.profiles)
    for r in results:
        assert isinstance(r, BundleEstimate)
        assert r.fits == (r.actual_tokens <= r.token_budget and r.selected_documents <= r.document_budget)


def test_budget_preflight_measures_every_profile_and_includes_marketing(catalog):
    report = build_budget_preflight(REPO_ROOT, catalog)
    configured = set(catalog.profiles)
    measured = {row["profile"] for row in report["profiles"]}
    assert measured == configured
    assert report["aggregate"]["total_profiles"] == len(configured)
    assert "marketing_change" in measured
    assert all(row["estimator"] == ESTIMATOR_ID for row in report["profiles"])


def test_budget_preflight_usage_reuses_chars_div_4_estimator(catalog):
    report = build_budget_preflight(REPO_ROOT, catalog)
    queries = {entry.profile: entry.query for entry in canonical_profile_queries()}
    for row in report["profiles"]:
        bundle = build_bundle(catalog, task_type=row["profile"], query=queries[row["profile"]])
        assert row["usage"] == math.ceil(len(bundle) / 4)
        assert row["headroom_tokens"] == row["budget"] - row["usage"]
        assert row["overflow_tokens"] == max(row["usage"] - row["budget"], 0)


@pytest.mark.parametrize(
    ("headroom_percent", "expected"),
    [
        (10.01, "PASS"),
        (10.0, "WARN"),
        (5.0, "WARN"),
        (4.99, "CRITICAL"),
        (0.0, "CRITICAL"),
        (-0.01, "FAIL"),
    ],
)
def test_budget_preflight_health_boundaries(headroom_percent, expected):
    assert classify_health(headroom_percent) == expected


def test_budget_preflight_report_json_schema_is_stable(catalog):
    report = build_budget_preflight(REPO_ROOT, catalog)
    encoded = format_budget_preflight_json(report)
    decoded = json.loads(encoded)
    assert decoded == report
    assert set(decoded) == {"estimator", "profiles", "aggregate"}
    assert set(decoded["aggregate"]) == {
        "total_profiles", "pass_count", "warn_count", "critical_count",
        "fail_count", "lowest_headroom_profile", "lowest_headroom_tokens",
        "calibration",
    }


def test_budget_preflight_is_deterministic(catalog):
    assert build_budget_preflight(REPO_ROOT, catalog) == build_budget_preflight(
        REPO_ROOT, catalog
    )


def test_small_chars_proxy_overflow_is_warning_not_blocking(catalog):
    profile = "cross_layer_architecture"
    query = "a change spans reasoning, routing, and approvals"
    baseline = estimate_bundle(catalog, task_type=profile, query=query)
    noisy_catalog = copy.deepcopy(catalog)
    noisy_catalog.profiles[profile]["maximum_approximate_token_budget"] = baseline.actual_tokens - 1

    bundle = build_bundle(noisy_catalog, task_type=profile, query=query)
    result = estimate_bundle(noisy_catalog, task_type=profile, query=query)
    assert bundle
    assert result.enforcement == "WARN"
    assert result.growth_signal == "WARN"
    assert result.overflow_tokens > 0


def test_hard_safety_ceiling_still_blocks_large_default_overflow(catalog):
    profile = "cross_layer_architecture"
    query = "a change spans reasoning, routing, and approvals"
    baseline = estimate_bundle(catalog, task_type=profile, query=query)
    unsafe_catalog = copy.deepcopy(catalog)
    unsafe_catalog.profiles[profile]["maximum_approximate_token_budget"] = baseline.actual_tokens - 300
    with pytest.raises(ContextLibrarianError, match="context budget overflow"):
        build_bundle(unsafe_catalog, task_type=profile, query=query)


def test_calibration_without_results_is_explicitly_stale():
    assert calibration_summary(REPO_ROOT) == {
        "status": "STALE",
        "latest_timestamp": None,
        "profiles": 0,
    }


def test_calibration_inventory_covers_every_profile(catalog):
    from tools.context_librarian.benchmark_token_estimate import _PROFILE_QUERIES

    assert set(_PROFILE_QUERIES) == set(catalog.profiles)


def test_budget_preflight_fails_closed_on_invalid_profile_budget(catalog):
    invalid_catalog = copy.deepcopy(catalog)
    invalid_catalog.profiles["approval_ux"]["maximum_approximate_token_budget"] = 0
    with pytest.raises(ContextLibrarianError, match="invalid token budget"):
        build_budget_preflight(REPO_ROOT, invalid_catalog)


def test_budget_preflight_fails_closed_when_query_mapping_is_incomplete(catalog, monkeypatch):
    monkeypatch.setattr(
        budget_preflight,
        "CANONICAL_PROFILE_QUERY_ENTRIES",
        budget_preflight.CANONICAL_PROFILE_QUERY_ENTRIES[:-1],
    )
    with pytest.raises(ContextLibrarianError, match="missing canonical"):
        build_budget_preflight(REPO_ROOT, catalog)


def test_budget_preflight_fails_closed_on_duplicate_query_mapping(catalog, monkeypatch):
    entries = budget_preflight.CANONICAL_PROFILE_QUERY_ENTRIES
    monkeypatch.setattr(
        budget_preflight,
        "CANONICAL_PROFILE_QUERY_ENTRIES",
        entries + (entries[0],),
    )
    with pytest.raises(ContextLibrarianError, match="duplicate canonical"):
        build_budget_preflight(REPO_ROOT, catalog)


def test_budget_history_records_initial_snapshot_idempotently(catalog, tmp_path, monkeypatch):
    report = build_budget_preflight(REPO_ROOT, catalog)
    history_path = tmp_path / "budget_history.json"
    first = record_budget_snapshot(REPO_ROOT, report, history_path)
    second = record_budget_snapshot(REPO_ROOT, report, history_path)
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert first["snapshot_added"] is True
    assert first["growth_breaks"] == []
    assert first["growth_break_counts"]["cross_layer_architecture"] == 0
    assert second["snapshot_added"] is False
    assert len(history["snapshots"]) == 1
    assert all(row["cause"] == "initial" for row in history["snapshots"][0]["profiles"])


def test_budget_history_records_growth_break_and_changed_paths(catalog, tmp_path, monkeypatch):
    first_report = build_budget_preflight(REPO_ROOT, catalog)
    history_path = tmp_path / "budget_history.json"
    record_budget_snapshot(REPO_ROOT, first_report, history_path)

    second_report = copy.deepcopy(first_report)
    for row in second_report["profiles"]:
        row["commit"] = "second-commit"
        if row["profile"] == "cross_layer_architecture":
            row["usage"] = row["budget"] + 1
            row["headroom_tokens"] = -1
            row["headroom_percent"] = -0.01
            row["overflow_tokens"] = 1
            row["fits"] = False
            row["health"] = "FAIL"
    monkeypatch.setattr(budget_history, "_changed_paths", lambda *_args: ["docs/new.md"])
    result = record_budget_snapshot(REPO_ROOT, second_report, history_path)
    history = json.loads(history_path.read_text(encoding="utf-8"))
    row = next(
        row for row in history["snapshots"][-1]["profiles"]
        if row["profile"] == "cross_layer_architecture"
    )
    assert result["growth_breaks"] == ["cross_layer_architecture"]
    assert result["growth_break_counts"]["cross_layer_architecture"] == 1
    assert row["cause"] == "growth"
    assert row["growth_break"] is True
    assert row["growth_break_count"] == 1
    previous = next(
        item for item in history["snapshots"][0]["profiles"]
        if item["profile"] == "cross_layer_architecture"
    )
    assert row["usage_delta"] == row["usage"] - previous["usage"]
    assert row["changed_paths"] == ["docs/new.md"]


def test_document_budget_is_enforced(catalog):
    with pytest.raises(ContextLibrarianError) as excinfo:
        build_bundle(
            catalog,
            task_type="core_reasoning_change",
            query="lead reasoning",
            max_documents=3,
        )
    message = str(excinfo.value)
    assert "document budget overflow" in message
    assert "no source was omitted" in message
    assert "PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md" in message


def test_token_overflow_reports_estimate_budget_overflow_and_node_source_breakdown(
    catalog,
):
    with pytest.raises(ContextLibrarianError) as excinfo:
        build_bundle(
            catalog,
            task_type="approval_ux",
            query="approval message",
            max_tokens=100,
        )
    message = str(excinfo.value)
    assert "estimated_tokens=" in message
    assert "budget=100" in message
    assert "overflow=" in message
    assert "breakdown by node/source:" in message
    assert "layer.approvals" in message
    assert "CURRENT_STATE_MAP.md" in message


def test_full_metadata_is_rendered_without_truncation(catalog):
    node = catalog.nodes["layer.core_reasoning"]
    bundle = build_bundle(
        catalog,
        task_type="core_reasoning_change",
        query="lead reasoning",
    )
    for value in node["notes"] + node["code_paths"] + node["test_paths"]:
        assert value in bundle
    for reference in node["canonical_docs"]:
        if reference.get("status") not in {"historical", "superseded"}:
            assert reference["path"] in bundle


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


def test_turn_coordinator_bundle_maps_auto_capture_flag(catalog):
    bundle = build_bundle(
        catalog,
        task_type="turn_coordinator_routing",
        query="lead routing",
    )
    assert "FEATURE_AUTO_CAPTURE" in bundle
    assert "feature_flags.py:98" in bundle


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


def test_stale_node_is_warning_and_does_not_block_bundle(catalog, monkeypatch):
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
    assert "- status: REVIEW_REQUIRED" in bundle
    assert "stale_nodes" in bundle
    assert "- stale_nodes: 1 ['layer.tools']" in bundle


def test_direct_verification_allows_planning_with_ledger(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_changed_paths", lambda _root, _commit: {"tools/dispatcher.py"})
    bundle = build_bundle(
        catalog, task_type="tool_execution", query="dispatcher evidence",
        direct_source_reverified=True, verification_ledger=["tools/dispatcher.py@main"],
    )
    assert "- status: WARNING" in bundle
    assert "tools/dispatcher.py@main" in bundle


def test_direct_verification_without_ledger_still_requires_review():
    gate = evaluate_workflow_gate(
        stale_node_ids=["layer.tools"], direct_source_reverified=True
    )
    assert gate["status"] == "REVIEW_REQUIRED"
    assert "direct_source_reverification" in gate["review_required"]


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
    assert "Stale nodes alone never stop" in agents

    assert "canonical Context Librarian bootstrap in `AGENTS.md`" in claude
    assert "suggest-profile" not in claude
    assert "**Before doing anything else**, read `AI_CONTEXT.md`" not in claude


# --- N17 pilot findings remediation (PR #485, 2026-07-28) ---
#
# הבדיקות למטה מגנות-רגרסיה על ארבעה מתוך חמשת הממצאים שפיילוט ה-non-inferiority
# מ-28/07/2026 מצא (docs/context_librarian/PHASE1_NON_INFERIORITY_PILOT.md, סעיף
# "2026-07-28 non-inferiority pilot advancement"): core_reasoning_change חסר
# מקור-סמכות מחייב, approval_ux חסר את ממצא-מקורות-האמת-המקבילים, turn_coordinator_routing
# חסר רשומת bug-log סמוכה, ו-commit/branch mislabeling של משימת ה-rp5. בדיקה חמישית
# מגנה על באג נפרד, לא-מהפיילוט, שנמצא תוך כדי התיקון: _render() הציג רק את ההערה הראשונה של
# כל node. שתי הבדיקות האחרונות בקובץ מגנות על ממצאי CodeRabbit על ה-PR הזה עצמו
# (path traversal, ערך expansion פגום).


def test_core_reasoning_profile_includes_decision_adapter_and_write_side_note(catalog):
    bundle = build_bundle(
        catalog,
        task_type="core_reasoning_change",
        query="business outcome maps to wrong reasoning state",
    )
    assert "`core/adapters/decision_adapter.py`" in bundle
    assert "decision_orchestrator.py no longer exists on main" in bundle
    assert "tma_api.py is listed above as both the only live caller" in bundle


def test_approval_ux_profile_surfaces_parallel_approval_mechanisms(catalog):
    bundle = build_bundle(
        catalog,
        task_type="approval_ux",
        query="repeated approval returns the wrong message",
    )
    assert "PARALLEL APPROVAL MECHANISMS" in bundle
    assert "`event_bus.py`" in bundle
    assert "PendingActionsStore" in bundle


def test_turn_coordinator_routing_expansion_surfaces_adjacent_bug(catalog):
    bundle = build_bundle(
        catalog,
        task_type="turn_coordinator_routing",
        query="explicit request routes to wrong handler",
    )
    assert "## Local Context Expansion" in bundle
    assert "BUG-130" in bundle
    assert "BUG-140" in bundle


def test_bounded_local_expansion_is_not_query_driven(catalog):
    def expansion_section(bundle: str) -> str:
        match = re.search(
            r"## Local Context Expansion\n\n(.*?)\n\n## Do Not Assume", bundle, re.S
        )
        assert match, "Local Context Expansion section missing"
        return match.group(1)

    first = build_bundle(
        catalog, task_type="turn_coordinator_routing", query="zzz unrelated wording"
    )
    second = build_bundle(
        catalog,
        task_type="turn_coordinator_routing",
        query="a completely different phrasing with no bug numbers at all",
    )
    assert expansion_section(first) == expansion_section(second)


def test_bounded_local_expansion_window_lines_is_capped(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "task_profiles/profiles.json"
    data = _read_json(path)
    profile = next(p for p in data["profiles"] if p["id"] == "approval_ux")
    profile["bounded_local_expansions"] = [
        {
            "path": "BUG_AUDIT_LOG.md",
            "anchor": "BUG-130",
            "window_lines": librarian.MAXIMUM_LOCAL_EXPANSION_WINDOW_LINES + 1,
            "role": "too large",
        }
    ]
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="window_lines"):
        load_catalog(REPO_ROOT)


def test_bounded_local_expansion_fails_closed_when_anchor_missing(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "task_profiles/profiles.json"
    data = _read_json(path)
    profile = next(p for p in data["profiles"] if p["id"] == "approval_ux")
    profile["bounded_local_expansions"] = [
        {
            "path": "BUG_AUDIT_LOG.md",
            "anchor": "NO-SUCH-ANCHOR-STRING-XYZ",
            "window_lines": 10,
            "role": "will not match anything",
        }
    ]
    _write_json(path, data)
    isolated_catalog = load_catalog(REPO_ROOT)
    with pytest.raises(ContextLibrarianError, match="not found"):
        build_bundle(isolated_catalog, task_type="approval_ux", query="approval message")


def test_bundle_provenance_reports_commit_branch_and_warns_off_main(catalog, monkeypatch):
    monkeypatch.setattr(
        librarian,
        "_git_provenance",
        lambda _root: {"commit": "abc1234", "branch": "feature-x", "on_main": "no"},
    )
    bundle = build_bundle(
        catalog, task_type="rp5_evidence_mismatch", query="evidence mismatch"
    )
    assert "generated_commit: `abc1234`" in bundle
    assert "generated_branch: `feature-x`" in bundle
    assert "- on_main_history: no" in bundle
    assert "WARNING: commit is not proven on `main`" in bundle


def test_bundle_provenance_omits_warning_when_on_main(catalog, monkeypatch):
    monkeypatch.setattr(
        librarian,
        "_git_provenance",
        lambda _root: {"commit": "deadbee", "branch": "main", "on_main": "yes"},
    )
    bundle = build_bundle(
        catalog, task_type="rp5_evidence_mismatch", query="evidence mismatch"
    )
    assert "- on_main_history: yes" in bundle
    assert "WARNING" not in bundle


@pytest.mark.parametrize("on_main", ["no", "unknown"])
def test_assert_main_fails_closed_unless_proven(catalog, monkeypatch, on_main):
    monkeypatch.setattr(
        librarian,
        "_git_provenance",
        lambda _root: {"commit": "abc1234", "branch": "feature-x", "on_main": on_main},
    )
    with pytest.raises(ContextLibrarianError, match="assert-main"):
        build_bundle(
            catalog,
            task_type="rp5_evidence_mismatch",
            query="evidence mismatch",
            assert_main=True,
        )


def test_assert_main_succeeds_when_proven_on_main(catalog, monkeypatch):
    monkeypatch.setattr(
        librarian,
        "_git_provenance",
        lambda _root: {"commit": "deadbee", "branch": "main", "on_main": "yes"},
    )
    bundle = build_bundle(
        catalog,
        task_type="rp5_evidence_mismatch",
        query="evidence mismatch",
        assert_main=True,
    )
    assert "- on_main_history: yes" in bundle


def test_git_provenance_returns_known_shape(catalog):
    result = librarian._git_provenance(catalog.repo_root)
    assert {
        "commit",
        "branch",
        "on_main",
        "on_main_history",
        "at_origin_main_tip",
    } <= set(result)
    assert result["on_main"] in {"yes", "no", "unknown"}
    assert result["on_main_history"] in {"yes", "no", "unknown"}
    assert result["at_origin_main_tip"] in {"yes", "no", "unknown"}


def test_provenance_distinguishes_history_from_origin_tip(catalog, monkeypatch):
    monkeypatch.setattr(
        librarian,
        "_git_provenance",
        lambda _root: {
            "commit": "oldcommit",
            "branch": "feature-x",
            "on_main": "yes",
            "on_main_history": "yes",
            "at_origin_main_tip": "no",
        },
    )
    historical = build_bundle(
        catalog,
        task_type="rp5_evidence_mismatch",
        query="evidence mismatch",
        assert_on_main_history=True,
    )
    assert "on_main_history: yes" in historical
    assert "at_origin_main_tip: no" in historical
    assert "\n- on_main:" not in historical
    with pytest.raises(ContextLibrarianError, match="origin-main-tip"):
        build_bundle(
            catalog,
            task_type="rp5_evidence_mismatch",
            query="evidence mismatch",
            assert_at_origin_main_tip=True,
        )


def test_provenance_warns_when_history_is_current_but_tip_is_old(catalog, monkeypatch):
    monkeypatch.setattr(
        librarian,
        "_git_provenance",
        lambda _root: {
            "commit": "oldcommit",
            "branch": "feature-x",
            "on_main": "yes",
            "on_main_history": "yes",
            "at_origin_main_tip": "no",
        },
    )
    bundle = build_bundle(
        catalog,
        task_type="rp5_evidence_mismatch",
        query="evidence mismatch",
    )
    assert "not the local `origin/main` tip" in bundle


def test_origin_main_tip_assert_fails_closed_when_ref_is_missing(catalog, monkeypatch):
    monkeypatch.setattr(
        librarian,
        "_git_provenance",
        lambda _root: {
            "commit": "oldcommit",
            "branch": "feature-x",
            "on_main": "yes",
            "on_main_history": "yes",
            "at_origin_main_tip": "unknown",
        },
    )
    with pytest.raises(ContextLibrarianError, match="at-origin-main-tip"):
        build_bundle(
            catalog,
            task_type="rp5_evidence_mismatch",
            query="evidence mismatch",
            assert_at_origin_main_tip=True,
        )


def test_output_is_deterministic_including_provenance_and_expansion(catalog):
    kwargs = {
        "task_type": "turn_coordinator_routing",
        "query": "explicit request routes to wrong handler",
    }
    assert build_bundle(catalog, **kwargs) == build_bundle(catalog, **kwargs)


def test_cli_assert_main_flag_fails_closed_off_main(monkeypatch, capsys):
    from tools.context_librarian.__main__ import main

    monkeypatch.setattr(
        librarian,
        "_git_provenance",
        lambda _root: {"commit": "abc1234", "branch": "feature-x", "on_main": "no"},
    )
    exit_code = main(
        [
            "build",
            "--task-type",
            "rp5_evidence_mismatch",
            "--query",
            "evidence",
            "--assert-main",
        ]
    )
    assert exit_code == 2
    assert "assert-main" in capsys.readouterr().err


def test_layer_notes_beyond_the_first_are_rendered_not_dropped(catalog):
    node = catalog.nodes["layer.core_reasoning"]
    assert len(node["notes"]) > 1, "fixture must exercise multiple notes in order"
    bundle = build_bundle(
        catalog, task_type="core_reasoning_change", query="lead reasoning"
    )
    note_positions = []
    for note in node["notes"]:
        assert note in bundle
        note_positions.append(bundle.index(note))
    assert note_positions == sorted(note_positions)


def test_single_layer_note_is_rendered_without_truncation(catalog):
    isolated = copy.deepcopy(catalog)
    isolated.nodes["layer.core_reasoning"]["notes"] = ["single fixture note"]
    bundle = build_bundle(
        isolated, task_type="core_reasoning_change", query="lead reasoning"
    )
    assert "single fixture note" in bundle


def test_layer_notes_fixture_rendering_matches_existing_format(catalog, monkeypatch):
    # This test exists to prove the exact layer-notes rendering FORMAT, not
    # to assert that layer.core_reasoning happens to be fresh on whatever
    # commit main is at when the suite runs -- staleness is real, mechanical
    # git-diff-derived state (see librarian._freshness) that legitimately
    # flips as later commits touch the node's own code_paths (e.g. tma_api.py
    # in commit bc40792) without a corresponding last_verified_commit bump.
    # Pin _git_changed_paths to "nothing changed" so the freshness label is
    # deterministic, matching the pattern used by
    # test_stale_detection_uses_code_diffs_not_path_existence and friends.
    monkeypatch.setattr(librarian, "_git_changed_paths", lambda _root, _commit: set())
    node = catalog.nodes["layer.core_reasoning"]
    notes = iter(node["notes"])
    first_note = next(notes)
    expected_lines = [
        f"- `core_reasoning` (primary, shadow, fresh against tracked code) — {first_note}"
    ]
    expected_lines.extend(f"    - {note}" for note in notes)
    bundle = build_bundle(
        catalog, task_type="core_reasoning_change", query="lead reasoning"
    )
    assert "\n".join(expected_lines) in bundle


def test_bounded_local_expansion_rejects_non_object_entry(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "task_profiles/profiles.json"
    data = _read_json(path)
    profile = next(p for p in data["profiles"] if p["id"] == "approval_ux")
    profile["bounded_local_expansions"] = [None]
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="bounded_local_expansions"):
        load_catalog(REPO_ROOT)


@pytest.mark.parametrize(
    ("bad_path", "expected_message"),
    [
        ("../../../etc/passwd", "escapes repo root"),
        ("/etc/passwd", "must be relative"),
    ],
)
def test_bounded_local_expansion_rejects_paths_outside_repo_root(
    tmp_path, monkeypatch, bad_path, expected_message
):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "task_profiles/profiles.json"
    data = _read_json(path)
    profile = next(p for p in data["profiles"] if p["id"] == "approval_ux")
    profile["bounded_local_expansions"] = [
        {
            "path": bad_path,
            "anchor": "root",
            "window_lines": 5,
            "role": "escape attempt",
        }
    ]
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match=expected_message):
        load_catalog(REPO_ROOT)


@pytest.mark.parametrize("absolute_path", ["/etc/passwd", "C:/etc/passwd"])
def test_bounded_local_expansion_rejects_posix_and_windows_absolute_paths(
    tmp_path, monkeypatch, absolute_path
):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "task_profiles/profiles.json"
    data = _read_json(path)
    profile = next(p for p in data["profiles"] if p["id"] == "approval_ux")
    profile["bounded_local_expansions"] = [
        {
            "path": absolute_path,
            "anchor": "root",
            "window_lines": 5,
            "role": "absolute path regression",
        }
    ]
    _write_json(path, data)
    with pytest.raises(ContextLibrarianError, match="must be relative"):
        load_catalog(REPO_ROOT)


def test_bounded_local_expansion_accepts_relative_path(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "task_profiles/profiles.json"
    data = _read_json(path)
    profile = next(p for p in data["profiles"] if p["id"] == "approval_ux")
    profile["bounded_local_expansions"] = [
        {
            "path": "BUG_AUDIT_LOG.md",
            "anchor": "BUG-130",
            "window_lines": 5,
            "role": "relative path regression",
        }
    ]
    _write_json(path, data)
    isolated_catalog = load_catalog(REPO_ROOT)
    bundle = build_bundle(isolated_catalog, task_type="approval_ux", query="approval")
    assert "relative path regression" in bundle


# --- Consumption Enforcement (CONSUMPTION_ENFORCEMENT_PLAN.md, Phase 1) ---


def test_consumption_checklist_lists_exactly_the_mandatory_tier(catalog):
    profile = catalog.profiles["approval_ux"]
    items = set(consumption_checklist(catalog, profile))

    mandatory_layers = list(
        dict.fromkeys(profile["primary_layers"] + profile["required_dependency_layers"])
    )
    def _current_docs(node):
        return [
            ref["path"]
            for ref in node["canonical_docs"]
            if ref.get("status") not in librarian.DEFAULT_EXCLUDED_STATUSES
        ]

    expected: set[str] = set()
    for layer in mandatory_layers:
        node = catalog.nodes[catalog.layer_nodes[layer]]
        expected.update(f"code:{path}" for path in node["code_paths"])
        expected.update(f"test:{path}" for path in node["test_paths"])
        expected.update(f"doc:{path}" for path in _current_docs(node))
    for decision in profile["mandatory_canonical_decisions"]:
        node = catalog.nodes[f"decision.{decision}"]
        expected.update(f"doc:{path}" for path in _current_docs(node))
        expected.add(f"decision:{decision}")
    for expansion in profile["bounded_local_expansions"]:
        if expansion.get("required_for_conclusion", True):
            expected.add(f"expansion:{expansion['path']}#{expansion['anchor']}")

    assert items == expected
    assert not any(item.startswith("evidence:") for item in items), (
        "no production claim was made; evidence must not be mandatory"
    )


def test_consumption_checklist_item_ids_are_stable_and_deterministic(catalog):
    profile = catalog.profiles["turn_coordinator_routing"]
    first = consumption_checklist(catalog, profile, production_claim=True)
    second = consumption_checklist(catalog, profile, production_claim=True)
    assert first == second == sorted(first)


@pytest.mark.parametrize(
    "profile_id",
    [
        "approval_ux",
        "tool_execution",
        "turn_coordinator_routing",
        "core_reasoning_change",
        "rp5_evidence_mismatch",
        "ux_f52_message",
        "cross_layer_architecture",
    ],
)
def test_optional_and_conditional_evidence_never_appear_in_consumption_checklist(
    catalog, profile_id
):
    profile = catalog.profiles[profile_id]
    mandatory_layers = set(profile["primary_layers"]) | set(profile["required_dependency_layers"])
    optional_layers = (
        set(profile["optional_evidence"])
        | {condition["layer"] for condition in profile["conditional_optional_evidence"]}
    ) - mandatory_layers

    # A path shared between an optional layer and a mandatory one is fine —
    # it is mandatory because of the mandatory layer, not despite it. What
    # must never happen is a path *unique* to the optional/conditional layer
    # leaking into the mandatory tier.
    mandatory_code = {
        path
        for layer in mandatory_layers
        for path in catalog.nodes[catalog.layer_nodes[layer]]["code_paths"]
    }
    mandatory_test = {
        path
        for layer in mandatory_layers
        for path in catalog.nodes[catalog.layer_nodes[layer]]["test_paths"]
    }
    mandatory_evidence = {
        ref["path"]
        for layer in mandatory_layers
        for ref in catalog.nodes[catalog.layer_nodes[layer]]["production_evidence"]
    }

    # production_claim=True is the maximum-exposure case (also pulls in
    # evidence:*) — even then, a strictly-optional/conditional layer's own
    # paths must never appear, since the checklist doesn't even accept a
    # query argument to be driven by.
    items = set(consumption_checklist(catalog, profile, production_claim=True))
    for layer in optional_layers:
        node = catalog.nodes[catalog.layer_nodes[layer]]
        for path in node["code_paths"]:
            if path not in mandatory_code:
                assert f"code:{path}" not in items
        for path in node["test_paths"]:
            if path not in mandatory_test:
                assert f"test:{path}" not in items
        for ref in node["production_evidence"]:
            if ref["path"] not in mandatory_evidence:
                assert f"evidence:{ref['path']}" not in items


def test_production_evidence_only_required_with_production_claim(catalog):
    profile = catalog.profiles["approval_ux"]
    without_claim = consumption_checklist(catalog, profile, production_claim=False)
    with_claim = consumption_checklist(catalog, profile, production_claim=True)
    assert not any(item.startswith("evidence:") for item in without_claim)
    evidence_items = [item for item in with_claim if item.startswith("evidence:")]
    assert evidence_items
    assert (
        "evidence:docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md"
        in with_claim
    )


def test_bounded_local_expansion_required_for_conclusion_field_is_additive_and_backward_compatible(
    tmp_path, monkeypatch
):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "task_profiles/profiles.json"
    data = _read_json(path)
    profile = next(p for p in data["profiles"] if p["id"] == "turn_coordinator_routing")

    before = build_bundle(
        load_catalog(REPO_ROOT), task_type="turn_coordinator_routing", query="routing"
    )

    for expansion in profile["bounded_local_expansions"]:
        expansion["required_for_conclusion"] = True
    _write_json(path, data)
    after_catalog = load_catalog(REPO_ROOT)
    after = build_bundle(after_catalog, task_type="turn_coordinator_routing", query="routing")
    assert before == after

    checklist_profile = after_catalog.profiles["turn_coordinator_routing"]
    items = consumption_checklist(after_catalog, checklist_profile)
    assert any(item.startswith("expansion:") for item in items)

    for expansion in profile["bounded_local_expansions"]:
        expansion["required_for_conclusion"] = False
    _write_json(path, data)
    opt_out_catalog = load_catalog(REPO_ROOT)
    opt_out_items = consumption_checklist(
        opt_out_catalog, opt_out_catalog.profiles["turn_coordinator_routing"]
    )
    assert not any(item.startswith("expansion:") for item in opt_out_items)
    # required_for_conclusion only scopes the checklist — it must not remove
    # the expansion from the rendered bundle itself.
    opt_out_bundle = build_bundle(
        opt_out_catalog, task_type="turn_coordinator_routing", query="routing"
    )
    assert "BUG-130" in opt_out_bundle


def test_verify_consumption_succeeds_when_all_mandatory_items_accounted_for(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "test query")
    result = verify_consumption(
        catalog, task_type="approval_ux", query="test query", ledger=ledger
    )
    assert result.status == "CONSUMPTION: COMPLETE"
    assert result.exit_code == 0
    assert not result.unreviewed_sources
    assert not result.blocked_reasons


def test_verify_consumption_fails_closed_on_missing_item(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "test query")
    dropped = ledger["review_receipts"].pop()
    result = verify_consumption(
        catalog, task_type="approval_ux", query="test query", ledger=ledger
    )
    assert result.status == "CONCLUSION_BLOCKED"
    assert result.exit_code == 2
    assert result.unreviewed_sources == (dropped["item_id"],)


def test_verify_consumption_fails_closed_on_empty_waiver_reason(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    profile = catalog.profiles["approval_ux"]
    items = consumption_checklist(catalog, profile)
    receipts = [
        _receipt(item_id, commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q")
        for item_id in items[1:]
    ]
    waived = _waiver(
        items[0], commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q",
        reason="   ",
    )
    ledger = _ledger(
        task_type="approval_ux", profile="approval_ux", query="q",
        commit="deadbee", branch="claude/test-branch",
        required_sources=items, review_receipts=receipts, waived_sources=[waived],
    )
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert items[0] in result.unreviewed_sources


@pytest.mark.parametrize("field", ["reason", "evidence_reference"])
def test_verify_consumption_fails_closed_on_non_string_reason_or_evidence(
    catalog, monkeypatch, field
):
    # A non-string reason/evidence_reference (e.g. a list) must fail closed
    # with a controlled CONCLUSION_BLOCKED, not crash — it is later used as a
    # dict key for duplicate detection, where an unhashable type would raise
    # an uncaught TypeError instead.
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    ledger["review_receipts"][0][field] = ["not", "a", "string"]
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert ledger["review_receipts"][0]["item_id"] in result.unreviewed_sources


def test_verify_consumption_fails_closed_on_missing_evidence_reference(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    ledger["review_receipts"][0]["evidence_reference"] = "  "
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert ledger["review_receipts"][0]["item_id"] in result.unreviewed_sources


@pytest.mark.parametrize("field", ["commit", "branch", "profile", "query"])
def test_verify_consumption_fails_closed_on_bundle_field_mismatch(catalog, monkeypatch, field):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    mismatched_item = ledger["review_receipts"][0]["item_id"]
    ledger["review_receipts"][0][field] = "something-else-entirely"
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert mismatched_item in result.unreviewed_sources


def test_verify_consumption_rejects_forged_unreviewed_sources_field(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    ledger["unreviewed_sources"] = []
    with pytest.raises(ContextLibrarianError, match="forged"):
        verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)


def test_verify_consumption_fails_closed_on_path_item_id_mismatch(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    mismatched_item = ledger["review_receipts"][0]["item_id"]
    ledger["review_receipts"][0]["path"] = "some/completely/unrelated/file.py"
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert mismatched_item in result.unreviewed_sources


def test_verify_consumption_fails_closed_on_decision_item_with_non_null_path(
    catalog, monkeypatch
):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    decision_receipt = next(
        r for r in ledger["review_receipts"] if r["item_id"].startswith("decision:")
    )
    decision_receipt["path"] = "not/actually/null.md"
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert decision_receipt["item_id"] in result.unreviewed_sources


def test_verify_consumption_fails_closed_on_unknown_item_id(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    # An extra receipt for an item that isn't in this profile's mandatory
    # tier at all must not be silently accepted.
    ledger["review_receipts"].append(
        _receipt(
            "code:totally/not/a/real/mandatory/path.py",
            commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q",
        )
    )
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"


def test_verify_consumption_fails_closed_on_duplicate_item_id_across_entries(
    catalog, monkeypatch
):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    duplicated_item = ledger["review_receipts"][0]["item_id"]
    # Same item covered by a second receipt — ambiguous, not "extra diligence".
    ledger["review_receipts"].append(
        _receipt(
            duplicated_item, commit="deadbee", branch="claude/test-branch",
            profile="approval_ux", query="q",
        )
    )
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert duplicated_item in result.unreviewed_sources


def test_verify_consumption_fails_closed_on_item_id_in_both_receipt_and_waiver(
    catalog, monkeypatch
):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    profile = catalog.profiles["approval_ux"]
    items = consumption_checklist(catalog, profile)
    receipts = [
        _receipt(item_id, commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q")
        for item_id in items
    ]
    conflicting_waiver = _waiver(
        items[0], commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q"
    )
    ledger = _ledger(
        task_type="approval_ux", profile="approval_ux", query="q",
        commit="deadbee", branch="claude/test-branch",
        required_sources=items, review_receipts=receipts, waived_sources=[conflicting_waiver],
    )
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert items[0] in result.unreviewed_sources


def test_verify_consumption_fails_closed_on_required_sources_mismatch(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    ledger["required_sources"] = ledger["required_sources"][:-1]
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert any("required_sources does not match" in reason for reason in result.blocked_reasons)


def test_verify_consumption_fails_closed_on_production_claim_mismatch(catalog, monkeypatch):
    # A ledger authored for a production claim, verified without
    # --production-claim, must not silently shrink the mandatory tier and
    # pass — that would let evidence review go unverified.
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q", production_claim=True)
    result = verify_consumption(
        catalog, task_type="approval_ux", query="q", ledger=ledger, production_claim=False
    )
    assert result.status == "CONCLUSION_BLOCKED"
    assert any("production_claim" in reason for reason in result.blocked_reasons)


def test_verify_consumption_succeeds_with_matching_production_claim(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q", production_claim=True)
    result = verify_consumption(
        catalog, task_type="approval_ux", query="q", ledger=ledger, production_claim=True
    )
    assert result.status == "CONSUMPTION: COMPLETE"
    assert any(item_id.startswith("evidence:") for item_id in ledger["required_sources"])


@pytest.mark.parametrize(
    "field", ["commit", "branch", "profile", "query", "reviewed_by", "reviewed_at"]
)
def test_verify_consumption_fails_closed_on_empty_attribution_field(catalog, monkeypatch, field):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    mismatched_item = ledger["review_receipts"][0]["item_id"]
    ledger["review_receipts"][0][field] = ""
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert mismatched_item in result.unreviewed_sources


def test_verify_consumption_fails_closed_on_missing_waiver_approval(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    profile = catalog.profiles["approval_ux"]
    items = consumption_checklist(catalog, profile)
    receipts = [
        _receipt(item_id, commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q")
        for item_id in items[1:]
    ]
    missing_approval = _receipt(
        items[0], commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q"
    )
    ledger = _ledger(
        task_type="approval_ux", profile="approval_ux", query="q",
        commit="deadbee", branch="claude/test-branch",
        required_sources=items, review_receipts=receipts, waived_sources=[missing_approval],
    )
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert items[0] in result.unreviewed_sources


def test_verify_consumption_fails_closed_on_self_approved_waiver(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    profile = catalog.profiles["approval_ux"]
    items = consumption_checklist(catalog, profile)
    receipts = [
        _receipt(item_id, commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q")
        for item_id in items[1:]
    ]
    same_identity = "claude-sonnet-5 / session-test"
    self_approved = _waiver(
        items[0], commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q",
        reviewed_by=same_identity, approved_by=same_identity,
    )
    ledger = _ledger(
        task_type="approval_ux", profile="approval_ux", query="q",
        commit="deadbee", branch="claude/test-branch",
        required_sources=items, review_receipts=receipts, waived_sources=[self_approved],
    )
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert items[0] in result.unreviewed_sources


def test_verify_consumption_treats_identity_change_as_waiver_expiry(catalog, monkeypatch):
    profile = catalog.profiles["approval_ux"]
    items = consumption_checklist(catalog, profile)
    receipts = [
        _receipt(item_id, commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q")
        for item_id in items[1:]
    ]
    waived = _waiver(
        items[0], commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q"
    )
    ledger = _ledger(
        task_type="approval_ux", profile="approval_ux", query="q",
        commit="deadbee", branch="claude/test-branch",
        required_sources=items, review_receipts=receipts, waived_sources=[waived],
    )

    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ok = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert ok.status == "CONSUMPTION: COMPLETE"

    monkeypatch.setattr(
        librarian, "_git_provenance", lambda _root: {**_FIXED_PROVENANCE, "commit": "newcommit"}
    )
    expired = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert expired.status == "CONCLUSION_BLOCKED"
    assert expired.exit_code == 2
    assert any("top-level identity" in reason for reason in expired.blocked_reasons)


def test_verify_consumption_warns_on_duplicate_boilerplate_evidence_across_items(
    catalog, monkeypatch
):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    profile = catalog.profiles["approval_ux"]
    items = consumption_checklist(catalog, profile)
    shared_reason = "reviewed as part of batch review"
    shared_evidence = "grep confirmed presence across the batch"
    receipts = [
        _receipt(
            item_id, commit="deadbee", branch="claude/test-branch", profile="approval_ux", query="q",
            reason=shared_reason, evidence_reference=shared_evidence,
        )
        for item_id in items
    ]
    ledger = _ledger(
        task_type="approval_ux", profile="approval_ux", query="q",
        commit="deadbee", branch="claude/test-branch",
        required_sources=items, review_receipts=receipts,
    )
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONSUMPTION: COMPLETE"
    assert result.exit_code == 0
    assert result.warnings
    assert "duplicate" in result.warnings[0]


def test_verify_consumption_validates_top_level_identity_independently_of_per_item(
    catalog, monkeypatch
):
    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    ledger = _fully_reviewed_ledger(
        catalog, "approval_ux", "q", commit="stale-commit-no-longer-current", branch="claude/test-branch"
    )
    result = verify_consumption(catalog, task_type="approval_ux", query="q", ledger=ledger)
    assert result.status == "CONCLUSION_BLOCKED"
    assert not result.unreviewed_sources
    assert any("top-level identity" in reason for reason in result.blocked_reasons)


def test_cli_estimate_single_profile_fits(monkeypatch, capsys):
    from tools.context_librarian.__main__ import main

    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    exit_code = main(
        ["estimate", "--task-type", "approval_ux", "--query", "approval message"]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "approval_ux\tFITS\t" in out


def test_cli_estimate_single_profile_over_budget_does_not_raise(monkeypatch, capsys):
    from tools.context_librarian.__main__ import main

    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    exit_code = main(
        [
            "estimate",
            "--task-type",
            "approval_ux",
            "--query",
            "approval message",
            "--max-tokens",
            "100",
        ]
    )
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "approval_ux\tOVER_BUDGET\t" in out


def test_cli_estimate_all_profiles(catalog, monkeypatch, capsys):
    from tools.context_librarian.__main__ import main

    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    # query שנבחר בכוונה כך שהוא מושך מספיק conditional optional evidence
    # כדי לחרוג באופן לגיטימי בפרופיל אמיתי אחד לפחות (rp5_evidence_mismatch)
    # -- בודק ש---all-profiles מדווח את התוצאה האמיתית של כל פרופיל
    # (תמהיל FITS/OVER_BUDGET) במקום להניח התאמה אוניברסלית ל-query
    # משותף שרירותי.
    exit_code = main(
        [
            "estimate",
            "--all-profiles",
            "--query",
            "approval message",
            "--max-tokens",
            "100",
        ]
    )
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == len(catalog.profiles)
    reported = {line.split("\t")[0] for line in lines}
    assert reported == set(catalog.profiles)
    any_over_budget = any("OVER_BUDGET" in line for line in lines)
    assert any_over_budget, (
        "test query no longer overflows any profile — pick a new query that "
        "legitimately overflows at least one, so this test still exercises "
        "the mixed FITS/OVER_BUDGET reporting path"
    )
    assert exit_code == 2


def test_cli_estimate_requires_task_type_or_all_profiles():
    from tools.context_librarian.__main__ import main

    with pytest.raises(SystemExit):
        main(["estimate", "--query", "q"])


def test_cli_budget_preflight_all_profiles_json(capsys):
    from tools.context_librarian.__main__ import main

    exit_code = main(["budget-preflight", "--all-profiles", "--json"])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["aggregate"]["total_profiles"] == 8
    assert len(report["profiles"]) == 8
    assert report["estimator"] == ESTIMATOR_ID


def test_cli_budget_preflight_summary_table(capsys):
    from tools.context_librarian.__main__ import main

    exit_code = main(["budget-preflight", "--all-profiles"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "profile\thealth\tusage/budget" in output
    assert "aggregate\tprofiles=8" in output


def test_cli_verify_consumption_subcommand_exists_and_is_wired(tmp_path, monkeypatch, capsys):
    from tools.context_librarian.__main__ import main

    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    catalog = load_catalog(REPO_ROOT)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, ledger)
    exit_code = main(
        [
            "verify-consumption",
            "--task-type",
            "approval_ux",
            "--query",
            "q",
            "--ledger",
            str(ledger_path),
        ]
    )
    assert exit_code == 0
    assert "CONSUMPTION: COMPLETE" in capsys.readouterr().out


def test_cli_verify_consumption_fails_closed_and_lists_unreviewed_sources(
    tmp_path, monkeypatch, capsys
):
    from tools.context_librarian.__main__ import main

    monkeypatch.setattr(librarian, "_git_provenance", lambda _root: _FIXED_PROVENANCE)
    catalog = load_catalog(REPO_ROOT)
    ledger = _fully_reviewed_ledger(catalog, "approval_ux", "q")
    ledger["review_receipts"].pop()
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, ledger)
    exit_code = main(
        [
            "verify-consumption",
            "--task-type",
            "approval_ux",
            "--query",
            "q",
            "--ledger",
            str(ledger_path),
        ]
    )
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "CONCLUSION_BLOCKED" in out
    assert "unreviewed_sources" in out


def test_gate_policy_classifies_github_activity_as_warning_not_stop():
    gate = evaluate_workflow_gate(github_activity=["PR #500", "commit abc"])
    assert gate["status"] == "WARNING"
    assert gate["planning_allowed"] is True
    assert gate["reasons"] == []


def test_gate_policy_stops_on_authority_conflict_and_stale_runtime_change():
    assert evaluate_workflow_gate(unresolved_conflicts=["a -> b"])["status"] == "STOP"
    gate = evaluate_workflow_gate(stale_authority_runtime_changes=["core/approval.py"])
    assert gate["status"] == "STOP"


def test_new_source_classification_never_auto_registers(catalog):
    result = classify_new_sources(
        catalog,
        ["test_new.py", "docs/new-planning.md", "core/new_runtime.py", "core/authority.py"],
    )
    by_path = {item["path"]: item["classification"] for item in result}
    assert by_path["test_new.py"] == "WARNING"
    assert by_path["docs/new-planning.md"] == "WARNING"
    assert by_path["core/new_runtime.py"] == "REVIEW_REQUIRED"
    assert by_path["core/authority.py"] == "STOP"


def test_image_assets_never_stop_on_authority_term_path_substring(catalog):
    # Regression for a false positive: a directory literally named
    # "reference-evidence" (inert UX design screenshots) tripped STOP
    # because "evidence" is an _AUTHORITY_TERMS substring of the path.
    # Images can't carry authority/dispatch logic, so they must classify
    # like docs (WARNING) regardless of naming coincidence — while a real
    # .py file with "authority"/"evidence" in its path must still STOP.
    result = classify_new_sources(
        catalog,
        [
            "docs/ux/reference-evidence/attio/attio-home-desktop.png",
            "docs/ux/reference-evidence/uidrop/owner-supplied-workbench-reference.jpg",
            "core/evidence_authority.py",
        ],
    )
    by_path = {item["path"]: item["classification"] for item in result}
    assert by_path["docs/ux/reference-evidence/attio/attio-home-desktop.png"] == "WARNING"
    assert by_path["docs/ux/reference-evidence/uidrop/owner-supplied-workbench-reference.jpg"] == "WARNING"
    assert by_path["core/evidence_authority.py"] == "STOP"


def test_catalog_metadata_files_are_not_classified_as_new_sources(catalog):
    result = classify_new_sources(
        catalog,
        [
            "docs/context_librarian/decisions/canonical_boundaries.json",
            "docs/context_librarian/layers/approvals.json",
        ],
    )
    assert result == []


def test_librarian_infrastructure_files_are_not_domain_sources(catalog):
    infrastructure = [
        ".githooks/post-merge",
        "docs/context_librarian/generated/.gitkeep",
        "docs/context_librarian/schema/edge_schema.json",
        "docs/context_librarian/schema/node_schema.json",
        "docs/context_librarian/task_profiles/profiles.json",
        "tools/context_librarian/__init__.py",
        "tools/context_librarian/__main__.py",
        "tools/context_librarian/benchmark_token_estimate.py",
        "tools/context_librarian/librarian.py",
        "tools/context_librarian/local_post_merge_check.sh",
        "tools/context_librarian/manage_hooks.py",
        "tools/context_librarian/pilot_preflight.py",
        "tools/context_librarian/refresh_after_merge.py",
    ]
    assert classify_new_sources(catalog, infrastructure) == []


def test_consumption_ledger_artifacts_are_governance_not_blocking(catalog):
    # Real ledger files already in the repo (verify-consumption output,
    # LEDGER_TOP_LEVEL_REQUIRED_FIELDS-shaped) — one at repo root, one nested
    # under docs/architecture/ — proving the check is structural, not path-based.
    result = classify_new_sources(
        catalog,
        [
            "ledger-premerge-approval-ux.json",
            "docs/architecture/turn-coordinator-full/CONSUMPTION_LEDGER.json",
        ],
    )
    by_path = {item["path"]: item for item in result}
    for path in (
        "ledger-premerge-approval-ux.json",
        "docs/architecture/turn-coordinator-full/CONSUMPTION_LEDGER.json",
    ):
        assert by_path[path]["classification"] == "GOVERNANCE_ARTIFACT"
        assert "consumption ledger" in by_path[path]["reason"]
        assert "not a runtime or production source" in by_path[path]["reason"]


def test_json_with_authority_terms_but_not_ledger_shaped_still_stops(catalog):
    # A same-named-pattern file ("approval" in the name, like the real ledger)
    # that does NOT have the ledger's required top-level fields must still be
    # caught as a genuinely unregistered, unknown-shape source — proving the
    # governance-artifact exemption is keyed on structure, not filename guessing.
    # Written directly under the real repo root (what catalog.repo_root actually
    # is) since _is_consumption_ledger_artifact reads the file from disk; always
    # removed afterward regardless of outcome.
    probe_path = REPO_ROOT / "not-a-ledger-approval-file.json"
    probe_path.write_text(json.dumps({"some_other_shape": True}), encoding="utf-8")
    try:
        result = classify_new_sources(catalog, ["not-a-ledger-approval-file.json"])
    finally:
        probe_path.unlink()
    assert len(result) == 1
    assert result[0]["classification"] == "STOP"
    assert result[0]["reason"] == "unregistered source may change authority"


def test_refresh_proposal_treats_governance_artifact_as_non_blocking(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_output", lambda _root, _args: "main-sha")
    monkeypatch.setattr(librarian, "_node_changed_between", lambda *_args: set())
    monkeypatch.setattr(
        librarian,
        "discover_new_sources",
        lambda *_args, **_kwargs: [
            {
                "path": "some/new/ledger.json",
                "classification": "GOVERNANCE_ARTIFACT",
                "reason": "generated Context Librarian consumption ledger",
            }
        ],
    )
    proposal = refresh_proposal(catalog)
    assert proposal["status"] == "WARNING"
    assert proposal["authority_review_required"] is False


@pytest.mark.parametrize("merge_shape", ["normal", "squash"])
def test_refresh_reconciles_provenance_to_canonical_main_sha(catalog, monkeypatch, merge_shape):
    canonical = "normal-main-sha" if merge_shape == "normal" else "squash-main-sha"
    monkeypatch.setattr(
        librarian, "_git_output",
        lambda _root, args: canonical if args[:2] == ["rev-parse", "--verify"] else "",
    )
    monkeypatch.setattr(
        librarian, "_node_changed_between",
        lambda _catalog, node, _sha: {"tracked.py"} if node["id"] == "layer.tools" else set(),
    )
    monkeypatch.setattr(librarian, "discover_new_sources", lambda *_args, **_kwargs: [])
    proposal = refresh_proposal(catalog)
    update = next(item for item in proposal["updates"] if item["node_id"] == "layer.tools")
    assert update["to"] == canonical
    assert update["to"] != "feature-branch-sha"


def test_refresh_noop_reports_ok_without_updates(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_output", lambda _root, _args: "main-sha")
    monkeypatch.setattr(librarian, "_node_changed_between", lambda *_args: set())
    monkeypatch.setattr(librarian, "discover_new_sources", lambda *_args, **_kwargs: [])
    proposal = refresh_after_merge(catalog)
    assert proposal["status"] == "OK"
    assert proposal["updates"] == []


def test_refresh_warning_only_is_non_blocking(catalog, monkeypatch):
    monkeypatch.setattr(librarian, "_git_output", lambda _root, _args: "main-sha")
    monkeypatch.setattr(librarian, "_node_changed_between", lambda *_args: set())
    monkeypatch.setattr(
        librarian,
        "discover_new_sources",
        lambda *_args, **_kwargs: [
            {"path": "test_new.py", "classification": "WARNING", "reason": "new test source"}
        ],
    )
    proposal = refresh_proposal(catalog)
    assert proposal["status"] == "WARNING"
    assert proposal["authority_review_required"] is False


def test_budget_overflow_is_reported_before_output_write(catalog, tmp_path):
    from tools.context_librarian.__main__ import main as cli_main

    output = tmp_path / "bundle.md"
    assert cli_main([
        "build", "--task-type", "rp5_evidence_mismatch", "--query", "evidence",
        "--max-tokens", "1", "--output", str(output),
    ]) == 2
    assert not output.exists()


def test_bundle_reports_budget_breakdown(catalog):
    estimate = estimate_bundle(
        catalog, task_type="tool_execution", query="dispatcher", max_tokens=1
    )
    assert estimate.fits is False
    with pytest.raises(ContextLibrarianError, match="breakdown by node/source"):
        build_bundle(
            catalog, task_type="tool_execution", query="dispatcher", max_tokens=1
        )
