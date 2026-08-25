"""Phase 4B-1B durable ActionContract lifecycle regression tests."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from airtable_schema import ActionContractsFields
from core.action_contract_repository import (
    ALLOWED_CONTRACT_TRANSITIONS,
    ActionContractRepository,
    ActionContractTransitionConflictError,
    ActionContractTransitionPersistenceError,
    _contract_to_fields,
    _record_to_contract,
)
from core.action_gateway import ActionGateway, ExecutionLedger
from core.dispatcher_outcome import DispatcherOutcome


class LifecycleRepository:
    """Shared durable store for independent ledger instances."""

    def __init__(self):
        self.records: dict[str, dict] = {}
        self.transitions: list[tuple[str, str, str, int]] = []
        self.fail_statuses: set[str] = set()

    def save(self, contract):
        self.records[contract.contract_id] = {
            "id": f"rec-{contract.contract_id}",
            "fields": _contract_to_fields(contract),
        }
        return True

    def get(self, contract_id):
        record = self.records.get(contract_id)
        return _record_to_contract(record) if record else None

    def find_by_business_fingerprint(self, fingerprint):
        for record in self.records.values():
            if record["fields"][ActionContractsFields.BUSINESS_FINGERPRINT] == fingerprint:
                return _record_to_contract(record)
        return None

    def find_pending_by_canonical_user(self, canonical_user_id):
        return [
            _record_to_contract(record)
            for record in self.records.values()
            if record["fields"][ActionContractsFields.CANONICAL_USER_ID] == canonical_user_id
            and record["fields"][ActionContractsFields.STATUS] == "pending"
        ]

    def transition(
        self, contract_id, *, expected_status, expected_version, new_status, updates=None,
    ):
        if new_status in self.fail_statuses:
            raise ActionContractTransitionPersistenceError("simulated lifecycle outage")
        contract = self.get(contract_id)
        if contract is None:
            raise ActionContractTransitionConflictError("missing")
        if contract.status != expected_status or contract.version != expected_version:
            raise ActionContractTransitionConflictError("stale")
        # Audit #9-3 fidelity: enforce the same transition-legality table as
        # the real repository, reused rather than duplicated, so an illegal
        # transition the real repository would reject is rejected here too.
        if (new_status != contract.status
                and new_status not in ALLOWED_CONTRACT_TRANSITIONS.get(contract.status, frozenset())):
            raise ActionContractTransitionConflictError(
                f"invalid lifecycle transition: {contract.status} -> {new_status}"
            )
        contract.status = new_status
        contract.version += 1
        for key, value in (updates or {}).items():
            setattr(contract, key, value)
        self.records[contract_id]["fields"] = _contract_to_fields(contract)
        self.transitions.append(
            (contract_id, expected_status, new_status, expected_version)
        )
        return self.get(contract_id)


def _identity():
    return SimpleNamespace(
        role="owner",
        user_id="owner-1",
        display_name="Owner",
        domain_id="real_estate",
        external_id="tg-100",
        allowed_domains=["real_estate"],
    )


def _propose(gateway):
    result = gateway.propose_action(
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner-1",
        tool_name="airtable_add",
        tool_inputs={"table": "Leads", "fields": {"Name": "Lifecycle Lead"}},
        origin_channel="telegram",
        origin_chat_id="tg-100",
        requires_approval=True,
        identity=_identity(),
        trusted_source="lead_capture",
    )
    assert result.ok is True
    return result.contract_id


def _gateway(repository, executor=None):
    return ActionGateway(
        ledger=ExecutionLedger(repository=repository),
        tool_executor=executor or MagicMock(
            return_value={"ok": True, "external_id": "rec12345678901234"}
        ),
    )


def test_approve_persists_actor_then_explicit_success_persists_completed():
    repository = LifecycleRepository()
    executor = MagicMock(return_value={"ok": True, "external_id": "rec12345678901234"})
    gateway = _gateway(repository, executor)
    contract_id = _propose(gateway)

    with patch("feature_flags.is_enabled", return_value=False):
        reply = gateway.approve(contract_id, "boss_hq:owner-1", "owner")

    durable = repository.get(contract_id)
    assert durable.status == "completed"
    assert durable.approved_by == "boss_hq:owner-1"
    assert durable.approved_at is not None
    assert [item[1:3] for item in repository.transitions] == [
        ("pending", "approved"), ("approved", "completed"),
    ]
    assert executor.call_count == 1
    assert "הפעולה הושלמה" in reply


def test_reject_persists_rejected_and_never_dispatches():
    repository = LifecycleRepository()
    executor = MagicMock()
    gateway = _gateway(repository, executor)
    contract_id = _propose(gateway)

    reply = gateway.reject(contract_id, rejected_by="boss_hq:owner-1")

    assert repository.get(contract_id).status == "rejected"
    assert executor.call_count == 0
    assert reply.startswith("🚫")


@pytest.mark.parametrize(
    ("outcome", "expected_status"),
    [
        (DispatcherOutcome(result="failed", user_message="denied", error="denied"), "failed"),
        (
            DispatcherOutcome(
                result="outcome_unknown", user_message="unknown", error="timeout after send",
            ),
            "outcome_unknown",
        ),
    ],
)
def test_atomic_non_success_preserves_canonical_outcome(outcome, expected_status):
    repository = LifecycleRepository()
    gateway = _gateway(repository)
    contract_id = _propose(gateway)

    with patch("feature_flags.is_enabled", return_value=True), patch(
        "core.action_gateway_atomic_executor.execute_with_atomic_claim",
        return_value=(False, outcome, outcome.error),
    ):
        gateway.approve(contract_id, "boss_hq:owner-1", "owner")

    assert repository.get(contract_id).status == expected_status


@pytest.mark.parametrize(
    "terminal", ["approved", "completed", "rejected", "failed", "outcome_unknown"],
)
def test_restart_pending_lookup_excludes_every_non_actionable_status(terminal):
    repository = LifecycleRepository()
    first = ExecutionLedger(repository=repository)
    contract_id = _propose(ActionGateway(ledger=first))
    if terminal == "rejected":
        first.update_status(contract_id, terminal)
    else:
        first.update_status(contract_id, "approved")
        if terminal != "approved":
            first.update_status(contract_id, terminal)

    restarted = ExecutionLedger(repository=repository)
    assert restarted.find_live_by_user("boss_hq:owner-1") == []
    assert restarted.find_by_id(contract_id).status == terminal


def test_restart_still_recovers_genuinely_pending_contract():
    repository = LifecycleRepository()
    contract_id = _propose(ActionGateway(ledger=ExecutionLedger(repository=repository)))

    restarted = ExecutionLedger(repository=repository)
    pending = restarted.find_live_by_user("boss_hq:owner-1")

    assert [contract.contract_id for contract in pending] == [contract_id]
    assert pending[0].status == "pending"


def test_approval_persistence_failure_is_fail_closed_before_dispatch():
    repository = LifecycleRepository()
    repository.fail_statuses.add("approved")
    executor = MagicMock()
    gateway = _gateway(repository, executor)
    contract_id = _propose(gateway)

    reply = gateway.approve(contract_id, "boss_hq:owner-1", "owner")

    assert repository.get(contract_id).status == "pending"
    assert gateway._ledger.find_by_id(contract_id).status == "pending"
    executor.assert_not_called()
    assert "לא נשמר" in reply


def test_terminal_persistence_failure_is_visible_and_not_reported_as_success():
    repository = LifecycleRepository()
    repository.fail_statuses.add("completed")
    executor = MagicMock(return_value={"ok": True, "external_id": "rec12345678901234"})
    gateway = _gateway(repository, executor)
    contract_id = _propose(gateway)

    with patch("feature_flags.is_enabled", return_value=False):
        reply = gateway.approve(contract_id, "boss_hq:owner-1", "owner")

    assert executor.call_count == 1
    assert repository.get(contract_id).status == "approved"
    assert "completed" in reply
    assert "אין לנסות שוב" in reply
    assert "✅" not in reply


def test_atomic_database_unavailable_never_dispatches_and_does_not_resurrect_pending():
    repository = LifecycleRepository()
    executor = MagicMock()
    gateway = _gateway(repository, executor)
    contract_id = _propose(gateway)

    with patch("feature_flags.is_enabled", return_value=True), patch(
        "core.action_gateway_atomic_executor.execute_with_atomic_claim",
        return_value=(False, None, "atomic claim database unavailable"),
    ):
        reply = gateway.approve(contract_id, "boss_hq:owner-1", "owner")

    executor.assert_not_called()
    assert repository.get(contract_id).status == "approved"
    assert ExecutionLedger(repository=repository).find_live_by_user("boss_hq:owner-1") == []
    assert "database unavailable" in reply


def test_stale_lifecycle_update_is_rejected_and_ram_cache_reflects_durable_truth():
    """Audit #8-2 correction: this assertion previously expected the RAM
    cache to stay frozen at its pre-conflict value. That predates BUG-127A's
    stale-cache refresh (core/action_gateway.py:940,
    _refresh_stale_contract_cache), which intentionally re-caches from
    durable truth as part of handling the conflict — before deciding the
    retry still fails. The conflict is still raised and the forbidden
    "approved" transition is never persisted anywhere; the RAM cache is
    allowed to reflect current durable truth ("rejected"), which is exactly
    what BUG-127A's refresh is for."""
    repository = LifecycleRepository()
    ledger = ExecutionLedger(repository=repository)
    contract_id = _propose(ActionGateway(ledger=ledger))
    durable = repository.get(contract_id)
    durable.status = "rejected"
    durable.version += 1
    repository.records[contract_id]["fields"] = _contract_to_fields(durable)

    with pytest.raises(ActionContractTransitionConflictError):
        ledger.update_status(contract_id, "approved")

    # Forbidden transition never persisted anywhere — neither cache nor
    # durable store ever shows "approved".
    assert ledger._store[contract_id].status != "approved"
    assert repository.get(contract_id).status != "approved"
    # BUG-127A: RAM cache legitimately refreshes to current durable truth.
    assert ledger._store[contract_id].status == "rejected"
    # Durable repository truth remains authoritative and unchanged by the
    # rejected attempt.
    assert repository.get(contract_id).status == "rejected"


