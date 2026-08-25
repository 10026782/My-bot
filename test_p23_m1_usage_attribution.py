import sys
from pathlib import Path
from types import SimpleNamespace

from core import create_execution_context, create_operation
from core.router.ownership_contracts import ExecutionClass, ResolvedCapability
from core.usage_telemetry import usage_attribution_from_context


def _context():
    capability = ResolvedCapability(
        "general.reasoning",
        ExecutionClass.FULL_AGENT,
        executor_ref="agent.loop",
    )
    operation = create_operation(capability)
    return create_execution_context(capability, operation)


def test_context_translation_uses_all_canonical_fields_without_creating_identity():
    context = _context()

    assert usage_attribution_from_context(context) == {
        "capability_id": "general.reasoning",
        "execution_class": "FULL_AGENT",
        "operation_id": context.operation.operation_id,
    }
    assert usage_attribution_from_context(None) == {}
    assert "create_operation" not in Path("core/usage_telemetry.py").read_text()
    assert "create_execution_context" not in Path("core/usage_telemetry.py").read_text()


def test_openai_attempts_keep_context_attribution_and_remain_separate(monkeypatch):
    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=self)
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            return SimpleNamespace(
                id=f"req-{self.calls}",
                usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    events = []
    monkeypatch.setattr(
        "core.usage_telemetry.record_llm_usage",
        lambda **kwargs: events.append(kwargs),
    )

    from llm_fallback import call_openai_text

    context = _context()
    for request in ("primary", "fallback"):
        assert call_openai_text(
            source=f"run_agent.{request}",
            messages=[{"role": "user", "content": "hello"}],
            execution_context=context,
        ) == "ok"

    assert len(events) == 2
    assert {event["operation_id"] for event in events} == {context.operation.operation_id}
    assert {event["capability_id"] for event in events} == {"general.reasoning"}
    assert {event["execution_class"] for event in events} == {"FULL_AGENT"}
    assert {event["request_id"] for event in events} == {"req-1"}


def test_legacy_openai_caller_keeps_legacy_attribution(monkeypatch):
    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **_kwargs):
            return SimpleNamespace(
                id="legacy-req",
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    events = []
    monkeypatch.setattr(
        "core.usage_telemetry.record_llm_usage",
        lambda **kwargs: events.append(kwargs),
    )

    from llm_fallback import call_openai_text

    call_openai_text(source="legacy.caller", messages=[{"role": "user", "content": "hello"}])

    assert "capability_id" not in events[0]
    assert "execution_class" not in events[0]
    assert "operation_id" not in events[0]


def test_run_agent_primary_uses_context_translation():
    source = Path("app.py").read_text()
    assert "usage_attribution_from_context(execution_context)" in source
    assert 'capability_id  = "general.reasoning"' not in source
    assert 'execution_class = "FULL_AGENT"' not in source
