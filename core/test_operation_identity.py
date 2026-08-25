import pytest

from core import OperationIdentity, create_operation
from core.router.ownership_contracts import ExecutionClass, ResolvedCapability


def _capability(executor_ref="agent.loop"):
    return ResolvedCapability(
        "general.reasoning",
        ExecutionClass.FULL_AGENT,
        executor_ref=executor_ref,
    )


def test_factory_requires_resolved_capability_and_preserves_identity():
    operation = create_operation(_capability())

    assert operation.capability_id == "general.reasoning"
    assert operation.execution_class is ExecutionClass.FULL_AGENT
    assert operation.operation_id

    with pytest.raises(TypeError):
        create_operation("general.reasoning")


def test_each_business_operation_gets_a_distinct_opaque_id():
    first = create_operation(_capability())
    second = create_operation(_capability())

    assert first.operation_id != second.operation_id
    assert set(first.__dataclass_fields__) == {
        "operation_id", "capability_id", "execution_class",
    }


def test_provider_executor_does_not_change_operation_identity_contract():
    first = create_operation(_capability("provider_a.executor"))
    second = create_operation(_capability("provider_b.executor"))

    assert first.capability_id == second.capability_id
    assert first.execution_class is second.execution_class
    assert first.operation_id != second.operation_id


def test_operation_identity_is_immutable_and_validated():
    operation = create_operation(_capability())

    with pytest.raises((AttributeError, TypeError)):
        operation.operation_id = "replacement"
    with pytest.raises(ValueError):
        OperationIdentity("", "general.reasoning", ExecutionClass.FULL_AGENT)
    with pytest.raises(TypeError):
        OperationIdentity("op-1", "general.reasoning", "FULL_AGENT")