def test_fake_lifecycle_repository_rejects_illegal_transition():
    """Audit #9-3 fidelity: LifecycleRepository (the in-memory test double)
    must reject a transition the real ActionContractRepository's
    ALLOWED_CONTRACT_TRANSITIONS table would also reject, not just a stale
    expected_status/version — proven directly against ALLOWED_CONTRACT_TRANSITIONS
    itself so this stays correct if the table's shape ever changes."""
    memory = LifecycleRepository()
    ledger = ExecutionLedger(repository=memory)
    contract_id = _propose(ActionGateway(ledger=ledger))
    assert "executing" not in ALLOWED_CONTRACT_TRANSITIONS["pending"]

    with pytest.raises(ActionContractTransitionConflictError):
        memory.transition(
            contract_id,
            expected_status="pending",
            expected_version=1,
            new_status="executing",
        )

    assert memory.get(contract_id).status == "pending"


def test_repository_transition_uses_partial_patch_and_verifies_version():
    repository = ActionContractRepository()
    memory = LifecycleRepository()
    ledger = ExecutionLedger(repository=memory)
    contract_id = _propose(ActionGateway(ledger=ledger))
    pending_record = memory.records[contract_id]
    approved_record = {
        "id": pending_record["id"],
        "fields": dict(pending_record["fields"]),
    }
    approved_record["fields"].update({
        ActionContractsFields.STATUS: "approved",
        ActionContractsFields.VERSION: 2,
        ActionContractsFields.APPROVED_BY: "boss_hq:owner-1",
        ActionContractsFields.APPROVED_AT: 123.5,
    })

    with patch(
        "core.action_contract_repository.at_get_by_field",
        side_effect=[pending_record, approved_record],
    ), patch("core.action_contract_repository.airtable_patch", return_value=True) as patch_record:
        result = repository.transition(
            contract_id,
            expected_status="pending",
            expected_version=1,
            new_status="approved",
            updates={"approved_by": "boss_hq:owner-1", "approved_at": 123.5},
        )

    fields = patch_record.call_args.args[2]
    assert fields == {
        ActionContractsFields.STATUS: "approved",
        ActionContractsFields.VERSION: 2,
        ActionContractsFields.APPROVED_BY: "boss_hq:owner-1",
        ActionContractsFields.APPROVED_AT: 123.5,
    }
    assert ActionContractsFields.NORMALIZED_PAYLOAD not in fields
    assert result.status == "approved"
    assert result.version == 2


