"""Repeatable TC8 staging verification.

This script is intentionally staging-only.  It applies only migration 002,
uses the existing PostgreSQL connection mechanism, and never prints secrets.
It does not mutate ActionContracts or change runtime authority.

TC10 note (2026-08-10): this script used to also run the full Turn
Coordinator / ActionGateway regression matrix as subprocesses here, against
whatever environment the caller's shell had exported. Because those
subprocesses inherited the ambient environment verbatim and the individual
test files only set fake Airtable credentials via ``os.environ.setdefault``
(a no-op once real staging credentials are already exported — exactly the
case when someone is mid staging-verification), a small set of fixed
identity strings baked into those test files collided with leftover
ActionContracts from a previous run against the same shared staging
Airtable base (see BUG-122 proposal_boundary_blocked in
docs/architecture/turn-coordinator-full/TC8_DURABLE_TURN_STATE.md's TC10
handoff section). That is not a valid deterministic regression environment,
so the full matrix no longer runs from this script at all — it runs
isolated, with credentials forced (not defaulted) to fake values regardless
of ambient environment, via ``scripts/run_isolated_regression.py``. This
script now covers only what is actually safe to exercise against a real,
dedicated, non-production PostgreSQL staging database: migration/schema
verification and the real repository/concurrency checks below.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "core" / "migrations" / "002_durable_turn_state.sql"
EXPECTED_COMMIT = os.getenv("TC8_EXPECTED_SHA", "").strip()

# When invoked as ``python scripts/verify_tc8_staging.py``, Python puts the
# scripts directory—not the repository root—on sys.path.  The verification
# imports the repository's real core package, so make that path explicit.
sys.path.insert(0, str(ROOT))


class VerificationFailure(RuntimeError):
    pass


def _check(label: str, fn, evidence: dict) -> None:
    try:
        detail = fn()
        evidence[label] = {"status": "PASS", "detail": detail}
        print(f"{label:<28} PASS{(' — ' + detail) if detail else ''}")
    except Exception as exc:
        evidence[label] = {
            "status": "FAIL",
            "detail": f"{type(exc).__name__}: {exc}",
        }
        print(f"{label:<28} FAIL — {type(exc).__name__}: {exc}")


def _deploy_sha() -> str:
    render_sha = os.getenv("RENDER_GIT_COMMIT", "").strip()
    if render_sha:
        return render_sha
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
    except Exception as exc:
        raise VerificationFailure("deployment SHA is unavailable") from exc


def _db_target():
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise VerificationFailure("DATABASE_URL is not configured")
    parsed = urlparse(raw)
    database = (parsed.path or "").lstrip("/")
    host = parsed.hostname or ""
    if not database or not host:
        raise VerificationFailure("DATABASE_URL has no database/host")
    return raw, host, database


def _connect():
    try:
        import psycopg2
    except Exception as exc:
        raise VerificationFailure("psycopg2 is unavailable") from exc
    raw, _, _ = _db_target()
    try:
        return psycopg2.connect(raw, connect_timeout=8)
    except Exception as exc:
        raise VerificationFailure("PostgreSQL connection failed") from exc


def _preflight(evidence: dict) -> None:
    sha = _deploy_sha()
    if EXPECTED_COMMIT and not (
        sha == EXPECTED_COMMIT or sha.startswith(EXPECTED_COMMIT)
    ):
        raise VerificationFailure(
            f"deploy SHA mismatch: expected {EXPECTED_COMMIT}, got {sha}"
        )
    evidence["Deploy SHA"] = {"status": "PASS", "detail": sha}
    print(f"{'Deploy SHA':<28} PASS — {sha}")

    raw, host, database = _db_target()
    del raw
    database_lower = database.lower()
    if not (
        any(token in database_lower for token in ("staging", "sandbox", "test", "dev"))
        or os.getenv("TC8_NON_PRODUCTION", "").lower() == "true"
    ):
        raise VerificationFailure(
            "database target is not identifiable as non-production"
        )
    evidence["Non-production"] = {
        "status": "PASS", "detail": f"host={host} database={database}",
    }
    print(f"{'Non-production':<28} PASS — host={host} database={database}")

    try:
        import psycopg2
        version = psycopg2.__version__
    except Exception as exc:
        raise VerificationFailure("psycopg2 import failed") from exc
    evidence["psycopg2"] = {"status": "PASS", "detail": version}
    print(f"{'psycopg2':<28} PASS — {version}")

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            current_database, current_user = cur.fetchone()
        evidence["PostgreSQL connection"] = {
            "status": "PASS", "detail": f"database={current_database} user={current_user}",
        }
        print(f"{'PostgreSQL connection':<28} PASS — database={current_database}")
    finally:
        conn.close()


def _apply_migration() -> str:
    if MIGRATION.name != "002_durable_turn_state.sql":
        raise VerificationFailure("migration path is not 002_durable_turn_state.sql")
    sql = MIGRATION.read_text(encoding="utf-8")
    if "CREATE TABLE IF NOT EXISTS durable_turn_state" not in sql:
        raise VerificationFailure("migration 002 content is unexpected")
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        return "migration 002 applied"
    finally:
        conn.close()


def _schema_check() -> str:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM information_schema.tables
                   WHERE table_name = 'durable_turn_state'"""
            )
            if cur.fetchone() is None:
                raise VerificationFailure("durable_turn_state table is missing")
            cur.execute(
                """SELECT indexname FROM pg_indexes
                   WHERE tablename = 'durable_turn_state'"""
            )
            indexes = {row[0] for row in cur.fetchall()}
            if "idx_durable_turn_state_contract" not in indexes:
                raise VerificationFailure("contract index is missing")
            cur.execute(
                """SELECT pg_get_constraintdef(oid)
                   FROM pg_constraint
                   WHERE conrelid = 'durable_turn_state'::regclass"""
            )
            constraints = " ".join(row[0] for row in cur.fetchall()).lower()
            for required in (
                "primary key (tenant_id, canonical_user_id)",
                "state <> 'claimed'",
                "version >= 1",
            ):
                if required not in constraints:
                    raise VerificationFailure(f"missing constraint: {required}")
        return "table, primary key, state/claim/version constraints, index"
    finally:
        conn.close()


