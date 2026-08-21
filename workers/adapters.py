"""Harness detection and the deliberately disabled pilot adapter."""

from __future__ import annotations

import shutil
import subprocess
import os
from dataclasses import dataclass
from typing import Protocol

from .contracts import WorkerProfile, WorkerRequest, WorkerResult, WorkerStatus


@dataclass(frozen=True)
class HarnessAvailability:
    harness: str
    available: bool
    executable: str | None = None


class HarnessAdapter(Protocol):
    harness: str

    def available(self) -> HarnessAvailability: ...

    def execute(self, request: WorkerRequest, profile: WorkerProfile) -> WorkerResult: ...


class SubprocessHarnessAdapter:
    """Generic adapter; no provider SDK and no installation side effect."""

    def __init__(self, harness: str, *, executable: str | None = None, allow_execution: bool = False):
        self.harness = harness
        self.executable = executable or harness
        self.allow_execution = allow_execution

    def available(self) -> HarnessAvailability:
        path = shutil.which(self.executable)
        return HarnessAvailability(self.harness, path is not None, path)

    def execute(self, request: WorkerRequest, profile: WorkerProfile) -> WorkerResult:
        if not self.available().available:
            return WorkerResult.blocked(request, profile.worker_id, "harness_not_installed")
        if not self.allow_execution:
            return WorkerResult.blocked(request, profile.worker_id, "worker_execution_disabled")
        if not profile.enabled:
            return WorkerResult.blocked(request, profile.worker_id, "worker_disabled")
        if profile.qualification not in ("pilot", "qualified"):
            return WorkerResult.blocked(request, profile.worker_id, "worker_unqualified")
        if profile.permission_profile != "development_isolated_worktree":
            return WorkerResult.blocked(request, profile.worker_id, "unsafe_permission_profile")

        safe_env = {
            key: value for key, value in os.environ.items()
            if not any(marker in key.upper() for marker in (
                "API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL",
                "AIRTABLE", "RENDER", "TELEGRAM", "TWILIO",
            ))
        }
        try:
            completed = subprocess.run(
                [self.executable, request.task],
                cwd=request.repo_path,
                capture_output=True,
                text=True,
                timeout=profile.timeout,
                check=False,
                env=safe_env,
            )
        except subprocess.TimeoutExpired:
            return WorkerResult.blocked(request, profile.worker_id, "timeout")
        status = WorkerStatus.SUCCESS if completed.returncode == 0 else WorkerStatus.FAILED
        return WorkerResult(
            request_id=request.request_id,
            worker_id=profile.worker_id,
            status=status,
            summary="harness execution finished",
            commands_run=[self.executable],
            exit_code=completed.returncode,
            stdout_ref="captured://stdout",
            stderr_ref="captured://stderr",
            evidence=list(request.verification_commands) if status is WorkerStatus.SUCCESS else [],
        )
