"""PR A tests for the pure Message Contract Envelope foundation."""

from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.agent_message_formatter import format_agent_message
from core.message_contract import (
    MESSAGE_CONTRACT_VERSION,
    DisplayPayload,
    InteractionType,
    MessageContract,
    MessageContractValidationError,
    MessageInteraction,
    MessageState,
    TurnContextSource,
    build_message_contract,
    format_message_contract,
    format_message_contract_with_meta,
)


def _build(**overrides) -> MessageContract:
    values = {
        "state": MessageState.APPROVAL_PENDING,
        "reply_owner": "gateway",
        "turn_context_source": TurnContextSource.LEGACY_INGRESS,
        "source_module": "test_message_contract",
        "display_payload": {
            "action": "create",
            "entity_type": "task",
            "entity_name": "מעקב ספק",
            "key_fields": [{"label": "תאריך", "value": "01/08/2026"}],
            "count": 1,
            "items": [],
            "reason_code": None,
            "execution_verified": None,
            "occurred_at": None,
        },
    }
    values.update(overrides)
    return build_message_contract(**values)


def test_message_state_registry_is_exactly_v1():
    assert {state.value for state in MessageState} == {
        "needs_input",
        "approval_pending",
        "approval_pending_query",
        "approval_pending_batch",
        "approved_processing",
        "success",
        "failure",
        "outcome_unknown",
        "unverified_effect",
        "mixed",
        "mixed_with_unknown",
        "cancelled",
        "already_completed",
        "already_cancelled",
        "no_pending_action",
        "neutral",
    }
    assert len(MessageState) == 16
    assert "idle" not in {state.value for state in MessageState}
    assert "clarification_needed" not in {state.value for state in MessageState}


@pytest.mark.parametrize(
    ("lifecycle", "evidence", "multiple", "expected"),
    [
        ("pending", None, False, MessageState.APPROVAL_PENDING),
        ("pending", None, True, MessageState.APPROVAL_PENDING_BATCH),
        ("rejected", None, False, MessageState.CANCELLED),
        ("failed", "verified_write_success", False, MessageState.FAILURE),
        ("approved", "verified_write_success", False, MessageState.APPROVED_PROCESSING),
        ("executing", "verified_write_success", False, MessageState.APPROVED_PROCESSING),
        ("completed", "verified_write_success", False, MessageState.SUCCESS),
        ("executed", "verified_read_only", False, MessageState.SUCCESS),
        ("completed", "failure", False, MessageState.FAILURE),
        ("completed", "outcome_unknown", False, MessageState.OUTCOME_UNKNOWN),
        ("completed", "unverified_effect", False, MessageState.UNVERIFIED_EFFECT),
        ("completed", "mixed", False, MessageState.MIXED),
        ("completed", "mixed_with_unknown", False, MessageState.MIXED_WITH_UNKNOWN),
        ("completed", None, False, MessageState.OUTCOME_UNKNOWN),
        ("completed", "no_evidence", False, MessageState.OUTCOME_UNKNOWN),
        ("outcome_unknown", "verified_write_success", False, MessageState.OUTCOME_UNKNOWN),
        ("draft", None, False, MessageState.NO_PENDING_ACTION),
        ("no_contract", None, False, MessageState.NO_PENDING_ACTION),
    ],
)
def test_lifecycle_evidence_precedence(lifecycle, evidence, multiple, expected):
    contract = _build(
        state=None,
        lifecycle_state=lifecycle,
        evidence_status=evidence,
        multiple_pending=multiple,
        execution_verified=True if expected is MessageState.SUCCESS else None,
    )
    assert contract.state is expected


def test_pending_query_is_distinct_presentation_semantic():
    contract = _build(
        state=MessageState.APPROVAL_PENDING_QUERY,
        display_payload={"entity_name": "יצירת ליד עבור דני כהן"},
    )
    assert contract.state is MessageState.APPROVAL_PENDING_QUERY
    assert contract.state is not MessageState.APPROVAL_PENDING
    assert format_message_contract(contract).startswith("יש פעולה שממתינה לאישור:")


