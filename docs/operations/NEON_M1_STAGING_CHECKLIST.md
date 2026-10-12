# Neon M1 — Staging Execution Checklist

**Status: PLAN ONLY.** Nothing here has been run against a real Neon endpoint. M1 is **staging only** — no production cutover, no Render env change, no flag change, no PostgreSQL/Oracle decommission. Context: [`NEON_MIGRATION_M0.md`](NEON_MIGRATION_M0.md) (tooling, M0.5 `get_conn()` validation). Companion docs: [`NEON_BACKUP_PLAN_DRIVE.md`](NEON_BACKUP_PLAN_DRIVE.md), [`RENDER_STATE_VERIFICATION_CHECKLIST.md`](RENDER_STATE_VERIFICATION_CHECKLIST.md).

M1 output is **results only**: fill the report table at the bottom; do not change anything because of a result without a new owner decision.

## 0. Preconditions (resolve BEFORE the first step)

| # | Precondition | Why |
|---|---|---|
| P1 | **Neon project created with PostgreSQL 16** (Neon lets you pick the major version at creation) | `pg_dump` must be ≥ the server's major version. The repo's CI (`postgres:16`), `docker-compose.oracle.yml` (`postgres:16-alpine`) and the local tooling are all 16. A Neon 17 server would make every `pg_dump` fail with a version mismatch unless a 17 client is installed. |
| P2 | **Two URLs** from the Neon console, same role/database: `NEON_DIRECT` (host `ep-….neon.tech`) and `NEON_POOLED` (host `ep-…-pooler.neon.tech`), both ending `?sslmode=require` | Direct for dump/restore/DDL/idle/terminate tests; pooled is what the app should use. |
| P3 | **A staging-only database/role.** Ideally a Neon *branch* or separate database used for nothing else; password rotated after M1 | The URL is pasted into a session transcript; treat it as burned afterward. Never commit it. |
| P4 | **A machine that can reach Neon on TCP 5432.** *The cloud session used for M0 cannot:* outbound is HTTPS-only through a policy proxy, and a direct TCP probe to `neon.tech:5432` timed out (`:443` was open). libpq cannot use an HTTP proxy. | Without raw TCP no `psql`/`psycopg2` step can run. |
| P5 | `psql`, `pg_dump`, `pg_restore` (≥ server major), Python 3 + `pip install -r requirements.txt`, this repo at branch `ccr-8ce58b74-gz57gr` (contains M0 tooling + M0.5) | |
| P6 | A **source dump to restore** that is *not production data* (see step 4) | M1 must not copy production data to a third-party free tier; that is M3's decision. |
| P7 | Staging app service (if any) must **not** share the production Airtable base or Telegram bot — see the Render checklist | M1 itself never starts the app, but any later soak would. |

**Resolving P4 (pick one; owner decision):**
1. *Cloud session:* the environment's network policy can be edited (environment menu in the session title bar → Edit → Network access: broader level, or Custom with `*.neon.tech` allowed). After the change, re-test: `timeout 6 bash -c 'exec 3<>/dev/tcp/<ep-host>/5432' && echo OPEN`. It is **not verified** that a broader level permits raw TCP 5432 — the probe above is the proof. If it still times out, use option 2.
2. *Operator machine:* run the commands below on a laptop/VM that has TCP egress, and paste back the output (passwords are redacted by the tools).
3. *(Needs a new, explicit go — it is code/CI):* a `workflow_dispatch` GitHub Actions job with the staging URL as a repo secret. Not authorised now.

Environment for every step (never `echo` these):

```bash
export NEON_DIRECT='postgresql://<role>:<password>@ep-<id>.<region>.aws.neon.tech/<db>?sslmode=require'
export NEON_POOLED='postgresql://<role>:<password>@ep-<id>-pooler.<region>.aws.neon.tech/<db>?sslmode=require'
export SOURCE_DATABASE_URL='<non-production source for step 4>'
cd <repo> && git checkout ccr-8ce58b74-gz57gr
```

**Global rules:** staging only · every test row/table uses the prefix `m1-` / `neon_probe_` and is removed at the end · stop at the first **FAIL in steps 6, 7, 12 or 14** (they are the safety gates) and report; other FAILs are recorded and the run continues · record *what you saw*, not what you expected.

---

## The 14 checks

