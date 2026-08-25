# voice_stt_adapter.py — F16 Media Layer: Speech-to-Text
#
# Transcribes voice note audio bytes via OpenAI Whisper (primary). Groq is
# left commented out as a Phase 2 speed upgrade, not wired into transcribe().
# Lazy SDK imports inside the provider helper — no hard dependency at import time.

from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from numbers import Real

from core import create_execution_context, create_operation
from core.usage_telemetry import usage_attribution_from_context

logger = logging.getLogger(__name__)

# Whisper API hard cap (Groq and OpenAI both reject larger files).
MAX_STT_BYTES = 25 * 1024 * 1024

_NIKUD_RE = re.compile(r"[֑-ׇ]")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class MediaError:
    error_code: str
    error_message: str
    retryable: bool


@dataclass
class TranscriptResult:
    raw_transcript: str = ""
    normalized_transcript: str = ""
    language: str = ""
    confidence: float | None = None
    duration_sec: float | None = None
    provider_used: str = ""
    error: MediaError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def verify_transcription_result_structure(result: object) -> TranscriptResult:
    """Validate only the bounded structure of a successful transcription."""
    if not isinstance(result, TranscriptResult):
        raise ValueError("transcription result must be a TranscriptResult")
    if not isinstance(result.raw_transcript, str):
        raise ValueError("raw_transcript must be a string")
    if not isinstance(result.language, str):
        raise ValueError("language must be a string")
    if result.duration_sec is not None and (
        isinstance(result.duration_sec, bool) or not isinstance(result.duration_sec, Real)
    ):
        raise ValueError("duration_sec must be numeric or None")
    return result


def _normalize_hebrew(text: str) -> str:
    """Strip Hebrew nikud (cantillation/vowel points) and collapse whitespace."""
    stripped = _NIKUD_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", stripped).strip()


def _transcribe_openai(
    path: str,
    *,
    execution_context=None,
) -> tuple[str, str, float | None]:
    """Returns (raw_transcript, language, duration_seconds). Raises on failure.

    duration_seconds comes from OpenAI's own verbose_json response (real
    provider-reported audio length), or remains None when both provider
    duration fields are absent. Unknown duration is recorded as unknown,
    never estimated from file size.
    """
    from openai import OpenAI

    stt_model = os.getenv("OPENAI_STT_MODEL", "whisper-1")
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    with open(path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=f,
            model=stt_model,
            language="he",
            prompt="משימה, ליד, זיכרון, רעיון, עסקה, תקבע, פגישה, תשלח, תזכיר, תעדכן, שלום, נדלן, ייבוא, כספים",
            response_format="verbose_json",
        )
    duration = getattr(resp, "duration", None)
    if duration is None:
        usage = getattr(resp, "usage", None)
        duration = getattr(usage, "seconds", None) if usage is not None else None
    request_id = getattr(resp, "_request_id", None)
    measurement_status = "measured" if duration is not None else "unknown"

    # Cost Telemetry Reliability PR2 (shadow only): durable
    # provider/service/model-generic recording — additive, doesn't feed
    # AI_Usage_Daily or EMERGENCY_STOP_AI yet.
    try:
        from core.usage_telemetry import record_stt_usage
        record_stt_usage(
            source           = "voice_stt_adapter",
            model            = stt_model,
            duration_seconds = float(duration) if duration is not None else None,
            measurement_status = measurement_status,
            caller           = "voice_stt_adapter._transcribe_openai",
            request_id       = request_id,
            **usage_attribution_from_context(execution_context),
        )
    except Exception as e:
        logger.error(f"[voice_stt] usage recording failed (non-fatal): {e}")

    return (resp.text or "").strip(), "he", duration


