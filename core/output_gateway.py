from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Thread-local context — Secondary Guard ───────────────────────────────────
_gateway_context = threading.local()


class AudienceClass(str, Enum):
    INTERNAL = "INTERNAL"   # owner בלבד — עובר ישיר, ללא Financial Gate
    CUSTOMER = "CUSTOMER"   # חייב לעבור Financial Gate


class OutputChannel(str, Enum):
    TWILIO_WHATSAPP = "twilio_whatsapp"
    META_WHATSAPP   = "meta_whatsapp"    # עתידי — חייב לעבור Gateway
    EMAIL           = "email"            # עתידי — חייב לעבור Gateway
    SMS             = "sms"              # עתידי — חייב לעבור Gateway
    TELEGRAM_OWNER  = "telegram_owner"   # תמיד INTERNAL


# ערוצים שמסווגים אוטומטית כ-INTERNAL ללא קשר ל-audience field
_ALWAYS_INTERNAL_CHANNELS = frozenset({OutputChannel.TELEGRAM_OWNER})

# ערוצים שיכולים להגיע ללקוח — חייבים לעבור Financial Gate
_CUSTOMER_CAPABLE_CHANNELS = frozenset({
    OutputChannel.TWILIO_WHATSAPP,
    OutputChannel.META_WHATSAPP,
    OutputChannel.EMAIL,
    OutputChannel.SMS,
})


@dataclass
class OutboundEnvelope:
    channel:        OutputChannel
    recipient:      str            # מספר טלפון / כתובת email
    body:           str            # גוף ההודעה
    audience:       AudienceClass  # INTERNAL או CUSTOMER
    source_module:  str            # מי שולח — לאודיט ("followup_engine", "scheduler", ...)
    source_ref:     str            # lead_id / action_id / job_name
    domain:         str            # "real_estate" / "import" / "recruitment"
    draft:          bool = False   # draft = treated as CUSTOMER even if not sent yet
    meta: dict      = field(default_factory=dict)  # source_type, approved_by, וכו'


@dataclass
class GatewayResult:
    status:        str            # "APPROVED" | "ESCALATED" | "INTERNAL_PASS" | "EMERGENCY_STOP"
    audit_id:      str = ""
    escalated:     bool = False
    fallback_sent: bool = False
    block_reason:  str = ""
    shadow_log:    bool = False

    @classmethod
    def approved(cls, audit_id: str) -> "GatewayResult":
        return cls(status="APPROVED", audit_id=audit_id)

    @classmethod
    def internal_pass(cls, audit_id: str) -> "GatewayResult":
        return cls(status="INTERNAL_PASS", audit_id=audit_id)

    @classmethod
    def escalated_result(cls, audit_id: str, fallback_sent: bool, reason: str) -> "GatewayResult":
        return cls(
            status="ESCALATED",
            audit_id=audit_id,
            escalated=True,
            fallback_sent=fallback_sent,
            block_reason=reason,
        )

    @classmethod
    def emergency_stop(cls, channel: str) -> "GatewayResult":
        return cls(status="EMERGENCY_STOP", block_reason=f"EMERGENCY_STOP active: {channel}")


def send_outbound(envelope: OutboundEnvelope) -> GatewayResult:
    """
    נקודת הכניסה היחידה לכל שליחה ללקוח.

    כלל ברזל: אין לקרוא ל-Send Adapter ישירות מחוץ לפונקציה זו.
    כל ערוץ עתידי חייב להירשם כאן לפני שימוש.
    """
    audit_id = str(uuid.uuid4())[:12]

    # שלב 1 — Emergency Stop (קיים כבר ב-feature_flags, C33)
    if _is_emergency_stopped(envelope.channel):
        logger.warning(
            "[COG] EMERGENCY_STOP active | channel=%s | source=%s | ref=%s",
            envelope.channel, envelope.source_module, envelope.source_ref
        )
        return GatewayResult.emergency_stop(envelope.channel)

    # שלב 2 — Classify: INTERNAL channels עוברים ישיר ללא בדיקה
    effective_audience = _classify_audience(envelope)
    if effective_audience == AudienceClass.INTERNAL:
        _audit_log(audit_id, envelope, "INTERNAL_PASS", reason="")
        return _execute_send(envelope, audit_id, internal=True)

    # שלב 3 — CUSTOMER path → Financial Gate
    from core.financial_gate import check as _fin_check
    fin_result = _fin_check(envelope)

    if fin_result.shadow_only:
        # Shadow mode: לא חוסמים, רק מתעדים
        _audit_log(audit_id, envelope, "APPROVED_SHADOW", reason=fin_result.reason)
        return _execute_send(envelope, audit_id, internal=False)

    if fin_result.escalated:
        return _handle_escalation(envelope, fin_result, audit_id)

    # שלב 4 — Approved, שלח
    _audit_log(audit_id, envelope, "APPROVED", reason="")
    return _execute_send(envelope, audit_id, internal=False)


def _classify_audience(envelope: OutboundEnvelope) -> AudienceClass:
    """TELEGRAM_OWNER תמיד INTERNAL — גם אם בטעות סומן CUSTOMER."""
    if envelope.channel in _ALWAYS_INTERNAL_CHANNELS:
        return AudienceClass.INTERNAL
    return envelope.audience