### 1. TLS / connectivity
```bash
psql "$NEON_DIRECT" -X -Atc "select version(), current_database(), current_user"
psql "$NEON_DIRECT" -X -Atc "select ssl, version, cipher from pg_stat_ssl where pid = pg_backend_pid()"
psql "${NEON_DIRECT%%\?*}?sslmode=disable" -X -Atc "select 1"            # must be REFUSED
psql "${NEON_DIRECT%%\?*}?sslmode=verify-full&sslrootcert=system" -X -Atc "select 1"   # optional hardening
psql "$NEON_POOLED" -X -Atc "select 1"
```
**Pass:** `ssl = t`, TLS ≥ 1.2; server major = 16; plaintext refused; direct and pooled both answer. Record whether `verify-full` works (if yes, recommend it for the production URL). **Record the server version** (if ≠ 16, stop: see P1).

### 2. Latency
```bash
for i in 1 2 3 4 5; do python3 scripts/neon/neon_readiness_check.py --url-env NEON_DIRECT; sleep 20; done
for i in 1 2 3 4 5; do python3 scripts/neon/neon_readiness_check.py --url-env NEON_POOLED; sleep 20; done
```
**Pass:** cold connect < 2.5 s (the tool's WARN line; app `connect_timeout` is 5 s), warm RTT median < ~150 ms. Record all ten cold/median numbers and the time of day. (A claim costs ≈ 3–4 round trips: liveness `SELECT 1`, `INSERT … RETURNING`, `COMMIT`.) Cold-after-suspend is measured in step 8.

### 3. Migrations on an empty DB
```bash
psql "$NEON_DIRECT" -X -Atc "select count(*) from information_schema.tables where table_schema='public'"   # expect 0
DATABASE_URL="$NEON_DIRECT" python3 -m core.database_migrations      # expect 001..006 + 3 more = 9 "Migration succeeded"
DATABASE_URL="$NEON_DIRECT" python3 -m core.database_migrations      # run again: idempotent, still all succeed
```
**Pass:** table count 0 before; 9 files succeed twice; exit 0. (Production's `preDeployCommand` runs exactly this module.)

### 4. Restore from a dump
The only dump produced so far is **synthetic** (3 test rows, local scratch PG, ephemeral to the M0 container). Regenerate one: start a scratch local PG 16, run the migrations against it, insert a few rows (include one `executing`, one `failed`, one `completed` claim), then:
```bash
SOURCE_DATABASE_URL="$LOCAL_SCRATCH_URL" scripts/neon/pg_transfer.sh dump        # prints the dump path
TARGET_DATABASE_URL="$NEON_DIRECT" scripts/neon/pg_transfer.sh restore <dump> --yes
```
**Pass:** restore exits 0 (it is `--single-transaction`: failure rolls back, never half-restores). **Do not use a production dump in M1.** *(If the owner wants a real staging dump instead, it must come from the staging DB, never production.)*

### 5. Full verify — schema and row counts
```bash
SOURCE_DATABASE_URL="$LOCAL_SCRATCH_URL" TARGET_DATABASE_URL="$NEON_DIRECT" scripts/neon/pg_transfer.sh verify
norm() { grep -v -E '^(--|SET |SELECT pg_catalog.set_config|$)' ; }
pg_dump "$LOCAL_SCRATCH_URL" --schema-only --no-owner --no-privileges | norm > /tmp/src.schema.sql
pg_dump "$NEON_DIRECT"       --schema-only --no-owner --no-privileges | norm > /tmp/neon.schema.sql
diff /tmp/src.schema.sql /tmp/neon.schema.sql && echo SCHEMA_IDENTICAL
```
**Pass:** `VERIFY OK` (identical counts, 9 tables) and an empty schema diff. Any diff: record verbatim (Neon-specific extensions/comments are plausible; table/constraint/column differences are not acceptable).

### 6. UNIQUE constraints on `action_execution_claims`  ⛔ gate
```bash
psql "$NEON_DIRECT" -X -c "select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid='public.action_execution_claims'::regclass order by 1"
python3 scripts/neon/neon_readiness_check.py --url-env NEON_DIRECT      # schema line
```
**Pass:** `PRIMARY KEY (contract_id)`, `UNIQUE (idempotency_key)`, `UNIQUE (execution_id)` present; readiness `schema` = PASS (incl. migration-006 columns).

### 7. Race test against real Neon  ⛔ gate
```bash
for n in 8 16; do for i in 1 2 3; do
  python3 scripts/neon/neon_readiness_check.py --url-env NEON_DIRECT --concurrency-probe --contenders $n | grep concurrency_probe
  python3 scripts/neon/neon_readiness_check.py --url-env NEON_POOLED --concurrency-probe --contenders $n | grep concurrency_probe
done; done
```
**Pass:** all 12 runs `PASS` with winners **exactly 1** in each of the 3 scenarios, on **both** endpoints (the pooler is the one that could plausibly break the semantics). Any run with 0 or ≥2 winners = **FAIL → stop**. A connection-limit error at 16 contenders on the direct endpoint is a *finding*, not a semantics failure — re-run at 8.

### 8. Idle > 5 minutes
Run in two terminals at the same time:
```bash
python3 scripts/neon/neon_readiness_check.py --url-env NEON_DIRECT --idle-seconds 330
python3 scripts/neon/neon_readiness_check.py --url-env NEON_POOLED --idle-seconds 330
```
**Record, don't judge:** PASS/FAIL per endpoint and the first-query latency after idle. A FAIL on the direct endpoint is *expected* (the server dropped the connection) and is the exact case M0.5 handles — that is what step 9 verifies. Immediately after, run step 2 once to capture a post-suspend **cold connect** time.

### 9. Stale-connection recovery with M0.5
Deterministic (no waiting) — uses the real repository and real `core.database.get_conn()`:
```bash
DATABASE_URL="$NEON_DIRECT" FEATURE_ATOMIC_CLAIMS=true python3 - <<'EOF'
import logging, os, time, psycopg2
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")   # shows "Discarding dead pooled …"
from core.atomic_claim_repository import claim_contract_execution as claim
def c(cid, key):
    t = time.perf_counter(); r = claim(cid, "m1-operator", key)
    return r.result, round(time.perf_counter() - t, 2)
print("1 warm            ", c("m1-stale-1", "m1-idem-stale-1"))
adm = psycopg2.connect(os.environ["DATABASE_URL"]); adm.autocommit = True
with adm.cursor() as cur:
    cur.execute("select count(*) from (select pg_terminate_backend(pid) from pg_stat_activity "
                "where datname = current_database() and usename = current_user and pid <> pg_backend_pid()) t")
    print("  terminated backends:", cur.fetchone()[0])
print("2 after server close", c("m1-stale-2", "m1-idem-stale-2"))   # expect ('acquired', …) + one WARNING line
print("3 duplicate of 2    ", c("m1-stale-2", "m1-idem-stale-2"))   # expect ('already_claimed', …)
EOF
```
Then the **natural** version: run the same first/last claim with `time.sleep(330)` in between, on `NEON_POOLED`. **Pass:** step 2 `acquired` (before M0.5 it was `error`), step 3 `already_claimed`, and the latency of step 2 recorded (= wake + reconnect). If `pg_terminate_backend` is denied on Neon, record that and rely on the natural 330 s version.

### 10. Network interruption / timeout
Cases (a) and (b)/(c) need no Neon cooperation:

**(a) Connect black-hole** — `connect_timeout=5`:
```bash
time DATABASE_URL='postgresql://u:p@10.255.255.1:5432/db?sslmode=require' FEATURE_ATOMIC_CLAIMS=true python3 - <<'EOF'
import logging; logging.disable(logging.CRITICAL)
from core.atomic_claim_repository import claim_contract_execution as claim
r = claim("m1-blackhole", "m1-operator", "m1-idem-blackhole"); print(r.result, r.error)
EOF
```
**Pass:** returns `unavailable`/`error` (never `acquired`) in ≈ 5 s, process does not hang.

**(b) Controllable link via a local TCP proxy** (operator scratch script — save as `tcpproxy.py` *outside* the repo; **not committed**). It was validated locally against plain PostgreSQL; it has **not** been tried through TLS to Neon:
```python
# python3 tcpproxy.py LISTEN_PORT TARGET_HOST TARGET_PORT   — control by typing on stdin:
#   forward | drop | arm | reset
#   drop  = forward client->server, DISCARD server->client (stalled link)
#   arm   = forward until a COMMIT is seen, then drop (lost-answer-after-commit) — PLAINTEXT ONLY
#   reset = abruptly close every open connection (cable pulled)
import asyncio, sys
LP, TH, TP = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
mode, conns = "forward", []
async def pipe(r, w, d):
    global mode
    try:
        while data := await r.read(65536):
            if d == "s2c" and mode == "drop":
                continue
            w.write(data); await w.drain()
            if d == "c2s" and mode == "arm" and b"COMMIT" in data:
                mode = "drop"; print("armed: COMMIT forwarded, answers now dropped", flush=True)
    except Exception:
        pass
    finally:
        w.close()
async def handle(cr, cw):
    sr, sw = await asyncio.open_connection(TH, TP)
    conns.append((cw, sw))
    await asyncio.gather(pipe(cr, sw, "c2s"), pipe(sr, cw, "s2c"))
async def cmds():
    global mode
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if line == "":
            await asyncio.sleep(3600); continue
        line = line.strip()
        if line == "reset":
            for cw, sw in conns: cw.close(); sw.close()
        elif line in ("forward", "drop", "arm"): mode = line
        print("mode:", mode, flush=True)
async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LP)
    await asyncio.gather(srv.serve_forever(), cmds())
asyncio.run(main())
```
Point the app's URL at the proxy while keeping the real hostname for TLS/SNI: `postgresql://<role>:<pw>@ep-<id>.<region>.aws.neon.tech/<db>?sslmode=require&hostaddr=127.0.0.1&port=15432`, with the proxy run as `python3 tcpproxy.py 15432 <ep-host> 5432`. Then, with a claim running in a thread:

* **stall** — type `drop`, start a claim, time how long it stays blocked, then type `reset`.
* **cable pull while idle** — warm claim, `reset`, next claim must be `acquired` (M0.5), duplicate `already_claimed`.

**Expected finding to measure, not to fix here:** `core/database.py` sets only `connect_timeout=5` — no `statement_timeout`/socket timeout/`tcp_user_timeout`. Locally a stalled link blocked a claim for > 25 s with no error, and only returned (`unavailable`) after the connection was reset. Record how long the real stall blocks. A stalled claim is *fail-closed* (nothing executes) but ties up one of the app's 4 gunicorn threads; if the measured block is minutes, propose a bounded-timeout change as a **separate** owner-approved step (M0.6) — do not apply it in M1.

**Lost-answer-after-commit** (caller sees an error although the server committed) was verified locally with `arm` on plaintext: the caller got `error` and **did not execute**; a row was left in `executing`; a retry returned `already_claimed`; so the action is not double-executed and the orphan is exactly what the step-11 gate catches. It cannot be reproduced through TLS (the proxy cannot see `COMMIT`); it is client-side behaviour, independent of Neon.

### 11. The `executing` gate
```bash
psql "$NEON_DIRECT" -X -c "insert into action_execution_claims(contract_id,claimant_id,execution_id,status,claimed_at,idempotency_key) values ('m1-gate','m1-operator','m1-exec-gate','executing',extract(epoch from now()),'m1-idem-gate')"
python3 scripts/neon/neon_readiness_check.py --url-env NEON_DIRECT --require-no-inflight; echo "exit=$?"     # expect FAIL, exit 1
psql "$NEON_DIRECT" -X -c "update action_execution_claims set status='failed' where contract_id='m1-gate'"
python3 scripts/neon/neon_readiness_check.py --url-env NEON_DIRECT --require-no-inflight; echo "exit=$?"     # no executing left → exit 0 (rows from the restore in step 4 included — resolve those too)
```
**Pass:** exit 1 while any `executing` row exists, exit 0 once none do. (If the step-4 dump contained an `executing` row it will trip this gate too — that is the point; resolve it on staging, then re-run.)

### 12. `already_claimed` and `idempotency_conflict`  ⛔ gate
```bash
DATABASE_URL="$NEON_DIRECT" FEATURE_ATOMIC_CLAIMS=true python3 - <<'EOF'
import logging; logging.disable(logging.CRITICAL)
from core.atomic_claim_repository import claim_contract_execution as claim
r = lambda cid, key: claim(cid, "m1-operator", key).result
print("first               ", r("m1-dup-A", "m1-idem-A"))   # acquired
print("same contract+key   ", r("m1-dup-A", "m1-idem-A"))   # already_claimed
print("same key, other ctr ", r("m1-dup-B", "m1-idem-A"))   # idempotency_conflict
print("same ctr, other key ", r("m1-dup-A", "m1-idem-X"))   # contract_identity_conflict
EOF
```
**Pass:** exactly `acquired`, `already_claimed`, `idempotency_conflict`, `contract_identity_conflict`. Repeat once through `NEON_POOLED`. Any other value = **FAIL → stop**.

### 13. dump → restore → verify against Neon
A restore must never target its own source (the script refuses), so restore Neon's dump to a **different** database:
```bash
SOURCE_DATABASE_URL="$NEON_DIRECT" scripts/neon/pg_transfer.sh dump                    # dump FROM Neon
# restore target: a scratch local PG 16 (proves the Neon dump is portable) ...
TARGET_DATABASE_URL="$LOCAL_SCRATCH2_URL" scripts/neon/pg_transfer.sh restore <dump> --yes
SOURCE_DATABASE_URL="$NEON_DIRECT" TARGET_DATABASE_URL="$LOCAL_SCRATCH2_URL" scripts/neon/pg_transfer.sh verify
# ... and, if the owner creates a second empty database/branch in the staging project, repeat into it
```
**Pass:** dump succeeds (no version mismatch), restore exits 0, `VERIFY OK`. Record dump size and dump/restore wall-clock time (feeds the emergency-restore time estimate).

### 14. Fail-closed when Neon is unavailable  ⛔ gate
Use a counting executor to prove **nothing executes** when the claim layer is down. Run once with an unreachable host (never up) and once with the proxy in `reset` after the pool is warm:
```bash
DATABASE_URL='postgresql://u:p@10.255.255.1:5432/db?sslmode=require' FEATURE_ATOMIC_CLAIMS=true python3 - <<'EOF'
import logging; logging.disable(logging.CRITICAL)
from core.action_gateway_atomic_executor import execute_with_atomic_claim
calls = []
ok, result, err = execute_with_atomic_claim(
    contract_id="m1-fc", canonical_user_id="m1-operator", tool_name="m1_noop", tool_inputs={},
    identity=None, executor_fn=lambda **kw: calls.append(kw) or {"ok": True},
    idempotency_key="m1-idem-fc")
print("ok=%s err=%r executor_called=%d" % (ok, err, len(calls)))   # expect ok=False, executor_called=0
EOF
```
**Pass:** `ok=False`, `executor_called=0`. Also confirm (read-only) that the TMA write path refuses with its 503 text when the pool is unavailable (`tma_api.py` `_claim_and_execute_approval` / `_queue_tma_write_approval`) — by reading the code path, not by running the app. If the owner can suspend the staging compute from the Neon console, repeat once against the suspended real endpoint and record wake time. **Any `executor_called > 0` = FAIL → stop.**

---

## Cleanup (end of M1)

```sql
DELETE FROM action_execution_claims WHERE contract_id LIKE 'm1-%' OR idempotency_key LIKE 'm1-%';
DROP TABLE IF EXISTS neon_probe_<any leftovers>;   -- the probe drops its own; check pg_tables
```
Then: owner **rotates the staging role password** (the URL appeared in a transcript), deletes the scratch dumps (`./pg_dumps/`), and stops local scratch databases. Do not leave `NEON_*` variables in shell history/profile.

## Results report (fill and return — results only)

| # | Check | Result (PASS / FAIL / FINDING) | Numbers / output |
|---|---|---|---|
| P1–P7 | Preconditions | | server version: ___ ; P4 route used: ___ |
| 1 | TLS/connectivity | | ssl/TLS ver: ___ ; plaintext refused: ___ ; verify-full: ___ |
| 2 | Latency | | direct cold ___/___ s, RTT med ___ ms ; pooled cold ___/___ s, RTT med ___ ms |
| 3 | Migrations (empty DB, ×2) | | |
| 4 | Restore | | dump source: ___ ; restore time ___ s |
| 5 | Verify counts + schema diff | | diff: ___ |
| 6 | UNIQUE constraints ⛔ | | |
| 7 | Race ×12 ⛔ | | direct ___ / pooled ___ ; limits hit: ___ |
| 8 | Idle 330 s | | direct ___ ; pooled ___ ; first query after idle ___ ms ; cold connect after suspend ___ s |
| 9 | Stale recovery (M0.5) | | forced close: ___ ; natural 330 s: ___ ; latency ___ s |
| 10 | Network interruption | | black-hole ___ s ; stall blocked ___ s ; cable pull recovery ___ |
| 11 | `executing` gate | | |
| 12 | already_claimed / idempotency_conflict ⛔ | | direct ___ ; pooled ___ |
| 13 | dump→restore→verify | | size ___ ; times ___ |
| 14 | Fail-closed ⛔ | | executor_called = ___ |

**Overall M1 verdict** = `PASS` only if steps 6, 7, 12 and 14 pass on real Neon and every other FAIL has an owner-accepted explanation. M1 PASS does **not** authorise M3; the production cutover remains a separate, explicit owner instruction. Until then: `STATUS: 🟡 CODE DONE, NOT VERIFIED IN PROD`.
