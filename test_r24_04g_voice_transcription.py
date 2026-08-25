import os
from unittest.mock import patch

import voice_stt_adapter
from core.router import ExecutionClass, Intent
from core.turn_coordinator_runtime import resolve_voice_transcription_capability


def test_intent_and_capability_are_canonical():
    capability = resolve_voice_transcription_capability()

    assert Intent.TRANSCRIBE_VOICE_NOTE in Intent.ALL
    assert capability.capability_id == "media.voice_transcription"
    assert capability.execution_class is ExecutionClass.NARROW_MODEL
    assert capability.executor_ref == "voice_stt_adapter._transcribe_openai"
    assert capability.fallback_ref == ""


def test_pre_paid_rejections_create_no_identity(monkeypatch):
    operations = []
    contexts = []
    monkeypatch.setattr(voice_stt_adapter, "create_operation", operations.append)
    monkeypatch.setattr(voice_stt_adapter, "create_execution_context", contexts.append)

    oversized = voice_stt_adapter.transcribe(
        b"x" * (voice_stt_adapter.MAX_STT_BYTES + 1), "audio/ogg"
    )
    with patch.dict(os.environ, {}, clear=True):
        missing_credential = voice_stt_adapter.transcribe(b"audio", "audio/ogg")

    assert oversized.error.error_code == "OVERSIZED"
    assert missing_credential.error.error_code == "STT_FAILED"
    assert operations == contexts == []


def test_eligible_transcription_creates_one_context_and_passes_same_context(monkeypatch):
    operations = []
    contexts = []
    real_operation = voice_stt_adapter.create_operation
    real_context = voice_stt_adapter.create_execution_context

    def create_operation(capability):
        operation = real_operation(capability)
        operations.append(operation)
        return operation

    def create_context(capability, operation):
        context = real_context(capability, operation)
        contexts.append(context)
        return context

    monkeypatch.setattr(voice_stt_adapter, "create_operation", create_operation)
    monkeypatch.setattr(voice_stt_adapter, "create_execution_context", create_context)
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
         patch.object(voice_stt_adapter, "_transcribe_openai") as provider:
        provider.return_value = ("שלום", "he", 1.2)
        result = voice_stt_adapter.transcribe(b"audio", "audio/ogg")

    assert result.ok and result.normalized_transcript == "שלום"
    assert len(operations) == len(contexts) == 1
    provider.assert_called_once_with(
        provider.call_args.args[0], execution_context=contexts[0]
    )
    assert contexts[0].resolved_capability.capability_id == "media.voice_transcription"
    assert contexts[0].operation.operation_id == operations[0].operation_id


def test_tempfile_failure_creates_no_paid_identity(monkeypatch):
    operations = []
    monkeypatch.setattr(voice_stt_adapter, "create_operation", operations.append)
    monkeypatch.setattr(voice_stt_adapter, "_audio_to_tempfile", lambda *_: (_ for _ in ()).throw(OSError("disk")))

    try:
        voice_stt_adapter.transcribe(b"audio", "audio/ogg")
    except OSError:
        pass
    else:
        raise AssertionError("tempfile failure behavior changed")
    assert operations == []


def test_structural_verifier_preserves_contract_and_rejects_invalid_types():
    valid = voice_stt_adapter.TranscriptResult(
        raw_transcript="שלום", language="he", duration_sec=1.2,
    )
    assert voice_stt_adapter.verify_transcription_result_structure(valid) is valid
    for invalid in (
        voice_stt_adapter.TranscriptResult(raw_transcript=1, language="he"),
        voice_stt_adapter.TranscriptResult(raw_transcript="x", language=1),
        voice_stt_adapter.TranscriptResult(raw_transcript="x", language="he", duration_sec="1"),
    ):
        try:
            voice_stt_adapter.verify_transcription_result_structure(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid result accepted: {invalid!r}")


def test_empty_and_missing_duration_behavior_remains_unchanged(monkeypatch):
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
         patch.object(voice_stt_adapter, "_transcribe_openai", return_value=("", "he", None)):
        result = voice_stt_adapter.transcribe(b"audio", "audio/ogg")

    assert result.ok
    assert result.raw_transcript == ""
    assert result.normalized_transcript == ""
    assert result.duration_sec is None
