"""Regression tests for C02-C04 audit Finding #3.

The canonical Lead writer must fail closed if ActionGateway proposal cannot
be completed. A direct Airtable mutation is not a valid fallback.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import core.lead_service as lead_service


class _Identity:
    tenant_id = "boss_hq"
    user_id = "eliyahu"
    memory_key = "boss_hq/eliyahu@owner"


class _Ledger:
    _repository = None

    def update_status(self, contract_id, status):
        return True

    def find_by_id(self, contract_id):
        return None


def _run(monkeypatch, gateway_result=None, gateway_error=None):
    gateway = Mock()
    gateway._ledger = _Ledger()
    if gateway_error is not None:
        gateway.propose_action.side_effect = gateway_error
    else:
        gateway.propose_action.return_value = gateway_result

    writer = Mock(return_value={"id": "recLEAD001"})
    monkeypatch.setattr("feature_flags.is_enabled", lambda name: False)
    monkeypatch.setattr("tma_api._resolve_profile_record_id", lambda user_id: "recOWNER123")
    monkeypatch.setattr(lead_service, "find_existing_lead", lambda name, phone: None)
    monkeypatch.setattr("core.action_gateway.action_gateway", gateway)
    monkeypatch.setattr("tools.airtable_gateway.airtable_create", writer)
    monkeypatch.setattr(lead_service, "_run_post_write_enrichment", lambda *args: None)
    result = lead_service.create_lead(
        _Identity(),
        lead_service.LeadPayload(name="Dana", phone="0501234567", domain="general"),
        source_module="test",
    )
    return result, gateway, writer


def test_gateway_success_uses_canonical_mutation_path(monkeypatch):
    result, gateway, writer = _run(
        monkeypatch,
        gateway_result=SimpleNamespace(ok=True, contract_id="contract-1", reason=""),
    )

    assert result.ok is True
    assert result.action == "created"
    gateway.propose_action.assert_called_once()
    writer.assert_called_once()


def test_gateway_exception_never_calls_direct_writer(monkeypatch):
    result, gateway, writer = _run(monkeypatch, gateway_error=RuntimeError("gateway unavailable"))

    assert result.ok is False
    assert result.action == "gateway_failed"
    gateway.propose_action.assert_called_once()
    writer.assert_not_called()


def test_gateway_failure_is_explicit_and_truthful(monkeypatch):
    result, _, writer = _run(monkeypatch, gateway_error=RuntimeError("gateway unavailable"))

    assert result.ok is False
    assert result.reason == "gateway_proposal_failed"
    assert result.evidence == {
        "gateway_proposal": "failed",
        "mutation_executed": False,
    }
    writer.assert_not_called()


def test_retry_after_gateway_failure_does_not_mutate_failed_attempt(monkeypatch):
    first, first_gateway, first_writer = _run(
        monkeypatch, gateway_error=RuntimeError("gateway unavailable")
    )
    second, second_gateway, second_writer = _run(
        monkeypatch, gateway_error=RuntimeError("gateway unavailable")
    )

    assert first.ok is False and second.ok is False
    assert first_writer.call_count == 0 and second_writer.call_count == 0
    first_gateway.propose_action.assert_called_once()
    second_gateway.propose_action.assert_called_once()


def test_existing_success_behavior_remains_unchanged(monkeypatch):
    result, _, writer = _run(
        monkeypatch,
        gateway_result=SimpleNamespace(ok=True, contract_id="contract-1", reason=""),
    )

    assert result.ok is True
    assert result.record_id == "recLEAD001"
    assert result.reason == ""
    writer.assert_called_once()
