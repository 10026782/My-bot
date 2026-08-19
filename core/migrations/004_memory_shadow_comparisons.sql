-- core/migrations/004_memory_shadow_comparisons.sql
-- Episodic Memory Phase 2B follow-up — durable shadow-comparison log.
--
-- Accumulates real comparison data between the legacy memory-assembly paths
-- (memory_store.get_for_claude, cmd_update.get_recent_business_context) and
-- the new Phase 2 retrieval contract (core/memory_retrieval.py), so a later
-- Phase 3/cutover decision is based on observed data, not guesswork. See
-- core/memory_retrieval_shadow.py's module docstring.
--
-- SHADOW ONLY: nothing reads this table to drive prompt/context assembly.
-- Structured counts only — no message text, no business-memory text, no
-- episodic payloads (matches the no-leakage contract already enforced in
-- format_shadow_comparison()).

CREATE TABLE IF NOT EXISTS memory_shadow_comparisons (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    tenant_id TEXT NOT NULL,
    canonical_user_id TEXT NOT NULL,
    domain_id TEXT,
    legacy_message_count INTEGER NOT NULL,
    legacy_business_char_count INTEGER NOT NULL,
    new_business_count INTEGER NOT NULL,
    new_business_available BOOLEAN NOT NULL,
    new_business_error TEXT,
    new_business_budget INTEGER NOT NULL,
    new_episodic_count INTEGER NOT NULL,
    new_episodic_available BOOLEAN NOT NULL,
    new_episodic_error TEXT,
    new_episodic_budget INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_shadow_comparisons_ts
    ON memory_shadow_comparisons(ts DESC);
CREATE INDEX IF NOT EXISTS idx_memory_shadow_comparisons_tenant
    ON memory_shadow_comparisons(tenant_id);
