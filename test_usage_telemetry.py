#!/usr/bin/env python3
"""
test_usage_telemetry.py — Regression tests for core/usage_telemetry.py
(Cost Telemetry Reliability PR, Part C).

Verifies against a fake in-process connection (no real PostgreSQL needed
for these assertions — mirrors how test_phase_4b0_1a_atomic_claims.py
tests core/atomic_claim_repository.py against core.database.get_conn):
  1. record_usage() is a no-op-but-safe (returns False, logs loudly, never
     raises) when PostgreSQL is unavailable — the exact failure mode that
     made AI_Usage_Daily read "אין שימוש" every day (a /tmp file that was
     never actually populated is indistinguishable, at read time, from
     "genuinely nothing happened" unless the read path is explicit about
     "unavailable" vs "zero").
  2. The request_id UNIQUE constraint is respected at the SQL level (ON
     CONFLICT DO NOTHING) — asserted here by checking the exact SQL this
     module sends, since a real dedup test needs a live Postgres (covered
     by the PR's staging runbook, not this offline script).
  3. get_usage_window()/get_daily_usage() report postgres_available=False
     (not zeroed-but-"available") when the pool is unavailable, so a
     caller (daily_watchdog) can tell "unknown" from "zero usage".
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from core.usage_telemetry import (
    record_usage, record_llm_usage, record_stt_usage,
    get_usage_window, get_daily_usage, get_trailing_hour_usage,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


print("\n── PostgreSQL unavailable => fail-soft, never raises ────────────────")

with patch("core.database.get_conn", return_value=None):
    ok = record_usage(
        provider="anthropic", service="text", model="claude-sonnet-4-6",
        source="test", unit="tokens", quantity_in=10, quantity_out=20,
    )
    chk("record_usage() returns False when PostgreSQL unavailable", ok is False)

    window = get_usage_window(__import__("datetime").datetime(2026, 1, 1),
                               __import__("datetime").datetime(2026, 1, 2))
    chk("get_usage_window() reports postgres_available=False", window["postgres_available"] is False)
    chk("get_usage_window() does NOT report zeroed-but-available (would look like real zero usage)",
        window == {"by_model": {}, "by_source": {}, "total_calls": 0,
                    "total_cost_usd": 0.0, "postgres_available": False})

    daily = get_daily_usage()
    chk("get_daily_usage() also reports postgres_available=False", daily["postgres_available"] is False)

    hourly = get_trailing_hour_usage()
    chk("get_trailing_hour_usage() also reports postgres_available=False", hourly["postgres_available"] is False)


print("\n── record_usage() writes with ON CONFLICT(request_id) DO NOTHING ────────────────")

fake_cursor = MagicMock()
fake_cursor.__enter__ = MagicMock(return_value=fake_cursor)
fake_cursor.__exit__ = MagicMock(return_value=False)
fake_conn = MagicMock()
fake_conn.cursor.return_value = fake_cursor

with patch("core.database.get_conn", return_value=fake_conn), \
     patch("core.database.release_conn"):
    ok = record_llm_usage(
        source="run_agent", model="claude-haiku-4-5-20251001",
        tokens_in=100, tokens_out=50, caller="test:123", request_id="msg_01ABC",
    )
    chk("record_llm_usage() returns True on a successful write", ok is True)

    sql_sent = fake_cursor.execute.call_args[0][0]
    params_sent = fake_cursor.execute.call_args[0][1]
    chk("INSERT targets usage_events", "INSERT INTO usage_events" in sql_sent)
    chk("dedup uses ON CONFLICT (request_id) DO NOTHING", "ON CONFLICT (request_id) DO NOTHING" in sql_sent)
    chk("request_id is passed through to the write", params_sent[10] == "msg_01ABC")
    chk("provider defaults to anthropic for record_llm_usage()", params_sent[0] == "anthropic")
    chk("service is 'text' for an LLM call", params_sent[1] == "text")


print("\n── record_stt_usage() uses service='stt', no input quantity ────────────────")

fake_cursor.reset_mock()
with patch("core.database.get_conn", return_value=fake_conn), \
     patch("core.database.release_conn"):
    ok = record_stt_usage(
        source="voice_stt_adapter", model="whisper-1", duration_seconds=12.5,
        caller="test", request_id="req-stt-1",
    )
    chk("record_stt_usage() returns True on a successful write", ok is True)
    params_sent = fake_cursor.execute.call_args[0][1]
    chk("provider defaults to openai for record_stt_usage()", params_sent[0] == "openai")
    chk("service is 'stt'", params_sent[1] == "stt")
    chk("unit is 'seconds'", params_sent[5] == "seconds")
    chk("quantity_in is None for STT (no input side)", params_sent[6] is None)
    chk("quantity_out carries duration_seconds", params_sent[7] == 12.5)


print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
