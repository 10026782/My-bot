# core/database.py — PostgreSQL connection pool for atomic coordination
#
# Phase 4B0.1 — transactional claims for ActionContract execution.
# Single source of truth for DB connection — all atomic operations route through
# get_pool() to ensure serialization and cache consistency.
#
# Feature flag: FEATURE_ATOMIC_CLAIMS (default OFF)
# Only activated when explicitly enabled + PostgreSQL env vars configured.

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_pool: Optional[object] = None  # psycopg2.pool.SimpleConnectionPool


def get_pool():
    """
    Lazy-initialize PostgreSQL connection pool.
    Returns None if PostgreSQL is not configured.

    Environment variables (all required):
      DATABASE_URL — full connection string (postgresql://user:password@host:port/dbname)
      or legacy format:
      DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD
    """
    global _pool

    if _pool is not None:
        return _pool

    try:
        import psycopg2
        from psycopg2 import pool
    except ImportError:
        logger.warning("psycopg2 not installed — atomic claims disabled")
        return None

    # Try DATABASE_URL first (Render standard)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            _pool = pool.SimpleConnectionPool(
                1, 5,
                db_url,
                connect_timeout=5
            )
            logger.info("PostgreSQL pool initialized from DATABASE_URL")
            return _pool
        except Exception as e:
            logger.error(f"Failed to initialize pool from DATABASE_URL: {e}")
            return None

    # Fall back to individual env vars
    host = os.getenv("DATABASE_HOST")
    port = os.getenv("DATABASE_PORT", "5432")
    name = os.getenv("DATABASE_NAME")
    user = os.getenv("DATABASE_USER")
    password = os.getenv("DATABASE_PASSWORD")

    if not all([host, name, user, password]):
        logger.debug("PostgreSQL env vars not fully configured — atomic claims disabled")
        return None

    try:
        _pool = pool.SimpleConnectionPool(
            1, 5,
            host=host,
            port=int(port),
            database=name,
            user=user,
            password=password,
            connect_timeout=5
        )
        logger.info("PostgreSQL pool initialized from env vars")
        return _pool
    except Exception as e:
        logger.error(f"Failed to initialize pool from env vars: {e}")
        return None


def get_conn():
    """Get a connection from the pool. Returns None if pool unavailable."""
    pool = get_pool()
    if pool is None:
        return None
    try:
        return pool.getconn()
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {e}")
        return None


def release_conn(conn):
    """Release a connection back to the pool."""
    if conn is not None:
        pool = get_pool()
        if pool is not None:
            try:
                pool.putconn(conn)
            except Exception as e:
                logger.error(f"Failed to release connection: {e}")
