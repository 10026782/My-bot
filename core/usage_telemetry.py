# core/usage_telemetry.py — Cost Telemetry Reliability PR2 (shadow only)
#
# The ONE shared recording point for every paid AI provider call this repo
# makes — Anthropic text (run_agent, llm_fallback, interaction_engine),
# OpenAI text fallback (llm_fallback), OpenAI Whisper STT
# (voice_stt_adapter) — durable in PostgreSQL (usage_events, see
# core/migrations/002_usage_events.sql).
#
# SHADOW ONLY: nothing in this PR reads from usage_events to drive
# AI_Usage_Daily or the EMERGENCY_STOP_AI trigger. cost_monitor.py's
# existing in-memory accumulators and pricing table are completely
# untouched — this module exists purely to start recording real,
# provider/service/model-generic usage durably, so a later PR can cut the
# trigger over to it only after this data has been observed running
# correctly for a while. COST_WATCHDOG_LIVE stays false through this PR.
#
# Every call site that gets a real response from a provider must call
# record_usage() (or the record_llm_usage()/record_stt_usage() shortcuts)
# exactly once per real API call — never per wrapper layer. Concretely:
# instrument at the innermost point where the raw SDK response is
# obtained (right after client.messages.create() /
# client.chat.completions.create() / client.audio.transcriptions.create()),
# not in any outer wrapper that merely calls something that already
# records. This is what makes call_anthropic_text()'s internal fallback to
# call_openai_text() safe: call_openai_text() records its own usage once,
# at its own call site; call_anthropic_text() never records a duplicate or
# a phantom row for the failed Anthropic attempt (a failed attempt never
# produced a usable response — there is nothing real to record).
#
# (provider, request_id) is the de-dup key — see the migration's
# UNIQUE(provider, request_id) constraint — as a second line of defense
# against the same call being recorded twice. Scoped to provider, not a
# bare request_id, since different providers' id namespaces aren't
# guaranteed disjoint.
#
# Fail-soft by design: PostgreSQL being unavailable must never break the
# caller's actual request (sending a Telegram reply, transcribing a voice
# note, etc.) — record_usage() never raises. It DOES log loudly on failure
# because a durable-telemetry gap is itself the exact kind of thing this
# rewrite exists to stop happening silently.
#
# Connection handling (fixed from an earlier draft, per review):
#   - Every read path uses exactly ONE connection/cursor for both "is
#     Postgres reachable" and the actual query — there is no separate
#     "probe a connection, release it, then acquire a second one for the
#     real query" step. A single acquire-query-release per call.
#   - A query that raises (not "Postgres unavailable", but "the query
#     itself failed" — bad SQL, a schema mismatch, a transient error mid-
#     query) is reported as status="error", never silently folded into an
#     empty/zeroed result. Conflating "the query failed" with "zero usage
#     happened" is exactly the AI_Usage_Daily bug (Part A/B of this PR
#     series) this module must not repeat for its own read path.
#   - Every except block that touches a connection calls conn.rollback()
#     before release_conn(conn) — an unhandled exception mid-transaction
#     leaves the connection in an aborted-transaction state; returning it
#     to the pool without rolling back poisons it for the next caller,
#     who would get "current transaction is aborted" on their first query.

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone, date as _date
from typing import Literal

from core.model_pricing import compute_cost

logger = logging.getLogger(__name__)

WindowStatus = Literal["ok", "unavailable", "error"]


