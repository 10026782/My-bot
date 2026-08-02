"""Small, dependency-injected runtime seam for canonical task proposals."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from airtable_schema import Tables, TaskFields
from core.router import (
    CanonicalActionProposal,
    Intent,
    IntentOwnershipDecision,
    IntentOwnershipRegistry,
    ResolverResult,
    prepare_task_proposal,
)
from core.router.task_resolvers import TaskLookup

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
) -> tuple[str, dict] | ResolverResult:
    result = prepare_task_proposal(
        intent, TASK_OWNERSHIP, scope=scope, lookup=lookup, query=query,
        title=title, fields=fields, limit=limit,
    )
    return gateway_call(result) if isinstance(result, CanonicalActionProposal) else result


def airtable_task_lookup(query: str, scope: str, limit: int):
    """Return at most resolver-limit+1 matching task records."""
    from tools.airtable_gateway import _safe_formula_param
    from tools.airtable_tools import airtable_get_records

    escaped = _safe_formula_param(str(query).replace("\\", "\\\\"))
    formula = f"SEARCH('{escaped}', {{{TaskFields.NAME}}})"
    return airtable_get_records(Tables.TASKS, formula, max_records=limit + 1)


def queue_task_request(
    *,
    intent: str,
    scope: str,
    title: str = "",
    query: str = "",
    fields: Mapping[str, object] | None = None,
    queue: Callable[[str, dict], dict],
) -> dict:
    """Prepare, fail closed on resolution, then use the existing queue."""
    try:
        result = prepare_task_gateway_call(
            intent, scope=scope, lookup=airtable_task_lookup,
            query=query, title=title, fields=fields,
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
