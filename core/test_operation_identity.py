import pytest

from core import ExecutionContext, OperationIdentity, create_execution_context, create_operation
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


def test_execution_context_requires_matching_immutable_authority():
    capability = _capability()
    operation = create_operation(capability)
    context = create_execution_context(capability, operation)

    assert context.resolved_capability is capability
    assert context.operation is operation
    assert set(context.__dataclass_fields__) == {
        "resolved_capability", "operation", "contract_id", "turn_id", "parent_operation_id",
    }
    with pytest.raises((AttributeError, TypeError)):
        context.operation = operation

    with pytest.raises(TypeError):
        create_execution_context("not-a-capability", operation)
    with pytest.raises(TypeError):
        create_execution_context(capability, "not-an-operation")


def test_execution_context_rejects_capability_and_class_mismatch():
    capability = _capability()
    other_capability = ResolvedCapability(
        "task.create", ExecutionClass.DETERMINISTIC, executor_ref="task.executor",
    )
    operation = create_operation(capability)

    with pytest.raises(ValueError, match="capability_id"):
        create_execution_context(other_capability, operation)

    mismatched_operation = OperationIdentity(
        operation.operation_id, capability.capability_id, ExecutionClass.NARROW_MODEL,
    )
    with pytest.raises(ValueError, match="execution_class"):
        create_execution_context(capability, mismatched_operation)


@pytest.mark.parametrize("field", ["contract_id", "turn_id", "parent_operation_id"])
def test_execution_context_accepts_optional_non_empty_correlations(field):
    capability = _capability()
    operation = create_operation(capability)

    context = create_execution_context(capability, operation, **{field: "ref-1"})

    assert getattr(context, field) == "ref-1"


@pytest.mark.parametrize("field", ["contract_id", "turn_id", "parent_operation_id"])
@pytest.mark.parametrize("value", ["", "   ", 123])
def test_execution_context_rejects_invalid_optional_correlations(field, value):
    capability = _capability()
    operation = create_operation(capability)

    with pytest.raises((TypeError, ValueError)):
        create_execution_context(capability, operation, **{field: value})


def test_execution_context_rejects_self_parent_and_never_creates_operation():
    capability = _capability()
    operation = create_operation(capability)

    with pytest.raises(ValueError, match="parent_operation_id"):
        create_execution_context(
            capability, operation, parent_operation_id=operation.operation_id,
        )

    context = create_execution_context(capability, operation, contract_id=None, turn_id=None)
    assert context.operation is operation
