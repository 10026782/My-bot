"""Tests for tools/context_librarian/reconcile.py and policy_registry.py.

Covers the 10 required scenarios for the three-outcome reconciliation engine
(CLEAN / AUTO_MAINTENANCE_REQUIRED / OWNER_DECISION_REQUIRED) plus the
Message D correction's required end-to-end coverage (A-I below) -- see
docs/context_librarian/RECONCILIATION.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.context_librarian import reconcile as reconcile_module
from tools.context_librarian.librarian import ContextLibrarianError, classify_new_sources, load_catalog
from tools.context_librarian.policy_registry import Policy, load_policy_registry, match_policy
from tools.context_librarian.reconcile import (
    AUTO_MAINTENANCE_REQUIRED,
    CLEAN,
    OWNER_DECISION_REQUIRED,
    apply_auto_maintenance,
    reconcile,
    stamp_observed,
)


REPO_ROOT = Path(__file__).resolve().parent
# Real, immutable git history used for a deterministic staleness test (G.1):
# 18724ce is the last commit that touched domain_utils.py; d8fa0ed... merged
# PR #629 on top of it, changing 133 unrelated files but never domain_utils.py.
_DOMAIN_UTILS_LAST_TOUCH = "18724ce"
_LATER_UNRELATED_MAIN_SHA = "d8fa0ed17b6b08f95c9cd3a36b0717098f7d617a"


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(REPO_ROOT)


@pytest.fixture(scope="module")
def policies():
    return load_policy_registry(REPO_ROOT)


def _classify(catalog, paths):
    return classify_new_sources(catalog, paths)


def _reconcile_with_fakes(
    catalog,
    policies,
    *,
    new_sources=(),
    mechanical_updates=(),
    main_sha="deadbee00000000000000000000000000000000",
):
    """Drives reconcile()'s classification/outcome logic without needing a
    real git history change or a real reconciliation_state.json baseline --
    mirrors the previous _reconcile_with_fake_proposal() helper, updated for
    the corrected internal seams (_resolve_main_sha/_mechanical_drift/
    _scan_new_sources instead of librarian.refresh_proposal)."""
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(reconcile_module, "_resolve_main_sha", lambda *_a, **_k: main_sha)
        mp.setattr(reconcile_module, "_mechanical_drift", lambda *_a, **_k: list(mechanical_updates))
        mp.setattr(reconcile_module, "_scan_new_sources", lambda *_a, **_k: list(new_sources))
        return reconcile(catalog, policies, main_ref="origin/main")
    finally:
        mp.undo()


def _isolated_catalog(monkeypatch, tmp_path):
    """Copies the real catalog into tmp_path and points librarian's
    CATALOG_RELATIVE_ROOT at the copy, so writes never touch the real repo
    -- the same isolation pattern test_context_librarian.py's own write
    tests already use."""
    import shutil

    from tools.context_librarian import librarian

    target = tmp_path / "catalog"
    shutil.copytree(REPO_ROOT / "docs/context_librarian", target)
    monkeypatch.setattr(librarian, "CATALOG_RELATIVE_ROOT", target)
    return load_catalog(REPO_ROOT)


# --- Policy registry basics ---------------------------------------------


def test_policy_registry_loads_all_ten_policies(policies):
    ids = {p.id for p in policies}
    assert ids == {
        "DOCUMENTATION_REFERENCE_ASSET",
        "STAGING_VERIFICATION_F15",
        "STAGING_VERIFICATION_APPROVALS_BUG_FAMILY",
        "STAGING_VERIFICATION_TURN_COORDINATOR",
        "TEST_SUPPORT_ARTIFACT",
        "SHARED_UI_PRIMITIVE",
        "CROSS_LAYER_SUPPORTING_METADATA",
        "OFFLINE_RESEARCH_TOOL",
        "EXTERNAL_RECOMMENDATION_CATALOG",
        "EXTERNAL_RECOMMENDATION_CATALOG_TEST",
    }


def test_policy_matching_is_glob_only_not_substring(policies):
    # "evidence" is nowhere in this path as a directory/keyword hit the old
    # substring-based STOP escalation would have cared about -- it must not
    # match DOCUMENTATION_REFERENCE_ASSET via substring coincidence either.
    assert match_policy("core/authority_evidence_tracker.py", policies) is None
    # A real match: exact glob against the declared pattern.
    assert match_policy("scripts/verify_f15_staging.py", policies).id == "STAGING_VERIFICATION_F15"


def test_target_field_never_inferred_all_policies_declare_it_explicitly(policies):
    for policy in policies:
        if policy.eligible_target is None:
            assert policy.target_field is None
            assert not policy.auto_registration_allowed
        else:
            assert policy.target_field in ("code_paths", "test_paths")


# --- G.1: unrelated main commit does not make every node semantically stale ---


def test_unrelated_main_commit_does_not_stale_untouched_node(catalog):
    from tools.context_librarian.librarian import refresh_proposal

    # Real, immutable range: 133 files changed, domain_utils.py not among them.
    changed = set(
        __import__("subprocess")
        .run(
            ["git", "diff", "--name-only", _DOMAIN_UTILS_LAST_TOUCH, _LATER_UNRELATED_MAIN_SHA],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        .stdout.splitlines()
    )
    assert len(changed) > 50, "expected real, substantial unrelated churn in this range"
    assert "domain_utils.py" not in changed

    proposal = refresh_proposal(catalog, main_ref=_LATER_UNRELATED_MAIN_SHA)
    stale_node_ids = {u["node_id"] for u in proposal["updates"]}
    assert "decision.business_domain_vocabulary" not in stale_node_ids


# --- Provenance correction: mechanical drift is anchored on last_observed_commit,
# never directly on last_verified_commit -----------------------------------


def test_observed_baseline_prefers_last_observed_commit_over_last_verified_commit():
    never_observed = {"last_verified_commit": "verified123"}
    assert reconcile_module._observed_baseline(never_observed) == "verified123"

    already_observed = {"last_verified_commit": "verified123", "last_observed_commit": "observed456"}
    assert reconcile_module._observed_baseline(already_observed) == "observed456"


# --- A: mechanical drift -> AUTO -> apply-auto -> reload -> CLEAN, across
# two separate load/reconcile cycles -----------------------------------


def test_apply_auto_maintenance_then_reconcile_is_clean_across_two_reload_cycles(
    catalog, policies, monkeypatch, tmp_path
):
    isolated = _isolated_catalog(monkeypatch, tmp_path)
    some_node = next(n for n in isolated.nodes.values() if n["code_paths"])
    fake_changed_path = some_node["code_paths"][0]
    main_sha = "a1b2c3d4e5f60000000000000000000000000000"

    def fake_changed(_repo_root, base, target):
        if base == target:
            return set()
        return {fake_changed_path}

    monkeypatch.setattr(reconcile_module, "_changed_paths_between", fake_changed)
    monkeypatch.setattr(reconcile_module, "_resolve_main_sha", lambda *_a, **_k: main_sha)
    monkeypatch.setattr(reconcile_module, "_scan_new_sources", lambda *_a, **_k: [])
    monkeypatch.setattr(reconcile_module, "_current_branch_and_commit", lambda _root: ("main", main_sha))
    monkeypatch.setattr(reconcile_module, "_working_tree_is_clean", lambda _root: True)

    first = reconcile(isolated, policies, main_ref="origin/main")
    assert first.outcome == AUTO_MAINTENANCE_REQUIRED
    assert any(u["node_id"] == some_node["id"] for u in first.mechanical_updates)

    applied = apply_auto_maintenance(isolated, first)
    assert some_node["id"] in applied["stamped_nodes"]
    assert applied["source_scan_commit"] == main_sha

    reloaded_1 = load_catalog(REPO_ROOT)
    assert reloaded_1.nodes[some_node["id"]]["last_observed_commit"] == main_sha
    second = reconcile(reloaded_1, policies, main_ref="origin/main")
    assert second.outcome == CLEAN

    # A second, entirely separate load/reconcile cycle -- the real CLI runs
    # as a fresh process every invocation, so this is the guarantee that
    # actually matters, not just "the same Python object stays clean".
    reloaded_2 = load_catalog(REPO_ROOT)
    third = reconcile(reloaded_2, policies, main_ref="origin/main")
    assert third.outcome == CLEAN


def test_apply_auto_maintenance_refuses_unless_outcome_is_auto_maintenance_required(catalog, policies):
    clean_result = _reconcile_with_fakes(catalog, policies)
    assert clean_result.outcome == CLEAN
    with pytest.raises(ContextLibrarianError):
        apply_auto_maintenance(catalog, clean_result)


def test_apply_auto_maintenance_requires_head_at_canonical_sha(catalog, policies, monkeypatch):
    result = _reconcile_with_fakes(
        catalog, policies,
        mechanical_updates=[{"node_id": "layer.marketing", "from": "a", "to": "deadbee00000000000000000000000000000000", "changed_paths": ["x.py"]}],
    )
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED
    monkeypatch.setattr(reconcile_module, "_current_branch_and_commit", lambda _root: ("main", "wrong-sha"))
    with pytest.raises(ContextLibrarianError):
        apply_auto_maintenance(catalog, result)


# --- B: policy-approved new source -> AUTO -> apply-auto -> registered into
# the correct target_field -> reload -> CLEAN -------------------------------


def test_policy_approved_new_source_registers_and_reconciles_clean(catalog, policies, monkeypatch, tmp_path):
    # Classification against the real (module-scoped) catalog fixture --
    # _catalog_referenced_paths() resolves paths relative to catalog.repo_root,
    # which only holds for the real repo layout, not an isolated tmp copy
    # whose catalog_root lives outside repo_root.
    assert "scripts/verify_bug157_160_163_staging.py" not in catalog.nodes["layer.approvals"]["test_paths"]
    new_sources = classify_new_sources(catalog, ["scripts/verify_bug157_160_163_staging.py"])

    isolated = _isolated_catalog(monkeypatch, tmp_path)
    main_sha = "b2c3d4e5f6070000000000000000000000000000"

    monkeypatch.setattr(reconcile_module, "_resolve_main_sha", lambda *_a, **_k: main_sha)
    monkeypatch.setattr(reconcile_module, "_mechanical_drift", lambda *_a, **_k: [])
    monkeypatch.setattr(reconcile_module, "_scan_new_sources", lambda *_a, **_k: new_sources)
    monkeypatch.setattr(reconcile_module, "_current_branch_and_commit", lambda _root: ("main", main_sha))
    monkeypatch.setattr(reconcile_module, "_working_tree_is_clean", lambda _root: True)

    first = reconcile(isolated, policies, main_ref="origin/main")
    assert first.outcome == AUTO_MAINTENANCE_REQUIRED
    assert len(first.auto_maintenance_sources) == 1
    assert first.auto_maintenance_sources[0]["policy_id"] == "STAGING_VERIFICATION_APPROVALS_BUG_FAMILY"
    assert first.auto_maintenance_sources[0]["target_field"] == "test_paths"

    applied = apply_auto_maintenance(isolated, first)
    assert "layer.approvals.test_paths:scripts/verify_bug157_160_163_staging.py" in applied["registered"]

    reloaded = load_catalog(REPO_ROOT)
    assert "scripts/verify_bug157_160_163_staging.py" in reloaded.nodes["layer.approvals"]["test_paths"]

    monkeypatch.setattr(reconcile_module, "_scan_new_sources", lambda *_a, **_k: [])
    second = reconcile(reloaded, policies, main_ref="origin/main")
    assert second.outcome == CLEAN


# --- C: unknown runtime source -> OWNER_DECISION_REQUIRED; apply-auto refuses ---


def test_unknown_runtime_python_file_requires_owner_decision_and_apply_auto_refuses(catalog, policies):
    new_sources = _classify(catalog, ["totally_new_unclassified_module.py"])
    result = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    assert len(result.decision_queue) == 1
    assert "policy_id" not in result.decision_queue[0]
    assert result.outcome == OWNER_DECISION_REQUIRED
    with pytest.raises(ContextLibrarianError):
        apply_auto_maintenance(catalog, result)


# --- D: STOP source -> OWNER_DECISION_REQUIRED even with a catch-all policy ---


def test_authority_named_path_never_auto_approved_even_with_hypothetical_policy_match(catalog, policies):
    new_sources = _classify(catalog, ["core/new_action_gateway_extension.py"])
    assert new_sources[0]["classification"] == "STOP"
    result = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    assert result.decision_queue[0]["path"] == "core/new_action_gateway_extension.py"
    assert result.outcome == OWNER_DECISION_REQUIRED

    # Structural guarantee, not just "no policy happens to match today": even
    # a maximally permissive (and nonsensically configured) policy that
    # matches every path must never move a STOP classification into
    # auto-maintenance.
    catch_all = Policy(
        id="CATCH_ALL_TEST_ONLY", description="test-only", path_patterns=("*",),
        runtime_consumed=True, authority=False, eligible_target=None, target_field=None,
        auto_registration_allowed=True, classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE",
        notes=(),
    )
    result_with_catch_all = _reconcile_with_fakes(catalog, (catch_all,), new_sources=new_sources)
    assert len(result_with_catch_all.auto_maintenance_sources) == 0
    assert result_with_catch_all.outcome == OWNER_DECISION_REQUIRED


# --- E: policy match with a target that does not exist -> OWNER_DECISION_REQUIRED ---


def test_policy_match_with_nonexistent_target_requires_owner_decision(catalog, policies):
    assert "decision.business_domain_vocabulary" not in catalog.nodes
    new_sources = _classify(catalog, ["domain_utils.py"])
    result = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    assert len(result.decision_queue) == 1
    item = result.decision_queue[0]
    assert item["policy_id"] == "CROSS_LAYER_SUPPORTING_METADATA"
    assert "does not exist" in item["policy_note"]
    assert result.outcome == OWNER_DECISION_REQUIRED


def test_staging_verification_f15_requires_target_to_exist(catalog, policies):
    # decision.f15_staging_verification_artifact is introduced by PR #628,
    # not by this branch -- until it is created and this branch rebased,
    # a match must not be silently trusted.
    assert "decision.f15_staging_verification_artifact" not in catalog.nodes
    new_sources = _classify(catalog, ["scripts/verify_f15_staging.py"])
    result = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    item = result.decision_queue[0]
    assert item["policy_id"] == "STAGING_VERIFICATION_F15"
    assert "does not exist" in item["policy_note"]
    assert result.outcome == OWNER_DECISION_REQUIRED


# --- F: multiple conflicting policy matches -> OWNER_DECISION_REQUIRED,
# unless they agree on an identical target -----------------------------


def test_multiple_conflicting_policy_matches_require_owner_decision(catalog, policies):
    conflict_a = Policy(
        id="CONFLICT_A", description="t", path_patterns=("some/conflicting/*.py",),
        runtime_consumed=True, authority=False, eligible_target="layer.approvals",
        target_field="test_paths", auto_registration_allowed=True,
        classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE", notes=(),
    )
    conflict_b = Policy(
        id="CONFLICT_B", description="t", path_patterns=("some/conflicting/*.py",),
        runtime_consumed=True, authority=False, eligible_target="layer.turn_coordinator",
        target_field="test_paths", auto_registration_allowed=True,
        classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE", notes=(),
    )
    new_sources = _classify(catalog, ["some/conflicting/newfile.py"])
    result = _reconcile_with_fakes(catalog, (conflict_a, conflict_b), new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    assert result.decision_queue[0]["path"] == "some/conflicting/newfile.py"
    assert "policy_id" not in result.decision_queue[0]
    assert result.outcome == OWNER_DECISION_REQUIRED


def test_multiple_policy_matches_agreeing_on_identical_target_are_not_ambiguous(catalog, policies):
    agree_a = Policy(
        id="AGREE_A", description="t", path_patterns=("some/agree/*.py",),
        runtime_consumed=True, authority=False, eligible_target="layer.approvals",
        target_field="test_paths", auto_registration_allowed=True,
        classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE", notes=(),
    )
    agree_b = Policy(
        id="AGREE_B", description="t", path_patterns=("some/agree/*.py",),
        runtime_consumed=True, authority=False, eligible_target="layer.approvals",
        target_field="test_paths", auto_registration_allowed=True,
        classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE", notes=(),
    )
    new_sources = _classify(catalog, ["some/agree/newfile.py"])
    result = _reconcile_with_fakes(catalog, (agree_a, agree_b), new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 1
    assert result.auto_maintenance_sources[0]["policy_id"] == "AGREE_A"
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED


# --- G.5: known shared UI primitives follow approved policy (still queued) ---


def test_new_tma_ui_primitive_is_pre_labelled_with_policy_but_still_queued(catalog, policies):
    new_sources = _classify(catalog, ["tma-frontend/src/components/ui/NewPrimitive.tsx"])
    result = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    assert len(result.decision_queue) == 1
    item = result.decision_queue[0]
    assert item["policy_id"] == "SHARED_UI_PRIMITIVE"
    assert item["eligible_target"] == "decision.tma_shared_ui_primitives"
    assert item["target_field"] == "code_paths"
    assert result.outcome == OWNER_DECISION_REQUIRED


# --- G.4: known reference assets remain non-blocking ----------------------


def test_reference_evidence_image_stays_non_blocking(catalog, policies):
    new_sources = _classify(catalog, ["docs/ux/reference-evidence/newvendor/newvendor-home.png"])
    result = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert len(result.decision_queue) == 0
    assert len(result.non_blocking_sources) == 1
    assert result.outcome == CLEAN


# --- Staging-verification family split (correction item 4) ----------------


def test_staging_verification_approvals_bug_family_is_auto_maintenance_eligible(catalog, policies):
    new_sources = _classify(catalog, ["scripts/verify_bug161_162_callback_staging.py"])
    result = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert len(result.decision_queue) == 0
    assert len(result.auto_maintenance_sources) == 1
    item = result.auto_maintenance_sources[0]
    assert item["policy_id"] == "STAGING_VERIFICATION_APPROVALS_BUG_FAMILY"
    assert item["eligible_target"] == "layer.approvals"
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED


def test_unknown_staging_verification_family_has_no_catch_all(catalog, policies):
    new_sources = _classify(catalog, ["scripts/verify_brandnewthing_staging.py"])
    result = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    assert len(result.decision_queue) == 1
    assert "policy_id" not in result.decision_queue[0]
    assert result.outcome == OWNER_DECISION_REQUIRED


# --- G.8: previously resolved classification does not reappear ------------


def test_registered_path_never_reappears_as_new_source(catalog, policies):
    registered_path = None
    for node in catalog.nodes.values():
        if node["code_paths"]:
            registered_path = node["code_paths"]
            break
    assert registered_path, "expected at least one registered code_path in the real catalog"
    new_sources = _classify(catalog, [registered_path[0]])
    assert new_sources == []


# --- G.9 / G (workflow safety, idempotency, permission split) -------------


def test_reconcile_workflow_never_pushes_to_main():
    workflow = REPO_ROOT / ".github/workflows/context-librarian-reconcile.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "push origin main" not in text
    assert "push origin HEAD:main" not in text
    assert "git push origin \"$branch\"" in text or "git push origin ${branch}" in text
    assert "gh pr create" in text
    assert "--base main" in text


def test_workflow_has_idempotency_guard_and_split_permissions():
    workflow = REPO_ROOT / ".github/workflows/context-librarian-reconcile.yml"
    text = workflow.read_text(encoding="utf-8")
    # G: second run for the same SHA must not create a duplicate branch/PR.
    assert "ls-remote --exit-code --heads origin" in text
    assert "gh pr list --head" in text
    assert "concurrency:" in text
    # item 6: workflow-level permissions default to read-only; only the
    # conditional, need-gated prepare-maintenance-pr job escalates to write.
    assert "permissions:\n  contents: read" in text
    assert "      contents: write" in text
    assert "persist-credentials: false" in text
    assert "needs.check.outputs.outcome == 'AUTO_MAINTENANCE_REQUIRED'" in text


# --- H / I: automation never writes semantic-review provenance ------------


def test_last_semantic_review_commit_never_written_by_reconcile_module():
    source = Path(reconcile_module.__file__).read_text(encoding="utf-8")
    assert 'raw_node["last_semantic_review_commit"]' not in source


def test_last_verified_commit_never_written_by_reconcile_module():
    source = Path(reconcile_module.__file__).read_text(encoding="utf-8")
    assert 'raw_node["last_verified_commit"]' not in source


# --- G.2: mechanical provenance advances automatically (stamp_observed) ---


def test_stamp_observed_advances_last_observed_without_touching_semantic_fields(
    catalog, monkeypatch, tmp_path
):
    isolated = _isolated_catalog(monkeypatch, tmp_path)

    sha = "1234567"
    monkeypatch.setattr(
        reconcile_module, "_current_branch_and_commit", lambda _root: ("main", sha)
    )
    before = {nid: n["last_verified_commit"] for nid, n in isolated.nodes.items()}
    written = stamp_observed(isolated, sha)
    assert written  # at least one node stamped

    reloaded = load_catalog(REPO_ROOT)
    for node_id in written:
        assert reloaded.nodes[node_id]["last_observed_commit"] == sha
        # last_verified_commit is untouched -- semantic review stays manual.
        assert reloaded.nodes[node_id]["last_verified_commit"] == before[node_id]

    # Idempotent across separate invocations (the real CLI loads a fresh
    # catalog per process -- stamp_observed's idempotency check reads
    # last_observed_commit off whatever catalog object it's handed, so the
    # guarantee is exercised the same way a second `--apply-observed` run
    # would see it: reload from the now-updated files, then call again.
    assert stamp_observed(load_catalog(REPO_ROOT), sha) == []


def test_stamp_observed_refuses_off_main_or_wrong_sha(catalog, monkeypatch):
    monkeypatch.setattr(
        reconcile_module, "_current_branch_and_commit", lambda _root: ("feature-x", "abc1234")
    )
    with pytest.raises(Exception):
        stamp_observed(catalog, "abc1234")


# --- Outcome state machine sanity -----------------------------------------


def test_outcome_clean_when_nothing_pending(catalog, policies):
    result = _reconcile_with_fakes(catalog, policies)
    assert result.outcome == CLEAN


def test_outcome_auto_maintenance_when_only_mechanical_updates_pending(catalog, policies):
    result = _reconcile_with_fakes(
        catalog, policies,
        mechanical_updates=[{"node_id": "layer.marketing", "from": "a", "to": "b", "changed_paths": ["x.py"]}],
    )
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED


def test_outcome_owner_decision_overrides_auto_maintenance(catalog, policies):
    new_sources = _classify(catalog, ["totally_unmatched_new_thing.py"])
    result = _reconcile_with_fakes(
        catalog, policies,
        new_sources=new_sources,
        mechanical_updates=[{"node_id": "layer.marketing", "from": "a", "to": "b", "changed_paths": ["x.py"]}],
    )
    assert result.outcome == OWNER_DECISION_REQUIRED


# --- G.10: repeated reconcile on unchanged input is idempotent ------------


def test_reconcile_is_idempotent_on_unchanged_input(catalog, policies):
    new_sources = _classify(
        catalog,
        [
            "business_tool_registry.py",
            "docs/ux/reference-evidence/x/y.png",
            "totally_unmatched_new_thing.py",
        ],
    )
    first = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    second = _reconcile_with_fakes(catalog, policies, new_sources=new_sources)
    assert first.to_json() == second.to_json()


def test_scan_new_sources_baseline_already_at_target_sha_finds_nothing(catalog, monkeypatch):
    monkeypatch.setattr(
        reconcile_module, "load_reconciliation_state",
        lambda _catalog_root: {"last_source_scan_commit": "samesha0000000000000000000000000000000000"},
    )
    result = reconcile_module._scan_new_sources(catalog, "samesha0000000000000000000000000000000000", "origin/main")
    assert result == []
