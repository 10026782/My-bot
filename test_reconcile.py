"""Tests for tools/context_librarian/reconcile.py and policy_registry.py.

Covers the 10 required scenarios for the three-outcome reconciliation engine
(CLEAN / AUTO_MAINTENANCE_REQUIRED / OWNER_DECISION_REQUIRED) plus the
Message D correction's required end-to-end coverage (A-I below) -- see
docs/context_librarian/RECONCILIATION.md.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from tools.context_librarian import policy_validators
from tools.context_librarian import reconcile as reconcile_module
from tools.context_librarian.librarian import Catalog, ContextLibrarianError, classify_new_sources, load_catalog
from tools.context_librarian.policy_registry import Policy, load_policy_registry, match_policy
from tools.context_librarian.reconcile import (
    AUTO_MAINTENANCE_REQUIRED,
    CLEAN,
    OWNER_DECISION_REQUIRED,
    apply_auto_maintenance,
    reconcile,
    stamp_observed,
)
from tools.context_librarian.reconciliation_state import load_reconciliation_state, update_auto_registrations


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


# A real, already-unregistered-on-main file used across the revalidation
# (Message E) tests below -- its real content genuinely satisfies
# STAGING_VERIFICATION_APPROVALS_BUG_FAMILY's predicate (has a __main__
# entrypoint, never referenced by tools/dispatcher.py or app.py), so tests
# that don't deliberately fake the predicate result exercise the real
# validator against real content, not a mock of it.
_SEED_PATH = "scripts/verify_bug157_160_163_staging.py"
_SEED_NODE = "layer.approvals"
_SEED_FIELD = "test_paths"
_SEED_POLICY_ID = "STAGING_VERIFICATION_APPROVALS_BUG_FAMILY"


def _seed_registration(monkeypatch, tmp_path, *, entry, node_id=_SEED_NODE, field=_SEED_FIELD, path=_SEED_PATH):
    """Builds an isolated catalog (real repo_root, tmp catalog_root) where
    `path` is already present in `node_id`'s `field`, with a matching
    auto_registrations provenance entry in the isolated reconciliation_state.json
    -- simulating "a previous cycle already auto-registered this path"
    without ever writing to the real repo's catalog files."""
    isolated = _isolated_catalog(monkeypatch, tmp_path)
    files = reconcile_module._catalog_node_files(isolated)
    file_path = files[node_id]
    data = json.loads(file_path.read_text(encoding="utf-8"))
    for node in data["nodes"]:
        if node["id"] == node_id and path not in node[field]:
            node[field].append(path)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_auto_registrations(isolated.catalog_root, {path: entry})
    return load_catalog(REPO_ROOT)


def _real_content_hash(path=_SEED_PATH):
    return reconcile_module._content_hash(REPO_ROOT / path)


# --- Policy registry basics ---------------------------------------------


def test_policy_registry_loads_all_eleven_policies(policies):
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
        "EXTERNAL_EXECUTION_RUNTIME",
    }


def test_policy_matching_is_glob_only_not_substring(policies):
    # "evidence" is nowhere in this path as a directory/keyword hit the old
    # substring-based STOP escalation would have cared about -- it must not
    # match DOCUMENTATION_REFERENCE_ASSET via substring coincidence either.
    assert match_policy("core/authority_evidence_tracker.py", policies) is None
    # A real match: exact glob against the declared pattern.
    assert match_policy("scripts/verify_f15_staging.py", policies).id == "STAGING_VERIFICATION_F15"
    assert match_policy("core/external_poll_lease.py", policies).id == "EXTERNAL_EXECUTION_RUNTIME"


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

    applied = apply_auto_maintenance(isolated, policies, first)
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
        apply_auto_maintenance(catalog, policies, clean_result)


def test_apply_auto_maintenance_requires_head_at_canonical_sha(catalog, policies, monkeypatch):
    result = _reconcile_with_fakes(
        catalog, policies,
        mechanical_updates=[{"node_id": "layer.marketing", "from": "a", "to": "deadbee00000000000000000000000000000000", "changed_paths": ["x.py"]}],
    )
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED
    monkeypatch.setattr(reconcile_module, "_current_branch_and_commit", lambda _root: ("main", "wrong-sha"))
    with pytest.raises(ContextLibrarianError):
        apply_auto_maintenance(catalog, policies, result)


# --- B: policy-approved new source -> AUTO -> apply-auto -> registered into
# the correct target_field -> reload -> CLEAN -------------------------------


def test_policy_approved_new_source_registers_and_reconciles_clean(catalog, policies, monkeypatch, tmp_path):
    # scripts/verify_bug157_160_163_staging.py -- this test's original
    # example -- was registered for real by PR #628 (a prerequisite this
    # branch rebases onto, see docs/context_librarian/RECONCILIATION.md), so
    # it is no longer a real "new source". Use
    # scripts/research_crawler_poc/reconcile_test_fixture.py instead: a real,
    # permanent, deliberately-unregistered fixture file kept for exactly this
    # test (same precedent as tc8_test_repo_stub.py), so this stays a genuine
    # real-file, real-classification, real-predicate end-to-end proof instead
    # of depending on which repository registration gaps happen to still be
    # open.
    #
    # Classification against the real (module-scoped) catalog fixture --
    # _catalog_referenced_paths() resolves paths relative to catalog.repo_root,
    # which only holds for the real repo layout, not an isolated tmp copy
    # whose catalog_root lives outside repo_root.
    fixture_path = "scripts/research_crawler_poc/reconcile_test_fixture.py"
    assert fixture_path not in catalog.nodes["decision.offline_research_support_tool"]["code_paths"]
    new_sources = classify_new_sources(catalog, [fixture_path])

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
    assert first.auto_maintenance_sources[0]["policy_id"] == "OFFLINE_RESEARCH_TOOL"
    assert first.auto_maintenance_sources[0]["target_field"] == "code_paths"

    applied = apply_auto_maintenance(isolated, policies, first)
    assert f"decision.offline_research_support_tool.code_paths:{fixture_path}" in applied["registered"]

    reloaded = load_catalog(REPO_ROOT)
    assert fixture_path in reloaded.nodes["decision.offline_research_support_tool"]["code_paths"]

    monkeypatch.setattr(reconcile_module, "_scan_new_sources", lambda *_a, **_k: [])
    second = reconcile(reloaded, policies, main_ref="origin/main")
    assert second.outcome == CLEAN


