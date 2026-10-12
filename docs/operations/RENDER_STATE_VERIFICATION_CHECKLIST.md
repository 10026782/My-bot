# Render — Manual State Verification Checklist (read-only)

**Purpose:** establish, from the Render dashboard itself, what production and staging actually are today. The repo's documents disagree: `docs/operations/DEPLOYMENT.md` / `ORACLE_MIGRATION_M0.md` say `FEATURE_ATOMIC_CLAIMS=true` and `DATABASE_URL` were set in production (read 28/08/2026), while `BOSS_PRODUCTION_RUNTIME_MAP.md` / `AI_CONTEXT.md` list atomic claims as *dormant*. Neither is current-date proof.

**Strictly read-only.** Look, record, close. **Do not edit any env var, flag, plan, service or database**; do not click Deploy/Restart/Suspend. **Do not paste secret values anywhere** — record only the masked forms requested below. Return the filled "Findings" table at the bottom.

Repo facts to compare against (verified in code on branch `ccr-8ce58b74-gz57gr`):

* `gunicorn.conf.py` — auto-loaded by `gunicorn app:app`: `workers = 1`, `worker_class = "gthread"`, `threads = 4`. One process, up to 4 request threads. Pool in `core/database.py`: 1–5 connections.
* The Start Command is documented as `gunicorn app:app` (`DEPLOYMENT.md`); the Pre-Deploy Command as `python -m core.predeploy` (runs the DB migrations, then the Emergency Stop preflight).
* `core/database.py` reads `DATABASE_URL` first; only if it is absent does it use `DATABASE_HOST/PORT/NAME/USER/PASSWORD`.

## A. Services — is there a staging, or only production?

Dashboard → *Services* (and *Projects/Environments*, if used).

| # | Look at | Record |
|---|---|---|
| A1 | The list of services for this app | name, type (Web Service / Worker / Static), **plan**, region, instance count |
| A2 | Is there a **second** web service that is clearly staging (name, branch, different URL)? | yes/no; name; which Git branch it deploys; Auto-Deploy on/off |
| A3 | For *each* service → Settings → Build & Deploy | branch, **Auto-Deploy** (expected `No` for production per the 28/08 read), **Start Command**, **Pre-Deploy Command**, Health Check Path |
| A4 | Dashboard → *Databases* | every PostgreSQL instance: name, **PG version**, plan, region, **Created**, status (and any *expires* notice) |
| A5 | Any *Environment Groups* shared by services | names, and which services link them — a group shared between staging and production is a red flag |

## B. Which PostgreSQL is each service actually using?

Do **not** infer from names. For each service → *Environment*:

| # | Look at | Record (masked — never the password) |
|---|---|---|
| B1 | Key `DATABASE_URL` — present? | present / absent |
| B2 | If present: the **host part only** and the database name | e.g. `dpg-xxxx…` (first 8 chars) · `*.render.com` vs `*.neon.tech` vs an IP/other · db name. *Internal* (`dpg-…-a`) vs *external* (`….virginia-postgres.render.com`) |
| B3 | Which dashboard database from A4 that host belongs to (match the `dpg-…` id) | database name, or "none of them" |
| B4 | Legacy discrete keys `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD` | each present/absent (only consulted if `DATABASE_URL` is absent) |
| B5 | Do staging and production point at the **same** database? | yes/no — must be **no** |

*Optional, read-only, from the service's Shell tab (only if available on the plan — otherwise skip):*
```bash
python3 - <<'EOF'
import os, urllib.parse as u, psycopg2
url = os.environ.get("DATABASE_URL", "")
p = u.urlsplit(url) if url else None
print("host:", (p.hostname[:12] + "…") if p and p.hostname else "none", "| db:", p.path.lstrip("/") if p else "none")
if url:
    c = psycopg2.connect(url, connect_timeout=5); cur = c.cursor()
    cur.execute("select current_database(), split_part(version(),' ',2)"); print(cur.fetchone())
    cur.execute("select to_regclass('public.action_execution_claims') is not null"); print("claims table:", cur.fetchone()[0])
    cur.execute("select status, count(*) from action_execution_claims group by 1 order by 1"); print("claims by status:", cur.fetchall())
EOF
```
(Read-only `SELECT`s; prints the host truncated, never the password.)

## C. Feature flags and gateway settings (key names and values — flags are not secrets)

Per service → *Environment*. Record the exact value or "absent":

