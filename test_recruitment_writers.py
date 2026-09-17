"""Focused Phase 2 tests for the single recruitment ActionGateway writer."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

import recruitment_crm as writer
from identity import Identity
from core.action_gateway import ActionGateway, ExecutionLedger
from core.dispatcher_outcome import DispatcherOutcome
from tools.dispatcher import _validate_execution_proof, dispatch_tool
from airtable_schema import (
    Direction,
    MonthlyCalculationBatchFields as BF,
    PaymentFields,
    WorkerAssignmentFields as AF,
    WorkerMonthlyResultFields as RF,
)


ASSIGNMENT_ID = "recAssignment0001"
BATCH_ID = "recBatch000000001"
RESULT_ID = "recResult00000001"
PAYMENT_ID = "recPayment0000001"


def assignment(*, organization="org1", start="2026-01-01", end=None):
    fields = {
        AF.REFERENCE: "WA-1", AF.CONTACT: ["contact1"], AF.ORGANIZATION: [organization],
        AF.STATUS: "active", AF.START_DATE: start,
    }
    if end:
        fields[AF.END_DATE] = end
    return {"id": ASSIGNMENT_ID, "fields": fields}


def batch(*, organization="org1", status="reviewed", month="2026-08-01", original=""):
    fields = {
        BF.REFERENCE: "B-1", BF.ORGANIZATION: [organization], BF.MONTH: month,
        BF.BATCH_TYPE: "canonical", BF.STATUS: status,
    }
    if original:
        fields[BF.ORIGINAL_CLOSED_BATCH] = [original]
    return {"id": BATCH_ID, "fields": fields}


def result():
    return {"id": RESULT_ID, "fields": {
        RF.REFERENCE: "R-1", RF.BATCH: [BATCH_ID], RF.WORKER_ASSIGNMENT: [ASSIGNMENT_ID],
        RF.ATTRIBUTED_REVENUE: 100, RF.WORKER_DUE: 40, RF.PAYOUT_STATUS: "pending",
    }}


def created(record_id):
    outcome = Mock(status="created", error=None)
    outcome.record = {"id": record_id}
    return outcome


def test_happy_path_creates_result_without_writing_derived_retained(monkeypatch):
    monkeypatch.setattr(writer, "_assignment", lambda _id: (writer.WorkerAssignmentRead.from_airtable(assignment()), assignment()["fields"]))
    monkeypatch.setattr(writer, "_batch", lambda _id: (writer.MonthlyCalculationBatchRead.from_airtable(batch()), batch()["fields"]))
    monkeypatch.setattr(writer, "_linked", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(writer, "_by_reference", lambda *_args: [])
    create = Mock(return_value=created(RESULT_ID))
    monkeypatch.setattr(writer, "airtable_create", create)

    response = writer.execute_recruitment_write("create_result", {
        "reference": "R-1", "batch_id": BATCH_ID, "assignment_id": ASSIGNMENT_ID,
        "attributed_revenue": "100", "worker_due": "40",
    }, actor_role="owner")

    assert response["ok"] is True
    fields = create.call_args.args[1]
    assert RF.POSEIDON_RETAINED not in fields


def test_duplicate_active_assignment_is_rejected(monkeypatch):
    monkeypatch.setattr(writer, "_linked", lambda *_args, **_kwargs: [assignment()])
    create = Mock()
    monkeypatch.setattr(writer, "airtable_create", create)
    response = writer.execute_recruitment_write("create_assignment", {
        "reference": "WA-2", "contact_id": "contact1", "organization_id": "org1",
        "status": "active", "start_date": "2026-08-01",
    }, actor_role="owner")
    assert response["ok"] is False
    assert "only one active" in response["user_message"]
    create.assert_not_called()


@pytest.mark.parametrize("organization,start,error", [
    ("org2", "2026-01-01", "organizations must match"),
    ("org1", "2026-09-01", "outside the assignment period"),
])
def test_result_rejects_wrong_organization_or_date(monkeypatch, organization, start, error):
    assignment_record = assignment(organization=organization, start=start)
    monkeypatch.setattr(writer, "_assignment", lambda _id: (
        writer.WorkerAssignmentRead.from_airtable(assignment_record), assignment_record["fields"]))
    monkeypatch.setattr(writer, "_batch", lambda _id: (
        writer.MonthlyCalculationBatchRead.from_airtable(batch()), batch()["fields"]))
    monkeypatch.setattr(writer, "_linked", lambda *_args, **_kwargs: [])
    response = writer.execute_recruitment_write("create_result", {
        "reference": "R-2", "batch_id": BATCH_ID, "assignment_id": ASSIGNMENT_ID,
        "attributed_revenue": 100, "worker_due": 40,
    }, actor_role="owner")
    assert response["ok"] is False
    assert error in response["user_message"]


def test_closed_batch_blocks_result_financial_mutation(monkeypatch):
    closed = batch(status="closed")
    monkeypatch.setattr(writer, "_result", lambda _id: (
        writer.WorkerMonthlyResultRead.from_airtable(result()), result()["fields"]))
    monkeypatch.setattr(writer, "_batch", lambda _id: (
        writer.MonthlyCalculationBatchRead.from_airtable(closed), closed["fields"]))
    monkeypatch.setattr(writer, "_assignment", lambda _id: (
        writer.WorkerAssignmentRead.from_airtable(assignment()), assignment()["fields"]))
    patch = Mock()
    monkeypatch.setattr(writer, "airtable_patch", patch)
    response = writer.execute_recruitment_write("update_result", {
        "record_id": RESULT_ID, "worker_due": 41,
    }, actor_role="owner")
    assert response["ok"] is False
    assert "immutable" in response["user_message"]
    patch.assert_not_called()


def test_adjustment_requires_closed_matching_original(monkeypatch):
    original = batch(status="reviewed")
    monkeypatch.setattr(writer, "_batch", lambda _id: (
        writer.MonthlyCalculationBatchRead.from_airtable(original), original["fields"]))
    monkeypatch.setattr(writer, "_linked", lambda *_args, **_kwargs: [])
    response = writer.execute_recruitment_write("create_adjustment_batch", {
        "reference": "ADJ-1", "organization_id": "org1", "month": "2026-08-01",
        "original_closed_batch_id": BATCH_ID,
    }, actor_role="owner")
    assert response["ok"] is False
    assert "closed original" in response["user_message"]


def test_same_reference_is_idempotent_only_when_payload_matches(monkeypatch):
    payload = {
        "reference": "WA-1", "contact_id": "contact1", "organization_id": "org1",
        "status": "active", "start_date": "2026-01-01",
    }
    monkeypatch.setattr(writer, "_linked", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(writer, "_by_reference", lambda *_args: [{"id": ASSIGNMENT_ID}])
    monkeypatch.setattr(writer, "get_record_fields", lambda *_args: assignment()["fields"])
    create = Mock()
    monkeypatch.setattr(writer, "airtable_create", create)
    response = writer.execute_recruitment_write("create_assignment", payload, actor_role="owner")
    assert response["ok"] is True
    assert response["evidence"]["idempotent"] is True
    create.assert_not_called()

    monkeypatch.setattr(writer, "get_record_fields", lambda *_args: {
        **assignment()["fields"], AF.START_DATE: "2025-01-01",
    })
    conflict = writer.execute_recruitment_write("create_assignment", payload, actor_role="owner")
    assert conflict["ok"] is False
    assert "different data" in conflict["user_message"]


def test_close_validates_reconciliation_and_incoming_payment(monkeypatch):
    reviewed = batch()
    reviewed["fields"][BF.INCOMING_PAYMENT] = [PAYMENT_ID]
    monkeypatch.setattr(writer, "_batch", lambda _id: (
        writer.MonthlyCalculationBatchRead.from_airtable(reviewed), reviewed["fields"]))
    monkeypatch.setattr(writer, "get_record_fields", lambda table, _id: (
        {PaymentFields.AMOUNT: 100, PaymentFields.DIRECTION: Direction.RECEIVABLE,
         PaymentFields.COUNTERPARTY_ORGANIZATION: ["org1"]}
        if table == writer.Tables.PAYMENTS else reviewed["fields"]))
    monkeypatch.setattr(writer, "_linked", lambda *_args, **_kwargs: [
        {"fields": {RF.ATTRIBUTED_REVENUE: 100}}])
    patch = Mock(return_value=True)
    monkeypatch.setattr(writer, "airtable_patch", patch)
    response = writer.execute_recruitment_write("close_batch", {"record_id": BATCH_ID},
                                                actor_role="owner")
    assert response["ok"] is True
    patch.assert_called_once()


def test_direct_dispatch_without_actiongateway_proof_is_rejected(monkeypatch):
    execute = Mock()
    monkeypatch.setattr(writer, "execute_recruitment_write", execute)
    monkeypatch.setattr("tools.dispatcher._ff.is_enabled", lambda _flag: False)
    response = dispatch_tool(
        "recruitment_write", {"operation": "create_assignment", "payload": {}},
        Identity("owner1", "owner"),
    )
    assert response["ok"] is False
    assert "approved ActionContract" in response["user_message"]
    execute.assert_not_called()


def test_recruitment_write_fingerprint_parity_rejects_nested_payload_tampering():
    gateway = ActionGateway(ledger=ExecutionLedger())
    identity = Identity("recruitment-owner", "owner")
    action = {
        "operation": "create_assignment",
        "payload": {
            "reference": "WA-fingerprint", "contact_id": "contact1", "organization_id": "org1",
            "status": "active", "start_date": "2026-08-01",
        },
    }
    proposed = gateway.propose_action(
        tenant_id=identity.tenant_id, canonical_user_id=identity.memory_key,
        tool_name="recruitment_write", tool_inputs=action,
        origin_channel="telegram", origin_chat_id=identity.user_id,
        requires_approval=True, identity=identity, trusted_source="recruitment",
    )
    assert proposed.ok
    contract = gateway.find_contract(proposed.contract_id)
    context = {
        "contract_id": contract.contract_id, "approved_by": identity.memory_key,
        "tool_name": contract.tool_name, "tenant_id": contract.tenant_id,
        "canonical_user_id": contract.canonical_user_id,
        "business_action_fingerprint": contract.business_action_fingerprint, "status": "approved",
    }
    assert _validate_execution_proof("recruitment_write", contract.normalized_payload,
                                    identity, context, "recruitment") is None

    changed_operation = deepcopy(contract.normalized_payload)
    changed_operation["operation"] = "create_canonical_batch"
    changed_nested = deepcopy(contract.normalized_payload)
    changed_nested["payload"]["organization_id"] = "org2"
    added_nested = deepcopy(contract.normalized_payload)
    added_nested["payload"]["notes"] = "after approval"
    removed_nested = deepcopy(contract.normalized_payload)
    del removed_nested["payload"]["start_date"]
    for tampered in (changed_operation, changed_nested, added_nested, removed_nested):
        assert _validate_execution_proof("recruitment_write", tampered, identity, context,
                                        "recruitment") == (
            "approval-sensitive execution proof does not match the action payload."
        )


@pytest.mark.parametrize(("action", "natural_key"), [
    ({"operation": "create_assignment", "payload": {
        "reference": "WA-durable", "contact_id": "contact1", "organization_id": "org1",
        "status": "active", "start_date": "2026-08-01",
    }}, "WA:contact1:org1:2026-08-01"),
    ({"operation": "create_canonical_batch", "payload": {
        "reference": "MCB-durable", "organization_id": "org1", "month": "2026-08-01",
    }}, "MCB:org1:2026-08"),
    ({"operation": "create_adjustment_batch", "payload": {
        "reference": "ADJ-durable", "organization_id": "org1", "month": "2026-08-01",
        "original_closed_batch_id": BATCH_ID, "adjustment_sequence": 1,
    }}, f"MCB-ADJ:{BATCH_ID}:1"),
    ({"operation": "create_result", "payload": {
        "reference": "WMR-durable", "batch_id": BATCH_ID, "assignment_id": ASSIGNMENT_ID,
        "attributed_revenue": "100", "worker_due": "40",
    }}, f"WMR:{BATCH_ID}:{ASSIGNMENT_ID}"),
])
def test_independent_recruitment_contexts_get_the_same_durable_natural_key(action, natural_key):
    first = ActionGateway(ledger=ExecutionLedger())
    second = ActionGateway(ledger=ExecutionLedger())
    identity = Identity("recruitment-owner", "owner")
    for gateway in (first, second):
        proposed = gateway.propose_action(
            tenant_id=identity.tenant_id, canonical_user_id=identity.memory_key,
            tool_name="recruitment_write", tool_inputs=action,
            origin_channel="telegram", origin_chat_id=identity.user_id,
            requires_approval=True, identity=identity, trusted_source="recruitment",
        )
        assert proposed.ok
        assert gateway.find_contract(proposed.contract_id).idempotency_key == natural_key


def test_uncertain_create_propagates_outcome_unknown_not_a_retryable_failure(monkeypatch):
    monkeypatch.setattr(writer, "_linked", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(writer, "_by_reference", lambda *_args: [])
    uncertain = Mock(status="outcome_unknown", error="timeout")
    uncertain.record = None
    monkeypatch.setattr(writer, "airtable_create", Mock(return_value=uncertain))
    response = writer.execute_recruitment_write("create_assignment", {
        "reference": "WA-unknown", "contact_id": "contact1", "organization_id": "org1",
        "status": "active", "start_date": "2026-08-01",
    }, actor_role="owner")
    assert isinstance(response, DispatcherOutcome)
    assert response.is_outcome_unknown()
    assert response.raw_response["evidence"]["status"] == "outcome_unknown"


def test_actiongateway_keeps_uncertain_recruitment_create_outcome_unknown(monkeypatch):
    from core.atomic_claim_repository import AtomicExecutionClaim, ClaimAcquisitionResult

    monkeypatch.setattr("feature_flags.is_enabled", lambda name: name == "FEATURE_ATOMIC_CLAIMS")
    monkeypatch.setattr("core.atomic_claim_repository.claim_contract_execution", lambda **_kwargs:
                        ClaimAcquisitionResult("acquired", AtomicExecutionClaim(
                            "contract", "owner", "execution", 0, "WA:contact1:org1:2026-08-01")))
    monkeypatch.setattr("core.atomic_claim_repository.update_claim_status", lambda *_args, **_kwargs: True)
    unknown = DispatcherOutcome(
        "outcome_unknown", "⚠️ תוצאת הכתיבה אינה ידועה. אין לנסות שוב אוטומטית.",
        error="timeout", raw_response={"ok": False, "tool": "recruitment_write"},
    )
    gateway = ActionGateway(ledger=ExecutionLedger(), tool_executor=lambda *_args, **_kwargs: unknown)
    identity = Identity("recruitment-unknown-owner", "owner", external_id="recruitment-unknown-owner")
    proposed = gateway.propose_action(
        tenant_id=identity.tenant_id, canonical_user_id=identity.memory_key,
        tool_name="recruitment_write",
        tool_inputs={"operation": "create_assignment", "payload": {
            "reference": "WA-unknown", "contact_id": "contact1", "organization_id": "org1",
            "start_date": "2026-08-01",
        }},
        origin_channel="telegram", origin_chat_id=identity.user_id,
        requires_approval=True, identity=identity, trusted_source="recruitment",
    )
    assert proposed.ok
    gateway.approve(proposed.contract_id, approver=identity.memory_key, approver_role="owner")
    assert gateway.find_contract(proposed.contract_id).status == "outcome_unknown"


def test_recruitment_create_never_falls_back_without_atomic_claims(monkeypatch):
    monkeypatch.setattr("feature_flags.is_enabled", lambda _name: False)
    execute = Mock()
    gateway = ActionGateway(ledger=ExecutionLedger(), tool_executor=execute)
    identity = Identity("recruitment-claim-owner", "owner", external_id="recruitment-claim-owner")
    proposed = gateway.propose_action(
        tenant_id=identity.tenant_id, canonical_user_id=identity.memory_key,
        tool_name="recruitment_write",
        tool_inputs={"operation": "create_assignment", "payload": {
            "reference": "WA-claim", "contact_id": "contact1", "organization_id": "org1",
            "status": "active", "start_date": "2026-08-01",
        }},
        origin_channel="telegram", origin_chat_id=identity.user_id,
        requires_approval=True, identity=identity, trusted_source="recruitment",
    )
    assert proposed.ok
    gateway.approve(proposed.contract_id, approver=identity.memory_key, approver_role="owner")
    execute.assert_not_called()
    assert gateway.find_contract(proposed.contract_id).status == "approved"


@pytest.mark.parametrize("tool,inputs", [
    ("airtable_add", {"table": writer.Tables.WORKER_ASSIGNMENTS, "fields": {"x": "y"}}),
    ("airtable_update", {"table": writer.Tables.WORKER_ASSIGNMENTS,
                         "record_id": ASSIGNMENT_ID, "fields": {"x": "y"}}),
])
def test_generic_airtable_writers_cannot_bypass_recruitment_writer(monkeypatch, tool, inputs):
    identity = Identity("owner1", "owner")
    monkeypatch.setattr("tools.dispatcher._ff.is_enabled", lambda _flag: False)
    context = {
        "contract_id": "contract1", "approved_by": identity.memory_key,
        "tool_name": tool, "tenant_id": identity.tenant_id,
        "canonical_user_id": identity.memory_key, "status": "approved",
        "business_action_fingerprint": ActionGateway.compute_business_fingerprint(
            identity.tenant_id, identity.memory_key, tool, ActionGateway.normalize_payload(inputs)),
    }
    response = dispatch_tool(tool, inputs, identity, trusted_source="action_gateway",
                             execution_context=context)
    assert response["ok"] is False
    assert "only be mutated through recruitment_write" in response["user_message"]