def test_repository_patch_failure_raises_visible_persistence_error():
    repository = ActionContractRepository()
    memory = LifecycleRepository()
    contract_id = _propose(ActionGateway(ledger=ExecutionLedger(repository=memory)))

    with patch(
        "core.action_contract_repository.at_get_by_field",
        return_value=memory.records[contract_id],
    ), patch("core.action_contract_repository.airtable_patch", return_value=False):
        with pytest.raises(ActionContractTransitionPersistenceError):
            repository.transition(
                contract_id,
                expected_status="pending",
                expected_version=1,
                new_status="approved",
            )


def test_repository_readback_conflict_is_not_silently_accepted():
    repository = ActionContractRepository()
    memory = LifecycleRepository()
    contract_id = _propose(ActionGateway(ledger=ExecutionLedger(repository=memory)))
    pending_record = memory.records[contract_id]
    conflicting_record = {
        "id": pending_record["id"],
        "fields": dict(pending_record["fields"]),
    }
    conflicting_record["fields"].update({
        ActionContractsFields.STATUS: "rejected",
        ActionContractsFields.VERSION: 2,
    })

    with patch(
        "core.action_contract_repository.at_get_by_field",
        side_effect=[pending_record, conflicting_record],
    ), patch("core.action_contract_repository.airtable_patch", return_value=True):
        with pytest.raises(ActionContractTransitionConflictError, match="read-back conflict"):
            repository.transition(
                contract_id,
                expected_status="pending",
                expected_version=1,
                new_status="approved",
            )
