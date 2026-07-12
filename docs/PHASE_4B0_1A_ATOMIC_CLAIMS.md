# Phase 4B0.1A/B — PostgreSQL Atomic Claims (Atomic Coordination Primitive)

**Phase 4B0.1A Status:** ✅ COMPLETE (infrastructure only, not wired to live)  
**Phase 4B0.1B Status:** ⏳ IMPLEMENTED, NOT VERIFIED (real PostgreSQL tests pending)  
**Updated:** 2026-07-12  
**Feature Flag:** `FEATURE_ATOMIC_CLAIMS` (default OFF)  
**Blocker for 4B0.1C:** Phase 4B0.1B must pass against staging PostgreSQL

## Overview

Phase 4B0.1A implements the PostgreSQL-backed atomic coordination primitive for ActionContract execution claims. This is the foundation for Phase 4B0.1B (concurrency tests) and Phase 4B (TMA approvals routing by contract_id).

**Problem it solves:**
- Earlier `guarded_transition()` mechanism (read → check → PATCH → re-read) provided NO protection under genuine concurrency
- Two callers could both read, both PATCH, both re-read success, and both proceed to execute the same contract
- Needed a genuinely atomic coordination primitive outside Airtable

**Solution:**
- Single PostgreSQL table: `action_execution_claims`
- Claim ownership with atomic `INSERT ... ON CONFLICT ... DO NOTHING RETURNING contract_id`
- Only the caller receiving a returned row may proceed to `dispatch_tool()`
- All other callers must stop before execution — fail-closed on not-returned

## Architecture

### Table: `action_execution_claims`

```sql
CREATE TABLE IF NOT EXISTS action_execution_claims (
    contract_id TEXT PRIMARY KEY,
    claimant_id TEXT NOT NULL,
    execution_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    claimed_at REAL NOT NULL,
    completed_at REAL,
    idempotency_key TEXT UNIQUE,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

**Key design decisions:**

1. **contract_id is PRIMARY KEY** — only one claim per contract
   - Duplicate claims are rejected by the DB constraint
   - Atomic: INSERT ... ON CONFLICT ... DO NOTHING

2. **execution_id is UNIQUE** — every execution gets its own ID
   - Tracks separate invocations (retry vs. duplicate)
   - Allows correlation with logs

3. **idempotency_key is UNIQUE** — retry-safety
   - Same caller retrying with same idempotency_key gets the same execution_id
   - Prevents accidental double-execution on network retry

4. **status lifecycle:** `pending` → (`completed` | `failed` | `outcome_unknown`)
   - `completed` — execution succeeded
   - `failed` — execution failed (error in `last_error`)
   - `outcome_unknown` — unclear if execution succeeded (don't auto-retry)

### Module: `core/atomic_claim_repository.py`

Provides high-level API for claiming and updating contract execution status:

```python
# Claim ownership
claim = claim_contract_execution(
    contract_id="contract-123",
    claimant_id="boss_hq:owner_1",
    idempotency_key="optional-key"
)

if claim is None:
    # Another caller already owns this contract — stop immediately
    return

# Only this caller proceeds to dispatch_tool()
result = dispatch_tool(contract_id, ...)

# Record outcome
if result.success:
    update_claim_status(contract_id, "completed")
else:
    update_claim_status(contract_id, "failed", error=str(result.error))
```

### Database Module: `core/database.py`

Manages PostgreSQL connection pooling:

- Lazy initialization on first use
- Supports both `DATABASE_URL` (Render standard) and individual env vars
- Graceful degradation if PostgreSQL not configured (returns None)
- Connection pool (SimpleConnectionPool, 1-5 connections)

### Migrations: `core/migrations/001_action_execution_claims.sql`

Run automatically at startup (when flag is enabled):
- Creates table if not exists
- Creates indices for performance (claimant_id, status, created_at)
- Idempotent — safe to run repeatedly

### Migration Runner: `core/database_migrations.py`

On startup, if PostgreSQL configured:
- Finds all `*.sql` files in `core/migrations/`
- Runs them in sorted order
- Commits or rolls back atomically
- Logs results

## Operational Guidelines

### When Flag is OFF (default)

All operations are no-ops:
- `claim_contract_execution()` returns None
- `update_claim_status()` returns True (no-op success)
- `get_claim()` returns None
- `list_pending_claims()` returns []

This allows safe co-existence with existing code until explicitly activated.

### When Flag is ON (staging/production)

Requires PostgreSQL to be configured:

```bash
export FEATURE_ATOMIC_CLAIMS=true
export DATABASE_URL="postgresql://user:pass@host:5432/boss_bot"
```

If PostgreSQL not configured and flag is ON:
- `claim_contract_execution()` logs a warning and returns None
- Action fails closed (no execution without a claim)

### Outcomes: Retry Semantics

| Outcome | Meaning | Auto-retry? | Action |
|---------|---------|-------------|--------|
| `completed` | Execution succeeded | N/A | Task done |
| `failed` | Execution failed with error | Yes (optional) | Retry with same contract |
| `outcome_unknown` | Unclear if succeeded | **No** | Investigate manually |

**Why no auto-retry on `outcome_unknown`:**
- Can't safely retry without knowing if the first attempt succeeded
- Might cause duplicate mutations (lead written twice, email sent twice)
- Better to escalate and investigate: check Airtable, logs, etc.

## Phase 4B0.1B (Concurrency Test)

Will test with two independent DB connections trying to claim the same contract simultaneously:

```python
# Thread 1
claim1 = claim_contract_execution("contract-X", "user-1")
assert claim1 is not None  # Thread 1 wins