def test_new_registration_node_gets_observed_commit_stamped_even_when_another_node_also_drifts(
    catalog, policies, monkeypatch, tmp_path
):
    """Regression for the production incident where the post-merge
    "Context Librarian Reconciliation" workflow stayed red on every single
    push to main: apply_auto_maintenance() used to compute drifted_node_ids
    (the set of nodes to stamp last_observed_commit for) from
    result.mechanical_updates BEFORE performing new-source registration. A
    node receiving its first-ever registration this run was therefore never
    included in that stamp -- unless drifted_node_ids happened to be empty,
    in which case the writer's None-means-"stamp every node" fallback
    accidentally covered it too, masking the bug in
    test_policy_approved_new_source_registers_and_reconciles_clean above
    (whose _mechanical_drift() mock always returns []).

    In production, OTHER real nodes genuinely had mechanical drift in the
    same run, so drifted_node_ids was a concrete non-None list that did not
    include the newly-registered node -- and the very next reconcile() (the
    CLI's own in-process post-apply verification, and every subsequent CI
    run thereafter, since last_source_scan_commit had already advanced past
    the file) kept finding "drift" for it forever, because its
    last_observed_commit baseline was never advanced. This test reproduces
    that exact combination: a real drifted node AND a real new registration
    in the same apply_auto_maintenance() call."""
    fixture_path = "scripts/research_crawler_poc/reconcile_test_fixture.py"
    assert fixture_path not in catalog.nodes["decision.offline_research_support_tool"]["code_paths"]
    new_sources = classify_new_sources(catalog, [fixture_path])

    isolated = _isolated_catalog(monkeypatch, tmp_path)
    main_sha = "d4e5f6070800000000000000000000000000000"
    other_node_id = next(
        n["id"]
        for n in isolated.nodes.values()
        if n["id"] != "decision.offline_research_support_tool" and n["code_paths"]
    )
    other_node_changed_path = isolated.nodes[other_node_id]["code_paths"][0]

    # Fake only the innermost git-shelling seam, not _mechanical_drift
    # itself -- this keeps the REAL per-node baseline/tracked-paths loop
    # running (for every node in the catalog, both reconcile() calls),
    # exactly like the CLI's real in-process post-apply verification does,
    # without ever needing a real git commit for the fake main_sha: any
    # node already stamped at main_sha hits base==target and never reaches
    # this fake at all.
    def fake_changed_paths(_repo_root, base, target):
        if base == target:
            return set()
        return {other_node_changed_path}

    monkeypatch.setattr(reconcile_module, "_resolve_main_sha", lambda *_a, **_k: main_sha)
    monkeypatch.setattr(reconcile_module, "_changed_paths_between", fake_changed_paths)
    monkeypatch.setattr(reconcile_module, "_scan_new_sources", lambda *_a, **_k: new_sources)
    monkeypatch.setattr(reconcile_module, "_current_branch_and_commit", lambda _root: ("main", main_sha))
    monkeypatch.setattr(reconcile_module, "_working_tree_is_clean", lambda _root: True)

    first = reconcile(isolated, policies, main_ref="origin/main")
    assert first.outcome == AUTO_MAINTENANCE_REQUIRED
    drifted_ids = [u["node_id"] for u in first.mechanical_updates]
    # drifted_node_ids is a concrete, non-empty list that does NOT include
    # the about-to-be-registered node -- the exact condition that used to
    # defeat the writer's None-means-everyone fallback (some other node's
    # tracked globs incidentally also matching the fake changed path is
    # fine and realistic; what matters is the registration target is absent).
    assert other_node_id in drifted_ids
    assert "decision.offline_research_support_tool" not in drifted_ids
    assert len(first.auto_maintenance_sources) == 1

    applied = apply_auto_maintenance(isolated, policies, first)
    assert other_node_id in applied["stamped_nodes"]
    assert "decision.offline_research_support_tool" in applied["stamped_nodes"], (
        "the newly-registered node's last_observed_commit must be stamped in "
        "the same apply, or it re-enters mechanical_updates on the very next "
        "reconcile() forever"
    )

    reloaded = load_catalog(REPO_ROOT)
    assert reloaded.nodes["decision.offline_research_support_tool"]["last_observed_commit"] == main_sha
    assert fixture_path in reloaded.nodes["decision.offline_research_support_tool"]["code_paths"]

    # _mechanical_drift itself was never mocked -- only its git-shelling
    # seam -- so this post-apply verification exercises the real per-node
    # baseline loop for every node in the catalog, exactly like the CLI's
    # in-process post-apply verification. Both stamped nodes now have
    # last_observed_commit == main_sha, so this must come back CLEAN.
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
        apply_auto_maintenance(catalog, policies, result)


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
        id="CATCH_ALL_TEST_ONLY", policy_version=1, description="test-only", path_patterns=("*",),
        runtime_consumed=True, authority=False, eligible_target=None, target_field=None,
        auto_registration_allowed=True, classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE",
        notes=(),
    )
    result_with_catch_all = _reconcile_with_fakes(catalog, (catch_all,), new_sources=new_sources)
    assert len(result_with_catch_all.auto_maintenance_sources) == 0
    assert result_with_catch_all.outcome == OWNER_DECISION_REQUIRED


# --- E: policy match with a target that does not exist -> OWNER_DECISION_REQUIRED ---


def _with_missing_target(policies, policy_id):
    """Returns a copy of `policies` with `policy_id`'s eligible_target
    redirected to a guaranteed-nonexistent node id, keeping everything else
    (id, real path_patterns, real target_field) intact. Used to prove the
    "target must exist" gate deterministically instead of depending on
    which real catalog decision nodes happen to not exist yet -- PR #628
    (a prerequisite this branch rebases onto) already created the specific
    real target nodes this test originally relied on being absent."""
    real_policy = next(p for p in policies if p.id == policy_id)
    missing_target_policy = dataclasses.replace(
        real_policy, eligible_target="decision.__nonexistent_test_target__"
    )
    return tuple(missing_target_policy if p.id == policy_id else p for p in policies)