def record_usage(
    *,
    provider: str,
    service: str,
    model: str,
    source: str,
    unit: str,
    quantity_out: float,
    quantity_in: float | None = None,
    caller: str = "",
    request_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    """
    Durably records one real provider API call and its cost. Returns True
    if the row was written (or already existed under the same request_id —
    that's still success, just deduplicated), False if PostgreSQL is
    unavailable or the write failed. Never raises.
    """
    cost_usd, exact = compute_cost(provider, service, model, quantity_in, quantity_out)

    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        logger.error(
            "[UsageTelemetry] PostgreSQL unavailable — usage NOT durably recorded "
            "(provider=%s service=%s model=%s source=%s quantity_in=%s quantity_out=%s "
            "cost=$%.4f). This is shadow-only telemetry (no trigger depends on it yet), "
            "but the gap itself should be investigated.",
            provider, service, model, source, quantity_in, quantity_out, cost_usd,
        )
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usage_events
                    (ts, provider, service, model, source, caller, unit,
                     quantity_in, quantity_out, cost_usd, cost_is_estimate,
                     request_id, meta)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (provider, request_id) DO NOTHING;
                """,
                (
                    provider, service, model, source, caller or None, unit,
                    quantity_in, quantity_out, cost_usd, not exact,
                    request_id, json.dumps(meta) if meta else None,
                ),
            )
            conn.commit()
        logger.debug(
            "[UsageTelemetry] recorded provider=%s service=%s model=%s source=%s "
            "quantity_out=%s cost=$%.4f estimate=%s",
            provider, service, model, source, quantity_out, cost_usd, not exact,
        )
        return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("[UsageTelemetry] record_usage failed: %s", e, exc_info=True)
        return False
    finally:
        release_conn(conn)


def record_llm_usage(
    *,
    source: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    provider: str = "anthropic",
    caller: str = "",
    request_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    """Convenience wrapper for the common case: a text LLM call."""
    return record_usage(
        provider=provider,
        service="text",
        model=model,
        source=source,
        unit="tokens",
        quantity_in=tokens_in,
        quantity_out=tokens_out,
        caller=caller,
        request_id=request_id,
        meta=meta,
    )


def record_stt_usage(
    *,
    source: str,
    model: str,
    duration_seconds: float,
    provider: str = "openai",
    caller: str = "",
    request_id: str | None = None,
    meta: dict | None = None,
) -> bool:
    """Convenience wrapper for the STT case: quantity_out = duration_seconds, no input side."""
    return record_usage(
        provider=provider,
        service="stt",
        model=model,
        source=source,
        unit="seconds",
        quantity_in=None,
        quantity_out=duration_seconds,
        caller=caller,
        request_id=request_id,
        meta=meta,
    )


def _empty_window_result(status: WindowStatus, error: str = "") -> dict:
    return {
        "status": status,
        "error": error,
        "by_model": {},
        "by_source": {},
        "total_calls": 0,
        "total_cost_usd": 0.0,
        "total_cost_usd_confirmed": 0.0,
        "total_cost_usd_estimated": 0.0,
    }


def get_usage_window(start: datetime, end: datetime) -> dict:
    """
    Aggregates durable usage_events in [start, end) using exactly ONE
    connection/cursor for the whole operation. Returns:
      {
        "status": "ok" | "unavailable" | "error",
        "error": str,  # only set for "error"
        "by_model": {(provider, service, model): {"quantity_in": float, "quantity_out": float,
                                                    "calls": int, "cost_usd": float,
                                                    "estimated_calls": int}},
        "by_source": {source: {"calls": int, "cost_usd": float}},
        "total_calls": int,
        "total_cost_usd": float,
        "total_cost_usd_confirmed": float,   # sum over exact-priced rows only
        "total_cost_usd_estimated": float,   # sum over fail-safe-priced rows only
      }

    status="unavailable" means PostgreSQL itself couldn't be reached — no
    connection was ever obtained. status="error" means a connection WAS
    obtained but the query itself failed (bad SQL, transient DB error,
    etc.) — this is deliberately distinct from "ok" with zero rows, and
    distinct from "unavailable": a caller must never treat either as "zero
    usage happened", only "ok" with an empty by_model/by_source actually
    means that. Never raises.
    """
    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        return _empty_window_result("unavailable")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT provider, service, model, source, quantity_in, quantity_out,
                       cost_usd, cost_is_estimate
                FROM usage_events
                WHERE ts >= %s AND ts < %s;
                """,
                (start, end),
            )
            rows = cur.fetchall()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("[UsageTelemetry] get_usage_window query failed: %s", e, exc_info=True)
        return _empty_window_result("error", str(e))
    finally:
        release_conn(conn)

    by_model: dict[tuple[str, str, str], dict] = {}
    by_source: dict[str, dict] = {}
    total_cost = 0.0
    total_cost_confirmed = 0.0
    total_cost_estimated = 0.0

    for provider, service, model, source, qin, qout, cost_usd, is_estimate in rows:
        key = (provider, service, model)
        m = by_model.setdefault(key, {
            "quantity_in": 0.0, "quantity_out": 0.0, "calls": 0,
            "cost_usd": 0.0, "estimated_calls": 0,
        })
        m["quantity_in"]  += float(qin or 0)
        m["quantity_out"] += float(qout or 0)
        m["calls"]        += 1
        m["cost_usd"]     += float(cost_usd or 0)
        if is_estimate:
            m["estimated_calls"] += 1

        s = by_source.setdefault(source, {"calls": 0, "cost_usd": 0.0})
        s["calls"]    += 1
        s["cost_usd"] += float(cost_usd or 0)

        total_cost += float(cost_usd or 0)
        if is_estimate:
            total_cost_estimated += float(cost_usd or 0)
        else:
            total_cost_confirmed += float(cost_usd or 0)

    return {
        "status": "ok",
        "error": "",
        "by_model": by_model,
        "by_source": by_source,
        "total_calls": len(rows),
        "total_cost_usd": total_cost,
        "total_cost_usd_confirmed": total_cost_confirmed,
        "total_cost_usd_estimated": total_cost_estimated,
    }


def get_daily_usage(day: _date | None = None) -> dict:
    """Usage for one UTC calendar day (default: today). See get_usage_window()."""
    if day is None:
        day = datetime.now(tz=timezone.utc).date()
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return get_usage_window(start, end)


def get_trailing_hour_usage(now: datetime | None = None) -> dict:
    """Usage in the trailing 60 minutes (default: from now)."""
    if now is None:
        now = datetime.now(tz=timezone.utc)
    return get_usage_window(now - timedelta(hours=1), now)
