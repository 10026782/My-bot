"""Stirling-PDF capability POC: registry registration, artifact-first input
validation (allowlist-under-root/symlink/size/mime/checksum), the merge HTTP
call contract, output validation, and the generic boundary's sync-completion
path. No network, no Docker — the HTTP boundary is mocked via
monkeypatch.setattr(httpx, "post"/"get", ...); real verification against a
live Stirling-PDF service happens only in the separate manual smoke
harness (scripts/stirling_pdf_capability_poc/smoke.py)."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

import core.stirling_pdf_adapter as stirling_pdf_adapter
from core.artifact_store import ArtifactStoreError
from core.external_capability_contract import get_contract, resolve_adapter
from core.external_execution_boundary import ExternalExecutionBoundary
from core.local_artifact_store import LocalArtifactStore
from core.stirling_pdf_adapter import StirlingPDFAdapter
from scripts.stirling_pdf_capability_poc.fixtures import minimal_pdf_bytes


# ── Fixtures / helpers ───────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


def _write_pdf(directory: Path, name: str) -> Path:
    path = directory / name
    path.write_bytes(minimal_pdf_bytes())
    return path


def _input_meta(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "result_ref": str(path),
        "mime_type": "application/pdf",
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _adapter(input_root: Path, output_root: Path, **kwargs) -> StirlingPDFAdapter:
    defaults = dict(
        base_url="http://stirling.test",
        api_key="test-key",
        input_root=input_root,
        store=LocalArtifactStore(root=output_root, subdir="stirling_pdf", suffix=".pdf"),
    )
    defaults.update(kwargs)
    return StirlingPDFAdapter(**defaults)


def _two_valid_inputs(input_root: Path) -> list[dict]:
    a = _write_pdf(input_root, "a.pdf")
    b = _write_pdf(input_root, "b.pdf")
    return [_input_meta(a), _input_meta(b)]


def _success_response() -> _FakeResponse:
    return _FakeResponse(200, content=minimal_pdf_bytes(), headers={"content-type": "application/pdf"})


def _unreachable_post(url, **kwargs):
    raise AssertionError("Stirling-PDF must not be called when validation should fail closed first")


# ── Registry registration (items 1, 2, 3) ───────────────────────────────

def test_stirling_pdf_registered_atomically_as_third_capability():
    adapter = resolve_adapter("stirling_pdf")
    assert isinstance(adapter, StirlingPDFAdapter)
    assert adapter.name == "stirling_pdf"


def test_stirling_pdf_contract_metadata():
    contract = get_contract("stirling_pdf")
    assert contract is not None
    assert contract.capability_id == "stirling_pdf"
    assert contract.adapter_name == "stirling_pdf"
    assert contract.execution_mode == "sync"
    assert contract.version == "2.14.3"
    assert contract.risk_class == "high"


def test_unknown_capability_still_fails_closed():
    assert resolve_adapter("some_future_capability_nobody_registered") is None
    assert get_contract("some_future_capability_nobody_registered") is None


# ── Missing configuration fails closed (items 4, 5) ─────────────────────

def test_missing_base_url_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    adapter = _adapter(tmp_path / "in", tmp_path / "out", base_url="")
    (tmp_path / "in").mkdir()
    inputs = _two_valid_inputs(tmp_path / "in")
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_base_url_unconfigured"


def test_missing_api_key_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    adapter = _adapter(tmp_path / "in", tmp_path / "out", api_key="")
    (tmp_path / "in").mkdir()
    inputs = _two_valid_inputs(tmp_path / "in")
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_api_key_unconfigured"


# ── Input validation (items 6-15) ───────────────────────────────────────

def test_fewer_than_two_pdfs_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    inputs = [_input_meta(_write_pdf(input_root, "a.pdf"))]
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_too_few_inputs"


def test_too_many_inputs_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    inputs = [_input_meta(_write_pdf(input_root, f"f{i}.pdf")) for i in range(11)]
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_too_many_inputs"


def test_input_outside_approved_root_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    good = _input_meta(_write_pdf(input_root, "a.pdf"))
    bad = _input_meta(_write_pdf(outside, "b.pdf"))
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": [good, bad]}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_outside_approved_root"


def test_symlink_input_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    real = _write_pdf(input_root, "real.pdf")
    link = input_root / "link.pdf"
    os.symlink(real, link)
    adapter = _adapter(input_root, tmp_path / "out")
    good = _input_meta(real)
    bad_meta = _input_meta(real)
    bad_meta["result_ref"] = str(link)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": [good, bad_meta]}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_symlink"


def test_missing_input_artifact_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    good = _input_meta(_write_pdf(input_root, "a.pdf"))
    missing = {"result_ref": str(input_root / "does-not-exist.pdf"), "mime_type": "application/pdf", "size": 10, "sha256": "0" * 64}
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": [good, missing]}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_not_regular_file"


def test_zero_byte_input_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    good = _input_meta(_write_pdf(input_root, "a.pdf"))
    empty_path = input_root / "empty.pdf"
    empty_path.write_bytes(b"")
    empty_meta = {"result_ref": str(empty_path), "mime_type": "application/pdf", "size": 0, "sha256": hashlib.sha256(b"").hexdigest()}
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": [good, empty_meta]}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_empty"


def test_non_pdf_input_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    good = _input_meta(_write_pdf(input_root, "a.pdf"))
    not_pdf = input_root / "notpdf.pdf"
    not_pdf.write_bytes(b"not a real pdf file at all")
    bad_meta = {
        "result_ref": str(not_pdf), "mime_type": "application/pdf",
        "size": not_pdf.stat().st_size, "sha256": hashlib.sha256(not_pdf.read_bytes()).hexdigest(),
    }
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": [good, bad_meta]}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_pdf_signature_invalid"


def test_input_mime_mismatch_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    good = _input_meta(_write_pdf(input_root, "a.pdf"))
    bad = _input_meta(_write_pdf(input_root, "b.pdf"))
    bad["mime_type"] = "application/octet-stream"
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": [good, bad]}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_mime_mismatch"


def test_input_size_mismatch_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    good = _input_meta(_write_pdf(input_root, "a.pdf"))
    bad = _input_meta(_write_pdf(input_root, "b.pdf"))
    bad["size"] = bad["size"] + 5
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": [good, bad]}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_size_mismatch"


def test_input_checksum_mismatch_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    good = _input_meta(_write_pdf(input_root, "a.pdf"))
    bad = _input_meta(_write_pdf(input_root, "b.pdf"))
    bad["sha256"] = "0" * 64
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": [good, bad]}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_checksum_mismatch"


# ── Size limits (items 16, 17) ───────────────────────────────────────────

def test_per_file_size_limit_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    monkeypatch.setattr(stirling_pdf_adapter, "_MAX_FILE_BYTES", 50)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    inputs = _two_valid_inputs(input_root)  # each ~316 bytes > 50
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_input_too_large"


def test_total_size_limit_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", _unreachable_post)
    monkeypatch.setattr(stirling_pdf_adapter, "_MAX_TOTAL_BYTES", 400)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    inputs = _two_valid_inputs(input_root)  # ~316 + ~316 > 400, each individually < 400
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_total_input_too_large"


# ── Caller cannot control endpoint/output/evidence (items 18-22) ────────

def test_caller_cannot_choose_endpoint(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        return _success_response()

    monkeypatch.setattr(httpx, "post", fake_post)
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({
        "contract_id": "c1",
        "payload": {"inputs": inputs, "endpoint": "/api/v1/evil", "path": "/x", "route": "/y", "url": "http://evil/"},
    })
    assert result.status == "completed"
    assert captured["url"] == "http://stirling.test/api/v1/general/merge-pdfs"


def test_pipeline_endpoint_unreachable_through_payload(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        return _success_response()

    monkeypatch.setattr(httpx, "post", fake_post)
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({
        "contract_id": "c1",
        "payload": {"inputs": inputs, "endpoint": "/api/v1/pipeline/handleData"},
    })
    assert result.status == "completed"
    assert "/api/v1/pipeline" not in captured["url"]
    assert captured["url"].endswith("/api/v1/general/merge-pdfs")


def test_caller_cannot_choose_output_path(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    output_root = tmp_path / "out"
    adapter = _adapter(input_root, output_root)
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({
        "contract_id": "job-1",
        "payload": {"inputs": inputs, "result_ref": "/etc/passwd", "output_path": "/etc/passwd"},
    })
    assert result.status == "completed"
    resolved = Path(result.result_ref).resolve()
    assert str(resolved).startswith(str((output_root / "stirling_pdf").resolve()))


def test_api_key_never_enters_evidence(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out", api_key="super-secret-key")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "completed"
    assert "super-secret-key" not in str(result.evidence)
    assert "super-secret-key" not in str(result)


def test_merge_request_produced_correctly(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out", api_key="k-123")
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs["headers"]
        captured["data"] = kwargs["data"]
        captured["file_field_names"] = [f[0] for f in kwargs["files"]]
        captured["file_names"] = [f[1][0] for f in kwargs["files"]]
        return _success_response()

    monkeypatch.setattr(httpx, "post", fake_post)
    a = _write_pdf(input_root, "a.pdf")
    b = _write_pdf(input_root, "b.pdf")
    inputs = [_input_meta(a), _input_meta(b)]
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "completed"
    assert captured["url"] == "http://stirling.test/api/v1/general/merge-pdfs"
    assert captured["headers"]["X-API-KEY"] == "k-123"
    assert captured["data"] == {"sortType": "orderProvided", "removeCertSign": "false", "generateToc": "false"}
    assert captured["file_field_names"] == ["fileInput", "fileInput"]
    assert captured["file_names"] == ["a.pdf", "b.pdf"]


# ── Failure semantics (items 23-28) ─────────────────────────────────────

def test_deterministic_4xx_is_failed(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _FakeResponse(401, content=b"unauthorized"))
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_http_401"


def test_timeout_is_outcome_unknown(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")

    def fake_post(url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", fake_post)
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "outcome_unknown"


def test_connection_reset_is_outcome_unknown(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")

    def fake_post(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "outcome_unknown"


def test_unexpected_exception_is_outcome_unknown(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")

    def fake_post(url, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(httpx, "post", fake_post)
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "outcome_unknown"


def test_success_status_non_pdf_response_rejected(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _FakeResponse(200, content=b"<html>oops</html>", headers={"content-type": "text/html"}))
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_output_content_type_mismatch"


def test_empty_response_rejected(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _FakeResponse(200, content=b"", headers={"content-type": "application/pdf"}))
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_output_empty"


def test_oversized_response_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(stirling_pdf_adapter, "_MAX_OUTPUT_BYTES", 50)
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())  # ~316 bytes > 50
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_output_too_large"


def test_non_pdf_signature_output_rejected(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _FakeResponse(200, content=b"not a pdf", headers={}))
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert result.failure_code == "stirling_pdf_output_signature_invalid"


# ── Successful merge / evidence (items 29-31) ────────────────────────────

def test_valid_response_produces_output_artifact_with_checksum(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    output_root = tmp_path / "out"
    adapter = _adapter(input_root, output_root)
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "job-1", "payload": {"inputs": inputs}})
    assert result.status == "completed"
    artifact = Path(result.result_ref)
    assert artifact.is_file()
    assert artifact.read_bytes().startswith(b"%PDF-")
    assert result.evidence["result_checksum"] == hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_evidence_is_bounded_to_declared_keys(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "job-2", "payload": {"inputs": inputs}})
    expected = {
        "adapter_name", "provider_status", "result_ref", "result_checksum",
        "operation", "input_count", "input_total_bytes", "output_bytes",
        "stirling_pdf_version", "elapsed_ms",
    }
    assert set(result.evidence) == expected
    assert result.evidence["operation"] == "merge_pdfs"
    assert result.evidence["input_count"] == "2"


# ── Boundary sync-completion (items 32-34) ──────────────────────────────

class FakeRepo:
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

    def due_submitted(self, interval_seconds=300):
        return [j for j in self.jobs.values() if j.status == "submitted"]


def test_sync_completed_state_persists_full_terminal_state(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())
    repo = FakeRepo()
    boundary = ExternalExecutionBoundary(repository=repo, adapter=adapter)
    inputs = _two_valid_inputs(input_root)
    outcome = boundary.submit(contract_id="job-5", idempotency_key="k1", payload={"inputs": inputs})
    assert outcome.result == "completed"
    job = repo.jobs["job-5"]
    assert job.status == "completed"
    assert job.completed_at is not None
    assert job.result_ref
    assert job.evidence["provider_status"] == "completed"


def test_completed_sync_job_never_enters_polling(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())
    repo = FakeRepo()
    boundary = ExternalExecutionBoundary(repository=repo, adapter=adapter)
    inputs = _two_valid_inputs(input_root)
    boundary.submit(contract_id="job-6", idempotency_key="k1", payload={"inputs": inputs})
    assert repo.due_submitted() == []


def test_duplicate_submit_with_same_contract_id_does_not_call_service_twice(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return _success_response()

    monkeypatch.setattr(httpx, "post", fake_post)
    repo = FakeRepo()
    boundary = ExternalExecutionBoundary(repository=repo, adapter=adapter)
    inputs = _two_valid_inputs(input_root)
    first = boundary.submit(contract_id="job-7", idempotency_key="k1", payload={"inputs": inputs})
    second = boundary.submit(contract_id="job-7", idempotency_key="k1", payload={"inputs": inputs})
    assert first.result == "completed" and second.result == "completed"
    assert len(calls) == 1


# ── Temp file lifecycle (items 35-37) ───────────────────────────────────

def test_transient_response_temp_file_cleaned_after_success(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())

    captured = {}
    real_named_temp = tempfile.NamedTemporaryFile

    def spy(*a, **kw):
        f = real_named_temp(*a, **kw)
        captured["path"] = Path(f.name)
        return f

    monkeypatch.setattr(stirling_pdf_adapter.tempfile, "NamedTemporaryFile", spy)
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "completed"
    assert not captured["path"].exists()


def test_transient_response_temp_file_cleaned_after_storage_failure(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()

    class _FailingStore:
        def put(self, *, path, identity, metadata):
            raise ArtifactStoreError("simulated_storage_failure")

    adapter = _adapter(input_root, tmp_path / "out", store=_FailingStore())
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())

    captured = {}
    real_named_temp = tempfile.NamedTemporaryFile

    def spy(*a, **kw):
        f = real_named_temp(*a, **kw)
        captured["path"] = Path(f.name)
        return f

    monkeypatch.setattr(stirling_pdf_adapter.tempfile, "NamedTemporaryFile", spy)
    inputs = _two_valid_inputs(input_root)
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "failed"
    assert not captured["path"].exists()


def test_input_source_artifacts_are_not_deleted_by_adapter(tmp_path, monkeypatch):
    input_root = tmp_path / "in"
    input_root.mkdir()
    adapter = _adapter(input_root, tmp_path / "out")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _success_response())
    a = _write_pdf(input_root, "a.pdf")
    b = _write_pdf(input_root, "b.pdf")
    inputs = [_input_meta(a), _input_meta(b)]
    result = adapter.submit({"contract_id": "c1", "payload": {"inputs": inputs}})
    assert result.status == "completed"
    assert a.is_file() and b.is_file()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
