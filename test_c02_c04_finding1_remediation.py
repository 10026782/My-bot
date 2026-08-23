"""Focused regression tests for C02-C04 Finding #1.

Provider acknowledgement is intentionally tested separately from media state.
"""

import logging
import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-c02-c04-f1-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:C02_C04_F1_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patC02C04F1Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appC02C04F1Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
import media_handler  # noqa: E402


def _identity():
    return SimpleNamespace(memory_key="boss_hq:test", role="owner")


def _common_app_patches():
    return [
        patch.object(app, "_apply_ingress_context_gate"),
        patch.object(app, "resolve_identity", return_value=_identity()),
        patch.object(app.idempotency, "is_duplicate", return_value=False),
        patch.object(app, "_channel_domain", return_value="general"),
        patch.object(app, "_inject_utm", None),
        patch("furniture_lead_funnel.handle_furniture_lead_message", return_value=None),
        patch.object(app, "run_agent", return_value=""),
    ]


def test_twilio_ack_is_not_processing_success_on_download_failure(caplog):
    caplog.set_level(logging.INFO, logger="app")
    request_values = {
        "NumMedia": "1",
        "MediaUrl0": "https://twilio.test/media",
        "MediaContentType0": "image/jpeg",
        "MessageSid": "SM-failure",
        "From": "whatsapp:+972500000000",
        "To": "whatsapp:+972511111111",
        "Body": "media received",
    }
    patches = _common_app_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
            patch.object(app, "_validate_twilio_signature", return_value=True), \
            patch("whatsapp_media_adapter.download_whatsapp_media", return_value=None), \
            patch("whatsapp_media_adapter.extract_whatsapp_media", return_value={
                "media_url": request_values["MediaUrl0"],
                "mime_type": "image/jpeg",
                "file_id": "SM-failure",
            }):
        response = app.app.test_client().post("/whatsapp", data=request_values)

    assert response.status_code == 200
    assert b"<Response" in response.data
    assert "status=FAILED" in caplog.text
    assert "success_evidence=False" in caplog.text
    assert "MEDIA_DOWNLOAD_FAILED" in caplog.text


def test_twilio_processing_success_has_explicit_completion(caplog):
    caplog.set_level(logging.INFO, logger="app")
    request_values = {
        "NumMedia": "1",
        "MediaUrl0": "https://twilio.test/media",
        "MediaContentType0": "image/jpeg",
        "MessageSid": "SM-success",
        "From": "whatsapp:+972500000000",
        "To": "whatsapp:+972511111111",
        "Body": "media received",
    }
    patches = _common_app_patches()
    success = media_handler.MediaResult(ok=True, asset_id="asset-1")
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
            patch.object(app, "_validate_twilio_signature", return_value=True), \
            patch("whatsapp_media_adapter.download_whatsapp_media", return_value=b"bytes"), \
            patch("whatsapp_media_adapter.extract_whatsapp_media", return_value={
                "media_url": request_values["MediaUrl0"],
                "mime_type": "image/jpeg",
                "file_id": "SM-success",
            }), \
            patch("media_handler.handle_file_upload", return_value=success):
        response = app.app.test_client().post("/whatsapp", data=request_values)

    assert response.status_code == 200
    assert "status=COMPLETED" in caplog.text
    assert "success_evidence=True" in caplog.text


def test_meta_processing_failure_is_reported_without_changing_ack():
    normalized = {
        "text": "media received",
        "from": "+972500000000",
        "to": "+972511111111",
        "msg_id": "wamid-failure",
        "media": {
            "media_type": "image",
            "media_id": "media-1",
            "message_id": "wamid-failure",
            "filename": "",
        },
    }
    response_obj = SimpleNamespace(content=b"bytes", raise_for_status=lambda: None)
    patches = _common_app_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
            patch.object(app, "_validate_meta_signature", return_value=True), \
            patch.object(app, "_normalize_meta_payload", return_value=normalized), \
            patch("meta_whatsapp_media_adapter.get_meta_media_download_url", return_value="https://meta.test/media"), \
            patch("requests.get", return_value=response_obj), \
            patch.dict(os.environ, {"META_BUSINESS_TOKEN": "meta-test-token"}), \
            patch("media_handler.handle_file_upload", return_value=media_handler.MediaResult(
                ok=False,
                error=media_handler.MediaError("ASSET_SAVE_FAILED", "not persisted", True),
            )), \
            patch.object(app, "_flag_enabled", return_value=False):
        response = app.app.test_client().post(
            "/webhooks/meta/whatsapp",
            json={"ignored": "patched"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "received_no_outbound"
    assert body["media_processing"]["status"] == "FAILED"
    assert body["media_processing"]["success_evidence"] is False
    assert body["media_processing"]["error_code"] == "ASSET_SAVE_FAILED"


def test_meta_text_only_has_no_media_processing_result():
    normalized = {
        "text": "hello",
        "from": "+972500000000",
        "to": "+972511111111",
        "msg_id": "wamid-text",
        "media": None,
    }
    patches = _common_app_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
            patch.object(app, "_validate_meta_signature", return_value=True), \
            patch.object(app, "_normalize_meta_payload", return_value=normalized), \
            patch.object(app, "_flag_enabled", return_value=False):
        response = app.app.test_client().post(
            "/webhooks/meta/whatsapp",
            json={"ignored": "patched"},
        )

    assert response.status_code == 200
    assert response.get_json() == {"status": "received_no_outbound"}


def test_media_status_never_marks_failed_result_as_success():
    result = media_handler.media_processing_status(
        media_handler.MediaResult(
            ok=False,
            error=media_handler.MediaError("PROCESSING_FAILED", "failed", True),
        )
    )
    assert result.status == "FAILED"
    assert result.success_evidence is False
    assert result.retryable is True


def test_twilio_processing_failure_does_not_enter_other_success_path():
    request_values = {
        "NumMedia": "1",
        "MediaUrl0": "https://twilio.test/voice",
        "MediaContentType0": "audio/ogg",
        "MessageSid": "SM-voice-failure",
        "From": "whatsapp:+972500000000",
        "To": "whatsapp:+972511111111",
        "Body": "media received",
    }
    patches = _common_app_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
            patch.object(app, "_validate_twilio_signature", return_value=True), \
            patch("whatsapp_media_adapter.download_whatsapp_media", return_value=b"bytes"), \
            patch("whatsapp_media_adapter.extract_whatsapp_media", return_value={
                "media_url": request_values["MediaUrl0"],
                "mime_type": "audio/ogg",
                "file_id": "SM-voice-failure",
            }), \
            patch("media_handler.handle_voice_note", return_value=media_handler.MediaResult(
                ok=False,
                error=media_handler.MediaError("STT_FAILED", "transcription failed", True),
            )), \
            patch("media_handler.handle_file_upload") as file_handler:
        response = app.app.test_client().post("/whatsapp", data=request_values)

    assert response.status_code == 200
    file_handler.assert_not_called()
