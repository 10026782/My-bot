#!/usr/bin/env python3
"""
test_cmd_status_markdown_fallback.py — BUG-121 regression test.

Root cause of the 20/07/2026 07:55 production incident (context=
command_dispatch, masked by BUG-120): /status sent format_startup_message()
via bot.send_message(..., parse_mode="Markdown") with no error handling.
That message embeds raw environment-variable names (e.g. GOOGLE_CLIENT_ID,
OWNER_TELEGRAM_ID) — Telegram's legacy Markdown parser can choke on their
underscores and return a 400 "Can't parse entities" error, which telebot
raises as ApiTelegramException. Confirmed via a real /status run by the
owner at 07:55, immediately reproduced locally.

Fixed with a plain-text retry fallback in cmd_status() so /status still
gets delivered instead of raising uncaught out of the command handler.
"""

from __future__ import annotations

import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import logging
logging.disable(logging.CRITICAL)

from unittest.mock import patch, MagicMock

import telebot
import app

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


class _FakeUser:
    id = 1


class _FakeChat:
    id = 12345


class _FakeMsg:
    from_user = _FakeUser()
    chat = _FakeChat()


def _markdown_parse_error():
    return telebot.apihelper.ApiTelegramException(
        "sendMessage", None,
        {"error_code": 400, "description": "Bad Request: can't parse entities: Can't find end of the entity starting at byte offset 42"},
    )


print("\n── cmd_status(): Markdown parse failure -> plain-text fallback ─")

calls = []


def _send_markdown_fails(chat_id, text, parse_mode=None, **kw):
    calls.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
    if parse_mode == "Markdown":
        raise _markdown_parse_error()
    return MagicMock()


calls.clear()
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=_send_markdown_fails):
    mock_identity.return_value = type("I", (), {"role": "owner"})()
    app.cmd_status(_FakeMsg())

chk("retries exactly once after the Markdown send fails", len(calls) == 2)
chk("first attempt used parse_mode=Markdown", calls and calls[0]["parse_mode"] == "Markdown")
chk("fallback attempt sent as plain text (no parse_mode)", len(calls) > 1 and calls[1]["parse_mode"] is None)
chk("fallback sends the same message body as the failed attempt", len(calls) > 1 and calls[0]["text"] == calls[1]["text"])
chk("fallback goes to the same chat_id", len(calls) > 1 and calls[0]["chat_id"] == calls[1]["chat_id"] == 12345)


print("\n── cmd_status(): Markdown send succeeds -> no fallback needed ─")

calls.clear()


def _send_markdown_ok(chat_id, text, parse_mode=None, **kw):
    calls.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
    return MagicMock()


with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=_send_markdown_ok):
    mock_identity.return_value = type("I", (), {"role": "owner"})()
    app.cmd_status(_FakeMsg())

chk("happy path: exactly one send, no retry", len(calls) == 1)


print("\n── end-to-end: real dispatch_tool path via process_new_updates() ──")

calls.clear()
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=_send_markdown_fails):
    mock_identity.return_value = type("I", (), {"role": "owner"})()

    update = telebot.types.Update.de_json({
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "t"},
            "text": "/status",
        },
    })
    try:
        app.bot.process_new_updates([update])
        dispatch_raised = False
    except Exception:
        dispatch_raised = True

chk("real /status dispatch via bot.process_new_updates() no longer raises out "
    "(previously: ApiTelegramException masked by BUG-120's AttributeError)",
    dispatch_raised is False)
chk("real dispatch still delivered the plain-text fallback", len(calls) == 2 and calls[1]["parse_mode"] is None)


print(f"\n{'='*40}")
print(f"cmd_status Markdown fallback tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
