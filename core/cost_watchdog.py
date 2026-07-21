# core/cost_watchdog.py — CORE_05 v3: Cost Telemetry Reliability
#
# daily_watchdog() is now the SOLE place that (a) computes the day's real
# spend from durable core.usage_telemetry data, (b) projects it into the
# AI_Usage_Daily Airtable table (a projection, not a source of truth — see
# core/migrations/002_usage_events.sql), and (c) triggers EMERGENCY_STOP_AI
# when COST_DAILY_LIMIT is exceeded. cost_monitor.py keeps the hourly
# alert-only check, also durable-data-driven.
#
# What changed vs the previous version of this file, and why:
#   - log_usage() / usage.jsonl / _read_last_24h() / _aggregate() are gone.
#     /tmp is per-instance and wiped on every Render redeploy — it produced
#     "אין שימוש ב-24 שעות האחרונות" every single day regardless of real
#     traffic (see docs/audit/POST_N15_WORK_SURVEY_20260720.md for the same
#     failure mode already tracked for EMERGENCY_STOP_* flag persistence).
#   - _write_airtable_row() used to log success unconditionally right after
#     calling airtable_create(), without checking its return value.
#     airtable_create() returns None (not an exception) on a non-2xx
#     response — e.g. the live 422 UNKNOWN_FIELD_NAME this table hit for
#     weeks while every day's log line still read "שורה יומית נכתבה
#     ל-Airtable". It now returns bool and the caller logs accordingly.
#   - Daily cost is computed from core.usage_telemetry (PostgreSQL,
#     survives restart/deploy) instead of an in-memory accumulator that
#     reset to zero on every process restart.
#
# flag: COST_WATCHDOG_ENABLED (falls back to COST_WATCHDOG_LIVE if unset).

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_SONNET_DAILY_LIMIT = int(os.environ.get("SONNET_DAILY_LIMIT", "100000"))


def _enabled() -> bool:
    val = os.environ.get("COST_WATCHDOG_ENABLED", "").strip().lower()
    if val:
        return val not in ("false", "0", "no")
    live = os.environ.get("COST_WATCHDOG_LIVE", "true").strip().lower()
    return live not in ("false", "0", "no")


def _send_owner_alert(text: str) -> None:
    owner = os.environ.get("OWNER_TELEGRAM_ID") or os.environ.get("ELIYAHU_CHAT_ID", "")
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not owner or not token:
        logger.warning("[CostWatchdogV2] אין OWNER_TELEGRAM_ID/TELEGRAM_TOKEN — התראה לא נשלחה")
        return
    try:
        import telebot  # type: ignore
        telebot.TeleBot(token).send_message(int(owner), text, parse_mode="Markdown")
        logger.info("[CostWatchdogV2] התראה נשלחה לאליהו")
    except Exception as e:
        logger.error("[CostWatchdogV2] _send_owner_alert error: %s", e)


def _bucket_for_model(service: str, model: str) -> str | None:
    """Maps a (service, model) to the legacy AI_Usage_Daily field it feeds.
    Only text LLM calls map to a bucket — STT/other services still count
    toward total_units but not toward claude_sonnet/claude_haiku."""
    if service != "text":
        return None
    if "sonnet" in model:
        return "claude_sonnet"
    if "haiku" in model:
        return "claude_haiku"
    return None


def _write_airtable_row(date_str: str, fields: dict) -> bool:
    """
    Writes (or overwrites) the AI_Usage_Daily projection row for one date.
    Returns True only when Airtable actually confirms the write — never
    logs success without checking airtable_create()'s return value (that
    silent-success bug is exactly what let this table go weeks without
    real data while every log line claimed success).
    """
    try:
        from airtable_schema import Tables
        table = getattr(Tables, "AI_USAGE_DAILY", "AI_Usage_Daily")
        row_fields = {"Date": date_str, **fields}

        from tools.airtable_gateway import airtable_create
        result = airtable_create(table, row_fields, source="cost_watchdog")

        if result is None:
            logger.error(
                "[CostWatchdogV2] AI_Usage_Daily write FAILED for %s — airtable_create() "
                "returned None (see the [gateway:cost_watchdog] warning immediately above "
                "for the actual HTTP status/body). NOT logging success.",
                date_str,
            )
            return False

        logger.info(
            "[CostWatchdogV2] שורה יומית נכתבה ל-Airtable (מאומת): %s — %s",
            date_str, row_fields,
        )
        return True
    except Exception as e:
        logger.error("[CostWatchdogV2] _write_airtable_row FAILED: %s", e, exc_info=True)
        return False


