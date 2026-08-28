"""Focused F52-G4-S2 checks for the Interaction Log system writer."""

from types import SimpleNamespace
from unittest.mock import patch

import interaction_engine
from core.action_gateway import (
    APPROVAL_POLICY_APPROVAL,
    APPROVAL_POLICY_SELF_CONFIRM,
    classify_approval_policy,
)
from identity import Role


def _inputs():
    interaction = interaction_engine.InteractionSchema(
        source_channel="calendar", raw_id="event-1", title="Supplier meeting",
        participants=["supplier"], timestamp="2026-08-28T10:00:00+00:00", domain="import",
    )
    analysis = interaction_engine.InteractionAnalysis(
        summary="Discussed delivery", next_steps="Send quote", sentiment="neutral",
    )
    return interaction, analysis


class _FakeGateway:
    def __init__(self, *, status="completed", record_id="rec-interaction"):
        self.status = status
        self.record_id = record_id
        self.proposal = None
        self.approval = None
        self._ledger = self

    def propose_action(self, **kwargs):
        self.proposal = kwargs
        return SimpleNamespace(ok=True, contract_id="contract-1", reason="registered")

    def approve(self, *args, **kwargs):
        self.approval = (args, kwargs)
        return "misleading display text"

    def find_by_id(self, _contract_id):
        return SimpleNamespace(
            status=self.status,
            agent_observations=(
                [{"kind": "execution_fact", "record_id": self.record_id}]
                if self.record_id else []
            ),
        )


def test_no_direct_provider_and_gateway_path():
    interaction, analysis = _inputs()
    gateway = _FakeGateway()
    with patch("core.action_gateway.action_gateway", gateway):
        assert interaction_engine.save_to_business_memory(interaction, analysis) == "rec-interaction"
    assert gateway.proposal["tool_name"] == "airtable_add"
    assert gateway.proposal["tool_inputs"]["table"] == "Interaction Log"


def test_explicit_system_identity_and_policy():
    interaction, analysis = _inputs()
    gateway = _FakeGateway()
    with patch("core.action_gateway.action_gateway", gateway):
        interaction_engine.save_to_business_memory(interaction, analysis)
    identity = gateway.proposal["identity"]
    assert identity.user_id == "interaction_engine_scheduler"
    assert identity.role == Role.MANAGER
    assert identity.channel == "scheduler"
    assert gateway.proposal["trusted_source"] == "interaction_engine_scheduler"
    assert gateway.proposal["requires_approval"] is True
    assert classify_approval_policy(
        "airtable_add", gateway.proposal["tool_inputs"], gateway.proposal["trusted_source"],
    ) == APPROVAL_POLICY_SELF_CONFIRM


def test_invalid_policy_cannot_be_self_confirmed():
    assert classify_approval_policy(
        "airtable_add", {"table": "Interaction Log", "fields": {"unexpected": "x"}},
        "interaction_engine_scheduler",
    ) == APPROVAL_POLICY_APPROVAL


def test_missing_structured_execution_fails_closed():
    interaction, analysis = _inputs()
    gateway = _FakeGateway(status="failed", record_id="")
    with patch("core.action_gateway.action_gateway", gateway):
        assert interaction_engine.save_to_business_memory(interaction, analysis) == ""


def test_structured_result_controls_success_not_display_text():
    interaction, analysis = _inputs()
    gateway = _FakeGateway(status="completed", record_id="rec-structured")
    with patch("core.action_gateway.action_gateway", gateway):
        assert interaction_engine.save_to_business_memory(interaction, analysis) == "rec-structured"
    assert gateway.approval is not None


def test_payload_preserved():
    interaction, analysis = _inputs()
    gateway = _FakeGateway()
    with patch("core.action_gateway.action_gateway", gateway):
        interaction_engine.save_to_business_memory(interaction, analysis)
    fields = gateway.proposal["tool_inputs"]["fields"]
    assert fields == {
        "Interaction Subject": "Supplier meeting",
        "Details": "Discussed delivery",
        "Interaction Type": "calendar",
        "Interaction Date": "2026-08-28T10:00:00+00:00",
        "Participants": "supplier",
        "Key Insights": "Send quote",
        "Follow-up Actions": "",
    }


def test_existing_scan_contract_remains_unchanged():
    assert interaction_engine.save_to_business_memory is interaction_engine.save_to_interaction_log
    assert interaction_engine.run_interaction_scan.__name__ == "run_interaction_scan"
