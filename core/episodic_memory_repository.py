"""Durable PostgreSQL repository for EpisodicEntry rows (Episodic Memory Phase 1).

Append-only: insert() is the only write operation, and it is idempotent
under a caller- or repository-assigned id (ON CONFLICT DO NOTHING). There is
no update path — a correction is a new row (event_type='correction'), never
an overwrite. Every operation is tenant-scoped; a missing/empty tenant_id
fails closed before any query runs, and a read never returns a row that
belongs to a different tenant than the one requested.

This module has no callers yet. It is not wired into the live turn loop, the
context builder, or retrieval — see
docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md, Phase 1.

Reuses the connection-injection pattern from core/turn_state_repository.py
and the append-only insert pattern from core/usage_telemetry.py.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from core.episodic_entry import EpisodicEntry, EpisodicEntryValidationError

logger = logging.getLogger(__name__)

_ROW_COLUMNS = (
    "id, tenant_id, canonical_user_id, session_id, entity_type, entity_id, "
    "domain_id, event_type, source, occurred_at, action_ref, outcome_ref, "
    "provenance_ref, payload, created_at"
)


class EpisodicMemoryError(RuntimeError):
    """Base class for fail-closed episodic-memory repository errors."""


class EpisodicMemoryStoreError(EpisodicMemoryError):
    """The durable store could not answer or persist a request."""


class EpisodicMemoryCorruptError(EpisodicMemoryError):
    """A row is present but does not match the EpisodicEntry contract shape."""


def _require_tenant(tenant_id: str) -> None:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise EpisodicEntryValidationError("tenant_id is required")


class EpisodicMemoryRepository:
    """PostgreSQL repository for the append-only ``episodic_entries`` log."""

    def __init__(self, connection_factory=None):
        # Same narrow injection point as TurnStateRepository: production
        # defaults to the shared PostgreSQL pool, tests supply a double.
        self._connection_factory = connection_factory

    def _connection(self):
        if self._connection_factory is not None:
            return self._connection_factory()
        from core.database import get_conn
        return get_conn()

    def _release(self, conn) -> None:
        if conn is None:
            return
        if self._connection_factory is not None:
            return
        from core.database import release_conn
        release_conn(conn)

    @staticmethod
    def _from_row(row) -> EpisodicEntry:
        if row is None or len(row) != 15:
            raise EpisodicMemoryCorruptError("episodic-entry row has an invalid shape")
        (entry_id, tenant_id, canonical_user_id, session_id, entity_type, entity_id,
         domain_id, event_type, source, occurred_at, action_ref, outcome_ref,
         provenance_ref, payload, created_at) = row
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError) as exc:
                raise EpisodicMemoryCorruptError("episodic-entry payload is not valid JSON") from exc
        try:
            return EpisodicEntry(
                id=entry_id,
                tenant_id=tenant_id,
                canonical_user_id=canonical_user_id,
                session_id=session_id,
                entity_type=entity_type,
                entity_id=entity_id,
                domain_id=domain_id,
                event_type=event_type,
                source=source,
                occurred_at=float(occurred_at),
                action_ref=action_ref,
                outcome_ref=outcome_ref,
                provenance_ref=provenance_ref,
                payload=payload,
                created_at=float(created_at),
            )
        except EpisodicEntryValidationError as exc:
            raise EpisodicMemoryCorruptError(f"episodic-entry row violates its contract: {exc}") from exc

    def insert(self, entry: EpisodicEntry) -> EpisodicEntry:
        """Append one entry. Idempotent: re-inserting the same id returns the
        row already on disk rather than raising or duplicating it."""
        _require_tenant(entry.tenant_id)
        entry_id = entry.id or str(uuid.uuid4())
        created_at = time.time()
        conn = self._connection()
        if conn is None:
            raise EpisodicMemoryStoreError("episodic-memory store unavailable")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""INSERT INTO episodic_entries
                        (id, tenant_id, canonical_user_id, session_id, entity_type,
                         entity_id, domain_id, event_type, source, occurred_at,
                         action_ref, outcome_ref, provenance_ref, payload, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        RETURNING {_ROW_COLUMNS}""",
                    (
                        entry_id, entry.tenant_id, entry.canonical_user_id, entry.session_id,
                        entry.entity_type, entry.entity_id, entry.domain_id, entry.event_type,
                        entry.source, entry.occurred_at, entry.action_ref, entry.outcome_ref,
                        entry.provenance_ref,
                        json.dumps(entry.payload) if entry.payload is not None else None,
                        created_at,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    # Same id already durable — return the existing row, not a duplicate.
                    cur.execute(
                        f"SELECT {_ROW_COLUMNS} FROM episodic_entries "
                        "WHERE id = %s AND tenant_id = %s",
                        (entry_id, entry.tenant_id),
                    )
                    row = cur.fetchone()
            conn.commit()
            if row is None:
                raise EpisodicMemoryStoreError("insert conflicted but no row could be read back")
            logger.debug(
                "[EpisodicMemory] inserted id=%s tenant=%s event_type=%s source=%s",
                entry_id, entry.tenant_id, entry.event_type, entry.source,
            )
            return self._from_row(row)
        except EpisodicMemoryError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise EpisodicMemoryStoreError("episodic-entry insert failed") from exc
        finally:
            self._release(conn)

    def get_by_id(self, tenant_id: str, entry_id: str) -> EpisodicEntry | None:
        _require_tenant(tenant_id)
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise EpisodicEntryValidationError("entry_id is required")
        conn = self._connection()
        if conn is None:
            raise EpisodicMemoryStoreError("episodic-memory store unavailable")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_ROW_COLUMNS} FROM episodic_entries "
                    "WHERE id = %s AND tenant_id = %s",
                    (entry_id, tenant_id),
                )
                row = cur.fetchone()
            return None if row is None else self._from_row(row)
        except EpisodicMemoryError:
            raise
        except Exception as exc:
            raise EpisodicMemoryStoreError("episodic-entry read failed") from exc
        finally:
            self._release(conn)

    def list_by_tenant(
        self,
        tenant_id: str,
        *,
        session_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
    ) -> list[EpisodicEntry]:
        """Tenant-scoped listing, optionally narrowed by session or entity.
        Ordered oldest-first (append order) to preserve episode sequence."""
        _require_tenant(tenant_id)
        if not isinstance(limit, int) or limit < 1:
            raise EpisodicEntryValidationError("limit must be a positive integer")
        where = ["tenant_id = %s"]
        params: list = [tenant_id]
        if session_id is not None:
            where.append("session_id = %s")
            params.append(session_id)
        if entity_type is not None:
            where.append("entity_type = %s")
            params.append(entity_type)
        if entity_id is not None:
            where.append("entity_id = %s")
            params.append(entity_id)
        params.append(limit)
        conn = self._connection()
        if conn is None:
            raise EpisodicMemoryStoreError("episodic-memory store unavailable")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_ROW_COLUMNS} FROM episodic_entries "
                    f"WHERE {' AND '.join(where)} "
                    "ORDER BY occurred_at ASC, id ASC LIMIT %s",
                    tuple(params),
                )
                rows = cur.fetchall()
            return [self._from_row(row) for row in rows]
        except EpisodicMemoryError:
            raise
        except Exception as exc:
            raise EpisodicMemoryStoreError("episodic-entry list failed") from exc
        finally:
            self._release(conn)

    def list_recent(self, tenant_id: str, *, limit: int = 50) -> list[EpisodicEntry]:
        """Most recent entries first, tenant-scoped."""
        _require_tenant(tenant_id)
        if not isinstance(limit, int) or limit < 1:
            raise EpisodicEntryValidationError("limit must be a positive integer")
        conn = self._connection()
        if conn is None:
            raise EpisodicMemoryStoreError("episodic-memory store unavailable")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_ROW_COLUMNS} FROM episodic_entries "
                    "WHERE tenant_id = %s "
                    "ORDER BY occurred_at DESC, id DESC LIMIT %s",
                    (tenant_id, limit),
                )
                rows = cur.fetchall()
            return [self._from_row(row) for row in rows]
        except EpisodicMemoryError:
            raise
        except Exception as exc:
            raise EpisodicMemoryStoreError("episodic-entry list failed") from exc
        finally:
            self._release(conn)
