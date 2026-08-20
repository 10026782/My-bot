"""Media Probe capability POC: registry registration, the artifact-first
input contract (approved-root containment, symlink rejection, size/checksum
verification, MIME allowlist), the ffprobe boundary (missing/timeout/nonzero
exit/malformed output/oversized stdout/too-many-streams -> all deterministic
"failed", never "outcome_unknown"), the JSON result-artifact write, evidence
boundedness, and the generic boundary's idempotent no-second-probe guarantee.

No real ffprobe call in the mocked tests — subprocess.run is monkeypatched
with canned ffprobe JSON. The "ffprobe not installed" test relies on ffprobe
genuinely not being on PATH in this environment, exercising the real
FileNotFoundError path with no mocking at all. A separate, not-CI-run real
smoke (scripts/media_probe_poc/smoke.py) proves an actual successful ffprobe
invocation end to end."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import core.media_probe_adapter as media_probe_adapter
from core.external_capability_contract import get_contract, resolve_adapter
from core.external_execution_boundary import ExternalExecutionBoundary
from core.local_artifact_store import LocalArtifactStore
from core.media_probe_adapter import MediaProbeAdapter

_VIDEO_PROBE = {
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "12.5", "size": "1048576", "bit_rate": "838860"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "tags": {"handler": "vide"}},
        {"codec_type": "audio", "codec_name": "aac"},
        {"codec_type": "subtitle", "codec_name": "mov_text"},
    ],
}

_AUDIO_ONLY_PROBE = {
    "format": {"format_name": "mp3", "duration": "N/A", "bit_rate": "abc"},
    "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
}


class FakeRepo:
    """Same in-memory fake used by test_external_capability_contract.py."""

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


def _adapter(tmp_path, *, input_root=None, store=None):
    root = input_root if input_root is not None else (tmp_path / "sources")
    root.mkdir(parents=True, exist_ok=True)
    result_store = store if store is not None else LocalArtifactStore(root=tmp_path / "results", subdir="media_probe", suffix=".json")
    return MediaProbeAdapter(input_root=root, store=result_store), root


def _write_source(root: Path, name: str, data: bytes) -> Path:
    path = root / name
    path.write_bytes(data)
    return path


def _payload(path: Path, *, size=None, sha256_hex=None, mime_type="video/mp4"):
    data = path.read_bytes() if path.is_file() else b""
    return {
        "result_ref": str(path),
        "mime_type": mime_type,
        "size": size if size is not None else len(data),
        "sha256": sha256_hex if sha256_hex is not None else hashlib.sha256(data).hexdigest(),
    }


def _fake_run(returncode=0, stdout="", stderr=""):
    def run(args, **kwargs):
        assert kwargs.get("shell") is not True
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)
    return run


# ── Registry registration ──────────────────────────────────────────────

def test_media_probe_registered():
    adapter = resolve_adapter("media_probe")
    assert isinstance(adapter, MediaProbeAdapter)
    assert adapter.name == "media_probe"


def test_media_probe_contract_metadata():
    contract = get_contract("media_probe")
    assert contract is not None
    assert contract.execution_mode == "sync"
    assert contract.risk_class == "low"


# ── Artifact-first input contract ────────────────────────────────────────

def test_missing_input_root_fails(tmp_path):
    adapter = MediaProbeAdapter(input_root=None, store=LocalArtifactStore(root=tmp_path, subdir="mp", suffix=".json"))
    result = adapter.submit({"payload": {"result_ref": str(tmp_path / "x.mp4"), "mime_type": "video/mp4", "size": 1, "sha256": "a" * 64}})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_input_root_not_configured"


@pytest.mark.parametrize("missing_key", ["result_ref", "mime_type", "size", "sha256"])
def test_missing_required_field_fails(tmp_path, missing_key):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"data")
    payload = _payload(src)
    del payload[missing_key]
    result = adapter.submit({"payload": payload})
    assert result.status == "failed"
    assert result.failure_code == f"media_probe_{missing_key}_missing"


@pytest.mark.parametrize("remote_ref", [
    "https://example.com/video.mp4",
    "gdrive://file-id-123",
    '{"drive_file_id": "abc", "web_view_link": "https://drive.google.com/x"}',
])
def test_remote_or_provider_specific_result_ref_rejected(tmp_path, remote_ref):
    adapter, _root = _adapter(tmp_path)
    result = adapter.submit({"payload": {"result_ref": remote_ref, "mime_type": "video/mp4", "size": 4, "sha256": "a" * 64}})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_remote_unsupported"


def test_artifact_outside_approved_root_rejected(tmp_path):
    adapter, root = _adapter(tmp_path)
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"data")
    result = adapter.submit({"payload": _payload(outside)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_path_outside_root"


def test_symlink_source_rejected(tmp_path):
    adapter, root = _adapter(tmp_path)
    real = tmp_path / "real.mp4"
    real.write_bytes(b"data")
    link = root / "link.mp4"
    link.symlink_to(real)
    result = adapter.submit({"payload": _payload(link)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_symlink_rejected"


def test_path_not_found_rejected(tmp_path):
    adapter, root = _adapter(tmp_path)
    result = adapter.submit({"payload": {"result_ref": str(root / "nope.mp4"), "mime_type": "video/mp4", "size": 4, "sha256": "a" * 64}})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_path_not_found"


def test_zero_byte_source_rejected(tmp_path):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "empty.mp4", b"")
    result = adapter.submit({"payload": _payload(src, size=0)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_empty_file"


def test_oversized_source_rejected(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    monkeypatch.setattr(media_probe_adapter, "_MAX_INPUT_BYTES", 4)
    src = _write_source(root, "big.mp4", b"toolarge")
    result = adapter.submit({"payload": _payload(src)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_input_too_large"


def test_supplied_size_mismatch_rejected(tmp_path):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"real-bytes")
    result = adapter.submit({"payload": _payload(src, size=999999)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_size_mismatch"


def test_supplied_checksum_mismatch_rejected(tmp_path):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"real-bytes")
    result = adapter.submit({"payload": _payload(src, sha256_hex="0" * 64)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_checksum_mismatch"


def test_unsupported_mime_rejected(tmp_path):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.exe", b"real-bytes")
    result = adapter.submit({"payload": _payload(src, mime_type="application/x-msdownload")})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_mime_unsupported"


# ── Subprocess safety ─────────────────────────────────────────────────

def test_caller_cannot_inject_ffprobe_flags_or_shell(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    adapter._ffprobe_version_cache = ""  # isolate the probe call from the separate `ffprobe -version` call
    src = _write_source(root, "a.mp4", b"real-bytes")
    captured = {}

    def run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(_VIDEO_PROBE), stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    payload = _payload(src)
    payload["ffprobe_flags"] = ["-hide_banner", "; rm -rf /"]
    payload["executable"] = "/bin/sh"
    result = adapter.submit({"payload": payload})

    assert result.status == "completed"
    assert captured["args"] == ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(src.resolve())]
    assert captured["kwargs"].get("shell") is not True
    assert "env" not in captured["kwargs"]


# ── ffprobe not installed (real, unmocked — see module docstring) ──────

def test_submit_ffprobe_not_installed_real(tmp_path):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "clip.mp4", b"not a real video")
    result = adapter.submit({"payload": _payload(src)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_ffprobe_not_installed"


# ── ffprobe failure paths -> always "failed" (mocked) ──────────────────

def test_ffprobe_nonzero_exit_fails(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=1, stderr="Invalid data"))
    result = adapter.submit({"payload": _payload(src)})
    assert result.status == "failed"
    assert result.failure_code.startswith("media_probe_ffprobe_failed")


def test_ffprobe_timeout_is_failed_not_outcome_unknown(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"junk")

    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=15)

    monkeypatch.setattr(subprocess, "run", run)
    result = adapter.submit({"payload": _payload(src)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_timeout"


def test_generic_exception_is_failed_not_outcome_unknown(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"junk")

    def run(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", run)
    result = adapter.submit({"payload": _payload(src)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_submit_exception"


def test_malformed_json_fails(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout="not json"))
    result = adapter.submit({"payload": _payload(src)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_invalid_ffprobe_output"


def test_oversized_stdout_fails(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"junk")
    monkeypatch.setattr(media_probe_adapter, "_MAX_STDOUT_BYTES", 10)
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_VIDEO_PROBE)))
    result = adapter.submit({"payload": _payload(src)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_oversized_stdout"


def test_too_many_streams_fails(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "a.mp4", b"junk")
    huge = {"format": {"format_name": "mp4"}, "streams": [{"codec_type": "audio", "codec_name": "aac"}] * 100}
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(huge)))
    result = adapter.submit({"payload": _payload(src)})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_too_many_streams"


# ── Normalization: no fabricated values ──────────────────────────────────

def test_video_metadata_normalized_and_stored(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "clip.mp4", b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_VIDEO_PROBE)))

    result = adapter.submit({"contract_id": "job-1", "payload": _payload(src)})

    assert result.status == "completed"
    stored_json = json.loads(Path(result.result_ref).read_text(encoding="utf-8"))
    assert stored_json["mime_type"] == "video/mp4"
    assert stored_json["size"] == len(b"junk")
    assert stored_json["duration"] == 12.5
    assert stored_json["container"] == "mov,mp4,m4a,3gp,3g2,mj2"
    assert stored_json["video_codec"] == "h264"
    assert stored_json["width"] == 1920
    assert stored_json["height"] == 1080
    assert stored_json["audio_stream_count"] == 1
    assert stored_json["audio_codecs"] == "aac"
    assert stored_json["subtitle_stream_count"] == 1
    assert stored_json["bitrate"] == 838860
    assert "tags" not in json.dumps(stored_json)  # arbitrary ffprobe tags never copied


def test_audio_only_missing_video_fields_are_null_not_fabricated(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "song.mp3", b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_AUDIO_ONLY_PROBE)))

    result = adapter.submit({"payload": _payload(src, mime_type="audio/mpeg")})

    assert result.status == "completed"
    stored_json = json.loads(Path(result.result_ref).read_text(encoding="utf-8"))
    assert stored_json["video_codec"] is None
    assert stored_json["width"] is None
    assert stored_json["height"] is None
    assert stored_json["subtitle_stream_count"] == 0
    assert stored_json["duration"] is None  # "N/A" never becomes 0 or a guess
    assert stored_json["bitrate"] is None  # "abc" never becomes 0 or a guess
    assert stored_json["audio_codecs"] == "mp3"


# ── Result artifact / evidence separation ────────────────────────────────

def test_result_stored_as_json_artifact_with_verified_checksum(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "clip.mp4", b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_VIDEO_PROBE)))

    result = adapter.submit({"contract_id": "job-2", "payload": _payload(src)})

    artifact = Path(result.result_ref)
    assert artifact.is_file()
    assert artifact.suffix == ".json"
    assert result.evidence["result_checksum"] == hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_evidence_is_bounded_and_excludes_raw_data(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "clip.mp4", b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_VIDEO_PROBE)))

    result = adapter.submit({"contract_id": "job-3", "payload": _payload(src)})

    expected_keys = {
        "adapter_name", "provider_status", "result_ref", "result_checksum",
        "operation", "input_mime_type", "input_size", "detected_format",
        "stream_count", "elapsed_ms", "ffprobe_version",
    }
    assert set(result.evidence) == expected_keys
    assert result.evidence["operation"] == "media_probe"
    assert result.evidence["stream_count"] == "3"
    blob = json.dumps(result.evidence)
    assert str(src) not in blob  # source path never leaks into evidence
    assert "h264" not in blob  # normalized result lives only in the stored artifact
    assert "Invalid data" not in blob


def test_evidence_bounded_through_the_generic_boundary(tmp_path, monkeypatch):
    """The boundary's own _bounded_evidence() must not need any key this
    adapter emits — a mismatch here would silently drop evidence in
    production even though the adapter's own return value looks fine."""
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "clip.mp4", b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_VIDEO_PROBE)))
    boundary = ExternalExecutionBoundary(repository=FakeRepo(), adapter=adapter)

    outcome = boundary.submit(contract_id="job-4", idempotency_key="job-4", payload=_payload(src))

    assert outcome.result == "completed"
    job = boundary.repository.get("job-4")
    assert set(job.evidence) == set(adapter.submit({"payload": _payload(src)}).evidence)


