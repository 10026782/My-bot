#!/usr/bin/env python3
"""scripts/neon/neon_readiness_check.py — Neon migration M0 readiness probe.

Operator tool (never imported by the live pipeline). Answers one question
about a PostgreSQL endpoint — Neon, the current Render PG, or a local scratch
DB: "is it safe to point DATABASE_URL here for atomic execution claims?"

Default mode is READ-ONLY (SELECTs only). Two opt-in probes create and drop a
uniquely named scratch table (`neon_probe_<random>`) of their own; neither
ever touches `action_execution_claims` or any production table.

  python3 scripts/neon/neon_readiness_check.py                   # uses DATABASE_URL
  python3 scripts/neon/neon_readiness_check.py --url-env NEON_DATABASE_URL
  python3 scripts/neon/neon_readiness_check.py --concurrency-probe
  python3 scripts/neon/neon_readiness_check.py --idle-seconds 330   # > Neon free 5-min suspend
  python3 scripts/neon/neon_readiness_check.py --require-no-inflight  # cutover gate

Checks
  url_shape          sslmode on non-local hosts; pooled vs direct endpoint
  connect_latency    cold connect + warm round-trip vs core/database.py's 5s connect_timeout
  schema             action_execution_claims exists with PK(contract_id),
                     UNIQUE(idempotency_key), UNIQUE(execution_id) + migration-006 columns
  inflight           claims by status; `executing` rows are outcome-ambiguous and
                     must be 0 before a cutover (--require-no-inflight makes it FAIL)
  concurrency_probe  N threads race `INSERT ... ON CONFLICT DO NOTHING RETURNING`
                     (same SQL shape as core/atomic_claim_repository.py); exactly one
                     winner per scenario or FAIL
  idle_probe         connection kept idle N seconds, then reused — shows whether the
                     pool in core/database.py would hand out a dead connection after
                     Neon scale-to-zero

Exit code 0 = no FAIL (WARN allowed unless --strict); 1 = at least one FAIL.
The password is never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import uuid
from urllib.parse import parse_qs, urlsplit

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"

# core/database.py uses connect_timeout=5 — a cold Neon wake-up has to fit well inside it.
APP_CONNECT_TIMEOUT_S = 5
COLD_CONNECT_WARN_S = APP_CONNECT_TIMEOUT_S / 2

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}
_SSL_OK = {"require", "verify-ca", "verify-full"}

_REQUIRED_CONSTRAINTS = {
    "PRIMARY KEY (contract_id)": "primary key on contract_id",
    "UNIQUE (idempotency_key)": "unique on idempotency_key",
    "UNIQUE (execution_id)": "unique on execution_id",
}
_REQUIRED_COLUMNS = ("original_idempotency_key", "superseded_by_contract_id")


def result(name: str, status: str, detail: str, **extra) -> dict:
    return {"name": name, "status": status, "detail": detail, **extra}


def redact_url(url: str) -> str:
    """postgresql://user:***@host:port/db?query — never leaks the password."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    user = f"{parts.username}:***@" if parts.username else ""
    query = f"?{parts.query}" if parts.query else ""
    return f"{parts.scheme}://{user}{host}{port}{parts.path}{query}"


def analyze_url(url: str) -> dict:
    parts = urlsplit(url)
    host = parts.hostname or ""
    query = parse_qs(parts.query)
    sslmode = (query.get("sslmode") or [""])[0]
    return {
        "host": host,
        "local": host in _LOCAL_HOSTS,
        "pooler": "-pooler" in host,
        "sslmode": sslmode,
        "has_password": bool(parts.password),
    }


def check_url_shape(url: str) -> dict:
    info = analyze_url(url)
    if not url.startswith(("postgresql://", "postgres://")):
        return result("url_shape", FAIL, "URL must start with postgresql:// or postgres://")
    if not info["local"] and info["sslmode"] not in _SSL_OK:
        return result(
            "url_shape", FAIL,
            f"non-local host {info['host']!r} without sslmode=require (got {info['sslmode']!r}) — "
            "Neon refuses plaintext; never send claims over an unencrypted link",
        )
    kind = "pooled (pgbouncer, transaction mode)" if info["pooler"] else "direct"
    note = (
        "ok for the app pool; use a DIRECT endpoint for pg_dump/pg_restore and DDL migrations"
        if info["pooler"] else
        "ok for migrations/pg_dump; consider the -pooler endpoint for the app to save connection slots"
    )
    return result("url_shape", PASS, f"{kind} endpoint, sslmode={info['sslmode'] or 'n/a'} — {note}",
                  host=info["host"], pooler=info["pooler"])


