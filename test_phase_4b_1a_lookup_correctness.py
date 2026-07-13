"""Phase 4B-1A P1: fail-closed durable proposal lookup regressions."""

from __future__ import annotations

import logging
import os
import re
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("AIRTABLE_API_KEY", "patPhase4B1ALookupTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPhase4B1ALookupTest")

from airtable_schema import ActionContractsFields, Tables
from core.action_contract_repository import (
    CONTRACT_PENDING_TTL_SECONDS,
    ActionContractLookupError,
    ActionContractRepository,
)
from core.action_gateway import ActionGateway, ExecutionLedger
from tools.airtable_gateway import AirtableLookupError, at_upsert


class FakeAirtable:
    """HTTP-level durable store shared by independent repository instances."""

    def __init__(self):
        self.records: dict[str, dict] = {}
        self.next_id = 1
        self.get_status = 200
        self.network_error: Exception | None = None
        self.post_calls = 0
        self.patch_calls = 0

    @staticmethod
    def _response(status: int, body: dict):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = body
        response.text = str(body)
        return response

    def get(self, url, headers=None, params=None, timeout=None):
        if self.network_error:
            raise self.network_error
        if self.get_status != 200:
            return self._response(self.get_status, {"error": "unavailable"})
        formula = (params or {}).get("filterByFormula", "")
        conditions = re.findall(r"\{([^}]+)\}='([^']*)'", formula)
        matches = [
            record for record in self.records.values()
            if all(str(record["fields"].get(field, "")) == value for field, value in conditions)
        ]
        maximum = (params or {}).get("maxRecords", len(matches))
        return self._response(200, {"records": matches[:maximum]})

    def post(self, url, headers=None, json=None, timeout=None):
        self.post_calls += 1
        record_id = f"rec{self.next_id:014d}"
        self.next_id += 1
        record = {"id": record_id, "fields": dict(json["fields"])}
        self.records[record_id] = record
        return self._response(201, record)

    def patch(self, url, headers=None, json=None, timeout=None):
        self.patch_calls += 1
        record_id = url.rsplit("/", 1)[-1]
        self.records[record_id]["fields"].update(json["fields"])
        return self._response(200, self.records[record_id])

    def patches(self):
        return (
            patch("tools.airtable_gateway.httpx.get", side_effect=self.get),
            patch("tools.airtable_gateway.httpx.post", side_effect=self.post),
            patch("tools.airtable_gateway.httpx.patch", side_effect=self.patch),
        )


def _identity():
    return SimpleNamespace(
        role="owner", user_id="owner-1", display_name="Owner",
        domain_id="real_estate", external_id="tg-100",
        allowed_domains=["real_estate"],
    )


def _propose(gateway: ActionGateway):
    return gateway.propose_action(
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner-1",
        tool_name="airtable_add",
        tool_inputs={"table": "Leads", "fields": {"Name": "Same lead"}},
        origin_channel="telegram",
        origin_chat_id="tg-100",
        requires_approval=True,
        identity=_identity(),
        trusted_source="lead_capture",
    )


def _with_store(store: FakeAirtable):
    get_patch, post_patch, patch_patch = store.patches()
    return get_patch, post_patch, patch_patch


def test_clean_not_found_creates_exactly_one_and_second_instance_reuses_original():
    store = FakeAirtable()
    p1, p2, p3 = _with_store(store)
    with p1, p2, p3:
        first_ledger = ExecutionLedger(repository=ActionContractRepository())
        original = _propose(ActionGateway(ledger=first_ledger))

        second_ledger = ExecutionLedger(repository=ActionContractRepository())
        duplicate = _propose(ActionGateway(ledger=second_ledger))

    assert original.ok is True
    assert duplicate.ok is False
    assert duplicate.contract_id == original.contract_id
    assert store.post_calls == 1
    assert len(store.records) == 1
    recovered = second_ledger._store[original.contract_id]
    fingerprint = recovered.business_action_fingerprint
    assert second_ledger._by_fingerprint[fingerprint] == original.contract_id


