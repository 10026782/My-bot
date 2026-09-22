-- Preserve failed claim audit evidence while allowing one explicitly proven recovery.
ALTER TABLE action_execution_claims
    ADD COLUMN IF NOT EXISTS original_idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS superseded_by_contract_id TEXT;
