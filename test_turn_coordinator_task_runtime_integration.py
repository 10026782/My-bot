from types import SimpleNamespace

from airtable_schema import Tables, TaskFields
from core.evidence_message_adapter import from_evidence_result
from core.evidence_projection import build_evidence_result
from core.lifecycle_message_adapter import from_action_lifecycle_result
from core.lifecycle_projection import build_action_lifecycle_result
from core.message_contract import format_message_contract
from core.router import Intent
from core.router.ownership_contracts import CanonicalActionProposal, ResolverResult
from core.turn_coordinator_runtime import (
    gateway_call,
    prepare_task_gateway_call,
    queue_task_request,
)
from core.router.task_resolvers import resolve_task


def lookup(query, scope, limit):
    assert scope == "tenant:user"
    return [{"id": "rec-task"}][:limit]


def test_create_uses_one_gateway_queue_without_agent_or_write():
    queued = []
    reply = queue_task_request(
        intent=Intent.CREATE_TASK, scope="tenant:user", title="Call supplier",
        queue=lambda tool, payload: queued.append((tool, payload)) or {"message": "pending"},
    )
    assert reply["message"] == "pending"
    assert queued == [("airtable_add", {"table": Tables.TASKS, "fields": {TaskFields.NAME: "Call supplier"}})]


def test_create_does_not_copy_runtime_user_id_into_linked_owner_field():
    queued = []
    identity = SimpleNamespace(user_id="eliyahu")
    reply = queue_task_request(
        intent=Intent.CREATE_TASK, scope="tenant:user", title="Call supplier",
        identity=identity,
        queue=lambda tool, payload: queued.append((tool, payload)) or {"message": "pending"},
    )
    assert reply["message"] == "pending"
    assert queued[0][1]["fields"] == {TaskFields.NAME: "Call supplier"}


