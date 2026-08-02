import time

import pytest

from core.action_gateway import ActionContract, ActionGateway
from core.evidence_projection import build_evidence_result
from core.lifecycle_projection import build_action_lifecycle_result


def _contract(status: str, *, contract_id: str = "c1", created_at: float | None = None) -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id="tenant-a",
        canonical_user_id="user-a",
        tool_name="airtable_add",
        normalized_payload={"table": "Leads", "fields": {"name": "Alice"}},
        business_action_fingerprint="fp",
        origin_channel="telegram",
        origin_chat_id="chat-a",
        requires_approval=True,
        status=status,
        created_at=time.time() if created_at is None else created_at,
    )


@pytest.mark.parametrize(
    ("status", "expected_lifecycle", "expected_approval", "expected_execution"),
    [
        ("pending", "pending", "pending", "not_started"),
        ("approved", "approved", "approved", "not_started"),
        ("executing", "executing", "approved", "in_progress"),
        ("completed", "completed", "approved", "succeeded"),
        ("failed", "failed", "approved", "failed"),
        ("outcome_unknown", "outcome_unknown", "approved", "outcome_unknown"),
        ("rejected", "rejected", "rejected", "not_started"),
    ],
)
def test_build_action_lifecycle_result_maps_statuses(
    status: str, expected_lifecycle: str, expected_approval: str, expected_execution: str
) -> None:
    result = build_action_lifecycle_result(_contract(status))
    assert result.contract_ref == "c1"
    assert result.lifecycle_state == expected_lifecycle
    assert result.approval_state == expected_approval
    assert result.execution_state == expected_execution


def test_build_action_lifecycle_result_marks_expired_pending_contracts() -> None:
    result = build_action_lifecycle_result(_contract("pending", created_at=0.0), now=25 * 3600)
    assert result.lifecycle_state == "expired"
    assert result.error_replay_classification == "expired"


def test_build_evidence_result_requires_verified_evidence_for_success() -> None:
    result = build_evidence_result(
        _contract("completed"),
        provider_result={"ok": True},
        evidence_ref="ev-1",
        verified=True,
    )
    assert result.result == "success"
    assert result.verified is True
    assert result.outcome_unknown is False


def test_build_evidence_result_fails_closed_without_verified_evidence() -> None:
    result = build_evidence_result(
        _contract("completed"),
        provider_result={"ok": True},
        evidence_ref="",
        verified=False,
    )
    assert result.result == "outcome_unknown"
    assert result.verified is False
    assert result.outcome_unknown is True


def test_gateway_status_helpers_return_projections() -> None:
    gateway = ActionGateway()
    gateway._ledger.save(_contract("pending"))

    lifecycle = gateway.approval_status("user-a")
    evidence = gateway.execution_status("user-a")

    assert lifecycle is not None
    assert lifecycle.lifecycle_state == "pending"
    assert evidence is not None
    assert evidence.result == "outcome_unknown"
