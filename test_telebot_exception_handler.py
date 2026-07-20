#!/usr/bin/env python3
"""
test_telebot_exception_handler.py — regression test for a production
incident (20/07/2026, alert context="command_dispatch").

app.py used to set `bot.exception_handler = handle_telebot_error`, a bare
function. telebot's TeleBot._handle_exception() calls
`self.exception_handler.handle(exception)` — it requires an OBJECT with a
.handle() method (telebot.ExceptionHandler), not a plain callable. That
mistake made the lookup itself raise
`AttributeError: 'function' object has no attribute 'handle'`, which then
propagated in place of whatever the REAL original exception inside a
/command handler was — every command-handler bug since this was introduced
got reported as this same useless AttributeError instead of its actual
cause. Fixed by implementing a proper telebot.ExceptionHandler subclass.
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
logging.disable(logging.CRITICAL)  # this test intentionally triggers real ERROR-level logging

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


print("\n── structural: bot.exception_handler shape ─")

chk(
    "bot.exception_handler is an OBJECT with a .handle() method, not a bare function "
    "(the exact shape telebot._handle_exception() requires)",
    hasattr(app.bot.exception_handler, "handle") and callable(app.bot.exception_handler.handle),
)
chk(
    "bot.exception_handler is a telebot.ExceptionHandler subclass instance",
    isinstance(app.bot.exception_handler, telebot.ExceptionHandler),
)


print("\n── end-to-end: real command-handler exception surfaces ─")


@app.bot.message_handler(commands=["__test_boom__"])
def _boom(message):
    raise ValueError("simulated real bug inside a command handler")


def _dispatch(text: str):
    update = telebot.types.Update.de_json({
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "is_bot": False, "first_name": "t"},
            "text": text,
        },
    })
    app.bot.process_new_updates([update])


try:
    _dispatch("/__test_boom__")
    chk("real ValueError from a command handler propagates out of process_new_updates()", False)
except ValueError as e:
    chk(
        "real ValueError from a command handler propagates unmasked "
        "(this is what app.py's command_dispatch except-block/report_error sees)",
        str(e) == "simulated real bug inside a command handler",
    )
except AttributeError as e:
    chk(f"REGRESSION — masking bug is back: {e}", False)


@app.bot.message_handler(commands=["__test_ok__"])
def _ok(message):
    pass


try:
    _dispatch("/__test_ok__")
    chk("a command handler that raises nothing dispatches cleanly", True)
except Exception as e:
    chk(f"a command handler that raises nothing dispatches cleanly (got {type(e).__name__}: {e})", False)


print(f"\n{'='*40}")
print(f"telebot exception_handler tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
