"""Focused PR B tests for the pure ApprovalLifecycleResult adapter."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

import pytest

from core.action_gateway import ApprovalLifecycleResult
import core.approval_lifecycle_message_adapter as adapter_module
from core.approval_lifecycle_message_adapter import (
    ADAPTER_SOURCE_MODULE,
    from_approval_lifecycle_result,
)
from core.message_contract import (
    InteractionType,
    MessageContract,
    MessageInteraction,
    MessageContractValidationError,
    MessageState,
    TurnContextSource,
)


def _result(**overrides) -> ApprovalLifecycleResult:
    values = {
        "canonical_state": "pending",
        "reply_owner": "gateway",
        "safe_business_description": "יצירת משימה: מעקב ספק",
        "safe_user_message": "יש משימה שממתינה לאישור: מעקב ספק",
        "contract_id": "123e4567-e89b-12d3-a456-426614174000",
        "is_final": True,
        "should_remove_keyboard": False,
        "final_response_required": True,
        "final_response_count": 1,
        "execution_verified": None,
        "evidence_status": None,
        "evidence_ref": None,
    }
    values.update(overrides)
    return ApprovalLifecycleResult(**values)


@pytest.mark.parametrize(
    ("canonical_state", "repeated", "expected"),
    [
        ("pending", False, MessageState.APPROVAL_PENDING),
        ("pending", True, MessageState.APPROVAL_PENDING),
        ("pending_conflict", False, MessageState.APPROVAL_PENDING),
        ("authorization_denied", False, MessageState.APPROVAL_PENDING),
        ("multiple_pending", False, MessageState.APPROVAL_PENDING_BATCH),
        ("approved_processing", False, MessageState.APPROVED_PROCESSING),
        ("completed", False, MessageState.OUTCOME_UNKNOWN),
        ("completed", True, MessageState.ALREADY_COMPLETED),
        ("rejected", False, MessageState.CANCELLED),
        ("rejected", True, MessageState.ALREADY_CANCELLED),
        ("failed", False, MessageState.FAILURE),
        ("outcome_unknown", False, MessageState.OUTCOME_UNKNOWN),
        ("no_contract", False, MessageState.NO_PENDING_ACTION),
    ],
)
def test_complete_canonical_state_mapping(canonical_state, repeated, expected):
    contract = from_approval_lifecycle_result(
        _result(canonical_state=canonical_state), repeated=repeated
    )
    assert contract.state is expected


def test_completed_without_evidence_never_claims_success():
    contract = from_approval_lifecycle_result(_result(canonical_state="completed"))
    assert contract.state is MessageState.OUTCOME_UNKNOWN
    assert contract.evidence_status is None
    assert contract.evidence_ref is None
    assert contract.execution_verified is None


def test_completed_with_verified_evidence_uses_existing_success_semantic():
    contract = from_approval_lifecycle_result(_result(
        canonical_state="completed",
        execution_verified=True,
        evidence_status="verified_write_success",
        evidence_ref="rec_verified",
    ))
    assert contract.state is MessageState.SUCCESS
    assert contract.execution_verified is True
    assert contract.evidence_status == "verified_write_success"
    assert contract.evidence_ref == "rec_verified"


@pytest.mark.parametrize(
    "evidence",
    [
        {"execution_verified": False, "evidence_status": "verified_write_success", "evidence_ref": "rec"},
        {"execution_verified": True, "evidence_status": "verified_write_success", "evidence_ref": None},
        {"execution_verified": True, "evidence_status": "outcome_unknown", "evidence_ref": "rec"},
    ],
)
def test_completed_without_matching_verified_evidence_stays_unknown(evidence):
    contract = from_approval_lifecycle_result(_result(
        canonical_state="completed", **evidence,
    ))
    assert contract.state is MessageState.OUTCOME_UNKNOWN


def test_repeated_is_explicit_and_never_inferred_from_wording():
    ordinary = _result(canonical_state="completed", safe_user_message="הפעולה הושלמה")
    replay_wording = replace(ordinary, safe_user_message="הפעולה כבר הושלמה")

    assert from_approval_lifecycle_result(ordinary) == from_approval_lifecycle_result(
        replay_wording
    )
    assert from_approval_lifecycle_result(replay_wording).state is MessageState.OUTCOME_UNKNOWN
    assert (
        from_approval_lifecycle_result(ordinary, repeated=True).state
        is MessageState.ALREADY_COMPLETED
    )


def test_invalid_state_and_non_boolean_repeated_are_rejected():
    with pytest.raises(MessageContractValidationError, match="unsupported ApprovalLifecycleResult"):
        from_approval_lifecycle_result(_result(canonical_state="invented"))
    with pytest.raises(MessageContractValidationError, match="non-empty string"):
        from_approval_lifecycle_result(_result(canonical_state=""))
    with pytest.raises(MessageContractValidationError, match="repeated must be bool"):
        from_approval_lifecycle_result(_result(), repeated=1)


def test_safe_description_is_the_only_copied_user_detail():
    source = _result(
        safe_business_description="יצירת משימה: מעקב ספק",
        safe_user_message="wording that must not enter the envelope",
        contract_id="contract-id-that-must-not-enter-the-envelope",
    )
    contract = from_approval_lifecycle_result(source)
    serialized = json.dumps(contract.to_dict(), ensure_ascii=False)
    user_safe = json.dumps(contract.user_safe_record(), ensure_ascii=False)
    audit = json.dumps(contract.observability_record(), ensure_ascii=False)

    assert contract.display_payload.entity_name == source.safe_business_description
    for forbidden in (source.safe_user_message, source.contract_id):
        assert forbidden not in serialized
        assert forbidden not in user_safe
        assert forbidden not in audit


def test_empty_safe_description_yields_empty_display_payload():
    contract = from_approval_lifecycle_result(_result(safe_business_description=""))
    assert contract.display_payload.entity_name is None
    assert contract.display_payload.completeness() == "empty"


def test_owner_provenance_and_audit_metadata_are_copied_without_deciding_owner():
    contract = from_approval_lifecycle_result(_result(reply_owner="gateway"))
    assert contract.reply_owner == "gateway"
    assert contract.turn_context_source is TurnContextSource.LEGACY_INGRESS
    assert contract.turn_id is None
    assert contract.source_module == ADAPTER_SOURCE_MODULE
    assert contract.observability_record()["reply_owner_candidate"] == "gateway"


def test_adapter_output_round_trips_through_canonical_schema():
    original = from_approval_lifecycle_result(
        _result(canonical_state="rejected"), repeated=True
    )
    restored = MessageContract.from_dict(json.loads(json.dumps(original.to_dict())))
    assert restored == original


def test_generic_approval_interaction_is_provider_neutral():
    interaction = MessageInteraction(
        type=InteractionType.CONFIRM_CANCEL,
        actions=("✅ אשר", "↩️ בטל"),
    )
    contract = from_approval_lifecycle_result(_result(), interaction=interaction)

    assert contract.interaction == interaction
    assert contract.interaction.type is InteractionType.CONFIRM_CANCEL
    assert contract.interaction.actions == ("✅ אשר", "↩️ בטל")
    assert all("callback" not in action for action in contract.interaction.actions)


def test_adapter_is_deterministic_and_does_not_mutate_input():
    source = _result()
    snapshot = source
    first = from_approval_lifecycle_result(source)
    second = from_approval_lifecycle_result(source)
    assert first == second
    assert source == snapshot


def test_adapter_delegates_to_the_canonical_builder_once(monkeypatch):
    sentinel = object()
    calls = []

    def fake_builder(**kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(adapter_module, "build_message_contract", fake_builder)
    result = adapter_module.from_approval_lifecycle_result(_result())

    assert result is sentinel
    assert len(calls) == 1
    assert calls[0]["state"] is MessageState.APPROVAL_PENDING
    assert calls[0]["evidence_ref"] is None


def test_adapter_module_has_no_side_effect_authority_imports_or_calls():
    module_path = Path(__file__).parent / "core" / "approval_lifecycle_message_adapter.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported = set()
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert imported <= {"__future__", "core.message_contract", "typing"}
    assert called_names.isdisjoint({
        "dispatch_tool",
        "format_agent_message",
        "format_message_contract",
        "requests",
        "send_message",
        "approve",
        "reject",
        "find_by_id",
        "classification",
    })
