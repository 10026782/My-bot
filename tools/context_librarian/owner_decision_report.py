"""Formats decision_queue items (from reconcile()/reconcile_pr()) into the
compact "Owner Decision Request" block a human can act on directly from a CI
summary or PR comment, without opening raw JSON or logs. See
docs/context_librarian/RECONCILIATION.md section F.

This module is presentation only -- it never classifies anything itself. It
consumes exactly what tools/context_librarian/reconcile.py's
_route_new_sources() already computed (classification, policy_id/
eligible_target when a policy matched, and the new block_reason code), plus
a small amount of mechanical, best-effort evidence gathering (grep-based
caller detection, a path-based nearest-node heuristic). None of that
evidence is a semantic judgment -- "Recommended decision" is always a
suggestion for the owner to accept, edit, or reject, never a resolution.
Per RECONCILIATION.md: automation may propose a recommendation based on
evidence, but must never resolve OWNER_DECISION_REQUIRED itself.
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from tools.context_librarian.librarian import Catalog
from tools.context_librarian.reconcile import ReconcileResult

_MAX_CONSUMERS_SHOWN = 8

_SCHEMA_PERSISTENCE_EXTENSIONS = (".sql",)
_RUNTIME_EXTENSIONS = (".py", ".js", ".ts", ".tsx")
_DATA_EXTENSIONS = (".json", ".yaml", ".yml")


def _run_git(repo_root: Path, args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
    )
    return completed.returncode, completed.stdout.strip()


def find_consumers(repo_root: Path, path: str, *, limit: int = _MAX_CONSUMERS_SHOWN) -> list[str]:
    """Best-effort, mechanical caller/consumer scan -- a plain `git grep` for
    the module's importable name (for .py sources) or its basename
    (everything else) across tracked files, excluding the source itself.
    This is NOT proof of usage or non-usage (grep can both over- and
    under-match); it is deterministic, reproducible evidence for a human to
    weigh, matching every other mechanical signal this module produces.
    """
    posix = PurePosixPath(path)
    if posix.suffix == ".py":
        stem = posix.stem
        pattern = rf"(^|[^A-Za-z0-9_])(import {stem}|from {stem} import|from \.{stem} import)"
        code, out = _run_git(
            repo_root,
            ["grep", "-l", "-E", "--", pattern, "*.py"],
        )
    else:
        needle = posix.name
        code, out = _run_git(
            repo_root,
            ["grep", "-l", "-F", "--", needle, "*.py"],
        )
    if code not in (0, 1):  # 1 == no matches, still a clean run
        return []
    hits = [line.strip() for line in out.splitlines() if line.strip() and line.strip() != path]
    return sorted(hits)[:limit]


def _authority_signal(item: dict[str, Any]) -> str:
    """Mechanical heuristic only -- flags likely-affected concerns from the
    file's extension and classification, never a semantic read of its
    content. Always phrased as "may" -- confirming or ruling this out is
    exactly the owner's call, not this function's."""
    path = item["path"]
    ext = PurePosixPath(path).suffix.lower()
    signals: list[str] = []
    if ext in _SCHEMA_PERSISTENCE_EXTENSIONS:
        signals.append("persistence schema (.sql migration)")
    if item["classification"] == "STOP":
        signals.append(
            "authority/source-of-truth (filename matched an authority-term heuristic -- "
            "see librarian.py's _AUTHORITY_TERMS)"
        )
    if ext in _RUNTIME_EXTENSIONS:
        signals.append("runtime behavior (executable source, not data/docs)")
    if ext in _DATA_EXTENSIONS and item["classification"] != "STOP":
        signals.append("possibly persistence/config state (data file, role not yet determined)")
    if not signals:
        signals.append("not mechanically determined -- requires a human read of the file")
    return "; ".join(signals)


def _closest_target(item: dict[str, Any]) -> str:
    target = item.get("eligible_target")
    return target if target else "UNKNOWN"


def _recommend(item: dict[str, Any]) -> tuple[str, str, str]:
    """Returns (recommended_decision, alternative, risk_if_misclassified).
    Driven entirely by the block_reason code reconcile.py's
    _route_new_sources() already attached -- no re-derivation of the
    classification logic here (single source of truth stays reconcile.py)."""
    reason = item.get("block_reason", "NO_POLICY_MATCH")
    target = item.get("eligible_target")
    policy_id = item.get("policy_id")

    if reason == "AMBIGUOUS_POLICY_MATCH":
        return (
            "NEEDS OWNER REVIEW",
            "resolve which of the conflicting policies should own this path, or "
            "split it into a new node scoped to exactly this file",
            "an automatic pick could silently borrow a different class's "
            "authority boundary or precedence",
        )
    if reason == "NO_POLICY_MATCH":
        return (
            "NEEDS OWNER REVIEW",
            "create a new decision node scoped exactly to this file's class, or "
            "confirm it belongs to an existing node not yet reflected in the "
            "policy registry",
            "misclassifying an unregistered file forfeits the fail-closed "
            "guard the very next scan would otherwise re-apply -- it stays "
            "invisible to review until explicitly resolved",
        )
    if reason == "STOP_NEVER_AUTO":
        if target:
            return (
                "NEEDS OWNER REVIEW",
                f"APPROVE EXISTING NODE ({target}) once the file's actual authority "
                "scope is confirmed to match that node's boundary",
                "a STOP-classified file may govern authority/precedence -- approving "
                "the wrong node lets logic controlled by a different boundary "
                "silently claim this one's guarantees",
            )
        return (
            "NEEDS OWNER REVIEW",
            "CREATE NEW NODE scoped to this file, once its actual authority "
            "boundary is confirmed",
            "a STOP-classified file may govern authority/precedence -- approving "
            "without a confirmed boundary risks granting authority nothing "
            "reviewed",
        )
    if reason == "TARGET_NODE_MISSING":
        return (
            "CREATE NEW NODE",
            f"APPROVE EXISTING NODE ({target}) is not yet possible -- the policy "
            f"{policy_id!r} names this target but it doesn't exist as a loaded "
            "catalog node yet",
            "deferring creation risks a second, ad-hoc registration path "
            "emerging for the same class before this one is formalized",
        )
    if reason == "POLICY_REQUIRES_HUMAN_CONFIRMATION":
        return (
            "APPROVE EXISTING NODE" + (f": {target}" if target else ""),
            "REJECT if this specific file does not actually meet the policy's "
            f"stated characteristics ({policy_id!r} requires human confirmation "
            "by design, even on a path match)",
            "approving a file that doesn't truly meet the policy's narrow "
            "characteristics folds unrelated logic into an already-scoped "
            "boundary",
        )
    if reason in ("PREDICATE_FAILED", "PREDICATE_UNPROVABLE"):
        return (
            "NEEDS OWNER REVIEW",
            f"APPROVE EXISTING NODE ({target}) if manual review shows this is a "
            "predicate false negative; otherwise CREATE NEW NODE or REJECT",
            "approving despite a failed/unprovable structural predicate could "
            "register a file that doesn't actually satisfy the class's proven "
            "characteristics, silently widening it",
        )
    if reason == "TARGET_FIELD_INVALID":
        return (
            "NEEDS OWNER REVIEW",
            f"fix the policy registry entry for {policy_id!r} (its target_field "
            "is missing/invalid) in the same PR, then re-run reconcile",
            "this is a policy-registry authoring bug, not a file-classification "
            "question -- approving the file without fixing the policy leaves "
            "the same bug for the next matching path",
        )
    return (
        "NEEDS OWNER REVIEW",
        "no automatic recommendation available for this block_reason",
        "unrecognized block_reason -- treat conservatively and review manually",
    )


def format_owner_decision_request(repo_root: Path, item: dict[str, Any]) -> str:
    """Renders the exact structured block a human resolves per unregistered
    source -- one call per decision_queue item."""
    recommended, alternative, risk = _recommend(item)
    consumers = find_consumers(repo_root, item["path"])
    consumers_line = ", ".join(consumers) if consumers else "no mechanical matches found"
    target = _closest_target(item)
    policy_line = item.get("policy_id") or "none"
    if target == "UNKNOWN" and policy_line == "none":
        closest_line = "- closest existing catalog node/policy: none found"
    else:
        closest_line = f"- closest existing catalog node/policy: {target} (policy: {policy_line})"

    lines = [
        "OWNER DECISION REQUIRED",
        "",
        "Source:",
        item["path"],
        "",
        "Classification:",
        item["classification"],
        "",
        "Proposed target:",
        target,
        "",
        "Evidence:",
        f"- why runtime/schema/authority relevant: {item.get('reason', 'n/a')}",
        f"- current callers/consumers (mechanical grep, best-effort): {consumers_line}",
        f"- affected concerns (mechanical heuristic): {_authority_signal(item)}",
        closest_line,
        "",
        "Recommended decision:",
        recommended,
        "",
        "Alternative:",
        alternative,
        "",
        "Risk if classified incorrectly:",
        risk,
        "",
        "Required owner answer (reply in this PR with exactly one):",
        f"- APPROVE EXISTING NODE: {target if target != 'UNKNOWN' else '<node id>'}",
        "- APPROVE EXISTING NODE: <different existing node id>",
        "- CREATE NEW NODE: <proposed node name/id>",
        f"- REJECT: {item['path']} is not runtime/schema/authority relevant (state why)",
    ]
    return "\n".join(lines)


def format_pr_summary(result: ReconcileResult, repo_root: Path) -> str:
    """Compact, GitHub-Markdown PR-time summary -- readable from the GitHub
    UI without opening raw logs or JSON (RECONCILIATION.md section F / item
    11). States the result, every file needing an owner decision with its
    proposed classification, the exact bounded owner choices, and whether
    the PR is merge-blocked."""
    blocked = result.outcome == "OWNER_DECISION_REQUIRED"
    lines = [
        "## Context Librarian -- pre-merge reconciliation",
        "",
        f"**Result:** `{result.outcome}`",
        f"**Merge status:** {'BLOCKED -- resolve the owner decision(s) below' if blocked else 'not blocked by this gate'}",
        "",
    ]

    if result.decision_queue:
        lines.append(f"### {len(result.decision_queue)} source(s) require an owner decision")
        lines.append("")
        for item in result.decision_queue:
            lines.append(f"<details><summary><code>{item['path']}</code> -- {item['classification']}</summary>")
            lines.append("")
            lines.append("```")
            lines.append(format_owner_decision_request(repo_root, item))
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    if result.auto_maintenance_sources:
        lines.append(
            f"### {len(result.auto_maintenance_sources)} source(s) match an already-approved policy"
        )
        lines.append(
            "No owner decision needed -- these are covered by an existing "
            "`policy_registry.json` entry. Not applied by this PR-time gate "
            "(read-only); registration happens through the existing "
            "post-merge `--apply-auto` path."
        )
        for item in result.auto_maintenance_sources:
            lines.append(f"- `{item['path']}` -> policy `{item['policy_id']}`, target `{item['eligible_target']}`")
        lines.append("")

    if result.non_blocking_sources:
        lines.append(
            f"<details><summary>{len(result.non_blocking_sources)} non-blocking new source(s) "
            "(docs/tests/images/governance artifacts)</summary>"
            "\n\n" + "\n".join(f"- `{item['path']}` ({item['classification']})" for item in result.non_blocking_sources)
            + "\n\n</details>"
        )
        lines.append("")

    if not blocked and not result.decision_queue:
        lines.append("Nothing in this PR's own diff requires an owner decision.")

    lines.append("")
    lines.append(
        "_Base: `origin/main` @ "
        f"`{result.canonical_main_sha[:12]}`. This is the pre-merge gate -- "
        "post-merge reconciliation on `main` remains the final safety net "
        "and is unaffected by this result._"
    )
    return "\n".join(lines)
