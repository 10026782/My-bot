"""Phase 4B-1A: durable new proposals and proposal-recovery lookups.

``agent_observations`` remain intentionally non-durable. Lifecycle durability
is exercised separately by the Phase 4B-1B suite.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.action_contract_repository import _contract_to_fields, _record_to_contract
from core.action_gateway import (
    ActionContract,
    ActionGateway,
    ExecutionLedger,
    _build_action_contract_repository,
)


class MemoryRepository:
    """Repository-shaped durable store that re-hydrates on every read."""

    def __init__(self, save_result=True, save_exception: Exception | None = None):
        self.save_result = save_result
        self.save_exception = save_exception
        self.save_calls = 0
        self.records: dict[str, dict] = {}

    def save(self, contract):
        self.save_calls += 1
        if self.save_exception:
            raise self.save_exception
        if self.save_result is True:
            self.records[contract.contract_id] = {
                "id": f"rec-{contract.contract_id}",
                "fields": _contract_to_fields(contract),
            }
        return self.save_result

    def get(self, contract_id):
        record = self.records.get(contract_id)
        return _record_to_contract(record) if record else None

    def find_pending_by_canonical_user(self, canonical_user_id):
        return [
            _record_to_contract(record)
            for record in self.records.values()
            if record["fields"].get("canonical_user_id") == canonical_user_id
            and record["fields"].get("status") == "pending"
        ]

    def find_by_business_fingerprint(self, fingerprint):
        for record in self.records.values():
            if record["fields"].get("business_action_fingerprint") == fingerprint:
                return _record_to_contract(record)
        return None

    def transition(
        self, contract_id, *, expected_status, expected_version, new_status, updates=None,
    ):
        contract = self.get(contract_id)
        if contract is None:
            raise RuntimeError("contract missing")
        if contract.status != expected_status or contract.version != expected_version:
            raise RuntimeError("stale lifecycle transition")
        contract.status = new_status
        contract.version += 1
        for key, value in (updates or {}).items():
            setattr(contract, key, value)
        self.records[contract_id]["fields"] = _contract_to_fields(contract)
        return self.get(contract_id)


def _identity():
    return SimpleNamespace(
        role="owner",
        user_id="owner-1",
        display_name="Owner One",
        domain_id="real_estate",
        external_id="tg-100",
        allowed_domains=["real_estate", "finance"],
    )


def _propose(gateway: ActionGateway):
    return gateway.propose_action(
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner-1",
        tool_name="airtable_add",
        tool_inputs={
            "table": "Leads",
            "provider_metadata": {"provider": "airtable", "base": "staging"},
            "fields": {"Name": "Durable Lead"},
        },
        origin_channel="telegram",
        origin_chat_id="tg-100",
        requires_approval=True,
        identity=_identity(),
        trusted_source="lead_capture",
    )


def test_flag_off_builds_ram_only_and_makes_zero_repository_calls():
    with patch("feature_flags.is_enabled", return_value=False), \
         patch("core.action_contract_repository.ActionContractRepository") as repo_cls:
        assert _build_action_contract_repository() is None
        repo_cls.assert_not_called()

    ledger = ExecutionLedger()
    result = _propose(ActionGateway(ledger=ledger))
    assert result.ok is True
    assert ledger._repository is None
    assert result.contract_id in ledger._store


def test_flag_on_constructs_one_repository():
    repository = MagicMock()
    with patch("feature_flags.is_enabled", return_value=True), \
         patch("core.action_contract_repository.ActionContractRepository", return_value=repository) as repo_cls:
        assert _build_action_contract_repository() is repository
        repo_cls.assert_called_once_with()


def test_successful_durable_save_happens_before_ok_result():
    repo = MemoryRepository()
    ledger = ExecutionLedger(repository=repo)
    result = _propose(ActionGateway(ledger=ledger))

    assert result.ok is True
    assert repo.save_calls == 1
    assert result.contract_id in repo.records
    assert result.contract_id in ledger._store


def test_status_update_is_durable_without_reusing_proposal_save():
    repo = MemoryRepository()
    ledger = ExecutionLedger(repository=repo)
    result = _propose(ActionGateway(ledger=ledger))
    assert repo.save_calls == 1

    ledger.update_status(result.contract_id, "approved")

    assert repo.save_calls == 1
    assert ledger.find_by_id(result.contract_id).status == "approved"
    assert repo.get(result.contract_id).status == "approved"


def test_repository_false_produces_no_actionable_proposal_or_ram_contract():
    repo = MemoryRepository(save_result=False)
    ledger = ExecutionLedger(repository=repo)
    result = _propose(ActionGateway(ledger=ledger))

    assert result.ok is False
    assert result.contract_id is None
    assert result.failure_code == "persistence_failed"
    assert ledger._store == {}
    assert ledger._by_fingerprint == {}


def test_repository_exception_produces_no_actionable_proposal_or_ram_contract():
    repo = MemoryRepository(save_exception=RuntimeError("store unavailable"))
    ledger = ExecutionLedger(repository=repo)
    result = _propose(ActionGateway(ledger=ledger))

    assert result.ok is False
    assert result.contract_id is None
    assert result.failure_code == "persistence_failed"
    assert ledger._store == {}
    assert ledger._by_fingerprint == {}


def test_shadow_gated_caller_receives_persistence_failure_instead_of_preview():
    repo = MemoryRepository(save_result=False)
    gateway = ActionGateway(ledger=ExecutionLedger(repository=repo))
    with patch("feature_flags.is_enabled", return_value=False):
        message = gateway.propose_gated(
            tenant_id="boss_hq",
            canonical_user_id="boss_hq:owner-1",
            tool_name="send_followup",
            tool_inputs={"draft": "hello"},
            origin_channel="telegram",
            origin_chat_id="tg-100",
            identity=_identity(),
        )
    assert message
    assert "לא הועברה לאישור" in message


def test_find_by_id_restores_full_frozen_contract_after_restart():
    repo = MemoryRepository()
    first = ExecutionLedger(repository=repo)
    proposed = _propose(ActionGateway(ledger=first))
    original = first.find_by_id(proposed.contract_id)
    original.context_interrupted = True
    original.reconfirmation_required = True
    original.context_integrity_unknown = True
    original.version = 7
    original.agent_observations.append({"kind": "non_durable_signal"})
    # Re-save only to build a full frozen-field fixture. Production status/
    # context write-through is deliberately not added by this PR.
    assert repo.save(original) is True

    restarted = ExecutionLedger(repository=repo)
    recovered = restarted.find_by_id(proposed.contract_id)

    assert recovered.contract_id == original.contract_id
    assert recovered.tool_name == original.tool_name
    assert recovered.normalized_payload == original.normalized_payload
    assert recovered.normalized_payload["table"] == "Leads"
    assert recovered.normalized_payload["provider_metadata"]["provider"] == "airtable"
    assert recovered.canonical_user_id == original.canonical_user_id
    assert recovered.actor_role == original.actor_role
    assert recovered.actor_user_id == original.actor_user_id
    assert recovered.actor_external_id == original.actor_external_id
    assert recovered.actor_allowed_domains == original.actor_allowed_domains
    assert recovered.business_action_fingerprint == original.business_action_fingerprint
    assert recovered.idempotency_key == original.idempotency_key
    assert recovered.approval_policy == original.approval_policy
    assert recovered.trusted_source == original.trusted_source
    assert recovered.context_interrupted is True
    assert recovered.reconfirmation_required is True
    assert recovered.context_integrity_unknown is True
    assert recovered.version == 7
    assert recovered.created_at == original.created_at
    assert recovered.status == original.status
    assert recovered.agent_observations == []  # explicitly non-durable in 4B-1A
    assert restarted._store[recovered.contract_id] is recovered
    assert restarted._by_fingerprint[recovered.business_action_fingerprint] == recovered.contract_id


def test_pending_by_user_recovers_after_restart_and_populates_both_indexes():
    repo = MemoryRepository()
    first = ExecutionLedger(repository=repo)
    proposed = _propose(ActionGateway(ledger=first))

    restarted = ExecutionLedger(repository=repo)
    pending = restarted.find_live_by_user("boss_hq:owner-1")

    assert [c.contract_id for c in pending] == [proposed.contract_id]
    assert restarted._store[proposed.contract_id] is pending[0]
    assert restarted._by_fingerprint[pending[0].business_action_fingerprint] == proposed.contract_id


def test_pending_recovery_does_not_resurrect_newer_local_state():
    repo = MemoryRepository()
    ledger = ExecutionLedger(repository=repo)
    proposed = _propose(ActionGateway(ledger=ledger))
    ledger.update_status(proposed.contract_id, "approved")

    assert ledger.find_live_by_user("boss_hq:owner-1") == []
    assert ledger.find_by_id(proposed.contract_id).status == "approved"


def test_fingerprint_duplicate_is_detected_after_restart_by_second_ledger():
    repo = MemoryRepository()
    first = ExecutionLedger(repository=repo)
    original = _propose(ActionGateway(ledger=first))
    fingerprint = first._store[original.contract_id].business_action_fingerprint

    second = ExecutionLedger(repository=repo)
    recovered = second.find_by_fingerprint(fingerprint)
    duplicate = _propose(ActionGateway(ledger=second))

    assert recovered.contract_id == original.contract_id
    assert second._store[original.contract_id] is recovered
    assert second._by_fingerprint[fingerprint] == original.contract_id
    assert duplicate.ok is False
    assert duplicate.contract_id == original.contract_id
    assert repo.save_calls == 1


if __name__ == "__main__":
    tests = [
        value for name, value in list(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"Phase 4B-1A durable proposal tests: {len(tests)} passed")
