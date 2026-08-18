"""Episodic Memory Phase 2 — retrieval contract tests.

Covers the required Phase 2 scenarios: tenant isolation, entity/session
filtering, deterministic recency ordering, category budget enforcement,
provenance, empty/unavailable Episodic store, Business-Memory-only and
Episodic-only snapshots, no cross-tenant leakage, shadow path not altering
existing context, and no LLM/ActionGateway/write calls anywhere in this
surface.
"""

from __future__ import annotations

import time

import pytest

from core.episodic_entry import EpisodicEntry, EpisodicEventType
from core.episodic_memory_repository import EpisodicMemoryRepository
from core.memory_retrieval import build_memory_snapshot
from core.memory_retrieval_contract import MemoryRetrievalRequest, MemoryRetrievalValidationError
from core.memory_retrieval_shadow import compare_with_live_paths


# ── Episodic double — mirrors test_episodic_memory_repository.py's fake ──


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
    def __init__(self):
        self.rows: dict[str, tuple] = {}

    def execute(self, sql, params):
        s = sql.lstrip()
        if s.startswith("INSERT"):
            entry_id = params[0]
            if entry_id in self.rows:
                return []
            self.rows[entry_id] = tuple(params)
            return [tuple(params)]

        if "ORDER BY" not in s:
            entry_id, tenant_id = params
            row = self.rows.get(entry_id)
            if row is None or row[1] != tenant_id:
                return []
            return [row]

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


def _seed_repo(entries: list[EpisodicEntry]) -> _FakeDb:
    db = _FakeDb()
    repo = EpisodicMemoryRepository(lambda: _Connection(db))
    for e in entries:
        repo.insert(e)
    return db


def _entry(**overrides) -> EpisodicEntry:
    fields = dict(
        tenant_id="tenant-a",
        canonical_user_id="user-a",
        event_type=EpisodicEventType.INTERACTION.value,
        source="test",
        occurred_at=1000.0,
    )
    fields.update(overrides)
    return EpisodicEntry(**fields)


def _patch_episodic_repo(monkeypatch, db: _FakeDb) -> None:
    monkeypatch.setattr(
        "core.memory_retrieval.EpisodicMemoryRepository",
        lambda: EpisodicMemoryRepository(lambda: _Connection(db)),
    )


def _patch_business_memory(monkeypatch, records: list[dict]) -> None:
    monkeypatch.setattr(
        "tools.airtable_tools.airtable_get_records",
        lambda table, formula="", max_records=None: list(records),
    )


def _no_business_memory(monkeypatch) -> None:
    _patch_business_memory(monkeypatch, [])


# ── 1. tenant isolation ──────────────────────────────────────────


def test_tenant_isolation(monkeypatch):
    db = _seed_repo([_entry(id="a", tenant_id="tenant-a"), _entry(id="b", tenant_id="boss_hq")])
    _patch_episodic_repo(monkeypatch, db)
    _no_business_memory(monkeypatch)

    snap_a = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u"))
    assert [e.id for e in snap_a.episodic_entries] == ["a"]

    snap_b = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="boss_hq", canonical_user_id="u"))
    assert [e.id for e in snap_b.episodic_entries] == ["b"]


# ── 2. entity filtering ──────────────────────────────────────────


def test_entity_filtering(monkeypatch):
    db = _seed_repo(
        [
            _entry(id="lead1", entity_type="lead", entity_id="L1"),
            _entry(id="lead2", entity_type="lead", entity_id="L2"),
            _entry(id="deal1", entity_type="deal", entity_id="D1"),
        ]
    )
    _patch_episodic_repo(monkeypatch, db)
    _no_business_memory(monkeypatch)

    snap = build_memory_snapshot(
        MemoryRetrievalRequest(
            tenant_id="tenant-a", canonical_user_id="u", entity_type="lead", entity_id="L1"
        )
    )
    assert [e.id for e in snap.episodic_entries] == ["lead1"]


# ── 3. session filtering ─────────────────────────────────────────


def test_session_filtering(monkeypatch):
    db = _seed_repo(
        [
            _entry(id="s1a", session_id="s1"),
            _entry(id="s1b", session_id="s1"),
            _entry(id="s2a", session_id="s2"),
        ]
    )
    _patch_episodic_repo(monkeypatch, db)
    _no_business_memory(monkeypatch)

    snap = build_memory_snapshot(
        MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u", session_id="s1")
    )
    assert {e.id for e in snap.episodic_entries} == {"s1a", "s1b"}


# ── 4. deterministic recency ordering ────────────────────────────


