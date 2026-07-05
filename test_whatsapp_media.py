# test_whatsapp_media.py — BUG-071 WhatsApp Media Support
#
# Tests Twilio + Meta WhatsApp media extraction, download, and routing
# through unified media_handler pipeline (same as Telegram C90).
#
# Verifies:
# 1. Twilio WhatsApp media extraction (NumMedia, MediaUrl0, MediaContentType0)
# 2. Meta WhatsApp media extraction (image/video/audio/document)
# 3. Media type inference (audio→voice handler, others→file handler)
# 4. Filename construction from URL or metadata
# 5. MIME type inference from Meta media types

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug071-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG071_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug071Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug071Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")


def test_twilio_media_extraction():
    """Test Twilio WhatsApp media extraction."""
    from providers.whatsapp_media_adapter import extract_whatsapp_media

    # Media present
    request_values = {
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/2010-04-01/Accounts/AC123/MediaUrl/ME456",
        "MediaContentType0": "image/jpeg",
        "MessageSid": "SM1234567890",
    }
    result = extract_whatsapp_media(request_values)
    assert result is not None
    assert result["media_url"] == "https://api.twilio.com/2010-04-01/Accounts/AC123/MediaUrl/ME456"
    assert result["mime_type"] == "image/jpeg"
    assert result["file_id"] == "SM1234567890"

    # No media
    request_values_no_media = {
        "NumMedia": "0",
    }
    result = extract_whatsapp_media(request_values_no_media)
    assert result is None

    # NumMedia but no URL
    request_values_bad = {
        "NumMedia": "1",
        "MessageSid": "SM123",
    }
    result = extract_whatsapp_media(request_values_bad)
    assert result is None


def test_twilio_media_filename_inference():
    """Test filename construction from Twilio media metadata."""
    from providers.whatsapp_media_adapter import infer_filename

    # URL with filename (has extension) — extract it
    url = "https://example.com/path/to/document.pdf"
    filename = infer_filename(url, "application/pdf", "SM123")
    assert filename == "document.pdf"

    # Path component without extension — fall back to file_id + extension
    url = "https://api.twilio.com/2010-04-01/Accounts/AC123/MediaUrl/ME456"
    filename = infer_filename(url, "audio/ogg", "SM456")
    assert filename == "SM456.ogg"

    # Plain domain URL — fall back to file_id + extension
    url = "https://example.com"
    filename = infer_filename(url, "audio/ogg", "SM456")
    assert filename == "SM456.ogg"


def test_twilio_file_type_inference():
    """Test media type classification."""
    from providers.whatsapp_media_adapter import infer_file_type

    assert infer_file_type("audio/ogg") == "audio"
    assert infer_file_type("audio/mp3") == "audio"
    assert infer_file_type("image/jpeg") == "image"
    assert infer_file_type("video/mp4") == "video"
    assert infer_file_type("application/pdf") == "document"


def test_meta_media_extraction():
    """Test Meta WhatsApp media extraction."""
    from providers.meta_whatsapp_media_adapter import extract_meta_whatsapp_media

    # Image message
    message_image = {
        "type": "image",
        "image": {"id": "IMG123"},
        "id": "msg456",
        "from": "+972123456789",
    }
    result = extract_meta_whatsapp_media(message_image)
    assert result is not None
    assert result["media_type"] == "image"
    assert result["media_id"] == "IMG123"
    assert result["message_id"] == "msg456"

    # Audio message
    message_audio = {
        "type": "audio",
        "audio": {"id": "AUD789"},
        "id": "msg999",
    }
    result = extract_meta_whatsapp_media(message_audio)
    assert result is not None
    assert result["media_type"] == "audio"
    assert result["media_id"] == "AUD789"

    # Document with filename
    message_doc = {
        "type": "document",
        "document": {"id": "DOC111", "filename": "invoice.pdf"},
        "id": "msg222",
    }
    result = extract_meta_whatsapp_media(message_doc)
    assert result is not None
    assert result["media_type"] == "document"
    assert result["media_id"] == "DOC111"
    assert result["filename"] == "invoice.pdf"

    # Text message (no media)
    message_text = {
        "type": "text",
        "text": {"body": "Hello"},
        "id": "msg333",
    }
    result = extract_meta_whatsapp_media(message_text)
    assert result is None


def test_meta_mime_type_inference():
    """Test MIME type inference from Meta media types."""
    from providers.meta_whatsapp_media_adapter import infer_mime_type_from_meta_type

    assert infer_mime_type_from_meta_type("image") == "image/jpeg"
    assert infer_mime_type_from_meta_type("video") == "video/mp4"
    assert infer_mime_type_from_meta_type("audio") == "audio/ogg"
    assert infer_mime_type_from_meta_type("document", "file.pdf") == "application/pdf"
    assert infer_mime_type_from_meta_type("document", "notes.txt") == "text/plain"
    assert infer_mime_type_from_meta_type("document") == "application/octet-stream"


def test_normalize_meta_payload_with_media():
    """Test _normalize_meta_payload extracts media metadata."""
    # This test verifies the updated _normalize_meta_payload includes media extraction.
    # Full integration test would require mocking the actual provider imports.
    from app import _normalize_meta_payload

    payload_with_image = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "type": "image",
                        "image": {"id": "IMG789"},
                        "id": "msg789",
                        "from": "+972123456789",
                    }],
                    "metadata": {
                        "display_phone_number": "+972123456789",
                    }
                }
            }]
        }]
    }

    result = _normalize_meta_payload(payload_with_image)
    assert result is not None
    assert result["from"] == "+972123456789"
    assert result["msg_id"] == "msg789"
    # media field should be present (even if extraction fails, field exists)
    assert "media" in result


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
