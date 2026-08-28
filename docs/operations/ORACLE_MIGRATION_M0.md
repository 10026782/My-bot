# Oracle Migration — M0 Readiness

**Scope: repository-side readiness only.** No Oracle resource was provisioned, no Render/Vercel/DNS setting was changed, no secret was rotated, no webhook was re-registered, and no staging deploy happened. This slice only adds files to this repo; see "Stop condition" at the bottom.

## Live Render verification (2026-08-28)

The prior migration audit (`FULL MIGRATION POSSIBLE — REMEDIATION REQUIRED`) left several items as repo-evidence-only (`STATIC VERIFIED / RUNTIME NOT ESTABLISHED`). During M0, read-only queries against the Render API (`GET /v1/services`, `GET /v1/services/{id}/env-vars` — key names only; a handful of already-non-secret operational values were also read) resolved a few of them with actual dashboard evidence:

| Question | Audit assumption | Live evidence |
|---|---|---|
| Is `core/predeploy.py` wired as Render's Pre-Deploy Command? | Contradictory docs, marked unresolved | **Confirmed wired** — `preDeployCommand: "python -m core.predeploy"` |
| Is Auto-Deploy on for `main`? | `DEPLOYMENT.md` said "Yes" | **`autoDeploy: "no"`** — deploys are manual |
| Is `/health` configured as Render's platform health check? | `DEPLOYMENT.md` said `/health` | **`healthCheckPath: ""`** — not configured, despite the route existing in `app.py` |
| Is PostgreSQL required in production, or staging-only? | Docs implied staging-only; `run_migrations()` no-ops gracefully without `DATABASE_URL` | **Required** — `FEATURE_ATOMIC_CLAIMS=true` and `DATABASE_URL` are both set live |
| Render plan / cost baseline | Unknown | Plan `starter` (paid), region `virginia`, `numInstances: 1`, `ipAllowList: 0.0.0.0/0` |

Two additional discrepancies surfaced, not fixed here (out of scope — they're facts about production, not repo readiness):

- **Google Workspace is not actually dormant.** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` are all set in production, contradicting `CLAUDE.md`'s "(currently frozen)" note. Migrate these values as-is; whether the integration is truly inactive needs a separate check, not assumed either way.
- **A malformed env var key exists on Render**: literally named `GOOGLE_DRIVE_FOLDER_IDGOOGLE_DRIVE_FOLDER_IDGOOGLE_DRIVE_FOLDER_ID` (alongside a separate, correctly-named `GOOGLE_DRIVE_ARTIFACT_FOLDER_ID`). Almost certainly a dashboard copy-paste artifact. Flagged for the owner to clean up directly in Render — not guessed at or silently corrected here.
- `SETUP_WEBHOOK=1` is set permanently in production, though `.env.example` documents it as a one-time flag meant to be removed after first webhook registration. Not changed here; carried into `.env.oracle.example` with a note.

No secret values were extracted or written anywhere in this repo. Where a real value was needed for `.env.oracle.example`, it's marked `# manual migration` — copy it by hand from the Render dashboard when M1 actually needs it.

## PostgreSQL decision: REQUIRED

`FEATURE_ATOMIC_CLAIMS=true` + `DATABASE_URL` set, confirmed live — not a repo-evidence inference. `docker-compose.oracle.yml` includes `postgres` as a normal always-on service, not gated behind a profile. `core/database_migrations.py::run_migrations()` still no-ops gracefully if `DATABASE_URL` is absent, so removing the service and unsetting the var remains a safe, supported path if atomic claims are ever deliberately turned off — that flexibility didn't need building, it already exists in the app.

## Files added/changed

See the PR description for the full table. In brief: `Dockerfile`, `docker-compose.oracle.yml`, `Caddyfile.oracle`, `.env.oracle.example`, `.github/workflows/deploy-oracle.yml`, `scripts/oracle/{backup_postgres,restore_postgres,healthcheck_alert}.sh`, plus doc corrections to `core/predeploy.py` and `docs/operations/DEPLOYMENT.md`. No file under `tools/`, `core/` (business logic), `airtable_*`, `tool_registry.py`, or `dispatcher.py` was touched — this slice is deploy/ops scaffolding only.

## Unresolved infrastructure decisions (intentionally left open)

- **Off-VM backup destination.** `scripts/oracle/backup_postgres.sh` supports `BACKUP_DEST_CMD` (a pluggable shell command — rclone, `aws s3 cp`, `scp`, etc.) but ships with none configured. Until one is set, backups are local-only on the same VM as the database — not a real backup. This needs an explicit choice (which provider, which retention) before Render can be decommissioned per the audit's Phase 16 criteria.
- **Domain name.** Still doesn't exist (per the original audit). `Caddyfile.oracle` and `docker-compose.oracle.yml` take it as `BOSS_DOMAIN`, supplied at deploy time — no hostname is hard-coded anywhere in this slice.
- **Frontend placement.** `tma-frontend/` is not touched by this slice; the audit's recommendation (stay on Vercel) still stands and nothing here assumes otherwise.

## How to test this slice locally (no Oracle VM required)

```bash
# 1. Build the image (native arch — fast, sanity check only)
docker build -t boss-bot-backend:test .

# 2. Build for arm64 via QEMU emulation (NOT native ARM64 hardware —
#    see "ARM64 status" in the PR description for exactly what this does
#    and doesn't prove)
docker buildx build --platform linux/arm64 -t boss-bot-backend:arm64-test .

# 3. Compose config validates
BOSS_DOMAIN=test.local POSTGRES_PASSWORD=test docker compose -f docker-compose.oracle.yml config -q

# 4. Full local stack (fill .env.oracle.example -> a local scratch env file first)
cp .env.oracle.example /tmp/backend.env   # fill with test/dummy values, never real secrets
BOSS_ENV_FILE=/tmp/backend.env BOSS_DOMAIN=test.local POSTGRES_PASSWORD=test \
  docker compose -f docker-compose.oracle.yml up -d
curl -f http://localhost/health   # via Caddy, once BOSS_DOMAIN resolves locally, or:
docker compose -f docker-compose.oracle.yml exec backend \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:10000/health').read())"
```

## Stop condition

M0 is repository readiness and a PR only. Per the task boundary, this slice does **not**: provision Oracle, deploy to any staging host, change Render, change Vercel, change DNS, register webhooks, rotate secrets, or merge its own PR. M1 (provisioning) requires a separate, explicit instruction.
