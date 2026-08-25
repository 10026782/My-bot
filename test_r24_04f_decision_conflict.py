import inspect
import importlib
import json
import sys
import types

import core
import decision_confidence as dc
import pytest
dc = importlib.reload(dc)
from airtable_schema import DecisionEventFields as EF, DecisionTrustLevel as TL
from core import ExecutionContext
from core.router import ExecutionClass, Intent
from core.turn_coordinator_runtime import resolve_decision_conflict_detection_capability


_REAL_DETECT_CONFLICT_AI = dc.detect_conflict_ai


@pytest.fixture(autouse=True)
def _restore_detector(monkeypatch):
    monkeypatch.setattr(dc, "detect_conflict_ai", _REAL_DETECT_CONFLICT_AI)


def _event(event_id, *, trust=TL.T2, topic="price"):
    fields = {EF.TRUST_LEVEL: trust, EF.STATUS: "Active", EF.CLAIM_TOPIC: topic}
    return {"id": event_id, "fields": fields}


def _capture_identities(monkeypatch):
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


def _fake_anthropic(monkeypatch, *, raises=None):
    class Messages:
        def create(self, **_kwargs):
            if raises:
                raise raises
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text=json.dumps({
                    "is_conflict": False,
                    "aspect": None,
                    "severity": None,
                }))],
                usage=types.SimpleNamespace(input_tokens=4, output_tokens=3),
                id="anthropic-conflict-request",
            )

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        types.SimpleNamespace(
            Anthropic=lambda **_kwargs: types.SimpleNamespace(messages=Messages())
        ),
    )


def test_intent_and_capability_are_canonical():
    capability = resolve_decision_conflict_detection_capability()

    assert Intent.DETECT_DECISION_CONFLICT in Intent.ALL
    assert capability.capability_id == "business.decision_conflict_detection"
    assert capability.execution_class is ExecutionClass.NARROW_MODEL
    assert capability.executor_ref == "decision_confidence.detect_conflict_ai"
    assert capability.validator_ref == "decision_confidence.pair_eligibility.v1"
    assert capability.verification_ref == "decision_confidence.conflict_result_schema.v1"
    assert capability.fallback_ref == "llm_fallback"


def test_ineligible_pairs_create_no_identity(monkeypatch):
    operations, contexts = _capture_identities(monkeypatch)
    monkeypatch.setattr(dc, "detect_conflict_ai", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))
    dc._conflict_cache.clear()

    for events in (
        [_event("low-a", trust=TL.T0), _event("low-b", trust=TL.T0)],
        [_event("no-topic-a", topic=""), _event("no-topic-b", topic="")],
        [_event("different-a", topic="price"), _event("different-b", topic="date")],
        [_event("one", topic="price")],
    ):
        dc.detect_conflicts_ai_lazy(events)

    assert operations == contexts == []


def test_cache_hit_and_budget_exhaustion_create_no_identity(monkeypatch):
    operations, contexts = _capture_identities(monkeypatch)
    calls = []
    monkeypatch.setattr(dc, "detect_conflict_ai", lambda *_args, **_kwargs: calls.append(1) or dc.ConflictResult(False))
    dc._conflict_cache.clear()
    pair = [_event("cached-a"), _event("cached-b")]
    dc._conflict_cache[dc._event_pair_hash(*pair)] = dc.ConflictResult(False)
    dc.detect_conflicts_ai_lazy(pair)

    original_cap = dc._MAX_AI_COMPARISONS_PER_RUN
    dc._MAX_AI_COMPARISONS_PER_RUN = 0
    try:
        dc.detect_conflicts_ai_lazy([_event("budget-a"), _event("budget-b")])
    finally:
        dc._MAX_AI_COMPARISONS_PER_RUN = original_cap

    assert calls == []
    assert operations == contexts == []


