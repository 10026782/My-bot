-- core/migrations/001_action_execution_claims.sql
-- Phase 4B0.1A — PostgreSQL atomic coordination primitive
--
-- Single atomic table: action_execution_claims
-- Claim ownership with INSERT ... ON CONFLICT ... DO NOTHING RETURNING
-- Only the caller receiving a returned row may proceed to dispatch_tool().
-- All other callers must stop before execution — fail-closed on not-returned.
--
-- Idempotency key for retry-safety: prevents duplicate claims on network retry.
-- Status transitions: pending → completed | failed | outcome_unknown (never auto-retry outcome_unknown).

CREATE TABLE IF NOT EXISTS action_execution_claims (
    contract_id TEXT PRIMARY KEY,
    claimant_id TEXT NOT NULL,
    execution_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'executing',
    claimed_at REAL NOT NULL,
    completed_at REAL,
    idempotency_key TEXT UNIQUE,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_action_execution_claims_claimant_id
    ON action_execution_claims(claimant_id);
CREATE INDEX IF NOT EXISTS idx_action_execution_claims_status
    ON action_execution_claims(status);
CREATE INDEX IF NOT EXISTS idx_action_execution_claims_created_at
    ON action_execution_claims(created_at DESC);
