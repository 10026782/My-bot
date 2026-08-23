"""Deterministic current-state budget preflight for every context profile."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .librarian import (
    ContextLibrarianError,
    estimate_bundle,
)


ESTIMATOR_ID = "chars_div_4"

# Keep this as an ordered entry list rather than a dict so duplicate profile
# mappings fail closed instead of being silently overwritten.
CANONICAL_PROFILE_QUERY_ENTRIES: tuple[tuple[str, str, str], ...] = (
    (
        "approval_ux",
        "canonical-approval-ux-v1",
        "repeated approval returns the wrong message",
    ),
    (
        "tool_execution",
        "canonical-tool-execution-v1",
        "dispatcher reports success without execution evidence",
    ),
    (
        "turn_coordinator_routing",
        "canonical-turn-coordinator-routing-v1",
        "an explicit request routes to the wrong handler",
    ),
    (
        "core_reasoning_change",
        "canonical-core-reasoning-change-v1",
        "business outcome maps to the wrong reasoning state",
    ),
    (
        "rp5_evidence_mismatch",
        "canonical-rp5-evidence-mismatch-v1",
        "a completion claim conflicts with available evidence",
    ),
    (
        "ux_f52_message",
        "canonical-ux-f52-message-v1",
        "change a Telegram approval button's wording",
    ),
    (
        "cross_layer_architecture",
        "canonical-cross-layer-architecture-v1",
        "a change spans reasoning, routing, and approvals",
    ),
    (
        "marketing_change",
        "canonical-marketing-change-v1",
        "update a marketing creative production handoff",
    ),
)


@dataclass(frozen=True)
class CanonicalProfileQuery:
    profile: str
    query_id: str
    query: str


def canonical_profile_queries() -> tuple[CanonicalProfileQuery, ...]:
    """Return the validated, one-query-per-profile preflight mapping."""

    entries = tuple(CanonicalProfileQuery(*entry) for entry in CANONICAL_PROFILE_QUERY_ENTRIES)
    profiles = [entry.profile for entry in entries]
    query_ids = [entry.query_id for entry in entries]
    if len(profiles) != len(set(profiles)):
        raise ContextLibrarianError("duplicate canonical budget-preflight profile mapping")
    if len(query_ids) != len(set(query_ids)):
        raise ContextLibrarianError("duplicate canonical budget-preflight query_id mapping")
    if any(not entry.query_id or not entry.query for entry in entries):
        raise ContextLibrarianError("canonical budget-preflight query mapping is incomplete")
    return entries


def classify_health(headroom_percent: float) -> str:
    """Classify current headroom without changing any enforcement behavior."""

    if headroom_percent < 0:
        return "FAIL"
    if headroom_percent < 5:
        return "CRITICAL"
    if headroom_percent <= 10:
        return "WARN"
    return "PASS"


def _current_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContextLibrarianError(
            f"cannot determine current commit for budget preflight: {exc}"
        ) from exc
    commit = result.stdout.strip()
    if not commit:
        raise ContextLibrarianError("budget preflight current commit is empty")
    return commit


def _validate_profile_budget(profile_id: str, profile: dict[str, Any]) -> int:
    budget = profile.get("maximum_approximate_token_budget")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise ContextLibrarianError(
            f"profile {profile_id!r} has an invalid token budget"
        )
    return budget


def build_budget_preflight(repo_root: Path, catalog) -> dict[str, Any]:
    """Build a complete current-state report for every configured profile."""

    mappings = canonical_profile_queries()
    configured = set(catalog.profiles)
    mapped = {entry.profile for entry in mappings}
    missing = sorted(configured - mapped)
    unknown = sorted(mapped - configured)
    if missing:
        raise ContextLibrarianError(
            "missing canonical budget-preflight query for profile(s): "
            + ", ".join(missing)
        )
    if unknown:
        raise ContextLibrarianError(
            "canonical budget-preflight query references unknown profile(s): "
            + ", ".join(unknown)
        )
    if len(mappings) != len(configured):
        raise ContextLibrarianError(
            "budget preflight measured profile count does not match configured count"
        )

    commit = _current_commit(repo_root)
    rows: list[dict[str, Any]] = []
    for entry in sorted(mappings, key=lambda item: item.profile):
        profile = catalog.profiles[entry.profile]
        budget = _validate_profile_budget(entry.profile, profile)
        try:
            estimate = estimate_bundle(
                catalog,
                task_type=entry.profile,
                query=entry.query,
            )
        except Exception as exc:
            if isinstance(exc, ContextLibrarianError):
                raise ContextLibrarianError(
                    f"budget preflight could not estimate {entry.profile!r}: {exc}"
                ) from exc
            raise ContextLibrarianError(
                f"budget preflight could not estimate {entry.profile!r}: {exc}"
            ) from exc

        if estimate.token_budget != budget:
            raise ContextLibrarianError(
                f"budget preflight budget mismatch for {entry.profile!r}"
            )
        usage = estimate.actual_tokens
        headroom_tokens = budget - usage
        headroom_percent = (headroom_tokens / budget) * 100
        overflow_tokens = max(usage - budget, 0)
        row = {
            "profile": entry.profile,
            "budget": budget,
            "usage": usage,
            "headroom_tokens": headroom_tokens,
            "headroom_percent": round(headroom_percent, 2),
            "overflow_tokens": overflow_tokens,
            "fits": usage <= budget,
            "health": classify_health(headroom_percent),
            "estimator": ESTIMATOR_ID,
            "query_id": entry.query_id,
            "commit": commit,
        }
        _validate_row(row)
        rows.append(row)

    health_counts = {health: 0 for health in ("PASS", "WARN", "CRITICAL", "FAIL")}
    for row in rows:
        health_counts[row["health"]] += 1
    lowest = min(rows, key=lambda row: (row["headroom_tokens"], row["profile"]))
    report = {
        "estimator": ESTIMATOR_ID,
        "profiles": rows,
        "aggregate": {
            "total_profiles": len(rows),
            "pass_count": health_counts["PASS"],
            "warn_count": health_counts["WARN"],
            "critical_count": health_counts["CRITICAL"],
            "fail_count": health_counts["FAIL"],
            "lowest_headroom_profile": lowest["profile"],
            "lowest_headroom_tokens": lowest["headroom_tokens"],
        },
    }
    _validate_report(report, len(configured))
    return report


def _validate_row(row: dict[str, Any]) -> None:
    required = {
        "profile", "budget", "usage", "headroom_tokens", "headroom_percent",
        "overflow_tokens", "fits", "health", "estimator", "query_id", "commit",
    }
    if set(row) != required:
        raise ContextLibrarianError("budget preflight result schema is malformed")
    if row["estimator"] != ESTIMATOR_ID:
        raise ContextLibrarianError("budget preflight estimator is malformed")
    if row["fits"] != (row["usage"] <= row["budget"]):
        raise ContextLibrarianError("budget preflight fits value is malformed")
    if row["overflow_tokens"] != max(row["usage"] - row["budget"], 0):
        raise ContextLibrarianError("budget preflight overflow value is malformed")


def _validate_report(report: dict[str, Any], configured_count: int) -> None:
    if set(report) != {"estimator", "profiles", "aggregate"}:
        raise ContextLibrarianError("budget preflight report schema is malformed")
    if report["estimator"] != ESTIMATOR_ID:
        raise ContextLibrarianError("budget preflight report estimator is malformed")
    rows = report["profiles"]
    if not isinstance(rows, list) or len(rows) != configured_count:
        raise ContextLibrarianError("budget preflight did not measure every profile")
    for row in rows:
        _validate_row(row)
    aggregate = report["aggregate"]
    expected = {
        "total_profiles", "pass_count", "warn_count", "critical_count", "fail_count",
        "lowest_headroom_profile", "lowest_headroom_tokens",
    }
    if not isinstance(aggregate, dict) or set(aggregate) != expected:
        raise ContextLibrarianError("budget preflight aggregate schema is malformed")
    if aggregate["total_profiles"] != configured_count:
        raise ContextLibrarianError("budget preflight aggregate count is malformed")


def format_budget_preflight_table(report: dict[str, Any]) -> str:
    rows = report["profiles"]
    lines = [
        "profile\thealth\tusage/budget\theadroom\theadroom_percent\toverflow",
    ]
    for row in rows:
        lines.append(
            f"{row['profile']}\t{row['health']}\t"
            f"{row['usage']}/{row['budget']}\t{row['headroom_tokens']}\t"
            f"{row['headroom_percent']:.2f}%\t{row['overflow_tokens']}"
        )
    aggregate = report["aggregate"]
    lines.append(
        "aggregate\t"
        f"profiles={aggregate['total_profiles']} "
        f"pass={aggregate['pass_count']} "
        f"warn={aggregate['warn_count']} "
        f"critical={aggregate['critical_count']} "
        f"fail={aggregate['fail_count']}\t"
        f"lowest={aggregate['lowest_headroom_profile']} "
        f"({aggregate['lowest_headroom_tokens']} tokens)"
    )
    return "\n".join(lines)


def format_budget_preflight_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
