# core/atomic_claims_health.py — Health signals for atomic claims infrastructure
#
# Phase 4B0.1A/B — readiness checks for PostgreSQL atomic coordination.
# Provides structured diagnostics: is PostgreSQL available? Have migrations run?
# Used for health/readiness endpoints and debug logging.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AtomicClaimsHealth:
    """Health status of atomic claims infrastructure."""
    enabled: bool  # FEATURE_ATOMIC_CLAIMS flag
    postgresql_available: bool  # Can connect to PostgreSQL
    migrations_run: bool  # action_execution_claims table exists
    error: Optional[str] = None

    def is_ready(self) -> bool:
        """Returns True only if all systems healthy and claims are ready to use."""
        return self.enabled and self.postgresql_available and self.migrations_run

    def summary(self) -> str:
        """Human-readable status summary."""
        if not self.enabled:
            return "DISABLED: FEATURE_ATOMIC_CLAIMS=false"
        if not self.postgresql_available:
            return "UNAVAILABLE: PostgreSQL connection failed"
        if not self.migrations_run:
            return "UNAVAILABLE: migrations not executed (action_execution_claims table missing)"
        return "READY: atomic claims operational"


def check_health() -> AtomicClaimsHealth:
    """
    Check health of atomic claims infrastructure.
    Safe to call repeatedly (uses existing pool, no side effects).

    Returns:
        AtomicClaimsHealth with current status and optional error details.
    """
    from feature_flags import is_enabled

    enabled = is_enabled("FEATURE_ATOMIC_CLAIMS")

    if not enabled:
        return AtomicClaimsHealth(
            enabled=False,
            postgresql_available=False,
            migrations_run=False,
        )

    # PostgreSQL availability check
    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        return AtomicClaimsHealth(
            enabled=True,
            postgresql_available=False,
            migrations_run=False,
            error="PostgreSQL connection pool failed",
        )

    # Migrations check — does action_execution_claims table exist?
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'action_execution_claims'
                );
                """
            )
            exists = cur.fetchone()[0]

        if not exists:
            return AtomicClaimsHealth(
                enabled=True,
                postgresql_available=True,
                migrations_run=False,
                error="Table action_execution_claims does not exist (migrations not run)",
            )

        # All checks passed
        return AtomicClaimsHealth(
            enabled=True,
            postgresql_available=True,
            migrations_run=True,
        )

    except Exception as e:
        return AtomicClaimsHealth(
            enabled=True,
            postgresql_available=True,
            migrations_run=False,
            error=f"Migration check failed: {e}",
        )
    finally:
        release_conn(conn)


def log_health_on_startup() -> None:
    """
    Log atomic claims health at startup.
    Called from app.py initialization.

    When FEATURE_ATOMIC_CLAIMS is enabled:
    - Must have PostgreSQL available
    - Must have migrations already run
    - Startup FAILS (hard error, not warning) if either is missing

    Never allows graceful degradation: flag ON = atomic claims MUST be operational.
    """
    health = check_health()
    logger.info(f"Atomic claims health: {health.summary()}")

    if health.error:
        logger.error(f"Atomic claims infrastructure error: {health.error}")

    # Fail-closed: flag enabled but infrastructure not ready = fatal startup error
    if health.enabled and not health.is_ready():
        fatal_msg = (
            f"FATAL: FEATURE_ATOMIC_CLAIMS is enabled but infrastructure not ready.\n"
            f"  Status: {health.summary()}\n"
            f"  Error: {health.error}\n"
            f"  Action: Check PostgreSQL configuration, run migrations, or disable flag."
        )
        logger.critical(fatal_msg)
        raise RuntimeError(
            "Atomic claims infrastructure not ready. See logs for details. "
            "Never fall back to non-atomic execution."
        )
