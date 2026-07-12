# core/atomic_claim_repository.py — PostgreSQL-backed atomic execution claims
#
# Phase 4B0.1A/B — transactional coordination for ActionContract execution.
# Every execution claim is atomic: only the caller receiving an ACQUIRED result
# has the right to proceed to dispatch_tool(). All other callers (duplicates,
# concurrent requests) must stop before execution.
#
# Claim ownership: INSERT ... ON CONFLICT ... DO NOTHING RETURNING contract_id
# If the row is returned, this caller wins the race and owns the contract.
# If None is returned, another caller already owns it — stop immediately.
#
# Result types (explicit, not ambiguous None):
#   - ACQUIRED: this caller won the race, acquired claim, may proceed to dispatch
#   - ALREADY_CLAIMED: another caller owns this contract, stop before execution
#   - UNAVAILABLE: PostgreSQL down or migrations not run — fail closed, never proceed
#   - DISABLED: FEATURE_ATOMIC_CLAIMS flag is OFF
#   - ERROR: unexpected error during claim attempt
#
# Claim status lifecycle (once ACQUIRED):
#   - executing: claim acquired, execution in progress
#   - completed: execution succeeded (tool result recorded in Airtable contract)
#   - failed: execution failed (error recorded in last_error, contract preserved)
#   - outcome_unknown: execution may have succeeded or failed (unclear)
#     Never automatically retry outcome_unknown — investigate manually.
#
# Fail-closed semantics: when FEATURE_ATOMIC_CLAIMS is ON and PostgreSQL is DOWN,
# claim_contract_execution() returns UNAVAILABLE. Caller must NOT fall back to
# legacy execution path — must fail the entire action closed.
#
# Feature flag: FEATURE_ATOMIC_CLAIMS (default OFF)
# Only active when flag is ON and PostgreSQL is configured.

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional, Literal

logger = logging.getLogger(__name__)

# Claim status constants
STATUS_EXECUTING = "executing"  # claim acquired, execution in progress
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_OUTCOME_UNKNOWN = "outcome_unknown"

ExecutionOutcome = Literal["completed", "failed", "outcome_unknown"]
ClaimResult = Literal["acquired", "already_claimed", "unavailable", "disabled", "error"]


@dataclass
class ClaimAcquisitionResult:
    """
    Explicit result type for claim acquisition attempts.
    Only ACQUIRED results may proceed to dispatch_tool().
    """
    result: ClaimResult
    claim: Optional[AtomicExecutionClaim] = None
    error: Optional[str] = None

    def is_acquired(self) -> bool:
        """Returns True only if this caller won the race and may proceed to dispatch."""
        return self.result == "acquired"

    def is_already_claimed(self) -> bool:
        """Returns True if another caller already owns this contract."""
        return self.result == "already_claimed"

    def is_unavailable(self) -> bool:
        """Returns True if PostgreSQL is down (fail-closed)."""
        return self.result == "unavailable"

    def is_disabled(self) -> bool:
        """Returns True if FEATURE_ATOMIC_CLAIMS flag is OFF."""
        return self.result == "disabled"

    def is_error(self) -> bool:
        """Returns True if an unexpected error occurred."""
        return self.result == "error"


class AtomicExecutionClaim:
    """
    A claim to execute an ActionContract.
    Only the holder of a claim (status=EXECUTING) may proceed to dispatch_tool().
    """

    def __init__(
        self,
        contract_id: str,
        claimant_id: str,
        execution_id: str,
        claimed_at: float,
        idempotency_key: Optional[str] = None,
    ):
        self.contract_id = contract_id
        self.claimant_id = claimant_id
        self.execution_id = execution_id
        self.claimed_at = claimed_at
        self.idempotency_key = idempotency_key or str(uuid.uuid4())
        self.status = STATUS_EXECUTING  # claim acquired, execution in progress
        self.completed_at: Optional[float] = None
        self.last_error: Optional[str] = None

    def mark_completed(self) -> None:
        """Mark this claim as successfully completed."""
        self.status = STATUS_COMPLETED
        self.completed_at = time.time()

    def mark_failed(self, error: str) -> None:
        """Mark this claim as failed with an error message."""
        self.status = STATUS_FAILED
        self.completed_at = time.time()
        self.last_error = error

    def mark_outcome_unknown(self, error: str) -> None:
        """Mark this claim with unknown outcome (don't auto-retry)."""
        self.status = STATUS_OUTCOME_UNKNOWN
        self.completed_at = time.time()
        self.last_error = error


