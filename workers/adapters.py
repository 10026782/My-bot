"""Harness detection and the deliberately disabled pilot adapter."""

from __future__ import annotations

import shutil
import subprocess
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from .contracts import WorkerProfile, WorkerRequest, WorkerResult, WorkerStatus


_ENV_ALLOWLIST = ("PATH", "HOME", "TMPDIR", "TERM", "SHELL", "USER", "LOGNAME", "LANG")
_SECRET_MARKERS = (
    "API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL",
    "AIRTABLE", "RENDER", "TELEGRAM", "TWILIO",
)


def _child_environment() -> dict[str, str]:
    """Allowlist-based child env: unnamed variables never pass; secrets never pass."""
    env = {}
    for key, value in os.environ.items():
        if (key in _ENV_ALLOWLIST or key.startswith("LC_")) and not any(
            marker in key.upper() for marker in _SECRET_MARKERS
        ):
            env[key] = value
    return env


def _normalize(path: str) -> str:
    path = path.replace("\\", "/").strip().strip('"')
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/")


def _covers(path: str, pattern: str) -> bool:
    path, pattern = _normalize(path), _normalize(pattern)
    return bool(pattern) and (path == pattern or path.startswith(pattern + "/"))


def _paths_from_entry(entry: str) -> list[str]:
    body = entry[3:].strip()
    if " -> " in body:
        old, new = body.split(" -> ", 1)
        return [_normalize(old), _normalize(new)]
    return [_normalize(body)]


def _content_signature(path: Path) -> str:
    """SHA-256 over file content; mtime-independent change detection."""
    digest = sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_forbidden(
    repo_path: str,
    forbidden_paths: tuple[str, ...],
) -> dict[str, str] | None:
    """SHA-256 content-digest map of every existing file under forbidden prefixes.

    Content digests detect same-size rewrites with restored mtimes that
    stat-based signatures cannot. Covers gitignored paths that
    `git status --porcelain` cannot see. Returns None when a declared
    forbidden location exists but cannot be inspected or read (fail closed).
    """
    snapshot: dict[str, str] = {}
    try:
        base = Path(repo_path)
        for pattern in forbidden_paths:
            root = base / _normalize(pattern)
            if root.is_file():
                snapshot[_normalize(pattern)] = _content_signature(root)
            elif root.is_dir():
                for current, dirs, files in os.walk(root):
                    dirs[:] = [
                        d for d in dirs if not os.path.islink(os.path.join(current, d))
                    ]
                    for name in files:
                        path = Path(current) / name
                        key = str(path.relative_to(base)).replace("\\", "/")
                        snapshot[key] = _content_signature(path)
    except OSError:
        return None
    return snapshot


def _forbidden_changes(
    before: dict[str, str],
    after: dict[str, str],
) -> list[str]:
    created_or_modified = [p for p in after if before.get(p) != after[p]]
    deleted = [p for p in before if p not in after]
    return sorted(set(created_or_modified + deleted))


