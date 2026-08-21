"""Small, provider-independent contracts for development workers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping


class Qualification(StrEnum):
    UNQUALIFIED = "unqualified"
    PILOT = "pilot"
    QUALIFIED = "qualified"
    DISABLED = "disabled"


class WorkerStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    INVALID_RESULT = "invalid_result"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkerProfile:
    worker_id: str
    role: str
    harness: str
    model: str = ""
    provider: str = ""
    enabled: bool = False
    permission_profile: str = "development_read_only"
    timeout: int = 300
    working_directory_policy: str = "isolated_worktree"
    qualification: Qualification = Qualification.UNQUALIFIED

    def __post_init__(self) -> None:
        if not self.worker_id or not self.role or not self.harness:
            raise ValueError("worker_id, role, and harness are required")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration only; secrets have no field here."""
        return asdict(self)


@dataclass(frozen=True)
class WorkerRequest:
    request_id: str
    task: str
    role: str
    repo_path: str
    base_ref: str = "HEAD"
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    verification_commands: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id or not self.task or not self.repo_path:
            raise ValueError("request_id, task, and repo_path are required")
        if not self.allowed_paths:
            raise ValueError("allowed_paths must explicitly bound repository changes")


@dataclass
class WorkerResult:
    request_id: str
    worker_id: str
    status: WorkerStatus
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    tests_run: list[str] = field(default_factory=list)
    test_results: Mapping[str, Any] = field(default_factory=dict)
    stdout_ref: str | None = None
    stderr_ref: str | None = None
    exit_code: int | None = None
    started_at: str = field(default_factory=_now)
    finished_at: str = field(default_factory=_now)
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.status = WorkerStatus(self.status)
        if self.status is WorkerStatus.SUCCESS and (
            self.exit_code != 0 or not self.evidence
        ):
            self.status = WorkerStatus.INVALID_RESULT

    @classmethod
    def blocked(cls, request: WorkerRequest, worker_id: str, reason: str) -> "WorkerResult":
        return cls(request.request_id, worker_id, WorkerStatus.BLOCKED, summary=reason)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result
