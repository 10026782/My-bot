"""Local-only MoneyPrinterTurbo adapter.

Upstream POC target: MoneyPrinterTurbo v1.3.3.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from core.external_execution_boundary import PollResult, SubmitResult

UPSTREAM_REPOSITORY = "https://github.com/harry0703/MoneyPrinterTurbo"
UPSTREAM_TAG = "v1.3.3"
_MAX_MEDIA = 8
_MAX_TIMEOUT = 3600
_MIN_ARTIFACT_BYTES = 1024
_VALIDATION_TIMEOUT_SECONDS = 15
_RUNNER = (
    "import os,pathlib,subprocess,sys;"
    "status=pathlib.Path(sys.argv[1]);"
    "rc=subprocess.run(sys.argv[2:]).returncode;"
    "temp=status.with_suffix('.tmp');temp.write_text(str(rc));os.replace(temp,status);"
    "raise SystemExit(rc)"
)


class MoneyPrinterTurboAdapter:
    name = "moneyprinterturbo"

    def __init__(self, *, runtime_root=None, jobs_root=None, media_root=None,
                 executable=None, timeout_seconds=None):
        self.runtime_root = Path(runtime_root or os.environ.get("MPT_RUNTIME_ROOT", ".")).resolve()
        jobs_value = jobs_root or os.environ.get("MPT_JOBS_ROOT")
        media_value = media_root or os.environ.get("MPT_APPROVED_MEDIA_ROOT")
        self.jobs_root = Path(jobs_value).resolve() if jobs_value else None
        self.media_root = Path(media_value).resolve() if media_value else None
        self.executable = executable or os.environ.get("MPT_EXECUTABLE", "uv")
        self.timeout_seconds = min(int(timeout_seconds or os.environ.get("MPT_TIMEOUT_SECONDS", "1800")), _MAX_TIMEOUT)

    def submit(self, request: dict) -> SubmitResult:
        payload = request.get("payload") if isinstance(request, dict) else None
        try:
            script, script_sha256, media, settings = self._validate(payload)
            self._check_runtime()
            provider_job_id = str(uuid.uuid4())
            job_dir = self.jobs_root / provider_job_id
            media_dir = job_dir / "media"
            output_dir = job_dir / "output"
            self.jobs_root.mkdir(parents=True, exist_ok=True)
            media_dir.mkdir(parents=True)
            output_dir.mkdir()
            copied_media = []
            for index, source in enumerate(media):
                target = media_dir / f"{index:02d}-{Path(source).name}"
                shutil.copy2(source, target)
                copied_media.append(str(target))

            manifest = {
                "provider_job_id": provider_job_id,
                "script_sha256": script_sha256,
                "approved_script": script,
                "media_refs": copied_media,
                "output_ref": str(self.runtime_root / "storage" / "tasks" / provider_job_id / "final-1.mp4"),
                "deadline": time.time() + self.timeout_seconds,
                "status": "created",
                "created_at": time.time(),
            }
            self._write_manifest(job_dir, manifest)
            argv = [
                self.executable, "run", "--project", str(self.runtime_root), "python", "cli.py",
                "--task-id", provider_job_id,
                "--video-script", script,
                "--video-source", "local",
                "--video-materials", ",".join(copied_media),
                "--video-aspect", settings["aspect_ratio"],
                "--voice-name", settings["voice_profile"],
                "--subtitle-enabled", "--bgm-type", "none", "--stop-at", "video",
            ]
            env = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
            process = subprocess.Popen(
                [sys.executable, "-c", _RUNNER, str(job_dir / "exit_status"), *argv],
                cwd=self.runtime_root, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            manifest.update({"status": "submitted", "pid": process.pid, "argv": argv})
            self._write_manifest(job_dir, manifest)
            return SubmitResult("accepted", provider_job_id, {"adapter_name": self.name, "provider_job_id": provider_job_id})
        except Exception as exc:
            return SubmitResult("failed", failure_code=f"mpt_{type(exc).__name__.lower()}"[:120])

    def poll(self, job) -> PollResult:
        try:
            job_dir = self._job_dir(job.provider_job_id)
            manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
            if hashlib.sha256(manifest["approved_script"].encode("utf-8")).hexdigest() != manifest["script_sha256"]:
                return PollResult("failed", failure_code="mpt_script_integrity")
            output = Path(manifest["output_ref"])
            expected_root = self.runtime_root / "storage" / "tasks" / str(uuid.UUID(job.provider_job_id))
            if not _within(output.resolve(), expected_root.resolve()):
                return PollResult("failed", failure_code="mpt_output_path")
            exit_code = _read_exit_status(job_dir / "exit_status")
            if exit_code is None:
                pid = manifest.get("pid")
                if manifest.get("deadline", 0) < time.time() and _pid_alive(pid):
                    os.kill(int(pid), 15)
                    return PollResult("failed", failure_code="mpt_timeout")
                if _pid_alive(pid):
                    return PollResult("submitted")
                return PollResult("outcome_unknown", failure_code="mpt_process_state_unknown")
            if exit_code != 0:
                return PollResult("failed", evidence={"validation_result": "process_exit_nonzero"}, failure_code="mpt_process_failed")

            evidence = self._validate_artifact(output)
            if evidence["validation_result"] != "valid":
                return PollResult("failed", evidence=evidence, failure_code="mpt_artifact_invalid")
            if output.is_file():
                final = job_dir / "output" / "final-1.mp4"
                if output != final:
                    shutil.copy2(output, final)
                return PollResult("completed", str(final), {
                    "provider_job_id": job.provider_job_id,
                    "result_ref": str(final),
                    "result_checksum": hashlib.sha256(final.read_bytes()).hexdigest(),
                    "script_sha256": manifest["script_sha256"],
                    "mime_type": "video/mp4",
                    "size": final.stat().st_size,
                    **evidence,
                })
        except Exception:
            return PollResult("outcome_unknown", failure_code="mpt_poll_unknown")

    @staticmethod
    def _validate_artifact(output: Path) -> dict:
        if not output.is_file() or output.is_symlink():
            return {"artifact_size": "0", "validation_result": "missing_or_not_regular"}
        size = output.stat().st_size
        evidence = {"artifact_size": str(size)}
        if size < _MIN_ARTIFACT_BYTES:
            return {**evidence, "validation_result": "too_small"}
        ffprobe = shutil.which("ffprobe")
        if ffprobe:
            try:
                result = subprocess.run(
                    [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                     "stream=codec_type,width,height,duration", "-of", "json", str(output)],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                    timeout=_VALIDATION_TIMEOUT_SECONDS,
                )
            except (OSError, subprocess.TimeoutExpired):
                return {**evidence, "validation_result": "ffprobe_error"}
            evidence["ffprobe_exit_code"] = str(result.returncode)
            if result.returncode or len(result.stdout) > 8192:
                return {**evidence, "validation_result": "ffprobe_invalid"}
            try:
                stream = json.loads(result.stdout).get("streams", [])[0]
                width, height = int(stream["width"]), int(stream["height"])
            except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                return {**evidence, "validation_result": "ffprobe_invalid"}
            if stream.get("codec_type") != "video" or width <= 0 or height <= 0:
                return {**evidence, "validation_result": "ffprobe_invalid"}
            evidence.update({"video_width": str(width), "video_height": str(height)})
            if stream.get("duration") not in (None, "N/A"):
                evidence["video_duration"] = str(stream["duration"])[:32]
            return {**evidence, "validation_result": "valid"}
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return {**evidence, "validation_result": "validator_unavailable"}
        try:
            result = subprocess.run(
                [ffmpeg, "-v", "error", "-i", str(output), "-map", "0:v:0", "-frames:v", "1", "-f", "null", "-"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=_VALIDATION_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {**evidence, "validation_result": "ffmpeg_error"}
        return {**evidence, "validation_result": "valid" if result.returncode == 0 else "ffmpeg_invalid"}

    def _validate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("payload")
        script = payload.get("approved_script")
        if not isinstance(script, str) or not script:
            raise ValueError("approved_script")
        digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
        if payload.get("script_sha256") != digest:
            raise ValueError("script_sha256")
        media = payload.get("approved_media_refs")
        if not isinstance(media, list) or not 1 <= len(media) <= _MAX_MEDIA:
            raise ValueError("approved_media_refs")
        checked = []
        for raw in media:
            path = Path(raw).resolve() if isinstance(raw, str) else None
            if path is None or self.media_root is None or not _within(path, self.media_root) or not path.is_file():
                raise ValueError("media_path_escape")
            checked.append(str(path))
        settings = {
            "aspect_ratio": payload.get("aspect_ratio", "9:16"),
            "voice_profile": payload.get("voice_profile", "zh-CN-XiaoxiaoNeural-Female"),
        }
        if settings["aspect_ratio"] not in {"9:16", "16:9", "1:1"}:
            raise ValueError("aspect_ratio")
        return script, digest, checked, settings

    def _check_runtime(self):
        if not self.runtime_root.is_dir() or not (self.runtime_root / "cli.py").is_file():
            raise ValueError("runtime_unconfigured")
        if self.jobs_root is None or self.media_root is None:
            raise ValueError("sandbox_unconfigured")
        config = self.runtime_root / "config.toml"
        if not config.is_file():
            raise ValueError("config_missing")
        text = config.read_text(encoding="utf-8")
        if "upload_post_enabled = false" not in text or "upload_post_auto_upload = false" not in text:
            raise ValueError("publishing_not_disabled")

    def _job_dir(self, provider_job_id):
        job_id = uuid.UUID(str(provider_job_id))
        path = (self.jobs_root / str(job_id)).resolve()
        if not _within(path, self.jobs_root) or not path.is_dir():
            raise ValueError("job_path")
        return path

    @staticmethod
    def _write_manifest(job_dir, manifest):
        path = job_dir / "manifest.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)


def _within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path), str(root))) == str(root)
    except ValueError:
        return False


def _pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _read_exit_status(path: Path) -> int | None:
    try:
        value = path.read_text(encoding="ascii").strip()
        return int(value) if value and value.lstrip("-").isdigit() else None
    except OSError:
        return None
