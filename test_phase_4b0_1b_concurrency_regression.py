#!/usr/bin/env python3
"""
test_phase_4b0_1b_concurrency_regression.py — Phase 4B0.1B real concurrency regression tests

CRITICAL: Tests real PostgreSQL concurrency to verify idempotency_key constraint handling.

Previous bug: idempotency_key uniqueness violations were not handled atomically.
When racer 2 tried to claim with duplicate idempotency_key (different contract), it returned
ERROR instead of IDEMPOTENCY_CONFLICT.

This suite verifies the fix by testing three concurrent scenarios:

1. Same contract + same idempotency_key (retry):
   → One ACQUIRED (winner), one ALREADY_CLAIMED (loser, same contract)

2. Same contract + different idempotency_key (concurrent approvals):
   → One ACQUIRED (winner), one ALREADY_CLAIMED (loser, same contract)

3. Different contracts + same idempotency_key (identity mismatch / bug):
   → One ACQUIRED (winner contract A), one IDEMPOTENCY_CONFLICT (loser contract B)

All tests use real PostgreSQL connection (no mocks).
Tests are idempotent — safe to run repeatedly against same database.
"""

from __future__ import annotations

import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

os.environ.setdefault("FEATURE_ATOMIC_CLAIMS", "true")  # Enable for real tests

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def cleanup_test_contracts(*contract_ids: str) -> None:
    """Delete test contracts from database to allow re-runs."""
    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            for cid in contract_ids:
                cur.execute(
                    "DELETE FROM action_execution_claims WHERE contract_id = %s;",
                    (cid,),
                )
            conn.commit()
    except Exception as e:
        print(f"⚠️  Cleanup failed: {e}")
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════
# Test 1: Same contract + same idempotency_key (retry safety)
# ══════════════════════════════════════════════════════════════════

def test_same_contract_same_idempotency_key():
    """
    Scenario: Two threads try to claim the same contract with the same idempotency_key.
    Expected: One ACQUIRED, one ALREADY_CLAIMED (both refer to same contract).
    """
    from core.atomic_claim_repository import claim_contract_execution

    contract_id = "test-contract-retry-safety-1"
    idempotency_key = "test-idem-key-retry-1"
    cleanup_test_contracts(contract_id)

    results = []
    barrier = threading.Barrier(2)

    def attempt_claim(thread_id: int):
        """Attempt to claim with synchronized barrier."""
        barrier.wait()  # Ensure both threads start simultaneously
        result = claim_contract_execution(
            contract_id=contract_id,
            claimant_id=f"approver_{thread_id}",
            idempotency_key=idempotency_key,
        )
        results.append({"thread": thread_id, "result": result.result})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt_claim, i) for i in [1, 2]]
        for future in as_completed(futures):
            future.result()

    acquired = [r for r in results if r["result"] == "acquired"]
    already_claimed = [r for r in results if r["result"] == "already_claimed"]

    chk(
        "Same contract + same idempotency_key: exactly one ACQUIRED",
        len(acquired) == 1
    )
    chk(
        "Same contract + same idempotency_key: exactly one ALREADY_CLAIMED",
        len(already_claimed) == 1
    )
    chk(
        "Same contract + same idempotency_key: no errors or conflicts",
        len(acquired) + len(already_claimed) == 2
    )

    cleanup_test_contracts(contract_id)


# ══════════════════════════════════════════════════════════════════
# Test 2: Same contract + different idempotency_key (concurrent approvals)
# ══════════════════════════════════════════════════════════════════

def test_same_contract_different_idempotency_keys():
    """
    Scenario: Two threads try to claim the same contract with DIFFERENT idempotency_keys.
    Expected: One ACQUIRED (wins contract), one CONTRACT_IDENTITY_CONFLICT (loses, concurrent execution attempt).
    """
    from core.atomic_claim_repository import claim_contract_execution

    contract_id = "test-contract-concurrent-approvals-1"
    cleanup_test_contracts(contract_id)

    results = []
    barrier = threading.Barrier(2)

    def attempt_claim(thread_id: int):
        """Attempt to claim with different idempotency_key per thread."""
        barrier.wait()  # Ensure both threads start simultaneously
        result = claim_contract_execution(
            contract_id=contract_id,
            claimant_id=f"approver_{thread_id}",
            idempotency_key=f"test-idem-key-concurrent-{thread_id}",  # Different per thread
        )
        results.append({"thread": thread_id, "result": result.result})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt_claim, i) for i in [1, 2]]
        for future in as_completed(futures):
            future.result()

    acquired = [r for r in results if r["result"] == "acquired"]
    contract_identity_conflicts = [r for r in results if r["result"] == "contract_identity_conflict"]

    chk(
        "Same contract + different idempotency_keys: exactly one ACQUIRED",
        len(acquired) == 1
    )
    chk(
        "Same contract + different idempotency_keys: exactly one CONTRACT_IDENTITY_CONFLICT",
        len(contract_identity_conflicts) == 1
    )
    chk(
        "Same contract + different idempotency_keys: zero ALREADY_CLAIMED",
        len([r for r in results if r["result"] == "already_claimed"]) == 0
    )

    cleanup_test_contracts(contract_id)


# ══════════════════════════════════════════════════════════════════
# Test 3: Different contracts + same idempotency_key (identity mismatch)
# ══════════════════════════════════════════════════════════════════

