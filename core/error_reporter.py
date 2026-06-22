# core/error_reporter.py — N09
#
# התראת Telegram על שגיאות בפרודקשן בלבד (RENDER=="true").
# לא מדבר עם app/telebot/dispatcher/context/identity/crm/airtable_gateway —
# מודול עזר טהור, נטו requests.post ישיר ל-Telegram Bot API.
#
# אסור לכלול payload/תוכן הודעות/מידע לקוח: context הוא שם הפונקציה בלבד,
# error message מוגבל ל-150 תווים, וה-traceback הוא format_exc() גולמי
# (לא format_exception עם locals) — מקוצר ל-600 תווים אחרונים, אחרי הסרת
# שורות שעלולות לכלול PII (phone/שם/name/digits ארוכים).

import os
import re
import logging
import traceback
from datetime import datetime

import requests

from feature_flags import ERROR_REPORTING

logger = logging.getLogger(__name__)

_RATE_LIMIT_PER_HOUR = 10
_sent_timestamps: list[float] = []

# שורות traceback שעלולות לכלול PII (טלפון/שם משתנה) — מוסרות לפני שליחה.
_PII_LINE_RE = re.compile(r"phone|שם|name|\d{6,}", re.IGNORECASE)


def _sanitize_traceback(tb: str) -> str:
    lines = [ln for ln in tb.splitlines() if not _PII_LINE_RE.search(ln)]
    return "\n".join(lines)[-600:]


def _is_enabled() -> bool:
    if os.environ.get("RENDER") != "true":
        return False
    return ERROR_REPORTING.strip().lower() in ("1", "true", "yes", "on", "enabled")


def _rate_limit_ok() -> bool:
    now = datetime.now().timestamp()
    cutoff = now - 3600
    while _sent_timestamps and _sent_timestamps[0] < cutoff:
        _sent_timestamps.pop(0)
    if len(_sent_timestamps) >= _RATE_LIMIT_PER_HOUR:
        return False
    _sent_timestamps.append(now)
    return True


def report_error(error: Exception, context: str = "", level: str = "ERROR") -> None:
    """שולח התראת Telegram על שגיאת פרודקשן. לעולם לא קורס — כשל שליחה → logger.error בלבד."""
    if not _is_enabled():
        return

    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("ELIYAHU_CHAT_ID", "")
    if not token or not chat_id:
        logger.error("[error_reporter] TELEGRAM_TOKEN/ELIYAHU_CHAT_ID missing — cannot send alert")
        return

    if not _rate_limit_ok():
        logger.error(f"[error_reporter] rate limit ({_RATE_LIMIT_PER_HOUR}/h) — alert dropped, context={context}")
        return

    error_str = str(error)[:150]
    tb = _sanitize_traceback(traceback.format_exc())
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    text = (
        f"🚨 שגיאה בפרודקשן\n"
        f"context: {context}\n"
        f"{type(error).__name__}: {error_str}\n"
        f"traceback: {tb}\n"
        f"time: {now_str}"
    )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )
        response.raise_for_status()
    except Exception as e:
        logger.error(f"[error_reporter] failed to send Telegram alert: {e}")
