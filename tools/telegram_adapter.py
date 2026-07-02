# tools/telegram_adapter.py — C52 Customer Output Gateway Send Adapter
#
# TELEGRAM_OWNER הוא ערוץ INTERNAL בלבד (ראה core/output_gateway._ALWAYS_INTERNAL_CHANNELS).
# שולח ישירות ל-Telegram Bot API — אותו pattern כמו core.output_gateway._notify_owner_escalation.

import logging
import os

import httpx

from core.action_result import ActionResult, ClaimType

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


def send_telegram(chat_id: str, text: str) -> ActionResult:
    """Send to the owner and return explicit delivery evidence."""
    _assert_gateway_context()   # ← Secondary Guard
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        logger.warning("[TelegramAdapter] TELEGRAM_TOKEN missing — send skipped")
        return ActionResult.failure(
            "TELEGRAM_TOKEN missing — send skipped",
            source="telegram_adapter",
        )

    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
        payload = response.json()
        delivered = bool(response.is_success and payload.get("ok") is True)
        error = "" if delivered else str(payload.get("description", "Telegram send failed"))
        return ActionResult(
            tool_called=True,
            tool_http_ok=response.is_success,
            business_success=delivered,
            delivery_attempted=True,
            delivery_success=delivered,
            adapter_mode="live",
            claim_type=ClaimType.SENT,
            error=error,
            source="telegram_adapter",
        )
    except Exception as exc:
        logger.error("[TelegramAdapter] send failed: %s", exc)
        return ActionResult(
            tool_called=True,
            delivery_attempted=True,
            delivery_success=False,
            adapter_mode="live",
            claim_type=ClaimType.SENT,
            fatal_error=str(exc),
            source="telegram_adapter",
        )
