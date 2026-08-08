from core.router.ownership_contracts import IntentOwnershipDecision, IntentOwnershipRegistry
from core.router.route_decision import Intent
from core.router.task_integration import prepare_task_proposal
from airtable_schema import TaskFields

# Owner strings match the live, wired TASK_OWNERSHIP registry
# (core/turn_coordinator_runtime.py) exactly -- this fixture previously used
# "TASK_BUILDER"/"RESOLVER" (uppercase, generic), which never matched
# production's "task_builder"/"task_resolver" and would have masked an owner
# mismatch bug instead of catching one.
_TASK_BUILDER_OWNER = "task_builder"
_TASK_RESOLVER_OWNER = "task_resolver"


def _registry():
    return IntentOwnershipRegistry({
        Intent.CREATE_TASK: IntentOwnershipDecision(
            Intent.CREATE_TASK, _TASK_BUILDER_OWNER, "structured create", 1.0,
        ),
        Intent.UPDATE_TASK: IntentOwnershipDecision(
            Intent.UPDATE_TASK, _TASK_RESOLVER_OWNER, "entity update", 1.0, True,
        ),
        Intent.COMPLETE_TASK: IntentOwnershipDecision(
            Intent.COMPLETE_TASK, _TASK_RESOLVER_OWNER, "entity completion", 1.0, True,
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
            Intent.CREATE_TASK, _TASK_BUILDER_OWNER, "bad resolver policy", 1.0, True,
        ),
    })
    try:
        prepare_task_proposal(Intent.CREATE_TASK, registry, scope="tenant:u1", title="x")
    except ValueError as error:
        assert "resolver policy mismatch" in str(error)
    else:
        raise AssertionError("policy mismatch was accepted")


# --- Hardening follow-up (post-PR #564): owner validation supplements resolver_required ---


def test_integration_create_rejects_wrong_owner_even_with_correct_resolver_required():
    """resolver_required=False matches CREATE_TASK's expected policy, but the
    registered owner is not task_builder -- this must still fail closed,
    before any proposal is constructed."""
    registry = IntentOwnershipRegistry({
        Intent.CREATE_TASK: IntentOwnershipDecision(
            Intent.CREATE_TASK, _TASK_RESOLVER_OWNER, "wrong owner for create", 1.0, False,
        ),
    })
    try:
        prepare_task_proposal(Intent.CREATE_TASK, registry, scope="tenant:u1", title="Call supplier")
    except ValueError as error:
        assert "owner mismatch" in str(error)
    else:
        raise AssertionError("wrong owner was accepted for create_task")


def test_integration_update_rejects_wrong_owner_before_lookup_runs():
    """resolver_required=True matches UPDATE_TASK's expected policy, but the
    registered owner is not task_resolver -- this must fail closed before the
    lookup callable is ever invoked."""
    registry = IntentOwnershipRegistry({
        Intent.UPDATE_TASK: IntentOwnershipDecision(
            Intent.UPDATE_TASK, _TASK_BUILDER_OWNER, "wrong owner for update", 1.0, True,
        ),
    })
    lookup_calls = []

    def tracking_lookup(query, scope, limit):
        lookup_calls.append((query, scope, limit))
        return [{"id": "rec1"}]

    try:
        prepare_task_proposal(
            Intent.UPDATE_TASK, registry, scope="tenant:u1", query="Call supplier",
            lookup=tracking_lookup,
        )
    except ValueError as error:
        assert "owner mismatch" in str(error)
    else:
        raise AssertionError("wrong owner was accepted for update_task")
    assert lookup_calls == [], "lookup must not run when the registered owner is wrong"


def test_live_task_ownership_registry_satisfies_owner_validation():
    """Regression guard: the live, wired TASK_OWNERSHIP registry
    (core/turn_coordinator_runtime.py) must keep passing this module's owner
    validation. This is exactly the drift this hardening PR found and fixed
    (the pre-existing test fixture used owner strings that never matched
    production) -- this test makes a future re-drift fail loudly here
    instead of only being caught deep in the runtime integration suite."""
    from core.turn_coordinator_runtime import TASK_OWNERSHIP

    create_proposal = prepare_task_proposal(
        Intent.CREATE_TASK, TASK_OWNERSHIP, scope="tenant:u1", title="Call supplier",
    )
    assert create_proposal.intent == Intent.CREATE_TASK

    update_result = prepare_task_proposal(
        Intent.UPDATE_TASK, TASK_OWNERSHIP, scope="tenant:u1", query="Call supplier",
        fields={TaskFields.DESCRIPTION: "Today"},
        lookup=lambda query, scope, limit: [{"id": "rec1"}],
    )
    assert update_result.intent == Intent.UPDATE_TASK

    complete_result = prepare_task_proposal(
        Intent.COMPLETE_TASK, TASK_OWNERSHIP, scope="tenant:u1", query="Call supplier",
        lookup=lambda query, scope, limit: [{"id": "rec1"}],
    )
    assert complete_result.intent == Intent.COMPLETE_TASK
