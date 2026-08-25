import json
import inspect
import sys
import types

import interaction_engine
import core
from core import ExecutionContext
from core.router import ExecutionClass, Intent
from core.turn_coordinator_runtime import resolve_business_interaction_analysis_capability


VALID_PAYLOAD = {
    "summary": "סיכום",
    "decisions": ["החלטה"],
    "tasks": [{"title": "משימה", "owner": "בעלים", "due": "2026-08-25"}],
    "risks": ["סיכון"],
    "next_steps": "המשך",
    "sentiment": "neutral",
    "keywords": ["מילה"],
}


def _interaction(title="פגישת ספק", content="הוחלט לבדוק ספק חלופי"):
    return interaction_engine.InteractionSchema(
        source_channel="calendar",
        raw_id=title,
        title=title,
        raw_content=content,
    )


def _fake_anthropic(monkeypatch, payload=VALID_PAYLOAD):
    calls = []

    class Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(text=json.dumps(payload))],
                usage=None,
                id="req-1",
            )

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(
        Anthropic=lambda **kwargs: types.SimpleNamespace(messages=Messages()),
    ))
    return calls


def test_intent_and_capability_are_canonical():
    capability = resolve_business_interaction_analysis_capability()

    assert Intent.ANALYZE_BUSINESS_INTERACTION in Intent.ALL
    assert capability.capability_id == "business.interaction_analysis"
    assert capability.execution_class is ExecutionClass.NARROW_MODEL
    assert capability.executor_ref == "interaction_engine.analysis"
    assert Intent.ANALYZE_BUSINESS_INTERACTION not in {
        Intent.ASK_QUESTION, Intent.GENERATE_REPORT, Intent.SUMMARIZE,
    }


def test_empty_interaction_creates_no_operation_or_context(monkeypatch):
    operations = []
    contexts = []
    monkeypatch.setattr(core, "create_operation", operations.append)
    monkeypatch.setattr(core, "create_execution_context", contexts.append)

    result = interaction_engine.analyze_interaction(
        interaction_engine.InteractionSchema(source_channel="calendar", raw_id="empty", title="")
    )

    assert result.summary == "אין תוכן לניתוח."
    assert operations == []
    assert contexts == []


def test_eligible_interaction_creates_one_context_at_direct_provider_boundary(monkeypatch):
    calls = _fake_anthropic(monkeypatch)
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

    result = interaction_engine.analyze_interaction(_interaction())

    assert result.summary == "סיכום"
    assert len(operations) == len(contexts) == 1
    assert isinstance(contexts[0], ExecutionContext)
    assert calls and calls[0]["model"] == "claude-sonnet-4-6"
    assert contexts[0].contract_id is None
    assert contexts[0].turn_id is None
    assert contexts[0].parent_operation_id is None
    source = inspect.getsource(interaction_engine.analyze_interaction)
    assert "capability_id" not in source
    assert "operation_id" not in source


def test_two_eligible_interactions_have_two_operations(monkeypatch):
    _fake_anthropic(monkeypatch)
    operations = []
    real_operation = core.create_operation
    monkeypatch.setattr(
        core,
        "create_operation",
        lambda capability: operations.append(real_operation(capability)) or operations[-1],
    )

    interaction_engine.analyze_interaction(_interaction("אחד"))
    interaction_engine.analyze_interaction(_interaction("שניים"))

    assert len(operations) == 2
    assert operations[0].operation_id != operations[1].operation_id


def test_local_fallback_keeps_one_operation(monkeypatch):
    operations = []
    real_operation = core.create_operation
    monkeypatch.setattr(
        core,
        "create_operation",
        lambda capability: operations.append(real_operation(capability)) or operations[-1],
    )
    monkeypatch.setitem(sys.modules, "anthropic", None)

    result = interaction_engine.analyze_interaction(_interaction(content="מחיר ₪50000"))

    assert result.summary
    assert len(operations) == 1


def test_structural_verifier_accepts_valid_payload_and_rejects_invalid_shapes():
    assert interaction_engine.verify_interaction_analysis_payload(VALID_PAYLOAD) == VALID_PAYLOAD
    invalid_payloads = [
        {**VALID_PAYLOAD, "summary": 1},
        {**VALID_PAYLOAD, "decisions": [1]},
        {**VALID_PAYLOAD, "tasks": [{"title": "x"}]},
        {**VALID_PAYLOAD, "risks": [1]},
        {**VALID_PAYLOAD, "next_steps": None},
        {**VALID_PAYLOAD, "sentiment": "unknown"},
        {**VALID_PAYLOAD, "keywords": "word"},
    ]
    for payload in invalid_payloads:
        try:
            interaction_engine.verify_interaction_analysis_payload(payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid payload accepted: {payload!r}")


def test_legacy_malformed_output_behavior_is_unchanged(monkeypatch):
    class Messages:
        def create(self, **kwargs):
            return types.SimpleNamespace(content=[types.SimpleNamespace(text="not json")], usage=None, id="req-1")

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(
        Anthropic=lambda **kwargs: types.SimpleNamespace(messages=Messages()),
    ))

    result = interaction_engine.analyze_interaction(_interaction())

    assert result == interaction_engine.InteractionAnalysis()
