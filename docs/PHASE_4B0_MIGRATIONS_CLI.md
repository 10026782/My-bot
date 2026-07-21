# PostgreSQL Migrations CLI — Phase 4B0.1A

**Purpose:** Explicit, idempotent CLI for running PostgreSQL migrations before app startup.

**Status:** ✅ Implemented. Render's actual Pre-Deploy Command is now `python -m core.predeploy` (see `docs/PHASE_4B0_1B_STAGING_RUNBOOK.md`/`core/predeploy.py` — it runs `run_migrations()` below, then the Emergency Stop preflight, in sequence); this module remains a standalone, directly-runnable CLI and is unchanged.

---

## Overview

Phase 4B0.1A atomic coordination requires PostgreSQL schema initialization (`action_execution_claims` table). Rather than running migrations as a side effect of app startup (risky, blocks startup, unclear error handling), migrations run as an explicit CLI command, invoked by `core/predeploy.py` in Render's **Pre-Deploy Command** phase, before the app starts.

**Benefits:**
- ✅ Explicit — migrations run first, then app starts
- ✅ Idempotent — safe to run on every deploy
- ✅ Fail-fast — deploy blocked if migrations fail (non-zero exit)
- ✅ Clear logging — dedicated migration output, not mixed with app logs
- ✅ Production-safe — app.py only calls health checks (which verify migrations already ran)

---

## CLI Usage

### Direct invocation (local development)
```bash
# Run migrations manually
python -m core.database_migrations

# Exit codes:
#   0 = success (or no-op if PostgreSQL not configured)
#   1 = failure (PostgreSQL unavailable or migration failed)
```

### Render Pre-Deploy Command
In Render Dashboard → Settings → Build & Deploy:

```
Pre-Deploy Command: python -m core.predeploy
```

`core/predeploy.py` calls this module's `run_migrations()` first, then the Emergency Stop preflight — see `core/predeploy.py`'s own docstring. This hook runs after `pip install -r requirements.txt` (Build Command) but before `gunicorn app:app` (Start Command).

**Render behavior:**
- If exit code = 0: deploy proceeds, app starts
- If exit code = 1: deploy **fails**, rollback, app does NOT start

---

## How It Works

### 1. Migration Execution (Pre-Deploy, explicit)

When `python -m core.database_migrations` runs:

1. **Check PostgreSQL configuration** (DATABASE_URL or DATABASE_HOST/PORT/etc.)
   - If PostgreSQL not configured: return 0 (no-op, not an error)
   - If configured but unreachable: return 1 (fail the deploy)

2. **Find all migrations** from `core/migrations/*.sql` (sorted by name)

3. **Execute each migration** idempotently:
   ```sql
   -- Example: core/migrations/001_action_execution_claims.sql
   CREATE TABLE IF NOT EXISTS action_execution_claims (
       contract_id TEXT PRIMARY KEY,
       claimant_id TEXT NOT NULL,
       ...
   );
   ```
   - If already exists: CREATE TABLE IF NOT EXISTS skips silently
   - Atomic: commit on success, rollback on error per migration

4. **Log results:**
   ```
   2026-07-12 14:23:45 [INFO] Running migration: 001_action_execution_claims.sql
   2026-07-12 14:23:46 [INFO] Migration succeeded: 001_action_execution_claims.sql
   2026-07-12 14:23:46 [INFO] All migrations completed successfully
   ```

5. **Exit with code 0 on success, 1 on failure**

### 2. App Startup (health check only)

When app.py starts, it NO LONGER runs migrations. Instead:

```python
# app.py, lines 133-144
try:
    from feature_flags import is_enabled
    if is_enabled("FEATURE_ATOMIC_CLAIMS"):
        from core.atomic_claims_health import log_health_on_startup
        log_health_on_startup()  # Checks if table exists, fails if not
except ImportError:
    pass
except Exception as e:
    logging.error(f"Atomic claims health check failed: {e}")
    raise
```

**Health check behavior:**
- ✅ Flag OFF: no-op, proceeds normally
- ✅ Flag ON, migrations completed: logs "READY", proceeds
- ❌ Flag ON, migrations not completed: raises RuntimeError, startup fails

---

## Scenarios

### Scenario 1: Normal Deploy (staging)

```
1. Render receives push to main
2. Build: pip install -r requirements.txt
3. Pre-Deploy: python -m core.predeploy (runs this module's migrations, then the Emergency Stop preflight)
   ✅ PostgreSQL reachable
   ✅ Ran 1 migration (001_action_execution_claims.sql)
   ✅ Exit code = 0
4. Start: gunicorn app:app
   ✅ FEATURE_ATOMIC_CLAIMS=true (from env)
   ✅ Health check: table exists, logs "READY"
   ✅ App starts normally
```

### Scenario 2: PostgreSQL Not Configured (production)