# Thread 2 (concurrent)
claim2 = claim_contract_execution("contract-X", "user-2")
assert claim2 is None  # Thread 2 loses — contract already claimed

# Only Thread 1 proceeds to dispatch
dispatch_tool(...)
update_claim_status("contract-X", "completed")
```

Separate test file: `test_phase_4b0_1b_concurrency.py` (not yet created).

## Phase 4B (TMA Approvals by contract_id)

Once 4B0.1A is proven and 4B0.1B concurrency tests pass:

1. TMA `/approve` button routes to a handler with contract_id
2. Handler calls `claim_contract_execution(contract_id, approver_id)`
3. If claim succeeds, proceeds to re-fetch contract from Airtable + dispatch
4. If claim fails (another approval already owns it), shows "contract already being executed"

This replaces the old `_queue_approval()` / `_pending_approvals` dict, which had no cross-instance protection.

## Limitations & Future Work

### Not Covered by Phase 4B0.1A

1. **No automatic cleanup** — stale claims sit in the table forever
   - Future: implement a cleanup job (DELETE WHERE claimed_at < NOW - 24h AND status = 'pending')

2. **No replay/recovery** — if Render crashes between claim + dispatch, the claim is orphaned
   - Future: recovery job checks Airtable for contracts in `executing` state with no matching claim

3. **No cross-tenant isolation** — `claimant_id` is a string, not enforced as any identity
   - By design: `claimant_id` is purely for logging, not access control
   - Access control remains in `dispatch_tool()` via identity enforcement

4. **No failure backoff** — if dispatch fails, next attempt must be a fresh claim (idempotency_key must differ)
   - By design: failed contracts stay in the table as `status=failed` for audit
   - Retry requires user action (approval button pressed again)

## Testing

### Phase 4B0.1A Tests (Existing)

File: `test_phase_4b0_1a_atomic_claims.py`

Covers:
- Feature flag integration (disabled when OFF)
- AtomicExecutionClaim lifecycle
- Schema file existence
- Status constants
- Database module graceful degradation
- Feature flag registry
- Module imports

Run:
```bash
python3 test_phase_4b0_1a_atomic_claims.py
```

Result: 26/26 passed

### Phase 4B0.1B Tests (Not Yet Created)

File: `test_phase_4b0_1b_concurrency.py`

Will cover:
- Two independent DB connections
- Simultaneous claim attempts
- Only one succeeds, one gets None
- Execution ownership enforcement

## Environment Variables

### Required (if using atomic claims)

```bash
FEATURE_ATOMIC_CLAIMS=true
# And one of:
DATABASE_URL=postgresql://...  # Render standard
# Or:
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=boss_bot
DATABASE_USER=postgres
DATABASE_PASSWORD=...
```

### Optional

```bash
# Migration control (future)
# DATABASE_MIGRATION_TIMEOUT=30  # timeout for running migrations (seconds)
```

## Files Modified/Created

### New Files

- `core/database.py` — connection pooling
- `core/database_migrations.py` — migration runner
- `core/atomic_claim_repository.py` — claim API
- `core/migrations/001_action_execution_claims.sql` — schema
- `test_phase_4b0_1a_atomic_claims.py` — tests
- `docs/PHASE_4B0_1A_ATOMIC_CLAIMS.md` — this document

### Modified Files

- `requirements.txt` — added `psycopg2-binary`
- `feature_flags.py` — added `FEATURE_ATOMIC_CLAIMS` to registry
- `.env.example` — documented PostgreSQL env vars

## Deployment Notes

**Important:** Phase 4B0.1A is infrastructure-only. The live `ActionGateway` is NOT wired to use it yet.

```python
# In ActionGateway.approve() / _execute_contract():
# ❌ NOT CALLING: claim_contract_execution()
# ✅ STILL USING: original in-memory update_status() path
```

Wiring happens in Phase 4B0.1C (staging rollout).

## Next Steps

1. **Phase 4B0.1B** — concurrency test harness
   - Two threads, same contract, prove atomicity
   - Verify exactly one claim succeeds
   - Verify atomic INSERT ... ON CONFLICT in production

2. **Phase 4B0.1C** — staging rollout
   - Enable `FEATURE_ATOMIC_CLAIMS` in staging
   - Wire `ActionGateway.approve()` to use `claim_contract_execution()`
   - Run 48+ hours of staging traffic
   - Verify claim success rate (should be 100% unique claims)

3. **Phase 4B** — TMA approvals by contract_id
   - Block on successful staging verification
   - Implement TMA handler with contract-based routing
   - Deprecate `_queue_approval()` / `_pending_approvals` dict