def claim_contract_execution(
    contract_id: str,
    claimant_id: str,
    idempotency_key: Optional[str] = None,
) -> ClaimAcquisitionResult:
    """
    Attempt to claim ownership of a contract for execution.

    Args:
        contract_id: ActionContract.contract_id
        claimant_id: canonical_user_id of the caller (e.g. "boss_hq:owner_1")
        idempotency_key: optional key for retry-safety

    Returns:
        ClaimAcquisitionResult with one of:
          - ACQUIRED: this caller won the race, claim is ready to use, status=executing
          - ALREADY_CLAIMED: another caller owns this contract, stop before execution
          - UNAVAILABLE: PostgreSQL down or not configured (fail-closed, never proceed)
          - DISABLED: FEATURE_ATOMIC_CLAIMS flag is OFF
          - ERROR: unexpected error during claim attempt

    Only ACQUIRED results may proceed to dispatch_tool().
    All other results must stop before execution (fail-closed).

    Idempotency: same idempotency_key prevents duplicate rows if retried.
    """
    from feature_flags import is_enabled

    if not is_enabled("FEATURE_ATOMIC_CLAIMS"):
        logger.debug(
            f"FEATURE_ATOMIC_CLAIMS disabled — claim_contract_execution skipped "
            f"(contract_id={contract_id})"
        )
        return ClaimAcquisitionResult(result="disabled")

    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        logger.error(
            f"PostgreSQL unavailable (fail-closed) — claim_contract_execution failed "
            f"(contract_id={contract_id}). Never fall back to legacy execution path."
        )
        return ClaimAcquisitionResult(
            result="unavailable",
            error="PostgreSQL not available or not configured"
        )

    try:
        execution_id = str(uuid.uuid4())
        idempotency_key = idempotency_key or str(uuid.uuid4())
        claimed_at = time.time()

        with conn.cursor() as cur:
            # Atomic claim: only one caller wins.
            cur.execute(
                """
                INSERT INTO action_execution_claims
                (contract_id, claimant_id, execution_id, status, claimed_at, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (contract_id) DO NOTHING
                RETURNING contract_id;
                """,
                (contract_id, claimant_id, execution_id, STATUS_EXECUTING, claimed_at, idempotency_key),
            )
            result = cur.fetchone()
            conn.commit()

        if result is None:
            logger.info(
                f"Claim rejected (contract already claimed by another caller): "
                f"contract_id={contract_id}, attempted_claimant={claimant_id}"
            )
            return ClaimAcquisitionResult(result="already_claimed")

        claim = AtomicExecutionClaim(
            contract_id=contract_id,
            claimant_id=claimant_id,
            execution_id=execution_id,
            claimed_at=claimed_at,
            idempotency_key=idempotency_key,
        )
        logger.info(
            f"Claim acquired (execution ownership acquired): "
            f"contract_id={contract_id}, claimant_id={claimant_id}, execution_id={execution_id}"
        )
        return ClaimAcquisitionResult(result="acquired", claim=claim)

    except Exception as e:
        logger.error(
            f"Error claiming contract execution: contract_id={contract_id}, error={e}"
        )
        return ClaimAcquisitionResult(
            result="error",
            error=str(e)
        )
    finally:
        release_conn(conn)


def update_claim_status(
    contract_id: str,
    outcome: ExecutionOutcome,
    error: Optional[str] = None,
) -> bool:
    """
    Update the status of an execution claim after dispatch_tool() completes.

    Args:
        contract_id: ActionContract.contract_id
        outcome: one of "completed", "failed", "outcome_unknown"
        error: optional error message if outcome is "failed" or "outcome_unknown"

    Returns:
        True if update succeeded, False otherwise.

    Note:
        This is a separate step from claim_contract_execution() to allow
        the caller to dispatch_tool() and record the result before updating
        the claim status. The Airtable ActionContract is the durable record;
        this table tracks execution ownership only.
    """
    from feature_flags import is_enabled

    if not is_enabled("FEATURE_ATOMIC_CLAIMS"):
        logger.debug(
            f"FEATURE_ATOMIC_CLAIMS disabled — update_claim_status skipped "
            f"(contract_id={contract_id})"
        )
        return True

    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        logger.warning(
            f"PostgreSQL not configured — update_claim_status failed "
            f"(contract_id={contract_id})"
        )
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE action_execution_claims
                SET status = %s, completed_at = %s, last_error = %s
                WHERE contract_id = %s;
                """,
                (outcome, time.time(), error, contract_id),
            )
            conn.commit()
        logger.info(
            f"Claim status updated: contract_id={contract_id}, outcome={outcome}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Error updating claim status: contract_id={contract_id}, error={e}"
        )
        return False
    finally:
        release_conn(conn)


def get_claim(contract_id: str) -> Optional[AtomicExecutionClaim]:
    """
    Retrieve an existing claim for a contract (read-only).
    Used for diagnostics and status checks, not for ownership changes.

    Returns:
        AtomicExecutionClaim if claim exists, None otherwise.
    """
    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        logger.debug("PostgreSQL not configured — get_claim skipped")
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT contract_id, claimant_id, execution_id, status, claimed_at,
                       completed_at, idempotency_key, last_error
                FROM action_execution_claims
                WHERE contract_id = %s;
                """,
                (contract_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        claim = AtomicExecutionClaim(
            contract_id=row[0],
            claimant_id=row[1],
            execution_id=row[2],
            claimed_at=row[4],
            idempotency_key=row[6],
        )
        claim.status = row[3]
        claim.completed_at = row[5]
        claim.last_error = row[7]
        return claim

    except Exception as e:
        logger.error(f"Error retrieving claim: contract_id={contract_id}, error={e}")
        return None
    finally:
        release_conn(conn)


def list_pending_claims(
    limit: int = 100,
) -> list[AtomicExecutionClaim]:
    """
    List all pending claims (for diagnostics/monitoring).

    Args:
        limit: maximum number of claims to return

    Returns:
        List of AtomicExecutionClaim objects with status=pending.
    """
    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        logger.debug("PostgreSQL not configured — list_pending_claims skipped")
        return []

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT contract_id, claimant_id, execution_id, status, claimed_at,
                       completed_at, idempotency_key, last_error
                FROM action_execution_claims
                WHERE status = %s
                ORDER BY claimed_at DESC
                LIMIT %s;
                """,
                (STATUS_PENDING, limit),
            )
            rows = cur.fetchall()

        claims = []
        for row in rows:
            claim = AtomicExecutionClaim(
                contract_id=row[0],
                claimant_id=row[1],
                execution_id=row[2],
                claimed_at=row[4],
                idempotency_key=row[6],
            )
            claim.status = row[3]
            claim.completed_at = row[5]
            claim.last_error = row[7]
            claims.append(claim)

        return claims

    except Exception as e:
        logger.error(f"Error listing pending claims: {e}")
        return []
    finally:
        release_conn(conn)
