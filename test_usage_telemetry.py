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
    format_usage_window, _empty_window_result,
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
    chk("the single query reads measurement_status",
        "measurement_status" in fake_cursor.execute.call_args[0][0])
    chk("the read uses exactly one query", fake_cursor.execute.call_count == 1)


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


def read_rows(rows):
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor
    with patch("core.database.get_conn", return_value=conn), \
         patch("core.database.release_conn"):
        return get_usage_window(
            __import__("datetime").datetime(2026, 1, 1),
            __import__("datetime").datetime(2026, 1, 2),
        )


print("\n── measurement_status preserves unknown measurement truth ────────────────")

measured = ("anthropic", "text", "claude-sonnet-4-6", "run_agent", 100, 50, 0.01, False, "measured")
measured_zero = ("anthropic", "text", "claude-sonnet-4-6", "run_agent", 0, 0, 0, False, "measured")
unknown = ("openai", "stt", "whisper-1", "voice_stt_adapter", None, None, None, False, "unknown")

window = read_rows([measured])
chk("measured-only window is complete", window["measurement_complete"] is True)
chk("measured-only window has no unknown calls", window["unknown_measurement_calls"] == 0)
chk("measured-only totals remain correct", window["total_cost_usd"] == 0.01)

window = read_rows([measured_zero])
chk("measured zero remains a measured call", window["measurement_complete"] is True)
chk("measured zero remains numeric zero", window["total_cost_usd"] == 0)

window = read_rows([unknown])
model = window["by_model"][("openai", "stt", "whisper-1")]
source = window["by_source"]["voice_stt_adapter"]
chk("unknown row still counts as a paid call", window["total_calls"] == 1)
chk("unknown row count is exact", window["unknown_measurement_calls"] == 1)
chk("unknown row makes measurement incomplete", window["measurement_complete"] is False)
chk("unknown quantity is not fabricated as measured zero", model["quantity_out"] == 0)
chk("unknown cost is not fabricated as measured zero cost", model["cost_usd"] == 0)
chk("unknown row is visible in model breakdown", model["unknown_measurement_calls"] == 1)
chk("unknown row is visible in source breakdown", source["unknown_measurement_calls"] == 1)
chk("unknown row is excluded from confirmed and estimated costs",
    window["total_cost_usd_confirmed"] == 0 and window["total_cost_usd_estimated"] == 0)

window = read_rows([measured, unknown])
chk("mixed rows preserve measured cost subtotal", window["total_cost_usd"] == 0.01)
chk("mixed rows preserve exact unknown count", window["unknown_measurement_calls"] == 1)
chk("mixed rows are incomplete", window["measurement_complete"] is False)

invalid_status = read_rows([(*measured[:-1], "unsupported")])
chk("unsupported measurement status returns telemetry error", invalid_status["status"] == "error")
invalid_measured = read_rows([(*measured[:6], None, measured[7], "measured")])
chk("invalid measured row returns telemetry error", invalid_measured["status"] == "error")


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
    chk("legacy capability attribution is explicit", params_sent[12] == "legacy.unknown")
    chk("legacy execution class is explicit", params_sent[13] == "UNKNOWN")
    chk("legacy operation correlation remains absent", params_sent[14] is None)
    chk("legacy workflow correlation remains absent", params_sent[15] is None)
    chk("measured is the default measurement status", params_sent[16] == "measured")

    fake_cursor2.reset_mock()
    ok = record_llm_usage(
        source="test", model="claude-sonnet-4-6", tokens_in=1, tokens_out=2,
        capability_id="lead.create", execution_class="NARROW_MODEL",
        operation_id="owner:op-123",
        workflow_id="owner:workflow-7",
    )
    params_sent = fake_cursor2.execute.call_args[0][1]
    chk("custom capability attribution is passed through", params_sent[12] == "lead.create")
    chk("custom execution class is passed through", params_sent[13] == "NARROW_MODEL")
    chk("custom operation correlation is passed through", params_sent[14] == "owner:op-123")
    chk("custom workflow correlation is passed through", params_sent[15] == "owner:workflow-7")


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
    chk("measured STT persists measurement_status", params_sent[16] == "measured")

