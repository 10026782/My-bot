from core.router.ownership_contracts import IntentOwnershipDecision, IntentOwnershipRegistry
from core.router.route_decision import Intent
from core.router.task_integration import prepare_task_proposal
from airtable_schema import TaskFields

# מחרוזות ה-owner תואמות בדיוק ל-registry החי והמחווט TASK_OWNERSHIP
# (core/turn_coordinator_runtime.py) -- ה-fixture הזה השתמש קודם ב-
# "TASK_BUILDER"/"RESOLVER" (אותיות גדולות, גנרי), שמעולם לא תאם לערכי
# הפרודקשן "task_builder"/"task_resolver" והיה מסתיר באג של owner שגוי
# במקום לתפוס אותו.
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


# --- המשך-hardening (אחרי PR #564): אימות owner משלים את resolver_required ---


def test_integration_create_rejects_wrong_owner_even_with_correct_resolver_required():
    """resolver_required=False תואם למדיניות הצפויה של CREATE_TASK, אבל
    ה-owner הרשום אינו task_builder -- זה חייב עדיין להיכשל בסגירה,
    לפני כל בניית proposal."""
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
    """resolver_required=True תואם למדיניות הצפויה של UPDATE_TASK, אבל
    ה-owner הרשום אינו task_resolver -- זה חייב להיכשל בסגירה לפני
    שה-lookup נקרא בכלל."""
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
    """שומר-רגרסיה: ה-registry החי והמחווט TASK_OWNERSHIP
    (core/turn_coordinator_runtime.py) חייב להמשיך לעבור את אימות ה-owner
    של המודול הזה. זה בדיוק ה-drift שה-PR הזה של hardening מצא ותיקן
    (ה-fixture הקודם של הטסט השתמש במחרוזות owner שמעולם לא תאמו
    לפרודקשן) -- הטסט הזה גורם ל-drift חוזר להיכשל בקול רם כאן, במקום
    להיתפס רק עמוק בתוך ה-runtime integration suite."""
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
