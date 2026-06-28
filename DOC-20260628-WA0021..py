# tools/whatsapp_adapter.py — C52 Customer Output Gateway Send Adapter
#
# Honest stub (ראה C38: "לא מעמיד פנים — מחזיר stub כך"): שונה משליחת Twilio REST
# מיוזמת מחוץ ל-TwiML reply הסינכרוני בתוך webhook הוואטסאפ.
# הפונקציה הזו קיימת כדי ש-Gateway יוכל לנתב TWILIO_WHATSAPP בלי NotImplementedError,
# ומוכנה לחיווט Twilio REST client אמיתי כשהיוצרה הזו תופעל בפועל.
#
# CXX — Action Integrity:
# send_whatsapp מחזיר ActionResult במקום None.
# adapter_mode = "stub" | "live"
# delivery_success = True רק כשנשלח בפועל — stub לא מציג delivery_success=True.

import hashlib
import logging
import os

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
            logger.error("[SecondaryGuard] bypass detected — staging mode, not raising")


def send_whatsapp(to: str, body: str):
    """
    שלח הודעת WhatsApp.

    מחזיר ActionResult עם:
      adapter_mode    = "stub" | "live"
      delivery_attempted = True תמיד
      delivery_success   = True רק כששליחה אמיתית הצליחה

    ClaimGate יחסום claim "נשלח" כשadapter_mode="stub".
    """
    # import כאן כדי לא לשבור אם core עדיין לא קיים
    try:
        from core.action_result import ActionResult, ClaimType
        _has_ar = True
    except ImportError:
        _has_ar = False

    _assert_gateway_context()  # ← Secondary Guard

    recipient_hash = hashlib.sha256(to.encode()).hexdigest()[:12]

    # ── Live send (עתידי — Twilio REST) ────────────────
    twilio_sid    = os.environ.get("TWILIO_ACCOUNT_SID", "")
    twilio_token  = os.environ.get("TWILIO_AUTH_TOKEN", "")
    twilio_from   = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
    live_mode     = bool(twilio_sid and twilio_token and twilio_from
                         and os.environ.get("WHATSAPP_LIVE_SEND") == "true")

    if live_mode:
        try:
            from twilio.rest import Client as TwilioClient
            client = TwilioClient(twilio_sid, twilio_token)
            msg = client.messages.create(
                from_=f"whatsapp:{twilio_from}",
                to=f"whatsapp:{to}",
                body=body,
            )
            logger.info(
                "[WhatsAppAdapter] LIVE sent | recipient_hash=%s sid=%s len=%d",
                recipient_hash, msg.sid, len(body),
            )
            if not _has_ar:
                return
            return ActionResult(
                tool_called        = True,
                tool_http_ok       = True,
                business_success   = True,
                delivery_attempted = True,
                delivery_success   = True,
                adapter_mode       = "live",
                claim_type         = ClaimType.SENT,
                source             = "whatsapp_adapter",
            )
        except Exception as e:
            logger.error("[WhatsAppAdapter] LIVE send failed: %s", e)
            if not _has_ar:
                return
            return ActionResult(
                tool_called        = True,
                tool_http_ok       = False,
                business_success   = False,
                delivery_attempted = True,
                delivery_success   = False,
                adapter_mode       = "live",
                claim_type         = ClaimType.SENT,
                fatal_error        = str(e),
                source             = "whatsapp_adapter",
            )

    # ── Stub mode (כברירת מחדל — TwiML reply מטפל בשליחה) ─────────────
    logger.info(
        "[WhatsAppAdapter] honest stub — not sent | recipient_hash=%s len=%d",
        recipient_hash, len(body),
    )
    if not _has_ar:
        return
    return ActionResult(
        tool_called        = True,
        tool_http_ok       = True,   # הcall עצמו עבר — stub לא שגיאה
        business_success   = False,  # לא נשלח בפועל
        delivery_attempted = True,
        delivery_success   = False,  # CXX: stub ≠ delivery_success
        adapter_mode       = "stub",
        claim_type         = ClaimType.SENT,
        source             = "whatsapp_adapter",
    )