def test_deterministic_recency_ordering(monkeypatch):
    db = _seed_repo(
        [
            _entry(id="old", occurred_at=100.0),
            _entry(id="new", occurred_at=300.0),
            _entry(id="mid", occurred_at=200.0),
        ]
    )
    _patch_episodic_repo(monkeypatch, db)
    _no_business_memory(monkeypatch)

    snap = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u"))
    assert [e.id for e in snap.episodic_entries] == ["new", "mid", "old"]

    # scoped path (session filter forces the sort-in-Python branch) must
    # produce the identical deterministic order
    db2 = _seed_repo(
        [
            _entry(id="old", occurred_at=100.0, session_id="s1"),
            _entry(id="new", occurred_at=300.0, session_id="s1"),
            _entry(id="mid", occurred_at=200.0, session_id="s1"),
        ]
    )
    _patch_episodic_repo(monkeypatch, db2)
    snap2 = build_memory_snapshot(
        MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u", session_id="s1")
    )
    assert [e.id for e in snap2.episodic_entries] == ["new", "mid", "old"]


# ── 5. category budget enforcement ───────────────────────────────


def test_category_budget_enforcement(monkeypatch):
    db = _seed_repo([_entry(id=f"e{i}", tenant_id="boss_hq", occurred_at=float(i)) for i in range(10)])
    _patch_episodic_repo(monkeypatch, db)
    _patch_business_memory(
        monkeypatch,
        [
            {"id": f"rec{i}", "fields": {"Event Title": f"t{i}", "Event Date": "2026-08-01"}}
            for i in range(10)
        ],
    )

    snap = build_memory_snapshot(
        MemoryRetrievalRequest(
            tenant_id="boss_hq",
            canonical_user_id="u",
            episodic_memory_budget=3,
            business_memory_budget=2,
        )
    )
    assert len(snap.episodic_entries) == 3
    assert len(snap.business_facts) == 2
    assert snap.metadata.episodic_memory_budget == 3
    assert snap.metadata.business_memory_budget == 2

    # zero budget is a legitimate, deterministic "give me none" request
    snap_zero = build_memory_snapshot(
        MemoryRetrievalRequest(
            tenant_id="boss_hq",
            canonical_user_id="u",
            episodic_memory_budget=0,
            business_memory_budget=0,
        )
    )
    assert snap_zero.episodic_entries == ()
    assert snap_zero.business_facts == ()
    assert snap_zero.metadata.episodic_memory_available is True
    assert snap_zero.metadata.business_memory_available is True


# ── 6. provenance preserved ───────────────────────────────────────


def test_provenance_preserved(monkeypatch):
    db = _seed_repo(
        [
            _entry(
                id="e1",
                tenant_id="boss_hq",
                action_ref="contract-1",
                outcome_ref="outcome-1",
                provenance_ref="tool-run-1",
            )
        ]
    )
    _patch_episodic_repo(monkeypatch, db)
    _patch_business_memory(
        monkeypatch,
        [
            {
                "id": "recXYZ",
                "fields": {
                    "Event Title": "Signed contract",
                    "Event Description": "Deal closed",
                    "Event Type": "Milestone",
                    "Domain": "General",
                    "Event Date": "2026-08-01",
                },
            }
        ],
    )

    snap = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="boss_hq", canonical_user_id="u"))

    episodic = snap.episodic_entries[0]
    assert episodic.action_ref == "contract-1"
    assert episodic.outcome_ref == "outcome-1"
    assert episodic.provenance_ref == "tool-run-1"
    assert episodic.tenant_id == "boss_hq"

    fact = snap.business_facts[0]
    assert fact.record_id == "recXYZ"
    assert fact.title == "Signed contract"
    assert fact.event_type == "Milestone"
    assert fact.source == "business_memory"


# ── 7. empty Episodic store ──────────────────────────────────────


def test_empty_episodic_store(monkeypatch):
    db = _FakeDb()
    _patch_episodic_repo(monkeypatch, db)
    _no_business_memory(monkeypatch)

    snap = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u"))
    assert snap.episodic_entries == ()
    assert snap.metadata.episodic_memory_available is True
    assert snap.metadata.episodic_memory_error is None


# ── 8. unavailable Episodic store ────────────────────────────────


def test_unavailable_episodic_store(monkeypatch):
    monkeypatch.setattr(
        "core.memory_retrieval.EpisodicMemoryRepository",
        lambda: EpisodicMemoryRepository(lambda: None),
    )
    _no_business_memory(monkeypatch)

    snap = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u"))
    assert snap.episodic_entries == ()
    assert snap.metadata.episodic_memory_available is False
    assert snap.metadata.episodic_memory_error is not None
    # The error field is durably persisted by the Phase 2B shadow-logging
    # follow-up (core/memory_retrieval_shadow.py::record_shadow_comparison),
    # so it must be a fixed exception class name, never raw exception text
    # (which can embed connection details, SQL fragments, or field values).
    assert snap.metadata.episodic_memory_error == "EpisodicMemoryStoreError"


# ── 9. Business Memory only ──────────────────────────────────────


