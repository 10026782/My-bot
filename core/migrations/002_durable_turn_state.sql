-- TC8: one durable coordination row per tenant/identity.
-- ActionContract remains lifecycle authority; contract_id is only a reference.
CREATE TABLE IF NOT EXISTS durable_turn_state (
    tenant_id TEXT NOT NULL,
    canonical_user_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    active_contract_id TEXT,
    state TEXT NOT NULL CHECK (state IN ('active', 'claimed', 'released', 'terminal')),
    owner_kind TEXT CHECK (owner_kind IN ('callback', 'text')),
    operation_id TEXT,
    version INTEGER NOT NULL CHECK (version >= 1),
    updated_at DOUBLE PRECISION NOT NULL,
    terminal_reason TEXT,
    PRIMARY KEY (tenant_id, canonical_user_id),
    CHECK (state <> 'claimed' OR (owner_kind IS NOT NULL AND operation_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_durable_turn_state_contract
    ON durable_turn_state(active_contract_id);
