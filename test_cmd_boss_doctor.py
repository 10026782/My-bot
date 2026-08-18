#!/usr/bin/env python3
"""
test_cmd_boss_doctor.py — owner-gate + wiring regression test for /boss_doctor.

/boss_doctor is a thin owner-only wrapper: authorize -> run_doctor() ->
format_report() -> reply. It must add no new checks, no mutation path, and
no secret exposure beyond what boss_doctor.py itself already guarantees
(covered separately by test_boss_doctor.py).
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
import boss_doctor as boss_doctor_module

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


def _identity(role: str):
    return type("I", (), {"role": role})()


# ══════════════════════════════════════════════════
# 1. Owner can run it
# ══════════════════════════════════════════════════

print("\n── owner can run /boss_doctor ─")

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))):
    mock_identity.return_value = _identity("owner")
    app.cmd_boss_doctor(_FakeMsg())

chk("owner gets exactly one reply", len(calls) == 1)
chk("reply goes to the requesting chat", calls and calls[0][0] == 12345)
chk("reply contains the BOSS Doctor header", calls and "BOSS Doctor" in calls[0][1])


# ══════════════════════════════════════════════════
# 2. Non-owner is rejected
# ══════════════════════════════════════════════════

print("\n── non-owner roles are rejected ─")

for role in ("partner", "manager", "employee", "lead", "guest", "readonly"):
    calls = []
    with patch("app.resolve_identity") as mock_identity, \
         patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
         patch("boss_doctor.run_doctor") as mock_run:
        mock_identity.return_value = _identity(role)
        app.cmd_boss_doctor(_FakeMsg())
    chk(f"role={role}: run_doctor() never called", mock_run.call_count == 0)
    chk(f"role={role}: gets the owner-only denial, not a report", len(calls) == 1 and "בעלים" in calls[0][1])

print("── identity=None is rejected ─")
calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch("boss_doctor.run_doctor") as mock_run:
    mock_identity.return_value = None
    app.cmd_boss_doctor(_FakeMsg())
chk("identity=None: run_doctor() never called", mock_run.call_count == 0)
chk("identity=None: gets the owner-only denial", len(calls) == 1 and "בעלים" in calls[0][1])


# ══════════════════════════════════════════════════
# 3 & 4. run_doctor() called exactly once; format_report() used for output
# ══════════════════════════════════════════════════

print("\n── run_doctor()/format_report() wiring ─")

_sentinel_report = boss_doctor_module.DoctorReport(checks=())
calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch("boss_doctor.run_doctor", return_value=_sentinel_report) as mock_run, \
     patch("boss_doctor.format_report", return_value="SENTINEL_REPORT_TEXT") as mock_format:
    mock_identity.return_value = _identity("owner")
    app.cmd_boss_doctor(_FakeMsg())

chk("run_doctor() called exactly once", mock_run.call_count == 1)
chk("format_report() called exactly once, with run_doctor()'s result", mock_format.call_count == 1 and mock_format.call_args[0][0] is _sentinel_report)
chk("the sent text is format_report()'s output, not something else", calls and calls[0][1] == "SENTINEL_REPORT_TEXT")


# ══════════════════════════════════════════════════
# 5. No mutation path from the command itself
# ══════════════════════════════════════════════════

print("\n── /boss_doctor never mutates anything ─")


def _boom(*a, **k):
    raise AssertionError("cmd_boss_doctor must never call a mutating function")


import feature_flags
import core.action_gateway as ag
import tools.dispatcher as dispatcher

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.object(feature_flags, "set_flag", _boom, create=True), \
     patch.object(feature_flags, "set_emergency_stop", _boom, create=True), \
     patch.object(dispatcher, "dispatch_tool", _boom, create=True):
    mock_identity.return_value = _identity("owner")
    app.cmd_boss_doctor(_FakeMsg())

chk("real run through poisoned mutation paths still succeeds (none were called)", len(calls) == 1)


# ══════════════════════════════════════════════════
# 6. No secrets in the command's output
# ══════════════════════════════════════════════════

print("\n── no secret leakage through the command reply ─")

secret = "SECRET_MARKER_CMD_BOSS_DOCTOR"
calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.dict(os.environ, {"AIRTABLE_API_KEY": secret}):
    mock_identity.return_value = _identity("owner")
    app.cmd_boss_doctor(_FakeMsg())

chk("secret env value never appears in the reply", calls and secret not in calls[0][1])


# ══════════════════════════════════════════════════
# 7. The command doesn't change Phase 1's own results
# ══════════════════════════════════════════════════

print("\n── command wiring does not change boss_doctor.run_doctor()'s own output ─")

direct_report = boss_doctor_module.format_report(boss_doctor_module.run_doctor())
calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))):
    mock_identity.return_value = _identity("owner")
    app.cmd_boss_doctor(_FakeMsg())
via_command = calls[0][1] if calls else None

chk("direct run_doctor()+format_report() matches the command's reply byte-for-byte",
    via_command == direct_report)


# ══════════════════════════════════════════════════
# 8. Regression: /status and owner-command routing still work
# ══════════════════════════════════════════════════

print("\n── regression: /status still owner-gated and end-to-end dispatch works ─")

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text, kw.get("parse_mode")))):
    mock_identity.return_value = _identity("owner")
    app.cmd_status(_FakeMsg())
chk("/status still replies for an owner", len(calls) >= 1)

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))):
    mock_identity.return_value = _identity("manager")
    app.cmd_status(_FakeMsg())
chk("/status still silently drops non-owner/admin (unchanged behavior)", len(calls) == 0)

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))):
    mock_identity.return_value = _identity("owner")

    update = telebot.types.Update.de_json({
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "t"},
            "text": "/boss_doctor",
        },
    })
    try:
        app.bot.process_new_updates([update])
        dispatch_raised = False
    except Exception:
        dispatch_raised = True

chk("real /boss_doctor dispatch via bot.process_new_updates() does not raise", dispatch_raised is False)
chk("real dispatch delivered a report", len(calls) == 1 and "BOSS Doctor" in calls[0][1])


print(f"\n{'='*40}")
print(f"cmd_boss_doctor tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
