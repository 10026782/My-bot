-- External Execution Boundary — short-lived polling ownership only.
-- Business/job state remains in Airtable; this table is not an execution ledger.
CREATE TABLE IF NOT EXISTS external_poll_leases (
    job_id TEXT PRIMARY KEY,
    lease_token TEXT NOT NULL UNIQUE,
    poller_id TEXT NOT NULL,
    lease_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    acquired_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_external_poll_leases_expiry
    ON external_poll_leases(lease_expires_at);
