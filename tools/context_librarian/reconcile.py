"""Three-outcome Context Librarian reconciliation, replacing the old binary
CHANGES_REQUIRED gate with CLEAN / AUTO_MAINTENANCE_REQUIRED / OWNER_DECISION_REQUIRED.

See docs/context_librarian/RECONCILIATION.md for the full design. In short:

- CLEAN: nothing to do.
- AUTO_MAINTENANCE_REQUIRED: only deterministic provenance bumps and/or
  policy-pre-approved registrations remain -- safe for automation to prepare
  a patch, never to push it to main or merge it.
- OWNER_DECISION_REQUIRED: at least one unregistered source neither matches
  an approved policy nor is otherwise resolved -- a human must classify it.
  Automation must never guess this one.

This module never makes a semantic authority decision itself. It only ever
(a) reuses a decision an owner already wrote into policy_registry.json, or
(b) reports mechanical provenance drift on already-registered nodes, or
(c) reports what still needs a human. It never adds/edits code_paths or
test_paths except through apply_auto_maintenance()'s narrow, fully-validated
registration path (see that function's docstring), and never touches
canonical_docs, edges, catalog nodes' identity, last_verified_commit, or
last_semantic_review_commit.

Provenance model (Message D correction, see RECONCILIATION.md):
- Mechanical node-level drift is measured against `last_observed_commit`
  (falling back to `last_verified_commit` only as a one-time migration
  default for nodes that have never been observed) -- never directly
  against `last_verified_commit`, which stays exclusively the semantic
  commit a human last reviewed the node's authority/ownership boundary at.
- New-source discovery is anchored on `last_source_scan_commit`
  (reconciliation_state.py), a single repo-level mechanical marker --
  never on the per-node `last_verified_commit` anchors librarian.py's own
  discover_new_sources() uses for its (still-supported, still-used-as-a-
  migration-fallback-only) anchor computation.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.context_librarian.librarian import (
    Catalog,
    ContextLibrarianError,
    classify_new_sources,
    discover_new_sources,
    load_catalog,
)
from tools.context_librarian.policy_registry import Policy, load_policy_registry, matching_policies
from tools.context_librarian.reconciliation_state import (
    load_reconciliation_state,
    write_source_scan_commit,
)


CLEAN = "CLEAN"
# Intentionally duplicated from librarian.py's own private
# _NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS rather than imported, mirroring
# refresh_after_merge.py's existing precedent of not depending on that
# module's private surface (see its own module docstring).
_NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS = frozenset({"WARNING", "GOVERNANCE_ARTIFACT"})
AUTO_MAINTENANCE_REQUIRED = "AUTO_MAINTENANCE_REQUIRED"
OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"
_REGISTERABLE_FIELDS = ("code_paths", "test_paths")


@dataclass(frozen=True)
class ReconcileResult:
    outcome: str
    main_ref: str
    canonical_main_sha: str
    mechanical_updates: tuple[dict[str, Any], ...]
    auto_maintenance_sources: tuple[dict[str, Any], ...]
    decision_queue: tuple[dict[str, Any], ...]
    non_blocking_sources: tuple[dict[str, Any], ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "main_ref": self.main_ref,
            "canonical_main_sha": self.canonical_main_sha,
            "mechanical_updates": list(self.mechanical_updates),
            "auto_maintenance_sources": list(self.auto_maintenance_sources),
            "decision_queue": list(self.decision_queue),
            "non_blocking_sources": list(self.non_blocking_sources),
        }


def _run_git(repo_root: Path, args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
    )
    return completed.returncode, completed.stdout.strip()


def _resolve_main_sha(repo_root: Path, main_ref: str) -> str:
    code, out = _run_git(repo_root, ["rev-parse", "--verify", main_ref])
    if code != 0 or not out:
        raise ContextLibrarianError(f"cannot resolve {main_ref}")
    return out


def _matches_tracked(changed: str, tracked: str) -> bool:
    import fnmatch

    tracked = tracked.replace("\\", "/")
    return changed == tracked or fnmatch.fnmatch(changed, tracked) or changed.startswith(
        tracked.rstrip("/") + "/"
    )


def _changed_paths_between(repo_root: Path, base: str, target: str) -> set[str]:
    """Isolated as its own function -- mockable seam for tests, mirroring
    _current_branch_and_commit()."""
    if base == target:
        return set()
    code, out = _run_git(repo_root, ["diff", "--name-only", base, target])
    if code != 0:
        raise ContextLibrarianError(f"cannot diff {base}..{target}")
    return {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()}


def _observed_baseline(node: dict[str, Any]) -> str:
    """Effective mechanical observation baseline: last_observed_commit if the
    node has ever been stamped, otherwise last_verified_commit as a one-time
    migration default. Never last_verified_commit once last_observed_commit
    exists -- that would silently upgrade a mechanical scan into looking like
    semantic re-verification."""
    return node.get("last_observed_commit") or node["last_verified_commit"]


def _mechanical_drift(catalog: Catalog, main_sha: str) -> list[dict[str, Any]]:
    """Registered-node drift, measured against each node's observation
    baseline (see _observed_baseline) -- NOT against last_verified_commit."""
    updates: list[dict[str, Any]] = []
    for node in sorted(catalog.nodes.values(), key=lambda item: item["id"]):
        baseline = _observed_baseline(node)
        changed_all = _changed_paths_between(catalog.repo_root, baseline, main_sha)
        tracked = (
            node["code_paths"]
            + node["test_paths"]
            + [ref["path"] for ref in node["canonical_docs"]]
            + [ref["path"] for ref in node["production_evidence"]]
        )
        changed = sorted(p for p in changed_all if any(_matches_tracked(p, t) for t in tracked))
        if changed:
            updates.append(
                {"node_id": node["id"], "from": baseline, "to": main_sha, "changed_paths": changed}
            )
    return updates


def _scan_new_sources(catalog: Catalog, main_sha: str, main_ref: str) -> list[dict[str, str]]:
    """New-source discovery anchored on last_source_scan_commit
    (reconciliation_state.json), not on any node's last_verified_commit.

    Migration fallback: if no scan has ever been recorded, falls back to
    librarian.discover_new_sources()'s existing last_verified_commit-anchor
    computation for this one first run only -- the very next
    apply_auto_maintenance() call establishes last_source_scan_commit and
    every subsequent scan uses it exclusively.
    """
    state = load_reconciliation_state(catalog.catalog_root)
    baseline = state.get("last_source_scan_commit")
    if baseline is None:
        return discover_new_sources(catalog, main_ref=main_ref)
    if baseline == main_sha:
        return []
    code, out = _run_git(catalog.repo_root, ["diff", "--diff-filter=A", "--name-only", baseline, main_sha])
    if code != 0:
        raise ContextLibrarianError(f"cannot scan new sources between {baseline}..{main_sha}")
    added = [line.strip() for line in out.splitlines() if line.strip()]
    return classify_new_sources(catalog, added)


def _resolve_policy(path: str, policies: tuple[Policy, ...]) -> tuple[Policy | None, bool]:
    """Returns (policy, ambiguous). Ambiguous=True (policy=None) when more
    than one policy matches the same path with differing (eligible_target,
    target_field) -- deterministic resolution failed, so this must never be
    silently narrowed to "just pick the first one". Multiple matches that
    all agree on the same target are treated as a single unambiguous match."""
    matches = matching_policies(path, policies)
    if not matches:
        return None, False
    first = matches[0]
    key = (first.eligible_target, first.target_field)
    if any((m.eligible_target, m.target_field) != key for m in matches[1:]):
        return None, True
    return first, False


def reconcile(
    catalog: Catalog, policies: tuple[Policy, ...], *, main_ref: str = "origin/main"
) -> ReconcileResult:
    """Pure classification -- no disk writes, no git writes."""
    main_sha = _resolve_main_sha(catalog.repo_root, main_ref)
    mechanical_updates = _mechanical_drift(catalog, main_sha)
    new_sources = _scan_new_sources(catalog, main_sha, main_ref)

    auto_maintenance: list[dict[str, Any]] = []
    decision_queue: list[dict[str, Any]] = []
    non_blocking: list[dict[str, Any]] = []

    for item in new_sources:
        classification = item["classification"]
        if classification in _NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS:
            non_blocking.append(item)
            continue

        policy, ambiguous = _resolve_policy(item["path"], policies)
        if ambiguous:
            decision_queue.append(
                {**item, "policy_note": "path matches multiple policies with different "
                 "targets -- ambiguous, requires owner decision"}
            )
            continue
        if policy is None:
            decision_queue.append(item)
            continue

        enriched = {
            **item,
            "policy_id": policy.id,
            "eligible_target": policy.eligible_target,
            "target_field": policy.target_field,
        }

        # STOP is never eligible for auto-maintenance, full stop -- even if a
        # future policy were mis-authored to match an authority-sounding
        # path, an unregistered source that tripped the authority-term
        # escalation always requires a human decision. This is a structural
        # guarantee, not a registry-authoring convention.
        if classification == "STOP":
            decision_queue.append(
                {**enriched, "policy_note": "STOP classification is never eligible for "
                 "auto-maintenance regardless of policy match"}
            )
            continue

        if not policy.auto_registration_allowed:
            decision_queue.append(
                {**enriched, "policy_note": "matches a known policy class but that policy "
                 "requires human confirmation before registration "
                 "(auto_registration_allowed=false)"}
            )
            continue

        if policy.eligible_target is not None and policy.eligible_target not in catalog.nodes:
            decision_queue.append(
                {**enriched, "policy_note": f"policy eligible_target "
                 f"{policy.eligible_target!r} does not exist in the loaded catalog yet -- "
                 "cannot auto-register until it is created"}
            )
            continue

        if policy.eligible_target is not None and policy.target_field not in _REGISTERABLE_FIELDS:
            decision_queue.append(
                {**enriched, "policy_note": "policy has an eligible_target but no valid "
                 "target_field declared -- cannot auto-register"}
            )
            continue

        auto_maintenance.append(enriched)

    if decision_queue:
        outcome = OWNER_DECISION_REQUIRED
    elif mechanical_updates or auto_maintenance:
        outcome = AUTO_MAINTENANCE_REQUIRED
    else:
        outcome = CLEAN

    return ReconcileResult(
        outcome=outcome,
        main_ref=main_ref,
        canonical_main_sha=main_sha,
        mechanical_updates=tuple(mechanical_updates),
        auto_maintenance_sources=tuple(auto_maintenance),
        decision_queue=tuple(decision_queue),
        non_blocking_sources=tuple(non_blocking),
    )


def reconcile_repo(repo_root: Path, *, main_ref: str = "origin/main") -> ReconcileResult:
    catalog = load_catalog(repo_root)
    policies = load_policy_registry(repo_root)
    return reconcile(catalog, policies, main_ref=main_ref)


def _working_tree_is_clean(repo_root: Path) -> bool:
    """Isolated as its own function -- mockable seam for tests, mirroring
    _current_branch_and_commit() and _changed_paths_between()."""
    code, out = _run_git(repo_root, ["status", "--porcelain"])
    return code == 0 and not out.strip()


def _current_branch_and_commit(repo_root: Path) -> tuple[str, str]:
    """Isolated as its own function so tests can monkeypatch git state
    directly, mirroring how test_context_librarian.py monkeypatches
    librarian._git_provenance rather than mocking subprocess calls."""
    branch_code, branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    commit_code, commit = _run_git(repo_root, ["rev-parse", "HEAD"])
    if branch_code != 0 or commit_code != 0:
        return "unknown", "unknown"
    return branch, commit


def _catalog_node_files(catalog: Catalog) -> dict[str, Path]:
    result: dict[str, Path] = {}
    paths = sorted((catalog.catalog_root / "layers").glob("*.json"))
    paths.append(catalog.catalog_root / "decisions/canonical_boundaries.json")
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        for node in data.get("nodes", []):
            result[node["id"]] = path
    return result


def _atomic_write_json_files(data_by_file: dict[Path, dict[str, Any]], original: dict[Path, str]) -> None:
    for path, data in data_by_file.items():
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        os.replace(temporary, path)


def _write_observed_commit(
    catalog: Catalog, main_sha: str, node_ids: list[str] | None = None
) -> list[str]:
    """Shared writer for last_observed_commit -- never adds/edits
    code_paths/test_paths/canonical_docs/edges, never a new node, and never
    last_verified_commit/last_semantic_review_commit. Callers are
    responsible for their own safety-invariant check before calling this;
    see stamp_observed() and apply_auto_maintenance() for the two current
    invariants (branch==main vs HEAD==canonical SHA + clean tree).

    Idempotent: a node already stamped at main_sha is left untouched.
    """
    target_ids = set(node_ids) if node_ids is not None else set(catalog.nodes)
    files = _catalog_node_files(catalog)
    original: dict[Path, str] = {}
    data_by_file: dict[Path, dict[str, Any]] = {}
    written: list[str] = []
    for node_id in sorted(target_ids):
        if node_id not in catalog.nodes:
            continue
        if catalog.nodes[node_id].get("last_observed_commit") == main_sha:
            continue
        path = files[node_id]
        if path not in data_by_file:
            original[path] = path.read_text(encoding="utf-8")
            data_by_file[path] = json.loads(original[path])
        for raw_node in data_by_file[path]["nodes"]:
            if raw_node["id"] == node_id:
                raw_node["last_observed_commit"] = main_sha
                written.append(node_id)
                break

    try:
        _atomic_write_json_files(data_by_file, original)
        load_catalog(catalog.repo_root)
    except Exception:
        for path, text in original.items():
            path.write_text(text, encoding="utf-8", newline="\n")
        raise
    return written


def stamp_observed(
    catalog: Catalog, main_sha: str, node_ids: list[str] | None = None
) -> list[str]:
    """Writes `last_observed_commit = main_sha` for the given nodes (default:
    every node). Requires the checkout to be on branch `main` at exactly
    `main_sha`, mirroring librarian.refresh_after_merge's existing write-path
    safety check: a provenance write from a detached HEAD or a feature
    branch would record a false claim about what `main` has been observed to
    contain. This is the manual/interactive entry point (CLI
    `reconcile --apply-observed`); apply_auto_maintenance() below uses the
    same shared writer with a different, CI-appropriate safety invariant.

    Returns the list of node ids actually written (idempotent).
    """
    branch, commit = _current_branch_and_commit(catalog.repo_root)
    if branch != "main" or commit != main_sha:
        raise ContextLibrarianError(
            "stamp_observed requires checkout branch main at exactly main_sha; "
            f"found branch={branch!r} commit={commit!r}"
        )
    return _write_observed_commit(catalog, main_sha, node_ids)


def _build_registration_plan(
    catalog: Catalog, auto_maintenance_sources: tuple[dict[str, Any], ...]
) -> list[tuple[str, str, str]]:
    """(target_node_id, target_field, path) triples to register, deterministically
    sorted and deduplicated, skipping anything already present (idempotent) and
    anything with no registerable target at all (mechanical-only policy match,
    e.g. DOCUMENTATION_REFERENCE_ASSET). reconcile()'s classification loop has
    already verified target existence/target_field validity for every item that
    reaches auto_maintenance_sources, so this is a pure, already-safe plan build."""
    plan: set[tuple[str, str, str]] = set()
    for item in auto_maintenance_sources:
        target = item.get("eligible_target")
        field = item.get("target_field")
        if target is None or field not in _REGISTERABLE_FIELDS:
            continue
        if target not in catalog.nodes:
            # Belt-and-braces: reconcile() already filters this case out of
            # auto_maintenance_sources, but a caller could hand this function
            # a hand-built result -- fail closed rather than KeyError.
            raise ContextLibrarianError(
                f"apply_auto_maintenance: target {target!r} does not exist in the "
                f"loaded catalog -- refusing to register {item['path']!r}"
            )
        if item["path"] in catalog.nodes[target][field]:
            continue
        plan.add((target, field, item["path"]))
    return sorted(plan)


def _apply_registration_plan(catalog: Catalog, plan: list[tuple[str, str, str]]) -> list[str]:
    if not plan:
        return []
    files = _catalog_node_files(catalog)
    original: dict[Path, str] = {}
    data_by_file: dict[Path, dict[str, Any]] = {}
    written: list[str] = []
    for target, field, path in plan:
        file_path = files[target]
        if file_path not in data_by_file:
            original[file_path] = file_path.read_text(encoding="utf-8")
            data_by_file[file_path] = json.loads(original[file_path])
        for raw_node in data_by_file[file_path]["nodes"]:
            if raw_node["id"] == target:
                if path not in raw_node[field]:
                    raw_node[field].append(path)
                    raw_node[field].sort()
                    written.append(f"{target}.{field}:{path}")
                break

    try:
        _atomic_write_json_files(data_by_file, original)
        load_catalog(catalog.repo_root)
    except Exception:
        for path, text in original.items():
            path.write_text(text, encoding="utf-8", newline="\n")
        raise
    return written


def apply_auto_maintenance(catalog: Catalog, result: ReconcileResult) -> dict[str, Any]:
    """The only bounded write path for AUTO_MAINTENANCE_REQUIRED. Performs,
    in order: (A) mechanical last_observed_commit bumps for drifted nodes,
    (C) policy-pre-approved registration of auto-maintenance sources into
    their declared target_field, then (B) advances last_source_scan_commit
    to the reconciled main SHA. B is last and unconditional on A/C succeeding
    (they raise on failure, rolling back their own file writes) so the scan
    baseline only ever advances past a window that was fully applied.

    Refuses outright unless result.outcome == AUTO_MAINTENANCE_REQUIRED --
    by construction that outcome never coexists with a non-empty
    decision_queue (OWNER_DECISION_REQUIRED always wins), so this can never
    silently skip an unresolved owner decision.

    Safety invariant is HEAD == the canonical main SHA this result was
    computed against, plus a clean working tree -- deliberately NOT "local
    branch literally named main" (stamp_observed's invariant): CI checkouts
    of a push-to-main event are not guaranteed to leave a branch named
    exactly "main" checked out, and this function is designed to run before
    any maintenance branch is created, not after.
    """
    if result.outcome != AUTO_MAINTENANCE_REQUIRED:
        raise ContextLibrarianError(
            f"apply_auto_maintenance requires outcome {AUTO_MAINTENANCE_REQUIRED}, "
            f"got {result.outcome}"
        )
    _, commit = _current_branch_and_commit(catalog.repo_root)
    if commit != result.canonical_main_sha:
        raise ContextLibrarianError(
            "apply_auto_maintenance requires HEAD to equal the canonical main SHA "
            f"(found {commit!r}, expected {result.canonical_main_sha!r})"
        )
    if not _working_tree_is_clean(catalog.repo_root):
        raise ContextLibrarianError("apply_auto_maintenance requires a clean working tree")

    drifted_node_ids = [u["node_id"] for u in result.mechanical_updates] or None
    stamped = _write_observed_commit(catalog, result.canonical_main_sha, drifted_node_ids)

    reloaded = load_catalog(catalog.repo_root)
    plan = _build_registration_plan(reloaded, result.auto_maintenance_sources)
    registered = _apply_registration_plan(reloaded, plan)

    write_source_scan_commit(catalog.catalog_root, result.canonical_main_sha)

    return {
        "stamped_nodes": stamped,
        "registered": registered,
        "source_scan_commit": result.canonical_main_sha,
    }