# Phase 2 upgrade (faster, not active): Groq whisper-large-v3.
# def _transcribe_groq(path: str) -> tuple[str, str]:
#     import groq
#     client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
#     with open(path, "rb") as f:
#         resp = client.audio.transcriptions.create(
#             file=f,
#             model=os.getenv("GROQ_STT_MODEL", "whisper-large-v3"),
#             language="he",
#         )
#     return (resp.text or "").strip(), getattr(resp, "language", "") or "he"


def _audio_to_tempfile(audio_bytes: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)
        return path
    except Exception:
        os.close(fd)
        raise


def transcribe(audio_bytes: bytes, mime_type: str) -> TranscriptResult:
    """
    Transcribe audio bytes to Hebrew text via OpenAI Whisper.
    Returns TranscriptResult with .error set (never raises) on total failure.
    """
    if len(audio_bytes) > MAX_STT_BYTES:
        return TranscriptResult(
            error=MediaError(
                "OVERSIZED",
                "הקובץ גדול מ-25MB ולא ניתן לתמלל. נסה קובץ קצר יותר.",
                False,
            )
        )

    suffix = ".ogg" if "ogg" in mime_type else ".mp3" if "mpeg" in mime_type else ".bin"
    tmp_path = _audio_to_tempfile(audio_bytes, suffix)
    try:
        if os.environ.get("OPENAI_API_KEY"):
            try:
                from core.turn_coordinator_runtime import resolve_voice_transcription_capability

                capability = resolve_voice_transcription_capability()
                operation = create_operation(capability)
                execution_context = create_execution_context(capability, operation)
                raw, lang, duration = _transcribe_openai(
                    tmp_path,
                    execution_context=execution_context,
                )
                logger.info("[voice_stt] provider=openai ok len=%d duration_sec=%s", len(raw), duration)
                return TranscriptResult(
                    raw_transcript=raw,
                    normalized_transcript=_normalize_hebrew(raw),
                    language=lang,
                    duration_sec=duration,
                    provider_used="openai",
                )
            except Exception as e:
                logger.warning("[voice_stt] provider=openai failed error=%s", e)

        # Phase 2 upgrade (not active):
        # try:
        #     if os.environ.get("GROQ_API_KEY"):
        #         raw, lang = _transcribe_groq(tmp_path)
        #         return TranscriptResult(
        #             raw_transcript=raw,
        #             normalized_transcript=_normalize_hebrew(raw),
        #             language=lang,
        #             provider_used="groq",
        #         )
        # except Exception as e:
        #     logger.error("[voice_stt] provider=groq failed error=%s", e)

        return TranscriptResult(
            error=MediaError(
                "STT_FAILED",
                "התמלול נכשל. נסה שוב מאוחר יותר.",
                True,
            )
        )
    finally:
        os.remove(tmp_path)


if __name__ == "__main__":
    assert _normalize_hebrew("שָׁלוֹם   עוֹלָם") == "שלום עולם"
    assert _normalize_hebrew("hello") == "hello"
    print("✅ nikud strip + whitespace collapse OK")

    too_big = transcribe(b"x" * (MAX_STT_BYTES + 1), "audio/ogg")
    assert not too_big.ok and too_big.error.error_code == "OVERSIZED"
    print("✅ oversized audio → OVERSIZED OK")

    saved_groq = os.environ.pop("GROQ_API_KEY", None)
    saved_openai = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test-key"
    import sys
    from unittest.mock import patch

    with patch.object(sys.modules[__name__], "_transcribe_openai", return_value=("שלום", "he", 1.23)):
        result = transcribe(b"fake-audio-bytes", "audio/ogg")
    assert result.ok and result.provider_used == "openai"
    if saved_openai is not None:
        os.environ["OPENAI_API_KEY"] = saved_openai
    else:
        del os.environ["OPENAI_API_KEY"]
    if saved_groq is not None:
        os.environ["GROQ_API_KEY"] = saved_groq
    print("✅ transcribe works with OPENAI_API_KEY only (Groq not required) OK")

    print("voice_stt_adapter.py self-test OK")
