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

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.context_librarian import policy_validators
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
    update_auto_registrations,
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
    revalidation_flags: tuple[dict[str, Any], ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "main_ref": self.main_ref,
            "canonical_main_sha": self.canonical_main_sha,
            "mechanical_updates": list(self.mechanical_updates),
            "auto_maintenance_sources": list(self.auto_maintenance_sources),
            "decision_queue": list(self.decision_queue),
            "non_blocking_sources": list(self.non_blocking_sources),
            "revalidation_flags": list(self.revalidation_flags),
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


def _content_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_auto_registrations(
    catalog: Catalog, policies: tuple[Policy, ...], main_sha: str
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Read-only continuous-revalidation pass over every previously
    auto-registered path (Message E correction items 3/4/8) -- registration
    is not permanent proof, so this re-checks it every reconcile() call, not
    just once at registration time.

    Returns (stale_flags, refreshed_entries):
    - stale_flags: entries whose content/policy/validator changed AND no
      longer satisfy their policy's CURRENT predicate. These force
      reconcile()'s outcome to OWNER_DECISION_REQUIRED (never silently
      re-approved) and the path is never removed from its node's
      code_paths/test_paths by this function -- quarantine, not deletion;
      an owner resolves it explicitly.
    - refreshed_entries: entries whose content/policy/validator changed but
      STILL satisfy the current predicate -- the same approved contract,
      freshly re-proven, safe for apply_auto_maintenance to mechanically
      persist (never a new architectural decision, so this never touches
      last_semantic_review_commit).

    A policy_version bump on any policy is caught here automatically on the
    very next call, for every path ever registered under it -- POLICY
    CHANGE REVALIDATES HISTORY, not just future matches.
    """
    policies_by_id = {p.id: p for p in policies}
    state = load_reconciliation_state(catalog.catalog_root)
    stale: list[dict[str, Any]] = []
    refreshed: dict[str, dict[str, Any]] = {}
    for path, entry in sorted(state.get("auto_registrations", {}).items()):
        target = entry.get("target_node")
        field = entry.get("target_field")
        if target not in catalog.nodes or path not in catalog.nodes[target].get(field, []):
            # No longer registered anywhere this engine controls (manually
            # removed/reclassified elsewhere) -- out of scope for this pass.
            continue
        full_path = catalog.repo_root / path
        if not full_path.exists():
            stale.append({
                "path": path, "status": "STALE_REVALIDATION_REQUIRED",
                "previous_policy": entry.get("policy_id"),
                "failed_predicate": "registered file no longer exists on disk",
                "changed_commit": main_sha, "current_target": target,
            })
            continue
        current_hash = _content_hash(full_path)
        policy = policies_by_id.get(entry.get("policy_id"))
        unchanged = (
            policy is not None
            and current_hash == entry.get("content_hash")
            and policy.policy_version == entry.get("policy_version")
            and policy_validators.VALIDATOR_VERSION == entry.get("validator_version")
        )
        if unchanged:
            continue
        if policy is None:
            stale.append({
                "path": path, "status": "STALE_REVALIDATION_REQUIRED",
                "previous_policy": entry.get("policy_id"),
                "failed_predicate": "policy no longer exists in the registry",
                "changed_commit": main_sha, "current_target": target,
            })
            continue
        ok = policy_validators.validate_predicate(policy.id, catalog.repo_root, path)
        if ok is not True:
            stale.append({
                "path": path, "status": "STALE_REVALIDATION_REQUIRED",
                "previous_policy": entry.get("policy_id"),
                "policy_version_then": entry.get("policy_version"),
                "policy_version_now": policy.policy_version,
                "failed_predicate": (
                    "structural/content predicate failed" if ok is False
                    else "predicate could not be proven"
                ),
                "changed_commit": main_sha, "current_target": target,
            })
            continue
        refreshed[path] = {
            "policy_id": policy.id,
            "policy_version": policy.policy_version,
            "target_node": target,
            "target_field": field,
            "validated_at_commit": main_sha,
            "content_hash": current_hash,
            "validator_version": policy_validators.VALIDATOR_VERSION,
            "classification_mode": "AUTO",
        }
    return stale, refreshed


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
    stale_flags, refreshed_entries = _scan_auto_registrations(catalog, policies, main_sha)

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

        # Message E correction items 1/6: a path glob is candidate selection
        # only -- never sufficient by itself for runtime-consumed code. Fail
        # closed (route to decision_queue) unless the policy's deterministic
        # structural/content predicate proves the match, never inferring
        # purity/authority from filename, directory, or naming convention.
        predicate_result = policy_validators.validate_predicate(
            policy.id, catalog.repo_root, item["path"]
        )
        if predicate_result is not True:
            decision_queue.append(
                {**enriched, "policy_note": (
                    "policy structural/content predicate failed"
                    if predicate_result is False
                    else "policy structural/content predicate could not be proven"
                )}
            )
            continue

        auto_maintenance.append(enriched)

    if decision_queue or stale_flags:
        outcome = OWNER_DECISION_REQUIRED
    elif mechanical_updates or auto_maintenance or refreshed_entries:
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
        revalidation_flags=tuple(stale_flags),
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


def apply_auto_maintenance(
    catalog: Catalog, policies: tuple[Policy, ...], result: ReconcileResult
) -> dict[str, Any]:
    """The only bounded write path for AUTO_MAINTENANCE_REQUIRED. Performs,
    in order: (A) mechanical last_observed_commit bumps for drifted nodes,
    (C) policy-pre-approved registration of auto-maintenance sources into
    their declared target_field -- recording full classification provenance
    (policy_id, policy_version, classification_mode, validated_at_commit,
    content_hash, validator_version, target_node, target_field) for every
    newly registered path, plus a mechanical refresh of that same provenance
    for already-registered paths whose content/policy/validator drifted but
    still satisfy their policy's current predicate -- then (B) advances
    last_source_scan_commit to the reconciled main SHA. B is last and
    unconditional on A/C succeeding (they raise on failure, rolling back
    their own file writes) so the scan baseline only ever advances past a
    window that was fully applied.

    Never writes last_semantic_review_commit or last_verified_commit: a
    passing revalidation proves "this source still satisfies its
    previously-approved contract", never "the architectural contract itself
    was semantically re-approved" -- those two fields stay human-only.

    Refuses outright unless result.outcome == AUTO_MAINTENANCE_REQUIRED --
    by construction that outcome never coexists with a non-empty
    decision_queue OR any STALE_REVALIDATION_REQUIRED flag (both force
    OWNER_DECISION_REQUIRED), so this can never silently skip an unresolved
    owner decision or silently re-approve a source that stopped satisfying
    its policy.

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
    reloaded = load_catalog(catalog.repo_root) if registered else reloaded

    policies_by_id = {p.id: p for p in policies}
    sources_by_path = {item["path"]: item for item in result.auto_maintenance_sources}
    new_provenance: dict[str, dict[str, Any]] = {}
    for target, field, path in plan:
        item = sources_by_path[path]
        new_provenance[path] = {
            "policy_id": item["policy_id"],
            "policy_version": policies_by_id[item["policy_id"]].policy_version,
            "target_node": target,
            "target_field": field,
            "validated_at_commit": result.canonical_main_sha,
            "content_hash": _content_hash(catalog.repo_root / path),
            "validator_version": policy_validators.VALIDATOR_VERSION,
            "classification_mode": "AUTO",
        }

    # Mechanical refresh only -- _scan_auto_registrations() only returns a
    # path here if its predicate still passes under the CURRENT policy; a
    # failing one would already have forced result.outcome to
    # OWNER_DECISION_REQUIRED and this function would have refused above.
    _, refreshed_entries = _scan_auto_registrations(reloaded, policies, result.canonical_main_sha)

    if new_provenance or refreshed_entries:
        update_auto_registrations(catalog.catalog_root, {**new_provenance, **refreshed_entries})

    write_source_scan_commit(catalog.catalog_root, result.canonical_main_sha)

    return {
        "stamped_nodes": stamped,
        "registered": registered,
        "provenance_recorded": sorted(new_provenance),
        "provenance_refreshed": sorted(refreshed_entries),
        "source_scan_commit": result.canonical_main_sha,
    }
