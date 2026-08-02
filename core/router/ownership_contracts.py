"""Frozen WS1 contracts for ownership, proposals, and bounded resolution.

These types are additive.  They are deliberately not wired into the live
router until the TC1 integration seam is reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


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
