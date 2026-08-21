"""Media Probe capability adapter — POC / NOT PRODUCTION READY.

Governed local artifact -> ffprobe -> normalized JSON result artifact. See
docs/research/MEDIA_PROBE_POC.md.

Input is a StoredArtifact-shaped reference (result_ref/mime_type/size/sha256
— the same fields core/artifact_store.py's StoredArtifact already carries,
no new ArtifactRef type), not a bare filesystem path: the caller cannot hand
this adapter an arbitrary path, only a reference it can independently verify
against a configured, approved local root. "Read-only" means the SOURCE
artifact is never modified, converted, or uploaded — it does not mean no
result is stored. The normalized probe result is written as a small JSON
artifact through the existing LocalArtifactStore, the same storage boundary
every other capability in this file uses.

This is a sync capability (CapabilityContract.execution_mode == "sync"):
submit() runs ffprobe and returns a terminal SubmitResult directly — poll()
is never legitimately reached and exists only to satisfy the ExternalAdapter
contract.

Failure semantics: this capability performs no durable external mutation
whose outcome could become unknowable — ffprobe is a local, read-only
subprocess call. Every validation/probe failure is therefore "failed", not
"outcome_unknown". The one exception is the local JSON-artifact write itself
(a genuine local durable effect), which defers to LocalArtifactStore's own
ArtifactStoreError.uncertain flag, same as every other adapter in this file.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from core.artifact_store import ArtifactStoreError
from core.external_execution_boundary import PollResult, SubmitResult
from core.local_artifact_store import LocalArtifactStore

_TIMEOUT_SECONDS = 15
_VERSION_TIMEOUT_SECONDS = 5
_HASH_CHUNK_BYTES = 1024 * 1024
_MAX_INPUT_BYTES = 500 * 1024 * 1024
_MAX_STDOUT_BYTES = 2 * 1024 * 1024
_MAX_STREAMS = 64

# Explicit POC input allowlist -- deliberately small; extend only against a
# real file that needs a format not listed here.
_ALLOWED_INPUT_MIME = frozenset({
    "video/mp4", "video/quicktime", "video/x-matroska", "video/webm",
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/ogg",
})


class _ProbeFailed(Exception):
    """ffprobe ran and deterministically reported failure (non-zero exit, bad output, over bound)."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _configured_input_root():
    root = os.environ.get("MEDIA_PROBE_INPUT_ROOT")
    return Path(root).resolve() if root else None


def _configured_store():
    root = os.environ.get("MEDIA_PROBE_ARTIFACT_ROOT")
    if not root:
        return None
    return LocalArtifactStore(root=root, subdir="media_probe", suffix=".json")


