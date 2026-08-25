"""Canonical operation identity contract and creation boundary."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from core.router.ownership_contracts import ExecutionClass, ResolvedCapability


@dataclass(frozen=True)
class OperationIdentity:
    """Immutable identity for one logical business/execution operation."""

    operation_id: str
    capability_id: str
    execution_class: ExecutionClass

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id.strip():
            raise ValueError("operation_id is required")
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            raise ValueError("capability_id is required")
        if not isinstance(self.execution_class, ExecutionClass):
            raise TypeError("execution_class must be an ExecutionClass")


def _validate_optional_correlation(name: str, value: str | None) -> None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{name} cannot be empty")


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable authority carrier for one execution and its correlations."""

    resolved_capability: ResolvedCapability
    operation: OperationIdentity
    contract_id: str | None = None
    turn_id: str | None = None
    parent_operation_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resolved_capability, ResolvedCapability):
            raise TypeError("resolved_capability must be a ResolvedCapability")
        if not isinstance(self.operation, OperationIdentity):
            raise TypeError("operation must be an OperationIdentity")
        if self.resolved_capability.capability_id != self.operation.capability_id:
            raise ValueError("capability_id does not match operation identity")
        if self.resolved_capability.execution_class is not self.operation.execution_class:
            raise ValueError("execution_class does not match operation identity")
        for name in ("contract_id", "turn_id", "parent_operation_id"):
            _validate_optional_correlation(name, getattr(self, name))
        if self.parent_operation_id == self.operation.operation_id:
            raise ValueError("parent_operation_id cannot equal operation_id")


def create_operation(resolved_capability: ResolvedCapability) -> OperationIdentity:
    """Create identity only; capability resolution and execution are external."""
    if not isinstance(resolved_capability, ResolvedCapability):
        raise TypeError("resolved_capability must be a ResolvedCapability")
    return OperationIdentity(
        operation_id=uuid.uuid4().hex,
        capability_id=resolved_capability.capability_id,
        execution_class=resolved_capability.execution_class,
    )


def create_execution_context(
    resolved_capability: ResolvedCapability,
    operation: OperationIdentity,
    *,
    contract_id: str | None = None,
    turn_id: str | None = None,
    parent_operation_id: str | None = None,
) -> ExecutionContext:
    """Bind existing authority objects without resolving or creating identity."""
    return ExecutionContext(
        resolved_capability=resolved_capability,
        operation=operation,
        contract_id=contract_id,
        turn_id=turn_id,
        parent_operation_id=parent_operation_id,
    )
