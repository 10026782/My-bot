"""R9: single-contract text confirmation uses the approval renderer only."""

from unittest.mock import Mock

from core.action_gateway import ActionGateway, ActionContract, ExecutionLedger, ApprovalLifecycleResult


def _contract(*, interrupted=False):
    return ActionContract(
        contract_id="r9-contract",
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:user",
        tool_name="airtable_add",
        normalized_payload={"table": "Tasks", "fields": {"name": "בדיקה"}},
        business_action_fingerprint="r9-fingerprint",
        status="pending",
        created_at=0.0,
        origin_channel="telegram",
        origin_chat_id="chat",
        requires_approval=True,
        context_interrupted=interrupted,
    )


def _result(**overrides):
    values = dict(
        canonical_state="completed",
        reply_owner="gateway",
        safe_business_description="יצירת משימה: בדיקה",
        safe_user_message="legacy receipt",
        contract_id="r9-contract",
        is_final=True,
        should_remove_keyboard=True,
        final_response_required=True,
        final_response_count=1,
    )
    values.update(overrides)
    return ApprovalLifecycleResult(**values)


def test_terminal_single_contract_receipt_reuses_approval_renderer():
    gateway = ActionGateway(ledger=ExecutionLedger())
    gateway.approve_with_lifecycle_result = Mock(return_value=_result())
    gateway._render_approval_lifecycle_reply = Mock(return_value="canonical receipt")

    message, terminal = gateway._resolve_single_contract(
        _contract(), "owner", "boss_hq:user",
    )

    assert terminal is True
    assert message == "canonical receipt"
    gateway._render_approval_lifecycle_reply.assert_called_once_with(
        gateway.approve_with_lifecycle_result.return_value,
        "legacy receipt",
    )


def test_reconfirmation_does_not_use_terminal_approval_renderer():
    gateway = ActionGateway(ledger=ExecutionLedger())
    gateway.approve_with_lifecycle_result = Mock()
    gateway._render_approval_lifecycle_reply = Mock()

    message, terminal = gateway._resolve_single_contract(
        _contract(interrupted=True), "owner", "boss_hq:user",
    )

    assert terminal is False
    assert "לאשר אותה" in message
    gateway.approve_with_lifecycle_result.assert_not_called()
    gateway._render_approval_lifecycle_reply.assert_not_called()
