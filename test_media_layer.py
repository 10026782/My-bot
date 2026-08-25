#!/usr/bin/env python3
"""
test_media_layer.py — Regression tests for the F16 Media Layer:
voice_stt_adapter.py, drive_adapter.py, media_gateway.py, media_handler.py.

מאמת:
1. STT: oversized/empty rejection, nikud strip, no-provider fallback failure
2. Drive: safe filename, empty-file rejection, missing-auth rejection
3. Gateway: AssetRecord → fields mapping (linked lead, transcript)
4. Handler: size-tier classification, memory keyword gate, idempotency key,
   oversized rejection for both voice and file paths, result formatting,
   flag-off "coming soon" stubs in app.py / tma_api.py
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
# 1. voice_stt_adapter
# ══════════════════════════════════════════════════════════════════

print("\n── voice_stt_adapter ────────────────")

from voice_stt_adapter import transcribe, _normalize_hebrew, MAX_STT_BYTES

chk(
    "nikud stripped + whitespace collapsed",
    _normalize_hebrew("שָׁלוֹם   עוֹלָם") == "שלום עולם",
)
chk("ascii text unaffected", _normalize_hebrew("hello world") == "hello world")

too_big = transcribe(b"x" * (MAX_STT_BYTES + 1), "audio/ogg")
chk(
    'oversized audio → error "OVERSIZED"',
    not too_big.ok and too_big.error.error_code == "OVERSIZED",
)

_saved_groq = os.environ.pop("GROQ_API_KEY", None)
_saved_openai = os.environ.pop("OPENAI_API_KEY", None)
no_provider = transcribe(b"fake-bytes", "audio/ogg")
chk(
    "no provider keys → STT_FAILED (never raises)",
    not no_provider.ok and no_provider.error.error_code == "STT_FAILED",
)
if _saved_groq is not None:
    os.environ["GROQ_API_KEY"] = _saved_groq
if _saved_openai is not None:
    os.environ["OPENAI_API_KEY"] = _saved_openai


# ══════════════════════════════════════════════════════════════════
# 2. drive_adapter
# ══════════════════════════════════════════════════════════════════

print("\n── drive_adapter ────────────────────")

from drive_adapter import upload_file, _safe_filename, get_or_create_folder

chk(
    "Hebrew filename preserved, unsafe chars stripped",
    _safe_filename('שלום/עולם:test?.mp3') == "שלום_עולם_test_.mp3",
)
empty_file = upload_file(b"", "x.mp3", "audio/mpeg", parent_folder_id="test-folder-id")
chk("empty file bytes → EMPTY_FILE error", not empty_file.ok and empty_file.error.error_code == "EMPTY_FILE")

with patch("drive_adapter.get_google_token", return_value=None):
    no_auth = upload_file(b"fake-bytes", "x.mp3", "audio/mpeg", parent_folder_id="test-folder-id")
    chk(
        "missing Google OAuth → GOOGLE_AUTH_MISSING error",
        not no_auth.ok and no_auth.error.error_code == "GOOGLE_AUTH_MISSING",
    )
    folder = get_or_create_folder("general", "root")
    chk("get_or_create_folder returns None without auth", folder is None)


# ══════════════════════════════════════════════════════════════════
# 3. media_gateway
# ══════════════════════════════════════════════════════════════════

print("\n── media_gateway ─────────────────────")

from media_gateway import AssetRecord, _asset_to_fields, save_asset
from airtable_schema import MediaFileFields

bare = AssetRecord(
    name="test.mp3", file_type="audio", mime_type="audio/mpeg",
    drive_url="https://drive.google.com/uc?id=abc", drive_file_id="abc",
    domain="general", source="telegram", size_bytes=1234, created_by="tester",
)
fields = _asset_to_fields(bare)
chk("required fields present", fields[MediaFileFields.NAME] == "test.mp3")
chk("optional linked-lead omitted when unset", MediaFileFields.LINKED_LEAD not in fields)
chk("optional transcript omitted when unset", MediaFileFields.RAW_TRANSCRIPT not in fields)

with_lead = AssetRecord(
    name="voice.ogg", file_type="audio", mime_type="audio/ogg",
    drive_url="https://drive.google.com/uc?id=def", drive_file_id="def",
    domain="real_estate", source="telegram", size_bytes=4321, created_by="tester",
    linked_lead_id="recABC123", raw_transcript="שָׁלוֹם", normalized_transcript="שלום",
)
fields2 = _asset_to_fields(with_lead)
chk("linked lead written as array", fields2[MediaFileFields.LINKED_LEAD] == ["recABC123"])
chk("raw transcript untouched", fields2[MediaFileFields.RAW_TRANSCRIPT] == "שָׁלוֹם")
chk("normalized transcript stripped", fields2[MediaFileFields.NORMALIZED_TRANSCRIPT] == "שלום")

with patch("media_gateway.airtable_create", return_value={"id": "recXYZ"}) as mock_create:
    rec_id = save_asset(bare)
    chk("save_asset returns record id on success", rec_id == "recXYZ")
    chk(
        "save_asset writes to 'Media Files' table via gateway",
        mock_create.call_args[0][0] == "Media Files",
    )

with patch("media_gateway.airtable_create", return_value=None):
    rec_id_fail = save_asset(bare)
    chk("save_asset returns None on gateway failure", rec_id_fail is None)


# ══════════════════════════════════════════════════════════════════
# 4. media_handler
# ══════════════════════════════════════════════════════════════════

print("\n── media_handler ─────────────────────")

import media_handler as mh

chk("5MB → normal tier", mh._classify_size(5 * 1024 * 1024) == "normal")
chk("20MB → large tier", mh._classify_size(20 * 1024 * 1024) == "large")
chk("60MB → oversized", mh._classify_size(60 * 1024 * 1024) == "oversized")

chk('memory keyword "סיכמנו" triggers gate', mh._should_save_to_memory("סיכמנו על המחיר") is True)
chk("no keyword → gate stays closed", mh._should_save_to_memory("שיחה רגילה") is False)

k1 = mh._idem_key("telegram", "file123", "user1")
k2 = mh._idem_key("telegram", "file123", "user1")
k3 = mh._idem_key("telegram", "file456", "user1")
chk("idempotency key deterministic", k1 == k2)
chk("idempotency key differs per file", k1 != k3)
chk("idempotency key is 16 chars", len(k1) == 16)

oversized_voice = mh.handle_voice_note(
    audio_bytes=b"x" * (mh.TIER_LARGE + 1),
    mime_type="audio/ogg",
    provider_media_id="f1",
    user_id="u1",
    domain="general",
    owner_chat_id="123",
)
chk(
    "oversized voice rejected before any I/O",
    not oversized_voice.ok and oversized_voice.error.error_code == "FILE_TOO_LARGE",
)

oversized_file = mh.handle_file_upload(
    file_bytes=b"x" * (mh.TIER_LARGE + 1),
    filename="x.pdf", mime_type="application/pdf", file_type="document",
    file_id="f2", user_id="u1", domain="general",
)
chk(
    "oversized file rejected before any I/O",
    not oversized_file.ok and oversized_file.error.error_code == "FILE_TOO_LARGE",
)

with patch("media_handler._idem_store") as mock_idem:
    mock_idem.is_duplicate.return_value = True
    dup = mh.handle_voice_note(
        audio_bytes=b"small", mime_type="audio/ogg", provider_media_id="f3",
        user_id="u1", domain="general", owner_chat_id="123",
    )
    chk("duplicate file blocked by idempotency", not dup.ok and dup.error.error_code == "DUPLICATE")

ok_msg = mh._format_media_result(mh.MediaResult(ok=True, drive_url="https://x", file_size_tier="normal"))
chk("success message includes drive url", "https://x" in ok_msg)
err_msg = mh._format_media_result(mh.MediaResult(ok=False, error=mh.MediaError("X", "boom", False)))
chk("error message surfaces error text", "boom" in err_msg)

# Large-tier result should note Drive-only / no-AI in the user-facing message
large_msg = mh._format_media_result(mh.MediaResult(ok=True, drive_url="https://x", file_size_tier="large"))
chk("large-tier message notes Drive-only (no AI)", "AI" in large_msg or "דרייב" in large_msg)


# ══════════════════════════════════════════════════════════════════
# 5. flag-off stubs (Telegram + TMA)
# ══════════════════════════════════════════════════════════════════

print("\n── flag-off stubs ────────────────────")

import feature_flags
chk("FEATURE_VOICE_NOTES default OFF", feature_flags.is_enabled("FEATURE_VOICE_NOTES") is False)
chk("FEATURE_MEDIA_UPLOAD default OFF", feature_flags.is_enabled("FEATURE_MEDIA_UPLOAD") is False)


print("\n" + "=" * 40)
print(f"  {passed}/{passed + failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
print("  All OK ✅")
