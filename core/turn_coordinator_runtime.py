"""Small, dependency-injected runtime seam for canonical task proposals."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from airtable_schema import Tables, TaskFields
from core.router import (
    CanonicalActionProposal,
    ExecutionClass,
    Handler,
    Intent,
    IntentOwnershipDecision,
    IntentOwnershipRegistry,
    ResolvedCapability,
    ResolverResult,
    prepare_task_proposal,
    resolve_capability,
    RouteDecision,
)
from core.router.task_resolvers import TaskLookup
from core.query_contract import contains

TASK_OWNERSHIP = IntentOwnershipRegistry({
    Intent.CREATE_TASK: IntentOwnershipDecision(
        Intent.CREATE_TASK, "task_builder", "task intent", 1.0,
        proposal_policy_ref="task_builder", evidence_policy_ref="task_write",
        reply_policy_ref="gateway",
    ),
    Intent.UPDATE_TASK: IntentOwnershipDecision(
        Intent.UPDATE_TASK, "task_resolver", "entity-dependent task intent", 1.0,
        resolver_required=True, proposal_policy_ref="task_builder",
        evidence_policy_ref="task_write", reply_policy_ref="gateway",
    ),
    Intent.COMPLETE_TASK: IntentOwnershipDecision(
        Intent.COMPLETE_TASK, "task_resolver", "entity-dependent task intent", 1.0,
        resolver_required=True, proposal_policy_ref="task_builder",
        evidence_policy_ref="task_write", reply_policy_ref="gateway",
    ),
})


def resolve_agent_capability(route: RouteDecision) -> ResolvedCapability:
    """Adapt an authoritative Agent route to the canonical reasoning capability."""
    if not isinstance(route, RouteDecision):
        raise TypeError("route must be a RouteDecision")
    if (
        route.handler != Handler.AGENT
        or route.intent == Intent.ENGINEERING_NOTE
        or route.response_override
    ):
        raise ValueError("route is not an executable Agent decision")

    ownership = IntentOwnershipDecision(
        intent=route.intent,
        owner="agent.loop",
        reason="RouteDecision selected the Agent executor",
        confidence=route.confidence,
    )
    return resolve_capability(
        ownership,
        {
            route.intent: (
                ResolvedCapability(
                    capability_id="general.reasoning",
                    execution_class=ExecutionClass.FULL_AGENT,
                    executor_ref="agent.loop",
                ),
            ),
        },
    )


def gateway_call(proposal: CanonicalActionProposal) -> tuple[str, dict]:
    """Convert the frozen proposal to the existing dispatcher payload."""
    if proposal.canonical_tool == "task_create":
        return "airtable_add", {"table": proposal.resource, "fields": dict(proposal.fields)}
    if proposal.canonical_tool in {"task_update", "task_complete"}:
        fields = dict(proposal.fields)
        record_id = str(fields.pop("record_id", "") or "").strip()
        if not record_id:
            raise ValueError("task update requires a stable record_id")
        return "airtable_update", {
            "table": proposal.resource, "record_id": record_id, "fields": fields,
        }
    raise ValueError(f"unsupported task proposal tool: {proposal.canonical_tool}")


def prepare_task_gateway_call(
    intent: str,
    *,
    scope: str,
    lookup: TaskLookup | None = None,
    query: str = "",
    title: str = "",
    fields: Mapping[str, object] | None = None,
    limit: int = 5,
    identity=None,
) -> tuple[str, dict] | ResolverResult:
    result = prepare_task_proposal(
        intent, TASK_OWNERSHIP, scope=scope, lookup=lookup, query=query,
        title=title, fields=fields, limit=limit, identity=identity,
    )
    return gateway_call(result) if isinstance(result, CanonicalActionProposal) else result


def airtable_task_lookup(query: str, scope: str, limit: int):
    """Return at most resolver-limit+1 matching task records."""
    from tools.airtable_read_adapter import list_records

    return list_records(
        Tables.TASKS,
        contains(TaskFields.NAME, str(query)),
        limit=limit + 1,
        paginate=True,
    )


def queue_task_request(
    *,
    intent: str,
    scope: str,
    title: str = "",
    query: str = "",
    fields: Mapping[str, object] | None = None,
    queue: Callable[[str, dict], dict],
    identity=None,
) -> dict:
    """Prepare, fail closed on resolution, then use the existing queue."""
    try:
        result = prepare_task_gateway_call(
            intent, scope=scope, lookup=airtable_task_lookup,
            query=query, title=title, fields=fields, identity=identity,
        )
    except ValueError as exc:
        return {"message": str(exc), "created_this_turn": False}
    if isinstance(result, ResolverResult):
        message = "לא מצאתי משימה מתאימה." if result.match_count == 0 else "מצאתי כמה משימות מתאימות. נא לציין משימה אחת בלבד."
        return {"message": message, "created_this_turn": False, "resolver_result": result}
    tool, payload = result
    outcome = queue(tool, payload)
    return {
        **outcome,
        "message": outcome.get("message") or "לא הצלחתי להעביר את הפעולה לאישור.",
    }
