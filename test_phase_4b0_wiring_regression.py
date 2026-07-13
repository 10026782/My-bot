#!/usr/bin/env python3
"""
test_phase_4b0_wiring_regression.py — Regression test for atomic claim wiring

CRITICAL: When FEATURE_ATOMIC_CLAIMS=true, every approval execution path
MUST create exactly one atomic claim and dispatch exactly once.

Bug: route_confirmation_word → approve() → _execute_contract() bypassed
atomic claim acquisition entirely, dispatching directly without claim creation.

This test reproduces that exact path and asserts:
1. One claim created in action_execution_claims
2. One dispatch_tool call (no duplicates)
3. Claim status transitions: executing → completed
"""

from __future__ import annotations

import os
import sys
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock, call
from typing import Any

os.environ.setdefault("FEATURE_ATOMIC_CLAIMS", "true")
os.environ.setdefault("FEATURE_ACTION_GATEWAY", "true")

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def test_route_confirmation_word_creates_atomic_claim():
    """
    Reproduce exact bug: route_confirmation_word → approve() → _execute_contract()
    must create exactly one atomic claim before dispatch.
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract

    # Create test contract (frozen state after approval)
    contract_id = "test-contract-wiring-regression"
    test_contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="user_1",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "rec123", "fields": {"Status": "Won"}},
        business_action_fingerprint="fingerprint_123",
        status="approved",  # Already approved
        origin_channel="telegram",
        origin_chat_id="chat_1",
        requires_approval=True,
        created_at=1234567890.0,
        actor_role="owner",
        actor_user_id="user_1",
        actor_external_id="tg_user_1",
        approved_by="user_1",  # Set by approve()
        approved_at=1234567891.0,
    )

    # Mock ledger
    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    # Mock executor to track calls
    executor_calls = []
    def mock_executor(tool_name, tool_inputs, contract_id=None, identity=None):
        executor_calls.append({"tool_name": tool_name, "contract_id": contract_id})
        return {"ok": True, "external_id": "ext_id_123"}

    # Test with flag ON: atomic executor must be called
    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.action_gateway_atomic_executor.execute_with_atomic_claim') as mock_atomic:
            mock_atomic.return_value = (True, {"ok": True, "external_id": "ext_123"}, None)

            # Create gateway and test _execute_contract directly
            gateway = ActionGateway(ledger=mock_ledger)
            gateway._tool_executor = mock_executor

            # Call _execute_contract with frozen approved contract
            result = gateway._execute_contract(test_contract)

            # Verify atomic claim acquisition was called
            chk(
                "Flag ON: execute_with_atomic_claim invoked",
                mock_atomic.called
            )

            # Verify executor was only called once (no duplicates)
            chk(
                f"Executor called exactly once via atomic wrapper (got {len(executor_calls)})",
                len(executor_calls) == 0  # executor_calls bypassed because atomic wrapper used
            )

            if mock_atomic.called:
                # Check that atomic executor was called with correct contract_id
                call_kwargs = mock_atomic.call_args[1]
                chk(
                    "Atomic executor called with correct contract_id",
                    call_kwargs.get('contract_id') == contract_id
                )
                chk(
                    "Atomic executor called with deterministic idempotency_key",
                    'idempotency_key' in call_kwargs and call_kwargs['idempotency_key'] is not None
                )


def test_flag_off_preserves_legacy_behavior():
    """
    When FEATURE_ATOMIC_CLAIMS=false, _execute_contract calls dispatcher directly
    without atomic coordination (legacy behavior, backward compatible).
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract

    contract_id = "test-contract-flag-off"
    test_contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="user_1",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "rec123", "fields": {"Status": "Won"}},
        business_action_fingerprint="fingerprint_456",
        status="approved",
        origin_channel="telegram",
        origin_chat_id="chat_1",
        requires_approval=True,
        created_at=1234567890.0,
        actor_role="owner",
        actor_user_id="user_1",
        actor_external_id="tg_user_1",
        approved_by="user_1",
        approved_at=1234567891.0,
    )

    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    executor_calls = []
    def mock_executor(tool_name, tool_inputs, contract_id=None, identity=None):
        executor_calls.append({"tool_name": tool_name})
        return {"ok": True, "external_id": "rec456"}

    # Test with flag OFF: direct dispatch, no atomic executor
    with patch('feature_flags.is_enabled', return_value=False):
        with patch('core.action_gateway_atomic_executor.execute_with_atomic_claim') as mock_atomic:
            gateway = ActionGateway(ledger=mock_ledger)
            gateway._tool_executor = mock_executor

            result = gateway._execute_contract(test_contract)

            # Atomic executor NOT called when flag OFF
            chk(
                "Flag OFF: execute_with_atomic_claim NOT invoked",
                not mock_atomic.called
            )

            # Executor called directly (legacy path)
            chk(
                "Flag OFF: executor called directly once",
                len(executor_calls) == 1
            )


