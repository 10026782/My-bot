import pytest

from core import create_execution_context, create_operation
from core.router import Handler, Intent, RouteDecision
from core.router.ownership_contracts import ExecutionClass
from core.turn_coordinator_runtime import resolve_agent_capability


def _route(**changes):
    values = {
        "handler": Handler.AGENT,
        "intent": Intent.ASK_QUESTION,
        "confidence": 1.0,
    }
    values.update(changes)
    return RouteDecision(**values)


def test_agent_route_resolves_canonical_reasoning_capability():
    resolved = resolve_agent_capability(_route())

    assert resolved.capability_id == "general.reasoning"
    assert resolved.execution_class is ExecutionClass.FULL_AGENT
    assert resolved.executor_ref == "agent.loop"


def test_one_reasoning_context_binds_one_operation_without_fallback_recreation():
    resolved = resolve_agent_capability(_route())
    operation = create_operation(resolved)
    context = create_execution_context(resolved, operation)

    assert context.operation is operation
    assert context.resolved_capability is resolved
    assert context.operation.operation_id


@pytest.mark.parametrize(
    "changes",
    [
        {"handler": Handler.TOOL},
        {"handler": Handler.CLARIFY},
        {"handler": "unknown"},
        {"intent": Intent.ENGINEERING_NOTE},
        {"response_override": "terminal"},
    ],
)
def test_non_executable_or_terminal_route_fails_closed(changes):
    with pytest.raises((TypeError, ValueError)):
        resolve_agent_capability(_route(**changes))


def test_fallback_context_parameter_is_optional_and_additive():
    from inspect import signature
    from llm_fallback import call_anthropic_text, call_openai_text

    for function in (call_anthropic_text, call_openai_text):
        parameter = signature(function).parameters["execution_context"]
        assert parameter.default is None
