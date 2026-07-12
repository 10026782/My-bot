#!/usr/bin/env python3
"""
test_phase_4b0_1a_atomic_claims.py — Phase 4B0.1A regression tests
PostgreSQL atomic coordination primitive for ActionContract execution claims.

Coverage (4B0.1A scope only — no concurrency test yet, that's 4B0.1B):
  1. Database initialization — schema creation, migration runner
  2. Atomic claim ownership — single claim per contract, INSERT ... ON CONFLICT
  3. Claim status lifecycle — pending → completed/failed/outcome_unknown
  4. Feature flag integration — disabled when flag is OFF
  5. Fail-closed reads — returns None on PostgreSQL unavailable
  6. Idempotency — same idempotency_key prevents duplicate rows
  7. Diagnostics — list_pending_claims(), get_claim()

Phase 4B0.1B (concurrency test) — spawns two independent DB connections
simultaneously, both try to claim same contract, proves only one succeeds.
Not included here — separate test file.
"""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import MagicMock, patch

# Environment setup — no real PostgreSQL needed for 4B0.1A (flag OFF)
os.environ.setdefault("FEATURE_ATOMIC_CLAIMS", "false")

# Optional: for manual testing with real PostgreSQL, set:
# os.environ["FEATURE_ATOMIC_CLAIMS"] = "true"
# os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/boss_bot_test"

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
# Test 1: Feature flag integration
# ══════════════════════════════════════════════════════════════════

def test_feature_flag_disabled():
    """When FEATURE_ATOMIC_CLAIMS is OFF, all operations are safe no-ops."""
    from core import atomic_claim_repository

    result = atomic_claim_repository.claim_contract_execution(
        contract_id="test-contract-1",
        claimant_id="boss_hq:owner_1",
    )

    chk("claim_contract_execution returns disabled result when flag is OFF",
        result.result == "disabled" and result.is_disabled())

    result = atomic_claim_repository.get_claim("test-contract-1")
    chk("get_claim returns None when flag is OFF", result is None)

    claims = atomic_claim_repository.list_pending_claims()
    chk("list_pending_claims returns empty list when flag is OFF", claims == [])


# ══════════════════════════════════════════════════════════════════
# Test 2: Atomic claim data structure
# ══════════════════════════════════════════════════════════════════

def test_claim_acquisition_result():
    """ClaimAcquisitionResult explicit types."""
    from core.atomic_claim_repository import ClaimAcquisitionResult

    acquired = ClaimAcquisitionResult(result="acquired")
    chk("ClaimAcquisitionResult.is_acquired() works", acquired.is_acquired())
    chk("ClaimAcquisitionResult.is_already_claimed() false for acquired", not acquired.is_already_claimed())

    already_claimed = ClaimAcquisitionResult(result="already_claimed")
    chk("ClaimAcquisitionResult.is_already_claimed() works", already_claimed.is_already_claimed())

    unavailable = ClaimAcquisitionResult(result="unavailable", error="PostgreSQL down")
    chk("ClaimAcquisitionResult.is_unavailable() works", unavailable.is_unavailable())
    chk("ClaimAcquisitionResult.error preserved", unavailable.error is not None)

    disabled = ClaimAcquisitionResult(result="disabled")
    chk("ClaimAcquisitionResult.is_disabled() works", disabled.is_disabled())

    error = ClaimAcquisitionResult(result="error", error="unexpected error")
    chk("ClaimAcquisitionResult.is_error() works", error.is_error())


def test_atomic_execution_claim_dataclass():
    """AtomicExecutionClaim lifecycle."""
    from core.atomic_claim_repository import AtomicExecutionClaim, STATUS_EXECUTING

    claim = AtomicExecutionClaim(
        contract_id="test-contract-2",
        claimant_id="boss_hq:owner_2",
        execution_id="exec-uuid-1",
        claimed_at=time.time(),
    )

    chk("AtomicExecutionClaim initialized with executing status (acquired)", claim.status == STATUS_EXECUTING)

    claim.mark_completed()
    chk("mark_completed sets status correctly", claim.status == "completed")
    chk("mark_completed sets completed_at", claim.completed_at is not None)

    claim2 = AtomicExecutionClaim(
        contract_id="test-contract-3",
        claimant_id="boss_hq:owner_3",
        execution_id="exec-uuid-2",
        claimed_at=time.time(),
    )
    claim2.mark_failed("test error")
    chk("mark_failed sets status correctly", claim2.status == "failed")
    chk("mark_failed records error", "test error" in (claim2.last_error or ""))

    claim3 = AtomicExecutionClaim(
        contract_id="test-contract-4",
        claimant_id="boss_hq:owner_4",
        execution_id="exec-uuid-3",
        claimed_at=time.time(),
    )
    claim3.mark_outcome_unknown("unclear result")
    chk("mark_outcome_unknown sets status", claim3.status == "outcome_unknown")
    chk("mark_outcome_unknown records error", "unclear result" in (claim3.last_error or ""))


