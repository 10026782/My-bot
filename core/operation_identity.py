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


def create_operation(resolved_capability: ResolvedCapability) -> OperationIdentity:
    """Create identity only; capability resolution and execution are external."""
    if not isinstance(resolved_capability, ResolvedCapability):
        raise TypeError("resolved_capability must be a ResolvedCapability")
    return OperationIdentity(
        operation_id=uuid.uuid4().hex,
        capability_id=resolved_capability.capability_id,
        execution_class=resolved_capability.execution_class,
    )
