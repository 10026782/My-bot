"""Narrow WS1 seam from ownership decisions to task proposals."""

from __future__ import annotations

from collections.abc import Mapping

from core.router.ownership_contracts import (
    CanonicalActionProposal,
    IntentOwnershipRegistry,
    ResolverResult,
)
from core.router.route_decision import Intent
from core.router.task_builders import (
    build_complete_task_proposal,
    build_create_task_proposal,
    build_update_task_proposal,
)
from core.router.task_resolvers import TaskLookup, resolve_task

TaskIntegrationResult = CanonicalActionProposal | ResolverResult


def prepare_task_proposal(
    intent: str,
    registry: IntentOwnershipRegistry,
    *,
    scope: str,
    lookup: TaskLookup | None = None,
    query: str = "",
    title: str = "",
    fields: Mapping[str, object] | None = None,
    limit: int = 5,
) -> TaskIntegrationResult:
    """Select the registered owner, resolve when required, then build.

    This returns a ResolverResult for zero/multiple matches instead of picking
    a task. It creates no ActionContract and performs no execution.
    """
    decision = registry.require(intent)
    needs_resolution = intent in {Intent.UPDATE_TASK, Intent.COMPLETE_TASK}
    if decision.resolver_required != needs_resolution:
        raise ValueError(f"resolver policy mismatch for intent: {intent}")

    if intent == Intent.CREATE_TASK:
        return build_create_task_proposal(title, **dict(fields or {}))
    if intent not in {Intent.UPDATE_TASK, Intent.COMPLETE_TASK}:
        raise ValueError(f"unsupported task integration intent: {intent}")
    if lookup is None:
        raise ValueError(f"lookup is required for intent: {intent}")

    result = resolve_task(query, lookup, scope=scope, limit=limit)
    if result.match_count != 1 or not result.stable_reference:
        return result
    if intent == Intent.COMPLETE_TASK:
        return build_complete_task_proposal(result.stable_reference)
    return build_update_task_proposal(result.stable_reference, **dict(fields or {}))
