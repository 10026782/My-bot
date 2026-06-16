# core/cost_watchdog.py — CORE_05 v2: Count-based usage watchdog
#
# Dollar-based emergency stop → cost_monitor.py (unchanged, still active).
# This module handles count-based tracking + JSONL persistence + Airtable aggregation.
#
# log_usage()     — append-only write to logs/usage.jsonl, never throws.
# daily_watchdog() — reads last 24h, aggregates, checks thresholds, alerts + Airtable row.
#
# flag: COST_WATCHDOG_ENABLED (default on — "Pipes first").

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_PATH = Path(os.environ.get("USAGE_LOG_PATH", "/tmp/usage.jsonl"))

# ── ספים (configurable via env) ──────────────────────────────────────
_SONNET_DAILY_LIMIT = int(os.environ.get("SONNET_DAILY_LIMIT", "50"))


def _enabled() -> bool:
    val = os.environ.get("COST_WATCHDOG_ENABLED", "true")
    return val.lower() not in ("false", "0", "no")


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


def _write_airtable_row(date_str: str, counts: dict[str, int]) -> None:
    """כותב שורה יומית ל-Airtable AI_Usage_Daily."""
    try:
        from airtable_schema import Tables
        table = getattr(Tables, "AI_USAGE_DAILY", "AI_Usage_Daily")
        fields: dict = {
            "Date":         date_str,
            "claude_sonnet": counts.get("claude_sonnet", 0),
            "claude_haiku":  counts.get("claude_haiku",  0),
            "total_units":   sum(counts.values()),
        }
        from tools.airtable_gateway import airtable_create
        result = airtable_create(table, fields, source="cost_watchdog")
        logger.info("[CostWatchdogV2] שורה יומית נכתבה ל-Airtable: %s — %s", date_str, fields)
        return result
    except Exception as e:
        logger.error("[CostWatchdogV2] _write_airtable_row FAILED: %s", e, exc_info=True)


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

        _write_airtable_row(date_str, counts)

    except Exception as e:
        logger.error("[CostWatchdogV2] daily_watchdog error: %s", e)
