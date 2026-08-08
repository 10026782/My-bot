"""Narrow WS1 seam from ownership decisions to lead proposals (TC4).

Mirrors ``core/router/task_integration.py``'s TC3 pattern exactly, using
TC5's ``resolve_lead`` for the bounded, identity-scoped lookup instead of a
second resolver implementation.
"""

from __future__ import annotations

from collections.abc import Mapping

from core.router.entity_resolvers import LeadLookup, resolve_lead
from core.router.lead_builders import build_create_lead_proposal, build_update_lead_proposal
from core.router.ownership_contracts import (
    CanonicalActionProposal,
    IntentOwnershipRegistry,
    ResolverResult,
)
from core.router.route_decision import Intent

LeadIntegrationResult = CanonicalActionProposal | ResolverResult


def prepare_lead_proposal(
    intent: str,
    registry: IntentOwnershipRegistry,
    *,
    scope: str,
    lookup: LeadLookup | None = None,
    query: str = "",
    name: str = "",
    fields: Mapping[str, object] | None = None,
    limit: int = 5,
) -> LeadIntegrationResult:
    """Select the registered owner, resolve when required, then build.

    This returns a ResolverResult for zero/multiple matches instead of
    picking a lead. It creates no ActionContract and performs no execution.
    """
    decision = registry.require(intent)
    needs_resolution = intent == Intent.UPDATE_LEAD
    if decision.resolver_required != needs_resolution:
        raise ValueError(f"resolver policy mismatch for intent: {intent}")

    if intent == Intent.CREATE_LEAD:
        return build_create_lead_proposal(name, **dict(fields or {}))
    if intent != Intent.UPDATE_LEAD:
        raise ValueError(f"unsupported lead integration intent: {intent}")
    if lookup is None:
        raise ValueError(f"lookup is required for intent: {intent}")

    result = resolve_lead(query, lookup, scope=scope, limit=limit)
    if result.match_count != 1 or not result.stable_reference:
        return result
    return build_update_lead_proposal(result.stable_reference, **dict(fields or {}))