def test_explicit_conflicts_empty_bypasses_paid_path(monkeypatch):
    calls = []
    monkeypatch.setattr(dc, "detect_conflicts_ai_lazy", lambda _events: calls.append(1))

    dc.calc_confidence([_event("explicit")], conflicts=[])

    assert calls == []


def test_multi_pair_scan_creates_one_context_operation_and_event_per_pair(monkeypatch):
    _fake_anthropic(monkeypatch)
    operations, contexts = _capture_identities(monkeypatch)
    helper_contexts = []
    events = []
    import llm_fallback

    real_helper = llm_fallback.call_anthropic_text

    def helper_wrapper(**kwargs):
        helper_contexts.append(kwargs["execution_context"])
        return real_helper(**kwargs)

    monkeypatch.setattr(llm_fallback, "call_anthropic_text", helper_wrapper)
    monkeypatch.setattr(
        "core.usage_telemetry.record_llm_usage",
        lambda **kwargs: events.append(kwargs),
    )
    dc._conflict_cache.clear()

    dc.detect_conflicts_ai_lazy([_event("a"), _event("b"), _event("c")])

    assert len(operations) == len(contexts) == len(helper_contexts) == len(events) == 3
    assert len({operation.operation_id for operation in operations}) == 3
    assert helper_contexts == contexts
    assert {event["operation_id"] for event in events} == {
        context.operation.operation_id for context in contexts
    }
    assert {event["capability_id"] for event in events} == {
        "business.decision_conflict_detection"
    }
    assert {event["execution_class"] for event in events} == {"NARROW_MODEL"}

    dc.detect_conflicts_ai_lazy([_event("a"), _event("b"), _event("c")])
    assert len(operations) == len(contexts) == len(helper_contexts) == len(events) == 3


def test_fallback_retains_same_context_and_attribution(monkeypatch):
    _fake_anthropic(monkeypatch, raises=TimeoutError("timeout"))
    monkeypatch.setattr(llm_fallback := __import__("llm_fallback"), "is_enabled", lambda _flag: True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class Completions:
        def create(self, **_kwargs):
            return types.SimpleNamespace(
                id="openai-fallback-request",
                usage=types.SimpleNamespace(prompt_tokens=2, completion_tokens=1),
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='{"is_conflict":false}'))],
            )

    class OpenAI:
        def __init__(self, **_kwargs):
            self.chat = types.SimpleNamespace(completions=Completions())

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=OpenAI))
    events = []
    monkeypatch.setattr("core.usage_telemetry.record_llm_usage", lambda **kwargs: events.append(kwargs))
    capability = resolve_decision_conflict_detection_capability()
    operation = core.create_operation(capability)
    context = core.create_execution_context(capability, operation)

    result = dc.detect_conflict_ai(_event("fallback-a"), _event("fallback-b"), execution_context=context)

    assert result.is_conflict is False
    assert len(events) == 1
    assert events[0]["provider"] == "openai"
    assert events[0]["operation_id"] == context.operation.operation_id
    assert events[0]["capability_id"] == "business.decision_conflict_detection"


def test_structural_verifier_is_strict_and_pure():
    valid = {"is_conflict": False, "aspect": None, "severity": None}
    assert dc.verify_decision_conflict_payload(valid) is valid

    for invalid in (
        {**valid, "is_conflict": 1},
        {**valid, "aspect": 3},
        {**valid, "severity": "critical"},
    ):
        try:
            dc.verify_decision_conflict_payload(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid payload accepted: {invalid!r}")


def test_legacy_failure_and_no_hardcoded_attribution(monkeypatch):
    monkeypatch.setattr(
        "llm_fallback.call_anthropic_text",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider failed")),
    )

    result = dc.detect_conflict_ai(_event("failure-a"), _event("failure-b"))

    assert result.is_conflict is False
    source = inspect.getsource(dc.detect_conflict_ai)
    assert "business.decision_conflict_detection" not in source
    assert "NARROW_MODEL" not in source
    assert "operation_id" not in source
    assert "workflow_id" not in source