def test_no_pending_action_uses_canonical_no_pending_wording():
    contract = _build(
        state=MessageState.NO_PENDING_ACTION,
        display_payload={},
    )
    assert format_message_contract(contract) == "אין כרגע פעולה שממתינה. אפשר להמשיך."
    assert format_message_contract(contract) != format_message_contract(
        _build(state=MessageState.APPROVAL_PENDING, display_payload={})
    )
    assert format_message_contract(contract) != format_message_contract(
        _build(state=MessageState.APPROVAL_PENDING_QUERY, display_payload={})
    )
    assert format_message_contract(contract) != format_message_contract(
        _build(state=MessageState.NEUTRAL, display_payload={})
    )


def test_success_is_rejected_without_matching_verified_evidence():
    with pytest.raises(MessageContractValidationError, match="success requires"):
        _build(state=MessageState.SUCCESS)
    with pytest.raises(MessageContractValidationError, match="success requires"):
        _build(
            state=MessageState.SUCCESS,
            evidence_status="outcome_unknown",
            execution_verified=True,
        )
    with pytest.raises(MessageContractValidationError, match="success requires"):
        _build(
            state=MessageState.SUCCESS,
            evidence_status="verified_write_success",
            execution_verified=False,
        )


def test_unknown_evidence_status_is_rejected_for_direct_non_success_state():
    with pytest.raises(MessageContractValidationError, match="unsupported evidence_status"):
        _build(
            state=MessageState.FAILURE,
            evidence_status="invented_evidence_classification",
        )


def test_verified_success_is_constructible():
    contract = _build(
        state=MessageState.SUCCESS,
        evidence_status="verified_write_success",
        execution_verified=True,
        display_payload={
            "action": "create",
            "entity_type": "task",
            "entity_name": "מעקב ספק",
            "key_fields": [],
            "count": 1,
            "items": [],
            "reason_code": None,
            "execution_verified": True,
            "occurred_at": None,
        },
    )
    assert contract.state is MessageState.SUCCESS


def test_invalid_or_conflicting_state_is_rejected():
    with pytest.raises(MessageContractValidationError, match="invalid MessageState"):
        _build(state="made_up")
    with pytest.raises(MessageContractValidationError, match="state or lifecycle_state"):
        _build(state=None)
    with pytest.raises(MessageContractValidationError, match="provide state or lifecycle_state"):
        _build(lifecycle_state="pending")
    with pytest.raises(MessageContractValidationError, match="unsupported lifecycle_state"):
        _build(state=None, lifecycle_state="invented")


def test_schema_validation_rejects_bad_version_owner_and_context_source():
    with pytest.raises(MessageContractValidationError, match="unsupported MessageContract version"):
        _build(version="2.0")
    with pytest.raises(MessageContractValidationError, match="reply_owner"):
        _build(reply_owner="")
    with pytest.raises(MessageContractValidationError, match="turn_context_source"):
        _build(turn_context_source="chat_id")


def test_display_payload_is_closed_and_rejects_internal_fields():
    for forbidden in (
        "tool_name",
        "contract_id",
        "record_id",
        "raw_provider_response",
        "internal_exception",
    ):
        with pytest.raises(MessageContractValidationError, match="unsupported fields"):
            DisplayPayload.from_mapping({forbidden: "secret"})


def test_display_payload_limits_and_types_are_validated():
    with pytest.raises(MessageContractValidationError, match="at most two"):
        DisplayPayload.from_mapping({
            "key_fields": [
                {"label": "a", "value": "1"},
                {"label": "b", "value": "2"},
                {"label": "c", "value": "3"},
            ]
        })
    with pytest.raises(MessageContractValidationError, match="non-negative"):
        DisplayPayload.from_mapping({"count": -1})
    with pytest.raises(MessageContractValidationError, match="v1 registry"):
        DisplayPayload.from_mapping({"action": "execute_shell"})


