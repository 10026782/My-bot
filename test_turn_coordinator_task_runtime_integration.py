from airtable_schema import TaskFields
from core.router import Intent
from core.router.ownership_contracts import ResolverResult
from core.turn_coordinator_runtime import (
    gateway_call,
    prepare_task_gateway_call,
    queue_task_request,
)


def lookup(query, scope, limit):
    assert scope == "tenant:user"
    return [{"id": "rec-task"}][:limit]


def test_create_uses_one_gateway_queue_without_agent_or_write():
    queued = []
    reply = queue_task_request(
        intent=Intent.CREATE_TASK, scope="tenant:user", title="Call supplier",
        queue=lambda tool, payload: queued.append((tool, payload)) or {"message": "pending"},
    )
    assert reply == "pending"
    assert queued == [("airtable_add", {"table": "משימות (Tasks)", "fields": {TaskFields.NAME: "Call supplier"}})]


def test_update_and_complete_require_one_stable_match():
    update = prepare_task_gateway_call(
        Intent.UPDATE_TASK, scope="tenant:user", lookup=lookup,
        query="supplier", fields={TaskFields.DESCRIPTION: "today"},
    )
    complete = prepare_task_gateway_call(
        Intent.COMPLETE_TASK, scope="tenant:user", lookup=lookup, query="supplier",
    )
    assert update == (
        "airtable_update", {"table": "משימות (Tasks)", "record_id": "rec-task", "fields": {TaskFields.DESCRIPTION: "today"}}
    )
    assert complete[1]["record_id"] == "rec-task"


def test_ambiguous_lookup_fails_closed():
    result = prepare_task_gateway_call(
        Intent.UPDATE_TASK, scope="tenant:user",
        lookup=lambda *_: [{"id": "a"}, {"id": "b"}],
        query="same", fields={TaskFields.DESCRIPTION: "today"},
    )
    assert isinstance(result, ResolverResult)
    assert result.match_count == 2
