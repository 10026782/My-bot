# media_handler.py — F16 Media Layer: orchestration
#
# Entry points called directly from app.py (Telegram) and tma_api.py (TMA
# upload route) — not registered as agent tools, no dispatcher/registry
# wiring (matches cmd_update.py's pattern for direct, non-agent actions).
#
# Photo/document pipeline (handle_file_upload / handle_tma_upload): classify
# size -> Drive upload -> Airtable metadata. Unchanged.
#
# Voice pipeline (handle_voice_note, F16 voice-logic rewrite): transcribe
# always -> detect action prefix -> no action: log to daily memory for
# review; action + short + no risk word: save to Business Memory directly;
# action + long OR risk word: owner approval gate (✅ שמור / ✏️ ערוך / ❌ בטל)
# before saving. No Drive, no Media Files record, for voice.

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from guards import idempotency as _idem_store
from media_gateway import AssetRecord, save_asset
import drive_adapter
from voice_stt_adapter import transcribe

logger = logging.getLogger(__name__)

TIER_NORMAL = 10 * 1024 * 1024
TIER_LARGE = 50 * 1024 * 1024

_MEMORY_KEYWORDS = (
    "פגישה", "סיכמנו", "החלטנו", "הלקוח אמר", "חשוב",
    "לזכור", "הסכמנו", "התחייבנו", "עסקה", "מחיר סופי",
)

# ── Voice action-prefix detection ───────────────────────────────────
# PREFIX_HARD בלבד — prefix מפורש בתחילת התמלול (אחרי נרמול) מפעיל routing.
# פעלי פעולה רכים ("תזכיר"/"תפתח"/"תשלח"/"תקבע") לא מפעילים Business Memory.
PREFIX_HARD = ("משימה:", "ליד:", "זיכרון:", "רעיון:", "עסקה:")  # exact startswith
RISK_WORDS = (
    "כסף", "חוזה", "התחייבות", "מחיקה", "שינוי סטטוס", "שלח ללקוח",
)
SHORT_TRANSCRIPT_WORD_LIMIT = 30


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
    message: str = ""
    error: MediaError | None = None


def _classify_size(size_bytes: int) -> str:
    if size_bytes > TIER_LARGE:
        return "oversized"
    if size_bytes > TIER_NORMAL:
        return "large"
    return "normal"


def _should_save_to_memory(text: str) -> bool:
    return any(kw in text for kw in _MEMORY_KEYWORDS)


_BIDI_CONTROL_CHARS = "".join(
    chr(c) for c in (0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E)
)


def _normalize_for_prefix(text: str) -> str:
    """מנרמל תמלול לפני זיהוי prefix."""
    import re
    text = re.sub(f"[{_BIDI_CONTROL_CHARS}]", "", text)
    PREFIX_WORDS = ["זיכרון", "משימה", "ליד", "רעיון", "עסקה"]
    for word in PREFIX_WORDS:
        text = re.sub(rf'^{word}[,،.。:\s]\s*', f'{word}: ', text)
    return text.strip()


def _has_action(transcript: str) -> bool:
    """רק PREFIX_HARD בתחילת התמלול (אחרי נרמול) מפעיל פעולה."""
    normalized = _normalize_for_prefix(transcript)
    return any(normalized.startswith(p) for p in PREFIX_HARD)


def _has_risk_words(transcript: str) -> bool:
    return any(w in transcript for w in RISK_WORDS)


def _idem_key(source: str, file_id: str, user_id: str) -> str:
    return hashlib.sha256(f"{source}:{file_id}:{user_id}".encode("utf-8")).hexdigest()[:16]