def test_lookup_network_error_fails_before_identity_and_creates_nothing():
    store = FakeAirtable()
    store.network_error = RuntimeError("network down")
    ledger = ExecutionLedger(repository=ActionContractRepository())
    p1, p2, p3 = _with_store(store)
    with p1, p2, p3, patch("core.action_gateway.uuid.uuid4") as uuid4:
        result = _propose(ActionGateway(ledger=ledger))

    assert result.ok is False
    assert result.failure_code == "persistence_lookup_failed"
    assert result.contract_id is None
    uuid4.assert_not_called()
    assert ledger._store == {}
    assert ledger._by_fingerprint == {}
    assert store.post_calls == 0
    assert store.records == {}


def test_lookup_429_and_500_each_create_zero_contracts():
    for status in (429, 500):
        store = FakeAirtable()
        store.get_status = status
        ledger = ExecutionLedger(repository=ActionContractRepository())
        p1, p2, p3 = _with_store(store)
        with p1, p2, p3:
            result = _propose(ActionGateway(ledger=ledger))
        assert result.failure_code == "persistence_lookup_failed"
        assert store.post_calls == 0
        assert ledger._store == {}
        assert ledger._by_fingerprint == {}


def test_failed_fingerprint_lookup_cannot_produce_two_distinct_contract_ids():
    store = FakeAirtable()
    store.get_status = 500
    results = []
    p1, p2, p3 = _with_store(store)
    with p1, p2, p3:
        for _ in range(2):
            ledger = ExecutionLedger(repository=ActionContractRepository())
            results.append(_propose(ActionGateway(ledger=ledger)))

    assert [result.failure_code for result in results] == [
        "persistence_lookup_failed", "persistence_lookup_failed",
    ]
    assert {result.contract_id for result in results} == {None}
    assert store.post_calls == 0


def test_strict_upsert_lookup_failure_performs_zero_create_calls():
    with patch(
        "tools.airtable_gateway.httpx.get",
        return_value=FakeAirtable._response(500, {"error": "server"}),
    ), patch("tools.airtable_gateway.airtable_create") as create:
        result = at_upsert(
            Tables.ACTION_CONTRACTS,
            {ActionContractsFields.CONTRACT_ID: "contract-1"},
            ActionContractsFields.CONTRACT_ID,
            fail_closed_on_lookup_error=True,
        )
    assert result is False
    create.assert_not_called()


def test_pending_within_ttl_is_reused_but_expired_creates_replacement():
    store = FakeAirtable()
    p1, p2, p3 = _with_store(store)
    with p1, p2, p3:
        first = _propose(ActionGateway(ledger=ExecutionLedger(repository=ActionContractRepository())))
        within_ttl = _propose(ActionGateway(ledger=ExecutionLedger(repository=ActionContractRepository())))
        only_record = next(iter(store.records.values()))
        only_record["fields"][ActionContractsFields.CREATED_AT] = (
            time.time() - CONTRACT_PENDING_TTL_SECONDS - 1
        )
        expired = _propose(ActionGateway(ledger=ExecutionLedger(repository=ActionContractRepository())))

    assert within_ttl.contract_id == first.contract_id
    assert expired.ok is True
    assert expired.contract_id != first.contract_id
    assert store.post_calls == 2


def test_get_and_pending_lookup_distinguish_outage_from_clean_empty():
    repository = ActionContractRepository()
    with patch("core.action_contract_repository.at_get_by_field", return_value=None):
        assert repository.get("missing-contract") is None
    with patch("core.action_contract_repository.at_list_by_formula", return_value=[]):
        assert repository.find_pending_by_canonical_user("user-with-no-pending") == []

    with patch(
        "core.action_contract_repository.at_get_by_field",
        side_effect=AirtableLookupError("down"),
    ):
        try:
            repository.get("contract-1")
        except ActionContractLookupError:
            pass
        else:
            raise AssertionError("get() invented a clean not-found result")

    with patch(
        "core.action_contract_repository.at_list_by_formula",
        side_effect=AirtableLookupError("down"),
    ):
        try:
            repository.find_pending_by_canonical_user("user-1")
        except ActionContractLookupError:
            pass
        else:
            raise AssertionError("pending lookup invented an empty result")

    failing_repository = MagicMock()
    failing_repository.find_pending_by_canonical_user.side_effect = ActionContractLookupError("down")
    try:
        ExecutionLedger(repository=failing_repository).find_live_by_user("user-1")
    except ActionContractLookupError:
        pass
    else:
        raise AssertionError("ExecutionLedger swallowed pending lookup failure")


