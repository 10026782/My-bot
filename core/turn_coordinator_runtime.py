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


def resolve_tma_contextual_answer_capability() -> ResolvedCapability:
    """Resolve the fixed authenticated TMA contextual-answer contract."""
    ownership = IntentOwnershipDecision(
        intent=Intent.ASK_QUESTION,
        owner="tma.contextual_answer",
        reason="authenticated /api/ai/ask endpoint contract",
        confidence=1.0,
    )
    return resolve_capability(
        ownership,
        {
            Intent.ASK_QUESTION: (
                ResolvedCapability(
                    capability_id="general.contextual_answer",
                    execution_class=ExecutionClass.NARROW_MODEL,
                    executor_ref="tma.contextual_answer",
                    validator_ref="tma.ask.request.v1",
                    verification_ref="tma.answer.non_empty.v1",
                    fallback_ref="llm_fallback",
                ),
            ),
        },
    )


def resolve_marketing_creative_drafting_capability() -> ResolvedCapability:
    """Resolve the validated /marketing_new creative-drafting contract."""
    ownership = IntentOwnershipDecision(
        intent=Intent.DRAFT_MARKETING_CREATIVES,
        owner="marketing.creative_drafting",
        reason="validated /marketing_new creative drafting contract",
        confidence=1.0,
    )
    return resolve_capability(
        ownership,
        {
            Intent.DRAFT_MARKETING_CREATIVES: (
                ResolvedCapability(
                    capability_id="marketing.creative_idea_drafting",
                    execution_class=ExecutionClass.NARROW_MODEL,
                    executor_ref="cmd_marketing._create_demand_and_generate_ideas",
                    validator_ref="cmd_marketing.capture_text.constraints",
                    verification_ref="cmd_marketing._parse_and_render_creative_proposals",
                    fallback_ref="llm_fallback",
                ),
            ),
        },
    )


def resolve_daily_persistence_gap_capability() -> ResolvedCapability:
    """Resolve the fixed eligible daily persistence-gap analysis contract."""
    ownership = IntentOwnershipDecision(
        intent=Intent.DETECT_DAILY_PERSISTENCE_GAPS,
        owner="daily_collector.analysis",
        reason="eligible fixed daily persistence-gap analysis contract",
        confidence=1.0,
    )
    return resolve_capability(
        ownership,
        {
            Intent.DETECT_DAILY_PERSISTENCE_GAPS: (
                ResolvedCapability(
                    capability_id="business.daily_persistence_gap_detection",
                    execution_class=ExecutionClass.NARROW_MODEL,
                    executor_ref="daily_collector.analysis",
                    validator_ref="daily_collector.history_eligibility.v1",
                    verification_ref="daily_collector.result_schema.v1",
                    fallback_ref="llm_fallback",
                ),
            ),
        },
    )


def resolve_business_interaction_analysis_capability() -> ResolvedCapability:
    """Resolve the fixed eligible business-interaction analysis contract."""
    ownership = IntentOwnershipDecision(
        intent=Intent.ANALYZE_BUSINESS_INTERACTION,
        owner="interaction_engine.analysis",
        reason="eligible fixed business interaction analysis contract",
        confidence=1.0,
    )
    return resolve_capability(
        ownership,
        {
            Intent.ANALYZE_BUSINESS_INTERACTION: (
                ResolvedCapability(
                    capability_id="business.interaction_analysis",
                    execution_class=ExecutionClass.NARROW_MODEL,
                    executor_ref="interaction_engine.analysis",
                    validator_ref="interaction_engine.eligibility.v1",
                    verification_ref="interaction_engine.analysis_schema.v1",
                    fallback_ref="interaction_engine._rule_based_analysis",
                ),
            ),
        },
    )


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
