"""Focused PR C tests for the pure ActionFact adapter."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

import pytest

from core.action_gateway import ActionFact
import core.action_fact_message_adapter as adapter_module
from core.action_fact_message_adapter import (
    ADAPTER_SOURCE_MODULE,
    from_action_fact,
)
from core.message_contract import (
    MessageContract,
    MessageContractValidationError,
    MessageState,
    TurnContextSource,
)


def _fact(**overrides) -> ActionFact:
    values = {
        "tool_name": "airtable_add",
        "contract_id": "123e4567-e89b-12d3-a456-426614174000",
        "outcome": "pending",
        "record_id": None,
        "error_code": None,
        "raw_tool_response": {},
    }
    values.update(overrides)
    return ActionFact(**values)


@pytest.mark.parametrize(
    ("outcome", "evidence_status", "execution_verified", "expected"),
    [
        ("pending", None, None, MessageState.APPROVAL_PENDING),
        ("rejected", None, None, MessageState.CANCELLED),
        ("failed", None, None, MessageState.FAILURE),
        ("executed", "verified_write_success", True, MessageState.SUCCESS),
        ("executed", "verified_read_only", True, MessageState.SUCCESS),
        ("executed", "outcome_unknown", None, MessageState.OUTCOME_UNKNOWN),
        ("executed", "unverified_effect", None, MessageState.UNVERIFIED_EFFECT),
        ("executed", "failure", None, MessageState.FAILURE),
        ("executed", "failed", None, MessageState.FAILURE),
        ("executed", "mixed", None, MessageState.MIXED),
        ("executed", "mixed_with_unknown", None, MessageState.MIXED_WITH_UNKNOWN),
        ("executed", None, None, MessageState.OUTCOME_UNKNOWN),
        ("executed", "no_evidence", None, MessageState.OUTCOME_UNKNOWN),
    ],
)
def test_complete_outcome_mapping(outcome, evidence_status, execution_verified, expected):
    contract = from_action_fact(
        _fact(outcome=outcome),
        evidence_status=evidence_status,
        execution_verified=execution_verified,
    )
    assert contract.state is expected


def test_executed_without_evidence_never_claims_success():
    contract = from_action_fact(_fact(outcome="executed"))
    assert contract.state is MessageState.OUTCOME_UNKNOWN
    assert contract.evidence_status is None
    assert contract.evidence_ref is None
    assert contract.execution_verified is None


def test_executed_with_mismatched_evidence_pairing_raises_never_silently_succeeds():
    with pytest.raises(MessageContractValidationError, match="success requires matching verified evidence"):
        from_action_fact(
            _fact(outcome="executed"),
            evidence_status="verified_write_success",
            execution_verified=None,
        )
    with pytest.raises(MessageContractValidationError, match="success requires matching verified evidence"):
        from_action_fact(
            _fact(outcome="executed"),
            evidence_status="verified_write_success",
            execution_verified=False,
        )
    # execution_verified=True alone (no matching evidence_status) never upgrades to success either.
    contract = from_action_fact(
        _fact(outcome="executed"), evidence_status=None, execution_verified=True,
    )
    assert contract.state is MessageState.OUTCOME_UNKNOWN


def test_invalid_outcome_is_rejected():
    with pytest.raises(MessageContractValidationError, match=r"unsupported ActionFact\.outcome"):
        from_action_fact(_fact(outcome="invented"))
    with pytest.raises(MessageContractValidationError, match=r"unsupported ActionFact\.outcome"):
        from_action_fact(_fact(outcome=""))
    # ActionFact.outcome values that ARE valid for the broader lifecycle_state
    # vocabulary but are NOT part of ActionFact's own closed 4-value contract
    # must still be rejected here (ActionFact never legitimately carries them).
    with pytest.raises(MessageContractValidationError, match=r"unsupported ActionFact\.outcome"):
        from_action_fact(_fact(outcome="completed"))
    with pytest.raises(MessageContractValidationError, match=r"unsupported ActionFact\.outcome"):
        from_action_fact(_fact(outcome="approved"))


def test_reason_code_mapping():
    failed = from_action_fact(_fact(outcome="failed", error_code="GOOGLE_AUTH_REQUIRED"))
    assert failed.reason_code == "GOOGLE_AUTH_REQUIRED"

    failed_no_code = from_action_fact(_fact(outcome="failed", error_code=None))
    assert failed_no_code.reason_code is None

    rejected = from_action_fact(_fact(outcome="rejected", error_code=None))
    assert rejected.reason_code == "ACTION_REJECTED"

    pending = from_action_fact(_fact(outcome="pending"))
    assert pending.reason_code is None

    executed = from_action_fact(_fact(outcome="executed"))
    assert executed.reason_code is None

    # metadata שפונה ל-formatter נישא גם ב-display payload הציבורי;
    # אחרת ה-wrapper הקנוני של MessageContract לא יכול לשמר את הניסוח
    # הקיים של פעולה שנכשלה.
    assert failed.display_payload.reason_code == "GOOGLE_AUTH_REQUIRED"
    assert rejected.display_payload.reason_code == "ACTION_REJECTED"


def test_non_string_error_code_is_rejected():
    with pytest.raises(MessageContractValidationError, match="error_code must be a string or None"):
        from_action_fact(_fact(outcome="failed", error_code=12345))


def test_description_is_the_only_copied_detail():
    forbidden_tool_name = "airtable_add"
    forbidden_record_id = "recXYZ0987654321ABCDE"
    forbidden_contract_id = "contract-id-that-must-not-enter-the-envelope"
    forbidden_raw_marker = "RAW_TOOL_RESPONSE_SECRET_MARKER"

    source = _fact(
        tool_name=forbidden_tool_name,
        contract_id=forbidden_contract_id,
        outcome="pending",
        record_id=forbidden_record_id,
        error_code=None,
        raw_tool_response={"internal": forbidden_raw_marker},
    )
    contract = from_action_fact(source, description="יש משימה שממתינה: מעקב ספק")
    serialized = json.dumps(contract.to_dict(), ensure_ascii=False)
    user_safe = json.dumps(contract.user_safe_record(), ensure_ascii=False)
    audit = json.dumps(contract.observability_record(), ensure_ascii=False)

    assert contract.display_payload.entity_name == "יש משימה שממתינה: מעקב ספק"
    for forbidden in (
        forbidden_tool_name,
        forbidden_record_id,
        forbidden_contract_id,
        forbidden_raw_marker,
    ):
        assert forbidden not in serialized
        assert forbidden not in user_safe
        assert forbidden not in audit


def test_empty_description_yields_empty_display_payload():
    contract = from_action_fact(_fact(outcome="pending"))
    assert contract.display_payload.entity_name is None
    assert contract.display_payload.completeness() == "empty"

    contract_blank = from_action_fact(_fact(outcome="pending"), description="   ")
    assert contract_blank.display_payload.entity_name is None


def test_non_string_description_is_rejected():
    with pytest.raises(MessageContractValidationError, match="description must be a string or None"):
        from_action_fact(_fact(outcome="pending"), description=123)


def test_evidence_ref_is_never_derived_from_contract_id_or_record_id():
    contract = from_action_fact(
        _fact(outcome="executed", contract_id="cid-1", record_id="rec-1"),
        evidence_status="verified_write_success",
        execution_verified=True,
    )
    assert contract.evidence_ref is None


def test_owner_and_provenance_are_fixed_never_inferred():
    contract = from_action_fact(_fact(outcome="pending"))
    assert contract.reply_owner == "gateway"
    assert contract.turn_context_source is TurnContextSource.LEGACY_INGRESS
    assert contract.turn_id is None
    assert contract.source_module == ADAPTER_SOURCE_MODULE
    assert contract.observability_record()["reply_owner_candidate"] == "gateway"


def test_adapter_output_round_trips_through_canonical_schema():
    original = from_action_fact(
        _fact(outcome="executed"),
        evidence_status="verified_read_only",
        execution_verified=True,
        description="קריאת נתוני ספק",
    )
    restored = MessageContract.from_dict(json.loads(json.dumps(original.to_dict())))
    assert restored == original

    failure = from_action_fact(_fact(outcome="failed", error_code="PERMISSION_DENIED"))
    restored_failure = MessageContract.from_dict(json.loads(json.dumps(failure.to_dict())))
    assert restored_failure == failure


def test_adapter_is_deterministic_and_does_not_mutate_input():
    source = _fact(outcome="rejected")
    snapshot = replace(source)
    first = from_action_fact(source)
    second = from_action_fact(source)
    assert first == second
    assert source == snapshot


def test_adapter_delegates_to_the_canonical_builder_once(monkeypatch):
    sentinel = object()
    calls = []

    def fake_builder(**kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(adapter_module, "build_message_contract", fake_builder)
    result = adapter_module.from_action_fact(_fact(outcome="pending"))

    assert result is sentinel
    assert len(calls) == 1
    assert calls[0]["lifecycle_state"] == "pending"
    assert calls[0]["multiple_pending"] is False
    assert calls[0]["evidence_ref"] is None
    assert calls[0]["turn_id"] is None


def test_adapter_module_has_no_side_effect_authority_imports_or_calls():
    module_path = Path(__file__).parent / "core" / "action_fact_message_adapter.py"
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
        "compose_status_reply",
        "requests",
        "send_message",
        "approve",
        "reject",
        "find_by_id",
        "classification",
    })


def test_only_action_gateway_imports_the_adapter_for_pr_d_runtime():
    """שער scope של PR D: מודול production יחיד בדיוק מחזיק בחיווט הראשון."""
    repo_root = Path(__file__).parent
    for filename in ("app.py", "tma_api.py"):
        content = (repo_root / filename).read_text(encoding="utf-8")
        assert "action_fact_message_adapter" not in content
        assert "from_action_fact" not in content

    gateway_content = (repo_root / "core/action_gateway.py").read_text(encoding="utf-8")
    assert gateway_content.count("from core.action_fact_message_adapter import from_action_fact") == 1
    assert gateway_content.count("from_action_fact(fact, description=description)") == 1
