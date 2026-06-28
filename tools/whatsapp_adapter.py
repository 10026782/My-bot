# tools/whatsapp_adapter.py — C52 Customer Output Gateway Send Adapter
#
# Honest stub (ראה C38: "לא מעמיד פנים — מחזיר stub כנה"): שום שליחת Twilio REST
# אמיתית לא קיימת עדיין מחוץ ל-TwiML reply הסינכרוני בתוך webhook הוואטסאפ.
# הפונקציה הזו קיימת כדי ש-Gateway יוכל לנתב TWILIO_WHATSAPP בלי NotImplementedError,
# ומוכנה לחיווט Twilio REST client אמיתי כשהיציאה הזו תופעל בפועל.
#
# CXX — Action Integrity: ה-adapter מחזיר ActionResult מפורש. במצב stub אין
# delivery success; ה-TwiML response של ה-webhook הוא שמבצע את התשובה בפועל.

import hashlib
import logging
import os

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


def send_whatsapp(to: str, body: str) -> ActionResult:
    """Record an honest stub attempt without claiming that delivery occurred."""
    _assert_gateway_context()   # ← Secondary Guard
    recipient_hash = hashlib.sha256(to.encode()).hexdigest()[:12]
    logger.info("[WhatsAppAdapter] honest stub — not sent | recipient_hash=%s len=%d",
                recipient_hash, len(body))
    return ActionResult(
        tool_called=True,
        tool_http_ok=True,
        business_success=False,
        delivery_attempted=True,
        delivery_success=False,
        adapter_mode="stub",
        claim_type=ClaimType.SENT,
        source="whatsapp_adapter",
    )