def test_different_contracts_same_idempotency_key():
    """
    Scenario: Two threads try to claim DIFFERENT contracts with the SAME idempotency_key.
    This should not happen in normal usage (indicates identity/session mismatch).
    Expected: One ACQUIRED (contract A), one IDEMPOTENCY_CONFLICT (contract B, fail-closed).
    """
    from core.atomic_claim_repository import claim_contract_execution

    contract_a = "test-contract-identity-mismatch-A"
    contract_b = "test-contract-identity-mismatch-B"
    idempotency_key = "test-idem-key-identity-mismatch-1"
    cleanup_test_contracts(contract_a, contract_b)

    results = []
    barrier = threading.Barrier(2)

    def attempt_claim(thread_id: int, contract_id: str):
        """Attempt to claim different contract with same idempotency_key."""
        barrier.wait()  # Ensure both threads start simultaneously
        result = claim_contract_execution(
            contract_id=contract_id,
            claimant_id=f"approver_{thread_id}",
            idempotency_key=idempotency_key,  # Same for both
        )
        results.append({"thread": thread_id, "contract": contract_id, "result": result.result})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt_claim, 1, contract_a),
            executor.submit(attempt_claim, 2, contract_b),
        ]
        for future in as_completed(futures):
            future.result()

    acquired = [r for r in results if r["result"] == "acquired"]
    idempotency_conflicts = [r for r in results if r["result"] == "idempotency_conflict"]

    chk(
        "Different contracts + same idempotency_key: exactly one ACQUIRED",
        len(acquired) == 1
    )
    chk(
        "Different contracts + same idempotency_key: exactly one IDEMPOTENCY_CONFLICT",
        len(idempotency_conflicts) == 1
    )
    chk(
        "Different contracts + same idempotency_key: winner gets contract A or B",
        acquired[0]["contract"] in [contract_a, contract_b] if acquired else False
    )
    chk(
        "Different contracts + same idempotency_key: loser gets different contract",
        len(idempotency_conflicts) == 1 and idempotency_conflicts[0]["contract"] != acquired[0]["contract"]
    )

    cleanup_test_contracts(contract_a, contract_b)


# ══════════════════════════════════════════════════════════════════
# Test 4: Idempotent re-runs (same contracts, same database)
# ══════════════════════════════════════════════════════════════════

def test_idempotent_reruns():
    """
    Scenario: Run the same test multiple times against the same database state.
    Expected: Results are consistent across runs (idempotent).
    """
    from core.atomic_claim_repository import claim_contract_execution

    contract_id = "test-contract-idempotent-1"

    # Run 1: Fresh claim
    cleanup_test_contracts(contract_id)
    result_1 = claim_contract_execution(
        contract_id=contract_id,
        claimant_id="approver_1",
        idempotency_key="test-idem-idempotent-1",
    )

    chk("Idempotent run 1: First claim succeeds (ACQUIRED)", result_1.is_acquired())

    # Run 2: Same claim again (should be idempotent — still owned by same contract)
    result_2 = claim_contract_execution(
        contract_id=contract_id,
        claimant_id="approver_1",
        idempotency_key="test-idem-idempotent-1",  # Same idempotency_key
    )

    chk("Idempotent run 2: Same claim with same idempotency_key (ALREADY_CLAIMED)",
        result_2.is_already_claimed())

    # Run 3: Different claimant, same contract (should be rejected as concurrent execution attempt)
    result_3 = claim_contract_execution(
        contract_id=contract_id,
        claimant_id="approver_2",
        idempotency_key="test-idem-idempotent-2",  # Different idempotency_key
    )

    chk("Idempotent run 3: Different claimant, different idempotency_key (CONTRACT_IDENTITY_CONFLICT)",
        result_3.is_contract_identity_conflict())

    # Run 4: New contract with same idempotency_key (should conflict)
    result_4 = claim_contract_execution(
        contract_id="test-contract-idempotent-2",  # Different contract
        claimant_id="approver_3",
        idempotency_key="test-idem-idempotent-1",  # Same as run 1
    )

    chk("Idempotent run 4: New contract with existing idempotency_key (IDEMPOTENCY_CONFLICT)",
        result_4.is_idempotency_conflict())

    cleanup_test_contracts(contract_id, "test-contract-idempotent-2")


# ══════════════════════════════════════════════════════════════════
# Test 5: PostgreSQL constraint verification
# ══════════════════════════════════════════════════════════════════

def test_schema_constraints():
    """
    Verify that database schema has correct constraints in place:
    - contract_id PRIMARY KEY (unique, not null)
    - idempotency_key UNIQUE (allows multiple nulls)
    """
    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        chk("PostgreSQL available", False)
        return

    try:
        with conn.cursor() as cur:
            # Check for PRIMARY KEY on contract_id
            cur.execute(
                """
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'action_execution_claims' AND constraint_type = 'PRIMARY KEY';
                """
            )
            pk = cur.fetchone()
            chk("Schema: PRIMARY KEY exists", pk is not None)

            # Check for UNIQUE constraint on idempotency_key
            cur.execute(
                """
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'action_execution_claims' AND constraint_type = 'UNIQUE';
                """
            )
            unique_constraints = cur.fetchall()
            has_idem_unique = any(
                "idempotency_key" in str(c[0]).lower() for c in unique_constraints
            )
            chk("Schema: UNIQUE constraint on idempotency_key exists", has_idem_unique)

            # Check for indices
            cur.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'action_execution_claims';
                """
            )
            indices = cur.fetchall()
            chk("Schema: indices exist", len(indices) > 0)

    except Exception as e:
        chk(f"Schema validation failed: {e}", False)
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("Phase 4B0.1B — Concurrency Regression Tests (Real PostgreSQL)")
    print("=" * 70)
    print()

    # Verify PostgreSQL is available and schema is correct
    test_schema_constraints()
    print()

    # Run regression tests
    test_same_contract_same_idempotency_key()
    print()
    test_same_contract_different_idempotency_keys()
    print()
    test_different_contracts_same_idempotency_key()
    print()
    test_idempotent_reruns()

    print()
    print("=" * 70)
    print(f"PASSED: {passed} | FAILED: {failed}")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