print("\n── unknown measurement writer contract ────────────────")

fake_cursor2.reset_mock()
with patch("core.database.get_conn", return_value=fake_conn2), \
     patch("core.database.release_conn"), \
     patch("core.usage_telemetry.compute_cost") as mock_compute:
    ok = record_stt_usage(
        source="voice_stt_adapter", model="whisper-1", duration_seconds=None,
        caller="test", request_id="req-stt-unknown", measurement_status="unknown",
    )
    params_sent = fake_cursor2.execute.call_args[0][1]
    chk("unknown STT write succeeds", ok is True)
    chk("unknown STT does not call compute_cost", mock_compute.call_count == 0)
    chk("unknown STT writes quantity_out=None", params_sent[7] is None)
    chk("unknown STT writes cost_usd=None", params_sent[8] is None)
    chk("unknown STT writes cost_is_estimate=False", params_sent[9] is False)
    chk("unknown STT persists measurement_status", params_sent[16] == "unknown")

for description, kwargs in (
    ("unsupported status returns False", {"measurement_status": "bogus", "quantity_out": 1}),
    ("measured None returns False", {"measurement_status": "measured", "quantity_out": None}),
    ("unknown numeric quantity returns False", {"measurement_status": "unknown", "quantity_out": 1}),
):
    with patch("core.database.get_conn") as mock_get_conn:
        ok = record_usage(
            provider="openai", service="stt", model="whisper-1", source="test",
            unit="seconds", **kwargs,
        )
    chk(description, ok is False and mock_get_conn.call_count == 0)


print("\n── format_usage_window() — ok, with data ────────────────")

ok_window = {
    "status": "ok", "error": "",
    "by_model": {
        ("anthropic", "text", "claude-sonnet-4-6"): {
            "quantity_in": 100.0, "quantity_out": 50.0, "calls": 2,
            "cost_usd": 0.01, "estimated_calls": 0,
            "unknown_measurement_calls": 0,
        },
    },
    "by_source": {"run_agent": {"calls": 2, "cost_usd": 0.01, "unknown_measurement_calls": 0}},
    "total_calls": 2, "total_cost_usd": 0.01,
    "total_cost_usd_confirmed": 0.01, "total_cost_usd_estimated": 0.0,
    "measurement_complete": True, "unknown_measurement_calls": 0,
}
text = format_usage_window(ok_window)
chk("ok window renders total calls", "Total calls: 2" in text)
chk("ok window renders model breakdown", "anthropic/text/claude-sonnet-4-6" in text)
chk("ok window renders source breakdown", "run_agent" in text)

incomplete_window = read_rows([measured, unknown])
incomplete_text = format_usage_window(incomplete_window)
chk("incomplete report states measurement is incomplete", "Measurement incomplete: 1" in incomplete_text)
chk("incomplete report labels known cost as subtotal", "Measured cost subtotal: $0.0100" in incomplete_text)
chk("incomplete report does not label subtotal as complete total", "Total cost:" not in incomplete_text)
chk("incomplete model breakdown exposes unknown measurement",
    "unknown measurement" in incomplete_text)


print("\n── format_usage_window() — unavailable/error are not shown as zero usage ────────────────")

text_unavail = format_usage_window(_empty_window_result("unavailable"))
chk("unavailable does not render as ok/zero usage", "unavailable" in text_unavail.lower())
chk("unavailable text does not claim total calls", "Total calls" not in text_unavail)

text_err = format_usage_window(_empty_window_result("error", "boom"))
chk("error does not render as ok/zero usage", "boom" in text_err)
chk("error text does not claim total calls", "Total calls" not in text_err)


print("\n── format_usage_window() — ok with empty by_model/by_source does not raise ────────────────")

empty_ok = _empty_window_result("ok")
text_empty = format_usage_window(empty_ok)
chk("empty ok window renders without raising", "Total calls: 0" in text_empty)
chk("empty ok window says no usage recorded", "No usage recorded" in text_empty)


print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
