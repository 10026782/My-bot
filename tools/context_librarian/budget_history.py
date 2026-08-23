"""Persistent, append-only history for Context Librarian budget snapshots."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .librarian import ContextLibrarianError


HISTORY_SCHEMA_VERSION = "1.0"


def _load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": HISTORY_SCHEMA_VERSION, "snapshots": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextLibrarianError(f"cannot load budget history {path}: {exc}") from exc
    _validate_history(value)
    return value


def _validate_history(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"schema_version", "snapshots"}:
        raise ContextLibrarianError("budget history schema is malformed")
    if value["schema_version"] != HISTORY_SCHEMA_VERSION:
        raise ContextLibrarianError("unsupported budget history schema version")
    snapshots = value["snapshots"]
    if not isinstance(snapshots, list):
        raise ContextLibrarianError("budget history snapshots must be a list")
    commits: set[str] = set()
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "commit", "estimator", "profiles", "aggregate"
        }:
            raise ContextLibrarianError("budget history snapshot schema is malformed")
        commit = snapshot["commit"]
        if not isinstance(commit, str) or not commit or commit in commits:
            raise ContextLibrarianError("budget history contains an invalid or duplicate commit")
        commits.add(commit)
        if not isinstance(snapshot["profiles"], list):
            raise ContextLibrarianError("budget history snapshot profiles must be a list")
        if not isinstance(snapshot["aggregate"], dict):
            raise ContextLibrarianError("budget history snapshot aggregate must be an object")


def _changed_paths(repo_root: Path, previous_commit: str | None, commit: str) -> list[str]:
    if not previous_commit:
        return []
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_root), "diff", "--name-only",
                f"{previous_commit}..{commit}", "--",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContextLibrarianError(
            f"cannot determine budget history changed paths: {exc}"
        ) from exc
    return sorted(path for path in result.stdout.splitlines() if path)


def _profile_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["profile"]: row for row in snapshot["profiles"]}


def _cause(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    if previous is None:
        return "initial"
    if current["estimator"] != previous["estimator"]:
        return "estimator_change"
    if current["budget"] != previous["budget"]:
        return "budget_change"
    if current["usage"] > previous["usage"]:
        return "growth"
    return "no_growth"


def _enrich_snapshot(
    report: dict[str, Any], previous: dict[str, Any] | None, changed_paths: list[str]
) -> tuple[dict[str, Any], list[str]]:
    previous_profiles = _profile_map(previous) if previous else {}
    rows: list[dict[str, Any]] = []
    growth_breaks: list[str] = []
    for row in report["profiles"]:
        old = previous_profiles.get(row["profile"])
        cause = _cause(old, row)
        usage_delta = row["usage"] - old["usage"] if old else None
        budget_delta = row["budget"] - old["budget"] if old else None
        # A break is a transition from fitting to overflowing caused by content
        # growth. Repeated observations of the same overflow are not new breaks.
        growth_break = bool(
            old
            and cause == "growth"
            and old["fits"]
            and not row["fits"]
        )
        if growth_break:
            growth_breaks.append(row["profile"])
        prior_break_count = old.get("growth_break_count", 0) if old else 0
        enriched = dict(row)
        enriched.update(
            {
                "previous_usage": old["usage"] if old else None,
                "usage_delta": usage_delta,
                "budget_delta": budget_delta,
                "previous_commit": previous["commit"] if previous else None,
                "changed_paths": changed_paths,
                "cause": cause,
                "growth_break": growth_break,
                "growth_break_count": prior_break_count + int(growth_break),
            }
        )
        rows.append(enriched)
    return {
        "commit": report["profiles"][0]["commit"],
        "estimator": report["estimator"],
        "profiles": rows,
        "aggregate": report["aggregate"],
    }, growth_breaks


def record_budget_snapshot(
    repo_root: Path, report: dict[str, Any], history_path: Path
) -> dict[str, Any]:
    """Append one commit snapshot and return recording metadata.

    Recording is idempotent for a commit: repeated runs against the same
    commit do not create duplicate snapshots or artificial growth breaks.
    """

    path = history_path if history_path.is_absolute() else repo_root / history_path
    history = _load_history(path)
    current_commit = report["profiles"][0]["commit"] if report["profiles"] else None
    if not current_commit:
        raise ContextLibrarianError("cannot record an empty budget preflight report")
    existing = next(
        (snapshot for snapshot in history["snapshots"] if snapshot["commit"] == current_commit),
        None,
    )
    if existing is not None:
        return {
            "snapshot_added": False,
            "snapshot_count": len(history["snapshots"]),
            "current_commit": current_commit,
            "previous_commit": None,
            "growth_breaks": [],
            "growth_break_counts": {
                row["profile"]: row.get("growth_break_count", 0)
                for row in existing["profiles"]
            },
        }

    previous = history["snapshots"][-1] if history["snapshots"] else None
    changed_paths = _changed_paths(
        repo_root,
        previous["commit"] if previous else None,
        current_commit,
    )
    snapshot, growth_breaks = _enrich_snapshot(report, previous, changed_paths)
    history["snapshots"].append(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "snapshot_added": True,
        "snapshot_count": len(history["snapshots"]),
        "current_commit": current_commit,
        "previous_commit": previous["commit"] if previous else None,
        "growth_breaks": growth_breaks,
        "growth_break_counts": {
            row["profile"]: row["growth_break_count"]
            for row in snapshot["profiles"]
        },
    }
