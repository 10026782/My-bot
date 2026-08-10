"""TC9 production boundary tests for ActionGateway -> MessageContract."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from core.action_gateway import ActionFact, ActionGateway, GatewayReply
from core.message_contract import MessageContract, MessageState


def _fact(outcome: str, **metadata) -> ActionFact:
    return ActionFact(
        tool_name="airtable_add",
        contract_id="contract-tc9",
        outcome=outcome,
        record_id="rec-tc9" if outcome in {"executed", "completed"} else None,
        error_code="provider_failed" if outcome == "failed" else None,
        raw_tool_response={},
        **metadata,
    )


def _gateway() -> ActionGateway:
    gateway = ActionGateway()
    gateway._ledger.find_by_id = lambda _contract_id: None
    return gateway


def _with_formatter(state: str):
    return patch.dict(os.environ, {"FEATURE_UNIFIED_STATUS_FORMATTER": state}, clear=False)


def test_pending_failed_unknown_and_verified_execution_cross_boundary():
    cases = (
        (_fact("pending"), MessageState.APPROVAL_PENDING),
        (_fact("failed", evidence_status="failure", execution_verified=False), MessageState.FAILURE),
        (_fact("outcome_unknown", evidence_status="outcome_unknown", execution_verified=False), MessageState.OUTCOME_UNKNOWN),
        (
            _fact(
                "executed",
                evidence_status="verified_write_success",
                evidence_ref="evidence-tc9",
                execution_verified=True,
            ),
            MessageState.SUCCESS,
        ),
    )

    with _with_formatter("on"):
        for fact, expected_state in cases:
            reply = _gateway().compose_status_reply(fact)
            assert isinstance(reply, GatewayReply)
            assert isinstance(reply.contract, MessageContract)
            assert reply.contract.state is expected_state
            assert reply.contract.evidence_status == fact.evidence_status
            assert reply.contract.evidence_ref == fact.evidence_ref
            assert reply.contract.execution_verified == fact.execution_verified


def test_existing_turn_id_is_propagated_and_missing_one_is_not_fabricated():
    with _with_formatter("on"):
        with_turn = _gateway().compose_status_reply(
            _fact(
                "executed",
                evidence_status="verified_write_success",
                evidence_ref="evidence-tc9",
                execution_verified=True,
                turn_id="turn-existing-1",
            )
        )
        without_turn = _gateway().compose_status_reply(
            _fact(
                "executed",
                evidence_status="verified_write_success",
                evidence_ref="evidence-tc9",
                execution_verified=True,
            )
        )

    assert with_turn.contract.turn_id == "turn-existing-1"
    assert without_turn.contract.turn_id is None


def test_serialization_round_trip_and_one_formatter_boundary_call():
    fact = _fact("pending")
    gateway = _gateway()
    with _with_formatter("on"), patch(
        "core.agent_message_formatter.format_agent_message_with_meta",
        wraps=__import__("core.agent_message_formatter", fromlist=["format_agent_message_with_meta"]).format_agent_message_with_meta,
    ) as formatter:
        reply = gateway.compose_status_reply(fact)

    restored = MessageContract.from_dict(json.loads(json.dumps(reply.contract.to_dict())))
    assert restored == reply.contract
    assert formatter.call_count == 1
    assert isinstance(reply.text, str) and reply.text


def test_unverified_completed_keeps_legacy_text_fallback_but_retains_contract():
    with _with_formatter("on"):
        reply = _gateway().compose_status_reply(_fact("executed"))

    assert isinstance(reply.contract, MessageContract)
    assert reply.contract.state is MessageState.OUTCOME_UNKNOWN
    assert "הפעולה הושלמה" in reply.text
