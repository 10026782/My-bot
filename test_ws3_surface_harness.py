"""WS3 surface parity, redaction, precedence, and rollback harness scenarios."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.message_contract import MessageState, TurnContextSource, build_message_contract
from core.message_surface_harness import (
    SUPPORTED_SURFACES,
    assert_surface_ready,
    rollback_is_safe,
    verify_surface_parity,
)


def _contract(state=MessageState.APPROVAL_PENDING, **overrides):
    """Build a representative public contract for harness scenarios."""
    values = {
        "state": state,
        "reply_owner": "gateway",
        "turn_context_source": TurnContextSource.LEGACY_INGRESS,
        "source_module": "test_ws3_surface_harness",
        "display_payload": {
            "action": "create",
            "entity_type": "task",
            "entity_name": "מעקב ספק",
            "key_fields": [{"label": "תאריך", "value": "01/08/2026"}],
        },
    }
    values.update(overrides)
    return build_message_contract(**values)


@pytest.mark.parametrize(
    "state",
    [
        MessageState.APPROVAL_PENDING,
        MessageState.APPROVAL_PENDING_BATCH,
        MessageState.SUCCESS,
        MessageState.FAILURE,
        MessageState.OUTCOME_UNKNOWN,
        MessageState.UNVERIFIED_EFFECT,
        MessageState.MIXED,
        MessageState.MIXED_WITH_UNKNOWN,
    ],
)
def test_every_public_state_has_cross_surface_parity(state):
    """Every formatter-supported state must remain identical across surfaces."""
    if state is MessageState.SUCCESS:
        contract = _contract(
            state,
            evidence_status="verified_write_success",
            execution_verified=True,
            display_payload={
                "action": "create",
                "entity_type": "task",
                "entity_name": "מעקב ספק",
                "execution_verified": True,
            },
        )
    else:
        contract = _contract(state)
    verification = assert_surface_ready(contract)
    assert tuple(render.surface for render in verification.renders) == SUPPORTED_SURFACES
    assert {render.state for render in verification.renders} == {state.value}
    assert rollback_is_safe(verification)


def test_internal_identifiers_and_tool_names_never_reach_any_surface():
    """Redaction must remove technical identifiers from every surface output."""
    contract = _contract(
        display_payload={
            "action": "create",
            "entity_type": "task",
            "entity_name": (
                "מעקב ספק airtable_add "
                "123e4567-e89b-12d3-a456-426614174000 recE0N2reMAt6TVe7"
            ),
        }
    )
    verification = verify_surface_parity(
        contract,
        forbidden_tokens=("airtable_add", "123e4567-e89b-12d3-a456-426614174000", "recE0N2reMAt6TVe7"),
    )
    assert verification.ready
    assert verification.leaks == ()
    assert all("airtable_add" not in render.text for render in verification.renders)


def test_completed_without_evidence_is_outcome_unknown_on_every_surface():
    """Completion without evidence must remain outcome-unknown everywhere."""
    contract = _contract(state=None, lifecycle_state="completed")
    verification = assert_surface_ready(contract)
    assert {render.state for render in verification.renders} == {MessageState.OUTCOME_UNKNOWN.value}
    assert all("✅" not in render.text for render in verification.renders)


def test_readiness_fails_closed_for_leak_and_surface_mismatch_inputs():
    """Readiness validation must reject unsupported or duplicate surfaces."""
    contract = _contract()
    with pytest.raises(ValueError, match="unsupported surface"):
        verify_surface_parity(contract, surfaces=("telegram", "sms"))
    with pytest.raises(ValueError, match="unique"):
        verify_surface_parity(contract, surfaces=("telegram", "telegram"))


def test_harness_is_pure_and_does_not_touch_runtime_surfaces():
    """The harness must stay independent of app runtime wiring."""
    module_path = Path(__file__).parent / "core" / "message_surface_harness.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imports <= {"__future__", "dataclasses", "typing", "core.message_contract"}
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module == "app"
        for node in ast.walk(tree)
    )