def _real_repository_tests() -> dict[str, str]:
    from core.turn_state_repository import (
        TurnStateConflictError,
        TurnStateRepository,
    )

    prefix = f"tc8-verify-{uuid.uuid4().hex}"
    repo1 = TurnStateRepository()
    repo2 = TurnStateRepository()
    identities = []

    def begin(tenant: str, user: str, contract: str):
        identities.append((tenant, user))
        return repo1.begin_or_get(tenant, user, f"turn-{uuid.uuid4().hex}", contract)

    try:
        state = begin(prefix, "user-persistence", "contract-persistence")
        if repo2.read(prefix, "user-persistence") != state:
            raise VerificationFailure("reconstruction mismatch")

        race_state = begin(prefix, "user-race", "contract-race")
        barrier = threading.Barrier(2)
        results = []

        def claim(repo):
            try:
                barrier.wait(timeout=10)
                results.append(repo.claim(
                    prefix, "user-race", expected_version=race_state.version,
                    operation_id=f"op-{uuid.uuid4().hex}", owner_kind="callback",
                ))
            except TurnStateConflictError:
                results.append("conflict")

        threads = [threading.Thread(target=claim, args=(repo1,)), threading.Thread(target=claim, args=(repo2,))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        if sum(item != "conflict" for item in results) != 1 or results.count("conflict") != 1:
            raise VerificationFailure(f"unexpected CAS race results: {results}")

        tenant_state = begin(prefix, "user-isolation", "contract-tenant-a")
        other_tenant = begin(prefix + "-other", "user-isolation", "contract-tenant-b")
        if tenant_state.active_contract_id == other_tenant.active_contract_id:
            raise VerificationFailure("tenant isolation collapsed")

        replay = begin(prefix, "user-replay", "contract-replay")
        claimed = repo1.claim(
            prefix, "user-replay", expected_version=replay.version,
            operation_id="replay-owner", owner_kind="text",
        )
        repo1.finalize(
            prefix, "user-replay", expected_version=claimed.state.version,
            operation_id="replay-owner", terminal_reason="completed",
        )
        try:
            repo2.claim(
                prefix, "user-replay", expected_version=replay.version,
                operation_id="stale-owner", owner_kind="callback",
            )
        except TurnStateConflictError:
            pass
        else:
            raise VerificationFailure("stale claim was accepted")

        release = begin(prefix, "user-release", "contract-release")
        released = repo1.claim(
            prefix, "user-release", expected_version=release.version,
            operation_id="release-owner", owner_kind="callback",
        )
        repo1.release(
            prefix, "user-release", expected_version=released.state.version,
            operation_id="release-owner", terminal_reason="test-release",
        )
        if repo2.read(prefix, "user-release").state != "released":
            raise VerificationFailure("release state was not persisted")

        return {
            "Persistence": "PASS",
            "CAS race": "PASS",
            "2-instance claim": "PASS",
            "Tenant isolation": "PASS",
            "Replay/stale": "PASS",
            "Terminal/release": "PASS",
        }
    finally:
        conn = _connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    for tenant, user in identities:
                        cur.execute(
                            "DELETE FROM durable_turn_state WHERE tenant_id = %s AND canonical_user_id = %s",
                            (tenant, user),
                        )
        finally:
            conn.close()


def _authority_check() -> str:
    migration = MIGRATION.read_text(encoding="utf-8")
    repository = (ROOT / "core" / "turn_state_repository.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    required = (
        "ActionContract remains lifecycle authority" in migration,
        "def _tc8_claim_contract" in app,
        "def _tc8_finish_contract" in app,
        "approve_with_lifecycle_result" in app,
        "reject_with_lifecycle_result" in app,
        "from core.action_contract" not in repository,
    )
    if not all(required):
        raise VerificationFailure("TC8 authority invariant check failed")
    return "ActionContract lifecycle authority unchanged"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-path", type=Path)
    args = parser.parse_args()
    evidence: dict = {}
    failed = False
    print("TC8 STAGING VERIFICATION\n")
    try:
        _preflight(evidence)
        for label, fn in (
            ("Migration 002", _apply_migration),
            ("Schema constraints", _schema_check),
            ("Migration idempotency", _apply_migration),
        ):
            _check(label, fn, evidence)
        if any(item["status"] == "FAIL" for item in evidence.values() if isinstance(item, dict)):
            failed = True
        if not failed:
            for label, detail in _real_repository_tests().items():
                evidence[label] = {"status": "PASS", "detail": "real PostgreSQL"}
                print(f"{label:<28} PASS — {detail}")
            _check("Authority invariants", _authority_check, evidence)
    except Exception as exc:
        failed = True
        evidence["fatal"] = {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}
        print(f"\nFATAL                       FAIL — {type(exc).__name__}: {exc}")

    if args.evidence_path:
        args.evidence_path.write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        print(f"Evidence written to {args.evidence_path}")

    print(
        "\nNote: the full Turn Coordinator / ActionGateway regression matrix "
        "(callback hardening, PR-0C callbacks, BUG-158 recovery, and the "
        "broader FULL_REGRESSION set) intentionally does not run from this "
        "script. Run it isolated instead: "
        "python scripts/run_isolated_regression.py — see "
        "scripts/regression_matrix.py and this script's module docstring "
        "for why (BUG-122 staging contamination, TC10 handoff)."
    )
    print("\nFINAL:")
    print("TC8: FAIL" if failed else "TC8: DONE")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
