#!/usr/bin/env python3
"""
test_phase_4b0_1c_concurrent_approvals.py — Phase 4B0.1C concurrent approval test
Verify that concurrent approval requests result in exactly one dispatcher invocation.

STATUS: STAGING ONLY — test concurrent approvals with ActionGateway atomic wiring
(FEATURE_ATOMIC_CLAIMS=true in staging, false in production)

Coverage:
  1. Two concurrent approval requests for same ActionContract
  2. Exactly one reaches dispatch_tool() (claim acquired)
  3. Other gets "contract already executing" response
  4. No duplicate tool invocations
  5. Claim status reflects execution (completed/failed)
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock
from typing import Optional

os.environ.setdefault("FEATURE_ATOMIC_CLAIMS", "false")  # Flag OFF by default

# Per-run UUID to namespace all test contract IDs (prevents collisions on repeated staging runs)
TEST_RUN_ID = str(uuid.uuid4())[:8]

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
# Test 1: Atomic executor factory
# ══════════════════════════════════════════════════════════════════

def test_atomic_executor_import():
    """Atomic executor module can be imported."""
    try:
        from core.action_gateway_atomic_executor import (
            execute_with_atomic_claim,
            create_atomic_aware_executor,
        )
        chk("Atomic executor module imports successfully", True)
    except Exception as e:
        chk(f"Atomic executor import failed: {e}", False)


# ══════════════════════════════════════════════════════════════════
# Test 2: Atomic executor when flag OFF
# ══════════════════════════════════════════════════════════════════

def test_atomic_executor_flag_off():
    """When FEATURE_ATOMIC_CLAIMS=OFF, executor behaves as before."""
    from core.action_gateway_atomic_executor import execute_with_atomic_claim

    # Mock executor that just returns success
    def mock_executor(tool_name, tool_inputs, identity):
        return {"ok": True, "external_id": "test-id"}

    success, result, error = execute_with_atomic_claim(
        contract_id=f"test-contract-flag-off-{TEST_RUN_ID}",
        canonical_user_id="boss_hq:approver_1",
        tool_name="test_tool",
        tool_inputs={"param": "value"},
        identity=None,
        executor_fn=mock_executor,
    )

    chk("Atomic executor with flag OFF: success", success)
    chk("Atomic executor with flag OFF: result returned", result is not None)
    chk("Atomic executor with flag OFF: no error", error is None)


# ══════════════════════════════════════════════════════════════════
# Test 3: Atomic executor fail-closed when flag ON but DB down
# ══════════════════════════════════════════════════════════════════

def test_atomic_executor_fail_closed_db_down():
    """When FEATURE_ATOMIC_CLAIMS=ON but PostgreSQL unavailable: fail-closed."""
    from core.action_gateway_atomic_executor import execute_with_atomic_claim

    mock_executor = MagicMock(return_value={"ok": True})

    # Simulate flag ON but DB down
    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim:
            from core.atomic_claim_repository import ClaimAcquisitionResult
            mock_claim.return_value = ClaimAcquisitionResult(result="unavailable", error="DB down")

            success, result, error = execute_with_atomic_claim(
                contract_id=f"test-contract-fail-closed-{TEST_RUN_ID}",
                canonical_user_id="boss_hq:approver_1",
                tool_name="test_tool",
                tool_inputs={},
                identity=None,
                executor_fn=mock_executor,
            )

            chk("Fail-closed: execution blocked (not success)", not success)
            chk("Fail-closed: error message present", error is not None)
            chk("Fail-closed: executor NOT called", not mock_executor.called)


# ══════════════════════════════════════════════════════════════════
# Test 4: Concurrent approvals with claim gate (mock)
# ══════════════════════════════════════════════════════════════════

def test_concurrent_approvals_mock():
    """Mock concurrent approvals: only one reaches executor."""
    from core.action_gateway_atomic_executor import execute_with_atomic_claim

    contract_id = f"test-contract-concurrent-{TEST_RUN_ID}"
    executor_call_count = 0
    executor_call_lock = __import__("threading").Lock()

    def counting_executor(tool_name, tool_inputs, identity):
        nonlocal executor_call_count
        with executor_call_lock:
            executor_call_count += 1
        time.sleep(0.01)  # Simulate tool execution
        return {"ok": True, "external_id": f"exec-{executor_call_count}"}

    results = []
    results_lock = __import__("threading").Lock()

    def attempt_approval(approver_id: int):
        """Attempt approval from concurrent thread."""
        # Simulate: flag ON, first caller acquires, second gets already_claimed
        with patch('feature_flags.is_enabled', return_value=True):
            with patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim:
                from core.atomic_claim_repository import ClaimAcquisitionResult, AtomicExecutionClaim

                # First caller acquires
                if approver_id == 1:
                    claim = AtomicExecutionClaim(
                        contract_id=contract_id,
                        claimant_id=f"approver_{approver_id}",
                        execution_id=f"exec-{approver_id}",
                        claimed_at=time.time(),
                    )
                    mock_claim.return_value = ClaimAcquisitionResult(result="acquired", claim=claim)
                # Second caller gets already_claimed
                else:
                    mock_claim.return_value = ClaimAcquisitionResult(result="already_claimed")

                success, result, error = execute_with_atomic_claim(
                    contract_id=contract_id,
                    canonical_user_id=f"approver_{approver_id}",
                    tool_name="test_tool",
                    tool_inputs={},
                    identity=None,
                    executor_fn=counting_executor,
                )

                with results_lock:
                    results.append({
                        "approver": approver_id,
                        "success": success,
                        "error": error,
                    })

    # Launch two concurrent approvals
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt_approval, i) for i in [1, 2]]
        for future in as_completed(futures):
            future.result()

    # Verify results
    chk(f"Concurrent approvals: exactly one reached executor (got {executor_call_count})",
        executor_call_count == 1)

    succeeded = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    chk("Concurrent approvals: one succeeded", len(succeeded) == 1)
    chk("Concurrent approvals: one failed (already_claimed or conflict)", len(failed) == 1)


# ══════════════════════════════════════════════════════════════════
# Test 5: Atomic executor factory
# ══════════════════════════════════════════════════════════════════

def test_atomic_executor_factory():
    """create_atomic_aware_executor factory creates working executor."""
    from core.action_gateway_atomic_executor import create_atomic_aware_executor
    from core.action_gateway import ExecutionLedger

    # Create mock ledger
    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.find_by_id = MagicMock(return_value=None)

    # Create mock base executor
    mock_base_executor = MagicMock(return_value={"ok": True})

    # Create atomic executor
    atomic_exec = create_atomic_aware_executor(mock_ledger, mock_base_executor)

    chk("Atomic executor factory: returns callable", callable(atomic_exec))

    # Call it (should work with flag OFF) — use unique contract_id to avoid collisions
    try:
        result = atomic_exec("test_tool", {}, f"test-contract-factory-{TEST_RUN_ID}")
        chk("Atomic executor factory: callable executes", result is not None)
    except Exception as e:
        chk(f"Atomic executor factory: execution failed: {e}", False)


# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("Phase 4B0.1C — Concurrent Approvals with Atomic Claims")
    print("=" * 70)
    print()

    test_atomic_executor_import()
    test_atomic_executor_flag_off()
    test_atomic_executor_fail_closed_db_down()
    test_concurrent_approvals_mock()
    test_atomic_executor_factory()

    print()
    print("=" * 70)
    print(f"PASSED: {passed} | FAILED: {failed}")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
