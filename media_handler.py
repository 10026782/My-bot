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
from airtable_schema import MediaPersistenceState
from media_gateway import (
    AssetRecord,
    find_asset_by_logical_media_key,
    save_asset,
    update_asset_persistence,
)
import drive_adapter
from voice_stt_adapter import transcribe
from tma_api import record_fields, record_id

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


@dataclass(frozen=True)
class MediaProcessingStatus:
    """Bounded, non-persistent distinction between provider ACK and processing."""
    status: str  # COMPLETED | FAILED | NOT_COMPLETED
    success_evidence: bool
    error_code: str = ""
    retryable: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "success_evidence": self.success_evidence,
            "error_code": self.error_code,
            "retryable": self.retryable,
        }


def media_processing_status(
    result: MediaResult | None,
    *,
    failure_code: str = "MEDIA_NOT_COMPLETED",
    retryable: bool = True,
) -> MediaProcessingStatus:
    """Convert a local media result into truthful bounded processing state."""
    if result is not None and result.ok:
        return MediaProcessingStatus("COMPLETED", success_evidence=True)
    error = result.error if result is not None else None
    return MediaProcessingStatus(
        "FAILED" if error else "NOT_COMPLETED",
        success_evidence=False,
        error_code=error.error_code if error else failure_code,
        retryable=error.retryable if error else retryable,
    )


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


def logical_media_key(source: str, file_id: str, file_bytes: bytes | None = None) -> str:
    """Return the provider-scoped durable identity used by Media Files/Drive."""
    source = (source or "").lower()
    if source == "tma":
        if file_bytes is None:
            raise ValueError("TMA logical media key requires file bytes")
        return f"tma:sha256:{hashlib.sha256(file_bytes).hexdigest()}"
    namespace = {"telegram": "telegram", "whatsapp": "twilio", "whatsapp_meta": "meta"}.get(source)
    if namespace:
        return f"{namespace}:{file_id}"
    raise ValueError(f"unsupported media source: {source}")


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
        BMF.DATE: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
        BMF.EVENT_TYPE: "Other",
        BMF.IMPACT: "Voice Note",
    }
    from cmd_update import normalize_business_memory_fields
    fields = normalize_business_memory_fields(fields, domain)
    record = airtable_create(Tables.BUSINESS_MEMORY, fields, source=f"media_handler:{source}")
    if record:
        logger.info("[media_handler] saved transcript to Business Memory id=%s", record_id(record))
        return True
    logger.warning("[media_handler] failed to save transcript to Business Memory")
    return False


# שדה "Status" בטבלת Media Files נוסף ידנית ב-Airtable (כמו שאר השדות בטבלה הזו —
# ראה הערת MediaFileFields). אין ניתוב לפי סוג ה-prefix שתאם (משימה/ליד/זיכרון/...) —
# זה F17, לא כאן: כל action_requested נשמר כ-pending גנרי ל-Voice Inbox.
_MEDIA_FILES_STATUS_FIELD = "Status"


def _save_transcript_to_media_files(transcript: str, domain: str, source: str, status: str = "pending") -> bool:
    """שומר תמלול קולי ל-Voice Inbox (טבלת Media Files, סטטוס pending) — בלי ניתוב לפי prefix."""
    from tools.airtable_gateway import airtable_create
    from airtable_schema import Tables, MediaFileFields as MFF

    fields = {
        MFF.NAME: f"הודעה קולית — {datetime.now(ZoneInfo('Asia/Jerusalem')).strftime('%d/%m/%Y')}",
        MFF.FILE_TYPE: "audio",
        MFF.DOMAIN: domain,
        MFF.SOURCE: source,
        MFF.NORMALIZED_TRANSCRIPT: transcript,
        _MEDIA_FILES_STATUS_FIELD: status,
    }
    record = airtable_create(Tables.MEDIA_FILES, fields, source=f"media_handler:{source}")
    if record:
        logger.info("[media_handler] saved transcript to Voice Inbox (Media Files) id=%s status=%s", record_id(record), status)
        return True
    logger.warning("[media_handler] failed to save transcript to Voice Inbox (Media Files)")
    return False