def test_policy_match_with_nonexistent_target_requires_owner_decision(catalog, policies):
    # decision.business_domain_vocabulary now exists for real (PR #628), and
    # domain_utils.py is registered under it, so it's no longer a real "new
    # source" either -- hand-build the classification item to still exercise
    # CROSS_LAYER_SUPPORTING_METADATA's real glob match, against a policy
    # copy whose target is synthetically forced missing (see
    # _with_missing_target).
    assert "decision.business_domain_vocabulary" in catalog.nodes
    patched_policies = _with_missing_target(policies, "CROSS_LAYER_SUPPORTING_METADATA")
    new_sources = [
        {"path": "domain_utils.py", "classification": "REVIEW_REQUIRED", "reason": "new runtime source"}
    ]
    result = _reconcile_with_fakes(catalog, patched_policies, new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    assert len(result.decision_queue) == 1
    item = result.decision_queue[0]
    assert item["policy_id"] == "CROSS_LAYER_SUPPORTING_METADATA"
    assert "does not exist" in item["policy_note"]
    assert result.outcome == OWNER_DECISION_REQUIRED


def test_staging_verification_f15_requires_target_to_exist(catalog, policies):
    # decision.f15_staging_verification_artifact now exists for real (PR
    # #628, a prerequisite this branch rebases onto), and
    # scripts/verify_f15_staging.py is registered under it -- see
    # test_policy_match_with_nonexistent_target_requires_owner_decision
    # above for why this uses a hand-built classification item and a
    # synthetically target-missing policy copy instead.
    assert "decision.f15_staging_verification_artifact" in catalog.nodes
    patched_policies = _with_missing_target(policies, "STAGING_VERIFICATION_F15")
    new_sources = [
        {
            "path": "scripts/verify_f15_staging.py",
            "classification": "REVIEW_REQUIRED",
            "reason": "new runtime source",
        }
    ]
    result = _reconcile_with_fakes(catalog, patched_policies, new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    item = result.decision_queue[0]
    assert item["policy_id"] == "STAGING_VERIFICATION_F15"
    assert "does not exist" in item["policy_note"]
    assert result.outcome == OWNER_DECISION_REQUIRED


# --- F: multiple conflicting policy matches -> OWNER_DECISION_REQUIRED,
# unless they agree on an identical target -----------------------------


def test_multiple_conflicting_policy_matches_require_owner_decision(catalog, policies):
    conflict_a = Policy(
        id="CONFLICT_A", policy_version=1, description="t", path_patterns=("some/conflicting/*.py",),
        runtime_consumed=True, authority=False, eligible_target="layer.approvals",
        target_field="test_paths", auto_registration_allowed=True,
        classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE", notes=(),
    )
    conflict_b = Policy(
        id="CONFLICT_B", policy_version=1, description="t", path_patterns=("some/conflicting/*.py",),
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


def test_multiple_policy_matches_agreeing_on_identical_target_are_not_ambiguous(
    catalog, policies, monkeypatch
):
    agree_a = Policy(
        id="AGREE_A", policy_version=1, description="t", path_patterns=("some/agree/*.py",),
        runtime_consumed=True, authority=False, eligible_target="layer.approvals",
        target_field="test_paths", auto_registration_allowed=True,
        classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE", notes=(),
    )
    agree_b = Policy(
        id="AGREE_B", policy_version=1, description="t", path_patterns=("some/agree/*.py",),
        runtime_consumed=True, authority=False, eligible_target="layer.approvals",
        target_field="test_paths", auto_registration_allowed=True,
        classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE", notes=(),
    )
    # A synthetic predicate for this test-only policy id -- reconcile()'s
    # fail-closed predicate gate (item 1/6) requires one for any policy with
    # auto_registration_allowed=True, same as the real registry loader does.
    monkeypatch.setitem(reconcile_module.policy_validators.VALIDATORS, "AGREE_A", lambda *_a: True)
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
    # scripts/verify_bug161_162_callback_staging.py was registered for real
    # by PR #628 (a prerequisite this branch rebases onto), so it is no
    # longer a real "new source" via classify_new_sources -- hand-build the
    # classification item to still exercise this policy's real glob match
    # and real predicate against the file's real (unchanged) content.
    new_sources = [
        {
            "path": "scripts/verify_bug161_162_callback_staging.py",
            "classification": "REVIEW_REQUIRED",
            "reason": "new runtime source",
        }
    ]
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


# --- Follow-up correction: crash-recovery idempotency (branch pushed but --

def test_workflow_run_blocks_have_consistent_indentation():
    """Every `run: |` block scalar's content indentation is fixed by its
    first non-blank line: a later line that is more indented than the
    `run:` key itself but less indented than that first content line
    invalidates the block under the YAML spec -- confirmed with PyYAML when
    this exact bug (a flush-left python heredoc body embedded in an
    indented `run: |` block) broke this workflow, even though it looked
    fine to a human skim. This repo has no PyYAML dependency (grepped: no
    other file imports it, not in requirements.txt), so this reimplements
    the one structural rule that bit us rather than doing full YAML
    parsing or adding a dependency for one test."""
    workflow = REPO_ROOT / ".github/workflows/context-librarian-reconcile.yml"
    lines = workflow.read_text(encoding="utf-8").splitlines()
    # A line at or below the run: key's own indentation only legitimately
    # ends the block scalar if it is itself a new YAML mapping key or
    # sequence item (e.g. the next "- name: ..." step) -- anything else at
    # that indentation (like a heredoc body's "import json" at column 0) is
    # leftover block content that dedented too far, which is exactly the
    # real bug this test caught (PyYAML raised "could not find expected
    # ':'" on the next line for that exact reason).
    new_yaml_entry = re.compile(r"^-\s|^[A-Za-z_][\w.-]*\s*:")
    checked_any = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == "run: |" or stripped.startswith("run: |"):
            run_indent = len(lines[i]) - len(lines[i].lstrip(" "))
            content_indent = None
            j = i + 1
            while j < len(lines):
                candidate = lines[j]
                if candidate.strip() == "":
                    j += 1
                    continue
                indent = len(candidate) - len(candidate.lstrip(" "))
                if indent <= run_indent and new_yaml_entry.match(candidate.strip()):
                    break  # block scalar genuinely ended here
                if content_indent is None:
                    content_indent = indent
                assert indent >= content_indent, (
                    f"line {j + 1} ({candidate!r}) is indented less than this "
                    f"run: | block's established content indentation "
                    f"({content_indent} spaces) -- invalid YAML block scalar"
                )
                j += 1
            checked_any = True
            i = j
            continue
        i += 1
    assert checked_any, "expected at least one 'run: |' block in this workflow"


def test_workflow_distinguishes_four_crash_recovery_cases():
    """PR that failed before gh pr create is not the same as a fully
    handled SHA -- 'branch exists' alone must not collapse into a single
    skip=true, per the AGENT 1 'FINAL TWO FIXES' correction."""
    workflow = REPO_ROOT / ".github/workflows/context-librarian-reconcile.yml"
    text = workflow.read_text(encoding="utf-8")
    for case in ("absent", "complete", "missing_pr", "unprovable"):
        assert f"case == '{case}'" in text

    # case 3 (missing_pr): recovers by creating only the missing PR, must
    # never re-create the branch or re-run apply-auto.
    missing_pr_step = text.split("case == 'missing_pr'")[1].split("- name:")[0]
    assert "gh pr create" in missing_pr_step
    assert "checkout -b" not in missing_pr_step
    assert "apply-auto" not in missing_pr_step
    assert "git push" not in missing_pr_step

    # case 4 (unprovable): fails closed, never mutates the branch.
    unprovable_step = text.split("case == 'unprovable'")[1].split("- name:")[0]
    assert "exit 1" in unprovable_step
    assert "git push" not in unprovable_step
    assert "checkout -b" not in unprovable_step
    assert "git push --force" not in unprovable_step

    # case 2 (complete): pure no-op, no mutating commands at all.
    complete_step = text.split("case == 'complete'")[1].split("- name:")[0]
    assert "gh pr create" not in complete_step
    assert "git push" not in complete_step


def test_workflow_branch_provenance_check_proves_single_bot_commit_on_canonical_sha():
    """The 'unprovable' classification must be driven by an actual proof --
    exactly one commit ahead of the canonical SHA, authored by the bot
    identity used elsewhere in this same workflow -- not just branch-name
    pattern matching, which an attacker or unrelated branch could satisfy."""
    workflow = REPO_ROOT / ".github/workflows/context-librarian-reconcile.yml"
    text = workflow.read_text(encoding="utf-8")
    assert 'rev-list --count "${sha}..${head_sha}"' in text
    assert 'rev-parse "${head_sha}^"' in text
    assert "context-librarian-bot@users.noreply.github.com" in text


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


# =====================================================================
# Message E correction: continuous revalidation of already-auto-registered
# paths (items 1-8) -- required tests A-H.
# =====================================================================


def _revalidate_only(catalog, policies, main_sha="deadbee00000000000000000000000000000000"):
    """Runs reconcile() with mechanical drift and new-source scanning both
    faked to empty, isolating the revalidation pass (_scan_auto_registrations)
    as the only thing that can produce a non-CLEAN outcome."""
    return _reconcile_with_fakes(catalog, policies, main_sha=main_sha)


# --- A: AUTO-registered file under Policy V1 -> reload -> unchanged file remains valid ---


def test_A_unchanged_registered_file_remains_valid(monkeypatch, tmp_path, policies):
    entry = {
        "policy_id": _SEED_POLICY_ID,
        "policy_version": 1,
        "target_node": _SEED_NODE,
        "target_field": _SEED_FIELD,
        "validated_at_commit": "priorsha0000000000000000000000000000000",
        "content_hash": _real_content_hash(),
        "validator_version": policy_validators.VALIDATOR_VERSION,
        "classification_mode": "AUTO",
    }
    isolated = _seed_registration(monkeypatch, tmp_path, entry=entry)
    result = _revalidate_only(isolated, policies)
    assert result.revalidation_flags == ()
    assert result.outcome == CLEAN

    # Reload -- a second, entirely separate cycle sees the same thing.
    reloaded = load_catalog(REPO_ROOT)
    result_2 = _revalidate_only(reloaded, policies)
    assert result_2.outcome == CLEAN


# --- B: modify the file but stay within V1 predicates -> automatic revalidation PASS ---


def test_B_changed_content_still_satisfying_predicate_auto_refreshes(monkeypatch, tmp_path, policies):
    entry = {
        "policy_id": _SEED_POLICY_ID,
        "policy_version": 1,
        "target_node": _SEED_NODE,
        "target_field": _SEED_FIELD,
        # Deliberately stale/wrong hash -- simulates "the file changed since
        # this was registered" without actually touching the real file.
        "validated_at_commit": "priorsha0000000000000000000000000000000",
        "content_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        "validator_version": policy_validators.VALIDATOR_VERSION,
        "classification_mode": "AUTO",
    }
    isolated = _seed_registration(monkeypatch, tmp_path, entry=entry)
    main_sha = "b000000000000000000000000000000000000000"
    result = _revalidate_only(isolated, policies, main_sha=main_sha)
    assert result.revalidation_flags == ()  # predicate still passes on real content
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED

    monkeypatch.setattr(reconcile_module, "_current_branch_and_commit", lambda _root: ("main", main_sha))
    monkeypatch.setattr(reconcile_module, "_working_tree_is_clean", lambda _root: True)
    applied = apply_auto_maintenance(isolated, policies, result)
    assert _SEED_PATH in applied["provenance_refreshed"]

    reloaded_state = load_reconciliation_state(isolated.catalog_root)
    refreshed_entry = reloaded_state["auto_registrations"][_SEED_PATH]
    assert refreshed_entry["content_hash"] == _real_content_hash()
    assert refreshed_entry["validated_at_commit"] == main_sha

    # Next cycle: content_hash now matches -> CLEAN.
    reloaded = load_catalog(REPO_ROOT)
    result_2 = _revalidate_only(reloaded, policies, main_sha=main_sha)
    assert result_2.outcome == CLEAN


# --- C: modify content so one required predicate fails -> OWNER_DECISION_REQUIRED ---


def test_C_predicate_failure_forces_owner_decision_and_blocks_apply_auto(
    monkeypatch, tmp_path, policies
):
    entry = {
        "policy_id": _SEED_POLICY_ID,
        "policy_version": 1,
        "target_node": _SEED_NODE,
        "target_field": _SEED_FIELD,
        "validated_at_commit": "priorsha0000000000000000000000000000000",
        "content_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        "validator_version": policy_validators.VALIDATOR_VERSION,
        "classification_mode": "AUTO",
    }
    isolated = _seed_registration(monkeypatch, tmp_path, entry=entry)
    # Simulate the file having changed in a way that now trips the
    # predicate -- e.g. it got wired into the live dispatcher.
    monkeypatch.setitem(policy_validators.VALIDATORS, _SEED_POLICY_ID, lambda *_a: False)

    result = _revalidate_only(isolated, policies)
    assert len(result.revalidation_flags) == 1
    flag = result.revalidation_flags[0]
    assert flag["path"] == _SEED_PATH
    assert flag["status"] == "STALE_REVALIDATION_REQUIRED"
    assert flag["previous_policy"] == _SEED_POLICY_ID
    assert flag["failed_predicate"] == "structural/content predicate failed"
    assert result.outcome == OWNER_DECISION_REQUIRED

    with pytest.raises(ContextLibrarianError):
        apply_auto_maintenance(isolated, policies, result)

    # Quarantine, not deletion: the path is still registered in the node.
    assert _SEED_PATH in isolated.nodes[_SEED_NODE][_SEED_FIELD]


# --- D: Policy V1 -> V2 -> every V1-classified source is revalidated ---


def test_D_policy_version_bump_revalidates_every_historical_match(monkeypatch, tmp_path, policies):
    entry = {
        "policy_id": _SEED_POLICY_ID,
        "policy_version": 1,
        "target_node": _SEED_NODE,
        "target_field": _SEED_FIELD,
        "validated_at_commit": "priorsha0000000000000000000000000000000",
        "content_hash": _real_content_hash(),
        "validator_version": policy_validators.VALIDATOR_VERSION,
        "classification_mode": "AUTO",
    }
    isolated = _seed_registration(monkeypatch, tmp_path, entry=entry)
    bumped = next(p for p in policies if p.id == _SEED_POLICY_ID)
    bumped_v2 = Policy(
        id=bumped.id, policy_version=2, description=bumped.description,
        path_patterns=bumped.path_patterns, runtime_consumed=bumped.runtime_consumed,
        authority=bumped.authority, eligible_target=bumped.eligible_target,
        target_field=bumped.target_field, auto_registration_allowed=bumped.auto_registration_allowed,
        classification_when_matched=bumped.classification_when_matched, notes=bumped.notes,
    )
    # content_hash is unchanged -- only the policy_version differs -- and the
    # revalidation pass must still trigger, proving POLICY CHANGE REVALIDATES
    # HISTORY rather than only applying V2 to future matches.
    result = _revalidate_only(isolated, (bumped_v2,))
    assert result.revalidation_flags == ()
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED

    monkeypatch.setattr(
        reconcile_module, "_current_branch_and_commit", lambda _root: ("main", result.canonical_main_sha)
    )
    monkeypatch.setattr(reconcile_module, "_working_tree_is_clean", lambda _root: True)
    applied = apply_auto_maintenance(isolated, (bumped_v2,), result)
    assert _SEED_PATH in applied["provenance_refreshed"]
    reloaded_state = load_reconciliation_state(isolated.catalog_root)
    assert reloaded_state["auto_registrations"][_SEED_PATH]["policy_version"] == 2


# --- E: one historical V1 source fails V2 -> surfaced, not silently grandfathered ---


def test_E_historical_source_failing_new_policy_version_is_surfaced(monkeypatch, tmp_path, policies):
    entry = {
        "policy_id": _SEED_POLICY_ID,
        "policy_version": 1,
        "target_node": _SEED_NODE,
        "target_field": _SEED_FIELD,
        "validated_at_commit": "priorsha0000000000000000000000000000000",
        "content_hash": _real_content_hash(),
        "validator_version": policy_validators.VALIDATOR_VERSION,
        "classification_mode": "AUTO",
    }
    isolated = _seed_registration(monkeypatch, tmp_path, entry=entry)
    bumped = next(p for p in policies if p.id == _SEED_POLICY_ID)
    bumped_v2 = Policy(
        id=bumped.id, policy_version=2, description=bumped.description,
        path_patterns=bumped.path_patterns, runtime_consumed=bumped.runtime_consumed,
        authority=bumped.authority, eligible_target=bumped.eligible_target,
        target_field=bumped.target_field, auto_registration_allowed=bumped.auto_registration_allowed,
        classification_when_matched=bumped.classification_when_matched, notes=bumped.notes,
    )
    # V2's predicate is stricter and this historical source no longer meets it.
    monkeypatch.setitem(policy_validators.VALIDATORS, _SEED_POLICY_ID, lambda *_a: False)

    result = _revalidate_only(isolated, (bumped_v2,))
    assert len(result.revalidation_flags) == 1
    flag = result.revalidation_flags[0]
    assert flag["policy_version_then"] == 1
    assert flag["policy_version_now"] == 2
    assert result.outcome == OWNER_DECISION_REQUIRED
    with pytest.raises(ContextLibrarianError):
        apply_auto_maintenance(isolated, (bumped_v2,), result)


# --- F: registered path never reappears as "new", but DOES revalidate -----


def test_F_registered_path_excluded_from_new_sources_but_still_revalidated(
    monkeypatch, tmp_path, policies
):
    entry = {
        "policy_id": _SEED_POLICY_ID,
        "policy_version": 1,
        "target_node": _SEED_NODE,
        "target_field": _SEED_FIELD,
        "validated_at_commit": "priorsha0000000000000000000000000000000",
        "content_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        "validator_version": policy_validators.VALIDATOR_VERSION,
        "classification_mode": "AUTO",
    }
    isolated = _seed_registration(monkeypatch, tmp_path, entry=entry)
    # Structurally, "not new" means "already present in some node's
    # code_paths/test_paths" -- classify_new_sources()'s exclusion set is
    # built from exactly this (see test_registered_path_never_reappears_as_new_source
    # for the direct classify_new_sources() proof on the real, un-isolated
    # catalog; isolated catalog_root/repo_root are decoupled by design in
    # this test file's isolation helper, which classify_new_sources()'s own
    # infra-path resolution isn't compatible with).
    assert _SEED_PATH in isolated.nodes[_SEED_NODE][_SEED_FIELD]

    result = _revalidate_only(isolated, policies)
    # Not in decision_queue (that's for NEW sources) -- but the stale hash
    # still drove a real revalidation outcome (AUTO_MAINTENANCE_REQUIRED,
    # since the real predicate still passes on real content).
    assert all(item["path"] != _SEED_PATH for item in result.decision_queue)
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED


# --- G: last_semantic_review_commit byte-identical before/after automatic runs ---


def test_G_last_semantic_review_commit_untouched_by_any_automatic_run(monkeypatch, tmp_path, policies):
    entry = {
        "policy_id": _SEED_POLICY_ID,
        "policy_version": 1,
        "target_node": _SEED_NODE,
        "target_field": _SEED_FIELD,
        "validated_at_commit": "priorsha0000000000000000000000000000000",
        "content_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        "validator_version": policy_validators.VALIDATOR_VERSION,
        "classification_mode": "AUTO",
    }
    isolated = _seed_registration(monkeypatch, tmp_path, entry=entry)

    # Hand-inject a human semantic review marker on the target node, exactly
    # as an owner would when registering/re-confirming a decision.
    files = reconcile_module._catalog_node_files(isolated)
    file_path = files[_SEED_NODE]
    data = json.loads(file_path.read_text(encoding="utf-8"))
    marker = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # valid commit_pattern hex, human-review marker
    for node in data["nodes"]:
        if node["id"] == _SEED_NODE:
            node["last_semantic_review_commit"] = marker
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    isolated = load_catalog(REPO_ROOT)
    assert isolated.nodes[_SEED_NODE]["last_semantic_review_commit"] == marker

    main_sha = "6000000000000000000000000000000000000006"
    monkeypatch.setattr(reconcile_module, "_current_branch_and_commit", lambda _root: ("main", main_sha))
    monkeypatch.setattr(reconcile_module, "_working_tree_is_clean", lambda _root: True)
    result = _revalidate_only(isolated, policies, main_sha=main_sha)
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED

    apply_auto_maintenance(isolated, policies, result)
    reloaded = load_catalog(REPO_ROOT)
    assert reloaded.nodes[_SEED_NODE]["last_semantic_review_commit"] == marker

    stamp_observed(reloaded, main_sha)
    reloaded_again = load_catalog(REPO_ROOT)
    assert reloaded_again.nodes[_SEED_NODE]["last_semantic_review_commit"] == marker


# --- H: a mistaken broad glob cannot override a failed structural predicate ---


def test_H_broad_glob_cannot_override_failed_structural_predicate(catalog, policies, monkeypatch):
    broad = Policy(
        id="BROAD_GLOB_TEST_ONLY", policy_version=1, description="deliberately over-broad",
        path_patterns=("*",), runtime_consumed=True, authority=False,
        eligible_target="layer.approvals", target_field="test_paths",
        auto_registration_allowed=True, classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE",
        notes=(),
    )
    # Its predicate correctly refuses everything -- proving the glob match
    # alone (which would otherwise happily claim any path) cannot smuggle a
    # registration past a failing structural check.
    monkeypatch.setitem(policy_validators.VALIDATORS, "BROAD_GLOB_TEST_ONLY", lambda *_a: False)

    new_sources = _classify(catalog, ["totally_new_unclassified_module.py"])
    result = _reconcile_with_fakes(catalog, (broad,), new_sources=new_sources)
    assert len(result.auto_maintenance_sources) == 0
    assert result.decision_queue[0]["policy_id"] == "BROAD_GLOB_TEST_ONLY"
    assert "predicate failed" in result.decision_queue[0]["policy_note"]
    assert result.outcome == OWNER_DECISION_REQUIRED


# =====================================================================
# Pre-merge (PR-time) owner decision gate -- reconcile_pr()
#
# See docs/context_librarian/RECONCILIATION.md section F. reconcile_pr()
# classifies only the sources a PR's own diff (base_ref..head_ref) adds,
# using the exact same per-item routing engine (_route_new_sources())
# reconcile() uses post-merge -- these tests exist specifically to prove
# that sharing, not just that reconcile_pr() "also produces an outcome".
# =====================================================================

from tools.context_librarian.reconcile import ReconcileResult, reconcile_pr  # noqa: E402
from tools.context_librarian.owner_decision_report import (  # noqa: E402
    find_consumers,
    format_owner_decision_request,
    format_pr_summary,
)


def _reconcile_pr_with_fakes(
    catalog,
    policies,
    *,
    new_sources=(),
    base_sha="0000000000000000000000000000000000000base",
    head_sha="1111111111111111111111111111111111111head",
):
    """Drives reconcile_pr()'s routing/outcome logic without a real git
    diff, mirroring _reconcile_with_fakes() above -- same fake-injection
    seam style, applied to reconcile_pr()'s own (smaller) set of internal
    calls (_resolve_main_sha, _scan_pr_new_sources)."""
    mp = pytest.MonkeyPatch()
    try:
        def fake_resolve(_repo_root, ref):
            return base_sha if ref == "origin/main" else head_sha
        mp.setattr(reconcile_module, "_resolve_main_sha", fake_resolve)
        mp.setattr(reconcile_module, "_scan_pr_new_sources", lambda *_a, **_k: list(new_sources))
        return reconcile_pr(catalog, policies, base_ref="origin/main", head_ref="HEAD")
    finally:
        mp.undo()


def test_pr_with_no_new_sources_is_clean(catalog, policies):
    result = _reconcile_pr_with_fakes(catalog, policies, new_sources=[])
    assert result.outcome == CLEAN
    assert result.decision_queue == ()
    assert result.auto_maintenance_sources == ()


def test_pr_source_covered_by_approved_policy_needs_no_owner_decision(catalog, policies):
    # Real, permanent, deliberately-unregistered fixture matching
    # OFFLINE_RESEARCH_TOOL (same fixture test_policy_approved_new_source_
    # registers_and_reconciles_clean() above uses for the post-merge path)
    # -- reused here so both paths are proven against the identical real
    # file, not two different examples that could quietly drift apart.
    fixture_path = "scripts/research_crawler_poc/reconcile_test_fixture.py"
    assert fixture_path not in catalog.nodes["decision.offline_research_support_tool"]["code_paths"]
    new_sources = classify_new_sources(catalog, [fixture_path])

    result = _reconcile_pr_with_fakes(catalog, policies, new_sources=new_sources)
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED
    assert result.decision_queue == ()
    assert len(result.auto_maintenance_sources) == 1
    assert result.auto_maintenance_sources[0]["policy_id"] == "OFFLINE_RESEARCH_TOOL"


def test_pr_unknown_runtime_source_requires_owner_decision(catalog, policies):
    new_sources = _classify(catalog, ["totally_new_unclassified_pr_module.py"])
    result = _reconcile_pr_with_fakes(catalog, policies, new_sources=new_sources)
    assert result.outcome == OWNER_DECISION_REQUIRED
    assert len(result.decision_queue) == 1
    assert result.decision_queue[0]["path"] == "totally_new_unclassified_pr_module.py"
    assert result.decision_queue[0]["block_reason"] == "NO_POLICY_MATCH"


def test_pr_authority_sensitive_source_is_stop_and_requires_owner_decision(catalog, policies):
    # "authority" in the filename trips librarian.py's _AUTHORITY_TERMS
    # escalation -- STOP, never eligible for auto-maintenance regardless of
    # any policy match (see test_H above for the post-merge equivalent, and
    # the dedicated STOP-with-policy-match test right below).
    new_sources = _classify(catalog, ["new_pr_authority_boundary.py"])
    assert new_sources[0]["classification"] == "STOP"

    result = _reconcile_pr_with_fakes(catalog, policies, new_sources=new_sources)
    assert result.outcome == OWNER_DECISION_REQUIRED
    assert result.decision_queue[0]["classification"] == "STOP"
    # No policy in the real registry matches this arbitrary filename, so it
    # fails closed one step earlier than the STOP-specific check -- still
    # OWNER_DECISION_REQUIRED either way (see the dedicated
    # STOP_NEVER_AUTO test below for the "STOP despite a policy match" case).
    assert result.decision_queue[0]["block_reason"] == "NO_POLICY_MATCH"


def test_pr_stop_classification_never_auto_eligible_even_with_a_matching_policy(catalog):
    """A STOP-classified file that DOES match a policy (eligible_target
    set, auto_registration_allowed=True) must still route to
    OWNER_DECISION_REQUIRED with block_reason STOP_NEVER_AUTO -- mirrors
    test_H_broad_glob_cannot_override_failed_structural_predicate's
    guarantee, exercised through the PR-time path this time."""
    broad = Policy(
        id="BROAD_GLOB_PR_TEST_ONLY", policy_version=1, description="deliberately over-broad",
        path_patterns=("*",), runtime_consumed=True, authority=False,
        eligible_target="layer.marketing", target_field="code_paths",
        auto_registration_allowed=True, classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE",
        notes=(),
    )
    new_sources = _classify(catalog, ["new_pr_authority_boundary_stop_policy.py"])
    assert new_sources[0]["classification"] == "STOP"

    result = _reconcile_pr_with_fakes(catalog, (broad,), new_sources=new_sources)
    assert result.outcome == OWNER_DECISION_REQUIRED
    assert result.decision_queue[0]["block_reason"] == "STOP_NEVER_AUTO"
    assert result.decision_queue[0]["policy_id"] == "BROAD_GLOB_PR_TEST_ONLY"
    assert result.auto_maintenance_sources == ()


def test_pr_mechanical_drift_on_main_never_blocks_an_unrelated_pr(catalog, policies):
    """reconcile_pr() must never surface main's own pre-existing,
    PR-unrelated backlog (mechanical_updates / revalidation_flags) -- those
    are the post-merge gate's job. A PR that adds nothing new must be CLEAN
    even if _mechanical_drift()/_scan_auto_registrations() would (if they
    were even called) find something stale on main."""
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(reconcile_module, "_mechanical_drift", lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("reconcile_pr() must never call _mechanical_drift")
        ))
        mp.setattr(reconcile_module, "_scan_auto_registrations", lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("reconcile_pr() must never call _scan_auto_registrations")
        ))
        result = _reconcile_pr_with_fakes(catalog, policies, new_sources=[])
    assert result.outcome == CLEAN
    assert result.mechanical_updates == ()
    assert result.revalidation_flags == ()


def test_owner_approved_catalog_update_in_same_pr_makes_second_reconcile_clean(policies):
    """Simulates the full 'Recording the owner decision' flow (spec item 4):
    a PR introduces a STOP-classified new file -> OWNER_DECISION_REQUIRED;
    the PR is then amended to register that same file into an existing
    node's code_paths (the owner's decision, encoded in the catalog) -> a
    second reconcile of the SAME diff is CLEAN, because the file is no
    longer unregistered and therefore never even reaches classification.

    Uses a fresh (not the shared module-scoped `catalog` fixture)
    load_catalog(REPO_ROOT) call and mutates its in-memory node dict
    directly, restored in `finally` -- proves the classification-exclusion
    contract (_catalog_referenced_paths/classify_new_sources) without
    needing a real file write (apply_auto_maintenance()'s own tests already
    cover the real-write path) and without the isolated-tmp-catalog path
    mismatch _catalog_referenced_paths() has against a repo_root/catalog_root
    split (see the comment on test_policy_approved_new_source_registers_
    and_reconciles_clean above)."""
    fresh = load_catalog(REPO_ROOT)
    new_path = "new_pr_authority_boundary_2.py"
    target_node_id = "layer.marketing"

    first_sources = classify_new_sources(fresh, [new_path])
    assert first_sources[0]["classification"] == "STOP"
    first = _reconcile_pr_with_fakes(fresh, policies, new_sources=first_sources)
    assert first.outcome == OWNER_DECISION_REQUIRED

    # Owner decision: register under an existing node (mirrors PR #651's
    # real "APPROVED under existing layer.marketing, do NOT create a new
    # layer" resolution).
    fresh.nodes[target_node_id]["code_paths"].append(new_path)
    try:
        second_sources = classify_new_sources(fresh, [new_path])
        assert second_sources == [], "a registered path must never reach classify_new_sources() again"
        second = _reconcile_pr_with_fakes(fresh, policies, new_sources=second_sources)
        assert second.outcome == CLEAN
    finally:
        fresh.nodes[target_node_id]["code_paths"].remove(new_path)


def test_reconcile_pr_and_reconcile_route_identical_new_sources_identically(catalog, policies):
    """The actual 'same classifier, not a parallel one' proof: feed the
    literal same new_sources list through both reconcile()'s and
    reconcile_pr()'s internal routing and assert byte-identical
    classification results (auto_maintenance/decision_queue/non_blocking),
    field for field -- not just 'both return some outcome'."""
    shared_new_sources = _classify(
        catalog,
        [
            "totally_new_unclassified_shared_module.py",
            "scripts/research_crawler_poc/reconcile_test_fixture.py",
            "new_shared_authority_thing.py",
        ],
    )

    post_merge_result = _reconcile_with_fakes(catalog, policies, new_sources=shared_new_sources)
    pr_result = _reconcile_pr_with_fakes(catalog, policies, new_sources=shared_new_sources)

    assert post_merge_result.decision_queue == pr_result.decision_queue
    assert post_merge_result.auto_maintenance_sources == pr_result.auto_maintenance_sources
    assert post_merge_result.non_blocking_sources == pr_result.non_blocking_sources
    # Both must agree an owner decision is required, for the same reason.
    assert post_merge_result.outcome == OWNER_DECISION_REQUIRED == pr_result.outcome


def test_scan_pr_new_sources_uses_merge_base_not_mutable_base_tip(tmp_path):
    """Real, non-monkeypatched proof of the two-dot -> three-dot fix: builds
    an actual small git repo where a file present at the fork point is
    independently deleted on the base branch *after* the PR branch forked.
    A two-dot diff (base_sha..head_sha, comparing base's CURRENT tip against
    head) would wrongly call that file "added" on the PR side (present on
    head, absent from base's current tree) even though the PR branch never
    touched it. The three-dot range (base_sha...head_sha,
    merge-base(base,head)..head) must not."""
    import subprocess as sp

    def run(*args: str) -> None:
        sp.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    def rev_parse(ref: str) -> str:
        return sp.run(
            ["git", "rev-parse", ref], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()

    run("init", "-q")
    run("config", "user.email", "test@test.com")
    run("config", "user.name", "test")
    (tmp_path / "old_shared_file.py").write_text("x = 1\n")
    run("add", ".")
    run("commit", "-q", "-m", "fork point: old_shared_file.py exists")
    fork_point = rev_parse("HEAD")
    base_branch = sp.run(
        ["git", "branch", "--show-current"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()

    run("checkout", "-q", "-b", "pr-branch")
    (tmp_path / "pr_new_file.py").write_text("y = 2\n")
    run("add", ".")
    run("commit", "-q", "-m", "PR adds pr_new_file.py")
    head_sha = rev_parse("HEAD")

    run("checkout", "-q", base_branch)
    (tmp_path / "old_shared_file.py").unlink()
    run("add", ".")
    run("commit", "-q", "-m", "base independently deletes old_shared_file.py")
    base_tip = rev_parse("HEAD")

    assert base_tip != fork_point, "test setup sanity: base must have moved past the fork point"

    catalog = Catalog(
        repo_root=tmp_path, catalog_root=tmp_path, node_schema={}, edge_schema={},
        nodes={}, edges=(), profiles={}, layer_nodes={},
    )

    # The bug this reproduces: a two-dot diff against base's CURRENT tip.
    two_dot_added = reconcile_module._run_git(
        tmp_path, ["diff", "--diff-filter=A", "--name-only", base_tip, head_sha]
    )[1].splitlines()
    assert "old_shared_file.py" in two_dot_added, (
        "test setup sanity: two-dot diff must reproduce the false positive "
        "this fix guards against"
    )

    # The fix: _scan_pr_new_sources() itself, using the three-dot range.
    added_sources = reconcile_module._scan_pr_new_sources(catalog, base_tip, head_sha)
    added_paths = {item["path"] for item in added_sources}
    assert "pr_new_file.py" in added_paths
    assert "old_shared_file.py" not in added_paths


def test_reconcile_pr_is_read_only_never_writes_reconciliation_state():
    """reconcile_pr_repo() against the real repo with base==head (a no-op
    diff, short-circuiting _scan_pr_new_sources()) must leave
    reconciliation_state.json byte-identical -- there is no PR-time
    apply-auto path; only the existing post-merge apply_auto_maintenance()
    may ever write it."""
    from tools.context_librarian.reconcile import reconcile_pr_repo

    state_path = REPO_ROOT / "docs/context_librarian/reconciliation_state.json"
    before = state_path.read_bytes()
    result = reconcile_pr_repo(REPO_ROOT, base_ref="HEAD", head_ref="HEAD")
    after = state_path.read_bytes()
    assert before == after
    assert result.outcome == CLEAN
    assert result.mechanical_updates == ()
    assert result.revalidation_flags == ()


def test_post_merge_reconcile_workflow_remains_the_final_safety_net(catalog, policies):
    """Post-merge reconcile() is unchanged by the pre-merge gate's addition
    -- still computes mechanical_updates/revalidation_flags (which
    reconcile_pr() deliberately never does), still the only path that feeds
    apply_auto_maintenance()."""
    result = _reconcile_with_fakes(
        catalog, policies,
        mechanical_updates=[{"node_id": "layer.marketing", "from": "a", "to": "b", "changed_paths": ["x.py"]}],
    )
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED
    assert result.mechanical_updates != ()


# --- Owner Decision Request formatting (tools/context_librarian/owner_decision_report.py) ---


def test_format_owner_decision_request_contains_every_required_section():
    item = {
        "path": "new_pr_authority_boundary_3.py",
        "classification": "STOP",
        "reason": "unregistered source may change authority",
        "block_reason": "NO_POLICY_MATCH",
    }
    text = format_owner_decision_request(REPO_ROOT, item)
    for heading in (
        "OWNER DECISION REQUIRED", "Source:", "Classification:", "Proposed target:",
        "Evidence:", "Recommended decision:", "Alternative:",
        "Risk if classified incorrectly:", "Required owner answer",
    ):
        assert heading in text
    assert "new_pr_authority_boundary_3.py" in text
    assert "STOP" in text
    # The agent proposes a recommendation; it must never claim to have
    # resolved the decision itself.
    assert "NEEDS OWNER REVIEW" in text
    assert "APPROVE EXISTING NODE" in text  # offered as a bounded answer choice
    assert "CREATE NEW NODE" in text
    assert "REJECT" in text


def test_format_owner_decision_request_never_auto_resolves_a_stop_even_with_policy_match():
    """A STOP item that happens to also match a policy (eligible_target set)
    must still recommend NEEDS OWNER REVIEW, never APPROVE EXISTING NODE
    outright -- matching reconcile.py's own structural guarantee that STOP
    is never auto-eligible regardless of policy match."""
    item = {
        "path": "some_authority_module.py",
        "classification": "STOP",
        "reason": "unregistered source may change authority",
        "block_reason": "STOP_NEVER_AUTO",
        "policy_id": "SOME_POLICY",
        "eligible_target": "layer.marketing",
        "target_field": "code_paths",
    }
    text = format_owner_decision_request(REPO_ROOT, item)
    assert "Recommended decision:\nNEEDS OWNER REVIEW" in text


def test_find_consumers_finds_real_callers_of_a_real_module():
    hits = find_consumers(REPO_ROOT, "marketing_fact_authority.py")
    assert "cmd_marketing.py" in hits


def test_find_consumers_reports_no_matches_for_a_module_nothing_imports():
    # find_consumers() searches every tracked file, not just *.py (fixed
    # per CodeRabbit review on PR #653 -- a *.py-only search would miss a
    # TS/JS/doc consumer). This test file's own literal string argument
    # above is therefore an expected self-match; assert no *other* file
    # references this nonexistent module.
    hits = find_consumers(REPO_ROOT, "totally_unreferenced_fixture_module_xyz.py")
    assert hits == ["test_reconcile.py"]


def test_format_pr_summary_states_result_and_merge_block_status():
    blocked_item = {
        "path": "blocked_thing.py", "classification": "REVIEW_REQUIRED",
        "reason": "new runtime source", "block_reason": "NO_POLICY_MATCH",
    }
    blocked = ReconcileResult(
        outcome=OWNER_DECISION_REQUIRED, main_ref="origin/main", canonical_main_sha="a" * 40,
        mechanical_updates=(), auto_maintenance_sources=(), decision_queue=(blocked_item,),
        non_blocking_sources=(), revalidation_flags=(),
    )
    text = format_pr_summary(blocked, REPO_ROOT)
    assert "OWNER_DECISION_REQUIRED" in text
    assert "BLOCKED" in text
    assert "blocked_thing.py" in text

    clean = ReconcileResult(
        outcome=CLEAN, main_ref="origin/main", canonical_main_sha="b" * 40,
        mechanical_updates=(), auto_maintenance_sources=(), decision_queue=(),
        non_blocking_sources=(), revalidation_flags=(),
    )
    clean_text = format_pr_summary(clean, REPO_ROOT)
    assert "CLEAN" in clean_text
    assert "not blocked" in clean_text


def test_format_pr_summary_renders_revalidation_flags_when_decision_queue_is_empty():
    """reconcile() forces OWNER_DECISION_REQUIRED whenever revalidation_flags
    is non-empty, even with an empty decision_queue (see _scan_auto_
    registrations()'s STALE_REVALIDATION_REQUIRED path). format_pr_summary()
    must never render 'BLOCKED' with nothing underneath explaining why --
    fixed per CodeRabbit review on PR #653."""
    flag = {
        "path": "some/stale_registered_thing.py",
        "status": "STALE_REVALIDATION_REQUIRED",
        "previous_policy": "OFFLINE_RESEARCH_TOOL",
        "failed_predicate": "structural/content predicate failed",
        "changed_commit": "c" * 40,
        "current_target": "decision.offline_research_support_tool",
    }
    result = ReconcileResult(
        outcome=OWNER_DECISION_REQUIRED, main_ref="origin/main", canonical_main_sha="d" * 40,
        mechanical_updates=(), auto_maintenance_sources=(), decision_queue=(),
        non_blocking_sources=(), revalidation_flags=(flag,),
    )
    text = format_pr_summary(result, REPO_ROOT)
    assert "BLOCKED" in text
    assert "some/stale_registered_thing.py" in text
    assert "OFFLINE_RESEARCH_TOOL" in text
    assert "Required owner action" in text
    assert "Nothing in this PR's own diff requires an owner decision." not in text