@pytest.mark.parametrize(
    "interaction",
    [
        MessageInteraction(
            InteractionType.CONFIRM_CANCEL,
            actions=("✅ אשר", "↩️ בטל"),
        ),
        MessageInteraction(
            InteractionType.SINGLE_CHOICE,
            options=("גיוס", "נדל״ן"),
            field="תחום",
            selected_values=("גיוס",),
        ),
        MessageInteraction(
            InteractionType.MULTI_CHOICE,
            options=("א", "ב"),
            selected_values=("א", "ב"),
        ),
        MessageInteraction(
            InteractionType.FREE_TEXT,
            field="שם",
        ),
        MessageInteraction(
            InteractionType.REVIEW_EDIT,
            actions=("✏️ ערוך", "↩️ בטל"),
            editable=True,
        ),
    ],
)
def test_provider_neutral_interaction_semantics_round_trip(interaction):
    contract = _build(interaction=interaction)
    restored = MessageContract.from_dict(contract.to_dict())
    assert restored.interaction == interaction
    assert restored.user_safe_record()["interaction"] == interaction.to_dict()
    rendered = format_message_contract(contract)
    assert "contract" not in rendered.lower()
    assert "callback" not in rendered.lower()


def test_interaction_is_optional_and_provider_identifiers_are_not_schema_fields():
    legacy = _build()
    assert legacy.interaction is None
    assert "interaction" not in legacy.to_dict()
    with pytest.raises(MessageContractValidationError, match="unsupported fields"):
        MessageInteraction.from_mapping({"type": "confirm_cancel", "callback_data": "secret"})


def test_serialization_round_trip_is_json_compatible():
    original = _build(
        turn_id="turn-123",
        evidence_status="approval_pending",
        evidence_ref="evidence-123",
    )
    encoded = json.dumps(original.to_dict(), ensure_ascii=False, sort_keys=True)
    restored = MessageContract.from_dict(json.loads(encoded))
    assert restored == original
    assert restored.version == MESSAGE_CONTRACT_VERSION
    assert restored.evidence_ref == "evidence-123"


@pytest.mark.parametrize(
    "state",
    (
        MessageState.NEEDS_INPUT,
        MessageState.ALREADY_COMPLETED,
        MessageState.ALREADY_CANCELLED,
        MessageState.NEUTRAL,
    ),
)
def test_direct_state_contract_round_trip_formatting_and_input_purity(state):
    original_input = {
        "action": "create",
        "entity_type": "task",
        "entity_name": "מעקב ספק",
        "key_fields": [{"label": "תאריך", "value": "01/08/2026"}],
        "count": 1,
        "items": [{"entity_name": "פריט בטוח"}],
        "reason_code": None,
        "execution_verified": None,
        "occurred_at": None,
    }
    input_snapshot = json.loads(json.dumps(original_input, ensure_ascii=False))

    contract = MessageContract(
        version=MESSAGE_CONTRACT_VERSION,
        state=state,
        display_payload=DisplayPayload.from_mapping(original_input),
        reply_owner="gateway",
        turn_context_source=TurnContextSource.LEGACY_INGRESS,
        source_module="test_message_contract",
    )
    assert contract.state is state
    assert contract.display_payload.entity_name == "מעקב ספק"

    serialized = contract.to_dict()
    assert serialized["state"] == state.value
    serialized_snapshot = json.loads(json.dumps(serialized, ensure_ascii=False))
    restored = MessageContract.from_dict(serialized)
    assert restored == contract
    assert restored.to_dict() == serialized_snapshot

    contract_snapshot = contract.to_dict()
    text, meta = format_message_contract_with_meta(contract)
    assert text == format_agent_message(state.value, contract.display_payload.to_dict())
    assert meta["state"] == state.value
    assert meta["formatter_state"] == "unrecognized"
    assert meta["fallback_used"] is True
    assert contract.to_dict() == contract_snapshot
    assert serialized == serialized_snapshot
    assert original_input == input_snapshot


def test_deserialization_rejects_unknown_state_and_fields():
    data = _build().to_dict()
    data["state"] = "bogus"
    with pytest.raises(MessageContractValidationError, match="invalid MessageState"):
        MessageContract.from_dict(data)
    data = _build().to_dict()
    data["contract_id"] = "must-not-enter-envelope"
    with pytest.raises(MessageContractValidationError, match="unsupported fields"):
        MessageContract.from_dict(data)