class MediaProbeAdapter:
    name = "media_probe"

    # Capability-specific evidence fields -- see core/external_execution_boundary.py
    # _UNIVERSAL_EVIDENCE_KEYS for the shared core (adapter_name, provider_status,
    # result_ref, result_checksum, ...). The full normalized probe result lives
    # in the stored JSON artifact, never in evidence.
    evidence_extra_keys = frozenset({
        "operation", "input_mime_type", "input_size", "detected_format",
        "stream_count", "elapsed_ms", "ffprobe_version",
    })

    def __init__(self, *, input_root=None, store=None):
        self.input_root = Path(input_root).resolve() if input_root is not None else _configured_input_root()
        self.store = store if store is not None else _configured_store()
        self._ffprobe_version_cache: str | None = None

    def submit(self, request: dict) -> SubmitResult:
        payload = request.get("payload") if isinstance(request, dict) else None
        contract_id = str(request.get("contract_id") or "") if isinstance(request, dict) else ""
        try:
            validated = self._validate_input(payload)
        except ValueError as exc:
            return SubmitResult("failed", failure_code=f"media_probe_{exc}"[:120])
        if self.store is None:
            return SubmitResult("failed", failure_code="media_probe_storage_unconfigured")

        started = time.monotonic()
        try:
            probe, stream_count = self._ffprobe(validated["path"])
        except FileNotFoundError:
            return SubmitResult("failed", failure_code="media_probe_ffprobe_not_installed")
        except _ProbeFailed as exc:
            return SubmitResult("failed", failure_code=str(exc)[:120])
        except subprocess.TimeoutExpired:
            return SubmitResult("failed", failure_code="media_probe_timeout")
        except Exception:
            # Nothing durable has happened yet -- a known failure, not an
            # uncertain one.
            return SubmitResult("failed", failure_code="media_probe_submit_exception")
        elapsed_ms = int((time.monotonic() - started) * 1000)

        metadata = _extract_metadata(probe)
        metadata["mime_type"] = validated["mime_type"]
        metadata["size"] = validated["size"]
        result_bytes = json.dumps(metadata, sort_keys=True).encode("utf-8")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tmp:
                tmp.write(result_bytes)
                tmp_path = Path(tmp.name)
            stored = self.store.put(
                path=tmp_path,
                identity=contract_id,
                metadata={"operation": "media_probe"},
                mime_type="application/json",
            )
        except ArtifactStoreError as exc:
            status = "outcome_unknown" if exc.uncertain else "failed"
            return SubmitResult(status, failure_code=exc.code[:120])
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        return SubmitResult(
            "completed",
            result_ref=stored.result_ref,
            evidence={
                "adapter_name": self.name,
                "provider_status": "completed",
                "result_ref": stored.result_ref,
                "result_checksum": stored.sha256,
                "operation": "media_probe",
                "input_mime_type": validated["mime_type"],
                "input_size": str(validated["size"]),
                "detected_format": str(metadata.get("container") or "")[:80],
                "stream_count": str(stream_count),
                "elapsed_ms": str(elapsed_ms),
                "ffprobe_version": self._get_ffprobe_version(),
            },
        )

    def poll(self, job) -> PollResult:
        # execution_mode is "sync" -- submit() already returned a terminal
        # result and the boundary never schedules this job for polling.
        return PollResult("outcome_unknown", failure_code="media_probe_unexpected_poll")

    def _validate_input(self, payload) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("payload")
        raw_ref = payload.get("result_ref")
        mime_type = payload.get("mime_type")
        size = payload.get("size")
        sha256_hex = payload.get("sha256")
        if not isinstance(raw_ref, str) or not raw_ref:
            raise ValueError("result_ref_missing")
        if not isinstance(mime_type, str) or not mime_type:
            raise ValueError("mime_type_missing")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("size_missing")
        if not isinstance(sha256_hex, str) or not sha256_hex:
            raise ValueError("sha256_missing")

        # 1. require configured root
        if self.input_root is None:
            raise ValueError("input_root_not_configured")

        # 2. inspect raw result_ref before resolve -- reject remote/provider-specific
        if "://" in raw_ref or raw_ref.lstrip().startswith("{"):
            raise ValueError("remote_unsupported")

        # 3. reject symlink before .resolve()
        raw_path = Path(raw_ref)
        if raw_path.is_symlink():
            raise ValueError("symlink_rejected")

        # 4. resolve
        resolved = raw_path.resolve()

        # 5. require containment under approved root
        try:
            resolved.relative_to(self.input_root)
        except ValueError:
            raise ValueError("path_outside_root")

        # 6. require regular file
        if not resolved.is_file():
            raise ValueError("path_not_found")

        # 7/8/9. non-empty, bounded max size, recompute size
        actual_size = resolved.stat().st_size
        if actual_size == 0:
            raise ValueError("empty_file")
        if actual_size > _MAX_INPUT_BYTES:
            raise ValueError("input_too_large")

        # 10. compare recomputed size with supplied size
        if actual_size != size:
            raise ValueError("size_mismatch")

        # 11/12. streaming SHA-256, compare with supplied checksum
        if _sha256_file(resolved).lower() != sha256_hex.lower():
            raise ValueError("checksum_mismatch")

        # 13. explicit MIME allowlist
        if mime_type not in _ALLOWED_INPUT_MIME:
            raise ValueError("mime_unsupported")

        return {"path": resolved, "mime_type": mime_type, "size": actual_size}

    @staticmethod
    def _ffprobe(path: Path) -> tuple[dict, int]:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise _ProbeFailed(f"media_probe_ffprobe_failed:{result.stderr[:80]}")
        if len(result.stdout.encode("utf-8", "ignore")) > _MAX_STDOUT_BYTES:
            raise _ProbeFailed("media_probe_oversized_stdout")
        try:
            probe = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise _ProbeFailed("media_probe_invalid_ffprobe_output")
        streams = probe.get("streams") or []
        if len(streams) > _MAX_STREAMS:
            raise _ProbeFailed("media_probe_too_many_streams")
        return probe, len(streams)

    def _get_ffprobe_version(self) -> str:
        if self._ffprobe_version_cache is not None:
            return self._ffprobe_version_cache
        version = ""
        try:
            result = subprocess.run(
                ["ffprobe", "-version"], capture_output=True, text=True, timeout=_VERSION_TIMEOUT_SECONDS,
            )
            if result.returncode == 0 and result.stdout:
                parts = result.stdout.splitlines()[0].split()
                if "version" in parts:
                    idx = parts.index("version")
                    if idx + 1 < len(parts):
                        version = parts[idx + 1][:40]
        except Exception:
            version = ""
        self._ffprobe_version_cache = version
        return version


def _extract_metadata(probe: dict) -> dict:
    fmt = probe.get("format") or {}
    streams = (probe.get("streams") or [])[:_MAX_STREAMS]
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
    audio_codecs = sorted({s["codec_name"] for s in audio_streams if s.get("codec_name")})

    return {
        "duration": _to_float(fmt.get("duration")),
        "container": fmt.get("format_name"),
        "video_codec": video.get("codec_name") if video else None,
        "width": _to_int(video.get("width")) if video else None,
        "height": _to_int(video.get("height")) if video else None,
        "audio_stream_count": len(audio_streams),
        "audio_codecs": ",".join(audio_codecs) or None,
        "subtitle_stream_count": len(subtitle_streams),
        "bitrate": _to_int(fmt.get("bit_rate")),
    }


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