def _handle_escalation(envelope: OutboundEnvelope, fin_result, audit_id: str) -> GatewayResult:
    """
    ESCALATE — לא BLOCK.
    1. שלח fallback ללקוח ("אחזור אליך")
    2. שלח alert לבעל הבית בטלגרם עם [שלח] [ערוך] [בטל]
    3. כתוב לאודיט
    לא קיימת אפשרות DROP שקטה.
    """
    fallback_sent = False
    _audit_log(audit_id, envelope, "ESCALATED", reason=fin_result.reason)

    # שלח fallback ללקוח — הליד נשאר חי
    fallback_body = "אני מעביר את זה לבדיקה ידנית, ויחזרו אליך עם תשובה מדויקת."
    try:
        _send_fallback_to_customer(envelope, fallback_body)
        fallback_sent = True
    except Exception as e:
        logger.error("[COG] fallback send failed: %s | audit_id=%s", e, audit_id)

    # Alert לבעל הבית
    try:
        _notify_owner_escalation(envelope, fin_result, audit_id)
    except Exception as e:
        logger.error("[COG] owner notify failed: %s | audit_id=%s", e, audit_id)

    return GatewayResult.escalated_result(
        audit_id=audit_id,
        fallback_sent=fallback_sent,
        reason=fin_result.reason,
    )


def _is_emergency_stopped(channel: OutputChannel) -> bool:
    from feature_flags import is_enabled
    if is_enabled("EMERGENCY_STOP_ALL"):
        return True
    channel_flag = {
        OutputChannel.TWILIO_WHATSAPP: "EMERGENCY_STOP_WHATSAPP",
        OutputChannel.META_WHATSAPP:   "EMERGENCY_STOP_WHATSAPP",
        OutputChannel.EMAIL:           "EMERGENCY_STOP_EMAIL",
    }.get(channel)
    return bool(channel_flag and is_enabled(channel_flag))


def _execute_send(envelope: OutboundEnvelope, audit_id: str, internal: bool) -> GatewayResult:
    """מגדיר thread-local context ואז קורא ל-Adapter."""
    _gateway_context.approved = True
    _gateway_context.audit_id = audit_id
    try:
        _dispatch_to_adapter(envelope)
    finally:
        _gateway_context.approved = False
        _gateway_context.audit_id = ""

    if internal:
        return GatewayResult.internal_pass(audit_id)
    return GatewayResult.approved(audit_id)


def _dispatch_to_adapter(envelope: OutboundEnvelope) -> None:
    """
    מנתב לפי ערוץ.
    כל ערוץ עתידי חייב להיות מוסף כאן — אחרת NotImplementedError.
    """
    if envelope.channel == OutputChannel.TWILIO_WHATSAPP:
        from tools.whatsapp_adapter import send_whatsapp
        send_whatsapp(to=envelope.recipient, body=envelope.body)

    elif envelope.channel == OutputChannel.TELEGRAM_OWNER:
        from tools.telegram_adapter import send_telegram
        send_telegram(chat_id=envelope.recipient, text=envelope.body)

    elif envelope.channel in (OutputChannel.META_WHATSAPP, OutputChannel.EMAIL, OutputChannel.SMS):
        raise NotImplementedError(
            f"[COG] Channel {envelope.channel} not yet wired. "
            "Register adapter here before use."
        )
    else:
        raise ValueError(f"[COG] Unknown channel: {envelope.channel}")


def _audit_log(audit_id: str, envelope: OutboundEnvelope, event: str, reason: str) -> None:
    recipient_hash = hashlib.sha256(envelope.recipient.encode()).hexdigest()[:12]
    body_preview   = envelope.body[:25].replace("\n", " ") + "..."
    logger.info(
        "[COG] %s | audit=%s | channel=%s | recipient_hash=%s | "
        "source=%s | ref=%s | domain=%s | draft=%s | reason=%s | preview=%s",
        event, audit_id, envelope.channel, recipient_hash,
        envelope.source_module, envelope.source_ref, envelope.domain,
        envelope.draft, reason, body_preview,
    )


def _send_fallback_to_customer(envelope: OutboundEnvelope, body: str) -> None:
    """שולח fallback — אותו ערוץ, אותו recipient, גוף קבוע."""
    fallback = OutboundEnvelope(
        channel=envelope.channel,
        recipient=envelope.recipient,
        body=body,
        audience=AudienceClass.CUSTOMER,
        source_module="output_gateway.fallback",
        source_ref=envelope.source_ref,
        domain=envelope.domain,
        meta={"is_fallback": True},
    )
    # שולחים ישיר ל-Adapter — fallback לא עובר Financial Gate שנית
    _gateway_context.approved = True
    try:
        _dispatch_to_adapter(fallback)
    finally:
        _gateway_context.approved = False


def _notify_owner_escalation(envelope: OutboundEnvelope, fin_result, audit_id: str) -> None:
    """
    Alert לבעל הבית בטלגרם.
    מציג: preview של הגוף + הסיבה לescalation + [שלח] [ערוך] [בטל]
    """
    import os
    import httpx

    owner_chat_id = os.environ.get("ELIYAHU_CHAT_ID", "")
    token         = os.environ.get("TELEGRAM_TOKEN", "")
    if not owner_chat_id or not token:
        logger.warning("[COG] owner notify skipped — ELIYAHU_CHAT_ID or TELEGRAM_TOKEN missing")
        return

    preview = envelope.body[:80].replace("\n", " ")
    text = (
        f"⚠️ *הודעה ממתינה לאישורך* (audit: `{audit_id}`)\n\n"
        f"*ערוץ:* {envelope.channel}\n"
        f"*מקור:* {envelope.source_module} / {envelope.source_ref}\n"
        f"*סיבה לעצירה:* {fin_result.reason}\n\n"
        f"*תצוגה מקדימה:*\n`{preview}...`\n\n"
        f"השב: *שלח*, *ערוך*, או *בטל*"
    )
    httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": owner_chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=5,
    )
