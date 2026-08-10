"""Durable, identity-scoped coordination state for TC8.

This repository owns coordination only.  It does not create, transition, or
repair ActionContracts; ``active_contract_id`` is an opaque reference to the
canonical lifecycle record owned by ActionGateway.

Every authority-changing operation is a conditional PostgreSQL UPDATE.  A
successful UPDATE increments ``version`` exactly once.  A zero-row UPDATE is
classified from a fresh read and is never treated as success.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

TurnStateName = Literal["active", "claimed", "released", "terminal"]
OwnerKind = Literal["callback", "text"]

_STATES = frozenset({"active", "claimed", "released", "terminal"})
_OWNER_KINDS = frozenset({"callback", "text"})


class TurnStateError(RuntimeError):
    """Base class for fail-closed turn-state errors."""


class TurnStateStoreError(TurnStateError):
    """The durable store could not answer or persist a request."""


class TurnStateConflictError(TurnStateError):
    """The requested mutation lost a version/ownership/state race."""


class TurnStateCorruptError(TurnStateError):
    """A row is present but cannot safely be used as authority."""


@dataclass(frozen=True)
class TurnState:
    tenant_id: str
    canonical_user_id: str
    turn_id: str
    active_contract_id: str | None
    state: TurnStateName
    owner_kind: OwnerKind | None
    operation_id: str | None
    version: int
    updated_at: float
    terminal_reason: str | None = None


@dataclass(frozen=True)
class TurnMutationResult:
    state: TurnState
    changed: bool


class TurnStateRepository:
    """PostgreSQL repository for one coordination row per identity/tenant."""

    def __init__(self, connection_factory=None):
        # Injection is deliberately narrow: production defaults to the shared
        # PostgreSQL pool, while focused tests can provide two independent
        # connections without changing authority semantics.
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
    def _validate_identity(tenant_id: str, canonical_user_id: str) -> None:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise TurnStateCorruptError("tenant_id is required")
        if not isinstance(canonical_user_id, str) or not canonical_user_id.strip():
            raise TurnStateCorruptError("canonical_user_id is required")

    @staticmethod
    def _from_row(row) -> TurnState:
        if row is None or len(row) != 10:
            raise TurnStateCorruptError("turn-state row has an invalid shape")
        (tenant_id, user_id, turn_id, contract_id, state, owner_kind,
         operation_id, version, updated_at, terminal_reason) = row
        if (not tenant_id or not user_id or not turn_id or state not in _STATES
                or (owner_kind is not None and owner_kind not in _OWNER_KINDS)
                or not isinstance(version, int) or version < 1
                or (state == "claimed" and (owner_kind is None or not operation_id))):
            raise TurnStateCorruptError("turn-state row violates its invariants")
        return TurnState(
            tenant_id=tenant_id,
            canonical_user_id=user_id,
            turn_id=turn_id,
            active_contract_id=contract_id,
            state=state,
            owner_kind=owner_kind,
            operation_id=operation_id,
            version=version,
            updated_at=float(updated_at),
            terminal_reason=terminal_reason,
        )

    @staticmethod
    def _select(cur, tenant_id: str, canonical_user_id: str):
        cur.execute(
            """SELECT tenant_id, canonical_user_id, turn_id,
                      active_contract_id, state, owner_kind, operation_id,
                      version, updated_at, terminal_reason
                 FROM durable_turn_state
                WHERE tenant_id = %s AND canonical_user_id = %s""",
            (tenant_id, canonical_user_id),
        )
        return cur.fetchone()

    def read(self, tenant_id: str, canonical_user_id: str) -> TurnState | None:
        self._validate_identity(tenant_id, canonical_user_id)
        conn = self._connection()
        if conn is None:
            raise TurnStateStoreError("turn-state store unavailable")
        try:
            with conn.cursor() as cur:
                row = self._select(cur, tenant_id, canonical_user_id)
            return None if row is None else self._from_row(row)
        except TurnStateError:
            raise
        except Exception as exc:
            raise TurnStateStoreError("turn-state read failed") from exc
        finally:
            self._release(conn)

    def create(self, tenant_id: str, canonical_user_id: str, turn_id: str,
               active_contract_id: str | None = None) -> TurnState:
        self._validate_identity(tenant_id, canonical_user_id)
        if not isinstance(turn_id, str) or not turn_id.strip():
            raise TurnStateCorruptError("turn_id is required")
        conn = self._connection()
        if conn is None:
            raise TurnStateStoreError("turn-state store unavailable")
        now = time.time()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO durable_turn_state
                       (tenant_id, canonical_user_id, turn_id,
                        active_contract_id, state, version, updated_at)
                       VALUES (%s, %s, %s, %s, 'active', 1, %s)
                       ON CONFLICT (tenant_id, canonical_user_id) DO NOTHING
                       RETURNING tenant_id, canonical_user_id, turn_id,
                                 active_contract_id, state, owner_kind,
                                 operation_id, version, updated_at,
                                 terminal_reason""",
                    (tenant_id, canonical_user_id, turn_id, active_contract_id, now),
                )
                row = cur.fetchone()
                if row is None:
                    raise TurnStateConflictError("identity already has durable turn state")
            conn.commit()
            return self._from_row(row)
        except TurnStateError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise TurnStateStoreError("turn-state create failed") from exc
        finally:
            self._release(conn)

    def begin_or_get(self, tenant_id: str, canonical_user_id: str,
                     turn_id: str, active_contract_id: str) -> TurnState:
        """Create or reuse the coordination row for one exact contract.

        A terminal/released row may be reopened for a later contract through
        an expected-version update. An active row for a different contract is
        a conflict: TC8 never guesses which lifecycle operation should win.
        """
        self._validate_identity(tenant_id, canonical_user_id)
        if not turn_id or not active_contract_id:
            raise TurnStateConflictError("turn and contract references are required")
        conn = self._connection()
        if conn is None:
            raise TurnStateStoreError("turn-state store unavailable")
        now = time.time()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO durable_turn_state
                       (tenant_id, canonical_user_id, turn_id,
                        active_contract_id, state, version, updated_at)
                       VALUES (%s, %s, %s, %s, 'active', 1, %s)
                       ON CONFLICT (tenant_id, canonical_user_id) DO NOTHING
                       RETURNING tenant_id, canonical_user_id, turn_id,
                                 active_contract_id, state, owner_kind,
                                 operation_id, version, updated_at,
                                 terminal_reason""",
                    (tenant_id, canonical_user_id, turn_id, active_contract_id, now),
                )
                row = cur.fetchone()
                if row is None:
                    row = self._select(cur, tenant_id, canonical_user_id)
                    current = self._from_row(row)
                    if current.active_contract_id == active_contract_id:
                        conn.commit()
                        return current
                    if current.state not in {"released", "terminal"}:
                        raise TurnStateConflictError(
                            "another active contract owns this identity turn"
                        )
                    cur.execute(
                        """UPDATE durable_turn_state
                              SET turn_id = %s, active_contract_id = %s,
                                  state = 'active', owner_kind = NULL,
                                  operation_id = NULL, terminal_reason = NULL,
                                  version = version + 1, updated_at = %s
                            WHERE tenant_id = %s AND canonical_user_id = %s
                              AND version = %s
                              AND state IN ('released', 'terminal')
                         RETURNING tenant_id, canonical_user_id, turn_id,
                                   active_contract_id, state, owner_kind,
                                   operation_id, version, updated_at,
                                   terminal_reason""",
                        (turn_id, active_contract_id, now, tenant_id,
                         canonical_user_id, current.version),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise TurnStateConflictError("turn restart lost a version race")
            conn.commit()
            return self._from_row(row)
        except TurnStateError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise TurnStateStoreError("turn begin failed") from exc
        finally:
            self._release(conn)

    def claim(self, tenant_id: str, canonical_user_id: str, *,
              expected_version: int, operation_id: str,
              owner_kind: OwnerKind) -> TurnMutationResult:
        """Atomically acquire the active coordination row for one path."""
        self._validate_identity(tenant_id, canonical_user_id)
        if not isinstance(expected_version, int) or expected_version < 1:
            raise TurnStateConflictError("required version is missing or invalid")
        if not operation_id or owner_kind not in _OWNER_KINDS:
            raise TurnStateConflictError("operation identity is incomplete")
        return self._mutate(
            tenant_id, canonical_user_id,
            expected_version=expected_version,
            where_extra="AND state = 'active'",
            params_extra=(),
            updates="state = 'claimed', owner_kind = %s, operation_id = %s",
            update_values=(owner_kind, operation_id),
            conflict_message="turn claim lost to a competing or stale operation",
        )

    def finalize(self, tenant_id: str, canonical_user_id: str, *,
                 expected_version: int, operation_id: str,
                 terminal_reason: str | None = None) -> TurnMutationResult:
        return self._owner_mutate(
            tenant_id, canonical_user_id, expected_version, operation_id,
            "terminal", terminal_reason,
        )

    def release(self, tenant_id: str, canonical_user_id: str, *,
                expected_version: int, operation_id: str,
                terminal_reason: str | None = None) -> TurnMutationResult:
        return self._owner_mutate(
            tenant_id, canonical_user_id, expected_version, operation_id,
            "released", terminal_reason,
        )

    def _owner_mutate(self, tenant_id, canonical_user_id, expected_version,
                      operation_id, state, terminal_reason):
        self._validate_identity(tenant_id, canonical_user_id)
        if state not in {"terminal", "released"} or not operation_id:
            raise TurnStateConflictError("terminal mutation is incomplete")
        return self._mutate(
            tenant_id, canonical_user_id,
            expected_version=expected_version,
            where_extra="AND state = 'claimed' AND operation_id = %s",
            params_extra=(operation_id,),
            updates="state = %s, terminal_reason = %s, owner_kind = owner_kind",
            update_values=(state, terminal_reason),
            conflict_message="stale, terminal, or non-owner operation",
        )

    def _mutate(self, tenant_id, canonical_user_id, *, expected_version,
                where_extra, params_extra, updates, update_values,
                conflict_message):
        conn = self._connection()
        if conn is None:
            raise TurnStateStoreError("turn-state store unavailable")
        now = time.time()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE durable_turn_state
                           SET {updates}, version = version + 1, updated_at = %s
                         WHERE tenant_id = %s AND canonical_user_id = %s
                           AND version = %s {where_extra}
                     RETURNING tenant_id, canonical_user_id, turn_id,
                               active_contract_id, state, owner_kind,
                               operation_id, version, updated_at,
                               terminal_reason""",
                    (*update_values, now, tenant_id, canonical_user_id,
                     expected_version, *params_extra),
                )
                row = cur.fetchone()
                if row is None:
                    raise TurnStateConflictError(conflict_message)
            conn.commit()
            return TurnMutationResult(state=self._from_row(row), changed=True)
        except TurnStateError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise TurnStateStoreError("turn-state mutation failed") from exc
        finally:
            self._release(conn)
