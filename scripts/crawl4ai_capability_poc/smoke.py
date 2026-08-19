"""Manual, network-touching smoke harness for the Crawl4AI capability POC.

Proves: resolve_adapter("crawl4ai") -> ExternalExecutionBoundary(...) ->
submit(...) -> a real Crawl4AI crawl -> a completed ExternalExecutionJob ->
a stored Markdown artifact.

Deliberately not run in CI (needs real network access and the isolated
crawl4ai dependency -- see requirements.txt in this directory) and
deliberately not wired to get_default_boundary()/Airtable: this harness
builds its own boundary with an in-memory job repository so a manual run
never touches production BOSS state. See
docs/research/CRAWL4AI_CAPABILITY_POC.md for full scope, security
limitations, and required env vars.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

# Appended, never inserted at 0: the repo root has its own top-level
# profile.py (an Airtable-backed module) that would otherwise shadow
# Python's stdlib `profile` module -- crawl4ai's own `import cProfile`
# transitively needs the real stdlib one.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from core.external_capability_contract import resolve_adapter  # noqa: E402
from core.external_execution_boundary import ExternalExecutionBoundary  # noqa: E402


class _InMemoryRepo:
    def __init__(self):
        self.jobs = {}

    def get(self, contract_id):
        job = self.jobs.get(contract_id)
        return replace(job) if job else None

    def create(self, job):
        self.jobs[job.contract_id] = replace(job)

    def update(self, job):
        self.jobs[job.contract_id] = replace(job)

    def list_for_adapter(self, adapter_name):
        return [j for j in self.jobs.values() if j.adapter_name == adapter_name]


class _UnusedLeases:
    """Sync completion never enters poll_due(); leases are never touched."""

    def acquire(self, *a, **k):
        raise AssertionError("poll_due() should never run for a sync-completed job")

    def release(self, *a, **k):
        raise AssertionError("poll_due() should never run for a sync-completed job")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--contract-id", default="crawl4ai-poc-smoke")
    args = parser.parse_args()

    if not os.environ.get("CRAWL4AI_ALLOWED_HOSTS"):
        print("Set CRAWL4AI_ALLOWED_HOSTS (comma-separated exact hostnames) before running.", file=sys.stderr)
        return 2
    if not os.environ.get("CRAWL4AI_ARTIFACT_ROOT"):
        print("Set CRAWL4AI_ARTIFACT_ROOT (a local directory) before running.", file=sys.stderr)
        return 2

    adapter = resolve_adapter("crawl4ai")
    if adapter is None:
        print("crawl4ai capability not registered", file=sys.stderr)
        return 2

    boundary = ExternalExecutionBoundary(repository=_InMemoryRepo(), lease_repository=_UnusedLeases(), adapter=adapter)
    outcome = boundary.submit(contract_id=args.contract_id, idempotency_key=args.contract_id, payload={"url": args.url})

    print(f"result: {outcome.result}")
    print(f"user_message: {outcome.user_message}")
    print(f"raw_response: {outcome.raw_response}")
    job = boundary.repository.get(args.contract_id)
    if job:
        print(f"job.status: {job.status}")
        print(f"job.result_ref: {job.result_ref}")
        print(f"job.evidence: {job.evidence}")
    return 0 if outcome.result == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
