"""Neon migration M0 — DB-free checks for scripts/neon/neon_readiness_check.py.

Standalone assert-based script (repo convention: `python3 test_neon_readiness_check.py`).
No database, no network. The race/atomicity behaviour itself is exercised by running the
probe against a real endpoint (see docs/operations/NEON_MIGRATION_M0.md).
"""

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "neon_readiness_check", os.path.join(_HERE, "scripts", "neon", "neon_readiness_check.py")
)
m = importlib.util.module_from_spec(_spec)
sys.modules["neon_readiness_check"] = m
_spec.loader.exec_module(m)

NEON_DIRECT = "postgresql://u:s3cret@ep-quiet-sun-123.us-east-1.aws.neon.tech/boss_bot?sslmode=require"
NEON_POOLED = "postgresql://u:s3cret@ep-quiet-sun-123-pooler.us-east-1.aws.neon.tech/boss_bot?sslmode=require"

# --- redaction: the password must never appear in any output ---------------------------------
red = m.redact_url(NEON_DIRECT)
assert "s3cret" not in red, red
assert "u:***@" in red and "sslmode=require" in red, red
assert m.redact_url("postgresql://localhost/db") == "postgresql://localhost/db"

# --- url analysis ----------------------------------------------------------------------------
assert m.analyze_url(NEON_POOLED)["pooler"] is True
assert m.analyze_url(NEON_DIRECT)["pooler"] is False
assert m.analyze_url("postgresql://u@localhost:5432/db")["local"] is True
assert m.analyze_url(NEON_DIRECT)["sslmode"] == "require"

# --- url shape: fail closed on plaintext to a remote host ------------------------------------
assert m.check_url_shape(NEON_DIRECT)["status"] == m.PASS
r = m.check_url_shape(NEON_POOLED)
assert r["status"] == m.PASS and r["pooler"] is True and "pooled" in r["detail"], r
assert m.check_url_shape("postgresql://u:p@ep-x.neon.tech/db")["status"] == m.FAIL
assert m.check_url_shape("postgresql://u:p@ep-x.neon.tech/db?sslmode=disable")["status"] == m.FAIL
assert m.check_url_shape("postgresql://u:p@ep-x.neon.tech/db?sslmode=prefer")["status"] == m.FAIL
assert m.check_url_shape("postgresql://u@localhost/db")["status"] == m.PASS
assert m.check_url_shape("mysql://u@host/db")["status"] == m.FAIL

# --- a missing env var is a FAIL result, never an exception ----------------------------------
os.environ.pop("NEON_TEST_UNSET_URL", None)
out = m.main(["--url-env", "NEON_TEST_UNSET_URL"])
assert out == 1, out

# --- the schema gate demands exactly the constraints the claim SQL relies on -----------------
assert set(m._REQUIRED_CONSTRAINTS) == {
    "PRIMARY KEY (contract_id)", "UNIQUE (idempotency_key)", "UNIQUE (execution_id)"
}
assert "superseded_by_contract_id" in m._REQUIRED_COLUMNS

# --- migrations on disk still define those constraints (guards drift between probe and DDL) ---
sql = open(os.path.join(_HERE, "core", "migrations", "001_action_execution_claims.sql"), encoding="utf-8").read()
assert "contract_id TEXT PRIMARY KEY" in sql
assert "execution_id TEXT NOT NULL UNIQUE" in sql
assert "idempotency_key TEXT UNIQUE" in sql

print("test_neon_readiness_check: all checks passed")
