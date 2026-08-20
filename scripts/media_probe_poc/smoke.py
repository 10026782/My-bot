"""Manual, real-ffprobe smoke harness for the Media Probe capability POC.

Proves: a tiny synthesized (not downloaded) media fixture -> governed
artifact metadata (result_ref/mime_type/size/sha256) -> resolve_adapter
("media_probe") -> ExternalExecutionBoundary.submit(...) -> a real ffprobe
invocation -> normalized metadata -> a stored JSON result artifact, then
independently re-verifies the result checksum, confirms the source file
was never touched, and confirms a duplicate submit does not re-invoke
ffprobe.

Deliberately not run in CI (needs a real ffprobe binary on PATH — CI has
none, matching this capability's "ffprobe not installed -> failed" test
path) and deliberately not wired to get_default_boundary()/Airtable: this
harness builds its own boundary with an in-memory job repository so a
manual run never touches production BOSS state. See
docs/research/MEDIA_PROBE_POC.md for full scope.

Usage (ffprobe must be on PATH — e.g. via system ffmpeg, or a user-local
`pip install --user static-ffmpeg` plus `static_ffmpeg.add_paths()`):

    MEDIA_PROBE_INPUT_ROOT=/tmp/mp_in MEDIA_PROBE_ARTIFACT_ROOT=/tmp/mp_out \
        python3 scripts/media_probe_poc/smoke.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

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
    def acquire(self, *a, **k):
        raise AssertionError("poll_due() should never run for a sync-completed job")

    def release(self, *a, **k):
        raise AssertionError("poll_due() should never run for a sync-completed job")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    input_root = os.environ.get("MEDIA_PROBE_INPUT_ROOT")
    artifact_root = os.environ.get("MEDIA_PROBE_ARTIFACT_ROOT")
    if not input_root or not artifact_root:
        print("Set MEDIA_PROBE_INPUT_ROOT and MEDIA_PROBE_ARTIFACT_ROOT (local directories) before running.", file=sys.stderr)
        return 2
    if shutil.which("ffprobe") is None or shutil.which("ffmpeg") is None:
        print("ffmpeg/ffprobe must be on PATH for this smoke (see module docstring).", file=sys.stderr)
        return 2

    input_root = Path(input_root)
    input_root.mkdir(parents=True, exist_ok=True)
    fixture = input_root / "smoke_fixture.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=5",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(fixture)],
        capture_output=True, check=True,
    )

    before_sha = _sha256(fixture)
    before_size = fixture.stat().st_size

    adapter = resolve_adapter("media_probe")  # reads MEDIA_PROBE_INPUT_ROOT / MEDIA_PROBE_ARTIFACT_ROOT from env
    if adapter is None:
        print("media_probe capability not registered", file=sys.stderr)
        return 2

    stored_artifacts = []
    real_put = adapter.store.put

    def _spying_put(**kwargs):
        stored = real_put(**kwargs)
        stored_artifacts.append(stored)
        return stored

    adapter.store.put = _spying_put

    boundary = ExternalExecutionBoundary(repository=_InMemoryRepo(), lease_repository=_UnusedLeases(), adapter=adapter)
    payload = {"result_ref": str(fixture), "mime_type": "video/mp4", "size": before_size, "sha256": before_sha}

    outcome = boundary.submit(contract_id="media-probe-poc-smoke", idempotency_key="media-probe-poc-smoke", payload=payload)
    print(f"result: {outcome.result}")
    print(f"user_message: {outcome.user_message}")
    job = boundary.repository.get("media-probe-poc-smoke")
    print(f"job.status: {job.status if job else None}")
    print(f"job.result_ref: {job.result_ref if job else None}")
    print(f"job.evidence: {job.evidence if job else None}")

    ok = outcome.result == "completed"
    if ok and job:
        stored_mime_ok = bool(stored_artifacts) and stored_artifacts[0].mime_type == "application/json"
        print(f"stored artifact mime_type == application/json: {stored_mime_ok}")
        ok = ok and stored_mime_ok

        result_path = Path(job.result_ref)
        stored_metadata = json.loads(result_path.read_text(encoding="utf-8"))
        print(f"stored normalized metadata: {stored_metadata}")
        real_checksum = hashlib.sha256(result_path.read_bytes()).hexdigest()
        ok = ok and real_checksum == job.evidence.get("result_checksum")
        print(f"independent result checksum match: {ok}")

        after_sha = _sha256(fixture)
        after_size = fixture.stat().st_size
        immutable = after_sha == before_sha and after_size == before_size
        print(f"source unchanged (sha256+size): {immutable}")
        ok = ok and immutable

        second = boundary.submit(contract_id="media-probe-poc-smoke", idempotency_key="media-probe-poc-smoke", payload=payload)
        no_rerun = second.result == "completed" and second.raw_response.get("external_job_status") == "completed"
        print(f"duplicate submit short-circuited (no second ffprobe run): {no_rerun}")
        ok = ok and no_rerun

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
