"""P23-M8B schema/data-contract evidence for usage_events."""

import os
from pathlib import Path

import pytest


ROOT = Path(__file__).parent
CREATE_SQL = (ROOT / "core/migrations/002_usage_events.sql").read_text()
UPGRADE_SQL = (ROOT / "core/migrations/005_usage_events_measurement_status.sql").read_text()


def test_canonical_create_represents_final_contract() -> None:
    assert "measurement_status TEXT NOT NULL DEFAULT 'measured'" in CREATE_SQL
    assert "quantity_out NUMERIC NOT NULL" not in CREATE_SQL
    assert "cost_usd NUMERIC NOT NULL" not in CREATE_SQL
    assert "usage_events_measurement_status_check" in CREATE_SQL
    assert "usage_events_measurement_values_check" in CREATE_SQL
    assert "measurement_status IN ('measured', 'unknown')" in CREATE_SQL


def test_upgrade_is_additive_and_idempotent_by_construction() -> None:
    assert "ADD COLUMN IF NOT EXISTS measurement_status TEXT NOT NULL DEFAULT 'measured'" in UPGRADE_SQL
    assert "ALTER COLUMN quantity_out DROP NOT NULL" in UPGRADE_SQL
    assert "ALTER COLUMN cost_usd DROP NOT NULL" in UPGRADE_SQL
    assert "pg_constraint" in UPGRADE_SQL
    assert "DO $$" in UPGRADE_SQL
    assert "DROP TABLE" not in UPGRADE_SQL.upper()
    assert "DELETE FROM" not in UPGRADE_SQL.upper()


def test_existing_contract_semantics_remain_unchanged() -> None:
    assert "quantity_in NUMERIC," in CREATE_SQL
    assert "cost_is_estimate BOOLEAN NOT NULL DEFAULT FALSE" in CREATE_SQL
    assert "UNIQUE(provider, request_id)" in CREATE_SQL
    assert "capability_id TEXT NOT NULL DEFAULT 'legacy.unknown'" in CREATE_SQL
    assert "execution_class TEXT NOT NULL DEFAULT 'UNKNOWN'" in CREATE_SQL


@pytest.mark.skipif(
    not os.environ.get("P23_M8B_DATABASE_URL"),
    reason="set P23_M8B_DATABASE_URL to run PostgreSQL migration contract checks",
)
def test_postgresql_contract_and_idempotency() -> None:
    psycopg2 = pytest.importorskip("psycopg2")
    schema = "p23_m8b_contract"
    with psycopg2.connect(os.environ["P23_M8B_DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {schema}")
            cur.execute(f"SET search_path TO {schema}, public")
            cur.execute(CREATE_SQL)
            cur.execute(UPGRADE_SQL)
            cur.execute(UPGRADE_SQL)

            cur.execute("SELECT column_name, is_nullable, column_default FROM information_schema.columns WHERE table_name='usage_events' AND column_name IN ('measurement_status', 'quantity_out', 'cost_usd') ORDER BY column_name")
            columns = {row[0]: row[1:] for row in cur.fetchall()}
            assert columns["measurement_status"][0] == "NO"
            assert "measured" in columns["measurement_status"][1]
            assert columns["quantity_out"][0] == "YES"
            assert columns["cost_usd"][0] == "YES"

            cur.execute("INSERT INTO usage_events (provider, service, model, source, unit, quantity_out, cost_usd) VALUES ('test', 'text', 'model', 'test', 'tokens', 0, 0)")
            cur.execute("INSERT INTO usage_events (provider, service, model, source, unit, measurement_status, quantity_out, cost_usd) VALUES ('test2', 'stt', 'model', 'test', 'seconds', 'unknown', NULL, NULL)")
            for values in (
                ("unknown", 0, 0),
                ("unknown", None, 0),
                ("measured", None, None),
                ("measured", 1, None),
                ("other", 1, 1),
            ):
                cur.execute("SAVEPOINT invalid_measurement")
                with pytest.raises(psycopg2.Error):
                    cur.execute("INSERT INTO usage_events (provider, service, model, source, unit, measurement_status, quantity_out, cost_usd) VALUES (%s, 'text', 'model', 'invalid', 'tokens', %s, %s, %s)", (f"invalid-{values[0]}", *values))
                cur.execute("ROLLBACK TO SAVEPOINT invalid_measurement")
            cur.execute(f"DROP SCHEMA {schema} CASCADE")
