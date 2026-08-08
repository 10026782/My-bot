"""Narrow WS1 seam from ownership decisions to lead proposals (TC4).

Mirrors ``core/router/task_integration.py``'s TC3 pattern exactly, using
TC5's ``resolve_lead`` for the bounded, identity-scoped lookup instead of a
second resolver implementation.
"""

from __future__ import annotations

from collections.abc import Mapping

from core.router.entity_resolvers import LeadLookup, resolve_lead
from core.router.lead_builders import (
    LeadIdentityPrecondition,
    build_create_lead_proposal,
    build_update_lead_proposal,
)
from core.router.ownership_contracts import (
    CanonicalActionProposal,
    IntentOwnershipRegistry,
    ResolverResult,
)
from core.router.route_decision import Intent

LeadIntegrationResult = CanonicalActionProposal | ResolverResult

# The WS1 ownership contract requires every owned intent to have one target
# owner (IntentOwnershipDecision.owner is the typed owner-selection result).
# resolver_required alone does not prove the registered owner is the right
# one for this intent -- a registry entry could have the correct
# resolver_required value with the wrong owner string. These constants are
# validated in addition to, not instead of, the existing resolver_required
# check below.
_LEAD_BUILDER_OWNER = "LEAD_BUILDER"
_LEAD_RESOLVER_OWNER = "RESOLVER"


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
    capture_policy: str | None = None,
    identity_precondition: LeadIdentityPrecondition | None = None,
) -> LeadIntegrationResult:
    """Select the registered owner, resolve when required, then build.

    This returns a ResolverResult for zero/multiple matches instead of
    picking a lead. It creates no ActionContract and performs no execution.
    ``capture_policy``/``identity_precondition`` are required for
    ``create_lead`` and threaded straight through to
    ``build_create_lead_proposal`` -- this seam does not decide or default
    either of them itself. Fails closed, before any proposal construction or
    lookup, when the registered decision's ``owner`` does not match the
    expected owner for this intent.
    """
    decision = registry.require(intent)
    needs_resolution = intent == Intent.UPDATE_LEAD
    if decision.resolver_required != needs_resolution:
        raise ValueError(f"resolver policy mismatch for intent: {intent}")

    if intent == Intent.CREATE_LEAD:
        if decision.owner != _LEAD_BUILDER_OWNER:
            raise ValueError(f"owner mismatch for intent: {intent}")
        if capture_policy is None:
            raise ValueError("capture_policy is required for intent: create_lead")
        if identity_precondition is None:
            raise ValueError("identity_precondition is required for intent: create_lead")
        return build_create_lead_proposal(
            name, scope=scope, capture_policy=capture_policy,
            identity_precondition=identity_precondition, **dict(fields or {}),
        )
    if intent != Intent.UPDATE_LEAD:
        raise ValueError(f"unsupported lead integration intent: {intent}")
    if decision.owner != _LEAD_RESOLVER_OWNER:
        raise ValueError(f"owner mismatch for intent: {intent}")
    if lookup is None:
        raise ValueError(f"lookup is required for intent: {intent}")

    result = resolve_lead(query, lookup, scope=scope, limit=limit)
    if result.match_count != 1 or not result.stable_reference:
        return result
    return build_update_lead_proposal(result.stable_reference, **dict(fields or {}))