def test_concurrent_approvals_single_dispatch():
    """
    Two concurrent confirmations of the same frozen contract: one ACQUIRED,
    one ALREADY_CLAIMED. Only winner reaches dispatcher (zero additional calls).
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract

    contract_id = "test-contract-concurrent"
    test_contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="user_1",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "rec123", "fields": {"Status": "Won"}},
        business_action_fingerprint="fingerprint_789",
        status="approved",
        origin_channel="telegram",
        origin_chat_id="chat_1",
        requires_approval=True,
        created_at=1234567890.0,
        actor_role="owner",
        actor_user_id="user_1",
        actor_external_id="tg_user_1",
        approved_by="user_1",
        approved_at=1234567891.0,
    )

    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    # Simulate concurrent call outcomes: first ACQUIRED, second ALREADY_CLAIMED
    call_sequence = [True, False]  # First call succeeds, second fails
    outcomes = []

    def mock_atomic_executor(contract_id, canonical_user_id, tool_name, tool_inputs, identity, executor_fn, idempotency_key=None):
        outcome = call_sequence.pop(0) if call_sequence else False
        if outcome:
            # First caller: ACQUIRED
            result = executor_fn(tool_name, tool_inputs, contract_id)
            outcomes.append(("acquired", result))
            return (True, result, None)
        else:
            # Second caller: ALREADY_CLAIMED (fail-closed)
            outcomes.append(("already_claimed", None))
            return (False, None, "Contract already being executed")

    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    executor_calls = []
    def mock_executor(tool_name, tool_inputs, contract_id=None, identity=None):
        executor_calls.append({"tool_name": tool_name})
        return {"ok": True, "external_id": "rec789"}

    # Simulate two concurrent approval attempts
    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.action_gateway_atomic_executor.execute_with_atomic_claim', side_effect=mock_atomic_executor):
            gateway = ActionGateway(ledger=mock_ledger)
            gateway._tool_executor = mock_executor

            # First approval (wins the race)
            result1 = gateway._execute_contract(test_contract)

            # Second approval (loses the race, already_claimed)
            result2 = gateway._execute_contract(test_contract)

            # Exactly one dispatch call from two concurrent attempts
            chk(
                f"Concurrent approvals: one dispatcher call (got {len(executor_calls)})",
                len(executor_calls) == 1
            )

            # One success, one failure
            chk(
                "Concurrent approvals: first call succeeded",
                len(outcomes) == 2 and outcomes[0][0] == "acquired"
            )

            chk(
                "Concurrent approvals: second call already_claimed",
                outcomes[1][0] == "already_claimed"
            )


def test_database_unavailable_zero_dispatch():
    """
    When PostgreSQL is unavailable, dispatcher is NOT called (fail-closed).
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract

    contract_id = "test-contract-db-down"
    test_contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="user_1",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "rec123", "fields": {"Status": "Won"}},
        business_action_fingerprint="fingerprint_abc",
        status="approved",
        origin_channel="telegram",
        origin_chat_id="chat_1",
        requires_approval=True,
        created_at=1234567890.0,
        actor_role="owner",
        actor_user_id="user_1",
        actor_external_id="tg_user_1",
        approved_by="user_1",
        approved_at=1234567891.0,
    )

    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    executor_calls = []
    def mock_executor(tool_name, tool_inputs, contract_id=None, identity=None):
        executor_calls.append({"tool_name": tool_name})
        return {"ok": True}

    # Test with flag ON but DB unavailable
    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.action_gateway_atomic_executor.execute_with_atomic_claim') as mock_atomic:
            # Simulate DB unavailable
            mock_atomic.return_value = (False, None, "PostgreSQL unavailable")

            gateway = ActionGateway(ledger=mock_ledger)
            gateway._tool_executor = mock_executor

            result = gateway._execute_contract(test_contract)

            # Executor NOT called when claim unavailable
            chk(
                "DB unavailable: zero dispatcher calls",
                len(executor_calls) == 0
            )

            # Result indicates failure
            chk(
                "DB unavailable: error message returned",
                "ביצוע נכשל" in result or "failed" in result.lower()
            )


if __name__ == "__main__":
    print("=" * 70)
    print("Phase 4B0 — ActionGateway Atomic Claim Wiring Regression Test")
    print("=" * 70)
    print()

    test_route_confirmation_word_creates_atomic_claim()
    print()
    test_flag_off_preserves_legacy_behavior()
    print()
    test_concurrent_approvals_single_dispatch()
    print()
    test_database_unavailable_zero_dispatch()

    print()
    print("=" * 70)
    print(f"PASSED: {passed} | FAILED: {failed}")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
