"""Media Probe capability POC: registry registration and the adapter's
read-only ffprobe boundary (missing input, ffprobe not installed / fails,
success parsing, and the "missing field -> None, never fabricated" rule).
No real ffprobe call in the success-path tests — subprocess.run is
monkeypatched with canned ffprobe JSON. The "ffprobe not installed" test
relies on ffprobe genuinely not being on PATH in this environment, exercising
the real FileNotFoundError path with no mocking at all."""

from __future__ import annotations

import json
import subprocess

import pytest

from core.external_capability_contract import get_contract, resolve_adapter
from core.media_probe_adapter import MediaProbeAdapter

_VIDEO_PROBE = {
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "12.5", "size": "1048576", "bit_rate": "838860"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
        {"codec_type": "audio", "codec_name": "aac"},
        {"codec_type": "subtitle", "codec_name": "mov_text"},
    ],
}

_AUDIO_ONLY_PROBE = {
    "format": {"format_name": "mp3", "duration": "200.0", "size": "3200000"},
    "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
}


def _fake_run(returncode=0, stdout="", stderr=""):
    def run(*args, **kwargs):
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


# ── Input validation ────────────────────────────────────────────────────

def test_submit_missing_path_fails():
    result = MediaProbeAdapter().submit({"payload": {}})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_path_missing"


def test_submit_path_not_found_fails(tmp_path):
    result = MediaProbeAdapter().submit({"payload": {"path": str(tmp_path / "nope.mp4")}})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_path_not_found"


# ── ffprobe not installed (real, unmocked — see module docstring) ──────

def test_submit_ffprobe_not_installed_real(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not a real video")
    result = MediaProbeAdapter().submit({"payload": {"path": str(video)}})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_ffprobe_not_installed"


# ── ffprobe failure paths (mocked) ──────────────────────────────────────

def test_submit_ffprobe_nonzero_exit_fails(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=1, stderr="Invalid data"))
    result = MediaProbeAdapter().submit({"payload": {"path": str(video)}})
    assert result.status == "failed"
    assert result.failure_code.startswith("media_probe_ffprobe_failed")


def test_submit_invalid_json_is_outcome_unknown_via_failed(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout="not json"))
    result = MediaProbeAdapter().submit({"payload": {"path": str(video)}})
    assert result.status == "failed"
    assert result.failure_code == "media_probe_invalid_ffprobe_output"


# ── Success paths (mocked) ──────────────────────────────────────────────

def test_submit_video_extracts_full_metadata(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_VIDEO_PROBE)))

    result = MediaProbeAdapter().submit({"payload": {"path": str(video)}})

    assert result.status == "completed"
    ev = result.evidence
    assert ev["mime_type"] == "video/mp4"
    assert ev["duration"] == "12.5"
    assert ev["video_codec"] == "h264"
    assert ev["width"] == "1920"
    assert ev["height"] == "1080"
    assert ev["audio_stream_count"] == "1"
    assert ev["audio_codecs"] == "aac"
    assert ev["subtitle_stream_count"] == "1"
    assert ev["bitrate"] == "838860"


def test_submit_audio_only_missing_video_fields_are_empty_not_fabricated(tmp_path, monkeypatch):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"junk")
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=0, stdout=json.dumps(_AUDIO_ONLY_PROBE)))

    result = MediaProbeAdapter().submit({"payload": {"path": str(audio)}})

    assert result.status == "completed"
    ev = result.evidence
    assert ev["video_codec"] == ""
    assert ev["width"] == ""
    assert ev["height"] == ""
    assert ev["subtitle_stream_count"] == "0"
    assert ev["bitrate"] == ""  # not present in the fixture -> empty, never guessed
    assert ev["audio_codecs"] == "mp3"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
