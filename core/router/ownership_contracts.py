"""Frozen WS1 contracts for ownership, proposals, and bounded resolution.

These types are additive. ``core/router/router.py`` itself does not import
this module: the live wiring runs through the separate
``core/turn_coordinator_runtime.py`` seam (``queue_task_request()``), called
from ``app.py``'s ``run_agent()`` for deterministic create/update/complete-task
routing. See ``docs/architecture/turn-coordinator/README.md`` for current
wiring status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class ExecutionClass(str, Enum):
    """Canonical executable route classes from SPEC_Agent_Last_Cost_Architecture."""

    DETERMINISTIC = "DETERMINISTIC"
    NARROW_MODEL = "NARROW_MODEL"
    FULL_AGENT = "FULL_AGENT"


class CapabilityResolutionError(ValueError):
    """A bounded capability could not be resolved safely."""


@dataclass(frozen=True)
class ResolvedCapability:
    """Immutable capability decision; references policies, never their contents."""

    capability_id: str
    execution_class: ExecutionClass
    capability_version: str = ""
    executor_ref: str = ""
    validator_ref: str = ""
    verification_ref: str = ""
    approval_risk_ref: str = ""
    fallback_ref: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            raise ValueError("capability_id is required")
        if not isinstance(self.execution_class, ExecutionClass):
            raise TypeError("execution_class must be an ExecutionClass")
        for name in (
            "capability_version", "executor_ref", "validator_ref",
            "verification_ref", "approval_risk_ref", "fallback_ref",
        ):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be a string")
        if not self.executor_ref.strip():
            raise ValueError("executor_ref is required")


def lookup_resolved_capability(
    capability_id: str,
    capabilities: Mapping[str, ResolvedCapability],
) -> ResolvedCapability:
    """Look up a known capability by id; this is not authority resolution."""
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise CapabilityResolutionError("capability_id is required")
    resolved = capabilities.get(capability_id)
    if resolved is None:
        raise CapabilityResolutionError(f"unknown capability: {capability_id}")
    if not isinstance(resolved, ResolvedCapability):
        raise TypeError("capability map values must be ResolvedCapability")
    if resolved.capability_id != capability_id:
        raise CapabilityResolutionError("capability map key does not match capability_id")
    return resolved


def resolve_capability(
    ownership: "IntentOwnershipDecision",
    candidates_by_intent: Mapping[str, tuple[ResolvedCapability, ...]],
) -> ResolvedCapability:
    """Resolve exactly one capability from an existing ownership decision."""
    if not isinstance(ownership, IntentOwnershipDecision):
        raise TypeError("ownership must be an IntentOwnershipDecision")
    candidates = candidates_by_intent.get(ownership.intent, ())
    if not isinstance(candidates, tuple) or not all(
        isinstance(candidate, ResolvedCapability) for candidate in candidates
    ):
        raise TypeError("capability candidates must be a tuple of ResolvedCapability")
    if len(candidates) != 1:
        raise CapabilityResolutionError(
            f"capability resolution requires exactly one match for intent: {ownership.intent}"
        )
    return candidates[0]


@dataclass(frozen=True)
class IntentOwnershipDecision:
    """One routing result: select an owner, never execute an action."""

    intent: str
    owner: str
    reason: str
    confidence: float
    resolver_required: bool = False
    proposal_policy_ref: str = ""
    evidence_policy_ref: str = ""
    reply_policy_ref: str = ""

    def __post_init__(self) -> None:
        if not self.intent or not self.owner or not self.reason:
            raise ValueError("intent, owner, and reason are required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class CanonicalActionProposal:
    """A named, validated mutation proposal; it does not execute anything."""

    intent: str
    canonical_tool: str
    resource: str
    fields: Mapping[str, object] = field(default_factory=dict)
    risk: str = "normal"
    approval_required: bool = False
    evidence_requirement: str = ""
    reply_policy: str = ""

    def __post_init__(self) -> None:
        if not self.intent or not self.canonical_tool or not self.resource:
            raise ValueError("intent, canonical_tool, and resource are required")
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


@dataclass(frozen=True)
class ResolverResult:
    """A bounded entity lookup result with no silent fallback."""

    entity_kind: str
    scope: str
    match_count: int
    stable_reference: str = ""
    source: str = ""
    version: str = ""
    freshness: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if not self.entity_kind or not self.scope:
            raise ValueError("entity_kind and scope are required")
        if self.match_count < 0:
            raise ValueError("match_count cannot be negative")
        if self.match_count != 1 and self.stable_reference:
            raise ValueError("stable_reference requires exactly one match")


@dataclass(frozen=True)
class ActionLifecycleResult:
    """Frozen WS2 lifecycle projection for an approval contract."""

    contract_ref: str
    lifecycle_state: str
    approval_state: str
    execution_state: str
    reply_owner: str = "gateway"
    error_replay_classification: str = ""

    def __post_init__(self) -> None:
        for attr_name in ("contract_ref", "lifecycle_state", "approval_state", "execution_state", "reply_owner"):
            value = getattr(self, attr_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{attr_name} is required")
        for attr_name in ("error_replay_classification",):
            value = getattr(self, attr_name)
            if not isinstance(value, str):
                raise ValueError(f"{attr_name} must be a string")


@dataclass(frozen=True)
class EvidenceResult:
    """Frozen WS2 evidence projection for a completed or failed execution."""

    result: str
    evidence_ref: str = ""
    provider_result: str = ""
    verified: bool = False
    outcome_unknown: bool = False
    error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.result, str) or not self.result.strip():
            raise ValueError("result is required")
        for attr_name in ("evidence_ref", "provider_result", "error"):
            value = getattr(self, attr_name)
            if not isinstance(value, str):
                raise ValueError(f"{attr_name} must be a string")


@dataclass(frozen=True)
class IntentOwnershipRegistry:
    """Immutable intent-to-owner registry; duplicate intents are impossible."""

    decisions: Mapping[str, IntentOwnershipDecision] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = dict(self.decisions)
        for intent, decision in normalized.items():
            if intent != decision.intent:
                raise ValueError("registry key must match decision.intent")
        object.__setattr__(self, "decisions", MappingProxyType(normalized))

    def for_intent(self, intent: str) -> IntentOwnershipDecision | None:
        return self.decisions.get(intent)

    def require(self, intent: str) -> IntentOwnershipDecision:
        decision = self.for_intent(intent)
        if decision is None:
            raise KeyError(f"no ownership decision for intent: {intent}")
        return decision

    def with_decision(self, decision: IntentOwnershipDecision) -> "IntentOwnershipRegistry":
        updated = dict(self.decisions)
        updated[decision.intent] = decision
        return IntentOwnershipRegistry(updated)
