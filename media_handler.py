# media_handler.py — F16 Media Layer: orchestration
#
# Entry points called directly from app.py (Telegram) and tma_api.py (TMA
# upload route) — not registered as agent tools, no dispatcher/registry
# wiring (matches cmd_update.py's pattern for direct, non-agent actions).
#
# Pipeline: classify size -> Drive upload -> (audio only) STT -> Airtable
# metadata -> optional Business Memory approval for the transcript.

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from guards import idempotency as _idem_store
from media_gateway import AssetRecord, save_asset
from drive_adapter import upload_file
from voice_stt_adapter import transcribe

logger = logging.getLogger(__name__)

TIER_NORMAL = 10 * 1024 * 1024
TIER_LARGE = 50 * 1024 * 1024

_MEMORY_KEYWORDS = (
    "פגישה", "סיכמנו", "החלטנו", "הלקוח אמר", "חשוב",
    "לזכור", "הסכמנו", "התחייבנו", "עסקה", "מחיר סופי",
)


@dataclass
class MediaError:
    error_code: str
    error_message: str
    retryable: bool


@dataclass
class MediaResult:
    ok: bool
    asset_id: str = ""
    drive_url: str = ""
    raw_transcript: str = ""
    normalized_transcript: str = ""
    saved_to_memory: bool = False
    file_size_tier: str = ""
    error: MediaError | None = None


def _classify_size(size_bytes: int) -> str:
    if size_bytes > TIER_LARGE:
        return "oversized"
    if size_bytes > TIER_NORMAL:
        return "large"
    return "normal"


def _should_save_to_memory(text: str) -> bool:
    return any(kw in text for kw in _MEMORY_KEYWORDS)


def _idem_key(source: str, file_id: str, user_id: str) -> str:
    return hashlib.sha256(f"{source}:{file_id}:{user_id}".encode("utf-8")).hexdigest()[:16]


def _format_media_result(result: MediaResult) -> str:
    if not result.ok:
        return f"❌ שגיאה בעיבוד הקובץ: {result.error.error_message}"

    lines = ["✅ הקובץ נשמר"]
    if result.drive_url:
        lines.append(f"🔗 {result.drive_url}")
    if result.normalized_transcript:
        lines.append(f"📝 תמלול: {result.normalized_transcript[:300]}")
    if result.saved_to_memory:
        lines.append("🧠 נשלח לאישור שמירה ב-Business Memory")
    elif result.file_size_tier == "large":
        lines.append("⚠️ קובץ גדול — נשמר בדרייב בלבד, ללא תמלול/ניתוח AI")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# Business Memory approval sub-flow
# ══════════════════════════════════════════════════════════════════

def _request_memory_approval(
    transcript: str,
    domain: str,
    source: str,
    owner_chat_id: str,
) -> tuple[str, str]:
    """Queues an owner-approval request to save a voice transcript to Business Memory."""
    from event_bus import bus

    label = f"🧠 שמירה ב-Business Memory: {transcript[:60]}"
    payload = {
        "action_type": "media_save_to_memory",
        "transcript": transcript,
        "domain": domain,
        "source": source,
    }
    action_id, btn_label = bus.request_approval(
        action="media_save_to_memory",
        payload=payload,
        chat_id=owner_chat_id,
        label=label,
    )
    return action_id, btn_label


def _handle_memory_confirmed(payload: dict, chat_id: str) -> str:
    """Subscribed to media_save_to_memory.confirmed — executes the Business Memory write."""
    from tools.airtable_gateway import airtable_create
    from airtable_schema import Tables, BusinessMemoryFields as BMF

    transcript = payload.get("transcript", "")
    domain = payload.get("domain", "general")
    source = payload.get("source", "media_handler")

    fields = {
        BMF.TITLE: f"הודעה קולית — {datetime.now(ZoneInfo('Asia/Jerusalem')).strftime('%d/%m/%Y')}",
        BMF.DESCRIPTION: transcript,
        BMF.DATE: datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        BMF.EVENT_TYPE: "Other",
        BMF.TAGS: [domain],
        BMF.IMPACT: "Voice Note",
    }
    record = airtable_create(Tables.BUSINESS_MEMORY, fields, source=f"media_handler:{source}")
    if record:
        logger.info("[media_handler] saved transcript to Business Memory id=%s", record.get("id"))
        return "✅ נשמר ב-Business Memory"
    logger.warning("[media_handler] failed to save transcript to Business Memory")
    return "❌ שמירה ל-Business Memory נכשלה"


def _register_subscriptions() -> None:
    from event_bus import bus

    bus.subscribe("media_save_to_memory.confirmed", _handle_memory_confirmed)


_register_subscriptions()


# ══════════════════════════════════════════════════════════════════
# Public entry points
# ══════════════════════════════════════════════════════════════════