def _trigger_daily_stop_durable(daily_cost: float, date_str: str) -> None:
    """
    Activates EMERGENCY_STOP_AI from the durable daily total (D.6). Prefers
    the new durable+verified write API (feature_flags.set_emergency_stop —
    core/emergency_stop.py's EmergencyStopManager, Airtable-backed) so
    success is only reported when write.ok and write.verified (D.7).

    That new API is a WRITE-side upgrade only — app.py's actual enforcement
    (_flag_enabled("EMERGENCY_STOP_AI"), app.py:3043) still reads through
    the legacy feature_flags.is_enabled()/set_flag() path; migrating that
    read path is an explicit later cutover the codebase already defers
    (see core/emergency_stop_bootstrap.py's module docstring). Skipping the
    legacy set_flag() call here would make this function durable but
    functionally inert — the bot would keep spending past the limit while
    Airtable quietly held the "true" nobody was reading. So this function
    always also calls the legacy set_flag(), regardless of whether the
    durable write succeeded, and reports the durable outcome separately —
    enforcement must never depend on the newer path succeeding.
    """
    from feature_flags import is_enabled, set_flag

    if is_enabled("EMERGENCY_STOP_AI"):
        logger.info(
            "[CostWatchdogV2] EMERGENCY_STOP_AI already active — daily cost $%.2f > limit "
            "confirmed again for %s, no new trigger needed.", daily_cost, date_str,
        )
        return

    durable_ok = False
    durable_verified = False
    durable_error = ""
    try:
        import feature_flags as _ff
        write_result = _ff.set_emergency_stop(
            "EMERGENCY_STOP_AI", True,
            operation_id=str(uuid.uuid4()),
            updated_by="cost_watchdog",
            reason=f"daily cost ${daily_cost:.2f} > limit (durable usage_events total, {date_str})",
        )
        durable_ok = write_result.ok
        durable_verified = write_result.verified
        durable_error = write_result.error
    except Exception as e:
        # Covers EmergencyStopNotConfigured (bootstrap_emergency_stop() not
        # run yet) and any unexpected failure — broad on purpose, this path
        # must never itself throw and skip the legacy set_flag() below.
        durable_error = f"{e.__class__.__name__}: {e}"

    if durable_ok and durable_verified:
        logger.critical(
            "[CostWatchdogV2] 🚨 EMERGENCY_STOP_AI — durable+verified write succeeded. "
            "daily cost $%.2f > limit ($%s)", daily_cost, date_str,
        )
    else:
        logger.critical(
            "[CostWatchdogV2] 🚨 EMERGENCY_STOP_AI — durable write NOT confirmed "
            "(ok=%s verified=%s error=%s) — falling back to legacy flag write. "
            "Someone should check Airtable Emergency_Window / the durable store directly.",
            durable_ok, durable_verified, durable_error,
        )

    # Always also write the legacy flag — this is what app.py actually
    # enforces today (see docstring above).
    set_flag("EMERGENCY_STOP_AI", True)

    _send_owner_alert(
        f"🚨 *Cost Emergency Stop*\n"
        f"עלות יומית (מאומתת, מ-usage_events): *${daily_cost:.2f}*\n"
        f"ה-AI נעצר אוטומטית. לאפשור מחדש:\n"
        f"`/flag EMERGENCY_STOP_AI false`\n\n"
        + ("(כתיבה דורבלת אומתה)" if (durable_ok and durable_verified)
           else f"⚠️ כתיבה דורבלת לא אושרה ({durable_error}) — נבדק ידנית.")
    )


