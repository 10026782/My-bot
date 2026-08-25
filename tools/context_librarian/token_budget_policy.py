"""Policy and calibration metadata for Context Librarian token enforcement."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .librarian import ContextLibrarianError


POLICY_RELATIVE_PATH = Path("docs/context_librarian/token_budget_policy.json")
CALIBRATION_RELATIVE_PATH = Path("docs/context_librarian/token_calibration.json")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextLibrarianError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContextLibrarianError(f"{path} must contain an object")
    return value


def load_policy(repo_root: Path) -> dict[str, int | str]:
    path = repo_root / POLICY_RELATIVE_PATH
    value = _load_json(path)
    required = {
        "schema_version",
        "growth_signal_estimator",
        "small_overflow_warning_tokens",
        "hard_safety_overflow_tokens",
        "calibration_stale_after_days",
    }
    if set(value) != required or value["schema_version"] != "1.0":
        raise ContextLibrarianError(f"{path}: token budget policy schema is malformed")
    for field in (
        "small_overflow_warning_tokens",
        "hard_safety_overflow_tokens",
        "calibration_stale_after_days",
    ):
        if isinstance(value[field], bool) or not isinstance(value[field], int) or value[field] <= 0:
            raise ContextLibrarianError(f"{path}: {field} must be a positive integer")
    if value["growth_signal_estimator"] != "chars_div_4":
        raise ContextLibrarianError(f"{path}: unsupported growth signal estimator")
    if value["small_overflow_warning_tokens"] >= value["hard_safety_overflow_tokens"]:
        raise ContextLibrarianError(f"{path}: warning band must be below hard safety ceiling")
    return value


def load_calibration(repo_root: Path) -> dict[str, Any]:
    path = repo_root / CALIBRATION_RELATIVE_PATH
    value = _load_json(path)
    required = {"schema_version", "estimator", "freshness_days", "results"}
    if set(value) != required or value["schema_version"] != "1.0":
        raise ContextLibrarianError(f"{path}: calibration schema is malformed")
    if value["estimator"] != "anthropic_count_tokens":
        raise ContextLibrarianError(f"{path}: unsupported calibration estimator")
    if (
        isinstance(value["freshness_days"], bool)
        or not isinstance(value["freshness_days"], int)
        or value["freshness_days"] <= 0
    ):
        raise ContextLibrarianError(f"{path}: freshness_days must be a positive integer")
    if not isinstance(value["results"], list):
        raise ContextLibrarianError(f"{path}: results must be a list")
    required_result = {
        "model", "commit_sha", "timestamp", "profile", "character_count",
        "estimated_tokens", "real_counted_tokens", "observed_ratio", "safety_margin",
    }
    for result in value["results"]:
        if not isinstance(result, dict) or set(result) != required_result:
            raise ContextLibrarianError(f"{path}: calibration result schema is malformed")
        if not result["model"] or not result["commit_sha"] or not result["profile"]:
            raise ContextLibrarianError(f"{path}: calibration identity is incomplete")
        for field in ("character_count", "estimated_tokens", "real_counted_tokens"):
            if isinstance(result[field], bool) or not isinstance(result[field], int) or result[field] <= 0:
                raise ContextLibrarianError(f"{path}: {field} must be a positive integer")
        if not isinstance(result["observed_ratio"], (int, float)) or result["observed_ratio"] <= 0:
            raise ContextLibrarianError(f"{path}: observed_ratio must be positive")
        if not isinstance(result["safety_margin"], (int, float)) or result["safety_margin"] < 0:
            raise ContextLibrarianError(f"{path}: safety_margin must be non-negative")
        try:
            datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ContextLibrarianError(f"{path}: timestamp is invalid") from exc
    return value


def calibration_summary(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    policy = load_policy(repo_root)
    calibration = load_calibration(repo_root)
    if calibration["freshness_days"] != policy["calibration_stale_after_days"]:
        raise ContextLibrarianError(
            "token budget policy and calibration freshness windows disagree"
        )
    now = now or datetime.now(timezone.utc)
    results = calibration["results"]
    if not results:
        return {"status": "STALE", "latest_timestamp": None, "profiles": 0}
    latest = max(results, key=lambda item: item["timestamp"])
    latest_time = datetime.fromisoformat(latest["timestamp"].replace("Z", "+00:00"))
    age_days = (now - latest_time).total_seconds() / 86400
    status = "CURRENT" if age_days <= calibration["freshness_days"] else "STALE"
    return {
        "status": status,
        "latest_timestamp": latest["timestamp"],
        "profiles": len({item["profile"] for item in results}),
    }


def calibrated_estimate(repo_root: Path, profile: str, proxy_tokens: int) -> tuple[int | None, float | None]:
    results = [item for item in load_calibration(repo_root)["results"] if item["profile"] == profile]
    if not results:
        return None, None
    result = max(results, key=lambda item: item["timestamp"])
    ratio = float(result["observed_ratio"])
    return max(1, round(proxy_tokens * ratio)), ratio


def enforcement_for_overflow(
    repo_root: Path,
    overflow_tokens: int,
    *,
    explicit_budget: bool,
) -> tuple[str, int, str]:
    policy = load_policy(repo_root)
    hard_ceiling = policy["hard_safety_overflow_tokens"]
    if overflow_tokens <= 0:
        return "PASS", hard_ceiling, "INFO"
    if explicit_budget or overflow_tokens > hard_ceiling:
        return "BLOCK", hard_ceiling, "BLOCK"
    if overflow_tokens <= policy["small_overflow_warning_tokens"]:
        return "WARN", hard_ceiling, "WARN"
    return "WARN", hard_ceiling, "WARN"
