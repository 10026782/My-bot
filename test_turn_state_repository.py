"""Focused TC8 contract tests using a shared transactional test double."""

from __future__ import annotations

import threading
import time

import pytest

from core.turn_state_repository import (
    TurnStateConflictError,
    TurnStateCorruptError,
    TurnStateRepository,
    TurnStateStoreError,
)


class _Cursor:
    def __init__(self, db):
        self.db = db
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.row = self.db.execute(sql, params)

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return _Cursor(self.db)

    def commit(self):
        return None

    def rollback(self):
        return None


class _SharedDb:
    """Small SQL-shaped double that preserves PostgreSQL CAS semantics."""

    def __init__(self):
        self.rows = {}
        self.lock = threading.Lock()

    @staticmethod
    def row(state):
        return (state["tenant"], state["user"], state["turn"], state["contract"],
                state["state"], state["owner"], state["op"], state["version"],
                state["updated"], state["reason"])

    def execute(self, sql, params):
        with self.lock:
            if sql.lstrip().startswith("INSERT"):
                tenant, user, turn, contract, updated = params
                key = (tenant, user)
                if key in self.rows:
                    return None
                state = {"tenant": tenant, "user": user, "turn": turn,
                         "contract": contract, "state": "active", "owner": None,
                         "op": None, "version": 1, "updated": updated, "reason": None}
                self.rows[key] = state
                return self.row(state)
            if sql.lstrip().startswith("SELECT"):
                tenant, user = params
                state = self.rows.get((tenant, user))
                return None if state is None else self.row(state)
            # update parameters are update values, timestamp, identity, version,
            # followed by optional owner/operation parameters.
            is_finalize = "state = %s, terminal_reason" in sql
            if is_finalize:
                tenant, user, version = params[-4], params[-3], params[-2]
            else:
                tenant, user, version = params[-3], params[-2], params[-1]
            state = self.rows.get((tenant, user))
            if state is None or state["version"] != version:
                return None
            if "AND state = 'active'" in sql and state["state"] != "active":
                return None
            if "turn_id = %s" in sql:
                turn, contract, updated = params[0], params[1], params[2]
                if state["state"] not in {"released", "terminal"}:
                    return None
                state.update({"turn": turn, "contract": contract, "state": "active",
                              "owner": None, "op": None, "reason": None})
                state["version"] += 1
                state["updated"] = updated
                return self.row(state)
            if is_finalize:
                op = params[-1]
                if state["state"] != "claimed" or state["op"] != op:
                    return None
            if "state = 'claimed', owner_kind" in sql:
                owner, op, updated = params[0], params[1], params[2]
                state["state"], state["owner"], state["op"] = "claimed", owner, op
            else:
                new_state, reason, updated = params[0], params[1], params[2]
                state["state"], state["reason"] = new_state, reason
            state["version"] += 1
            state["updated"] = updated
            return self.row(state)


def _repos():
    db = _SharedDb()
    factory = lambda: _Connection(db)
    return db, TurnStateRepository(factory), TurnStateRepository(factory)


def test_create_read_and_restart_recovery():
    db, first, _ = _repos()
    created = first.create("tenant-a", "user-a", "turn-1", "contract-1")
    assert first.read("tenant-a", "user-a") == created
    restarted = TurnStateRepository(lambda: _Connection(db))
    assert restarted.read("tenant-a", "user-a").turn_id == "turn-1"


def test_begin_or_get_reuses_only_terminal_rows_for_new_contracts():
    _, repo, _ = _repos()
    first = repo.begin_or_get("tenant-a", "user-a", "turn-1", "contract-1")
    claimed = repo.claim("tenant-a", "user-a", expected_version=first.version,
                         operation_id="op-1", owner_kind="text").state
    terminal = repo.finalize("tenant-a", "user-a", expected_version=claimed.version,
                             operation_id="op-1", terminal_reason="completed").state
    next_turn = repo.begin_or_get("tenant-a", "user-a", "turn-2", "contract-2")
    assert next_turn.version == terminal.version + 1
    assert next_turn.active_contract_id == "contract-2"
    assert next_turn.state == "active"


def test_cas_conflict_and_two_instance_race():
    _, first, second = _repos()
    state = first.create("tenant-a", "user-a", "turn-1")
    winner, loser = [], []

    def attempt(repo, op):
        try:
            winner.append(repo.claim("tenant-a", "user-a", expected_version=state.version,
                                     operation_id=op, owner_kind="callback"))
        except TurnStateConflictError:
            loser.append(op)

    threads = [threading.Thread(target=attempt, args=(first, "a")),
               threading.Thread(target=attempt, args=(second, "b"))]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert len(winner) == 1
    assert len(loser) == 1


def test_callback_text_race_duplicate_replay_and_terminal_release():
    _, repo, _ = _repos()
    state = repo.create("tenant-a", "user-a", "turn-1", "contract-1")
    claimed = repo.claim("tenant-a", "user-a", expected_version=state.version,
                         operation_id="callback-1", owner_kind="callback").state
    with pytest.raises(TurnStateConflictError):
        repo.claim("tenant-a", "user-a", expected_version=state.version,
                   operation_id="text-1", owner_kind="text")
    terminal = repo.finalize("tenant-a", "user-a", expected_version=claimed.version,
                             operation_id="callback-1", terminal_reason="approved")
    with pytest.raises(TurnStateConflictError):
        repo.finalize("tenant-a", "user-a", expected_version=terminal.state.version,
                      operation_id="callback-1")


def test_release_is_terminal_for_claiming_and_corrupt_rows_fail_closed():
    db, repo, _ = _repos()
    state = repo.create("tenant-a", "user-a", "turn-1")
    claimed = repo.claim("tenant-a", "user-a", expected_version=state.version,
                         operation_id="text-1", owner_kind="text").state
    released = repo.release("tenant-a", "user-a", expected_version=claimed.version,
                            operation_id="text-1", terminal_reason="cancelled")
    assert released.state.state == "released"
    with pytest.raises(TurnStateConflictError):
        repo.claim("tenant-a", "user-a", expected_version=released.state.version,
                   operation_id="callback-2", owner_kind="callback")

    db.rows[("tenant-b", "user-b")] = {
        "tenant": "tenant-b", "user": "user-b", "turn": "turn-b",
        "contract": None, "state": "claimed", "owner": None, "op": None,
        "version": 1, "updated": time.time(), "reason": None,
    }
    with pytest.raises(TurnStateCorruptError):
        repo.read("tenant-b", "user-b")


def test_unavailable_store_fails_closed():
    repo = TurnStateRepository(lambda: None)
    with pytest.raises(TurnStateStoreError) as exc_info:
        repo.read("tenant-a", "user-a")
    assert "unavailable" in str(exc_info.value)


def test_tenant_isolation_and_fail_closed_inputs():
    _, repo, _ = _repos()
    created = repo.create("tenant-a", "same-user", "turn-a")
    other = repo.create("tenant-b", "same-user", "turn-b")
    assert created.turn_id != other.turn_id
    with pytest.raises(TurnStateConflictError):
        repo.claim("tenant-a", "same-user", expected_version=99,
                   operation_id="stale", owner_kind="text")
    with pytest.raises(TurnStateCorruptError):
        repo.read("", "same-user")
