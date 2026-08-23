"""Focused Track F #5 regression tests for voice STT idempotency."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import media_handler
from guards.idempotency import IdempotencyStore
from voice_stt_adapter import TranscriptResult


_VOICE_ARGS = (b"audio", "audio/ogg", "voice-1", "user-1", "general", "owner-1")


def _success() -> TranscriptResult:
    return TranscriptResult(raw_transcript="hello", normalized_transcript="hello")


def _failure() -> TranscriptResult:
    return TranscriptResult(
        error=media_handler.MediaError("STT_FAILED", "temporary", True),
    )


def test_stt_failure_releases_reservation_for_immediate_retry():
    store = IdempotencyStore()

    with patch.object(media_handler, "_idem_store", store), \
         patch.object(media_handler, "transcribe", side_effect=[_failure(), _success()]), \
         patch.object(media_handler, "_log_unhandled_voice_note"):
        first = media_handler.handle_voice_note(*_VOICE_ARGS)
        second = media_handler.handle_voice_note(*_VOICE_ARGS)

    assert not first.ok and first.error.error_code == "STT_FAILED"
    assert second.ok and second.error is None


def test_active_voice_duplicate_is_blocked_until_stt_finishes():
    store = IdempotencyStore()
    started = Event()
    finish = Event()

    def slow_success(*_args):
        started.set()
        assert finish.wait(timeout=2)
        return _success()

    with patch.object(media_handler, "_idem_store", store), \
         patch.object(media_handler, "transcribe", side_effect=slow_success), \
         patch.object(media_handler, "_log_unhandled_voice_note"):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(media_handler.handle_voice_note, *_VOICE_ARGS)
            assert started.wait(timeout=2)
            second = media_handler.handle_voice_note(*_VOICE_ARGS)
            finish.set()
            first = first_future.result(timeout=2)

    assert not second.ok and second.error.error_code == "DUPLICATE"
    assert first.ok


def test_successful_voice_processing_remains_duplicate_suppressed():
    store = IdempotencyStore()

    with patch.object(media_handler, "_idem_store", store), \
         patch.object(media_handler, "transcribe", return_value=_success()) as transcribe, \
         patch.object(media_handler, "_log_unhandled_voice_note"):
        first = media_handler.handle_voice_note(*_VOICE_ARGS)
        second = media_handler.handle_voice_note(*_VOICE_ARGS)

    assert first.ok
    assert not second.ok and second.error.error_code == "DUPLICATE"
    transcribe.assert_called_once()
