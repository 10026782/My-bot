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
