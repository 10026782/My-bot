"""Media Probe capability adapter — POC / NOT PRODUCTION READY.

Local media file -> bounded structured metadata via ffprobe. Read-only: no
conversion, no upload, no mutation. See docs/research/MEDIA_PROBE_POC.md.

This is a sync capability (CapabilityContract.execution_mode == "sync"):
submit() runs ffprobe and returns a terminal SubmitResult directly — poll()
is never legitimately reached and exists only to satisfy the ExternalAdapter
contract.
"""

from __future__ import annotations

import json
import mimetypes
import subprocess
from pathlib import Path

from core.external_execution_boundary import PollResult, SubmitResult

_TIMEOUT_SECONDS = 15


class _ProbeFailed(Exception):
    """ffprobe ran and deterministically reported failure (non-zero exit, bad output)."""


class MediaProbeAdapter:
    name = "media_probe"

    # Capability-specific evidence fields — see core/external_execution_boundary.py
    # _UNIVERSAL_EVIDENCE_KEYS for the shared core (adapter_name, provider_status,
    # completed_at, result_ref, ...).
    evidence_extra_keys = frozenset({
        "mime_type", "duration", "container", "video_codec", "width", "height",
        "audio_stream_count", "audio_codecs", "subtitle_stream_count", "bitrate",
    })

    def submit(self, request: dict) -> SubmitResult:
        payload = request.get("payload") if isinstance(request, dict) else None
        try:
            path = self._validate_path(payload)
        except ValueError as exc:
            return SubmitResult("failed", failure_code=f"media_probe_{exc}"[:120])

        try:
            probe = self._ffprobe(path)
        except FileNotFoundError:
            return SubmitResult("failed", failure_code="media_probe_ffprobe_not_installed")
        except _ProbeFailed as exc:
            return SubmitResult("failed", failure_code=str(exc)[:120])
        except subprocess.TimeoutExpired:
            return SubmitResult("outcome_unknown", failure_code="media_probe_timeout")
        except Exception:
            # Anything past this point is uncertain, not a known failure —
            # never presented as success.
            return SubmitResult("outcome_unknown", failure_code="media_probe_submit_exception")

        metadata = _extract_metadata(path, probe)
        return SubmitResult(
            "completed",
            result_ref=str(path),
            evidence={
                "adapter_name": self.name,
                "provider_status": "completed",
                "result_ref": str(path),
                **{k: ("" if v is None else str(v)) for k, v in metadata.items()},
            },
        )

    def poll(self, job) -> PollResult:
        # execution_mode is "sync" — submit() already returned a terminal
        # result and the boundary never schedules this job for polling.
        return PollResult("outcome_unknown", failure_code="media_probe_unexpected_poll")

    @staticmethod
    def _validate_path(payload) -> Path:
        if not isinstance(payload, dict):
            raise ValueError("payload")
        raw = payload.get("path")
        if not isinstance(raw, str) or not raw:
            raise ValueError("path_missing")
        path = Path(raw)
        if not path.is_file():
            raise ValueError("path_not_found")
        return path

    @staticmethod
    def _ffprobe(path: Path) -> dict:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise _ProbeFailed(f"media_probe_ffprobe_failed:{result.stderr[:80]}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            raise _ProbeFailed("media_probe_invalid_ffprobe_output")


def _extract_metadata(path: Path, probe: dict) -> dict:
    fmt = probe.get("format") or {}
    streams = probe.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

    mime_type, _ = mimetypes.guess_type(str(path))
    audio_codecs = sorted({s["codec_name"] for s in audio_streams if s.get("codec_name")})

    return {
        "mime_type": mime_type,
        "size": _to_int(fmt.get("size")) or path.stat().st_size,
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
