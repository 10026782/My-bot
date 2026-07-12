# Phase 4B0.1B Staging Runbook — Real Concurrency Test

**Status:** ⏳ IMPLEMENTED, NOT VERIFIED  
**Blocker:** Real PostgreSQL concurrency tests must pass before Phase 4B0.1C wiring  
**Environment:** Render staging PostgreSQL (independent DB connections, synchronization barrier)

## Prerequisites

1. **Staging PostgreSQL database** with atomic claims schema
2. **FEATURE_ATOMIC_CLAIMS=true** in staging env vars
3. **Phase 4B0.1A infrastructure** already deployed (migrations run)
4. **Independent DB connections** to test genuine concurrency
5. **Synchronization barrier** to force exact-simultaneous claim attempts

## What We're Testing

**Core Hypothesis:** Only one caller per contract can acquire execution claim, even under perfect race conditions.

**Test Outcomes:**
- **Caller 1:** `result.is_acquired() = True`, owns claim
- **Caller 2:** `result.is_already_claimed() = True`, stops before dispatch
- **DB State:** One row in `action_execution_claims` with `status=executing`
- **Durable Verification:** Claim visible in PostgreSQL, persists across restarts

## Staging Setup

### 1. Verify PostgreSQL is Available

```bash
# From staging environment
psql $DATABASE_URL -c "\dt action_execution_claims"
# Should show the table exists
```

### 2. Ensure Migrations are Run

```bash
# From app startup logs
grep "PostgreSQL migrations completed successfully" /var/log/...
# OR
psql $DATABASE_URL -c "SELECT * FROM action_execution_claims LIMIT 0;"
# Should not error
```

### 3. Enable Flag in Staging

```bash
# Set in Render environment variables
FEATURE_ATOMIC_CLAIMS=true

# Restart app
heroku restart --app boss-bot-staging
# (or equivalent for your Render deployment)
```

### 4. Verify App Starts Successfully

```bash
# Check logs for startup health check
# Should see: "Atomic claims health: READY: atomic claims operational"
# Must NOT see: "FATAL: FEATURE_ATOMIC_CLAIMS is enabled but infrastructure not ready"
```

## Running Phase 4B0.1B Tests

### Option A: Run Against Staging (Recommended)

```bash
# From local machine, connecting to staging database
export FEATURE_ATOMIC_CLAIMS=true
export DATABASE_URL="postgresql://user:password@staging-db.onrender.com:5432/boss_bot"

# Run concurrency tests
python3 test_phase_4b0_1b_concurrency.py

# Expected output:
# ✅ ACQUIRED result: is_acquired() = True
# ✅ ALREADY_CLAIMED result: is_acquired() = False
# ✅ Mock concurrency: exactly one acquired (got 1)
# ✅ Real PostgreSQL concurrency: exactly one acquired (got 1)
# ✅ Real PostgreSQL concurrency: exactly one already_claimed (got 1)
# ✅ Idempotency test: first attempt acquired
# ✅ Idempotency test: retry handled safely
# ✅ Fail-closed: returns unavailable when DB down
# ✅ Strict concurrency: exactly one acquired (got 1)
# ✅ Strict concurrency: exactly one already_claimed (got 1)
```

### Option B: Run Test Script Inside Staging App

```bash
# SSH into staging app container
heroku ps:exec --app boss-bot-staging

# Set env vars inside container
export FEATURE_ATOMIC_CLAIMS=true
# DATABASE_URL already set in environment

# Run tests
cd /app
python3 test_phase_4b0_1b_concurrency.py
```

## Expected Test Results

### All Tests Should Pass

```
Phase 4B0.1B — PostgreSQL Atomic Claims (Concurrency Tests)
============================================================

✓ PostgreSQL configured — running full concurrency tests

✅ ACQUIRED result: is_acquired() = True
✅ ACQUIRED result: is_already_claimed() = False
✅ ALREADY_CLAIMED result: is_acquired() = False
✅ UNAVAILABLE result: must fail closed
✅ ERROR result: must fail closed
✅ Mock concurrency: exactly one acquired (got 1)
✅ Mock concurrency: non-winner got already_claimed
✅ Real PostgreSQL concurrency: exactly one acquired (got 1)
✅ Real PostgreSQL concurrency: exactly one already_claimed (got 1)
✅ Real PostgreSQL concurrency: acquired claim has status=executing
✅ Idempotency test: first attempt acquired
✅ Idempotency test: retry handled safely
✅ Fail-closed: returns unavailable when DB down
✅ Fail-closed: is_acquired() = False
✅ Fail-closed: error message present
✅ Strict concurrency: exactly one acquired (got 1)
✅ Strict concurrency: exactly one already_claimed (got 1)

PASSED: 17 | FAILED: 0
```