def daily_watchdog() -> None:
    """
    Scheduler job — כל יום 08:15.
    שואב שימוש יומי מ-usage_events (Postgres, durable), כותב פרויקציה
    ל-AI_Usage_Daily, ומפעיל EMERGENCY_STOP_AI אם העלות היומית האמיתית
    חצתה את COST_DAILY_LIMIT. Never raises.
    """
    if not _enabled():
        return
    try:
        from core.usage_telemetry import get_daily_usage
        from core.model_pricing import get_pricing_mismatch_count

        usage = get_daily_usage()
        date_str = datetime.now(tz=timezone.utc).date().isoformat()

        if not usage["postgres_available"]:
            logger.error(
                "[CostWatchdogV2] PostgreSQL unavailable — cannot compute durable daily usage "
                "for %s. AI_Usage_Daily projection and EMERGENCY_STOP_AI trigger both skipped "
                "this run (fail-safe: skip, do not write a false zero row).",
                date_str,
            )
            return

        by_model = usage["by_model"]
        counts = {"claude_sonnet": 0.0, "claude_haiku": 0.0, "whatsapp_conversation": 0}
        total_units = 0.0

        for (provider, service, model), agg in by_model.items():
            units = agg["quantity_in"] + agg["quantity_out"]
            bucket = _bucket_for_model(service, model)
            if bucket:
                counts[bucket] += units
            total_units += units

        daily_cost = usage["total_cost_usd"]
        logger.info(
            "[CostWatchdogV2] daily durable usage %s: calls=%d total_units=%.0f cost=$%.4f "
            "by_model=%s",
            date_str, usage["total_calls"], total_units, daily_cost,
            {f"{p}/{s}/{m}": a["calls"] for (p, s, m), a in by_model.items()},
        )

        mismatch_count = get_pricing_mismatch_count()
        if mismatch_count:
            logger.error(
                "[CostWatchdogV2] daily cost includes %d fail-safe-priced calls (unrecognized "
                "model/service) — figure is a conservative estimate, not exact for those calls.",
                mismatch_count,
            )

        saved = _write_airtable_row(date_str, {
            "claude_sonnet":         int(counts["claude_sonnet"]),
            "claude_haiku":          int(counts["claude_haiku"]),
            "whatsapp_conversation": int(counts["whatsapp_conversation"]),
            "total_units":           int(total_units),
        })
        if not saved:
            logger.error(
                "[CostWatchdogV2] AI_Usage_Daily projection NOT saved for %s — usage is durable "
                "in PostgreSQL (usage_events) but not reflected in Airtable this run.",
                date_str,
            )

        sonnet_count = counts["claude_sonnet"]
        if sonnet_count > _SONNET_DAILY_LIMIT:
            _send_owner_alert(
                f"⚠️ *Cost Watchdog — חריגת שימוש*\n"
                f"תאריך: {date_str}\n\n"
                f"claude_sonnet: *{int(sonnet_count):,}* (סף: {_SONNET_DAILY_LIMIT:,})\n"
                f"עלות יומית מאומתת: ${daily_cost:.2f}"
            )

        from cost_monitor import COST_DAILY_LIMIT
        if daily_cost > COST_DAILY_LIMIT:
            _trigger_daily_stop_durable(daily_cost, date_str)

    except Exception as e:
        logger.error("[CostWatchdogV2] daily_watchdog error: %s", e, exc_info=True)


def get_stats() -> dict:
    """Diagnostics for /status — trailing-hour + today, from durable data."""
    try:
        from core.usage_telemetry import get_daily_usage, get_trailing_hour_usage
        from cost_monitor import COST_HOURLY_LIMIT, COST_DAILY_LIMIT

        hourly = get_trailing_hour_usage()
        daily = get_daily_usage()
        return {
            "enabled":              _enabled(),
            "postgres_available":   daily["postgres_available"],
            "hourly_cost_usd":      round(hourly["total_cost_usd"], 4),
            "hourly_limit_usd":     COST_HOURLY_LIMIT,
            "daily_cost_usd":       round(daily["total_cost_usd"], 4),
            "daily_limit_usd":      COST_DAILY_LIMIT,
            "daily_calls":          daily["total_calls"],
        }
    except Exception as e:
        logger.error("[CostWatchdogV2] get_stats error: %s", e)
        return {"enabled": _enabled(), "error": str(e)}
