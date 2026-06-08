# cost_monitor.py — CORE_05: Cost Watchdog
# רושם כל קריאת Claude API (tokens_in + tokens_out + model + caller),
# מחשב עלות שעתית ויומית, שולח התראה לOwner אם עלות שעה > $X,
# ומפעיל Emergency Stop אוטומטי (EMERGENCY_STOP_AI) אם עלות יום > $Y.
# flag: COST_WATCHDOG_LIVE (env: COST_WATCHDOG_LIVE=true), כבוי כברירת מחדל.

import logging
import os
import threading
from datetime import datetime, timezone, date as _date

from feature_flags import is_enabled, set_flag

logger = logging.getLogger(__name__)

# ── תמחור לפי מודל ($ per 1M tokens) ──────────────────────────────
_PRICE: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5":   (1.00,  5.00),
    "claude-sonnet-4-6":  (3.00, 15.00),
    "claude-opus-4-6":    (5.00, 25.00),
    "claude-opus-4-7":    (5.00, 25.00),
    "claude-opus-4-8":    (5.00, 25.00),
}
_DEFAULT_PRICE = (5.00, 25.00)  # fallback: הכי יקר — לא להמעיט בהערכה

COST_HOURLY_LIMIT: float = float(os.environ.get("COST_HOURLY_LIMIT", "5.0"))
COST_DAILY_LIMIT:  float = float(os.environ.get("COST_DAILY_LIMIT",  "20.0"))

_lock = threading.Lock()

# ── מצבר שעתי ─────────────────────────────────────────────────────
_hourly_cost:    float    = 0.0
_hourly_calls:   int      = 0
_hourly_start:   datetime = datetime.now(tz=timezone.utc)
_hourly_alerted: bool     = False

# ── מצבר יומי ──────────────────────────────────────────────────────
_daily_cost:     float  = 0.0
_daily_calls:    int    = 0
_daily_date:     _date  = datetime.now(tz=timezone.utc).date()
_daily_stopped:  bool   = False   # מונע כפל Emergency Stop ביום נתון


def _compute_cost(tokens_in: int, tokens_out: int, model: str) -> float:
    price_in, price_out = _PRICE.get(model, _DEFAULT_PRICE)
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def record_call(model: str, tokens_in: int, tokens_out: int, caller: str = "") -> None:
    """
    קורא לזה מ-run_agent מיד אחרי כל client.messages.create().
    non-blocking, לעולם לא זורק.
    """
    if not is_enabled("COST_WATCHDOG_LIVE"):
        return
    try:
        call_cost = _compute_cost(tokens_in, tokens_out, model)

        with _lock:
            global _hourly_cost, _hourly_calls, _hourly_start, _hourly_alerted
            global _daily_cost, _daily_calls, _daily_date, _daily_stopped

            now   = datetime.now(tz=timezone.utc)
            today = now.date()

            # איפוס יומי כשעברנו חצות
            if today != _daily_date:
                _daily_cost    = 0.0
                _daily_calls   = 0
                _daily_date    = today
                _daily_stopped = False

            # איפוס שעתי כשעברה שעה
            if (now - _hourly_start).total_seconds() >= 3600:
                _hourly_cost    = 0.0
                _hourly_calls   = 0
                _hourly_start   = now
                _hourly_alerted = False

            _hourly_cost  += call_cost
            _hourly_calls += 1
            _daily_cost   += call_cost
            _daily_calls  += 1

        logger.debug(
            f"[CostWatchdog] {model} in={tokens_in} out={tokens_out} "
            f"cost=${call_cost:.4f} caller={caller} | "
            f"hourly=${_hourly_cost:.3f} daily=${_daily_cost:.3f}"
        )
    except Exception as e:
        logger.error(f"[CostWatchdog] record_call error: {e}")


def check_thresholds() -> None:
    """
    בודק סף שעתי/יומי ומפעיל התראות ועצירת חירום.
    Scheduler קורא לזה כל 60 דקות.
    non-blocking, לעולם לא זורק.
    """
    if not is_enabled("COST_WATCHDOG_LIVE"):
        return
    try:
        with _lock:
            hourly = _hourly_cost
            daily  = _daily_cost
            alerted = _hourly_alerted
            stopped = _daily_stopped

        if daily > COST_DAILY_LIMIT and not stopped:
            _trigger_daily_stop(daily)

        elif hourly > COST_HOURLY_LIMIT and not alerted:
            _send_hourly_alert(hourly)

    except Exception as e:
        logger.error(f"[CostWatchdog] check_thresholds error: {e}")


def _trigger_daily_stop(daily_cost: float) -> None:
    global _daily_stopped
    with _lock:
        if _daily_stopped:
            return
        _daily_stopped = True

    try:
        set_flag("EMERGENCY_STOP_AI", True)
        logger.critical(
            f"[CostWatchdog] 🚨 EMERGENCY_STOP_AI — "
            f"daily cost ${daily_cost:.2f} > limit ${COST_DAILY_LIMIT:.2f}"
        )
        _send_owner_message(
            f"🚨 *Cost Emergency Stop*\n"
            f"עלות יומית: *${daily_cost:.2f}* עברה את הסף *${COST_DAILY_LIMIT:.2f}*\n"
            f"ה-AI נעצר אוטומטית. לאפשור מחדש:\n"
            f"`/flag EMERGENCY_STOP_AI false`"
        )
    except Exception as e:
        logger.error(f"[CostWatchdog] _trigger_daily_stop error: {e}")


def _send_hourly_alert(hourly_cost: float) -> None:
    global _hourly_alerted
    with _lock:
        if _hourly_alerted:
            return
        _hourly_alerted = True

    try:
        logger.warning(
            f"[CostWatchdog] ⚠️ hourly cost ${hourly_cost:.2f} > limit ${COST_HOURLY_LIMIT:.2f}"
        )
        _send_owner_message(
            f"⚠️ *Cost Alert — עלות גבוהה*\n"
            f"עלות שעה: *${hourly_cost:.2f}* עברה את הסף *${COST_HOURLY_LIMIT:.2f}*\n"
            f"AI פועל כרגיל — אם הדפוס ממשיך ייעצר ביום."
        )
    except Exception as e:
        logger.error(f"[CostWatchdog] _send_hourly_alert error: {e}")


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


def get_stats() -> dict:
    """מחזיר נתוני עלות נוכחיים — לאבחון ו-/status."""
    with _lock:
        return {
            "enabled":          is_enabled("COST_WATCHDOG_LIVE"),
            "hourly_cost_usd":  round(_hourly_cost, 4),
            "hourly_calls":     _hourly_calls,
            "hourly_limit_usd": COST_HOURLY_LIMIT,
            "hourly_alerted":   _hourly_alerted,
            "daily_cost_usd":   round(_daily_cost, 4),
            "daily_calls":      _daily_calls,
            "daily_limit_usd":  COST_DAILY_LIMIT,
            "daily_date":       str(_daily_date),
            "daily_stopped":    _daily_stopped,
        }


def job_cost_watchdog() -> None:
    """Scheduler job — כל 60 דקות."""
    check_thresholds()