`FEATURE_ATOMIC_CLAIMS` · `FEATURE_ACTION_CONTRACT_PERSISTENCE` · `FEATURE_ACTION_GATEWAY` · `FEATURE_EPISODIC_CAPTURE` · `FEATURE_MEMORY_SHADOW_LOGGING` · any `EMERGENCY_STOP_*` (note these are Airtable-backed at runtime; the env var is not authoritative) · `SETUP_WEBHOOK` (documented as `1` in production on 28/08/2026 and 01/09/2026 — confirm) · `PORT` · `WEB_CONCURRENCY`.

Interpretation (for the reviewer, not for the person filling this in): `FEATURE_ATOMIC_CLAIMS=true` **and** a working `DATABASE_URL` means every guarded write needs a live PostgreSQL claim, so a database outage = all guarded writes refused. `true` with no usable `DATABASE_URL` = writers using `require_claim` fail closed.

## D. Workers / processes / instances

| # | Look at | Record |
|---|---|---|
| D1 | Service → Settings → **Start Command** | exact text. Expected `gunicorn app:app`. **Any `-w`/`--workers`/`-k`/`--threads` flag overrides `gunicorn.conf.py`** — record it |
| D2 | Env var `WEB_CONCURRENCY` | present/absent + value (the config file's `workers = 1` takes precedence over it, but a stray value is worth knowing) |
| D3 | Service → *Scaling* | **number of instances** (the 28/08 read: `numInstances: 1`) and whether auto-scaling is enabled. `gunicorn.conf.py` explicitly forbids more than one instance until a distributed scheduler/leader lock exists |
| D4 | Service → *Logs*, search for the startup lines | one `post_worker_init`/scheduler start per deploy (more than one = more than one process) |
| D5 | Service → *Metrics* | instance type (RAM/CPU) and whether memory ever approaches the limit |

## E. Staging isolation (matters before ANY staging soak)

If a staging service exists, it must not be able to act on production data or users:

| # | Check | Required |
|---|---|---|
| E1 | `AIRTABLE_BASE_ID` differs between staging and production (compare only the last 4 characters) | different base |
| E2 | `TELEGRAM_TOKEN` differs (compare only the bot id before `:`) and the staging bot is a different bot | different bot |
| E3 | `DATABASE_URL` differs (B5) | different DB |
| E4 | Twilio/WhatsApp, Google OAuth refresh token, `ELIYAHU_CHAT_ID`, `GOOGLE_DRIVE_*_FOLDER_ID` — shared with production? | ideally separate; record |
| E5 | Webhook registration (`SETUP_WEBHOOK`) on staging | must not re-register the production bot's webhook |

If any of E1–E3 is "same as production", **stop and report** — do not run any M1 soak against that staging service.

## F. Database plan, backups and limits (decision input for the Neon move)

For each Render PostgreSQL in A4 → *Info / Backups / Metrics*:

* plan and monthly cost, storage size and **current usage**, connection limit and typical connection count;
* **backup/PITR settings and retention** Render provides, and the date of the last successful backup;
* anything marked *free tier*/*expires* (Render's free PostgreSQL expires — a dated expiry on a staging database matters).

## Findings (fill and return — no secret values)

| Item | Production | Staging (or "none") |
|---|---|---|
| Service name / plan / region / instances (A1, D3) | | |
| Auto-Deploy / Start Command / Pre-Deploy (A3, D1) | | |
| `WEB_CONCURRENCY` (D2) | | |
| `DATABASE_URL` present? host prefix + db name (B1–B2) | | |
| Matches which Render DB? PG version (A4, B3) | | |
| Legacy `DATABASE_*` keys (B4) | | |
| Staging DB ≠ production DB? (B5) | n/a | |
| `FEATURE_ATOMIC_CLAIMS` (C) | | |
| `FEATURE_ACTION_CONTRACT_PERSISTENCE` (C) | | |
| `FEATURE_ACTION_GATEWAY` (C) | | |
| `FEATURE_EPISODIC_CAPTURE` / `FEATURE_MEMORY_SHADOW_LOGGING` (C) | | |
| Shared env group (A5) | | |
| Staging isolation E1–E5 | n/a | |
| DB plan, cost, size, backups, expiry (F) | | |
| Optional Shell read: claims table exists? counts by status | | |

**What this unlocks:** a verified answer to "is PostgreSQL really in use in production, and is `FEATURE_ATOMIC_CLAIMS` really on?" — which decides how risky M3 is and corrects whichever of `DEPLOYMENT.md` / `BOSS_PRODUCTION_RUNTIME_MAP.md` is wrong. Nothing in this checklist changes production; any change it suggests needs a separate owner instruction.
