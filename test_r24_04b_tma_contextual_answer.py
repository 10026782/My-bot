from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from flask import Flask

import core
import context as context_module
import llm_fallback
import memory_store
import tma_api
from core import create_execution_context, create_operation
from core.router.ownership_contracts import ExecutionClass
from core.turn_coordinator_runtime import resolve_tma_contextual_answer_capability
from identity import Role
from tma_api import verify_tma_contextual_answer


def test_tma_contextual_answer_uses_one_narrow_model_capability():
    resolved = resolve_tma_contextual_answer_capability()
    operation = create_operation(resolved)
    context = create_execution_context(resolved, operation)

    assert resolved.capability_id == "general.contextual_answer"
    assert resolved.execution_class is ExecutionClass.NARROW_MODEL
    assert resolved.executor_ref == "tma.contextual_answer"
    assert context.operation is operation


def test_all_context_variants_share_the_same_fixed_capability():
    app = Flask(__name__)
    identity = SimpleNamespace(role=Role.OWNER, is_owner=True, memory_key="tma-test")
    fake_context = SimpleNamespace(
        model="test-model",
        max_tokens=100,
        system_prompt="test-system",
        memory_key="tma-test",
    )
    operations = []
    contexts = []
    calls = []

    real_create_operation = core.create_operation
    real_create_execution_context = core.create_execution_context

    def create_operation_spy(resolved):
        operation = real_create_operation(resolved)
        operations.append(operation)
        return operation

    def create_context_spy(resolved, operation, **kwargs):
        execution_context = real_create_execution_context(resolved, operation, **kwargs)
        contexts.append(execution_context)
        return execution_context

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(core, "create_operation", create_operation_spy)
        monkeypatch.setattr(core, "create_execution_context", create_context_spy)
        monkeypatch.setattr(context_module, "build_context", lambda *_args: fake_context)
        monkeypatch.setattr(memory_store.memory, "get_for_claude", lambda *_args: [])
        monkeypatch.setattr(
            tma_api,
            "_at_get_record",
            lambda *_args: {"fields": {"Name": "Lead", "phone": "1", "status": "new", "Score": 1, "summary": "summary"}},
        )
        monkeypatch.setattr(
            tma_api,
            "_get_global_kpis",
            lambda: {
                "income_this_month": 0,
                "pending_payments_count": 0,
                "overdue_tasks": 0,
                "hot_leads_count": 0,
            },
        )

        def fake_call(**kwargs):
            calls.append(kwargs)
            return "answer"

        monkeypatch.setattr(llm_fallback, "call_anthropic_text", fake_call)

        for context_type in ("general", "lead_card", "projects_hub"):
            payload = {"question": "What is next?", "context": context_type}
            if context_type == "lead_card":
                payload["context_id"] = "lead-1"

            with app.test_request_context("/api/ai/ask", method="POST", json=payload):
                response = tma_api.ask_ai.__wrapped__(identity=identity)

            response = response[0] if isinstance(response, tuple) else response
            assert response.get_json() == {"answer": "answer", "context": context_type}

        assert len(operations) == len(contexts) == len(calls) == 3
        assert len({operation.operation_id for operation in operations}) == 3
        assert all(
            context.resolved_capability.capability_id == "general.contextual_answer"
            and context.resolved_capability.execution_class is ExecutionClass.NARROW_MODEL
            for context in contexts
        )
        assert all(
            call["execution_context"] is context
            for call, context in zip(calls, contexts)
        )
    finally:
        monkeypatch.undo()


def test_tma_fallback_preserves_context_for_existing_telemetry_translation(monkeypatch):
    class ProviderTimeout(Exception):
        pass

    class FakeAnthropic:
        def __init__(self, **_kwargs):
            self.messages = SimpleNamespace(
                create=lambda **_kwargs: (_ for _ in ()).throw(ProviderTimeout("timeout"))
            )

    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **_kwargs):
            return SimpleNamespace(
                id="tma-fallback-request",
                usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
                choices=[SimpleNamespace(message=SimpleNamespace(content="fallback answer"))],
            )

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=FakeAnthropic))
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_fallback, "_fallback_enabled", lambda: True)
    events = []
    monkeypatch.setattr(
        "core.usage_telemetry.record_llm_usage",
        lambda **kwargs: events.append(kwargs),
    )

    resolved = resolve_tma_contextual_answer_capability()
    operation = create_operation(resolved)
    execution_context = create_execution_context(resolved, operation)

    assert llm_fallback.call_anthropic_text(
        source="tma_api.ask_ai",
        model="test-model",
        max_tokens=100,
        messages=[{"role": "user", "content": "question"}],
        execution_context=execution_context,
    ) == "fallback answer"

    assert len(events) == 1
    assert events[0]["capability_id"] == "general.contextual_answer"
    assert events[0]["execution_class"] == "NARROW_MODEL"
    assert events[0]["operation_id"] == operation.operation_id
    assert "capability_id  =" not in Path("llm_fallback.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("answer", ["answer", "  answer  ", "תשובה תקינה"])
def test_tma_answer_verifier_accepts_non_empty_strings(answer):
    assert verify_tma_contextual_answer(answer) == answer


@pytest.mark.parametrize("answer", ["", "   ", None, 42])
def test_tma_answer_verifier_rejects_structurally_invalid_output(answer):
    with pytest.raises(ValueError):
        verify_tma_contextual_answer(answer)


def test_tma_wiring_reuses_context_and_does_not_enter_agent_loop():
    source = Path("tma_api.py").read_text(encoding="utf-8")

    assert "execution_context=execution_context" in source
    assert "run_agent(" not in source
    assert 'general.reasoning' not in source
    assert "workflow_id" not in source
    assert "workflow_run_id" not in source
