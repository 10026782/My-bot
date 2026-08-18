"""Episodic Memory Phase 1 — contract + repository tests.

Mirrors the fake-Postgres-double style of test_turn_state_repository.py.
Covers: insert+read, tenant isolation, session/entity filtering, append-only
semantics, ordering, structured payload round-trip, fail-closed invalid
tenant, repository failure semantics, and the Phase 1 non-goals (no LLM/
context coupling, no ActionGateway import, no retrieval/ranking surface).
"""

from __future__ import annotations

import json
import logging

import pytest

from core.episodic_entry import EpisodicEntry, EpisodicEntryValidationError, EpisodicEventType
from core.episodic_memory_repository import (
    EpisodicMemoryCorruptError,
    EpisodicMemoryRepository,
    EpisodicMemoryStoreError,
)


class _Cursor:
    def __init__(self, db):
        self.db = db
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.result = self.db.execute(sql, params)

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return list(self.result or [])


class _Connection:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return _Cursor(self.db)

    def commit(self):
        return None

    def rollback(self):
        return None


class _FakeDb:
    """SQL-shaped double for the exact statements the repository issues."""

    def __init__(self):
        self.rows: dict[str, tuple] = {}

    def execute(self, sql, params):
        s = sql.lstrip()
        if s.startswith("INSERT"):
            entry_id = params[0]
            if entry_id in self.rows:
                return []  # ON CONFLICT DO NOTHING -> no RETURNING row
            self.rows[entry_id] = tuple(params)
            return [tuple(params)]

        if "ORDER BY" not in s:
            # get_by_id / insert's post-conflict re-select
            entry_id, tenant_id = params
            row = self.rows.get(entry_id)
            if row is None or row[1] != tenant_id:
                return []
            return [row]

        # list_by_tenant / list_recent
        *where_params, limit = params
        candidates = [r for r in self.rows.values() if r[1] == where_params[0]]
        idx = 1
        if "session_id = %s" in s:
            candidates = [r for r in candidates if r[3] == where_params[idx]]
            idx += 1
        if "entity_type = %s" in s:
            candidates = [r for r in candidates if r[4] == where_params[idx]]
            idx += 1
        if "entity_id = %s" in s:
            candidates = [r for r in candidates if r[5] == where_params[idx]]
            idx += 1
        reverse = "occurred_at DESC" in s
        candidates.sort(key=lambda r: (r[9], r[0]), reverse=reverse)
        return candidates[:limit]


def _repo():
    db = _FakeDb()
    return db, EpisodicMemoryRepository(lambda: _Connection(db))


def _entry(**overrides):
    fields = dict(
        tenant_id="tenant-a",
        canonical_user_id="user-a",
        event_type=EpisodicEventType.INTERACTION.value,
        source="test",
        occurred_at=1000.0,
    )
    fields.update(overrides)
    return EpisodicEntry(**fields)


# 1. insert + read
def test_insert_and_get_by_id_round_trip():
    _, repo = _repo()
    saved = repo.insert(_entry())
    fetched = repo.get_by_id("tenant-a", saved.id)
    assert fetched == saved
    assert fetched.event_type == "interaction"
    assert fetched.created_at is not None


# 2. tenant isolation
def test_tenant_isolation():
    _, repo = _repo()
    saved = repo.insert(_entry(tenant_id="tenant-a"))
    assert repo.get_by_id("tenant-b", saved.id) is None
    repo.insert(_entry(tenant_id="tenant-b", canonical_user_id="user-b"))
    assert len(repo.list_by_tenant("tenant-a")) == 1
    assert len(repo.list_by_tenant("tenant-b")) == 1


# 3. session/entity filtering
def test_session_and_entity_filtering():
    _, repo = _repo()
    repo.insert(_entry(session_id="s1", entity_type="lead", entity_id="L1"))
    repo.insert(_entry(session_id="s2", entity_type="lead", entity_id="L2"))
    repo.insert(_entry(session_id="s1", entity_type="deal", entity_id="D1"))

    by_session = repo.list_by_tenant("tenant-a", session_id="s1")
    assert {e.entity_id for e in by_session} == {"L1", "D1"}

    by_entity = repo.list_by_tenant("tenant-a", entity_type="lead", entity_id="L2")
    assert len(by_entity) == 1 and by_entity[0].session_id == "s2"