def _connect(url: str, timeout: float = APP_CONNECT_TIMEOUT_S):
    import psycopg2  # noqa: PLC0415 — optional dependency of this operator tool

    return psycopg2.connect(url, connect_timeout=int(timeout))


def check_connect_latency(url: str, rounds: int = 10) -> tuple[dict, object | None]:
    t0 = time.perf_counter()
    try:
        conn = _connect(url)
    except Exception as exc:  # noqa: BLE001
        return result("connect_latency", FAIL, f"cannot connect within {APP_CONNECT_TIMEOUT_S}s: {type(exc).__name__}: {exc}"), None
    cold = time.perf_counter() - t0
    samples = []
    with conn.cursor() as cur:
        for _ in range(rounds):
            t = time.perf_counter()
            cur.execute("SELECT 1")
            cur.fetchone()
            samples.append((time.perf_counter() - t) * 1000)
        cur.execute("SHOW server_version")
        version = cur.fetchone()[0]
    conn.rollback()
    median_ms = statistics.median(samples)
    p_max_ms = max(samples)
    status = WARN if cold > COLD_CONNECT_WARN_S else PASS
    detail = (f"cold connect {cold:.2f}s (limit {APP_CONNECT_TIMEOUT_S}s), warm RTT median "
              f"{median_ms:.1f}ms max {p_max_ms:.1f}ms, server {version}")
    if status == WARN:
        detail += " — cold connect uses more than half the app's connect_timeout"
    return result("connect_latency", status, detail, cold_s=round(cold, 3),
                  warm_median_ms=round(median_ms, 1), server_version=version), conn


def check_schema(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.action_execution_claims')")
        if cur.fetchone()[0] is None:
            conn.rollback()
            return result("schema", FAIL, "table action_execution_claims is missing — run `python -m core.database_migrations` first")
        cur.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'public.action_execution_claims'::regclass AND contype IN ('p','u')"
        )
        defs = {row[0] for row in cur.fetchall()}
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='action_execution_claims'"
        )
        columns = {row[0] for row in cur.fetchall()}
    conn.rollback()
    missing = [label for definition, label in _REQUIRED_CONSTRAINTS.items() if definition not in defs]
    missing += [f"column {c}" for c in _REQUIRED_COLUMNS if c not in columns]
    if missing:
        return result("schema", FAIL, "action_execution_claims is not claim-safe, missing: " + ", ".join(missing))
    return result("schema", PASS, "action_execution_claims has PK(contract_id), UNIQUE(idempotency_key), UNIQUE(execution_id) and migration-006 columns")


def check_inflight(conn, require_none: bool) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.action_execution_claims')")
        if cur.fetchone()[0] is None:
            conn.rollback()
            return result("inflight", INFO, "no claims table here — nothing in flight")
        cur.execute("SELECT status, count(*) FROM action_execution_claims GROUP BY status ORDER BY status")
        counts = {status: n for status, n in cur.fetchall()}
    conn.rollback()
    executing = counts.get("executing", 0)
    unknown = counts.get("outcome_unknown", 0)
    summary = ", ".join(f"{k}={v}" for k, v in counts.items()) or "empty"
    if executing and require_none:
        return result("inflight", FAIL, f"{executing} claim(s) still `executing` ({summary}) — outcome unknown; resolve before cutover", counts=counts)
    if executing or unknown:
        return result("inflight", WARN, f"claims by status: {summary} — `executing`/`outcome_unknown` rows must be reviewed by a human before cutover", counts=counts)
    return result("inflight", PASS, f"claims by status: {summary}", counts=counts)


def _race(url: str, table: str, rows: list[tuple[str, str, str]]) -> int:
    """One thread per row, own connection, barrier-synchronised; returns winner count.

    Same SQL shape as core/atomic_claim_repository.py: untargeted ON CONFLICT DO NOTHING
    RETURNING, commit only when a row came back.
    """
    barrier = threading.Barrier(len(rows))
    winners: list[int] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker(contract_id: str, execution_id: str, idem: str) -> None:
        conn = None
        try:
            conn = _connect(url)
            barrier.wait(timeout=15)
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {table} (contract_id, execution_id, idempotency_key) "
                    "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING contract_id",
                    (contract_id, execution_id, idem),
                )
                won = cur.fetchone() is not None
            if won:
                conn.commit()
                with lock:
                    winners.append(1)
            else:
                conn.rollback()
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            if conn is not None:
                conn.close()

    threads = [threading.Thread(target=worker, args=row) for row in rows]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    if errors:
        raise RuntimeError("; ".join(sorted(set(errors))))
    return len(winners)


