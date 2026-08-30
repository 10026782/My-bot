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


def test_multi_contract_confirmation_uses_batch_renderer():
    gateway = ActionGateway(ledger=ExecutionLedger())
    contracts = [_contract(), _contract()]
    contracts[1].contract_id = "r9-contract-2"
    gateway._render_pending_batch_reply = Mock(return_value="batch receipt")

    assert gateway.route_confirmation_word(
        "boss_hq:user", live_contracts=contracts, use_session_bookmark=False,
    ) == "batch receipt"
    gateway._render_pending_batch_reply.assert_called_once()


def test_disambiguation_confirmation_uses_terminal_approval_renderer():
    gateway = ActionGateway(ledger=ExecutionLedger())
    contract = _contract()
    gateway._disambiguation["boss_hq:user"] = [contract]
    gateway.approve_with_lifecycle_result = Mock(return_value=_result())
    gateway._render_approval_lifecycle_reply = Mock(return_value="canonical receipt")

    assert gateway.route_disambiguation(
        "boss_hq:user", "1", approver_role="owner",
    ) == "canonical receipt"
    gateway._render_approval_lifecycle_reply.assert_called_once_with(
        gateway.approve_with_lifecycle_result.return_value,
        "legacy receipt",
    )


def test_combined_confirmation_uses_terminal_approval_renderer():
    gateway = ActionGateway(ledger=ExecutionLedger())
    contract = _contract()
    gateway.find_live_contracts = Mock(return_value=[contract])
    gateway.approve_with_lifecycle_result = Mock(return_value=_result())
    gateway._render_approval_lifecycle_reply = Mock(return_value="canonical receipt")

    assert gateway.route_combined_word(
        "boss_hq:user", "כן 1", approver_role="owner",
    ) == "canonical receipt"
    gateway._render_approval_lifecycle_reply.assert_called_once_with(
        gateway.approve_with_lifecycle_result.return_value,
        "legacy receipt",
    )