def _resolve_drive_folder(domain: str) -> tuple[str | None, MediaError | None]:
    """Resolves the domain/month Drive folder. drive_adapter.upload_file()
    requires parent_folder_id explicitly (no default) — caller always
    resolves it first via _get_upload_folder()."""
    parent_folder_id = drive_adapter._get_upload_folder(domain)
    if not parent_folder_id:
        return None, MediaError(
            "DRIVE_FAILED", "לא ניתן לגשת לתיקיית Drive (אימות Google חסר או שגיאת תיקייה).", True
        )
    return parent_folder_id, None


def _format_media_result(result: MediaResult) -> str:
    if result.message:
        return result.message
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
# Business Memory save + approval gate (voice)
# ══════════════════════════════════════════════════════════════════

def _save_transcript_to_memory(transcript: str, domain: str, source: str) -> bool:
    """Writes a voice transcript to Business Memory via the Airtable gateway."""
    from tools.airtable_gateway import airtable_create
    from airtable_schema import Tables, BusinessMemoryFields as BMF

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
        return True
    logger.warning("[media_handler] failed to save transcript to Business Memory")
    return False


def _handle_memory_confirmed(payload: dict, chat_id: str) -> str:
    """Subscribed to media_save_to_memory.confirmed — fires after the owner taps ✅ שמור."""
    transcript = payload.get("transcript", "")
    domain = payload.get("domain", "general")
    source = payload.get("source", "media_handler")
    saved = _save_transcript_to_memory(transcript, domain, source)
    return "✅ נשמר ב-Business Memory" if saved else "❌ שמירה ל-Business Memory נכשלה"


def _register_subscriptions() -> None:
    from event_bus import bus

    bus.subscribe("media_save_to_memory.confirmed", _handle_memory_confirmed)


_register_subscriptions()


# Owner chat_id -> {"domain": ..., "source": ...} while awaiting a follow-up
# text message after tapping ✏️ ערוך.
_pending_voice_edits: dict[str, dict] = {}
_voice_callbacks_registered = False


def _register_voice_callbacks(bot) -> None:
    """Registers the ✏️ ערוך callback + follow-up text capture on the live bot instance.
    Idempotent — safe to call on every approval request."""
    global _voice_callbacks_registered
    if _voice_callbacks_registered:
        return

    @bot.callback_query_handler(func=lambda c: (c.data or "").startswith("voice_edit:"))
    def _cb_voice_edit(call):
        from event_bus import bus

        action_id = call.data.split(":", 1)[1]
        item = bus.pop(action_id)
        if not item:
            bot.answer_callback_query(call.id, "⏰ פג תוקף — ההקלטה לא קיימת יותר.")
            return

        owner_id = str(call.from_user.id)
        _pending_voice_edits[owner_id] = {
            "domain": item["payload"].get("domain", "general"),
            "source": item["payload"].get("source", "media_handler"),
        }
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, "✍️ שלח את הטקסט המעודכן לשמירה בזיכרון:")
        bot.answer_callback_query(call.id)

    @bot.message_handler(
        func=lambda m: (
            str(getattr(m.from_user, "id", "")) in _pending_voice_edits
            and bool(getattr(m, "text", None))
            and not m.text.startswith("/")
        )
    )
    def _capture_voice_edit(msg):
        owner_id = str(msg.from_user.id)
        state = _pending_voice_edits.pop(owner_id, None)
        if not state:
            return
        saved = _save_transcript_to_memory(msg.text, state["domain"], state["source"])
        bot.send_message(
            msg.chat.id,
            f"🧠 נשמר בזיכרון:\n{msg.text}" if saved else "❌ שמירה ל-Business Memory נכשלה",
        )

    _voice_callbacks_registered = True


