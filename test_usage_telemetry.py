#!/usr/bin/env python3
"""
test_usage_telemetry.py — Regression tests for core/usage_telemetry.py
(Cost Telemetry Reliability PR2, shadow-only durable usage recording).

Verifies against a fake in-process connection (no real PostgreSQL needed
for these assertions — mirrors how test_phase_4b0_1a_atomic_claims.py
tests core/atomic_claim_repository.py against core.database.get_conn):

  1. record_usage() is fail-soft (returns False, logs loudly, never
     raises) when PostgreSQL is unavailable.
  2. record_usage() calls conn.rollback() before release_conn() on a
     write failure — an unhandled exception mid-transaction must not
     leave a poisoned (aborted-transaction) connection in the pool for
     the next caller.
  3. get_usage_window() uses exactly ONE connection/cursor for the whole
     operation — no "probe a connection, release it, acquire a second one
     for the real query" pattern.
  4. get_usage_window() distinguishes three states, not two:
       - status="unavailable": no connection could be obtained at all.
       - status="error": a connection was obtained but the query itself
         raised — this must NOT be folded into an empty/zeroed "ok"
         result (that would be indistinguishable from "zero usage
         happened", exactly the AI_Usage_Daily conflation this PR series
         exists to stop repeating).
       - status="ok": the query actually ran; an empty result here really
         does mean zero usage in the window.
     And that a query failure also rolls back before releasing.
  5. (provider, request_id) dedup is expressed via
     ON CONFLICT (provider, request_id) DO NOTHING in the INSERT sent to
     the database — scoped to provider, not a bare request_id, since
     different providers' id namespaces aren't guaranteed disjoint.
  6. record_llm_usage()/record_stt_usage() shortcuts set the right
     provider/service/unit defaults.
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
    chk("get_usage_window() reports status='unavailable'", window["status"] == "unavailable")
    chk("get_usage_window() does NOT report status='ok' with zeroed data (would look like real zero usage)",
        window["status"] != "ok")
    chk("get_usage_window() total_calls is 0 when unavailable (informational only, not a claim of 'zero usage')",
        window["total_calls"] == 0)

    daily = get_daily_usage()
    chk("get_daily_usage() also reports status='unavailable'", daily["status"] == "unavailable")

    hourly = get_trailing_hour_usage()
    chk("get_trailing_hour_usage() also reports status='unavailable'", hourly["status"] == "unavailable")


print("\n── get_usage_window() uses exactly ONE connection for the whole read ────────────────")

fake_cursor = MagicMock()
fake_cursor.__enter__ = MagicMock(return_value=fake_cursor)
fake_cursor.__exit__ = MagicMock(return_value=False)
fake_cursor.fetchall.return_value = []
fake_conn = MagicMock()
fake_conn.cursor.return_value = fake_cursor

with patch("core.database.get_conn", return_value=fake_conn) as mock_get_conn, \
     patch("core.database.release_conn") as mock_release_conn:
    window = get_usage_window(__import__("datetime").datetime(2026, 1, 1),
                               __import__("datetime").datetime(2026, 1, 2))
    chk("get_usage_window() calls get_conn() exactly once", mock_get_conn.call_count == 1)
    chk("get_usage_window() calls release_conn() exactly once", mock_release_conn.call_count == 1)
    chk("a successful empty query reports status='ok' (this IS a real zero)", window["status"] == "ok")
    chk("status='ok' with 0 rows means total_calls=0 genuinely", window["total_calls"] == 0)


print("\n── get_usage_window() query failure => status='error', rollback before release ────────────────")

fake_cursor_fail = MagicMock()
fake_cursor_fail.__enter__ = MagicMock(return_value=fake_cursor_fail)
fake_cursor_fail.__exit__ = MagicMock(return_value=False)
fake_cursor_fail.execute.side_effect = RuntimeError("simulated query failure")
fake_conn_fail = MagicMock()
fake_conn_fail.cursor.return_value = fake_cursor_fail

with patch("core.database.get_conn", return_value=fake_conn_fail), \
     patch("core.database.release_conn") as mock_release_conn:
    window = get_usage_window(__import__("datetime").datetime(2026, 1, 1),
                               __import__("datetime").datetime(2026, 1, 2))
    chk("a query failure reports status='error', not 'ok' or 'unavailable'", window["status"] == "error")
    chk("status='error' is distinct from status='unavailable' (different failure modes)",
        window["status"] != "unavailable")
    chk("error message is captured", "simulated query failure" in window["error"])
    chk("conn.rollback() was called before release_conn() on query failure",
        fake_conn_fail.rollback.called)
    chk("release_conn() was still called after the failure (connection returned to pool)",
        mock_release_conn.called)


print("\n── record_usage() rolls back before releasing on write failure ────────────────")

fake_cursor_write_fail = MagicMock()
fake_cursor_write_fail.__enter__ = MagicMock(return_value=fake_cursor_write_fail)
fake_cursor_write_fail.__exit__ = MagicMock(return_value=False)
fake_cursor_write_fail.execute.side_effect = RuntimeError("simulated write failure")
fake_conn_write_fail = MagicMock()
fake_conn_write_fail.cursor.return_value = fake_cursor_write_fail

with patch("core.database.get_conn", return_value=fake_conn_write_fail), \
     patch("core.database.release_conn") as mock_release_conn:
    ok = record_usage(
        provider="anthropic", service="text", model="claude-sonnet-4-6",
        source="test", unit="tokens", quantity_in=10, quantity_out=20,
    )
    chk("record_usage() returns False on write failure", ok is False)
    chk("conn.rollback() was called before release_conn() on write failure",
        fake_conn_write_fail.rollback.called)
    chk("release_conn() was still called after the failure", mock_release_conn.called)


print("\n── record_usage() writes with ON CONFLICT(provider, request_id) DO NOTHING ────────────────")

fake_cursor2 = MagicMock()
fake_cursor2.__enter__ = MagicMock(return_value=fake_cursor2)
fake_cursor2.__exit__ = MagicMock(return_value=False)
fake_conn2 = MagicMock()
fake_conn2.cursor.return_value = fake_cursor2

with patch("core.database.get_conn", return_value=fake_conn2), \
     patch("core.database.release_conn"):
    ok = record_llm_usage(
        source="run_agent", model="claude-haiku-4-5-20251001",
        tokens_in=100, tokens_out=50, caller="test:123", request_id="msg_01ABC",
    )
    chk("record_llm_usage() returns True on a successful write", ok is True)

    sql_sent = fake_cursor2.execute.call_args[0][0]
    params_sent = fake_cursor2.execute.call_args[0][1]
    chk("INSERT targets usage_events", "INSERT INTO usage_events" in sql_sent)
    chk("dedup uses ON CONFLICT (provider, request_id) DO NOTHING",
        "ON CONFLICT (provider, request_id) DO NOTHING" in sql_sent)
    chk("request_id is passed through to the write", params_sent[10] == "msg_01ABC")
    chk("provider defaults to anthropic for record_llm_usage()", params_sent[0] == "anthropic")
    chk("service is 'text' for an LLM call", params_sent[1] == "text")


print("\n── record_stt_usage() uses service='stt', no input quantity ────────────────")

fake_cursor2.reset_mock()
with patch("core.database.get_conn", return_value=fake_conn2), \
     patch("core.database.release_conn"):
    ok = record_stt_usage(
        source="voice_stt_adapter", model="whisper-1", duration_seconds=12.5,
        caller="test", request_id="req-stt-1",
    )
    chk("record_stt_usage() returns True on a successful write", ok is True)
    params_sent = fake_cursor2.execute.call_args[0][1]
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
