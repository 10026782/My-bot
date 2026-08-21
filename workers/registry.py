"""Declarative worker profiles and fail-closed routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .adapters import HarnessAdapter, HarnessAvailability, SubprocessHarnessAdapter
from .contracts import Qualification, WorkerProfile, WorkerRequest, WorkerResult


INITIAL_PROFILES = (
    WorkerProfile("builder_qwen", "builder", "qwen", model="", qualification=Qualification.UNQUALIFIED),
    WorkerProfile("auditor_deepseek", "auditor", "opencode", model="", qualification=Qualification.UNQUALIFIED),
    WorkerProfile("reviewer_claude", "reviewer", "claude", model="", qualification=Qualification.UNQUALIFIED),
    WorkerProfile("researcher_kimi", "researcher", "kimi", model="", qualification=Qualification.UNQUALIFIED),
)


class WorkerRegistry:
    def __init__(self, profiles: tuple[WorkerProfile, ...] = INITIAL_PROFILES,
                 adapters: Mapping[str, HarnessAdapter] | None = None):
        self.profiles = {profile.worker_id: profile for profile in profiles}
        self.adapters = dict(adapters or {
            name: SubprocessHarnessAdapter(name) for name in ("claude", "opencode", "qwen", "kimi")
        })

    def availability(self) -> list[HarnessAvailability]:
        return [self.adapters[name].available() for name in sorted(self.adapters)]

    def get(self, worker_id: str) -> WorkerProfile:
        try:
            return self.profiles[worker_id]
        except KeyError:
            raise KeyError(f"unknown worker: {worker_id}") from None


@dataclass
class WorkerRouter:
    registry: WorkerRegistry

    def dry_run(self, request: WorkerRequest) -> WorkerResult:
        matches = [p for p in self.registry.profiles.values() if p.role == request.role]
        if not matches:
            return WorkerResult.blocked(request, "router", "no_worker_for_role")
        profile = matches[0]
        if profile.harness not in self.registry.adapters:
            return WorkerResult.blocked(request, profile.worker_id, "unknown_harness")
        return WorkerResult.blocked(request, profile.worker_id, "dry_run")

    def execute(self, request: WorkerRequest, worker_id: str) -> WorkerResult:
        profile = self.registry.get(worker_id)
        if profile.role != request.role:
            return WorkerResult.blocked(request, worker_id, "role_mismatch")
        adapter = self.registry.adapters.get(profile.harness)
        if adapter is None:
            return WorkerResult.blocked(request, worker_id, "unknown_harness")
        return adapter.execute(request, profile)
