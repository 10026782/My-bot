"""Mechanical, fail-closed Context Librarian catalog refresh after a merge.

Scope, deliberately narrow: this module only bumps `last_verified_commit`
for nodes whose *already-registered* code_paths/test_paths/canonical_docs
were touched between two commits. It never adds, removes, or edits a
canonical_docs/code_paths/edges/budget entry, and it never invents a new
node. Any change that would require a human judgment call --- a changed
file the catalog doesn't already claim, a catalog load failure (stale
reference, broken edge), or a refresh that would blow a profile's token
budget --- is reported as REVIEW_REQUIRED (or ERROR) and left untouched.

This is deliberately independent of librarian.py's private helpers so it
cannot silently drift if that module's internals move; the small amount of
matching/file-discovery logic it needs is duplicated here in a few lines
rather than imported.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from tools.context_librarian.librarian import (
    Catalog,
    ContextLibrarianError,
    estimate_bundle,
    load_catalog,
)


_TEST_FILENAME_PATTERN = re.compile(r"^test_[^/]+\.py$")


@dataclass(frozen=True)
class NodeRefresh:
    node_id: str
    old_commit: str
    new_commit: str
    matched_paths: tuple[str, ...]


@dataclass(frozen=True)
class ReviewItem:
    category: str
    detail: str


@dataclass(frozen=True)
class RefreshPlan:
    status: str  # "OK" | "REVIEW_REQUIRED" | "ERROR"
    new_commit: str
    refreshed: tuple[NodeRefresh, ...]
    review_required: tuple[ReviewItem, ...]
    error: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _catalog_files(catalog_root: Path) -> list[Path]:
    files = sorted((catalog_root / "layers").glob("*.json"))
    files.append(catalog_root / "decisions/canonical_boundaries.json")
    return files


def _matches_tracked_path(changed: str, tracked: str) -> bool:
    # Intentionally mirrors librarian.py's own `_matches_tracked_path()`
    # semantics (path-equality, glob, or directory-prefix). Duplicated
    # rather than imported: this module must not depend on librarian.py's
    # private surface.
    tracked = tracked.replace("\\", "/")
    return (
        changed == tracked
        or fnmatch.fnmatch(changed, tracked)
        or changed.startswith(tracked.rstrip("/") + "/")
    )


def _node_tracked_paths(node: dict[str, Any]) -> list[str]:
    paths = list(node["code_paths"]) + list(node["test_paths"])
    paths += [ref["path"] for ref in node["canonical_docs"]]
    return paths


def _claimed_directories(catalog: Catalog) -> set[str]:
    """Directories where at least one node already registers a path.

    Used only to flag a *new* file living alongside already-tracked files
    as worth a human look — never to auto-register it.
    """
    dirs: set[str] = set()
    for node in catalog.nodes.values():
        for p in node["code_paths"]:
            dirs.add(str(PurePosixPath(p).parent))
        for ref in node["canonical_docs"]:
            dirs.add(str(PurePosixPath(ref["path"]).parent))
    return dirs


def _known_test_paths(catalog: Catalog) -> set[str]:
    known: set[str] = set()
    for node in catalog.nodes.values():
        known.update(node["test_paths"])
    return known


def resolve_commit(repo_root: Path, ref: str) -> str:
    """Resolves a symbolic ref (`HEAD`, `HEAD~3`, `ORIG_HEAD`, a branch name)
    to a full commit SHA. Every commit this module writes into the catalog
    must be an actual hash — `last_verified_commit` fails schema validation
    (`^[0-9a-f]{7,40}$`) for anything else, and `git diff` against a moving
    ref like `HEAD` would silently mean something different on every call.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", ref],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContextLibrarianError(f"cannot resolve commit ref {ref!r}: {exc}") from exc
    return completed.stdout.strip()


