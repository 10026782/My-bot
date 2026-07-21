# cost_monitor.py — CORE_05: Cost Watchdog (hourly alert)
#
# Hourly $ threshold check only. Reads durable usage from
# core.usage_telemetry (PostgreSQL) instead of accumulating an in-memory
# counter — the previous _hourly_cost/_daily_cost globals reset to zero on
# every process restart/redeploy, and separately mispriced Haiku (keyed as
# "claude-haiku-4-5" against the real "claude-haiku-4-5-20251001" string,
# silently falling back to Opus pricing — a 5x overcount on the model that
# carries almost all traffic). Pricing now lives in core.model_pricing,
# keyed by the exact strings actually sent to each provider.
#
# The daily $ threshold and EMERGENCY_STOP_AI trigger moved to
# core/cost_watchdog.py::daily_watchdog() — one place computes the durable
# daily total and decides whether to stop, instead of two independent
# accumulators (this file's old daily logic vs core/cost_watchdog.py's
# jsonl-based one) that could disagree.
#
# flag: COST_WATCHDOG_LIVE (env: COST_WATCHDOG_LIVE=true), כבוי כברירת מחדל.

import logging
import os

from feature_flags import is_enabled

logger = logging.getLogger(__name__)

COST_HOURLY_LIMIT: float = float(os.environ.get("COST_HOURLY_LIMIT", "5.0"))
COST_DAILY_LIMIT:  float = float(os.environ.get("COST_DAILY_LIMIT",  "20.0"))


def _send_owner_message(text: str) -> None:
    owner_chat_id = (
        os.environ.get("OWNER_TELEGRAM_ID", "")
        or os.environ.get("ELIYAHU_CHAT_ID", "")
    )
    if not owner_chat_id:
        logger.warning("[CostWatchdog] OWNER_TELEGRAM_ID/ELIYAHU_CHAT_ID לא מוגדר — לא ניתן לשלוח התראה")
        return
    try:
        import telebot  # type: ignore
        token = os.environ.get("TELEGRAM_TOKEN", "")
        if not token:
            return
        b = telebot.TeleBot(token)
        b.send_message(int(owner_chat_id), text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"[CostWatchdog] _send_owner_message error: {e}")


def check_thresholds() -> None:
    """
    בודק סף שעתי בדולרים, מהעלות האמיתית של השעה האחרונה (usage_events,
    durable). שולח התראה בלבד — לא עוצר AI (זה תפקידו של
    core/cost_watchdog.py::daily_watchdog, מהסכום היומי).
    Scheduler קורא לזה כל 60 דקות. non-blocking, לעולם לא זורק.
    """
    if not is_enabled("COST_WATCHDOG_LIVE"):
        return
    try:
        from core.usage_telemetry import get_trailing_hour_usage

        usage = get_trailing_hour_usage()
        if not usage["postgres_available"]:
            logger.error(
                "[CostWatchdog] PostgreSQL unavailable — cannot compute durable hourly cost, "
                "skipping this check (fail-safe: skip, not zero)."
            )
            return

        hourly_cost = usage["total_cost_usd"]
        logger.debug(
            f"[CostWatchdog] trailing-hour cost=${hourly_cost:.4f} "
            f"calls={usage['total_calls']} limit=${COST_HOURLY_LIMIT:.2f}"
        )

        if hourly_cost > COST_HOURLY_LIMIT:
            logger.warning(
                f"[CostWatchdog] ⚠️ hourly cost ${hourly_cost:.2f} > limit ${COST_HOURLY_LIMIT:.2f}"
            )
            _send_owner_message(
                f"⚠️ *Cost Alert — עלות גבוהה*\n"
                f"עלות שעה אחרונה (מאומתת): *${hourly_cost:.2f}* עברה את הסף *${COST_HOURLY_LIMIT:.2f}*\n"
                f"AI פועל כרגיל — אם הדפוס ממשיך ייעצר ביום (בדיקה יומית ב-08:15)."
            )

    except Exception as e:
        logger.error(f"[CostWatchdog] check_thresholds error: {e}")


def get_stats() -> dict:
    """מחזיר נתוני עלות נוכחיים — לאבחון ו-/status. מאציל ל-core.cost_watchdog.get_stats()."""
    from core.cost_watchdog import get_stats as _durable_stats
    return _durable_stats()


def job_cost_watchdog() -> None:
    """Scheduler job — כל 60 דקות."""
    check_thresholds()
