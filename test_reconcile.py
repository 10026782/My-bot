"""Tests for tools/context_librarian/reconcile.py and policy_registry.py.

Covers the 10 required scenarios for the three-outcome reconciliation engine
(CLEAN / AUTO_MAINTENANCE_REQUIRED / OWNER_DECISION_REQUIRED) -- see
docs/context_librarian/RECONCILIATION.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.context_librarian import reconcile as reconcile_module
from tools.context_librarian.librarian import classify_new_sources, load_catalog
from tools.context_librarian.policy_registry import load_policy_registry, match_policy
from tools.context_librarian.reconcile import (
    AUTO_MAINTENANCE_REQUIRED,
    CLEAN,
    OWNER_DECISION_REQUIRED,
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


def _fake_proposal(new_sources, updates=(), main_sha="deadbee00000000000000000000000000000000"):
    return {
        "status": "CHANGES_REQUIRED" if new_sources or updates else "OK",
        "main_ref": "origin/main",
        "canonical_main_sha": main_sha,
        "updates": list(updates),
        "new_sources": list(new_sources),
        "authority_review_required": bool(new_sources),
    }


def _classify(catalog, paths):
    return classify_new_sources(catalog, paths)


# --- Policy registry basics ---------------------------------------------


def test_policy_registry_loads_all_seven_policies(policies):
    ids = {p.id for p in policies}
    assert ids == {
        "DOCUMENTATION_REFERENCE_ASSET",
        "STAGING_VERIFICATION_ARTIFACT",
        "TEST_SUPPORT_ARTIFACT",
        "SHARED_UI_PRIMITIVE",
        "CROSS_LAYER_SUPPORTING_METADATA",
        "OFFLINE_RESEARCH_TOOL",
        "EXTERNAL_RECOMMENDATION_CATALOG",
    }


def test_policy_matching_is_glob_only_not_substring(policies):
    # "evidence" is nowhere in this path as a directory/keyword hit the old
    # substring-based STOP escalation would have cared about -- it must not
    # match DOCUMENTATION_REFERENCE_ASSET via substring coincidence either.
    assert match_policy("core/authority_evidence_tracker.py", policies) is None
    # A real match: exact glob against the declared pattern.
    assert match_policy("scripts/verify_f15_staging.py", policies).id == "STAGING_VERIFICATION_ARTIFACT"


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


# --- G.2: mechanical provenance advances automatically -------------------


def test_stamp_observed_advances_last_observed_without_touching_semantic_fields(
    catalog, monkeypatch, tmp_path
):
    import shutil

    from tools.context_librarian import librarian

    target = tmp_path / "catalog"
    shutil.copytree(REPO_ROOT / "docs/context_librarian", target)
    monkeypatch.setattr(librarian, "CATALOG_RELATIVE_ROOT", target)
    isolated = load_catalog(REPO_ROOT)

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


# --- G.3: known verification scripts classify deterministically ----------


def test_new_staging_verification_script_is_auto_maintenance_eligible(catalog, policies):
    new_sources = _classify(catalog, ["scripts/verify_newthing_staging.py"])
    fake = _fake_proposal(new_sources)
    result = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert len(result.decision_queue) == 0
    assert len(result.auto_maintenance_sources) == 1
    item = result.auto_maintenance_sources[0]
    assert item["policy_id"] == "STAGING_VERIFICATION_ARTIFACT"
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED


def _reconcile_with_fake_proposal(catalog, policies, fake_proposal, monkeypatch=None):
    """Runs reconcile()'s classification logic against a hand-built proposal
    without needing a real git history change -- reconcile() itself only
    calls refresh_proposal() once at the top, so a direct monkeypatch call
    per-test would work too; this helper avoids repeating that boilerplate."""
    import pytest as _pytest

    mp = _pytest.MonkeyPatch()
    try:
        mp.setattr(reconcile_module, "refresh_proposal", lambda *_a, **_k: fake_proposal)
        return reconcile(catalog, policies, main_ref="origin/main")
    finally:
        mp.undo()


# --- G.4: known reference assets remain non-blocking ----------------------


def test_reference_evidence_image_stays_non_blocking(catalog, policies):
    new_sources = _classify(
        catalog, ["docs/ux/reference-evidence/newvendor/newvendor-home.png"]
    )
    fake = _fake_proposal(new_sources)
    result = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert len(result.decision_queue) == 0
    assert len(result.non_blocking_sources) == 1
    assert result.outcome == CLEAN


# --- G.5: known shared UI primitives follow approved policy ---------------


def test_new_tma_ui_primitive_is_pre_labelled_with_policy_but_still_queued(catalog, policies):
    new_sources = _classify(
        catalog, ["tma-frontend/src/components/ui/NewPrimitive.tsx"]
    )
    fake = _fake_proposal(new_sources)
    result = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert len(result.auto_maintenance_sources) == 0
    assert len(result.decision_queue) == 1
    item = result.decision_queue[0]
    assert item["policy_id"] == "SHARED_UI_PRIMITIVE"
    assert item["eligible_target"] == "decision.tma_shared_ui_primitives"
    assert result.outcome == OWNER_DECISION_REQUIRED


# --- G.6: unknown runtime .py still requires owner decision ---------------


def test_unknown_runtime_python_file_requires_owner_decision(catalog, policies):
    new_sources = _classify(catalog, ["totally_new_unclassified_module.py"])
    fake = _fake_proposal(new_sources)
    result = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert len(result.auto_maintenance_sources) == 0
    assert len(result.decision_queue) == 1
    assert "policy_id" not in result.decision_queue[0]
    assert result.outcome == OWNER_DECISION_REQUIRED


# --- G.7: authority-named runtime code is never auto-approved -------------


def test_authority_named_path_never_auto_approved_even_with_hypothetical_policy_match(
    catalog, policies
):
    new_sources = _classify(catalog, ["core/new_action_gateway_extension.py"])
    assert new_sources[0]["classification"] == "STOP"
    fake = _fake_proposal(new_sources)
    result = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert len(result.auto_maintenance_sources) == 0
    assert result.decision_queue[0]["path"] == "core/new_action_gateway_extension.py"
    assert result.outcome == OWNER_DECISION_REQUIRED

    # Structural guarantee, not just "no policy happens to match today": even
    # a maximally permissive policy that matches every path must never move
    # a STOP classification into auto-maintenance.
    from tools.context_librarian.policy_registry import Policy

    catch_all = Policy(
        id="CATCH_ALL_TEST_ONLY",
        description="test-only",
        path_patterns=("*",),
        runtime_consumed=True,
        authority=False,
        eligible_target=None,
        auto_registration_allowed=True,
        classification_when_matched="AUTO_MAINTENANCE_ELIGIBLE",
        notes=(),
    )
    result_with_catch_all = _reconcile_with_fake_proposal(
        catalog, (catch_all,), fake
    )
    assert len(result_with_catch_all.auto_maintenance_sources) == 0
    assert result_with_catch_all.outcome == OWNER_DECISION_REQUIRED


# --- G.8: previously resolved classification does not reappear ------------


def test_registered_path_never_reappears_as_new_source(catalog, policies):
    # business_tool_registry.py is registered (code_paths) in a real layer
    # today via decision.external_business_tool_recommendation_catalog only
    # once PR #628 merges; using a definitely-already-registered path here
    # instead so the guarantee is exercised against current main state.
    registered_path = next(iter(catalog.nodes.values()))["code_paths"]
    if not registered_path:
        for node in catalog.nodes.values():
            if node["code_paths"]:
                registered_path = node["code_paths"]
                break
    assert registered_path, "expected at least one registered code_path in the real catalog"
    new_sources = _classify(catalog, [registered_path[0]])
    assert new_sources == []


# --- G.9: automation never pushes directly to main -------------------------


def test_reconcile_workflow_never_pushes_to_main():
    workflow = REPO_ROOT / ".github/workflows/context-librarian-reconcile.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "push origin main" not in text
    assert "push origin HEAD:main" not in text
    assert "git push origin \"$branch\"" in text or "git push origin ${branch}" in text
    assert "gh pr create" in text
    assert "--base main" in text


# --- G.10: repeated reconcile on unchanged main is idempotent -------------


def test_reconcile_is_idempotent_on_unchanged_input(catalog, policies):
    new_sources = _classify(
        catalog,
        [
            "business_tool_registry.py",
            "docs/ux/reference-evidence/x/y.png",
            "totally_unmatched_new_thing.py",
        ],
    )
    fake = _fake_proposal(new_sources)
    first = _reconcile_with_fake_proposal(catalog, policies, fake)
    second = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert first.to_json() == second.to_json()


# --- Outcome state machine sanity -----------------------------------------


def test_outcome_clean_when_nothing_pending(catalog, policies):
    fake = _fake_proposal([], updates=[])
    result = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert result.outcome == CLEAN


def test_outcome_auto_maintenance_when_only_mechanical_updates_pending(catalog, policies):
    fake = _fake_proposal(
        [], updates=[{"node_id": "layer.marketing", "from": "a", "to": "b", "changed_paths": ["x.py"]}]
    )
    result = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert result.outcome == AUTO_MAINTENANCE_REQUIRED


def test_outcome_owner_decision_overrides_auto_maintenance(catalog, policies):
    new_sources = _classify(catalog, ["totally_unmatched_new_thing.py"])
    fake = _fake_proposal(
        new_sources,
        updates=[{"node_id": "layer.marketing", "from": "a", "to": "b", "changed_paths": ["x.py"]}],
    )
    result = _reconcile_with_fake_proposal(catalog, policies, fake)
    assert result.outcome == OWNER_DECISION_REQUIRED
