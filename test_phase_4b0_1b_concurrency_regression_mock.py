#!/usr/bin/env python3
"""
test_phase_4b0_1b_concurrency_regression_mock.py — Mock version of regression tests

Tests the idempotency_conflict fix locally using mocks.
Real PostgreSQL tests must run on Render staging: see PHASE_4B0_CONCURRENCY_REGRESSION_GUIDE.md

Mocks the three critical scenarios:
1. Same contract + same idempotency_key (retry) → ACQUIRED + ALREADY_CLAIMED
2. Same contract + different idempotency_key (concurrent) → ACQUIRED + ALREADY_CLAIMED
3. Different contracts + same idempotency_key (conflict) → ACQUIRED + IDEMPOTENCY_CONFLICT
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
# Test 1: Same contract + same idempotency_key returns ACQUIRED then ALREADY_CLAIMED
# ══════════════════════════════════════════════════════════════════

def test_mock_same_contract_same_idem():
    """Mock: first caller ACQUIRED, second caller ALREADY_CLAIMED."""
    from core.atomic_claim_repository import claim_contract_execution

    contract_id = "test-contract-A"
    idem_key = "idem-1"

    # First caller: INSERT succeeds, gets row back
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate INSERT success (row returned)
        mock_cursor.fetchone.return_value = (contract_id,)

        result1 = claim_contract_execution(contract_id, "user_1", idem_key)
        chk("Mock same contract + same idem: first caller ACQUIRED", result1.is_acquired())

    # Second caller: INSERT fails (no row), but query finds the contract
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate INSERT failure (no row returned)
        # Then query finds contract exists
        mock_cursor.fetchone.side_effect = [
            None,  # INSERT returns no row
            (contract_id,),  # SELECT contract_id found
        ]

        result2 = claim_contract_execution(contract_id, "user_2", idem_key)
        chk("Mock same contract + same idem: second caller ALREADY_CLAIMED", result2.is_already_claimed())


# ══════════════════════════════════════════════════════════════════
# Test 2: Same contract + different idempotency_key returns ACQUIRED then ALREADY_CLAIMED
# ══════════════════════════════════════════════════════════════════

def test_mock_same_contract_diff_idem():
    """Mock: first caller ACQUIRED, second caller ALREADY_CLAIMED (different idem_key)."""
    from core.atomic_claim_repository import claim_contract_execution

    contract_id = "test-contract-B"

    # First caller: INSERT succeeds
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchone.return_value = (contract_id,)

        result1 = claim_contract_execution(contract_id, "user_1", "idem-1")
        chk("Mock same contract + diff idem: first caller ACQUIRED", result1.is_acquired())

    # Second caller: different idem_key, same contract, still loses
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # INSERT fails, query finds contract exists
        mock_cursor.fetchone.side_effect = [
            None,  # INSERT returns no row
            (contract_id,),  # SELECT contract_id found
        ]

        result2 = claim_contract_execution(contract_id, "user_2", "idem-2")
        chk("Mock same contract + diff idem: second caller ALREADY_CLAIMED", result2.is_already_claimed())


# ══════════════════════════════════════════════════════════════════
# Test 3: Different contracts + same idempotency_key returns ACQUIRED then IDEMPOTENCY_CONFLICT
# ══════════════════════════════════════════════════════════════════

def test_mock_diff_contracts_same_idem():
    """Mock: first caller (contract A) ACQUIRED, second caller (contract B) IDEMPOTENCY_CONFLICT."""
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
        chk("Mock diff contracts + same idem: contract A ACQUIRED", result_a.is_acquired())

    # Second caller tries contract B with same idem_key: INSERT fails on idem_key uniqueness
    # Query finds contract doesn't exist, but idem_key exists under contract A
    with patch('core.database.get_conn') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # INSERT fails (no row returned)
        # SELECT contract_id returns None (contract B doesn't exist)
        # SELECT idempotency_key returns contract A (idem_key exists there)
        mock_cursor.fetchone.side_effect = [
            None,  # INSERT returns no row (idem_key uniqueness violation)
            None,  # SELECT contract_id (contract_b) not found
            (contract_a,),  # SELECT idempotency_key found under contract_a
        ]

        result_b = claim_contract_execution(contract_b, "user_2", shared_idem)
        chk("Mock diff contracts + same idem: contract B IDEMPOTENCY_CONFLICT", result_b.is_idempotency_conflict())
        chk("Mock diff contracts + same idem: error message mentions conflict",
            "conflict" in (result_b.error or "").lower() or "idempotency" in (result_b.error or "").lower())


# ══════════════════════════════════════════════════════════════════
# Test 4: New result type is properly defined
# ══════════════════════════════════════════════════════════════════

def test_new_result_type():
    """Verify IDEMPOTENCY_CONFLICT is a valid result type."""
    from core.atomic_claim_repository import ClaimAcquisitionResult

    result = ClaimAcquisitionResult(result="idempotency_conflict", error="test conflict")
    chk("New type: is_idempotency_conflict() method exists", hasattr(result, "is_idempotency_conflict"))
    chk("New type: is_idempotency_conflict() returns True", result.is_idempotency_conflict())
    chk("New type: other checks return False",
        not result.is_acquired() and not result.is_already_claimed() and not result.is_disabled())


# ══════════════════════════════════════════════════════════════════
# Test 5: Atomic executor handles new result type
# ══════════════════════════════════════════════════════════════════

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

            chk("Executor: IDEMPOTENCY_CONFLICT blocks execution (not success)", not success)
            chk("Executor: error message present", error is not None)
            chk("Executor: executor NOT called", not mock_executor.called)


# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("Phase 4B0.1B — Concurrency Regression Tests (MOCK/Local)")
    print("Real PostgreSQL tests: see PHASE_4B0_CONCURRENCY_REGRESSION_GUIDE.md")
    print("=" * 70)
    print()

    test_mock_same_contract_same_idem()
    print()
    test_mock_same_contract_diff_idem()
    print()
    test_mock_diff_contracts_same_idem()
    print()
    test_new_result_type()
    print()
    test_executor_handles_idempotency_conflict()

    print()
    print("=" * 70)
    print(f"PASSED: {passed} | FAILED: {failed}")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
