import os
import logging
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-c02-c04-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:C02_C04_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patC02C04Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appC02C04Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app
import media_handler
from context import AgentContext
from core.router.route_decision import RouteDecision
from identity import Identity, Role


SENTINEL = "SENSITIVE_SENTINEL_123"


def test_voice_logs_metadata_without_transcript(caplog):
    caplog.set_level(logging.DEBUG)
    stt = SimpleNamespace(
        ok=True,
        raw_transcript=SENTINEL,
        normalized_transcript=SENTINEL,
        error=None,
    )
    with patch.object(media_handler, "transcribe", return_value=stt), \
         patch.object(media_handler, "_log_unhandled_voice_note"):
        result = media_handler.handle_voice_note(
            b"audio", "audio/ogg", "log-test-voice", "user-1", "general", "owner-1",
        )

    assert result.ok is True
    assert SENTINEL not in caplog.text
    assert "transcription analyzed" in caplog.text
    assert "source=telegram" in caplog.text
    assert "chars=" in caplog.text
    assert "action_requested=False" in caplog.text


def _tool_response():
    return SimpleNamespace(
        content=[SimpleNamespace(
            type="tool_use", name="test_read_tool", id="tool-1",
            input={"secret": SENTINEL, "label": "private value"},
        )],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )


def _text_response():
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="tool completed")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )


def test_tool_logs_metadata_without_input_or_result(caplog):
    caplog.set_level(logging.DEBUG)
    import emergency_stop_test_support
    emergency_stop_test_support.configure_all_clear_emergency_stop()
    identity = Identity(user_id="tool-log-user", role=Role.OWNER)
    ctx = AgentContext(
        system_prompt="test", allowed_tools=[], memory_key="tool-log-user",
        max_tokens=100, model="claude-haiku-test", identity_label="owner",
    )
    meta = SimpleNamespace(read_only=True, requires_approval=False)
    raw_result = {"ok": True, "user_message": SENTINEL, "private": "result value"}

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=RouteDecision()), \
         patch.object(app, "build_context", return_value=ctx), \
         patch.object(app.client.messages, "create", side_effect=[_tool_response(), _text_response()]), \
         patch.object(app, "get_tool_meta", return_value=meta), \
         patch.object(app, "enforce", return_value=meta), \
         patch.object(app, "dispatch_tool", return_value=raw_result), \
         patch.object(app, "validate_tool_output", return_value=raw_result), \
         patch.object(app.bot, "send_chat_action", side_effect=RuntimeError(SENTINEL)), \
         patch.object(app, "_capture_last_tool_result"), \
         patch.object(app, "_build_tool_context", return_value=""), \
         patch.object(app, "_build_action_resolution_context", return_value=""):
        reply = app.run_agent(SENTINEL, "tool-log-user")

    assert reply == "tool completed"
    assert SENTINEL not in caplog.text
    assert "name=test_read_tool" in caplog.text
    assert "input_key_count=2" in caplog.text
    assert "result_type=dict" in caplog.text
    assert "typing indicator failed error_type=RuntimeError" in caplog.text


def test_meta_reply_log_contains_metadata_without_reply_content(caplog):
    caplog.set_level(logging.INFO, logger="app")
    sentinel = "SENSITIVE_REPLY_SENTINEL_9F31"
    normalized = {
        "text": "hello",
        "from": "+972500000000",
        "to": "+972511111111",
        "msg_id": "wamid-log-test",
        "media": None,
    }
    with patch.object(app, "_validate_meta_signature", return_value=True), \
         patch.object(app, "_normalize_meta_payload", return_value=normalized), \
         patch.object(app, "_apply_ingress_context_gate"), \
         patch.object(app, "resolve_identity", return_value=SimpleNamespace(memory_key="boss_hq:log-test")), \
         patch.object(app.idempotency, "is_duplicate", return_value=False), \
         patch.object(app, "_channel_domain", return_value="general"), \
         patch.object(app, "_flag_enabled", side_effect=lambda name: name == "META_OUTBOUND_ENABLED"), \
         patch.object(app, "run_agent", return_value=sentinel) as run_agent:
        response = app.app.test_client().post(
            "/webhooks/meta/whatsapp", json={"ignored": "patched"},
        )

    assert response.status_code == 200
    assert response.get_json() == {"status": "received"}
    run_agent.assert_called_once()
    assert sentinel not in caplog.text
    assert "result_type=str" in caplog.text
    assert f"reply_length={len(sentinel)}" in caplog.text