# PR-0C Phase 3: media_save_to_memory.confirmed is no longer subscribed here —
# _send_voice_approval_request() below now queues a tool_name="media_save_to_memory"
# payload, so app.py::_handle_approval_callback_impl's tool_name branch (which
# executes via tools/approval_actions.py::media_save_to_memory, and through
# ActionGateway.approve() when FEATURE_ACTION_GATEWAY is on) handles ✅ שמור —
# not this .confirmed event anymore.


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
        # PR-0C Phase 3: fields now live under tool_inputs (see
        # _send_voice_approval_request) — not at the payload's top level.
        _tool_inputs = item["payload"].get("tool_inputs", {})
        _pending_voice_edits[owner_id] = {
            "domain": _tool_inputs.get("domain", "general"),
            "source": _tool_inputs.get("source", "media_handler"),
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
    (callback_data prefixes "approve:"/"reject:"); ✏️ ערוך is registered here.

    PR-0C Phase 3: payload now carries tool_name/tool_inputs (like every other
    Agent-tool approval) so app.py's tool_name branch — which executes via
    tools/approval_actions.py::media_save_to_memory, through ActionGateway.approve()
    when FEATURE_ACTION_GATEWAY is on — handles ✅ שמור, instead of the removed
    media_save_to_memory.confirmed event_bus subscriber."""
    from event_bus import bus
    from identity import resolve_identity

    identity = resolve_identity("telegram", owner_chat_id)
    tool_inputs = {"transcript": transcript, "domain": domain, "source": source}

    from core.action_gateway import action_gateway as _gw
    block_message = _gw.propose_gated(
        tenant_id=getattr(identity, "tenant_id", "boss_hq"),
        canonical_user_id=identity.memory_key,
        tool_name="media_save_to_memory", tool_inputs=tool_inputs,
        origin_channel="telegram", origin_chat_id=owner_chat_id,
        identity=identity,
    )
    if block_message:
        return block_message

    action_id, _ = bus.request_approval(
        action="media_save_to_memory",
        payload={
            "tool_name":         "media_save_to_memory",
            "tool_inputs":       tool_inputs,
            "origin_channel":    "telegram",
            "origin_chat_id":    owner_chat_id,
            "canonical_user_id": identity.memory_key,
            "user_chat_id":      owner_chat_id,
            "channel":           "telegram",
        },
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
    provider_media_id: str,
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

    idem_key = _idem_key(source, provider_media_id, user_id)
    if _idem_store.is_duplicate("media", idem_key, ""):
        return MediaResult(
            ok=False,
            error=MediaError("DUPLICATE", "הקובץ הזה כבר התקבל.", False),
        )

    stt_result = transcribe(audio_bytes, mime_type)
    if not stt_result.ok:
        _idem_store.release("media", idem_key, "")
        return MediaResult(
            ok=False,
            error=MediaError(stt_result.error.error_code, stt_result.error.error_message, stt_result.error.retryable),
        )

    raw_transcript = stt_result.raw_transcript
    transcript = stt_result.normalized_transcript

    normalized_for_prefix = _normalize_for_prefix(transcript)
    action_requested = _has_action(transcript)
    prefix_match_count = sum(
        normalized_for_prefix.startswith(prefix) for prefix in PREFIX_HARD
    )
    logger.info(
        "[voice] transcription analyzed source=%s chars=%d normalized_chars=%d "
        "action_requested=%s prefix_match_count=%d",
        source,
        len(transcript or ""),
        len(normalized_for_prefix or ""),
        action_requested,
        prefix_match_count,
    )

    # אישור חובה תמיד עבור מילות סיכון, ללא קשר לאיתור action_requested או לאורך הטקסט.
    if _has_risk_words(transcript):
        ack = _send_voice_approval_request(transcript, domain, source, owner_chat_id, reason="מילת סיכון")
        return MediaResult(ok=True, raw_transcript=raw_transcript, normalized_transcript=transcript, message=ack)

    # שלב 3 — אין פעולה: רק תמלול, ללא Drive, ללא זיכרון.
    if not action_requested:
        _log_unhandled_voice_note(transcript, user_id, source)
        return MediaResult(
            ok=True, raw_transcript=raw_transcript, normalized_transcript=transcript,
            message=f"📝 תומלל:\n{transcript}\n\nלא בוצעה פעולה.",
        )

    # שלב 4 — action_requested=True, ללא מילת סיכון: Voice Inbox (pending) בלבד.
    # אין ניתוב לפי איזה prefix תאם (משימה/ליד/זיכרון/...) — זה F17, לא כאן.
    saved = _save_transcript_to_media_files(transcript, domain, source, status="pending")
    return MediaResult(
        ok=saved, raw_transcript=raw_transcript, normalized_transcript=transcript, saved_to_memory=saved,
        message=f"📥 נשמר ל-Voice Inbox:\n{transcript}" if saved else "❌ שמירה ל-Voice Inbox נכשלה",
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
            error=MediaError("FILE_TOO_LARGE", "הקובץ גדול מ-50MB. הגודל המרבי הוא 50MB.", False),
        )

    idem_key = _idem_key(source, file_id, user_id)
    if _idem_store.is_duplicate("media", idem_key, ""):
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError("DUPLICATE", "הקובץ הזה כבר הועלה.", False),
        )

    def release_reservation() -> None:
        _idem_store.release("media", idem_key, "")

    parent_folder_id, folder_err = _resolve_drive_folder(domain)
    if folder_err:
        release_reservation()
        return MediaResult(ok=False, file_size_tier=tier, error=folder_err)

    try:
        media_key = logical_media_key(source, file_id, file_bytes)
    except ValueError as exc:
        release_reservation()
        return MediaResult(ok=False, file_size_tier=tier, error=MediaError("MEDIA_KEY_INVALID", str(exc), False))

    media_lookup = find_asset_by_logical_media_key(media_key)
    if media_lookup.status == "duplicate":
        release_reservation()
        return MediaResult(ok=False, file_size_tier=tier, error=MediaError("MEDIA_DUPLICATE_KEY", media_lookup.error, False))
    if media_lookup.status == "error":
        release_reservation()
        return MediaResult(ok=False, file_size_tier=tier, error=MediaError("MEDIA_LOOKUP_FAILED", "Media Files lookup failed", True))
    if media_lookup.status == "reusable":
        fields = record_fields(media_lookup.record)
        return MediaResult(
            ok=True, asset_id=record_id(media_lookup.record) or "",
            drive_url=fields.get("Drive URL", ""), file_size_tier=tier,
        )
    media_record = media_lookup.record if media_lookup.status == "incomplete" else None
    media_record_id = (record_id(media_record) or "") if media_record else ""

    def mark_partial(record_id: str, drive_file_id: str, drive_url: str) -> None:
        if record_id:
            update_asset_persistence(
                record_id,
                state=MediaPersistenceState.PARTIAL,
                drive_file_id=drive_file_id,
                drive_url=drive_url,
                last_error_code="MEDIA_FILES_PARTIAL",
            )

    existing_drive = drive_adapter.find_existing_by_logical_media_key(media_key, parent_folder_id)
    if existing_drive.ok:
        if media_record_id:
            reconciled = update_asset_persistence(
                media_record_id,
                state=MediaPersistenceState.ASSET_PERSISTED,
                drive_file_id=existing_drive.file_id,
                drive_url=existing_drive.web_url,
            )
            if reconciled:
                return MediaResult(
                    ok=True, asset_id=media_record_id,
                    drive_url=existing_drive.web_url, file_size_tier=tier,
                )
            mark_partial(media_record_id, existing_drive.file_id, existing_drive.web_url)
            release_reservation()
            return MediaResult(
                ok=False, drive_url=existing_drive.web_url, file_size_tier=tier,
                error=MediaError("MEDIA_FILES_RECONCILIATION_FAILED", "Media Files reconciliation failed", True),
            )
        reconciled_id = save_asset(AssetRecord(
            name=filename,
            file_type=file_type,
            mime_type=mime_type,
            drive_url=existing_drive.web_url,
            drive_file_id=existing_drive.file_id,
            domain=domain,
            source=source,
            size_bytes=size_bytes,
            created_by=user_id,
            provider_media_id=file_id,
            linked_lead_id=linked_lead_id,
            logical_media_key=media_key,
            persistence_state=MediaPersistenceState.DRIVE_UPLOADED,
        ))
        if not reconciled_id:
            release_reservation()
            return MediaResult(
                ok=False, drive_url=existing_drive.web_url, file_size_tier=tier,
                error=MediaError("MEDIA_FILES_RECONCILIATION_FAILED", "Media Files persistence failed", True),
            )
        if not update_asset_persistence(
            reconciled_id,
            state=MediaPersistenceState.ASSET_PERSISTED,
            drive_file_id=existing_drive.file_id,
            drive_url=existing_drive.web_url,
        ):
            mark_partial(reconciled_id, existing_drive.file_id, existing_drive.web_url)
            release_reservation()
            return MediaResult(
                ok=False, drive_url=existing_drive.web_url, file_size_tier=tier,
                error=MediaError("MEDIA_FILES_RECONCILIATION_FAILED", "Media Files reconciliation failed", True),
            )
        return MediaResult(
            ok=True, asset_id=reconciled_id, drive_url=existing_drive.web_url,
            file_size_tier=tier,
        )
    if existing_drive.error and existing_drive.error.error_code not in {"DRIVE_NOT_FOUND"}:
        release_reservation()
        return MediaResult(ok=False, file_size_tier=tier, error=existing_drive.error)

    if not media_record_id:
        media_record_id = save_asset(AssetRecord(
            name=filename,
            file_type=file_type,
            mime_type=mime_type,
            drive_url="",
            drive_file_id="",
            domain=domain,
            source=source,
            size_bytes=size_bytes,
            created_by=user_id,
            provider_media_id=file_id,
            linked_lead_id=linked_lead_id,
            logical_media_key=media_key,
            persistence_state=MediaPersistenceState.PENDING,
        )) or ""

    drive_result = drive_adapter.upload_file(
        file_bytes, filename, mime_type, parent_folder_id, logical_media_key=media_key,
    )
    if not drive_result.ok:
        if media_record_id:
            update_asset_persistence(
                media_record_id,
                state=MediaPersistenceState.FAILED,
                last_error_code=drive_result.error.error_code,
            )
        release_reservation()
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            error=MediaError(drive_result.error.error_code, drive_result.error.error_message, drive_result.error.retryable),
        )

    if media_record_id:
        state_saved = update_asset_persistence(
            media_record_id,
            state=MediaPersistenceState.DRIVE_UPLOADED,
            drive_file_id=drive_result.file_id,
            drive_url=drive_result.web_url,
        )
        asset_id = media_record_id
    else:
        asset_id = save_asset(AssetRecord(
            name=drive_result.name,
            file_type=file_type,
            mime_type=mime_type,
            drive_url=drive_result.web_url,
            drive_file_id=drive_result.file_id,
            domain=domain,
            source=source,
            size_bytes=size_bytes,
            created_by=user_id,
            provider_media_id=file_id,
            linked_lead_id=linked_lead_id,
            logical_media_key=media_key,
            persistence_state=MediaPersistenceState.DRIVE_UPLOADED,
        ))
        state_saved = bool(asset_id)
    if not state_saved or not asset_id:
        mark_partial(media_record_id, drive_result.file_id, drive_result.web_url)
        release_reservation()
        return MediaResult(
            ok=False,
            file_size_tier=tier,
            drive_url=drive_result.web_url,
            error=MediaError("MEDIA_FILES_PARTIAL", "Drive object exists but Media Files state is partial.", True),
        )
    if not update_asset_persistence(
        asset_id,
        state=MediaPersistenceState.ASSET_PERSISTED,
        drive_file_id=drive_result.file_id,
        drive_url=drive_result.web_url,
    ):
        mark_partial(asset_id, drive_result.file_id, drive_result.web_url)
        release_reservation()
        return MediaResult(
            ok=False, file_size_tier=tier, drive_url=drive_result.web_url,
            error=MediaError("MEDIA_FILES_PARTIAL", "Drive object exists but final persistence is incomplete.", True),
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
    file_id = hashlib.sha256(file_bytes).hexdigest()
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


# mime -> document_converter input_type, mirrors tools/google_tools.py's
# _MIME_TO_TYPE (kept local — that dict is private to its own module).
_DOCUMENT_MIME_TO_TYPE = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/html": "html",
    "text/plain": "txt",
    "text/markdown": "markdown",
}


def extract_text_if_document(file_bytes: bytes, mime_type: str) -> str | None:
    """Best-effort text extraction via document_converter, for callers (e.g.
    cmd_update.py) that want a document's content alongside its caption/link.
    Never raises: unsupported mime types (images, pdf, pptx, ...) and any
    conversion failure both return None so the caller can fall back to
    whatever it already had (caption/Drive link)."""
    input_type = _DOCUMENT_MIME_TO_TYPE.get(mime_type)
    if input_type is None:
        return None

    import os
    import tempfile
    from pathlib import Path
    from document_converter.engine import convert_document

    tmp_path: str | None = None
    output_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{input_type}", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        result = convert_document(tmp_path, input_type, "markdown")
        if result.get("confidence") != "high" or not result.get("output_file"):
            return None

        output_path = Path(result["output_file"])
        return output_path.read_text(encoding="utf-8")[:3000]
    except Exception as e:
        logger.error(f"[Media] extract_text_if_document failed: {e}", exc_info=True)
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if output_path:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass


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
        provider_media_id="f1",
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
        audio_bytes=b"audio-bytes", mime_type="audio/ogg", provider_media_id="v1",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert no_action.ok and no_action.message == "📝 תומלל:\nשיחה רגילה בלי שום הוראה\n\nלא בוצעה פעולה."
        mock_log.assert_called_once()
    print("✅ no action prefix → transcript shown in message, logged for review, no memory/approval")

    with patch.object(_this, "transcribe", return_value=_stt("משימה: להתקשר ללקוח מחר")), \
         patch.object(_this, "_save_transcript_to_media_files", return_value=True) as mock_save:
        short_action = handle_voice_note(
        audio_bytes=b"audio-bytes", mime_type="audio/ogg", provider_media_id="v2",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert short_action.ok and short_action.saved_to_memory
        assert "נשמר ל-Voice Inbox" in short_action.message
        mock_save.assert_called_once_with("משימה: להתקשר ללקוח מחר", "general", "telegram", status="pending")
    print("✅ hard prefix, no risk word → saved to Voice Inbox (pending), not Business Memory directly")

    with patch.object(_this, "transcribe", return_value=_stt("תשלח לו את החוזה החדש")), \
         patch.object(_this, "_send_voice_approval_request", return_value="📨 ack") as mock_approve, \
         patch.object(_this, "_save_transcript_to_media_files") as mock_save:
        risky = handle_voice_note(
        audio_bytes=b"audio-bytes", mime_type="audio/ogg", provider_media_id="v3",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert risky.ok and risky.message == "📨 ack"
        mock_approve.assert_called_once_with("תשלח לו את החוזה החדש", "general", "telegram", "123", reason="מילת סיכון")
        assert not mock_save.called
    print("✅ risk word present → approval gate even for short text, no direct save")

    long_text = "משימה: " + " ".join(["דבר"] * 35)
    with patch.object(_this, "transcribe", return_value=_stt(long_text)), \
         patch.object(_this, "_send_voice_approval_request") as mock_approve, \
         patch.object(_this, "_save_transcript_to_media_files", return_value=True) as mock_save:
        long_action = handle_voice_note(
        audio_bytes=b"audio-bytes", mime_type="audio/ogg", provider_media_id="v4",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert long_action.ok and "נשמר ל-Voice Inbox" in long_action.message
        mock_save.assert_called_once_with(long_text, "general", "telegram", status="pending")
        assert not mock_approve.called
    print("✅ action + >30 words, no risk word → Voice Inbox (pending) too, no approval gate, no length branching")

    # PREFIX_HARD בלבד — פעלי פעולה רכים ("תזכיר"/"תפתח"/"תשלח"/"תקבע") לא מפעילים
    # action_requested בהיעדר prefix מפורש וללא מילת סיכון.
    with patch.object(_this, "transcribe", return_value=_stt("תזכיר לי לקבוע פגישה מחר")), \
         patch.object(_this, "_log_unhandled_voice_note") as mock_log, \
         patch.object(_this, "_save_transcript_to_memory") as mock_save, \
         patch.object(_this, "_send_voice_approval_request") as mock_approve:
        soft_verb_only = handle_voice_note(
        audio_bytes=b"audio-bytes", mime_type="audio/ogg", provider_media_id="v5",
            user_id="u1", domain="general", owner_chat_id="123",
        )
        assert soft_verb_only.ok and soft_verb_only.message == "📝 תומלל:\nתזכיר לי לקבוע פגישה מחר\n\nלא בוצעה פעולה."
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