def _send_voice_approval_request(
    transcript: str, domain: str, source: str, owner_chat_id: str, reason: str,
) -> str:
    """Queues an owner-approval request and sends the ✅ שמור / ✏️ ערוך / ❌ בטל buttons.
    Approve/reject are handled by app.py's existing generic approval-callback routing
    (callback_data prefixes "approve:"/"reject:"); ✏️ ערוך is registered here."""
    from event_bus import bus

    action_id, _ = bus.request_approval(
        action="media_save_to_memory",
        payload={"transcript": transcript, "domain": domain, "source": source},
        chat_id=owner_chat_id,
        label=f"🧠 שמירה ב-Business Memory ({reason}): {transcript[:60]}",
    )

    if not owner_chat_id:
        return "⚠️ לא הוגדר chat owner — האישור נשמר אך לא נשלחה הודעה."

    try:
        import telebot
        from app import bot

        _register_voice_callbacks(bot)
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(
            telebot.types.InlineKeyboardButton("✅ שמור", callback_data=f"approve:{action_id}"),
            telebot.types.InlineKeyboardButton("✏️ ערוך", callback_data=f"voice_edit:{action_id}"),
            telebot.types.InlineKeyboardButton("❌ בטל", callback_data=f"reject:{action_id}"),
        )
        bot.send_message(
            owner_chat_id,
            f"🎙️ *תמלול הודעה קולית* ({reason})\n\n{transcript[:500]}",
            reply_markup=kb,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("[media_handler] failed to send voice approval buttons: %s", e)
        return "⚠️ התמלול הושלם אך לא ניתן היה לשלוח בקשת אישור."

    return "📨 התמלול ממתין לאישורך למעלה ⬆️"


def _log_unhandled_voice_note(transcript: str, user_id: str, source: str) -> None:
    """No action detected — log into the day's memory so daily_collector can flag it for review."""
    try:
        from identity import resolve_identity
        from memory_store import memory

        identity = resolve_identity(source, user_id)
        memory.add(identity.memory_key, "user", f"[הודעה קולית, ללא פעולה]: {transcript}", channel=source)
    except Exception as e:
        logger.warning("[media_handler] failed to log unhandled voice note: %s", e)


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
) -> MediaResult:
    """Voice-note pipeline: transcribe always -> detect action prefix -> route.
    No Drive, no Media Files record — see module header for the full decision tree."""
    size_bytes = len(audio_bytes)
    if _classify_size(size_bytes) == "oversized":
        return MediaResult(
            ok=False,
            file_size_tier="oversized",
            error=MediaError("FILE_TOO_LARGE", "הקובץ גדול מ-50MB. הגודל המרבי הוא 50MB.", False),
        )

    idem_key = _idem_key(source, telegram_file_id, user_id)
    if _idem_store.is_duplicate("media", idem_key, ""):
        return MediaResult(
            ok=False,
            error=MediaError("DUPLICATE", "הקובץ הזה כבר התקבל.", False),
        )

    stt_result = transcribe(audio_bytes, mime_type)
    if not stt_result.ok:
        return MediaResult(
            ok=False,
            error=MediaError(stt_result.error.error_code, stt_result.error.error_message, stt_result.error.retryable),
        )

    raw_transcript = stt_result.raw_transcript
    transcript = stt_result.normalized_transcript

    normalized_for_prefix = _normalize_for_prefix(transcript)
    action_requested = _has_action(transcript)
    logger.info(f"[voice] transcript repr: {repr(transcript[:50])}")
    logger.info(f"[voice] normalized for prefix: {repr(normalized_for_prefix[:50])}")
    logger.info(f"[voice] action_requested: {action_requested}")
    logger.info(f"[voice] PREFIX_HARD matches: {[p for p in PREFIX_HARD if normalized_for_prefix.startswith(p)]}")

    # אישור חובה תמיד עבור מילות סיכון, ללא קשר לאיתור action_requested או לאורך הטקסט.
    if _has_risk_words(transcript):
        ack = _send_voice_approval_request(transcript, domain, source, owner_chat_id, reason="מילת סיכון")
        return MediaResult(ok=True, raw_transcript=raw_transcript, normalized_transcript=transcript, message=ack)

    # שלב 3 — אין פעולה: רק תמלול, ללא Drive, ללא זיכרון.
    if not action_requested:
        _log_unhandled_voice_note(transcript, user_id, source)
        return MediaResult(
            ok=True, raw_transcript=raw_transcript, normalized_transcript=transcript,
            message="📝 תומלל. לא בוצעה פעולה.",
        )

    word_count = len(transcript.split())
    if word_count <= SHORT_TRANSCRIPT_WORD_LIMIT:
        saved = _save_transcript_to_memory(transcript, domain, source)
        return MediaResult(
            ok=saved, raw_transcript=raw_transcript, normalized_transcript=transcript, saved_to_memory=saved,
            message=f"🧠 נשמר בזיכרון:\n{transcript}" if saved else "❌ שמירה ל-Business Memory נכשלה",
        )

    ack = _send_voice_approval_request(transcript, domain, source, owner_chat_id, reason="טקסט ארוך")
    return MediaResult(ok=True, raw_transcript=raw_transcript, normalized_transcript=transcript, message=ack)


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
            error=MediaError("FILE_TOO_LARGE", "הקובץ גדול מ-50MB. הגודל המרבי הוא 50MB.", False),
        )

    idem_key = _idem_key(source, file_id, user_id)
    if _idem_store.is_duplicate("media", idem_key, ""):
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError("DUPLICATE", "הקובץ הזה כבר הועלה.", False),
        )

    parent_folder_id, folder_err = _resolve_drive_folder(domain)
    if folder_err:
        return MediaResult(ok=False, file_size_tier=tier, error=folder_err)

    drive_result = drive_adapter.upload_file(file_bytes, filename, mime_type, parent_folder_id)
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
    if not asset_id:
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            drive_url=drive_result.web_url,
            error=MediaError("ASSET_SAVE_FAILED", "הקובץ הועלה ל-Drive אך לא נשמר ב-Airtable.", True),
        )

    return MediaResult(
        ok=True,
        asset_id=asset_id,
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
    linked_lead_id: str = "",
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
        linked_lead_id=linked_lead_id,
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

    # ── Voice-logic coverage (F16 rewrite): transcribe -> prefix/risk detection -> route.
    # No Drive involved for voice anymore — only transcribe()/_save_transcript_to_memory()/
    # _send_voice_approval_request()/_log_unhandled_voice_note() are mocked.
    import sys
    from unittest.mock import patch
    from voice_stt_adapter import TranscriptResult

    _this = sys.modules[__name__]

    def _stt(text: str) -> TranscriptResult:
        return TranscriptResult(raw_transcript=text, normalized_transcript=text, provider_used="openai")

    with patch.object(_this, "transcribe", return_value=_stt("שיחה רגילה בלי שום הוראה")), \
         patch.object(_this, "_log_unhandled_voice_note") as mock_log:
        no_action = handle_voice_note(
            audio_bytes=b"audio-bytes", mime_type="audio/ogg", telegram_file_id="v1",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert no_action.ok and no_action.message == "📝 תומלל. לא בוצעה פעולה."
        mock_log.assert_called_once()
    print("✅ no action prefix → transcript only, logged for review, no memory/approval")

    with patch.object(_this, "transcribe", return_value=_stt("משימה: להתקשר ללקוח מחר")), \
         patch.object(_this, "_save_transcript_to_memory", return_value=True) as mock_save:
        short_action = handle_voice_note(
            audio_bytes=b"audio-bytes", mime_type="audio/ogg", telegram_file_id="v2",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert short_action.ok and short_action.saved_to_memory
        assert "נשמר בזיכרון" in short_action.message
        mock_save.assert_called_once_with("משימה: להתקשר ללקוח מחר", "general", "telegram")
    print("✅ hard prefix + ≤30 words, no risk word → saved to Business Memory directly")

    with patch.object(_this, "transcribe", return_value=_stt("תשלח לו את החוזה החדש")), \
         patch.object(_this, "_send_voice_approval_request", return_value="📨 ack") as mock_approve, \
         patch.object(_this, "_save_transcript_to_memory") as mock_save:
        risky = handle_voice_note(
            audio_bytes=b"audio-bytes", mime_type="audio/ogg", telegram_file_id="v3",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert risky.ok and risky.message == "📨 ack"
        mock_approve.assert_called_once_with("תשלח לו את החוזה החדש", "general", "telegram", "123", reason="מילת סיכון")
        assert not mock_save.called
    print("✅ risk word present → approval gate even for short text, no direct save")

    long_text = "משימה: " + " ".join(["דבר"] * 35)
    with patch.object(_this, "transcribe", return_value=_stt(long_text)), \
         patch.object(_this, "_send_voice_approval_request", return_value="📨 ack") as mock_approve, \
         patch.object(_this, "_save_transcript_to_memory") as mock_save:
        long_action = handle_voice_note(
            audio_bytes=b"audio-bytes", mime_type="audio/ogg", telegram_file_id="v4",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert long_action.ok and long_action.message == "📨 ack"
        mock_approve.assert_called_once_with(long_text, "general", "telegram", "123", reason="טקסט ארוך")
        assert not mock_save.called
    print("✅ action + >30 words, no risk word → approval gate (preview), no direct save")

    # PREFIX_HARD בלבד — פעלי פעולה רכים ("תזכיר"/"תפתח"/"תשלח"/"תקבע") לא מפעילים
    # action_requested בהיעדר prefix מפורש וללא מילת סיכון.
    with patch.object(_this, "transcribe", return_value=_stt("תזכיר לי לקבוע פגישה מחר")), \
         patch.object(_this, "_log_unhandled_voice_note") as mock_log, \
         patch.object(_this, "_save_transcript_to_memory") as mock_save, \
         patch.object(_this, "_send_voice_approval_request") as mock_approve:
        soft_verb_only = handle_voice_note(
            audio_bytes=b"audio-bytes", mime_type="audio/ogg", telegram_file_id="v5",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert soft_verb_only.ok and soft_verb_only.message == "📝 תומלל. לא בוצעה פעולה."
        mock_log.assert_called_once()
        assert not mock_save.called and not mock_approve.called
    print("✅ soft verb alone (no PREFIX_HARD, no risk word) → no action, not saved to memory")

    chk_comma = _has_action("זיכרון, לקבוע פגישה עם הלקוח")
    assert chk_comma is True
    print("✅ comma-normalized prefix (\"זיכרון, ...\") → still recognized as PREFIX_HARD")

    with patch.object(drive_adapter, "_get_upload_folder", return_value=None):
        no_folder = handle_file_upload(
            file_bytes=b"x" * 1024,
            filename="x.pdf",
            mime_type="application/pdf",
            file_type="document",
            file_id="f11",
            user_id="u1",
            domain="general",
        )
        assert not no_folder.ok and no_folder.error.error_code == "DRIVE_FAILED"
    print("✅ missing/unresolvable Drive folder → DRIVE_FAILED, no crash")

    with patch.object(drive_adapter, "_get_upload_folder", return_value="folder123"), \
         patch.object(drive_adapter, "upload_file") as mock_upload, \
         patch.object(_this, "save_asset", return_value=None):
        mock_upload.return_value = drive_adapter.DriveFile(
            file_id="f3", web_url="https://drive/x", name="x.pdf", size_bytes=1024
        )
        save_failed = handle_file_upload(
            file_bytes=b"x" * 1024,
            filename="x.pdf",
            mime_type="application/pdf",
            file_type="document",
            file_id="f12",
            user_id="u1",
            domain="general",
        )
        assert not save_failed.ok and save_failed.error.error_code == "ASSET_SAVE_FAILED"
    print("✅ Drive upload succeeds but Airtable save fails → ASSET_SAVE_FAILED (not silently ok=True)")

    print("media_handler.py self-test OK")
