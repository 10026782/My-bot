# tools/telegram_adapter.py — C52 Customer Output Gateway Send Adapter
#
# TELEGRAM_OWNER הוא ערוץ INTERNAL בלבד (ראה core/output_gateway._ALWAYS_INTERNAL_CHANNELS).
# שולח ישירות ל-Telegram Bot API — אותו pattern כמו core.output_gateway._notify_owner_escalation.

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def _assert_gateway_context() -> None:
    """
    מונע שליחה ישירה שעוקפת את ה-Gateway.
    production: AssertionError → crash מוקדם.
    staging:    log בלבד.
    """
    import core.output_gateway as _gw
    approved = getattr(_gw._gateway_context, "approved", False)
    if not approved:
        env = os.environ.get("APP_ENV", "production")
        if env == "production":
            raise AssertionError(
                "BOSS VIOLATION: direct send bypasses Customer Output Gateway. "
                "Use core.output_gateway.send_outbound()."
            )
        else:
            logging.getLogger(__name__).error(
                "[SecondaryGuard] bypass detected — staging mode, not raising"
            )


def send_telegram(chat_id: str, text: str) -> None:
    _assert_gateway_context()   # ← Secondary Guard
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        logger.warning("[TelegramAdapter] TELEGRAM_TOKEN missing — send skipped")
        return
    httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=5,
    )
