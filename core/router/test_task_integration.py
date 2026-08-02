from core.router.ownership_contracts import IntentOwnershipDecision, IntentOwnershipRegistry
from core.router.route_decision import Intent
from core.router.task_integration import prepare_task_proposal
from airtable_schema import TaskFields


def _registry():
    return IntentOwnershipRegistry({
        Intent.CREATE_TASK: IntentOwnershipDecision(
            Intent.CREATE_TASK, "TASK_BUILDER", "structured create", 1.0,
        ),
        Intent.UPDATE_TASK: IntentOwnershipDecision(
            Intent.UPDATE_TASK, "RESOLVER", "entity update", 1.0, True,
        ),
        Intent.COMPLETE_TASK: IntentOwnershipDecision(
            Intent.COMPLETE_TASK, "RESOLVER", "entity completion", 1.0, True,
        ),
    })


def test_integration_builds_create_without_lookup():
    proposal = prepare_task_proposal(
        Intent.CREATE_TASK, _registry(), scope="tenant:u1", title="Call supplier"
    )
    assert proposal.intent == Intent.CREATE_TASK
    assert proposal.fields[TaskFields.NAME] == "Call supplier"


def test_integration_resolves_then_builds_update():
    proposal = prepare_task_proposal(
        Intent.UPDATE_TASK, _registry(), scope="tenant:u1", query="Call supplier",
        fields={TaskFields.DESCRIPTION: "Today"},
        lookup=lambda query, scope, limit: [{"id": "rec1"}],
    )
    assert proposal.intent == Intent.UPDATE_TASK
    assert proposal.fields["record_id"] == "rec1"


def test_integration_returns_resolver_result_for_ambiguous_update():
    result = prepare_task_proposal(
        Intent.UPDATE_TASK, _registry(), scope="tenant:u1", query="Call",
        lookup=lambda query, scope, limit: [{"id": "rec1"}, {"id": "rec2"}],
    )
    assert result.match_count == 2
    assert result.stable_reference == ""


def test_integration_rejects_registry_policy_mismatch():
    registry = IntentOwnershipRegistry({
        Intent.CREATE_TASK: IntentOwnershipDecision(
            Intent.CREATE_TASK, "TASK_BUILDER", "bad resolver policy", 1.0, True,
        ),
    })
    try:
        prepare_task_proposal(Intent.CREATE_TASK, registry, scope="tenant:u1", title="x")
    except ValueError as error:
        assert "resolver policy mismatch" in str(error)
    else:
        raise AssertionError("policy mismatch was accepted")
