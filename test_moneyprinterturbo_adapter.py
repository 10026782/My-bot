import hashlib
import json
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


def test_poll_completed_is_restart_safe(tmp_path):
    jobs = tmp_path / "jobs"
    job = jobs / "00000000-0000-0000-0000-000000000001"
    (job / "output").mkdir(parents=True)
    output = job / "output" / "final-1.mp4"
    output.write_bytes(b"mp4")
    runtime = tmp_path / "runtime"
    task_output = runtime / "storage" / "tasks" / job.name
    task_output.mkdir(parents=True)
    runtime_output = task_output / "final-1.mp4"
    runtime_output.write_bytes(b"mp4")
    script = "approved"
    (job / "manifest.json").write_text(json.dumps({
        "output_ref": str(runtime_output),
        "approved_script": script,
        "script_sha256": hashlib.sha256(script.encode()).hexdigest(),
    }))
    adapter = MoneyPrinterTurboAdapter(runtime_root=runtime, jobs_root=jobs, media_root=tmp_path)
    result = adapter.poll(SimpleNamespace(provider_job_id=job.name))
    assert result.status == "completed"
    assert result.result_ref == str(output)


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
    assert "--video-source" in seen["argv"]
    assert seen["argv"][seen["argv"].index("--video-source") + 1] == "local"
    assert "--video-subject" not in seen["argv"]
    assert "--video-terms" not in seen["argv"]
    assert seen["kwargs"]["env"].keys() == {"PATH", "LANG", "LC_ALL"}
