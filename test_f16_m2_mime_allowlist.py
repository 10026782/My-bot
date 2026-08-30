"""F16-M2 regression: canonical MIME allowlist, fail-closed.

Exercises the actual policy boundary (media_handler._validate_mime and its
wiring into handle_file_upload()/handle_voice_note()) rather than mocking it
away. No content-based MIME detection exists anywhere in the current F16
ingestion path (confirmed in BUG_AUDIT_LOG.md's F16-M2 discovery) — this is
not a gap in this test, it's the documented current architecture; §7's
declared-vs-detected comparison has no existing path to exercise.
"""

from unittest.mock import patch

import media_handler
from media_handler import (
    ALLOWED_MEDIA_MIME_TYPES,
    _validate_mime,
    handle_file_upload,
    handle_voice_note,
)


def test_allowed_mime_passes_validation():
    assert _validate_mime("image/jpeg") is None
    assert _validate_mime("application/pdf", "report.pdf") is None


def test_unsupported_mime_rejected():
    err = _validate_mime("application/x-msdownload", "virus.exe")
    assert err is not None and err.error_code == "MIME_UNSUPPORTED"


def test_missing_mime_rejected():
    err = _validate_mime("")
    assert err is not None and err.error_code == "MIME_MISSING"


def test_octet_stream_accepted_only_with_known_extension():
    assert _validate_mime("application/octet-stream", "notes.txt") is None
    err = _validate_mime("application/octet-stream", "mystery.bin")
    assert err is not None and err.error_code == "MIME_UNSUPPORTED"
    err_no_name = _validate_mime("application/octet-stream", "")
    assert err_no_name is not None and err_no_name.error_code == "MIME_UNSUPPORTED"


def test_policy_reads_from_canonical_ssot_not_a_hardcoded_literal():
    with patch.object(media_handler, "ALLOWED_MEDIA_MIME_TYPES", frozenset({"text/plain"})):
        assert _validate_mime("text/plain") is None
        err = _validate_mime("image/jpeg")
        assert err is not None and err.error_code == "MIME_UNSUPPORTED"
    assert "image/jpeg" in ALLOWED_MEDIA_MIME_TYPES


def test_handle_file_upload_rejects_unsupported_mime_before_any_io():
    with patch.object(media_handler.drive_adapter, "_get_upload_folder") as mock_folder:
        result = handle_file_upload(
            file_bytes=b"x" * 1024,
            filename="virus.exe",
            mime_type="application/x-msdownload",
            file_type="document",
            file_id="f-m2-1",
            user_id="u1",
            domain="general",
        )
    assert not result.ok and result.error.error_code == "MIME_UNSUPPORTED"
    mock_folder.assert_not_called()


def test_handle_voice_note_rejects_unsupported_mime_before_any_io():
    with patch.object(media_handler, "transcribe") as mock_transcribe:
        result = handle_voice_note(
            audio_bytes=b"audio-bytes",
            mime_type="application/zip",
            provider_media_id="v-m2-1",
            user_id="u1",
            domain="general",
            owner_chat_id="123",
        )
    assert not result.ok and result.error.error_code == "MIME_UNSUPPORTED"
    mock_transcribe.assert_not_called()


if __name__ == "__main__":
    test_allowed_mime_passes_validation()
    test_unsupported_mime_rejected()
    test_missing_mime_rejected()
    test_octet_stream_accepted_only_with_known_extension()
    test_policy_reads_from_canonical_ssot_not_a_hardcoded_literal()
    test_handle_file_upload_rejects_unsupported_mime_before_any_io()
    test_handle_voice_note_rejects_unsupported_mime_before_any_io()
    print("test_f16_m2_mime_allowlist.py self-test OK")
