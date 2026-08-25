import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import voice_stt_adapter
from core import create_execution_context, create_operation
from core.turn_coordinator_runtime import resolve_voice_transcription_capability
from core.usage_telemetry import usage_attribution_from_context


class FakeTranscriptions:
    def __init__(self, duration=1.25):
        self.duration = duration
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text="שלום", duration=self.duration)


class FakeOpenAI:
    transcriptions = None

    def __init__(self, **_kwargs):
        self.audio = SimpleNamespace(transcriptions=FakeOpenAI.transcriptions)


def _context():
    capability = resolve_voice_transcription_capability()
    operation = create_operation(capability)
    return create_execution_context(capability, operation)


def test_transcription_usage_gets_one_canonical_event_from_existing_context(monkeypatch):
    provider = FakeTranscriptions()
    FakeOpenAI.transcriptions = provider
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    events = []
    operations = []
    contexts = []
    real_operation = voice_stt_adapter.create_operation
    real_context = voice_stt_adapter.create_execution_context

    def create_operation_spy(capability):
        operation = real_operation(capability)
        operations.append(operation)
        return operation

    def create_context_spy(capability, operation):
        context = real_context(capability, operation)
        contexts.append(context)
        return context

    monkeypatch.setattr(voice_stt_adapter, "create_operation", create_operation_spy)
    monkeypatch.setattr(voice_stt_adapter, "create_execution_context", create_context_spy)
    monkeypatch.setattr("core.usage_telemetry.record_stt_usage", lambda **kwargs: events.append(kwargs))
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
         patch.object(voice_stt_adapter, "usage_attribution_from_context", wraps=usage_attribution_from_context) as translate:
        first = voice_stt_adapter.transcribe(b"audio", "audio/ogg")
        second = voice_stt_adapter.transcribe(b"audio", "audio/ogg")

    assert first.ok and second.ok
    assert len(operations) == len(contexts) == len(events) == 2
    assert {event["capability_id"] for event in events} == {"media.voice_transcription"}
    assert {event["execution_class"] for event in events} == {"NARROW_MODEL"}
    assert [event["operation_id"] for event in events] == [
        context.operation.operation_id for context in contexts
    ]
    assert operations[0].operation_id != operations[1].operation_id
    assert translate.call_args_list[0].args == (contexts[0],)
    assert translate.call_args_list[1].args == (contexts[1],)
    assert provider.calls[0]["model"] == "whisper-1"
    assert provider.calls[0]["language"] == "he"
    assert provider.calls[0]["response_format"] == "verbose_json"


def test_legacy_helper_without_context_does_not_fabricate_attribution(monkeypatch, tmp_path):
    provider = FakeTranscriptions()
    FakeOpenAI.transcriptions = provider
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    events = []
    monkeypatch.setattr("core.usage_telemetry.record_stt_usage", lambda **kwargs: events.append(kwargs))

    path = tmp_path / "voice.ogg"
    path.write_bytes(b"audio")
    raw, language, duration = voice_stt_adapter._transcribe_openai(str(path))

    assert (raw, language, duration) == ("שלום", "he", 1.25)
    assert "capability_id" not in events[0]
    assert "execution_class" not in events[0]
    assert "operation_id" not in events[0]


def test_missing_duration_and_telemetry_failure_remain_non_fatal(monkeypatch, tmp_path):
    provider = FakeTranscriptions(duration=None)
    FakeOpenAI.transcriptions = provider
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    events = []
    monkeypatch.setattr("core.usage_telemetry.record_stt_usage", lambda **kwargs: events.append(kwargs))
    path = tmp_path / "voice.ogg"
    path.write_bytes(b"audio")

    assert voice_stt_adapter._transcribe_openai(str(path), execution_context=_context())[2] is None
    assert events == []

    provider.duration = 1.25
    monkeypatch.setattr(
        "core.usage_telemetry.record_stt_usage",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("telemetry down")),
    )
    raw, language, duration = voice_stt_adapter._transcribe_openai(
        str(path), execution_context=_context(),
    )
    assert (raw, language, duration) == ("שלום", "he", 1.25)
