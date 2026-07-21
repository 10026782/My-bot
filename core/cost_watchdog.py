# core/cost_watchdog.py — CORE_05 v2: Count-based usage watchdog
#
# Dollar-based emergency stop → cost_monitor.py (unchanged, still active).
# This module handles count-based tracking + JSONL persistence + Airtable aggregation.
#
# log_usage()     — append-only write to logs/usage.jsonl, never throws.
# daily_watchdog() — reads last 24h, aggregates, checks thresholds, alerts + Airtable row.
#
# flag: COST_WATCHDOG_ENABLED (default on — "Pipes first").
#
# Cost Telemetry Reliability, PR1 (write-truthfulness + upsert only — no
# usage_events, no trigger changes, no new Airtable fields; those are
# separate PRs in the same series): _write_airtable_row() now upserts by
# Date (find-or-create, was create-only — a retry used to silently
# duplicate the day's row) and only logs success when Airtable actually
# confirms the write. Previously it logged "שורה יומית נכתבה ל-Airtable"
# unconditionally right after calling airtable_create(), which returns
# None (not an exception) on a non-2xx response — this table hit a real
# 422 UNKNOWN_FIELD_NAME for weeks while every log line still claimed
# success (see _write_airtable_row's own docstring).
#
# This PR writes ONLY the 5 fields that exist in the live table today
# (Date, claude_sonnet, claude_haiku, whatsapp_conversation, total_units).
# A cost-breakdown schema extension (total_cost_usd, openai_text_cost_usd,
# openai_stt_cost_usd, unpriced_events) was considered for this PR but
# deferred to PR2 in this series — schema_cache.json is a local guess
# about what fields validate_airtable_fields() will accept, NOT proof the
# live Airtable table actually has them; writing values for fields nobody
# has confirmed exist would risk the exact silent-422 failure mode this PR
# exists to fix, just for new fields instead of "Date". PR2 will verify
# against the live Airtable Meta API before adding anything.
#
# The upsert (lookup, then create-or-patch) is BEST-EFFORT SEQUENTIAL, not
# atomic — there is no compare-and-set here. Two concurrent daily_watchdog()
# runs for the same Date could both see "no existing row" and both call
# airtable_create(), producing a duplicate (a lookup→create TOCTOU window).
# This is sufficient today because the scheduler runs in-process with
# WEB_CONCURRENCY=1 (one call to daily_watchdog() at a time), so it
# prevents the duplicate this PR actually set out to fix (sequential
# retries/double-fires) — it does NOT guarantee correctness under true
# concurrent writers. A real fix would need either an Airtable unique-field
# constraint (Airtable has none) or a compare-and-set primitive equivalent
# to core/emergency_stop.py's EmergencyStopStore.write() expected_operation_id
# pattern — out of scope here.
#
# HOTFIX (post-merge production smoke failure): the lookup originally used
# at_get_by_field(table, "Date", date_str), which builds {Date}='YYYY-MM-DD'
# — a plain text-equality formula. Date is an Airtable DATE field, not
# text, so that formula never matched and every call took the create
# branch — production smoke showed 2 runs producing 2 rows, then 4 rows on
# a repeat. Fixed to at_list_by_formula() with
# DATETIME_FORMAT({Date}, 'YYYY-MM-DD')='<date_str>' (converts the date
# field to text before comparing) and max_records=2 so an already-existing
# duplicate (e.g. from this very bug) is detected and refused rather than
# patched arbitrarily. See _write_airtable_row()'s own docstring for the
# full account.

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta, date as _date
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_PATH = Path(os.environ.get("USAGE_LOG_PATH", "/tmp/usage.jsonl"))

# ── ספים (configurable via env) ──────────────────────────────────────
_SONNET_DAILY_LIMIT = int(os.environ.get("SONNET_DAILY_LIMIT", "100000"))


def _enabled() -> bool:
    val = os.environ.get("COST_WATCHDOG_ENABLED", "").strip().lower()
    if val:
        return val not in ("false", "0", "no")
    live = os.environ.get("COST_WATCHDOG_LIVE", "true").strip().lower()
    return live not in ("false", "0", "no")


def log_usage(
    source_type: str,
    units: int,
    meta: dict | None = None,
    user_id: str = "system",
) -> None:
    """
    מתעד שימוש append-only ל-logs/usage.jsonl.
    source_type: "claude_sonnet" | "claude_haiku" | "whatsapp_conversation" | ...
    units: tokens (Claude) or 1 (conversation count)
    never raises — כשל בלוג לא מפיל את הקריאה המקורית.
    """
    if not _enabled():
        return
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts":          datetime.now(tz=timezone.utc).isoformat(),
            "source_type": source_type,
            "units":       units,
            "user_id":     user_id,
        }
        if meta:
            entry["meta"] = meta
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("[CostWatchdogV2] log_usage error (non-fatal): %s", e)


# ══════════════════════════════════════════════════════════════════════
# Daily aggregation
# ══════════════════════════════════════════════════════════════════════