# ── Source immutability ──────────────────────────────────────────────────

def test_source_artifact_never_modified(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    src = _write_source(root, "clip.mp4", b"junk")
    before_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    before_size = src.stat().st_size
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_VIDEO_PROBE)))

    result = adapter.submit({"payload": _payload(src)})

    assert result.status == "completed"
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before_sha
    assert src.stat().st_size == before_size


# ── Sync capability semantics ─────────────────────────────────────────

def test_poll_is_never_legitimately_reached():
    adapter = MediaProbeAdapter(input_root=None, store=None)
    result = adapter.poll(object())
    assert result.status == "outcome_unknown"
    assert result.failure_code == "media_probe_unexpected_poll"


def test_duplicate_contract_id_does_not_rerun_ffprobe(tmp_path, monkeypatch):
    adapter, root = _adapter(tmp_path)
    adapter._ffprobe_version_cache = ""  # isolate the probe call from the separate `ffprobe -version` call
    src = _write_source(root, "clip.mp4", b"junk")
    call_count = {"n": 0}

    def run(args, **kwargs):
        call_count["n"] += 1
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(_VIDEO_PROBE), stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    boundary = ExternalExecutionBoundary(repository=FakeRepo(), adapter=adapter)

    first = boundary.submit(contract_id="dup-1", idempotency_key="dup-1", payload=_payload(src))
    second = boundary.submit(contract_id="dup-1", idempotency_key="dup-1", payload=_payload(src))

    assert first.result == "completed"
    assert second.result == "completed"
    assert call_count["n"] == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
