"""WS3 lifecycle/evidence adapter integration and parity coverage."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.evidence_message_adapter import from_evidence_result
from core.lifecycle_message_adapter import from_action_lifecycle_result
from core.message_contract import MessageContractValidationError, MessageState
from core.message_surface_harness import assert_surface_ready
from core.router.ownership_contracts import ActionLifecycleResult, EvidenceResult


def _lifecycle(state: str) -> ActionLifecycleResult:
    return ActionLifecycleResult("contract-internal", state, "approval", "execution", "gateway")


def _evidence(**overrides) -> EvidenceResult:
    values = {
        "result": "completed",
        "evidence_ref": "evidence-internal",
        "provider_result": "provider-internal",
        "verified": True,
        "outcome_unknown": False,
        "error": "",
    }
    values.update(overrides)
    return EvidenceResult(**values)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("pending", MessageState.APPROVAL_PENDING),
        ("approved", MessageState.APPROVED_PROCESSING),
        ("executing", MessageState.APPROVED_PROCESSING),
        ("completed", MessageState.OUTCOME_UNKNOWN),
        ("failed", MessageState.FAILURE),
        ("cancelled", MessageState.CANCELLED),
        ("expired", MessageState.FAILURE),
        ("outcome_unknown", MessageState.OUTCOME_UNKNOWN),
        ("duplicate", MessageState.OUTCOME_UNKNOWN),
        ("stale", MessageState.OUTCOME_UNKNOWN),
        ("not_found", MessageState.NO_PENDING_ACTION),
        ("unavailable", MessageState.FAILURE),
    ],
)
def test_all_required_lifecycle_states_map_to_existing_public_states(state, expected):
    contract = from_action_lifecycle_result(_lifecycle(state), description="משימה")
    assert contract.state is expected
    verification = assert_surface_ready(contract)
    assert len({render.text for render in verification.renders}) == 1


def test_evidence_verified_completion_is_success_and_unknown_is_not():
    success = from_evidence_result(_evidence(), description="משימה")
    unknown = from_evidence_result(_evidence(verified=False, outcome_unknown=True), description="משימה")
    assert success.state is MessageState.SUCCESS
    assert unknown.state is MessageState.OUTCOME_UNKNOWN
    assert_surface_ready(success)
    assert_surface_ready(unknown)


def test_combined_evidence_precedence_downgrades_optimistic_completion():
    contract = from_action_lifecycle_result(
        _lifecycle("completed"),
        evidence=_evidence(verified=False, error="raw provider exception"),
        description="משימה",
    )
    assert contract.state is MessageState.FAILURE
    text = assert_surface_ready(contract).renders[0].text
    assert "raw provider exception" not in text


@pytest.mark.parametrize(
    ("lifecycle_state", "evidence", "expected"),
    [
        ("pending", _evidence(verified=False, error="provider failed"), MessageState.FAILURE),
        ("approved", _evidence(verified=False, outcome_unknown=True), MessageState.OUTCOME_UNKNOWN),
    ],
)
def test_evidence_precedence_beats_optimistic_lifecycle_text(lifecycle_state, evidence, expected):
    contract = from_action_lifecycle_result(_lifecycle(lifecycle_state), evidence=evidence)
    assert contract.state is expected


def test_cancelled_lifecycle_beats_stale_or_optimistic_evidence():
    contract = from_action_lifecycle_result(
        _lifecycle("cancelled"), evidence=_evidence(), description="משימה"
    )
    assert contract.state is MessageState.CANCELLED


def test_unknown_lifecycle_fails_closed_and_internal_data_is_not_user_safe():
    with pytest.raises(MessageContractValidationError):
        from_action_lifecycle_result(_lifecycle("invented_state"))
    contract = from_evidence_result(
        _evidence(provider_result="airtable_add rec123", error="Traceback: secret"),
        description="airtable_add rec123",
    )
    verification = assert_surface_ready(
        contract, forbidden_tokens=("airtable_add", "rec123", "Traceback", "secret")
    )
    assert verification.leaks == ()


def test_adapters_do_not_import_runtime_authorities():
    for relative in ("core/lifecycle_message_adapter.py", "core/evidence_message_adapter.py"):
        tree = ast.parse((Path(__file__).parent / relative).read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert "core.action_gateway" not in imports
        assert "app" not in imports