def _read_last_24h() -> list[dict]:
    """קורא רשומות מה-24 שעות האחרונות מה-JSONL."""
    if not _LOG_PATH.exists():
        return []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    records: list[dict] = []
    try:
        with _LOG_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry.get("ts", ""))
                    if ts >= cutoff:
                        records.append(entry)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("[CostWatchdogV2] _read_last_24h error: %s", e)
    return records


def _aggregate(records: list[dict]) -> dict[str, int]:
    """מחשב סכום units לפי source_type."""
    totals: dict[str, int] = {}
    for r in records:
        src = r.get("source_type", "unknown")
        totals[src] = totals.get(src, 0) + int(r.get("units", 0))
    return totals


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


def _write_airtable_row(date_str: str, counts: dict[str, int]) -> bool:
    """
    Upserts the AI_Usage_Daily row for one date. Returns True only when
    Airtable actually confirms the write.

    HOTFIX (post-merge production smoke failure): the previous version
    looked up the existing row via at_get_by_field(table, "Date", date_str),
    which builds the formula {Date}='YYYY-MM-DD'. Date is an Airtable DATE
    field, not text — a plain string-equality formula against a date field
    never matches, so at_get_by_field() always returned None and every
    single call took the create branch. Production smoke confirmed this:
    two consecutive runs produced two rows, not one create + one patch;
    repeating produced four. Returning True only proved each write
    succeeded — it never proved upsert picked the right branch, which is
    exactly the gap that let this ship broken the first time.

    Fixed by:
      - Looking up via at_list_by_formula() with a date-aware formula:
        DATETIME_FORMAT({Date}, 'YYYY-MM-DD')='<date_str>' — converts the
        date field to text on Airtable's side before comparing, instead of
        comparing a date value to a text literal.
      - Requesting max_records=2 (not 1) so a genuine duplicate — e.g. from
        this exact bug already having run in production — is DETECTED
        (2+ matches) rather than silently patching an arbitrary one of
        several rows for the same date. 2+ matches refuses to write at all
        (a data-integrity problem, not a normal upsert case) and must be
        fixed manually in Airtable first.
      - date_str is validated with date.fromisoformat() before any Airtable
        call — a malformed date_str must never reach Airtable as a formula
        fragment or silently create a row under a garbage date.

    Two bugs this already fixed vs the pre-#435 version (unchanged by this
    hotfix):
      1. It used to log "שורה יומית נכתבה ל-Airtable" unconditionally right
         after calling airtable_create(), without checking the return
         value. airtable_create() returns None (not an exception) on any
         non-2xx response — e.g. the live 422 UNKNOWN_FIELD_NAME this table
         hit for weeks while every day's log line still claimed success
         (the field was "﻿Date", BOM-prefixed, vs the plain "Date" this
         write sends — since fixed directly in Airtable).
      2. It always called airtable_create(), so re-running daily_watchdog()
         for a date that already has a row (a manual retry, a scheduler
         double-fire) used to silently create a SECOND row for the same
         date instead of overwriting it.

    Writes ONLY the 5 fields that exist in the live table today. A cost
    breakdown (total_cost_usd/openai_text_cost_usd/openai_stt_cost_usd/
    unpriced_events) is intentionally NOT written here — those fields
    aren't confirmed to exist in the live Airtable table yet, and writing
    0 for a value nobody is actually measuring would itself be a
    non-truthful placeholder (indistinguishable from "measured, zero
    usage"). schema_cache.json making up a field name doesn't make it
    exist in Airtable — see PR2 in the cost-telemetry series, which
    verifies against the live Meta API before adding anything.

    The upsert (lookup-then-create-or-patch) is best-effort SEQUENTIAL,
    not atomic — see this module's docstring for the TOCTOU caveat under
    true concurrency; it's sufficient today only because the scheduler
    calls this one job at a time (WEB_CONCURRENCY=1). This hotfix does NOT
    make the upsert atomic — it fixes the lookup formula that was making
    every call miss the existing row entirely, a strictly worse bug than
    the pre-existing TOCTOU window.
    """
    try:
        _date.fromisoformat(date_str)
    except (ValueError, TypeError) as e:
        logger.error(
            "[CostWatchdogV2] AI_Usage_Daily write REFUSED for %r — not a valid "
            "ISO date (%s). No Airtable call made.",
            date_str, e,
        )
        return False

    try:
        from airtable_schema import Tables
        table = getattr(Tables, "AI_USAGE_DAILY", "AI_Usage_Daily")
        fields: dict = {
            "Date":                   date_str,
            "claude_sonnet":           counts.get("claude_sonnet",          0),
            "claude_haiku":            counts.get("claude_haiku",           0),
            "whatsapp_conversation":   counts.get("whatsapp_conversation",  0),
            "total_units":             sum(counts.values()),
        }

        from tools.airtable_gateway import (
            airtable_create, airtable_patch, at_list_by_formula,
            _safe_formula_param, AirtableLookupError,
        )

        formula = f"DATETIME_FORMAT({{Date}}, 'YYYY-MM-DD')='{_safe_formula_param(date_str)}'"
        try:
            matches = at_list_by_formula(table, formula, max_records=2)
        except AirtableLookupError as e:
            logger.error(
                "[CostWatchdogV2] AI_Usage_Daily upsert lookup FAILED for %s (%s) — "
                "cannot tell whether a row already exists, refusing to blind-create "
                "(would risk a duplicate). NOT logging success.",
                date_str, e,
            )
            return False

        if len(matches) >= 2:
            logger.error(
                "[CostWatchdogV2] AI_Usage_Daily DUPLICATE-ROW INTEGRITY ERROR for %s — "
                "at least 2 matching rows for this date (record ids seen: %s; the lookup "
                "caps at max_records=2, so the true count may be higher). Refusing to "
                "write (would guess which row is authoritative). Needs manual cleanup in "
                "Airtable before this date can be updated again.",
                date_str, [m.get("id") for m in matches],
            )
            return False

        if len(matches) == 1:
            record_id = matches[0]["id"]
            write_fields = {k: v for k, v in fields.items() if k != "Date"}
            ok = airtable_patch(table, record_id, write_fields, source="cost_watchdog")
            if not ok:
                logger.error(
                    "[CostWatchdogV2] AI_Usage_Daily upsert (patch) FAILED for %s "
                    "(record %s) — see the [gateway:cost_watchdog] warning above for "
                    "the actual HTTP status/body. NOT logging success.",
                    date_str, record_id,
                )
                return False
            logger.info(
                "[CostWatchdogV2] AI_Usage_Daily upsert OK: branch=patch date=%s "
                "record_id=%s source=cost_watchdog fields=%s",
                date_str, record_id, fields,
            )
            return True

        # len(matches) == 0
        result = airtable_create(table, fields, source="cost_watchdog")
        if result is None:
            logger.error(
                "[CostWatchdogV2] AI_Usage_Daily write FAILED for %s — airtable_create() "
                "returned None (see the [gateway:cost_watchdog] warning above for the "
                "actual HTTP status/body). NOT logging success.",
                date_str,
            )
            return False

        record_id = result.get("id", "?")
        logger.info(
            "[CostWatchdogV2] AI_Usage_Daily upsert OK: branch=create date=%s "
            "record_id=%s source=cost_watchdog fields=%s",
            date_str, record_id, fields,
        )
        return True
    except Exception as e:
        logger.error("[CostWatchdogV2] _write_airtable_row FAILED: %s", e, exc_info=True)
        return False