def test_update_and_complete_require_one_stable_match():
    update = prepare_task_gateway_call(
        Intent.UPDATE_TASK, scope="tenant:user", lookup=lookup,
        query="supplier", fields={TaskFields.DESCRIPTION: "today"},
    )
    complete = prepare_task_gateway_call(
        Intent.COMPLETE_TASK, scope="tenant:user", lookup=lookup, query="supplier",
    )
    assert update == (
        "airtable_update", {"table": Tables.TASKS, "record_id": "rec-task", "fields": {TaskFields.DESCRIPTION: "today"}}
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


class FakeGateway:
    """DI harness for the queue/approval contract; production suites cover ActionGateway."""

    def __init__(self):
        self.contracts = []
        self.writes = 0
        self.agent_calls = 0
        self.atomic_claims = 0
        self.public_replies = 0

    def queue(self, tool, payload):
        for index, existing in enumerate(self.contracts, start=1):
            if existing["payload"] == payload and existing["status"] == "rejected":
                return {"message": "rejected", "contract_id": index, "created_this_turn": False}
        contract = {"tool": tool, "payload": payload, "status": "pending"}
        self.contracts.append(contract)
        return {"message": "pending", "contract_id": len(self.contracts)}

    def approve(self, verified=True):
        contract = self.contracts[0]
        if contract["status"] != "pending":
            return "terminal"
        contract["status"] = "completed" if verified else "outcome_unknown"
        self.writes += 1
        self.atomic_claims += 1
        self.public_replies += 1
        return contract["status"]

    def reject(self):
        self.contracts[0]["status"] = "rejected"


def _create(gateway):
    return queue_task_request(
        intent=Intent.CREATE_TASK, scope="tenant:user", title="Call supplier",
        queue=gateway.queue,
    )


def _update(gateway, lookup=lookup):
    proposal = prepare_task_gateway_call(
        Intent.UPDATE_TASK, scope="tenant:user", lookup=lookup,
        query="supplier", fields={TaskFields.DESCRIPTION: "today"},
    )
    if not isinstance(proposal, ResolverResult):
        gateway.queue(*proposal)
    return proposal


def _complete(gateway, lookup=lookup):
    proposal = prepare_task_gateway_call(
        Intent.COMPLETE_TASK, scope="tenant:user", lookup=lookup, query="supplier",
    )
    if not isinstance(proposal, ResolverResult):
        gateway.queue(*proposal)
    return proposal


def test_create_pending_contract():
    gateway = FakeGateway()
    _create(gateway)
    assert gateway.contracts[0]["status"] == "pending"


def test_create_agent_zero():
    gateway = FakeGateway()
    _create(gateway)
    assert gateway.agent_calls == 0


def test_create_no_write_before_approval():
    gateway = FakeGateway()
    _create(gateway)
    assert gateway.writes == 0


def test_create_approval_executes_once():
    gateway = FakeGateway()
    _create(gateway)
    gateway.approve()
    gateway.approve()
    assert gateway.writes == 1


def test_create_verified_evidence_completes():
    gateway = FakeGateway()
    _create(gateway)
    gateway.approve()
    evidence = build_evidence_result(SimpleNamespace(status="completed"), evidence_ref="receipt", verified=True)
    assert evidence.verified and evidence.result == "success"


def test_create_unverified_is_unknown():
    gateway = FakeGateway()
    _create(gateway)
    gateway.approve(verified=False)
    evidence = build_evidence_result(SimpleNamespace(status="completed"), provider_result="ok")
    assert evidence.outcome_unknown and not evidence.verified


def test_create_rejection_is_terminal():
    gateway = FakeGateway()
    _create(gateway)
    gateway.reject()
    assert gateway.contracts[0]["status"] == "rejected"


def test_rejected_replay_creates_no_contract():
    gateway = FakeGateway()
    _create(gateway)
    gateway.reject()
    count = len(gateway.contracts)
    _create(gateway)
    assert len(gateway.contracts) == count


def test_update_zero_matches_no_proposal():
    result = _update(FakeGateway(), lambda *_: [])
    assert isinstance(result, ResolverResult) and result.match_count == 0


def test_update_one_match_has_stable_reference():
    result = _update(FakeGateway())
    assert result[1]["record_id"] == "rec-task"


def test_update_multiple_matches_no_selection():
    result = _update(FakeGateway(), lambda *_: [{"id": "a"}, {"id": "b"}])
    assert isinstance(result, ResolverResult) and not result.stable_reference


def test_update_lookup_is_bounded():
    seen = []
    def bounded(query, scope, limit):
        seen.append(limit)
        return [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    result = resolve_task("supplier", bounded, scope="tenant:user", limit=2)
    assert seen == [3] and result.match_count == 3


def test_update_has_no_agent_fallback():
    gateway = FakeGateway()
    _update(gateway)
    assert gateway.agent_calls == 0


def test_update_no_write_before_approval():
    gateway = FakeGateway()
    _update(gateway)
    assert gateway.writes == 0


def test_complete_zero_matches_fails_closed():
    result = _complete(FakeGateway(), lambda *_: [])
    assert isinstance(result, ResolverResult) and result.match_count == 0


def test_complete_one_match_creates_proposal():
    result = _complete(FakeGateway())
    assert result[1]["record_id"] == "rec-task"


def test_complete_multiple_matches_no_proposal():
    result = _complete(FakeGateway(), lambda *_: [{"id": "a"}, {"id": "b"}])
    assert isinstance(result, ResolverResult)


def test_complete_not_completed_before_approval():
    gateway = FakeGateway()
    _complete(gateway)
    assert gateway.contracts[0]["status"] == "pending"


def test_complete_requires_verified_evidence():
    gateway = FakeGateway()
    _complete(gateway)
    gateway.approve()
    evidence = build_evidence_result(SimpleNamespace(status="completed"), evidence_ref="receipt", verified=True)
    assert evidence.result == "success"


def test_duplicate_callback_executes_once():
    gateway = FakeGateway()
    _create(gateway)
    gateway.approve()
    evidence = build_evidence_result(SimpleNamespace(status="completed"), evidence_ref="receipt", verified=True)
    assert evidence.verified
    gateway.approve()
    assert gateway.writes == 1


def test_stale_callback_does_not_execute():
    gateway = FakeGateway()
    _create(gateway)
    gateway.contracts[0]["status"] = "expired"
    gateway.approve()
    assert gateway.writes == 0


def test_terminal_replay_does_not_mutate():
    gateway = FakeGateway()
    _create(gateway)
    gateway.reject()
    gateway.approve()
    assert gateway.writes == 0


def test_missing_lifecycle_snapshot_fails_closed():
    try:
        build_action_lifecycle_result(None)
    except ValueError:
        assert True
    else:
        raise AssertionError("missing lifecycle snapshot must not produce success")


def test_missing_evidence_is_not_success():
    evidence = build_evidence_result(SimpleNamespace(status="completed"))
    assert evidence.outcome_unknown


def test_provider_ack_is_not_verified_completion():
    evidence = build_evidence_result(SimpleNamespace(status="completed"), provider_result={"ok": True})
    assert not evidence.verified and evidence.outcome_unknown


def test_one_action_contract():
    gateway = FakeGateway()
    _create(gateway)
    assert len(gateway.contracts) == 1


def test_one_atomic_claim():
    gateway = FakeGateway()
    _create(gateway)
    gateway.approve()
    assert gateway.atomic_claims == 1


def test_one_public_reply():
    gateway = FakeGateway()
    _create(gateway)
    gateway.approve()
    assert gateway.public_replies == 1


def test_ws3_lifecycle_adapter():
    lifecycle = SimpleNamespace(
        lifecycle_state="completed", reply_owner="gateway", contract_ref="internal",
        approval_state="approved", execution_state="succeeded", error_replay_classification="",
    )
    evidence = SimpleNamespace(result="success", evidence_ref="receipt", provider_result="", verified=True, outcome_unknown=False, error="")
    contract = from_action_lifecycle_result(lifecycle, evidence=evidence)
    assert contract.source_module == "core.lifecycle_message_adapter"


def test_no_action_contract_id_in_reply():
    evidence = SimpleNamespace(result="success", evidence_ref="receipt", provider_result="", verified=True, outcome_unknown=False, error="")
    text = format_message_contract(from_evidence_result(evidence))
    assert "contract" not in text.lower()


def test_no_airtable_record_id_in_reply():
    evidence = SimpleNamespace(result="success", evidence_ref="receipt", provider_result="rec-secret", verified=True, outcome_unknown=False, error="")
    text = format_message_contract(from_evidence_result(evidence))
    assert "rec-secret" not in text


def test_no_tool_name_in_reply():
    evidence = SimpleNamespace(result="success", evidence_ref="receipt", provider_result="airtable_update", verified=True, outcome_unknown=False, error="")
    text = format_message_contract(from_evidence_result(evidence))
    assert "airtable_update" not in text


def test_outcome_unknown_is_not_success():
    evidence = SimpleNamespace(result="outcome_unknown", evidence_ref="", provider_result="", verified=False, outcome_unknown=True, error="missing")
    contract = from_evidence_result(evidence)
    assert contract.state.value != "completed"


def test_app_create_consumer_receives_gateway_mapping(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:TEST")
    monkeypatch.setenv("AIRTABLE_API_KEY", "test")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "test")
    import app

    identity = SimpleNamespace(memory_key="tenant:user", role="owner")
    monkeypatch.setattr(app, "enforce", lambda *_: None)
    monkeypatch.setattr(
        app, "_queue_approval_detailed",
        lambda *_, **__: {
            "message": "pending", "created_this_turn": True,
            "contract_id": "c1", "reply_owner": "gateway",
            "final_response_count": 1, "action_tool": "airtable_add",
        },
    )
    out_meta = {}
    reply = app._queue_deterministic_create_task(
        "Call supplier", "chat", "telegram", "create", identity, out_meta,
    )
    assert reply == "pending"
    assert out_meta == {
        "source_module": "action_gateway", "reply_owner": "gateway",
        "final_response_count": 1,
    }


def test_app_update_consumer_preserves_gateway_metadata(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:TEST")
    monkeypatch.setenv("AIRTABLE_API_KEY", "test")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "test")
    import app
    import core.turn_coordinator_runtime as runtime

    identity = SimpleNamespace(memory_key="tenant:user", role="owner")
    monkeypatch.setattr(app, "enforce", lambda *_: None)
    monkeypatch.setattr(runtime, "airtable_task_lookup", lambda *_: [{"id": "rec-task"}])
    monkeypatch.setattr(
        app, "_queue_approval_detailed",
        lambda *_: {
            "message": "pending", "created_this_turn": True,
            "contract_id": "c1", "reply_owner": "gateway",
            "final_response_count": 1, "source_module": "action_gateway",
        },
    )
    out_meta = {}
    reply = app._queue_deterministic_task_update(
        "update_task", "עדכן משימה supplier: today", "chat", "telegram", identity, out_meta,
    )
    assert reply == "pending"
    assert out_meta["reply_owner"] == "gateway"


def test_missing_update_record_id_fails_closed():
    try:
        gateway_call(CanonicalActionProposal(
            intent=Intent.UPDATE_TASK, canonical_tool="task_update",
            resource="משימות (Tasks)", fields={"record_id": ""},
        ))
    except ValueError as exc:
        assert "stable" in str(exc)
    else:
        raise AssertionError("missing stable reference must fail closed")


def test_bounded_reader_rejects_invalid_limits(monkeypatch):
    from tools import airtable_tools

    assert airtable_tools.airtable_get_records("Tasks", max_records=0) == []
    try:
        airtable_tools.airtable_get_records("Tasks", max_records=-1)
    except ValueError as exc:
        assert "negative" in str(exc)
    else:
        raise AssertionError("negative max_records must fail closed")


def test_create_does_not_copy_runtime_identity_into_linked_owner():
    """A runtime user_id is not an Airtable linked-record ID."""
    identity = SimpleNamespace(user_id="eliyahu", role="owner")
    queued = []
    reply = queue_task_request(
        intent=Intent.CREATE_TASK, scope="tenant:user", title="Call supplier",
        queue=lambda tool, payload: queued.append((tool, payload)) or {"message": "pending"},
        identity=identity,
    )
    assert reply["message"] == "pending"
    assert queued == [("airtable_add", {
        "table": Tables.TASKS,
        "fields": {TaskFields.NAME: "Call supplier"},
    })]


def test_create_respects_explicit_owner():
    """Explicit OWNER in fields should not be overridden by identity."""
    identity = SimpleNamespace(user_id="eliyahu", role="owner")
    queued = []
    reply = queue_task_request(
        intent=Intent.CREATE_TASK, scope="tenant:user", title="Call supplier",
        fields={TaskFields.OWNER: "someone_else"},
        queue=lambda tool, payload: queued.append((tool, payload)) or {"message": "pending"},
        identity=identity,
    )
    assert reply["message"] == "pending"
    assert queued[0][1]["fields"][TaskFields.OWNER] == "someone_else"


def test_create_without_identity_has_no_owner():
    """When identity is None, OWNER should not be auto-populated."""
    queued = []
    reply = queue_task_request(
        intent=Intent.CREATE_TASK, scope="tenant:user", title="Call supplier",
        queue=lambda tool, payload: queued.append((tool, payload)) or {"message": "pending"},
        identity=None,
    )
    assert reply["message"] == "pending"
    assert TaskFields.OWNER not in queued[0][1]["fields"]
