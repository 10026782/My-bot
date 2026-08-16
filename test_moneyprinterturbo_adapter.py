import hashlib
import json
import time
from types import SimpleNamespace

import pytest

from core.moneyprinterturbo_adapter import MoneyPrinterTurboAdapter


def _payload(script, media):
    return {
        "approved_script": script,
        "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "approved_media_refs": [str(media)],
        "aspect_ratio": "9:16",
        "voice_profile": "no-voice",
    }


def _poll_fixture(tmp_path, *, artifact=b"", exit_code="0"):
    job_id = "00000000-0000-0000-0000-000000000001"
    job = tmp_path / "jobs" / job_id
    (job / "output").mkdir(parents=True)
    runtime = tmp_path / "runtime"
    output = runtime / "storage" / "tasks" / job_id / "final-1.mp4"
    output.parent.mkdir(parents=True)
    output.write_bytes(artifact)
    script = "approved"
    (job / "manifest.json").write_text(json.dumps({
        "output_ref": str(output),
        "approved_script": script,
        "script_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "pid": 12345,
        "deadline": time.time() + 60,
    }))
    if exit_code is not None:
        (job / "exit_status").write_text(str(exit_code), encoding="ascii")
    return MoneyPrinterTurboAdapter(runtime_root=runtime, jobs_root=tmp_path / "jobs", media_root=tmp_path), job_id, output


def test_missing_or_wrong_script_hash_rejected(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    adapter = MoneyPrinterTurboAdapter(runtime_root=tmp_path, jobs_root=tmp_path / "jobs", media_root=tmp_path)
    with pytest.raises(ValueError, match="approved_script"):
        adapter._validate({"approved_media_refs": [str(media)]})
    bad = _payload("approved", media)
    bad["script_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="script_sha256"):
        adapter._validate(bad)


def test_media_path_escape_rejected(tmp_path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"x")
    adapter = MoneyPrinterTurboAdapter(runtime_root=tmp_path, jobs_root=tmp_path / "jobs", media_root=media_root)
    with pytest.raises(ValueError, match="media_path_escape"):
        adapter._validate(_payload("approved", outside))


def test_poll_completed_is_restart_safe(tmp_path, monkeypatch):
    adapter, job_id, _ = _poll_fixture(tmp_path, artifact=b"x" * 2048)
    monkeypatch.setattr(adapter, "_validate_artifact", lambda _: {"artifact_size": "2048", "validation_result": "valid"})
    result = adapter.poll(SimpleNamespace(provider_job_id=job_id))
    assert result.status == "completed"
    assert result.result_ref.endswith("output/final-1.mp4")


def test_missing_or_zero_artifact_never_completes(tmp_path):
    adapter, job_id, output = _poll_fixture(tmp_path, artifact=b"")
    output.unlink()
    assert adapter.poll(SimpleNamespace(provider_job_id=job_id)).status == "failed"
    adapter, job_id, _ = _poll_fixture(tmp_path / "zero", artifact=b"")
    assert adapter.poll(SimpleNamespace(provider_job_id=job_id)).status == "failed"


def test_fake_and_truncated_mp4_never_complete(tmp_path, monkeypatch):
    adapter, job_id, _ = _poll_fixture(tmp_path, artifact=b"x" * 48)
    result = adapter.poll(SimpleNamespace(provider_job_id=job_id))
    assert result.status == "failed"
    assert result.evidence["validation_result"] == "too_small"

    adapter, job_id, _ = _poll_fixture(tmp_path / "truncated", artifact=b"x" * 2048)
    monkeypatch.setattr("core.moneyprinterturbo_adapter.shutil.which", lambda name: "ffprobe" if name == "ffprobe" else None)
    monkeypatch.setattr("core.moneyprinterturbo_adapter.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"streams": []}'))
    assert adapter.poll(SimpleNamespace(provider_job_id=job_id)).status == "failed"


def test_valid_ffprobe_video_completes_with_bounded_evidence(tmp_path, monkeypatch):
    adapter, job_id, _ = _poll_fixture(tmp_path, artifact=b"x" * 2048)
    monkeypatch.setattr("core.moneyprinterturbo_adapter.shutil.which", lambda name: "ffprobe" if name == "ffprobe" else None)
    monkeypatch.setattr("core.moneyprinterturbo_adapter.subprocess.run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout='{"streams": [{"codec_type": "video", "width": 1080, "height": 1920, "duration": "6.12"}]}'
    ))
    result = adapter.poll(SimpleNamespace(provider_job_id=job_id))
    assert result.status == "completed"
    assert result.evidence["artifact_size"] == "2048"
    assert result.evidence["video_width"] == "1080"
    assert result.evidence["video_duration"] == "6.12"


def test_live_or_unknown_process_never_completes(tmp_path, monkeypatch):
    adapter, job_id, _ = _poll_fixture(tmp_path, artifact=b"x" * 2048, exit_code=None)
    monkeypatch.setattr("core.moneyprinterturbo_adapter._pid_alive", lambda _: True)
    assert adapter.poll(SimpleNamespace(provider_job_id=job_id)).status == "submitted"
    monkeypatch.setattr("core.moneyprinterturbo_adapter._pid_alive", lambda _: False)
    assert adapter.poll(SimpleNamespace(provider_job_id=job_id)).status == "outcome_unknown"


def test_validator_error_and_nonzero_exit_fail_closed(tmp_path, monkeypatch):
    adapter, job_id, _ = _poll_fixture(tmp_path, artifact=b"x" * 2048)
    monkeypatch.setattr(adapter, "_validate_artifact", lambda _: {"artifact_size": "2048", "validation_result": "ffprobe_error"})
    assert adapter.poll(SimpleNamespace(provider_job_id=job_id)).status == "failed"
    adapter, job_id, _ = _poll_fixture(tmp_path / "exit", artifact=b"x" * 2048, exit_code="2")
    assert adapter.poll(SimpleNamespace(provider_job_id=job_id)).status == "failed"


def test_submit_uses_local_script_and_materials_only(tmp_path, monkeypatch):
    runtime = tmp_path / "mpt"
    runtime.mkdir()
    (runtime / "cli.py").write_text("")
    (runtime / "config.toml").write_text(
        "upload_post_enabled = false\nupload_post_auto_upload = false\n"
    )
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    seen = {}

    class FakeProcess:
        pid = 12345

    def fake_popen(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr("core.moneyprinterturbo_adapter.subprocess.Popen", fake_popen)
    adapter = MoneyPrinterTurboAdapter(
        runtime_root=runtime, jobs_root=tmp_path / "jobs", media_root=tmp_path
    )
    result = adapter.submit({"payload": _payload("exact approved script", media)})
    assert result.status == "accepted"
    child_argv = seen["argv"][4:]
    assert "--video-source" in child_argv
    assert child_argv[child_argv.index("--video-source") + 1] == "local"
    assert "--video-subject" not in child_argv
    assert "--video-terms" not in child_argv
    assert seen["kwargs"]["env"].keys() == {"PATH", "LANG", "LC_ALL"}