def test_shadow_propose_gated_and_app_queue_block_lookup_failure():
    repository = MagicMock()
    repository.find_by_business_fingerprint.side_effect = ActionContractLookupError("down")
    gateway = ActionGateway(ledger=ExecutionLedger(repository=repository))
    with patch("feature_flags.is_enabled", return_value=False):
        message = gateway.propose_gated(
            tenant_id="boss_hq", canonical_user_id="boss_hq:owner-1",
            tool_name="send_followup", tool_inputs={"draft": "hello"},
            origin_channel="telegram", origin_chat_id="tg-100",
            identity=_identity(),
        )
    assert message and "לא הועברה לאישור" in message

    app_source = open("app.py", encoding="utf-8").read()
    assert 'in {"persistence_failed", "persistence_lookup_failed"}' in app_source


def test_actioncontracts_at_upsert_callers_explicitly_choose_strict_mode():
    repository = ActionContractRepository()
    contract = MagicMock()
    contract.contract_id = "contract-audit"
    contract.tenant_id = "boss_hq"
    contract.canonical_user_id = "owner-1"
    contract.tool_name = "airtable_add"
    contract.normalized_payload = {"table": "Leads"}
    contract.business_action_fingerprint = "fp-audit"
    contract.origin_channel = "telegram"
    contract.origin_chat_id = "tg-100"
    contract.requires_approval = True
    contract.status = "pending"
    contract.created_at = time.time()
    contract.approved_by = None
    contract.approved_at = None
    contract.version = 1
    contract.actor_role = "owner"
    contract.actor_user_id = "owner-1"
    contract.actor_display_name = "Owner"
    contract.actor_domain_id = "general"
    contract.actor_external_id = "tg-100"
    contract.actor_allowed_domains = []
    contract.approval_policy = "approval"
    contract.trusted_source = "agent"
    contract.context_interrupted = False
    contract.reconfirmation_required = False
    contract.context_integrity_unknown = False
    contract.idempotency_key = "idem-audit"

    with patch("core.action_contract_repository.at_upsert", return_value=True) as upsert:
        assert repository.save(contract) is True
    assert upsert.call_args.kwargs["fail_closed_on_lookup_error"] is True

    gateway_source = open("core/action_gateway.py", encoding="utf-8").read()
    assert "fail_closed_on_lookup_error=True" in gateway_source


def test_live_lookup_diagnostic_contains_only_safe_lookup_metadata(caplog):
    repository = MagicMock()
    repository.find_by_business_fingerprint.return_value = None
    repository.save.return_value = True
    gateway = ActionGateway(ledger=ExecutionLedger(repository=repository))

    with patch("feature_flags.is_enabled", return_value=True), caplog.at_level(logging.WARNING):
        result = _propose(gateway)

    assert result.ok is True
    diagnostics = [
        record.getMessage() for record in caplog.records
        if record.getMessage().startswith("[ActionContractLookupDiagnostic]")
    ]
    assert len(diagnostics) == 1
    message = diagnostics[0]
    for field in (
        "fingerprint=", "process_id=", "persistence_flag=",
        "repository_type=", "lookup_outcome=", "returned_contract_id=",
        "new_contract_id_generated=",
    ):
        assert field in message
    assert "lookup_outcome=clean_not_found" in message
    assert "new_contract_id_generated=True" in message
    assert "normalized_payload" not in message
    assert "Same lead" not in message
    assert "boss_hq:owner-1" not in message
