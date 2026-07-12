#!/usr/bin/env python3
"""
test_phase_4b0_1b_concurrency_regression_mock.py — Mock version of regression tests

Tests the untargeted ON CONFLICT DO NOTHING fix locally using mocks.
Real PostgreSQL tests must run on Render staging: see PHASE_4B0_CONCURRENCY_REGRESSION_GUIDE.md

Mocks four critical scenarios:
1. Same contract + same idempotency_key (retry) → ACQUIRED + ALREADY_CLAIMED
2. Same contract + different idempotency_key (concurrent) → ACQUIRED + CONTRACT_IDENTITY_CONFLICT
3. Different contracts + same idempotency_key (conflict) → ACQUIRED + IDEMPOTENCY_CONFLICT
4. Different contracts + different idempotency_keys (independent) → ACQUIRED + ACQUIRED
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

os.environ.setdefault("FEATURE_ATOMIC_CLAIMS", "true")

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
# Test 1: Same contract + same idempotency_key (retry)
# ══════════════════════════════════════════════════════════════════

def test_mock_same_contract_same_idem():
    """
    Scenario A: Same contract, same idempotency_key (retry).
    First caller ACQUIRED, second caller ALREADY_CLAIMED.
    """
    from core.atomic_claim_repository import claim_contract_execution

    contract_id = "test-contract-A"
    idem_key = "idem-1"

    # First caller: INSERT succeeds (untargeted ON CONFLICT DO NOTHING doesn't fire)
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchone.return_value = (contract_id,)
        result1 = claim_contract_execution(contract_id, "user_1", idem_key)
        chk("Scenario A: first caller ACQUIRED", result1.is_acquired())

    # Second caller: INSERT fails (contract_id PRIMARY KEY conflict)
    # Query finds: contract_id exists with SAME idempotency_key
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # fetchone: INSERT returns None (conflict)
        # fetchall: SELECT finds (contract_id, idem_key) with same contract and same key
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = [(contract_id, idem_key)]

        result2 = claim_contract_execution(contract_id, "user_1", idem_key)
        chk("Scenario A: second caller (retry) ALREADY_CLAIMED", result2.is_already_claimed())


# ══════════════════════════════════════════════════════════════════
# Test 2: Same contract + different idempotency_key (concurrent)
# ══════════════════════════════════════════════════════════════════

def test_mock_same_contract_diff_idem():
    """
    Scenario B: Same contract, different idempotency_key (concurrent execution).
    First caller ACQUIRED, second caller CONTRACT_IDENTITY_CONFLICT (fail-closed).
    """
    from core.atomic_claim_repository import claim_contract_execution

    contract_id = "test-contract-B"
    idem_key_1 = "idem-1"
    idem_key_2 = "idem-2"

    # First caller: INSERT succeeds
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchone.return_value = (contract_id,)
        result1 = claim_contract_execution(contract_id, "user_1", idem_key_1)
        chk("Scenario B: first caller ACQUIRED", result1.is_acquired())

    # Second caller: INSERT fails (contract_id PRIMARY KEY conflict)
    # Query finds: contract_id exists but with DIFFERENT idempotency_key
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # fetchone: INSERT returns None (conflict on contract_id)
        # fetchall: SELECT finds (contract_id, idem_key_1) but we tried with idem_key_2
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = [(contract_id, idem_key_1)]

        result2 = claim_contract_execution(contract_id, "user_2", idem_key_2)
        chk("Mock same contract + diff idem: second caller CONTRACT_IDENTITY_CONFLICT", result2.is_contract_identity_conflict())


# ══════════════════════════════════════════════════════════════════
# Test 3: Different contracts + same idempotency_key (identity mismatch)
# ══════════════════════════════════════════════════════════════════

def test_mock_diff_contracts_same_idem():
    """
    Scenario C: Different contracts, same idempotency_key (identity/session mismatch).
    First caller (contract A) ACQUIRED, second caller (contract B) IDEMPOTENCY_CONFLICT (fail-closed).
    """
    from core.atomic_claim_repository import claim_contract_execution

    contract_a = "test-contract-A"
    contract_b = "test-contract-B"
    shared_idem = "idem-shared"

    # First caller claims contract A: INSERT succeeds
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchone.return_value = (contract_a,)
        result_a = claim_contract_execution(contract_a, "user_1", shared_idem)
        chk("Scenario C: contract A ACQUIRED", result_a.is_acquired())

    # Second caller tries contract B with same idem_key: INSERT fails (idempotency_key UNIQUE conflict)
    # Query finds: (contract_a, shared_idem) — different contract, same key
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # fetchone: INSERT returns None (conflict on idempotency_key)
        # fetchall: SELECT finds (contract_a, shared_idem) which is different contract, same key
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = [(contract_a, shared_idem)]

        result_b = claim_contract_execution(contract_b, "user_2", shared_idem)
        chk("Scenario C: contract B IDEMPOTENCY_CONFLICT", result_b.is_idempotency_conflict())


# ══════════════════════════════════════════════════════════════════
# Test 4: Different contracts + different idempotency_keys (independent)
# ══════════════════════════════════════════════════════════════════

def test_mock_diff_contracts_diff_idem():
    """
    Scenario D: Different contracts, different idempotency_keys (independent claims).
    Both callers get ACQUIRED (no conflict).
    """
    from core.atomic_claim_repository import claim_contract_execution

    contract_a = "test-contract-A"
    contract_b = "test-contract-B"
    idem_a = "idem-A"
    idem_b = "idem-B"

    # Caller 1: INSERT succeeds for contract A
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchone.return_value = (contract_a,)
        result_a = claim_contract_execution(contract_a, "user_1", idem_a)
        chk("Scenario D: contract A ACQUIRED", result_a.is_acquired())

    # Caller 2: INSERT succeeds for contract B (no conflict with A)
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchone.return_value = (contract_b,)
        result_b = claim_contract_execution(contract_b, "user_2", idem_b)
        chk("Scenario D: contract B ACQUIRED (independent)", result_b.is_acquired())






# ══════════════════════════════════════════════════════════════════
# Test 5: New result types are properly defined
# ══════════════════════════════════════════════════════════════════

def test_new_result_types():
    """Verify new result types are valid."""
    from core.atomic_claim_repository import ClaimAcquisitionResult

    # Test IDEMPOTENCY_CONFLICT
    result_idem = ClaimAcquisitionResult(result="idempotency_conflict", error="test conflict")
    chk("New type: is_idempotency_conflict() method exists", hasattr(result_idem, "is_idempotency_conflict"))
    chk("New type: is_idempotency_conflict() returns True", result_idem.is_idempotency_conflict())

    # Test CONTRACT_IDENTITY_CONFLICT
    result_contract = ClaimAcquisitionResult(result="contract_identity_conflict", error="test conflict")
    chk("New type: is_contract_identity_conflict() method exists", hasattr(result_contract, "is_contract_identity_conflict"))
    chk("New type: is_contract_identity_conflict() returns True", result_contract.is_contract_identity_conflict())

    # Verify they're distinct
    chk("New types: distinct from each other", result_idem.is_idempotency_conflict() and not result_idem.is_contract_identity_conflict())


# ══════════════════════════════════════════════════════════════════
# Test 6: Atomic executor handles new result types
# ══════════════════════════════════════════════════════════════════

def test_executor_handles_contract_identity_conflict():
    """Verify execute_with_atomic_claim handles CONTRACT_IDENTITY_CONFLICT as failure (fail-closed)."""
    from core.action_gateway_atomic_executor import execute_with_atomic_claim
    from core.atomic_claim_repository import ClaimAcquisitionResult

    mock_executor = MagicMock(return_value={"ok": True})

    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim:
            mock_claim.return_value = ClaimAcquisitionResult(
                result="contract_identity_conflict",
                error="Contract already being executed"
            )

            success, result, error = execute_with_atomic_claim(
                contract_id="test-contract",
                canonical_user_id="user_1",
                tool_name="test_tool",
                tool_inputs={},
                identity=None,
                executor_fn=mock_executor,
            )

            chk("Executor: CONTRACT_IDENTITY_CONFLICT blocks execution", not success)
            chk("Executor: error message present", error is not None)
            chk("Executor: executor NOT called", not mock_executor.called)


def test_executor_handles_idempotency_conflict():
    """Verify execute_with_atomic_claim handles IDEMPOTENCY_CONFLICT as failure (fail-closed)."""
    from core.action_gateway_atomic_executor import execute_with_atomic_claim
    from core.atomic_claim_repository import ClaimAcquisitionResult

    mock_executor = MagicMock(return_value={"ok": True})

    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim:
            mock_claim.return_value = ClaimAcquisitionResult(
                result="idempotency_conflict",
                error="Idempotency key already used for different contract"
            )

            success, result, error = execute_with_atomic_claim(
                contract_id="test-contract",
                canonical_user_id="user_1",
                tool_name="test_tool",
                tool_inputs={},
                identity=None,
                executor_fn=mock_executor,
            )

            chk("Executor: IDEMPOTENCY_CONFLICT blocks execution", not success)
            chk("Executor: error message present", error is not None)
            chk("Executor: executor NOT called", not mock_executor.called)


# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("Phase 4B0.1B — Concurrency Regression Tests (MOCK/Local)")
    print("Untargeted ON CONFLICT DO NOTHING + conflict classification")
    print("Real PostgreSQL tests: see PHASE_4B0_CONCURRENCY_REGRESSION_GUIDE.md")
    print("=" * 70)
    print()

    test_mock_same_contract_same_idem()
    print()
    test_mock_same_contract_diff_idem()
    print()
    test_mock_diff_contracts_same_idem()
    print()
    test_mock_diff_contracts_diff_idem()
    print()
    test_new_result_types()
    print()
    test_executor_handles_contract_identity_conflict()
    print()
    test_executor_handles_idempotency_conflict()

    print()
    print("=" * 70)
    print(f"PASSED: {passed} | FAILED: {failed}")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