def test_deserialization_rejects_missing_display_payload():
    data = _build().to_dict()
    del data["display_payload"]
    with pytest.raises(MessageContractValidationError, match="display_payload is required"):
        MessageContract.from_dict(data)


def test_user_safe_and_audit_records_are_separated():
    contract = _build(
        turn_id="turn-123",
        evidence_status="approval_pending",
        evidence_ref="audit-evidence-ref",
    )
    safe = contract.user_safe_record()
    audit = contract.observability_record()

    assert set(safe) == {"state", "display_payload"}
    assert "turn_id" not in safe and "evidence_ref" not in safe and "reply_owner" not in safe
    assert "display_payload" not in audit
    assert "מעקב ספק" not in json.dumps(audit, ensure_ascii=False)
    assert audit["reply_owner_candidate"] == "gateway"
    assert audit["source_component"] == "test_message_contract"


def test_builder_does_not_mutate_input_and_result_is_immutable():
    payload = {
        "action": "create",
        "entity_type": "task",
        "entity_name": "מעקב ספק",
        "key_fields": [{"label": "תאריך", "value": "01/08/2026"}],
        "count": 1,
        "items": [{"entity_name": "פריט בטוח"}],
        "reason_code": None,
        "execution_verified": None,
        "occurred_at": None,
    }
    snapshot = json.loads(json.dumps(payload, ensure_ascii=False))
    first = _build(display_payload=payload)
    second = _build(display_payload=payload)
    assert payload == snapshot
    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.state = MessageState.FAILURE
    with pytest.raises(AttributeError):
        first.display_payload.key_fields.append("x")


def test_correlation_is_nullable_and_never_synthesized():
    contract = _build(turn_id=None, evidence_ref=None)
    assert contract.turn_id is None
    assert contract.evidence_ref is None
    assert contract.turn_context_source is TurnContextSource.LEGACY_INGRESS


def test_evidence_reference_is_copied_verbatim():
    contract = _build(evidence_ref="authority-issued-ref")
    assert contract.evidence_ref == "authority-issued-ref"
    assert contract.to_dict()["evidence_ref"] == "authority-issued-ref"


def test_wrapper_matches_existing_formatter_for_supported_state():
    contract = _build()
    expected = format_agent_message(
        contract.state.value,
        contract.display_payload.to_dict(),
    )
    assert format_message_contract(contract) == expected


def test_wrapper_is_deterministic_and_payload_free_in_meta():
    contract = _build()
    first = format_message_contract_with_meta(contract)
    second = format_message_contract_with_meta(contract)
    assert first == second
    text, meta = first
    assert text
    assert "display_payload" not in meta
    assert "מעקב ספק" not in json.dumps(meta, ensure_ascii=False)
    assert meta["state"] == "approval_pending"
    assert meta["formatter_state"] == "approval_pending"


def test_new_state_uses_existing_formatter_fail_safe_without_new_wording():
    contract = _build(state=MessageState.APPROVED_PROCESSING)
    text, meta = format_message_contract_with_meta(contract)
    assert text == format_agent_message("approved_processing", contract.display_payload.to_dict())
    assert meta["fallback_used"] is True
    assert meta["formatter_state"] == "unrecognized"
    assert meta["state"] == "approved_processing"


def test_module_has_no_side_effect_authority_imports():
    module_path = Path(__file__).parent / "core" / "message_contract.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden_prefixes = (
        "app",
        "telebot",
        "twilio",
        "airtable",
        "core.action_gateway",
        "core.action_contract_repository",
        "core.turn_evidence",
        "core.turn_envelope",
        "tools.dispatcher",
        "anthropic",
        "requests",
    )
    assert not any(name.startswith(forbidden_prefixes) for name in imported)
    assert imported <= {
        "__future__",
        "ast",
        "core.agent_message_formatter",
        "dataclasses",
        "enum",
        "typing",
    }
