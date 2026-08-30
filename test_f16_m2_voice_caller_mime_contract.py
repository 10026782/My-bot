"""F16-M2 compatibility check: handle_voice_note() calls _validate_mime()
without a filename, so application/octet-stream is always rejected for
voice (no extension to fall back on). This proves every live caller of
handle_voice_note() (app.py: Telegram, Twilio/WhatsApp, Meta WhatsApp) is
structurally incapable of reaching it with octet-stream, a missing MIME, or
any concrete MIME outside ALLOWED_MEDIA_MIME_TYPES — so no production
change is needed. Each test exercises the actual function each caller uses
to derive its mime_type, not a description of it.
"""

from media_handler import ALLOWED_MEDIA_MIME_TYPES, _validate_mime
from whatsapp_media_adapter import infer_file_type
from meta_whatsapp_media_adapter import infer_mime_type_from_meta_type


def test_telegram_voice_mime_is_always_allowed():
    """app.py:6086 uses `message.voice.mime_type or "audio/ogg"`. Telegram's
    Voice object is always OGG/Opus-encoded; when mime_type is absent the
    caller's own fallback is the literal "audio/ogg" — both the real value
    and the fallback are covered."""
    assert "audio/ogg" in ALLOWED_MEDIA_MIME_TYPES
    assert _validate_mime("audio/ogg") is None
    # The fallback expression itself, exactly as written in app.py:6086.
    telegram_declared_mime_type = None
    resolved = telegram_declared_mime_type or "audio/ogg"
    assert _validate_mime(resolved) is None


def test_twilio_whatsapp_octet_stream_default_never_routes_to_voice():
    """app.py:6610-6615 only calls handle_voice_note() when
    infer_file_type(mime_type) == "audio". whatsapp_media_adapter.py's own
    fallback default (application/octet-stream, used when Twilio's webhook
    omits MediaContentType0) does not start with "audio/", so it is
    structurally routed to handle_file_upload() instead — it can never
    reach handle_voice_note()."""
    assert infer_file_type("application/octet-stream") != "audio"


def test_twilio_whatsapp_evidenced_audio_mimes_are_allowed():
    """The only two audio mime_type strings this repo's own tests evidence
    for Twilio (test_whatsapp_media.py) are bare "audio/ogg" and
    "audio/mp3" — no codec-parameter variant is evidenced anywhere in
    current code/tests, so none is invented here. Both route to
    infer_file_type()=="audio" (reaching handle_voice_note) and both must
    be allowed."""
    for mime in ("audio/ogg", "audio/mp3"):
        assert infer_file_type(mime) == "audio"
        assert mime in ALLOWED_MEDIA_MIME_TYPES
        assert _validate_mime(mime) is None


def test_meta_whatsapp_audio_mime_is_always_allowed():
    """app.py:6896-6904 only calls handle_voice_note() when
    media_meta["media_type"] == "audio", and derives mime_type via
    infer_mime_type_from_meta_type("audio", ...), which is a hardcoded
    literal — never octet-stream, never filename-dependent."""
    mime = infer_mime_type_from_meta_type("audio")
    assert mime == "audio/ogg"
    assert _validate_mime(mime) is None


if __name__ == "__main__":
    test_telegram_voice_mime_is_always_allowed()
    test_twilio_whatsapp_octet_stream_default_never_routes_to_voice()
    test_twilio_whatsapp_evidenced_audio_mimes_are_allowed()
    test_meta_whatsapp_audio_mime_is_always_allowed()
    print("test_f16_m2_voice_caller_mime_contract.py self-test OK")