### Key Assertions

1. **Only one ACQUIRED** per contract (even with 2+ concurrent callers)
2. **All others get ALREADY_CLAIMED** (not errors, clean rejection)
3. **Durable row in DB** with `status=executing`, visible on re-query
4. **Idempotency safe** — retry with same key doesn't create duplicate rows
5. **Fail-closed works** — when DB down + flag ON → unavailable (not acquired)

## Verifying Durable State

After tests pass, verify database state:

```bash
# Query all pending claims from staging PostgreSQL
psql $DATABASE_URL << 'SQL'
SELECT 
  contract_id,
  claimant_id,
  execution_id,
  status,
  created_at
FROM action_execution_claims
WHERE status = 'executing'
ORDER BY created_at DESC
LIMIT 10;
SQL
```

Expected: Rows for each test contract, all with `status=executing`, one per `contract_id`.

## Recording Results

Create a log file with exact output:

```bash
python3 test_phase_4b0_1b_concurrency.py > /tmp/4b0_1b_results.txt 2>&1

# Upload or attach to PR
cat /tmp/4b0_1b_results.txt
```

**Format for verification log:**
```
Date: 2026-07-13
Environment: Render staging PostgreSQL
FEATURE_ATOMIC_CLAIMS: true
PostgreSQL Status: Connected
Migrations: Run (action_execution_claims exists)

Test Results:
  PASSED: 17 | FAILED: 0
  
Winner/Loser Verification:
  Thread 1: ACQUIRED (owns claim)
  Thread 2: ALREADY_CLAIMED (rejected)
  Thread 3: ALREADY_CLAIMED (rejected)
  
Database Durable State:
  Rows in action_execution_claims: 3 test contracts
  All status: executing
  All have unique execution_id
  No duplicates per contract_id
  
Idempotency Test:
  Same idempotency_key: Handled safely ✅
  No duplicate rows created: Verified ✅

Fail-Closed Test:
  PostgreSQL down + flag ON: Returns unavailable ✅
  Never falls back to non-atomic: Verified ✅

Conclusion: Phase 4B0.1B VERIFIED IN STAGING ✅
```

## Troubleshooting

### Tests Skipped (PostgreSQL not configured)

```
⚠ PostgreSQL not configured — running mock tests only
```

**Fix:**
1. Verify `DATABASE_URL` is set and correct
2. Test connection: `psql $DATABASE_URL -c "SELECT 1;"`
3. Verify `FEATURE_ATOMIC_CLAIMS=true`

### Tests Fail: "ALREADY_CLAIMED returned for all"

```
❌ Real PostgreSQL concurrency: exactly one acquired (got 0)
```

**Cause:** Likely sequential execution (not concurrent), or previous test rows blocking.

**Fix:**
1. Use unique contract IDs per test run
2. Verify synchronization barrier is working
3. Check: are threads actually running in parallel? Add logging.

### Database Error: "table action_execution_claims does not exist"

**Fix:**
1. Verify migrations ran: `psql $DATABASE_URL -c "\dt"`
2. Re-run migrations: `python3 -c "from core.database_migrations import run_migrations; run_migrations()"`
3. Check app startup logs for migration errors

## What Passes = Green Light for Phase 4B0.1C

Once all 17 tests pass against staging PostgreSQL:

✅ **Can proceed to Phase 4B0.1C wiring:**
1. Wire `ActionGateway.approve()` to call `claim_contract_execution()`
2. Update approval flow to check `result.is_acquired()` before dispatch
3. Run 48+ hours of staging traffic
4. Monitor claim success rate (should be 100% unique claims)

🚫 **Cannot proceed if:**
- Any test fails
- Claims not durable in PostgreSQL
- Winner/loser not correctly distinguished
- Idempotency broken

## After Phase 4B0.1B Verification

Update docs:
```bash
git commit -m "chore(phase-4b0): Phase 4B0.1B verified against staging PostgreSQL

- Concurrency test: 17/17 pass
- Database state: Durable, correct winner/loser
- Idempotency: Safe across retries
- Fail-closed: PostgreSQL down handled correctly

Ready for Phase 4B0.1C wiring.
"
```

Then begin Phase 4B0.1C staging rollout.

## Reference

- **Test file:** `test_phase_4b0_1b_concurrency.py`
- **Health check:** `core/atomic_claims_health.py`
- **Schema:** `core/migrations/001_action_execution_claims.sql`
- **API:** `core/atomic_claim_repository.py` with `ClaimAcquisitionResult`