def check_concurrency_probe(url: str, n: int = 8) -> dict:
    table = f"neon_probe_{uuid.uuid4().hex[:10]}"
    setup = None
    try:
        setup = _connect(url)
        with setup.cursor() as cur:
            cur.execute(
                f"CREATE TABLE {table} (contract_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL UNIQUE, "
                "idempotency_key TEXT UNIQUE)"
            )
        setup.commit()
        # Scenario A: same contract, same key, n contenders.
        a = _race(url, table, [("probe-A", f"exec-A-{i}", "idem-A") for i in range(n)])
        # Scenario B: DIFFERENT contracts sharing one idempotency_key (the untargeted-conflict case).
        b = _race(url, table, [(f"probe-B-{i}", f"exec-B-{i}", "idem-B") for i in range(n)])
        # Scenario C: same contract, DIFFERENT keys (contract_identity_conflict case).
        c = _race(url, table, [("probe-C", f"exec-C-{i}", f"idem-C-{i}") for i in range(n)])
    except Exception as exc:  # noqa: BLE001
        return result("concurrency_probe", FAIL, f"probe could not complete: {type(exc).__name__}: {exc}")
    finally:
        try:
            if setup is not None:
                setup.rollback()
                with setup.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {table}")
                setup.commit()
                setup.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[probe] WARNING: could not drop scratch table {table}: {exc}", file=sys.stderr)
    detail = f"{n} contenders per scenario — winners: same-contract/same-key={a}, shared-key/different-contract={b}, same-contract/different-key={c} (each must be exactly 1)"
    if (a, b, c) == (1, 1, 1):
        return result("concurrency_probe", PASS, detail)
    return result("concurrency_probe", FAIL, detail + " — UNIQUE claims are NOT atomic on this endpoint; do not use it for execution claims")


def check_idle_probe(url: str, seconds: int) -> dict:
    try:
        conn = _connect(url)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()
    except Exception as exc:  # noqa: BLE001
        return result("idle_probe", FAIL, f"cannot open connection: {type(exc).__name__}: {exc}")
    print(f"[idle_probe] holding one pooled-style connection idle for {seconds}s ...", file=sys.stderr)
    time.sleep(seconds)
    t = time.perf_counter()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.rollback()
        took = (time.perf_counter() - t) * 1000
        return result("idle_probe", PASS, f"connection survived {seconds}s idle (first query after idle {took:.0f}ms)")
    except Exception as exc:  # noqa: BLE001
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        return result(
            "idle_probe", FAIL,
            f"connection DIED after {seconds}s idle ({type(exc).__name__}) — core/database.py's SimpleConnectionPool "
            "does not validate connections, so the first claim after an idle gap would fail closed. "
            "Add connection validation/keepalives (see docs/operations/NEON_MIGRATION_M0.md) before cutover",
        )


def run(args: argparse.Namespace) -> list[dict]:
    url = os.environ.get(args.url_env, "").strip()
    if not url:
        return [result("url_shape", FAIL, f"environment variable {args.url_env} is not set")]
    print(f"[neon_readiness_check] target: {redact_url(url)}", file=sys.stderr)
    results = [check_url_shape(url)]
    if results[0]["status"] == FAIL:
        return results
    try:
        import psycopg2  # noqa: F401, PLC0415
    except ImportError:
        return results + [result("connect_latency", FAIL, "psycopg2 is not installed (pip install -r requirements.txt)")]
    latency, conn = check_connect_latency(url)
    results.append(latency)
    if conn is None:
        return results
    try:
        results.append(check_schema(conn))
        results.append(check_inflight(conn, args.require_no_inflight))
    finally:
        conn.close()
    if args.concurrency_probe:
        results.append(check_concurrency_probe(url, args.contenders))
    if args.idle_seconds:
        results.append(check_idle_probe(url, args.idle_seconds))
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--url-env", default="DATABASE_URL", help="env var holding the PostgreSQL URL (default DATABASE_URL)")
    p.add_argument("--concurrency-probe", action="store_true", help="race N connections on a scratch table (creates/drops neon_probe_*)")
    p.add_argument("--contenders", type=int, default=8)
    p.add_argument("--idle-seconds", type=int, default=0, help="hold a connection idle N seconds then reuse it (use 330 for Neon free)")
    p.add_argument("--require-no-inflight", action="store_true", help="FAIL if any claim is still `executing` (cutover gate)")
    p.add_argument("--strict", action="store_true", help="treat WARN as failure")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    results = run(args)
    bad = {FAIL, WARN} if args.strict else {FAIL}
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    else:
        for r in results:
            print(f"{r['status']:<5} {r['name']:<18} {r['detail']}")
    return 1 if any(r["status"] in bad for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
