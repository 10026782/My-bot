# core/whatsapp_ingress_adapter.py — C94 Stage ד: WhatsApp (Twilio) ingress adapter
#
# "WhatsApp is an INGRESS SOURCE ADAPTER only" — same principle as Telegram's
# (core/telegram_ingress_adapter.py) and the file adapter's. This module's
# ONLY C94 responsibility is turning one already-received WhatsApp text
# message into a valid IngressEnvelope, before it enters
# classify_ingress()/the router. It does not call classify_ingress() itself,
# does not know about tiers/ActionGateway, and never touches EvidenceTrace
# (that's a byproduct built downstream — see core/router/capture_router.py,
# already wired for every channel since C94 Stage ג).
#
# Twilio only. Meta Cloud API stays gated (META_OUTBOUND_ENABLED=false by
# default — inbound is received but run_agent() is skipped, outbound is an
# honest stub) and is NOT wired to an envelope here. This is deliberate, not
# an oversight: BUG-071 (the bug that motivated this whole C91/C94 spec) was
# specifically about WhatsApp media handling silently diverging between
# providers — building a second, Meta-specific envelope path now, before
# Meta is even a live outbound channel, would repeat that exact mistake in
# miniature. When Meta Cloud API becomes real, it reuses the SAME
# source_channel="whatsapp" with provider="meta_cloud_api" (already a valid
# value in core/ingress_envelope.py's PROVIDERS) — no other code changes.

from __future__ import annotations

from core.ingress_envelope import IngressEnvelope

# channel this adapter's messages arrive on → provider. WhatsApp today only
# has Twilio wired to an envelope — extend this mapping (not source_channel)
# if/when Meta Cloud API is approved for its own Stage.
_CHANNEL_TO_PROVIDER = {
    "whatsapp": "twilio_whatsapp",
}


def build_whatsapp_envelope(*, identity, raw_event_id: str, text: str) -> IngressEnvelope:
    """
    בונה IngressEnvelope להודעת טקסט בודדת מ-WhatsApp (Twilio בלבד), לפני כל
    כניסה ל-classify_ingress()/Router. provider נגזר מ-_CHANNEL_TO_PROVIDER
    (לא hardcoded inline) — כמו ב-Telegram/file adapters. raw_event_id הוא
    Twilio's MessageSid. source_ref (לא raw_ref — ראה C94-A.1) הוא מצביע
    קבוע-מראש ("whatsapp:msg:<raw_event_id>"), זמין תמיד לפני סיווג —
    raw_ref עצמו ממשיך להיווצר רק בתוך classify_ingress/_save_raw_capture,
    בדיוק כמו היום. envelope_id מזוהה אוטומטית (uuid) על ידי IngressEnvelope
    עצמו.
    """
    return IngressEnvelope(
        source_channel="whatsapp",
        provider=_CHANNEL_TO_PROVIDER["whatsapp"],
        raw_event_id=raw_event_id,
        sender_identity=identity.memory_key,
        normalized_text=text,
        attachments=(),
        source_ref=f"whatsapp:msg:{raw_event_id}",
    )
