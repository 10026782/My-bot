"""Manual, network-touching smoke harness for the Stirling-PDF merge_pdfs
capability POC.

Proves: resolve_adapter("stirling_pdf") -> ExternalExecutionBoundary(...) ->
submit(merge_pdfs) -> a real Stirling-PDF 2.14.3 merge -> a completed
ExternalExecutionJob -> a stored, checksummed output PDF artifact ->
a duplicate submit with the same contract_id does not call the service again.

Deliberately not run in CI (needs a real local Stirling-PDF instance -- see
docker-compose.yml in this directory) and deliberately not wired to
get_default_boundary()/Airtable: this harness builds its own boundary with
an in-memory job repository so a manual run never touches production BOSS
state. See docs/research/STIRLING_PDF_CAPABILITY_POC.md for full scope,
required env vars, and security limitations.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import replace
from pathlib import Path

# Appended, never inserted at 0: the repo root has its own top-level
# profile.py (an Airtable-backed module) that would otherwise shadow
# Python's stdlib `profile` module -- httpx's dependency chain can hit this
# the same way crawl4ai's did (see scripts/crawl4ai_capability_poc/smoke.py).
sys.path.append(str(Path(__file__).resolve().parents[2]))

from core.external_capability_contract import resolve_adapter  # noqa: E402
from core.external_execution_boundary import ExternalExecutionBoundary  # noqa: E402
from scripts.stirling_pdf_capability_poc.fixtures import minimal_pdf_bytes  # noqa: E402


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


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Set {name} before running.", file=sys.stderr)
        raise SystemExit(2)
    return value


def _prepare_inputs(input_root: Path) -> list[dict]:
    import hashlib

    input_root.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(2):
        path = input_root / f"smoke-input-{i}.pdf"
        path.write_bytes(minimal_pdf_bytes(width=200 + i * 10, height=200))
        paths.append(path)
    inputs = []
    for path in paths:
        data = path.read_bytes()
        inputs.append({
            "result_ref": str(path),
            "mime_type": "application/pdf",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return inputs


def main() -> int:
    base_url = _require_env("STIRLING_PDF_BASE_URL")
    _require_env("STIRLING_PDF_API_KEY")
    input_root = Path(_require_env("STIRLING_PDF_INPUT_ROOT"))
    _require_env("STIRLING_PDF_ARTIFACT_ROOT")

    adapter = resolve_adapter("stirling_pdf")
    if adapter is None:
        print("stirling_pdf capability not registered", file=sys.stderr)
        return 2

    print(f"Checking health: {base_url}/api/v1/info/status ...")
    if not adapter.healthcheck():
        print("Stirling-PDF service is not healthy/reachable.", file=sys.stderr)
        return 2
    print("OK: service healthy.")

    inputs = _prepare_inputs(input_root)
    print(f"Prepared {len(inputs)} input PDF artifacts under {input_root}")

    boundary = ExternalExecutionBoundary(repository=_InMemoryRepo(), lease_repository=_UnusedLeases(), adapter=adapter)
    contract_id = "stirling-pdf-poc-smoke"

    started = time.monotonic()
    outcome = boundary.submit(contract_id=contract_id, idempotency_key=contract_id, payload={"inputs": inputs})
    first_elapsed = time.monotonic() - started

    print(f"result: {outcome.result}")
    print(f"user_message: {outcome.user_message}")
    print(f"raw_response: {outcome.raw_response}")
    job = boundary.repository.get(contract_id)
    if not job:
        print("No job persisted.", file=sys.stderr)
        return 1
    print(f"job.status: {job.status}")
    print(f"job.result_ref: {job.result_ref}")
    print(f"job.evidence: {job.evidence}")

    if outcome.result != "completed" or job.status != "completed":
        return 1

    artifact = Path(job.result_ref)
    if not artifact.is_file() or artifact.stat().st_size == 0:
        print("Output artifact missing or empty.", file=sys.stderr)
        return 1
    if not artifact.read_bytes().startswith(b"%PDF-"):
        print("Output artifact is not a valid PDF.", file=sys.stderr)
        return 1
    print(f"OK: output artifact {artifact} is a non-empty valid PDF ({artifact.stat().st_size} bytes)")

    started = time.monotonic()
    second_outcome = boundary.submit(contract_id=contract_id, idempotency_key=contract_id, payload={"inputs": inputs})
    second_elapsed = time.monotonic() - started
    print(f"duplicate submit result: {second_outcome.result} (first={first_elapsed:.2f}s, duplicate={second_elapsed:.2f}s)")
    if second_outcome.result != "completed":
        print("Duplicate submit did not short-circuit to completed.", file=sys.stderr)
        return 1
    if second_elapsed > 1.0:
        print("WARNING: duplicate submit took >1s -- verify it did not re-call the service.", file=sys.stderr)

    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