def handle_voice_note(
    audio_bytes: bytes,
    mime_type: str,
    telegram_file_id: str,
    user_id: str,
    domain: str,
    owner_chat_id: str,
    source: str = "telegram",
    linked_lead_id: str = "",
) -> MediaResult:
    """Full voice-note pipeline: idempotency -> Drive -> STT -> Airtable -> memory approval."""
    size_bytes = len(audio_bytes)
    tier = _classify_size(size_bytes)
    if tier == "oversized":
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError("FILE_TOO_LARGE", f"{size_bytes} bytes exceeds {TIER_LARGE}", False),
        )

    idem_key = _idem_key(source, telegram_file_id, user_id)
    if _idem_store.is_duplicate("media", idem_key, ""):
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError("DUPLICATE", "this file was already processed", False),
        )

    drive_result = upload_file(audio_bytes, f"{telegram_file_id}.ogg", mime_type, domain=domain)
    if not drive_result.ok:
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError(drive_result.error.error_code, drive_result.error.error_message, drive_result.error.retryable),
        )

    raw_transcript = ""
    normalized_transcript = ""
    if tier == "normal":
        stt_result = transcribe(audio_bytes, mime_type)
        if stt_result.ok:
            raw_transcript = stt_result.raw_transcript
            normalized_transcript = stt_result.normalized_transcript
        else:
            logger.warning("[media_handler] STT failed: %s", stt_result.error.error_message)

    asset = AssetRecord(
        name=drive_result.name,
        file_type="audio",
        mime_type=mime_type,
        drive_url=drive_result.web_url,
        drive_file_id=drive_result.file_id,
        domain=domain,
        source=source,
        size_bytes=size_bytes,
        created_by=user_id,
        telegram_file_id=telegram_file_id,
        linked_lead_id=linked_lead_id,
        raw_transcript=raw_transcript,
        normalized_transcript=normalized_transcript,
    )
    asset_id = save_asset(asset)

    saved_to_memory = False
    if normalized_transcript and _should_save_to_memory(normalized_transcript):
        action_id, _ = _request_memory_approval(normalized_transcript, domain, source, owner_chat_id)
        saved_to_memory = bool(action_id)

    return MediaResult(
        ok=True,
        asset_id=asset_id or "",
        drive_url=drive_result.web_url,
        raw_transcript=raw_transcript,
        normalized_transcript=normalized_transcript,
        saved_to_memory=saved_to_memory,
        file_size_tier=tier,
    )


def handle_file_upload(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    file_type: str,
    file_id: str,
    user_id: str,
    domain: str,
    source: str = "telegram",
    linked_lead_id: str = "",
) -> MediaResult:
    """Photo/document pipeline: idempotency -> Drive -> Airtable. No STT, no memory approval."""
    size_bytes = len(file_bytes)
    tier = _classify_size(size_bytes)
    if tier == "oversized":
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError("FILE_TOO_LARGE", f"{size_bytes} bytes exceeds {TIER_LARGE}", False),
        )

    idem_key = _idem_key(source, file_id, user_id)
    if _idem_store.is_duplicate("media", idem_key, ""):
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError("DUPLICATE", "this file was already processed", False),
        )

    drive_result = upload_file(file_bytes, filename, mime_type, domain=domain)
    if not drive_result.ok:
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError(drive_result.error.error_code, drive_result.error.error_message, drive_result.error.retryable),
        )

    asset = AssetRecord(
        name=drive_result.name,
        file_type=file_type,
        mime_type=mime_type,
        drive_url=drive_result.web_url,
        drive_file_id=drive_result.file_id,
        domain=domain,
        source=source,
        size_bytes=size_bytes,
        created_by=user_id,
        telegram_file_id=file_id,
        linked_lead_id=linked_lead_id,
    )
    asset_id = save_asset(asset)

    return MediaResult(
        ok=True,
        asset_id=asset_id or "",
        drive_url=drive_result.web_url,
        file_size_tier=tier,
    )


def handle_tma_upload(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    user_id: str,
    domain: str,
    source: str = "tma",
) -> MediaResult:
    """TMA upload route entry point — treated as a generic document/image upload."""
    file_type = "image" if mime_type.startswith("image/") else "document"
    file_id = hashlib.sha256(file_bytes[:1024]).hexdigest()[:16]
    return handle_file_upload(
        file_bytes=file_bytes,
        filename=filename,
        mime_type=mime_type,
        file_type=file_type,
        file_id=file_id,
        user_id=user_id,
        domain=domain,
        source=source,
    )


if __name__ == "__main__":
    assert _classify_size(5 * 1024 * 1024) == "normal"
    assert _classify_size(20 * 1024 * 1024) == "large"
    assert _classify_size(60 * 1024 * 1024) == "oversized"

    assert _should_save_to_memory("סיכמנו על המחיר") is True
    assert _should_save_to_memory("שיחה רגילה") is False

    k1 = _idem_key("telegram", "file123", "user1")
    k2 = _idem_key("telegram", "file123", "user1")
    k3 = _idem_key("telegram", "file456", "user1")
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 16

    oversized = handle_voice_note(
        audio_bytes=b"x" * (TIER_LARGE + 1),
        mime_type="audio/ogg",
        telegram_file_id="f1",
        user_id="u1",
        domain="general",
        owner_chat_id="123",
    )
    assert not oversized.ok and oversized.error.error_code == "FILE_TOO_LARGE"

    oversized_file = handle_file_upload(
        file_bytes=b"x" * (TIER_LARGE + 1),
        filename="x.pdf",
        mime_type="application/pdf",
        file_type="document",
        file_id="f2",
        user_id="u1",
        domain="general",
    )
    assert not oversized_file.ok and oversized_file.error.error_code == "FILE_TOO_LARGE"

    ok_text = _format_media_result(MediaResult(ok=True, drive_url="https://x", file_size_tier="normal"))
    assert "✅" in ok_text
    err_text = _format_media_result(MediaResult(ok=False, error=MediaError("X", "boom", False)))
    assert "❌" in err_text

    print("media_handler.py self-test OK")
