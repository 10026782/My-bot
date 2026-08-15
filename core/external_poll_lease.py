"""PostgreSQL TTL lease for one external-job poll owner at a time."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class PollLease:
    job_id: str
    lease_token: str
    poller_id: str


class ExternalPollLeaseRepository:
    """Uses the existing PostgreSQL pool; never stores external job state."""

    def __init__(self, connection_factory=None, release_connection=None):
        if connection_factory is None:
            from core.database import get_conn
            connection_factory = get_conn
        if release_connection is None:
            from core.database import release_conn
            release_connection = release_conn
        self._get_conn = connection_factory
        self._release_conn = release_connection

    def acquire(self, job_id: str, poller_id: str, lease_seconds: int = 120) -> PollLease | None:
        token = str(uuid.uuid4())
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO external_poll_leases
                        (job_id, lease_token, poller_id, lease_expires_at)
                    VALUES (%s, %s, %s, NOW() + (%s * INTERVAL '1 second'))
                    ON CONFLICT (job_id) DO UPDATE SET
                        lease_token = EXCLUDED.lease_token,
                        poller_id = EXCLUDED.poller_id,
                        lease_expires_at = EXCLUDED.lease_expires_at,
                        acquired_at = NOW()
                    WHERE external_poll_leases.lease_expires_at <= NOW()
                    RETURNING job_id
                    """,
                    (job_id, token, poller_id, int(lease_seconds)),
                )
                acquired = cur.fetchone()
            conn.commit()
            return PollLease(job_id, token, poller_id) if acquired else None
        except Exception:
            conn.rollback()
            return None
        finally:
            self._release_conn(conn)

    def release(self, lease: PollLease) -> bool:
        conn = self._get_conn()
        if conn is None:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM external_poll_leases WHERE job_id=%s AND lease_token=%s",
                    (lease.job_id, lease.lease_token),
                )
                released = cur.rowcount == 1
            conn.commit()
            return released
        except Exception:
            conn.rollback()
            return False
        finally:
            self._release_conn(conn)
