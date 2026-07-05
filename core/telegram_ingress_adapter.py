# core/telegram_ingress_adapter.py — C94 Stage ג: Telegram ingress adapter
#
# "Telegram is an INGRESS SOURCE ADAPTER only" — same principle as C90's file
# adapter (core/file_ingress_adapter.py). This module's ONLY C94 responsibility
# is turning one already-received Telegram text message into a valid
# IngressEnvelope, before it enters classify_ingress()/the router. It does not
# call classify_ingress() itself, does not know about tiers/ActionGateway, and
# never touches EvidenceTrace (that's a byproduct built downstream — see
# core/router/capture_router.py).

from __future__ import annotations

from core.ingress_envelope import IngressEnvelope

# channel this adapter's messages arrive on → provider. Telegram today only
# has one provider (Bot API) — extend this mapping if that ever changes,
# rather than hardcoding provider inline at the call site.
_CHANNEL_TO_PROVIDER = {
    "telegram": "telegram_bot_api",
}


def build_telegram_envelope(*, identity, raw_event_id: str, text: str) -> IngressEnvelope:
    """
    בונה IngressEnvelope להודעת טקסט בודדת מ-Telegram, לפני כל כניסה ל-
    classify_ingress()/Router. provider נגזר מ-_CHANNEL_TO_PROVIDER (לא
    hardcoded inline) — כמו ב-file adapter. source_ref (לא raw_ref — ראה
    C94-A.1) הוא מצביע קבוע-מראש ("telegram:msg:<raw_event_id>"), זמין תמיד
    לפני סיווג — raw_ref עצמו ממשיך להיווצר רק בתוך classify_ingress/
    _save_raw_capture, בדיוק כמו היום. envelope_id מזוהה אוטומטית (uuid)
    על ידי IngressEnvelope עצמו.
    """
    return IngressEnvelope(
        source_channel="telegram",
        provider=_CHANNEL_TO_PROVIDER["telegram"],
        raw_event_id=raw_event_id,
        sender_identity=identity.memory_key,
        normalized_text=text,
        attachments=(),
        source_ref=f"telegram:msg:{raw_event_id}",
    )