def _first_violation(
    repo_path: str,
    allowed_paths: tuple[str, ...],
    forbidden_paths: tuple[str, ...],
    forbidden_before: dict[str, str] | None = None,
) -> str | None:
    """Audit worktree changes; fail closed on audit failure.

    Two layers: (1) a pre/post SHA-256 content-digest diff over everything
    under forbidden_paths, which detects changes to gitignored files that
    git itself cannot report, independently of mtime; (2) `git status
    --porcelain` coverage for tracked and untracked changes against
    allowed_paths/forbidden_paths.

    Returns the first violation as a reportable string, or None when every
    changed path is inside bounds.
    """
    if forbidden_before is not None:
        after = _snapshot_forbidden(repo_path, forbidden_paths)
        if after is None:
            return "path_audit_unavailable"
        changes = _forbidden_changes(forbidden_before, after)
        if changes:
            return f"forbidden-ignored-change:{changes[0]}"
    try:
        completed = subprocess.run(
            ["git", "-C", repo_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=_child_environment(),
        )
    except (subprocess.TimeoutExpired, OSError):
        return "path_audit_unavailable"
    if completed.returncode != 0:
        return "path_audit_unavailable"
    for line in completed.stdout.splitlines():
        if len(line) <= 3 or not line[3:].strip():
            continue
        for path in _paths_from_entry(line):
            if any(_covers(path, pattern) for pattern in forbidden_paths):
                return f"forbidden-path:{path}"
            if not any(_covers(path, pattern) for pattern in allowed_paths):
                return f"path-outside-allowed:{path}"
    return None


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

        child_env = _child_environment()
        forbidden_before = _snapshot_forbidden(request.repo_path, request.forbidden_paths)
        if forbidden_before is None:
            return WorkerResult.blocked(request, profile.worker_id, "path_audit_unavailable")
        try:
            completed = subprocess.run(
                [self.executable, request.task],
                cwd=request.repo_path,
                capture_output=True,
                text=True,
                timeout=profile.timeout,
                check=False,
                env=child_env,
            )
        except subprocess.TimeoutExpired:
            return WorkerResult(
                request.request_id, profile.worker_id, WorkerStatus.TIMEOUT,
                summary="harness timed out", commands_run=[self.executable],
            )
        violation = _first_violation(
            request.repo_path, request.allowed_paths, request.forbidden_paths,
            forbidden_before,
        )
        if violation:
            if violation == "path_audit_unavailable":
                return WorkerResult.blocked(request, profile.worker_id, violation)
            return WorkerResult(
                request.request_id, profile.worker_id, WorkerStatus.FAILED,
                summary="path_boundary_violation", commands_run=[self.executable],
                exit_code=completed.returncode, evidence=[f"path-violation:{violation}"],
            )
        evidence = []
        test_results = {}
        commands_run = [self.executable]
        if completed.returncode == 0:
            for command in request.verification_commands:
                commands_run.append(command)
                try:
                    verification = subprocess.run(
                        command,
                        cwd=request.repo_path,
                        capture_output=True,
                        text=True,
                        timeout=profile.timeout,
                        check=False,
                        shell=True,
                        env=child_env,
                    )
                except subprocess.TimeoutExpired:
                    return WorkerResult(
                        request.request_id, profile.worker_id, WorkerStatus.TIMEOUT,
                        summary="verification timed out", commands_run=commands_run,
                    )
                test_results[command] = verification.returncode
                if verification.returncode != 0:
                    return WorkerResult(
                        request.request_id, profile.worker_id, WorkerStatus.FAILED,
                        summary="verification failed", commands_run=commands_run,
                        tests_run=list(request.verification_commands), test_results=test_results,
                        exit_code=completed.returncode,
                    )
                evidence.append(f"verification-executed:{command}")
        status = WorkerStatus.SUCCESS if completed.returncode == 0 else WorkerStatus.FAILED
        if status is WorkerStatus.SUCCESS:
            violation = _first_violation(
                request.repo_path, request.allowed_paths, request.forbidden_paths,
                forbidden_before,
            )
            if violation == "path_audit_unavailable":
                return WorkerResult.blocked(request, profile.worker_id, violation)
            if violation:
                return WorkerResult(
                    request.request_id, profile.worker_id, WorkerStatus.FAILED,
                    summary="path_boundary_violation", commands_run=commands_run,
                    tests_run=list(request.verification_commands), test_results=test_results,
                    exit_code=completed.returncode, evidence=[f"path-violation:{violation}"],
                )
        return WorkerResult(
            request_id=request.request_id,
            worker_id=profile.worker_id,
            status=status,
            summary="harness execution finished",
            commands_run=commands_run,
            tests_run=list(request.verification_commands),
            test_results=test_results,
            exit_code=completed.returncode,
            stdout_ref="captured://stdout",
            stderr_ref="captured://stderr",
            evidence=evidence,
        )
