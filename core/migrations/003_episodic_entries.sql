-- core/migrations/003_episodic_entries.sql
-- Episodic Memory Phase 1 — durable interaction/action/result/outcome log.
--
-- Contract-only phase: rows are written exclusively through
-- core/episodic_memory_repository.py. Nothing in the live turn loop writes
-- here yet — no wiring, no retrieval, no context injection, no ranking. See
-- docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md, Phase 1,
-- which named this table the single largest gap in the current memory
-- taxonomy (no durable store exists for episode history today).
--
-- Append-only by construction: the repository exposes no UPDATE path. A
-- correction is a new row with event_type='correction', never an overwrite
-- of a prior row — this table is a log, not a mutable record.
--
-- action_ref/outcome_ref/provenance_ref are opaque string references into
-- existing sources of truth (ActionContract ids, tool execution ids,
-- evidence ids) that live in Airtable today, not Postgres. No FOREIGN KEY
-- is declared for them: a cross-database FK isn't enforceable, and
-- declaring one anyway would misrepresent referential integrity Postgres
-- cannot actually check.
--
-- Every query this repository issues is tenant-scoped (tenant_id is always
-- the leading filter), so a standalone occurred_at-only index would only
-- serve queries this repository never makes. Timestamp ordering is instead
-- folded into each tenant-scoped composite index below.

CREATE TABLE IF NOT EXISTS episodic_entries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    canonical_user_id TEXT NOT NULL,
    session_id TEXT,
    entity_type TEXT,
    entity_id TEXT,
    domain_id TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'interaction', 'action_proposed', 'action_executed',
        'tool_result', 'outcome', 'correction'
    )),
    source TEXT NOT NULL,
    occurred_at DOUBLE PRECISION NOT NULL,
    action_ref TEXT,
    outcome_ref TEXT,
    provenance_ref TEXT,
    payload JSONB,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_episodic_entries_tenant_occurred
    ON episodic_entries(tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_episodic_entries_tenant_session
    ON episodic_entries(tenant_id, session_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_episodic_entries_tenant_entity
    ON episodic_entries(tenant_id, entity_type, entity_id, occurred_at DESC);
