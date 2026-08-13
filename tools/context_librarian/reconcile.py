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
(c) reports what still needs a human. It never adds/edits code_paths,
canonical_docs, edges, or catalog nodes -- see stamp_observed()'s docstring
for the one thing it IS allowed to write.
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
    load_catalog,
    refresh_proposal,
)
from tools.context_librarian.policy_registry import Policy, load_policy_registry, match_policy


CLEAN = "CLEAN"
# Intentionally duplicated from librarian.py's own private
# _NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS rather than imported, mirroring
# refresh_after_merge.py's existing precedent of not depending on that
# module's private surface (see its own module docstring).
_NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS = frozenset({"WARNING", "GOVERNANCE_ARTIFACT"})
AUTO_MAINTENANCE_REQUIRED = "AUTO_MAINTENANCE_REQUIRED"
OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"


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


def reconcile(
    catalog: Catalog, policies: tuple[Policy, ...], *, main_ref: str = "origin/main"
) -> ReconcileResult:
    """Pure classification -- no disk writes, no git writes.

    Reuses refresh_proposal() for updates/new_sources exactly as
    `refresh-after-merge --check` does, then re-routes each blocking
    new_source through the policy registry instead of leaving every one of
    them as an undifferentiated REVIEW_REQUIRED/STOP.
    """
    proposal = refresh_proposal(catalog, main_ref=main_ref)

    auto_maintenance: list[dict[str, Any]] = []
    decision_queue: list[dict[str, Any]] = []
    non_blocking: list[dict[str, Any]] = []

    for item in proposal["new_sources"]:
        classification = item["classification"]
        if classification in _NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS:
            non_blocking.append(item)
            continue

        policy = match_policy(item["path"], policies)
        # STOP is never eligible for auto-maintenance, full stop -- even if a
        # future policy were mis-authored to match an authority-sounding
        # path, an unregistered source that tripped the authority-term
        # escalation always requires a human decision. This is a structural
        # guarantee, not a registry-authoring convention.
        if classification != "STOP" and policy is not None and policy.auto_registration_allowed:
            auto_maintenance.append(
                {**item, "policy_id": policy.id, "eligible_target": policy.eligible_target}
            )
        elif policy is not None:
            decision_queue.append(
                {
                    **item,
                    "policy_id": policy.id,
                    "eligible_target": policy.eligible_target,
                    "policy_note": (
                        "matches a known policy class but that policy requires human "
                        "confirmation before registration (auto_registration_allowed=false)"
                    ),
                }
            )
        else:
            decision_queue.append(item)

    if decision_queue:
        outcome = OWNER_DECISION_REQUIRED
    elif proposal["updates"] or auto_maintenance:
        outcome = AUTO_MAINTENANCE_REQUIRED
    else:
        outcome = CLEAN

    return ReconcileResult(
        outcome=outcome,
        main_ref=main_ref,
        canonical_main_sha=proposal["canonical_main_sha"],
        mechanical_updates=tuple(proposal["updates"]),
        auto_maintenance_sources=tuple(auto_maintenance),
        decision_queue=tuple(decision_queue),
        non_blocking_sources=tuple(non_blocking),
    )


def reconcile_repo(repo_root: Path, *, main_ref: str = "origin/main") -> ReconcileResult:
    catalog = load_catalog(repo_root)
    policies = load_policy_registry(repo_root)
    return reconcile(catalog, policies, main_ref=main_ref)


def _run_git(repo_root: Path, args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
    )
    return completed.returncode, completed.stdout.strip()


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


def stamp_observed(
    catalog: Catalog, main_sha: str, node_ids: list[str] | None = None
) -> list[str]:
    """Writes `last_observed_commit = main_sha` for the given nodes (default:
    every node). This is the ONLY thing this module ever writes to a catalog
    file -- never code_paths/test_paths/canonical_docs/edges, never a new
    node, and never `last_verified_commit`/`last_semantic_review_commit`
    (those remain librarian.refresh_after_merge's and a human's territory,
    respectively -- see NODE_FIELDS's docstring in librarian.py).

    Requires the checkout to be on branch `main` at exactly `main_sha`,
    mirroring librarian.refresh_after_merge's write-path safety check: a
    provenance write from a detached HEAD or a feature branch would record
    a false claim about what `main` has been observed to contain.

    Returns the list of node ids actually written (idempotent: a node
    already stamped at main_sha is left untouched and excluded).
    """
    branch, commit = _current_branch_and_commit(catalog.repo_root)
    if branch != "main" or commit != main_sha:
        raise ContextLibrarianError(
            "stamp_observed requires checkout branch main at exactly main_sha; "
            f"found branch={branch!r} commit={commit!r}"
        )

    target_ids = set(node_ids) if node_ids is not None else set(catalog.nodes)
    files = _catalog_node_files(catalog)
    original: dict[Path, str] = {}
    data_by_file: dict[Path, dict[str, Any]] = {}
    written: list[str] = []
    for node_id in sorted(target_ids):
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
        for path, data in data_by_file.items():
            payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
            ) as handle:
                handle.write(payload)
                temporary = Path(handle.name)
            os.replace(temporary, path)
        load_catalog(catalog.repo_root)
    except Exception:
        for path, text in original.items():
            path.write_text(text, encoding="utf-8", newline="\n")
        raise
    return written