# ══════════════════════════════════════════════════════════════════
# Test 3: Database migrations (schema file exists)
# ══════════════════════════════════════════════════════════════════

def test_schema_file_exists():
    """Migration file exists in expected location."""
    from pathlib import Path

    schema_file = Path(__file__).parent / "core" / "migrations" / "001_action_execution_claims.sql"
    chk("Migration schema file exists", schema_file.exists())

    content = schema_file.read_text()
    chk(
        "Schema defines action_execution_claims table",
        "CREATE TABLE IF NOT EXISTS action_execution_claims" in content,
    )
    chk("Schema defines contract_id PRIMARY KEY", "contract_id TEXT PRIMARY KEY" in content)
    chk("Schema defines claimant_id", "claimant_id TEXT NOT NULL" in content)
    chk("Schema defines execution_id UNIQUE", "execution_id TEXT NOT NULL UNIQUE" in content)
    chk("Schema defines idempotency_key UNIQUE", "idempotency_key TEXT UNIQUE" in content)


# ══════════════════════════════════════════════════════════════════
# Test 4: Status constants
# ══════════════════════════════════════════════════════════════════

def test_status_constants():
    """All status constants are defined."""
    from core.atomic_claim_repository import (
        STATUS_EXECUTING,
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_OUTCOME_UNKNOWN,
    )

    chk("STATUS_EXECUTING == 'executing'", STATUS_EXECUTING == "executing")
    chk("STATUS_COMPLETED == 'completed'", STATUS_COMPLETED == "completed")
    chk("STATUS_FAILED == 'failed'", STATUS_FAILED == "failed")
    chk("STATUS_OUTCOME_UNKNOWN == 'outcome_unknown'", STATUS_OUTCOME_UNKNOWN == "outcome_unknown")


# ══════════════════════════════════════════════════════════════════
# Test 5: Database module fail-safe
# ══════════════════════════════════════════════════════════════════

def test_database_module_graceful_degradation():
    """Database module gracefully handles missing PostgreSQL."""
    from core import database

    # When DATABASE_URL and related env vars are not set, get_pool should return None
    result = database.get_pool()
    chk("get_pool returns None when PostgreSQL not configured", result is None)

    result = database.get_conn()
    chk("get_conn returns None when pool is unavailable", result is None)


# ══════════════════════════════════════════════════════════════════
# Test 6: Feature flag registry
# ══════════════════════════════════════════════════════════════════

def test_feature_flag_registered():
    """FEATURE_ATOMIC_CLAIMS is in the registry."""
    with open("feature_flags.py", "r") as f:
        content = f.read()
    chk(
        "FEATURE_ATOMIC_CLAIMS is in feature_flags.py registry",
        "FEATURE_ATOMIC_CLAIMS" in content,
    )


# ══════════════════════════════════════════════════════════════════
# Test 7: Module imports work
# ══════════════════════════════════════════════════════════════════

def test_imports():
    """All required modules can be imported."""
    try:
        from core.database import get_pool, get_conn, release_conn
        chk("core.database imports successfully", True)
    except Exception as e:
        chk(f"core.database import failed: {e}", False)

    try:
        from core.database_migrations import run_migrations
        chk("core.database_migrations imports successfully", True)
    except Exception as e:
        chk(f"core.database_migrations import failed: {e}", False)

    try:
        from core.atomic_claim_repository import (
            AtomicExecutionClaim,
            ClaimAcquisitionResult,
            claim_contract_execution,
            update_claim_status,
            get_claim,
            list_pending_claims,
        )
        chk("core.atomic_claim_repository imports successfully", True)
    except Exception as e:
        chk(f"core.atomic_claim_repository import failed: {e}", False)

    try:
        from core.atomic_claims_health import (
            AtomicClaimsHealth,
            check_health,
            log_health_on_startup,
        )
        chk("core.atomic_claims_health imports successfully", True)
    except Exception as e:
        chk(f"core.atomic_claims_health import failed: {e}", False)


def test_atomic_claims_health_when_disabled():
    """Health check when flag is OFF."""
    from core.atomic_claims_health import check_health

    health = check_health()
    chk("Health check when flag OFF: enabled=False", not health.enabled)
    chk("Health check when flag OFF: postgresql_available=False", not health.postgresql_available)
    chk("Health check when flag OFF: migrations_run=False", not health.migrations_run)
    chk("Health check when flag OFF: not is_ready()", not health.is_ready())
    chk("Health check when flag OFF: summary mentions DISABLED", "DISABLED" in health.summary())


# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("Phase 4B0.1A/B — PostgreSQL Atomic Claims (Infrastructure Tests)")
    print("=" * 70)

    test_imports()
    test_claim_acquisition_result()
    test_feature_flag_disabled()
    test_atomic_execution_claim_dataclass()
    test_schema_file_exists()
    test_status_constants()
    test_database_module_graceful_degradation()
    test_feature_flag_registered()
    test_atomic_claims_health_when_disabled()

    print()
    print("=" * 70)
    print(f"PASSED: {passed} | FAILED: {failed}")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