def compute_changed_files(repo_root: Path, base_commit: str, head_commit: str) -> set[str]:
    try:
        completed = subprocess.run(
            ["git", "diff", "--name-only", base_commit, head_commit, "--"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContextLibrarianError(
            f"cannot diff {base_commit}..{head_commit}: {exc}"
        ) from exc
    return {
        line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()
    }


def _find_matching_nodes(
    catalog: Catalog, changed_files: set[str]
) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {}
    for node_id, node in catalog.nodes.items():
        tracked = _node_tracked_paths(node)
        hit = sorted(
            f for f in changed_files if any(_matches_tracked_path(f, t) for t in tracked)
        )
        if hit:
            matches[node_id] = hit
    return matches


def _find_unmapped_files(
    catalog: Catalog, changed_files: set[str], mapped_files: set[str]
) -> list[ReviewItem]:
    claimed_dirs = _claimed_directories(catalog)
    known_tests = _known_test_paths(catalog)
    items: list[ReviewItem] = []
    for changed in sorted(changed_files - mapped_files):
        name = PurePosixPath(changed).name
        if _TEST_FILENAME_PATTERN.match(name) and changed not in known_tests:
            items.append(
                ReviewItem(
                    category="unknown_test_file",
                    detail=(
                        f"{changed} looks like a test file but is not registered in "
                        "any node's test_paths"
                    ),
                )
            )
            continue
        parent = str(PurePosixPath(changed).parent)
        if parent in claimed_dirs:
            items.append(
                ReviewItem(
                    category="unknown_canonical_file",
                    detail=(
                        f"{changed} changed in {parent!r}, a directory the catalog "
                        "already tracks, but is not registered in any node's "
                        "code_paths/canonical_docs"
                    ),
                )
            )
    return items


def _replace_nodes(catalog: Catalog, nodes: dict[str, dict[str, Any]]) -> Catalog:
    return Catalog(
        repo_root=catalog.repo_root,
        catalog_root=catalog.catalog_root,
        node_schema=catalog.node_schema,
        edge_schema=catalog.edge_schema,
        nodes=nodes,
        edges=catalog.edges,
        profiles=catalog.profiles,
        layer_nodes=catalog.layer_nodes,
    )


def _check_budget_overflow(candidate_catalog: Catalog) -> list[ReviewItem]:
    """מבצעת dry-run-estimate לכל profile מול הקטלוג אחרי הרענון.

    משתמשת ב-`estimate_bundle()` (אותו render/measure ש-`build_bundle()`
    משתמש בו, רק שלא זורק שגיאה) כך שחריגת תקציב היא תוצאת `fits=False`
    מובנית ולא משהו שמפורש חזרה מתוך טקסט חריגה. כשל מבני (reference
    שבור, מצב git לא תקין) עדיין זורק שגיאה מ-`estimate_bundle()` עצמו
    ומדווח גם כן כאן — כשל freshness/validation על הנתונים המרועננים
    הוא בדיוק סוג הדבר שרענון מכני אסור לו לבלוע בשקט.
    """
    items: list[ReviewItem] = []
    for profile_id in sorted(candidate_catalog.profiles):
        try:
            result = estimate_bundle(candidate_catalog, task_type=profile_id, query="")
        except ContextLibrarianError as exc:
            items.append(
                ReviewItem(
                    category="post_refresh_build_error",
                    detail=f"profile {profile_id!r} fails to build after refresh: {exc}",
                )
            )
            continue
        if not result.fits:
            items.append(
                ReviewItem(
                    category="budget_overflow",
                    detail=(
                        f"profile {profile_id!r} needs approximately "
                        f"{result.actual_tokens} tokens after refresh, exceeding "
                        f"its {result.token_budget} budget"
                    ),
                )
            )
    return items


def plan_refresh(
    catalog: Catalog, *, changed_files: set[str], new_commit: str
) -> RefreshPlan:
    """Pure planning step — no disk writes, no git calls.

    Kept pure and side-effect-free so callers (tests, CI `--check`, the
    post-merge hook) can all exercise the exact same decision logic.
    """
    changed_files = {f.replace("\\", "/") for f in changed_files}
    node_matches = _find_matching_nodes(catalog, changed_files)
    mapped_files = {f for hits in node_matches.values() for f in hits}
    review = _find_unmapped_files(catalog, changed_files, mapped_files)

    refreshed: list[NodeRefresh] = []
    updated_nodes = copy.deepcopy(catalog.nodes)
    for node_id, hits in sorted(node_matches.items()):
        old_commit = catalog.nodes[node_id]["last_verified_commit"]
        if old_commit == new_commit:
            continue
        updated_nodes[node_id]["last_verified_commit"] = new_commit
        refreshed.append(
            NodeRefresh(
                node_id=node_id,
                old_commit=old_commit,
                new_commit=new_commit,
                matched_paths=tuple(hits),
            )
        )

    if refreshed:
        candidate_catalog = _replace_nodes(catalog, updated_nodes)
        review = review + _check_budget_overflow(candidate_catalog)

    status = "REVIEW_REQUIRED" if review else "OK"
    return RefreshPlan(
        status=status,
        new_commit=new_commit,
        refreshed=tuple(refreshed),
        review_required=tuple(review),
    )


def _locate_node_file(catalog_root: Path, node_id: str) -> Path | None:
    for path in _catalog_files(catalog_root):
        data = json.loads(path.read_text(encoding="utf-8"))
        for raw_node in data.get("nodes", []):
            if raw_node.get("id") == node_id:
                return path
    return None


def apply_refresh(catalog_root: Path, plan: RefreshPlan) -> None:
    """Writes only the mechanical `last_verified_commit` bumps in `plan.refreshed`.

    Never touches anything under `plan.review_required` — those are, by
    construction, never eligible nodes in `plan.refreshed` in the first
    place (see plan_refresh's disjoint mapped/unmapped split).
    """
    for item in plan.refreshed:
        path = _locate_node_file(catalog_root, item.node_id)
        if path is None:
            raise ContextLibrarianError(
                f"cannot locate catalog file for node {item.node_id!r}"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        found = False
        for raw_node in data.get("nodes", []):
            if raw_node.get("id") == item.node_id:
                raw_node["last_verified_commit"] = item.new_commit
                found = True
                break
        if not found:
            raise ContextLibrarianError(
                f"node {item.node_id!r} vanished from {path} between planning and apply"
            )
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def run_refresh(
    repo_root: Path, *, base_commit: str, head_commit: str, apply: bool
) -> RefreshPlan:
    try:
        resolved_base = resolve_commit(repo_root, base_commit)
        resolved_head = resolve_commit(repo_root, head_commit)
    except ContextLibrarianError as exc:
        return RefreshPlan(
            status="ERROR",
            new_commit=head_commit,
            refreshed=(),
            review_required=(),
            error=str(exc),
        )
    try:
        catalog = load_catalog(repo_root)
    except ContextLibrarianError as exc:
        return RefreshPlan(
            status="ERROR",
            new_commit=resolved_head,
            refreshed=(),
            review_required=(),
            error=str(exc),
        )
    try:
        changed_files = compute_changed_files(repo_root, resolved_base, resolved_head)
    except ContextLibrarianError as exc:
        return RefreshPlan(
            status="ERROR",
            new_commit=resolved_head,
            refreshed=(),
            review_required=(),
            error=str(exc),
        )
    plan = plan_refresh(catalog, changed_files=changed_files, new_commit=resolved_head)
    if apply and plan.refreshed:
        apply_refresh(catalog.catalog_root, plan)
    return plan


def _print_plan(plan: RefreshPlan) -> None:
    print(f"status: {plan.status}")
    if plan.error:
        print(f"error: {plan.error}")
    for item in plan.refreshed:
        matched = ", ".join(item.matched_paths)
        print(f"refreshed {item.node_id}: {item.old_commit} -> {item.new_commit} (matched: {matched})")
    for item in plan.review_required:
        print(f"REVIEW_REQUIRED [{item.category}]: {item.detail}")
    if plan.status == "OK" and not plan.refreshed:
        print("nothing to refresh")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.context_librarian.refresh_after_merge",
        description=(
            "Mechanically refresh last_verified_commit for catalog nodes whose "
            "already-registered paths changed between --base and --head. Never "
            "adds/removes/edits canonical_docs, code_paths, edges, or budgets — "
            "any change that would require that is reported as REVIEW_REQUIRED "
            "and left untouched."
        ),
    )
    parser.add_argument("--base", required=True, help="commit before the merge")
    parser.add_argument("--head", required=True, help="commit after the merge")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="report only; never writes (CI mode)"
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="write the mechanical refresh to disk (post-merge hook mode)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    apply = bool(args.apply) and not args.check
    plan = run_refresh(
        _repo_root(), base_commit=args.base, head_commit=args.head, apply=apply
    )
    _print_plan(plan)
    if plan.status == "ERROR":
        return 2
    if plan.status == "REVIEW_REQUIRED":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