def daily_watchdog() -> None:
    """
    Scheduler job — כל יום 08:00.
    קורא usage.jsonl (24 שעות אחרונות), מסכם, בודק ספים,
    שולח התראה לאליהו אם חריגה, כותב שורה ל-AI_Usage_Daily.
    Never raises.
    """
    if not _enabled():
        return
    try:
        records = _read_last_24h()
        counts = _aggregate(records)
        date_str = datetime.now(tz=timezone.utc).date().isoformat()

        if not counts:
            logger.info("[CostWatchdogV2] אין שימוש ב-24 שעות האחרונות — כותב שורת אפסים")

        logger.info("[CostWatchdogV2] daily: %s", counts)

        # בדיקת ספים — כל source_type בנפרד
        alerts: list[str] = []

        sonnet_count = counts.get("claude_sonnet", 0)
        if sonnet_count > _SONNET_DAILY_LIMIT:
            alerts.append(
                f"• claude_sonnet: *{sonnet_count}* קריאות (סף: {_SONNET_DAILY_LIMIT})"
            )

        # WA threshold — מופעל רק כשמוגדר
        wa_limit = int(os.environ.get("WHATSAPP_CONV_DAILY_LIMIT", "0"))
        if wa_limit:
            wa_count = counts.get("whatsapp_conversation", 0)
            if wa_count > wa_limit:
                alerts.append(
                    f"• whatsapp_conversation: *{wa_count}* (סף: {wa_limit})"
                )

        if alerts:
            breakdown = "\n".join(
                f"  • {src}: {cnt:,}" for src, cnt in sorted(counts.items())
            )
            _send_owner_alert(
                f"⚠️ *Cost Watchdog — חריגת שימוש*\n"
                f"תאריך: {date_str}\n\n"
                f"*חריגות:*\n" + "\n".join(alerts) +
                f"\n\n*כל השימוש היום:*\n{breakdown}"
            )

        saved = _write_airtable_row(date_str, counts)
        if not saved:
            logger.error(
                "[CostWatchdogV2] AI_Usage_Daily projection NOT saved for %s this run — "
                "see the _write_airtable_row error immediately above for why.",
                date_str,
            )

    except Exception as e:
        logger.error("[CostWatchdogV2] daily_watchdog error: %s", e)