```
1. Render receives push to main
2. Build: pip install -r requirements.txt
3. Pre-Deploy: python -m core.predeploy (runs this module's migrations, then the Emergency Stop preflight)
   ℹ️ PostgreSQL not configured (DATABASE_URL empty)
   ✅ No-op (return 0, not an error)
4. Start: gunicorn app:app
   ✅ FEATURE_ATOMIC_CLAIMS=false (default, production)
   ✅ App starts normally, atomic claims disabled
```

### Scenario 3: PostgreSQL Down (deploy failure)

```
1. Render receives push to main
2. Build: pip install -r requirements.txt
3. Pre-Deploy: python -m core.predeploy (runs this module's migrations, then the Emergency Stop preflight)
   ❌ PostgreSQL unreachable (connection timeout)
   ❌ Failed to get database connection for migrations
   ❌ Exit code = 1
4. Render: STOPS deploy here
   ❌ Start command never runs
   ❌ Previous version remains active
   ❌ Logs visible in Render Dashboard
```

**Action:** Restore PostgreSQL connectivity, retry deploy.

### Scenario 4: Idempotent Re-deploy (no schema changes)

```
1. Render receives push to main
2. Build: pip install -r requirements.txt
3. Pre-Deploy: python -m core.predeploy (runs this module's migrations, then the Emergency Stop preflight)
   ✅ PostgreSQL reachable
   ✅ Ran 1 migration: 001_action_execution_claims.sql
      (table already exists → CREATE TABLE IF NOT EXISTS does nothing)
   ✅ Exit code = 0
4. Start: gunicorn app:app
   ✅ App starts normally
```

No side effects, no duplicates, no errors.

---

## Adding New Migrations

To add a new migration:

1. Create `core/migrations/002_new_schema.sql`
   ```sql
   -- Phase 4B0.1X — Description
   -- Idempotent schema changes
   ALTER TABLE action_execution_claims ADD COLUMN new_field TEXT UNIQUE;
   CREATE INDEX idx_new_field ON action_execution_claims(new_field);
   ```

2. Use `IF NOT EXISTS` / `IF EXISTS` to ensure idempotency
   - `CREATE TABLE IF NOT EXISTS`
   - `CREATE INDEX IF NOT EXISTS`
   - `ALTER TABLE IF EXISTS`

3. Next deploy will automatically pick up `002_*.sql` and run it in order

4. Verify in logs:
   ```
   2026-07-12 14:23:46 [INFO] Running migration: 002_new_schema.sql
   2026-07-12 14:23:47 [INFO] Migration succeeded: 002_new_schema.sql
   ```

---

## Troubleshooting

### Pre-Deploy Command Fails with "PostgreSQL connection failed"

**Cause:** `FEATURE_ATOMIC_CLAIMS=true` but PostgreSQL unreachable.

**Fix:**
1. Verify `DATABASE_URL` or `DATABASE_HOST`, `DATABASE_PORT`, etc. in Render env
2. Verify PostgreSQL instance is running (check Render dashboard)
3. Verify credentials are correct
4. Retry deploy

### Pre-Deploy Command Succeeds, But App Won't Start

**Cause:** Health check finds table missing (somehow migrations were skipped).

**Logs:** `FATAL: FEATURE_ATOMIC_CLAIMS is enabled but infrastructure not ready.`

**Fix:**
1. Check Render events log — did pre-deploy actually run?
2. Manually run: `heroku run python -m core.database_migrations` (or equivalent for your platform)
3. Restart app

### Pre-Deploy Command Takes Too Long

**Default:** Simple migration runner, no timeout.

**If needed:** Monitor deploy time in Render Dashboard. Normal time: < 5 seconds.

If >30s:
1. Check if PostgreSQL is slow or overloaded
2. Add caching/pooling improvements to `core/database.py` if needed

---

## Migration State Tracking

Migrations are NOT tracked in a separate `schema_migrations` table. Idempotency is achieved by SQL constraints:

- `CREATE TABLE IF NOT EXISTS` — skipped if table exists
- `CREATE INDEX IF NOT EXISTS` — skipped if index exists
- Rollback on failure (per migration, within transaction)

This is safe for our use case (small schema, infrequent changes). If migrations become frequent or complex, consider adding a migration tracking table.

---

## Related Documentation

- `docs/PHASE_4B0_1A_ATOMIC_CLAIMS.md` — Schema design, table structure
- `docs/PHASE_4B0_1C_STAGING_WIRING.md` — Staging deployment checklist
- `docs/operations/DEPLOYMENT.md` — Render deployment steps
- `core/database_migrations.py` — Implementation

---

## Key Points

✅ **Explicit:** Migrations run via pre-deploy command, before app starts  
✅ **Idempotent:** Safe to run on every deploy, uses `IF NOT EXISTS`  
✅ **Fail-fast:** Non-zero exit blocks deploy if migrations fail  
✅ **Production-safe:** App.py only checks health, never runs migrations  
✅ **Backward compatible:** PostgreSQL not configured = no-op, not error  

