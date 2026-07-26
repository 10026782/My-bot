"""Focused regression coverage for PR1 single-speaker approval UX."""

import time

from core.action_gateway import (
    ActionContract,
    ActionGateway,
    ExecutionLedger,
    build_approval_lifecycle_result,
)


def _contract(*, status="pending", channel="telegram", suffix="1"):
    return ActionContract(
        contract_id=f"123e4567-e89b-12d3-a456-42661417400{suffix}",
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner",
        tool_name="airtable_add",
        normalized_payload={
            "table": "Leads",
            "fields": {"Name": "נועה", "record_id": "recABCDEFGHIJKLMN"},
        },
        business_action_fingerprint=f"fingerprint-{suffix}",
        origin_channel=channel,
        origin_chat_id="requester-chat",
        requires_approval=True,
        status=status,
        created_at=time.time(),
    )


def test_state_to_message_mapping_and_single_owner():
    pending = build_approval_lifecycle_result(_contract())
    completed = build_approval_lifecycle_result(_contract(status="completed"))
    repeated_completed = build_approval_lifecycle_result(
        _contract(status="completed"), repeated=True,
    )
    rejected = build_approval_lifecycle_result(_contract(status="rejected"))
    repeated_rejected = build_approval_lifecycle_result(
        _contract(status="rejected"), repeated=True,
    )
    missing = build_approval_lifecycle_result(canonical_state="no_contract")
    pending_conflict = build_approval_lifecycle_result(
        _contract(), canonical_state="pending_conflict",
    )

    assert pending.safe_user_message.startswith("יש פעולה שממתינה לאישור:")
    assert completed.safe_user_message.startswith("הפעולה הושלמה:")
    assert repeated_completed.safe_user_message == "הפעולה כבר הושלמה"
    assert rejected.safe_user_message.startswith("הפעולה נדחתה:")
    assert repeated_rejected.safe_user_message == "הפעולה כבר נדחתה"
    assert missing.safe_user_message == "אין פעולה שממתינה לאישור"
    assert "לשלוח מחדש" in pending_conflict.safe_user_message
    assert "לא נשמרה" in pending_conflict.safe_user_message
    assert pending_conflict.should_remove_keyboard is False
    for result in (
        pending, pending_conflict, completed, repeated_completed,
        rejected, repeated_rejected, missing,
    ):
        assert result.reply_owner == "gateway"
        assert result.is_final is True
        assert result.final_response_required is True
        assert result.final_response_count == 1


def test_identifiers_and_tool_names_are_never_user_visible():
    contract = _contract(status="completed")
    result = build_approval_lifecycle_result(
        contract,
        safe_reason=(
            f"airtable_add {contract.contract_id} recABCDEFGHIJKLMN"
        ),
    )
    assert "airtable_add" not in result.safe_user_message
    assert contract.contract_id not in result.safe_user_message
    assert "recABCDEFGHIJKLMN" not in result.safe_user_message


def test_authorization_denial_keeps_pending_contract_actionable_for_owner():
    contract = _contract()
    result = build_approval_lifecycle_result(
        contract, canonical_state="authorization_denied",
    )
    assert result.safe_user_message == "⛔ הפעולה דורשת אישור בעלים."
    assert result.reply_owner == "gateway"
    assert result.final_response_count == 1
    assert result.should_remove_keyboard is False
    assert contract.status == "pending"
    assert contract.tool_name not in result.safe_user_message
    assert contract.contract_id not in result.safe_user_message


def test_telegram_and_whatsapp_share_the_same_semantics():
    telegram = build_approval_lifecycle_result(_contract(channel="telegram"))
    whatsapp = build_approval_lifecycle_result(_contract(channel="whatsapp"))
    assert telegram.canonical_state == whatsapp.canonical_state == "pending"
    assert telegram.safe_user_message == whatsapp.safe_user_message


def test_multiple_pending_is_read_only_and_safe():
    first = _contract(suffix="1")
    second = _contract(suffix="2")
    before = (first.status, second.status)
    result = build_approval_lifecycle_result(contracts=[first, second])
    assert result.canonical_state == "multiple_pending"
    assert (first.status, second.status) == before
    assert "airtable_add" not in result.safe_user_message
    assert first.contract_id not in result.safe_user_message
    assert second.contract_id not in result.safe_user_message


def test_repeated_text_resolution_uses_recent_terminal_contract():
    ledger = ExecutionLedger()
    gateway = ActionGateway(ledger=ledger)
    completed = _contract(status="completed")
    ledger.save(completed)
    assert gateway.route_confirmation_word("boss_hq:owner") == "הפעולה כבר הושלמה"

    rejected = _contract(status="rejected", suffix="2")
    rejected.created_at += 1
    ledger.save(rejected)
    assert gateway.route_cancellation_word("boss_hq:owner") == "הפעולה כבר נדחתה"