# 4. append-only semantics
def test_append_only_no_update_surface_and_idempotent_reinsert():
    assert not hasattr(EpisodicMemoryRepository, "update")
    assert not hasattr(EpisodicMemoryRepository, "delete")

    _, repo = _repo()
    first = repo.insert(_entry(id="fixed-id", payload={"n": 1}))
    replay = repo.insert(_entry(id="fixed-id", payload={"n": 999}))
    # Re-inserting the same id returns what is already durable, unchanged —
    # never silently rewrites content under an existing id.
    assert replay.payload == {"n": 1} == first.payload


# 5. timestamp/order
def test_ordering_ascending_and_descending():
    _, repo = _repo()
    repo.insert(_entry(id="a", occurred_at=100.0))
    repo.insert(_entry(id="b", occurred_at=300.0))
    repo.insert(_entry(id="c", occurred_at=200.0))

    ascending = repo.list_by_tenant("tenant-a")
    assert [e.id for e in ascending] == ["a", "c", "b"]

    descending = repo.list_recent("tenant-a")
    assert [e.id for e in descending] == ["b", "c", "a"]


# 6. structured payload round-trip
def test_structured_payload_round_trip():
    _, repo = _repo()
    payload = {"tool": "airtable_add", "fields": {"Name": "x"}, "count": 3}
    saved = repo.insert(_entry(payload=payload))
    fetched = repo.get_by_id("tenant-a", saved.id)
    assert fetched.payload == payload

    with pytest.raises(EpisodicEntryValidationError):
        _entry(payload={"n": object()})  # not JSON-serializable

    with pytest.raises(EpisodicEntryValidationError):
        _entry(payload={"blob": "x" * 9000})  # exceeds bound


# 7. invalid tenant rejected / fail-closed
def test_invalid_tenant_fails_closed_without_touching_store():
    def _boom():
        raise AssertionError("must not touch the store for an invalid tenant")

    repo = EpisodicMemoryRepository(_boom)
    with pytest.raises(EpisodicEntryValidationError):
        repo.get_by_id("", "some-id")
    with pytest.raises(EpisodicEntryValidationError):
        repo.list_by_tenant("   ")
    with pytest.raises(EpisodicEntryValidationError):
        EpisodicEntry(
            tenant_id="", canonical_user_id="u", event_type="interaction",
            source="s", occurred_at=1.0,
        )


# 8. no secret-specific behavior (no accidental logging of payload content)
def test_no_secret_leakage_through_logging(caplog):
    _, repo = _repo()
    secret = "SECRET_MARKER_EPISODIC_ENTRY"
    with caplog.at_level(logging.DEBUG):
        repo.insert(_entry(payload={"token": secret}))
    assert secret not in caplog.text


# 9. repository failure semantics
def test_repository_failure_semantics():
    unavailable = EpisodicMemoryRepository(lambda: None)
    with pytest.raises(EpisodicMemoryStoreError):
        unavailable.insert(_entry())
    with pytest.raises(EpisodicMemoryStoreError):
        unavailable.get_by_id("tenant-a", "x")
    with pytest.raises(EpisodicMemoryStoreError):
        unavailable.list_by_tenant("tenant-a")

    db, repo = _repo()
    db.rows["corrupt"] = ("corrupt", "tenant-a", "user-a", None, None, None,
                           None, "not-a-real-event-type", "src", 1.0,
                           None, None, None, None, 1.0)
    with pytest.raises(EpisodicMemoryCorruptError):
        repo.get_by_id("tenant-a", "corrupt")


# 10, 11, 12. Phase 1 non-goals: no LLM/context coupling, no ActionGateway
# import, no retrieval/ranking surface on the repository.
def test_phase1_surface_has_no_forbidden_coupling():
    import core.episodic_entry as entry_module
    import core.episodic_memory_repository as repo_module

    forbidden_substrings = (
        "anthropic", "context.py", "import context", "action_gateway",
        "dispatcher", "run_agent",
    )
    for module in (entry_module, repo_module):
        source = open(module.__file__, encoding="utf-8").read().lower()
        for needle in forbidden_substrings:
            assert needle not in source, f"{module.__name__} unexpectedly references {needle!r}"

    public_methods = {
        name for name in dir(EpisodicMemoryRepository)
        if not name.startswith("_")
    }
    assert public_methods == {"insert", "get_by_id", "list_by_tenant", "list_recent"}
    for forbidden in ("rank", "retrieve", "budget", "score", "search"):
        assert not any(forbidden in m for m in public_methods)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
