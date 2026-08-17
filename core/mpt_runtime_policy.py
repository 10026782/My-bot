"""Bounded operational policy for MoneyPrinterTurbo executions."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone


RETRYABLE_FAILURES = frozenset({"TRANSIENT_TTS", "TRANSIENT_NETWORK"})
NEVER_RETRY_FAILURES = frozenset({
    "RESOURCE_LIMIT", "INVALID_INPUT", "ARTIFACT_VALIDATION_FAILED",
    "OUTCOME_UNKNOWN", "AUTH_FAILURE",
})


@dataclass(frozen=True)
class MPTExecutionPolicy:
    max_concurrent: int = 1
    max_per_day: int = 1
    max_runtime_seconds: int | None = 1800
    runtime_profile: str = ""

    @classmethod
    def from_env(cls) -> "MPTExecutionPolicy":
        raw_minutes = os.environ.get("MPT_MAX_RUNTIME_MINUTES", "30").strip()
        try:
            minutes = max(1, int(raw_minutes))
        except ValueError:
            minutes = 30
        return cls(
            max_concurrent=max(1, _int_env("MPT_MAX_CONCURRENT_EXECUTIONS", 1)),
            max_per_day=max(1, _int_env("MPT_MAX_EXECUTIONS_PER_DAY", 1)),
            max_runtime_seconds=minutes * 60 if raw_minutes else None,
            runtime_profile=os.environ.get("MPT_RUNTIME_PROFILE", "").strip().lower(),
        )

    def runtime_supported(self, *, render_plan_id: str = "") -> bool:
        profile = self.runtime_profile or render_plan_id.strip().lower()
        if not profile:
            return True  # unknown runtime: adapter performs its own safe checks
        return profile in {"standard-2gb", "render-standard-2gb", "plan-srv-008"}

    def active_count(self, jobs) -> int:
        return sum(1 for job in jobs if job.adapter_name == "moneyprinterturbo" and job.status == "submitted")

    def daily_count(self, jobs, *, now: float | None = None) -> int:
        now = time.time() if now is None else now
        today = datetime.fromtimestamp(now, timezone.utc).date()
        count = 0
        for job in jobs:
            if job.adapter_name != "moneyprinterturbo":
                continue
            stamp = job.submitted_at or job.completed_at
            if stamp is not None and datetime.fromtimestamp(float(stamp), timezone.utc).date() == today:
                count += 1
        return count

    def capacity_available(self, jobs, *, now: float | None = None) -> bool:
        return self.active_count(jobs) < self.max_concurrent and self.daily_count(jobs, now=now) < self.max_per_day

    def capacity_reason(self, jobs, *, now: float | None = None) -> str:
        if self.active_count(jobs) >= self.max_concurrent:
            return "MPT_CONCURRENCY_LIMIT"
        if self.daily_count(jobs, now=now) >= self.max_per_day:
            return "MPT_DAILY_LIMIT"
        return ""

    def retry_allowed(self, classification: str, retry_count: int) -> bool:
        return classification in RETRYABLE_FAILURES and retry_count < 1


def classify_failure(*, exit_code: int | None = None, failure_code: str = "") -> str:
    code = failure_code.lower()
    if exit_code in {-9, 137} or "resource" in code or "sigkill" in code:
        return "RESOURCE_LIMIT"
    if exit_code in {-15, 143} or "timeout" in code:
        return "TIMEOUT"
    if "auth" in code or "permission" in code:
        return "AUTH_FAILURE"
    if "network" in code:
        return "TRANSIENT_NETWORK"
    if "tts" in code:
        return "TRANSIENT_TTS"
    if "artifact" in code or "ffprobe" in code:
        return "ARTIFACT_VALIDATION_FAILED"
    if "invalid" in code or "input" in code:
        return "INVALID_INPUT"
    if "unknown" in code or not failure_code:
        return "OUTCOME_UNKNOWN"
    return "MEDIA_VALIDATION_FAILED"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default