def test_business_memory_only(monkeypatch):
    db = _FakeDb()
    _patch_episodic_repo(monkeypatch, db)
    _patch_business_memory(
        monkeypatch, [{"id": "rec1", "fields": {"Event Title": "t", "Event Date": "2026-08-01"}}]
    )

    snap = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="boss_hq", canonical_user_id="u"))
    assert len(snap.business_facts) == 1
    assert snap.episodic_entries == ()


# ── 10. Episodic Memory only ─────────────────────────────────────


def test_episodic_memory_only(monkeypatch):
    db = _seed_repo([_entry(id="e1")])
    _patch_episodic_repo(monkeypatch, db)
    _no_business_memory(monkeypatch)

    # a tenant that isn't the single known Business Memory scope
    snap = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u"))
    assert len(snap.episodic_entries) == 1
    assert snap.business_facts == ()
    assert snap.metadata.business_memory_available is True  # skipped, not failed


# ── 11. no cross-tenant leakage ──────────────────────────────────


def test_no_cross_tenant_leakage(monkeypatch):
    db = _seed_repo(
        [
            _entry(id="a1", tenant_id="tenant-a", canonical_user_id="u"),
            _entry(id="b1", tenant_id="tenant-b", canonical_user_id="u"),
        ]
    )
    _patch_episodic_repo(monkeypatch, db)
    _no_business_memory(monkeypatch)

    snap = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u"))
    assert all(e.tenant_id == "tenant-a" for e in snap.episodic_entries)
    assert "b1" not in [e.id for e in snap.episodic_entries]

    # a non-canonical tenant never sees Business Memory content either
    _patch_business_memory(monkeypatch, [{"id": "rec1", "fields": {"Event Title": "secret"}}])
    snap2 = build_memory_snapshot(MemoryRetrievalRequest(tenant_id="tenant-a", canonical_user_id="u"))
    assert snap2.business_facts == ()


# ── 12. shadow path does not alter existing context ─────────────


def test_shadow_path_does_not_alter_existing_context(monkeypatch):
    from memory_store import memory as live_memory_store

    uid = "boss_hq:shadow-test-user"
    live_memory_store.clear(uid)
    live_memory_store.add(uid, "user", "hello")

    db = _seed_repo([_entry(id="e1", tenant_id="boss_hq")])
    _patch_episodic_repo(monkeypatch, db)
    _no_business_memory(monkeypatch)

    before = live_memory_store.get_for_claude(uid)
    result = compare_with_live_paths(
        MemoryRetrievalRequest(tenant_id="boss_hq", canonical_user_id="u"), memory_key=uid
    )
    after = live_memory_store.get_for_claude(uid)

    assert before == after == [{"role": "user", "content": "hello"}]
    assert result.live_conversation_message_count == 1
    assert len(result.new_snapshot.episodic_entries) == 1

    live_memory_store.clear(uid)


# ── 13/14/15. no LLM calls, no ActionGateway calls, no writes ───


def test_no_llm_or_action_gateway_or_write_calls(monkeypatch):
    import core.memory_retrieval as retrieval_module
    import core.memory_retrieval_contract as contract_module
    import core.memory_retrieval_shadow as shadow_module

    forbidden = ("anthropic", "action_gateway", "dispatcher", "run_agent")
    for module in (retrieval_module, contract_module, shadow_module):
        source = open(module.__file__, encoding="utf-8").read().lower()
        for needle in forbidden:
            assert needle not in source, f"{module.__name__} unexpectedly references {needle!r}"

    # Seed first, using the real (unpatched) insert() — only then do we
    # forbid writes, so this checks build_memory_snapshot's own behavior,
    # not the test fixture's.
    db = _seed_repo([_entry(id="e1", tenant_id="boss_hq")])
    _patch_episodic_repo(monkeypatch, db)
    _patch_business_memory(
        monkeypatch, [{"id": "rec1", "fields": {"Event Title": "t", "Event Date": "2026-08-01"}}]
    )

    def _boom(*_a, **_kw):
        raise AssertionError("must not write")

    monkeypatch.setattr("tools.airtable_gateway.airtable_create", _boom, raising=False)
    monkeypatch.setattr(EpisodicMemoryRepository, "insert", _boom)

    # build_memory_snapshot must complete without ever calling either writer
    build_memory_snapshot(MemoryRetrievalRequest(tenant_id="boss_hq", canonical_user_id="u"))


# ── request validation ───────────────────────────────────────────


def test_invalid_request_fails_closed():
    with pytest.raises(MemoryRetrievalValidationError):
        MemoryRetrievalRequest(tenant_id="", canonical_user_id="u")
    with pytest.raises(MemoryRetrievalValidationError):
        MemoryRetrievalRequest(tenant_id="t", canonical_user_id="")
    with pytest.raises(MemoryRetrievalValidationError):
        MemoryRetrievalRequest(tenant_id="t", canonical_user_id="u", episodic_memory_budget=-1)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
