# voice_stt_adapter.py — F16 Media Layer: Speech-to-Text
#
# Transcribes voice note audio bytes via Groq Whisper (primary) → OpenAI
# Whisper (fallback), mirroring llm_fallback.py's provider-fallback style.
# Lazy SDK imports inside transcribe() — no hard dependency at import time.

from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass

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


def _normalize_hebrew(text: str) -> str:
    """Strip Hebrew nikud (cantillation/vowel points) and collapse whitespace."""
    stripped = _NIKUD_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", stripped).strip()


def _transcribe_groq(path: str) -> tuple[str, str]:
    """Returns (raw_transcript, language). Raises on failure."""
    import groq

    client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
    with open(path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=f,
            model=os.getenv("GROQ_STT_MODEL", "whisper-large-v3"),
            language="he",
        )
    return (resp.text or "").strip(), getattr(resp, "language", "") or "he"


def _transcribe_openai(path: str) -> tuple[str, str]:
    """Returns (raw_transcript, language). Raises on failure."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    with open(path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=f,
            model=os.getenv("OPENAI_STT_MODEL", "whisper-1"),
            language="he",
        )
    return (resp.text or "").strip(), "he"


def transcribe(audio_bytes: bytes, mime_type: str) -> TranscriptResult:
    """
    Transcribe audio bytes to Hebrew text. Groq primary, OpenAI fallback.
    Returns TranscriptResult with .error set (never raises) on total failure.
    """
    if not audio_bytes:
        return TranscriptResult(error=MediaError("EMPTY_AUDIO", "no audio bytes provided", False))

    if len(audio_bytes) > MAX_STT_BYTES:
        return TranscriptResult(
            error=MediaError(
                "AUDIO_TOO_LARGE",
                f"audio is {len(audio_bytes)} bytes, max is {MAX_STT_BYTES}",
                False,
            )
        )

    suffix = ".ogg" if "ogg" in mime_type else ".mp3" if "mpeg" in mime_type else ".bin"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)

        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            try:
                raw, lang = _transcribe_groq(path)
                logger.info("[voice_stt] provider=groq ok len=%d", len(raw))
                return TranscriptResult(
                    raw_transcript=raw,
                    normalized_transcript=_normalize_hebrew(raw),
                    language=lang,
                    provider_used="groq",
                )
            except Exception as e:
                logger.warning("[voice_stt] provider=groq failed error=%s", e)

        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            try:
                raw, lang = _transcribe_openai(path)
                logger.info("[voice_stt] provider=openai ok len=%d", len(raw))
                return TranscriptResult(
                    raw_transcript=raw,
                    normalized_transcript=_normalize_hebrew(raw),
                    language=lang,
                    provider_used="openai",
                )
            except Exception as e:
                logger.warning("[voice_stt] provider=openai failed error=%s", e)

        return TranscriptResult(
            error=MediaError(
                "STT_UNAVAILABLE",
                "no STT provider succeeded (GROQ_API_KEY/OPENAI_API_KEY missing or both failed)",
                True,
            )
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    assert _normalize_hebrew("שָׁלוֹם   עוֹלָם") == "שלום עולם"
    assert _normalize_hebrew("hello") == "hello"

    too_big = transcribe(b"x" * (MAX_STT_BYTES + 1), "audio/ogg")
    assert not too_big.ok and too_big.error.error_code == "AUDIO_TOO_LARGE"

    empty = transcribe(b"", "audio/ogg")
    assert not empty.ok and empty.error.error_code == "EMPTY_AUDIO"

    no_keys = dict(os.environ)
    os.environ.pop("GROQ_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)
    no_provider = transcribe(b"fake-audio-bytes", "audio/ogg")
    assert not no_provider.ok and no_provider.error.error_code == "STT_UNAVAILABLE"
    os.environ.clear()
    os.environ.update(no_keys)

    print("voice_stt_adapter.py self-test OK")
