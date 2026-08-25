import json
import sys
import types

import core
import interaction_engine


PAYLOAD = {
    "summary": "סיכום",
    "decisions": [],
    "tasks": [],
    "risks": [],
    "next_steps": "המשך",
    "sentiment": "neutral",
    "keywords": [],
}


def _interaction(title="פגישה"):
    return interaction_engine.InteractionSchema(
        source_channel="calendar", raw_id=title, title=title, raw_content="תוכן"
    )


def _fake_anthropic(monkeypatch):
    class Messages:
        def create(self, **_kwargs):
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(text=json.dumps(PAYLOAD))],
                usage=types.SimpleNamespace(input_tokens=3, output_tokens=2),
                id="anthropic-request",
            )

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        types.SimpleNamespace(
            Anthropic=lambda **_kwargs: types.SimpleNamespace(messages=Messages())
        ),
    )


def _capture_contexts(monkeypatch):
    operations = []
    contexts = []
    real_operation = core.create_operation
    real_context = core.create_execution_context

    def create_operation(capability):
        operation = real_operation(capability)
        operations.append(operation)
        return operation

    def create_context(capability, operation):
        context = real_context(capability, operation)
        contexts.append(context)
        return context

    monkeypatch.setattr(core, "create_operation", create_operation)
    monkeypatch.setattr(core, "create_execution_context", create_context)
    return operations, contexts


def test_paid_interaction_translates_existing_context_once(monkeypatch):
    _fake_anthropic(monkeypatch)
    operations, contexts = _capture_contexts(monkeypatch)
    events = []
    monkeypatch.setattr(
        "core.usage_telemetry.record_llm_usage",
        lambda **kwargs: events.append(kwargs),
    )

    result = interaction_engine.analyze_interaction(_interaction())

    assert result.summary == "סיכום"
    assert len(operations) == len(contexts) == len(events) == 1
    context = contexts[0]
    assert events[0]["capability_id"] == "business.interaction_analysis"
    assert events[0]["execution_class"] == "NARROW_MODEL"
    assert events[0]["operation_id"] == context.operation.operation_id
    assert events[0]["request_id"] == "anthropic-request"
    assert "workflow_id" not in events[0]
    assert "workflow_run_id" not in events[0]


def test_two_paid_interactions_have_distinct_context_operations_and_events(monkeypatch):
    _fake_anthropic(monkeypatch)
    operations, contexts = _capture_contexts(monkeypatch)
    events = []
    monkeypatch.setattr(
        "core.usage_telemetry.record_llm_usage",
        lambda **kwargs: events.append(kwargs),
    )

    interaction_engine.analyze_interaction(_interaction("אחת"))
    interaction_engine.analyze_interaction(_interaction("שתיים"))

    assert len(operations) == len(contexts) == len(events) == 2
    assert len({item.operation_id for item in operations}) == 2
    assert {event["operation_id"] for event in events} == {
        context.operation.operation_id for context in contexts
    }


def test_empty_interaction_has_no_context_or_usage_event(monkeypatch):
    operations, contexts = _capture_contexts(monkeypatch)
    events = []
    monkeypatch.setattr(
        "core.usage_telemetry.record_llm_usage",
        lambda **kwargs: events.append(kwargs),
    )

    result = interaction_engine.analyze_interaction(
        interaction_engine.InteractionSchema(
            source_channel="calendar", raw_id="empty", title=""
        )
    )

    assert result.summary == "אין תוכן לניתוח."
    assert operations == contexts == events == []


def test_telemetry_failure_is_nonfatal_and_fallback_has_no_event(monkeypatch):
    _fake_anthropic(monkeypatch)
    operations, contexts = _capture_contexts(monkeypatch)
    monkeypatch.setattr(
        "core.usage_telemetry.record_llm_usage",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("telemetry down")),
    )

    assert interaction_engine.analyze_interaction(_interaction()).summary == "סיכום"
    assert len(operations) == len(contexts) == 1

    operations.clear()
    contexts.clear()
    monkeypatch.setitem(sys.modules, "anthropic", None)
    result = interaction_engine.analyze_interaction(_interaction("fallback"))

    assert result.summary
    assert len(operations) == len(contexts) == 1

