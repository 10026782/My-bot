# core/database_migrations.py — PostgreSQL migration runner
#
# Phase 4B0.1A — schema initialization for atomic coordination.
# Run migrations on startup if PostgreSQL is configured.
# Idempotent — safe to call repeatedly.

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def run_migrations() -> bool:
    """
    Run all pending migrations from core/migrations/*.sql.
    Returns True if all migrations succeeded, False if any failed.
    Returns True (no-op) if PostgreSQL not configured.
    """
    from core.database import get_conn, release_conn

    pool = get_conn()
    if pool is None:
        logger.debug("PostgreSQL not configured — migrations skipped")
        return True

    try:
        conn = get_conn()
        if conn is None:
            logger.error("Failed to get database connection for migrations")
            return False

        migrations_dir = Path(__file__).parent / "migrations"
        if not migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {migrations_dir}")
            return True

        migration_files = sorted(migrations_dir.glob("*.sql"))
        if not migration_files:
            logger.debug("No migration files found")
            return True

        with conn.cursor() as cur:
            for migration_file in migration_files:
                try:
                    with open(migration_file, "r") as f:
                        sql = f.read()
                    logger.info(f"Running migration: {migration_file.name}")
                    cur.execute(sql)
                    conn.commit()
                    logger.info(f"Migration succeeded: {migration_file.name}")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Migration failed ({migration_file.name}): {e}")
                    return False

        return True

    except Exception as e:
        logger.error(f"Migration runner error: {e}")
        return False
    finally:
        if conn is not None:
            release_conn(conn)
