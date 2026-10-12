# Neon Migration — M0 Readiness

**Scope: repository-side readiness only** (same boundary as [`ORACLE_MIGRATION_M0.md`](ORACLE_MIGRATION_M0.md)). No Neon project was created, no Render/Vercel setting was changed, no secret was created or rotated, nothing was deployed. This slice adds operator tooling and documentation; see "Stop condition" at the bottom. The only runtime file changed is `core/database.py::get_conn()` (M0.5, owner-approved — see "Finding"); nothing under `tools/`, `airtable_*`, `tool_registry.py` or `dispatcher.py`, and no claim semantics changed.

## What this migration is (and is not)

- **Is:** moving the *PostgreSQL database* — today the one behind `DATABASE_URL`, holding `action_execution_claims` (atomic execution claims / idempotency), `durable_turn_state`, `external_poll_leases`, and the shadow/telemetry tables — to **Neon**. Airtable stays the business/durable state; the app host stays where it is.
- **Is not:** a VM migration. Per the Render read recorded in `ORACLE_MIGRATION_M0.md` (28/08/2026 snapshot — *not* current-date proof): plan `starter`, region `virginia`, `numInstances: 1`, manual deploys, `preDeployCommand: python -m core.predeploy`. Only `DATABASE_URL` changes; `core/predeploy.py` keeps running `core/database_migrations.py` against whatever URL it is given.
- **Supersedes** only the PostgreSQL half of the Oracle plan (`docker-compose.oracle.yml`'s `postgres` service, `scripts/oracle/{backup,restore}_postgres.sh`). Those files are untouched.

Why Neon: it is real PostgreSQL, so `core/atomic_claim_repository.py`'s `INSERT ... ON CONFLICT DO NOTHING RETURNING`, the multi-step `SELECT ... FOR UPDATE` recovery transaction, `core/turn_state_repository.py`'s versioned CAS and `core/external_poll_lease.py`'s `NOW() + INTERVAL` upsert all keep their exact semantics. Turso/D1 would require rewriting the repository SQL, the migration runner and (for D1) giving up interactive transactions.

**Next:** [`NEON_M1_STAGING_CHECKLIST.md`](NEON_M1_STAGING_CHECKLIST.md) (14-check staging run, plan only) · [`NEON_BACKUP_PLAN_DRIVE.md`](NEON_BACKUP_PLAN_DRIVE.md) (Drive backups, plan only) · [`RENDER_STATE_VERIFICATION_CHECKLIST.md`](RENDER_STATE_VERIFICATION_CHECKLIST.md) (read-only production/staging fact-finding).

## Files added

| File | Purpose |
|---|---|
| `scripts/neon/neon_readiness_check.py` | Read-only probe of any PG endpoint: URL/TLS shape, connect latency vs the app's 5s `connect_timeout`, claim-table constraints, in-flight claims, opt-in concurrency race probe, opt-in idle/suspend probe. |
| `scripts/neon/pg_transfer.sh` | `dump` / `restore` / `counts` / `verify` between two endpoints with `pg_dump`/`pg_restore`/`psql` only. URLs from env vars (never argv). Also the off-platform backup path. |
| `test_neon_readiness_check.py` | DB-free unit checks of the probe's URL analysis, redaction and result shape. |
| `.env.example` | Comment-only Neon connection notes. |

## What was actually proven (local, PostgreSQL 16, two scratch clusters)

| Claim | Evidence |
|---|---|
| Repo migrations `001`–`006` apply cleanly to an empty UTF-8 PG | `python -m core.database_migrations` → all 9 files succeeded |
| `pg_transfer.sh` round-trips a populated DB | dump → restore → `verify`: identical counts in 9 tables |
| `restore` refuses without `--yes`, and refuses when target == source | both refusals observed |
| `verify` detects divergence | deleted one target row → `VERIFY FAILED` with a diff, exit 1 |
| The concurrency probe measures real atomicity | 8 threads × 3 scenarios (same contract+key; different contracts sharing a key; same contract with different keys) → exactly 1 winner each. **Negative control:** same race on a table with no UNIQUE constraints → 8 winners, so the probe can fail |
| Cutover gate works | `--require-no-inflight` with one `executing` claim → FAIL, exit 1 |
| The probe leaves nothing behind | no `neon_probe_*` table remained |

**Not proven (needs a real Neon endpoint — first M1 task):** TLS/`sslmode=require` handshake, pooled (`-pooler`) endpoint behaviour, real cold-start time versus `connect_timeout=5`, what a Free-plan scale-to-zero does to idle connections, free-plan quota headroom, restore time and PITR window.

## Finding: the app's pool does not survive a server-side connection close

`core/database.py` hands out `psycopg2.pool.SimpleConnectionPool` connections without validating them. Neon Free suspends compute after 5 idle minutes (not disableable per vendor docs — verify), and the server then drops idle connections.

Reproduced locally with the real `core.atomic_claim_repository.claim_contract_execution()` and `pg_terminate_backend` standing in for the suspend:

| Step | Result |
|---|---|
| healthy pool | `acquired` |
| server closes all pooled backends | — |
| **first claim afterwards** | **`error`** — "server closed the connection unexpectedly"; **no claim row written, nothing executed** |
| second claim | `acquired` (pool self-heals) |

So this is **fail-closed and safe** — a claim is never granted on a dead link — but with Neon Free it would recur after every idle gap, surfacing as one failed approval attempt the owner must retry. It would also hit `durable_turn_state` first, since that path is live.

**M0.5 — APPLIED (owner-approved 06/10/2026, `core/database.py::get_conn()` only; CODE DONE, NOT VERIFIED IN PROD).** Validate on checkout, discard a dead connection, retry once, otherwise return `None` (the existing "unavailable → fail closed" contract). Scope guard: no change to `atomic_claim_repository.py` claim semantics, no retry of any external action, no flag/`DATABASE_URL`/deploy change.

*Cross-Layer Planning Gate assessment:* `SINGLE-LAYER` — one function in the persistence-connection layer; contract unchanged (`get_conn()` still returns a connection or `None`; all callers already treat `None` as unavailable/fail-closed); no authority, lifecycle, routing or evidence change.

*Verification (local PostgreSQL 16):* `test_database_conn_validation.py` (fake pool: healthy, dead→fresh, dead×2→`None`, `getconn` failure→`None`, unconfigured→`None`); real scenario with the real repository and a server-side `pg_terminate_backend` — first claim after the close `acquired` (was `error`), duplicate → `already_claimed`, same key on another contract → `idempotency_conflict`; and `test_phase_4b0_1a_atomic_claims`, `test_phase_4b0_1b_concurrency` (+ `_regression`, `_regression_mock`), `test_phase_4b0_1c_concurrent_approvals`, `test_phase_4b2_wiring`, `test_turn_state_repository`, `test_external_execution_boundary`/`_validator` (leases), `test_approval_concurrency`, `test_c84_tma_approval_ttl`, `test_pr0c0_tma_approval_truthfulness`, `test_predeploy`, `test_usage_telemetry`, `test_episodic_memory_repository`, `test_memory_shadow_logging`, `test_phase_4b_rollout_tooling`, `smoke_tests.py` all pass. Cost: one extra round trip per checkout. Still to confirm on a real Neon endpoint (M1): `neon_readiness_check.py --idle-seconds 330`.

The applied code:

```python
def get_conn():
    for _ in range(2):
        pool = get_pool()
        if pool is None:
            return None
        try:
            conn = pool.getconn()
        except Exception as e:
            logger.error(f"Failed to get connection from pool: {e}")
            return None
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.rollback()
            return conn
        except Exception:
            try: pool.putconn(conn, close=True)
            except Exception: pass
    return None
```

Re-run `neon_readiness_check.py --idle-seconds 330` against the real endpoint to confirm on real Neon (the probe opens its own plain connection, so it shows the *server's* behaviour; the app-level fix is covered by the tests above).

## Phases

| Phase | Content | Gate to proceed |
|---|---|---|
| **M0** (this slice) | Tooling, docs, local proof | Owner reviews; explicit go for M1 |
| **M0.5** | Connection-validation hardening above (+ `test_database_conn_validation.py`) | **DONE (code, local tests green); not deployed.** Deploy rides the next manual Render deploy |
| **M1** | Create Neon project (region near Render `virginia`, e.g. AWS us-east), **staging first**: point the staging service's `DATABASE_URL` at it; run migrations; run readiness check with `--concurrency-probe --idle-seconds 330` | All checks PASS on real Neon; cold connect well under 5s; idle probe understood |
| **M2** | Staging soak: approve/reject flows, duplicate-approve race, restart survival | No unexplained `error`/`unavailable` claim results |
| **M3** | Production cutover (below) | M2 clean; fresh backup exists off-platform |
| **M4** | Keep the old PG untouched and unused for a rollback window, then decommission | Owner decision after N clean days |

### M3 cutover runbook

1. **Preflight** (old DB): `SOURCE_DATABASE_URL=… DATABASE_URL=… python3 scripts/neon/neon_readiness_check.py --require-no-inflight` → must PASS. Any `executing`/`outcome_unknown` row is a human decision *before* the move (a claim row whose outcome is unknown must never be silently carried across).
2. **Quiesce:** tell the owner to stop approving; deploys are manual (`autoDeploy: no`), so nothing else restarts the app meanwhile.
3. `scripts/neon/pg_transfer.sh dump` against the old DB; ship it off-platform (`BACKUP_DEST_CMD`).
4. `restore <dump> --yes` into Neon using a **direct** endpoint, then `verify` → identical counts.
5. `neon_readiness_check.py --url-env TARGET_DATABASE_URL --concurrency-probe` on Neon → all PASS.
6. Set `DATABASE_URL` on the Render service to the Neon URL (pooled endpoint for the app is fine; keep `sslmode=require`), manual deploy. `preDeploy` migrations are idempotent.
7. **Verify, don't assume:** `/status`, `/boss_doctor` (`postgres_configured`), then one real low-risk approval end-to-end and a duplicate-approve attempt. Only then report done (CLAUDE.md "סיימתי = מאומת").

**Rollback:** the old DB is never written to by this process (restore targets Neon only; `pg_transfer.sh` refuses target == source), so reverting `DATABASE_URL` restores the previous state. Any claim rows created on Neon after cutover must first be exported (`dump` from Neon) and reviewed by a human — keep the window short.

## Risks and open decisions

- **Free-plan suspension/quota is a single point of availability.** `FEATURE_ATOMIC_CLAIMS` is fail-closed: if Neon is suspended-and-unwakeable or the free compute quota is exhausted, *every* guarded write is refused (safe, but a full approval outage). Mitigation: M0.5 hardening, alert on `unavailable` claim results, and a paid-plan fallback decision (Neon's paid plan or staying on the current PG) if Free proves marginal. Quotas and the PITR window quoted in the vendor comparison came from third-party aggregators — **confirm on Neon's own pricing page before M1.**
- **Backups:** Free-plan PITR is short; the real backup is a scheduled `pg_transfer.sh dump` with an off-platform `BACKUP_DEST_CMD`. The destination is **undecided** (same open item as Oracle M0).
- **Account/secret ownership:** the Neon URL lives only in the Render env (and a local scratch env for operators). Never commit it; the tools redact passwords in output.
- **Pooled vs direct endpoint:** pooled (pgbouncer, transaction mode) for the app; direct for `pg_dump`/`pg_restore`/DDL. Whether `SELECT ... FOR UPDATE` recovery behaves under the pooler on real Neon is an M1 check, not an assumption.
- **Production state is unverified here.** Which DB production actually uses today, and `FEATURE_ATOMIC_CLAIMS`'s live value, must be re-read from the Render dashboard at M1 — `BOSS_PRODUCTION_RUNTIME_MAP.md` and `DEPLOYMENT.md` disagree.

## Running the tools locally

```bash
export SOURCE_DATABASE_URL='postgresql://…'   # old DB
export TARGET_DATABASE_URL='postgresql://…?sslmode=require'   # Neon direct endpoint

python3 scripts/neon/neon_readiness_check.py --url-env SOURCE_DATABASE_URL --require-no-inflight
python3 scripts/neon/neon_readiness_check.py --url-env TARGET_DATABASE_URL --concurrency-probe --idle-seconds 330
scripts/neon/pg_transfer.sh dump
scripts/neon/pg_transfer.sh restore ./pg_dumps/boss_bot_<ts>.dump --yes
scripts/neon/pg_transfer.sh verify
python3 test_neon_readiness_check.py
```

`pg_dump` must be the same major version as, or newer than, the server.

## Stop condition

M0 is repository readiness only. It does **not**: create a Neon project, change Render or Vercel, rotate or create secrets, deploy, perform the production cutover, change `DATABASE_URL` or any flag, decommission PostgreSQL/Oracle, or merge anything. M1 requires a separate, explicit instruction.
