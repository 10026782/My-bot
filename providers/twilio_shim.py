# providers/twilio_shim.py
# F13 — TwilioChannelAdapter shim
# עוטף את core/output_gateway.py ללא שינויו.
#
# הערה (SPEC-001): send_via_cog לא קיים — נקודת הכניסה האמיתית היא
# send_outbound(OutboundEnvelope). audience מוגדר ל-CUSTOMER (conservative —
# עובר Financial Gate) כי לאדפטר אין דרך לדעת אם הנמען הוא owner פנימי.
# validate_inbound לא יכול לעטוף את _validate_twilio_signature() הקיים —
# הפונקציה הזו קוראת את Flask request global בלי פרמטרים, ולא מקבלת
# (headers, body). stub כן מצהיר NotImplementedError במקום להחזיר True
# ולהעמיד פנים שיש אימות חתימה.

from __future__ import annotations
from typing import Any

from core.output_gateway import (
    send_outbound, OutboundEnvelope, AudienceClass, OutputChannel,
)


class TwilioChannelAdapter:
    def send(self, to: str, message: str,
              media_url: str | None = None) -> dict[str, Any]:
        envelope = OutboundEnvelope(
            channel=OutputChannel.TWILIO_WHATSAPP,
            recipient=to,
            body=message,
            audience=AudienceClass.CUSTOMER,
            source_module="twilio_shim",
            source_ref="F13",
            domain="boss_hq",
            meta={"media_url": media_url} if media_url else {},
        )
        result = send_outbound(envelope)
        return {
            "status":     result.status,
            "audit_id":   result.audit_id,
            "escalated":  result.escalated,
            "block_reason": result.block_reason,
        }

    def parse_inbound(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        sender = raw_payload.get("From", "whatsapp:unknown").removeprefix("whatsapp:")
        return {
            "sender":    sender,
            "to":        raw_payload.get("To", "whatsapp:unknown").removeprefix("whatsapp:"),
            "body":      raw_payload.get("Body", "").strip(),
            "media_url": raw_payload.get("MediaUrl0"),
        }

    def validate_inbound(self, request_headers: dict[str, str],
                         request_body: bytes) -> bool:
        raise NotImplementedError(
            "app.py._validate_twilio_signature() takes no params and reads Flask's "
            "request global directly — it cannot be wrapped behind a (headers, body) "
            "signature without changing the existing function (SPEC-001)."
        )
