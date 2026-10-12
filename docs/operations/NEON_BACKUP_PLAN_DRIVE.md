# Neon PostgreSQL Backups → Google Drive — Plan

**Status: PLAN ONLY.** Nothing is configured: no scheduled job, no Drive folder, no key, no read-only DB role, no external automation. This document records the recommended design so that the implementation (a later, separately approved step) is mechanical. Owner decision recorded 06/10/2026: **Google Drive is the planned destination for PostgreSQL dumps taken outside Neon.** Context: [`NEON_MIGRATION_M0.md`](NEON_MIGRATION_M0.md); tools: `scripts/neon/pg_transfer.sh` (`dump` already supports `BACKUP_DEST_CMD`).

## 1. Why a logical dump to Drive at all

Neon Free keeps only a short point-in-time-restore window (confirm the exact window on Neon's own pricing page before relying on it). PITR/branching is the **fast, first-choice** recovery for "I broke something an hour ago"; the Drive dump is the **independent copy** for "the Neon project/account is gone or the window has passed". Drive is also outside Neon's failure domain, which is the point.

The data is tiny (claims, turn state, leases, a few shadow tables): dumps are expected in the tens-of-KB to low-MB range, so frequency and retention below are limited by *usefulness*, not cost.

## 2. What the dump is — and what it is not

* `pg_dump --format=custom --no-owner --no-privileges` of the whole database (already what `pg_transfer.sh dump` does), checked readable with `pg_restore --list`.
* It is **not** the business backup: Airtable remains the business/durable state and has its own history. The dump protects the *coordination* state: execution claims, durable turn state, poll leases, plus the shadow/telemetry tables.
* **Airtable `ActionContracts` is a second, independent record** of every contract's status (`executing`/`completed`/`failed`/`outcome_unknown`/…). That is what makes a stale restore recoverable (see §7, reconciliation).

## 3. Frequency

| Kind | When | Purpose |
|---|---|---|
| `daily` | once a day, 03:00 Asia/Jerusalem | RPO ≤ 24 h beyond Neon PITR |
| `pre-change` | on demand, **before** any cutover, migration, deploy that touches the DB, or flag change affecting claims | an exact "before" image |
| `manual` | on demand | investigations, restore drills |

Recommendation: **daily + pre-change**, not hourly. Claim volume is low, PITR covers the intra-day window, and an old claim row lost between dumps is reconstructable from Airtable (§7). Revisit (e.g. every 6 h) only if claim volume grows or the reconciliation in §7 proves painful. Backups are not outbound messages to people, so the Shabbat/holiday quiet-hours guard does not apply to them; the 03:00 slot is chosen for low load.

## 4. Retention

| Tier | Keep |
|---|---|
| daily | last 14 |
| weekly (Sunday's daily) | last 8 |
| monthly (1st of month) | last 6 |
| `pre-change` | 90 days (never auto-pruned inside the cutover window) |
| `manual` | until the owner deletes them |

Never prune below the **3 most recent verified** dumps, whatever the rule says. Drive pruning must be its own explicit step: `pg_transfer.sh`'s `RETENTION_DAYS` mtime pruning only touches the *local* `BACKUP_DIR`.

## 5. Naming convention and manifest

```
Drive: BOSS-DB-Backups/<env>/<YYYY>/<MM>/
  boss_bot_<env>_pg<major>_<YYYYMMDDTHHMMSSZ>_<kind>.dump.age
  boss_bot_<env>_pg<major>_<YYYYMMDDTHHMMSSZ>_<kind>.dump.age.sha256
  boss_bot_<env>_pg<major>_<YYYYMMDDTHHMMSSZ>_<kind>.manifest.json
```

* `<env>` = `staging` | `prod`; `<kind>` = `daily` | `pre-change` | `manual`; timestamps always UTC.
* `manifest.json` (plain text, **no secrets**): `git_sha`, `pg_dump` version, server version, UTC time, `kind`, the output of `pg_transfer.sh counts` (rows per table), the list of applied migration file names, dump byte size and SHA-256. This makes verification and reconciliation possible without decrypting anything.
* Note the current script writes `boss_bot_<ts>.dump`; adopting this convention is part of the later implementation, not a change to make now.

## 6. Encryption and secrets

Dumps contain contract IDs, claimant identities, error text, and — if the corresponding flags are on — episodic memory content and usage data. Treat them as **confidential**.

* **Encrypt before upload**, client-side, with [`age`](https://age-encryption.org) using a **public key** (`age -r <pubkey>`): the backup job holds only the public key and can never decrypt. The private key is kept offline by the owner (password manager + one offline copy) — **losing it makes every backup unreadable**, so restore drills (§8) must prove the key works.
* **Least-privilege database access:** a dedicated Neon role used only for dumps (`backup_ro`, read-only on the schema; e.g. membership in `pg_read_all_data`). Its URL is the only DB credential the backup job needs. Never use the app's owner role.
* **Least-privilege Drive access:** the repo's existing Drive artifact store already uses the narrow `drive.file` scope (`core/google_drive_artifact_store.py`) and a dedicated folder env var (`GOOGLE_DRIVE_ARTIFACT_FOLDER_ID`). Reuse that pattern with a **separate, private, owner-only folder** for backups — not the shared BOSS root (`GOOGLE_DRIVE_FOLDER_ID`). With `drive.file` the credential can only see files it created, which is desirable for the upload job and means the *restore* path must use the same OAuth client (or the owner downloads manually from Drive). Verify the exact scopes and ownership before implementing.
* **Where secrets live:** the read-only DB URL, the Drive credential and the age *public* key live only in the job's secret store (the future runner's secrets). Never in the repo, never in `.env.example`, never in logs; the repo tools already redact passwords in output.
* No decrypted dump is ever written to a shared or synced location; delete local plaintext immediately after use.

## 7. Verification, and reconciliation after a stale restore

Every produced dump: `pg_restore --list` succeeds (already in `pg_transfer.sh dump`), SHA-256 recorded, manifest written, **upload re-read and checksum-compared** before the local copy is deleted. Weekly: restore the newest dump into a scratch database, run `pg_transfer.sh verify`-style count comparison against the manifest, and discard.

If a restore is **older than the loss** (RPO window), the restored claims table can be *missing* claims created since. That is dangerous in one specific way: a missing claim for an already-executed contract removes the idempotency guard. Therefore, before approvals are re-enabled after any restore, reconcile against Airtable `ActionContracts`:

1. List contracts with status `executing`, `completed`, `failed`, `outcome_unknown`, `approved` whose timestamps fall after the dump's time (manifest).
2. For each with no claim row: insert a claim row reflecting the contract's recorded status (`completed` / `failed` / `outcome_unknown`; never `executing`-then-retry).
3. Anything `outcome_unknown` or `executing` is a **human decision** — never auto-retried (existing contract of `atomic_claim_repository.py`).

## 8. Emergency restore runbook

Fastest path first: **Neon PITR/branch restore** if the target moment is inside Neon's window. Otherwise, from Drive:

1. **Declare and contain.** Owner activates the emergency stop for claims-guarded writes (`EMERGENCY_STOP_*` via the durable Airtable-backed mechanism) so no new approvals execute while the DB is in question. Do not "fix forward" with the DB in an unknown state.
2. **Pick the dump.** Newest `daily`/`pre-change` whose manifest `git_sha`/migrations are compatible with the deployed code; confirm its `.sha256`.
3. **Fetch and decrypt** with the owner-held age private key; verify the checksum *before* decrypting and `pg_restore --list` *after*.
4. **Restore into a NEW database/branch first — never over the live one:** `TARGET_DATABASE_URL=<new> scripts/neon/pg_transfer.sh restore <dump> --yes`, then `SOURCE_DATABASE_URL=<manifest counts> … verify` against the manifest counts, then `python3 scripts/neon/neon_readiness_check.py --url-env TARGET_DATABASE_URL --concurrency-probe --require-no-inflight`.
5. **Reconcile with Airtable** (§7).
6. **Switch:** owner sets `DATABASE_URL` on the Render service to the restored database and does the manual deploy (this is the only step that touches production config — explicit owner action).
7. **Canary:** one low-risk approval end-to-end plus a duplicate-approve attempt (`already_claimed`); then lift the emergency stop.
8. Record what happened in `CHANGE_CONTROL_LOG.md`/`BUG_AUDIT_LOG.md` (append-only).

Estimated restore time is measured in M1 step 13 (dump size and restore wall-clock); record it here once known.

**Restore drills:** one **before M3** (a real Drive → decrypt → restore → verify into a scratch DB, proving the private key and the fetch path work), then quarterly. A backup that has never been restored is not a backup.

## 9. Where the automation could run (deferred decision — do not set up yet)

| Option | Notes |
|---|---|
| Scheduled GitHub Actions workflow | no VM, secrets in the repo's secret store, simple; has TCP egress to Neon; a new workflow file = code change needing explicit approval |
| Job inside the app's `scheduler.py` | no new infrastructure, but the app would back up its own DB through the same pool, ties backup health to app health, and needs `pg_dump` in the Render runtime (not guaranteed) |
| Small scheduled worker elsewhere | more to maintain; only if the above are unsuitable |

Recommendation when the time comes: a scheduled GitHub Actions job (independent of the app and of Render). **Not authorised now.**

## 10. Open items for the owner

1. Drive account/folder that will hold backups (private, owner-only) and who may read it.
2. Custody of the age private key (and the offline copy).
3. Confirm Neon's PITR window and quota on Neon's own pricing page.
4. Approve (later) the automation option in §9.
