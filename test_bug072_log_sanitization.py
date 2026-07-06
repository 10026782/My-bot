# test_bug072_log_sanitization.py — BUG-072: app.py logged raw chat_id /
# user_chat_id / owner_chat_id / user_id (phone numbers, Telegram user ids)
# in plaintext across many log lines. Fixed by routing every such value
# through _sanitize_id() before it reaches a logger call.
#
# Two levels of coverage:
#   1. Unit-level: _sanitize_id() behaves as a stable, non-reversible
#      fingerprint (same input -> same output, output != input).
#   2. Static/source-level (mirrors smoke_tests.py's style): grep app.py's
#      source for the exact raw-id logging patterns previously reported in
#      BUG_AUDIT_LOG.md / AI_CONTEXT.md and assert none remain unsanitized.
#      This is a regression guard against the pattern creeping back in.

import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import re
import sys

import app as _app_mod

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# 1. _sanitize_id() unit behavior
# ══════════════════════════════════════════════════
print("\n── BUG-072: _sanitize_id() unit behavior ──")

fp1 = _app_mod._sanitize_id("+972501234567")
fp2 = _app_mod._sanitize_id("+972501234567")
fp3 = _app_mod._sanitize_id("7228089151")

chk("_sanitize_id: same input -> same fingerprint", fp1 == fp2)
chk("_sanitize_id: different input -> different fingerprint", fp1 != fp3)
chk("_sanitize_id: fingerprint does not contain the raw phone number", "972501234567" not in fp1)
chk("_sanitize_id: fingerprint does not contain the raw chat id", "7228089151" not in fp3)
chk("_sanitize_id: empty/None input handled safely", _app_mod._sanitize_id("") == "?" and _app_mod._sanitize_id(None) == "?")


# ══════════════════════════════════════════════════
# 2. Static source guard — no raw chat_id/user_id left unsanitized in a
# logger call. Mirrors the exact variable names BUG-072 reported.
# ══════════════════════════════════════════════════
print("\n── BUG-072: static source guard — no raw id left in app.py logger calls ──")

with open("app.py", encoding="utf-8") as f:
    _src = f.read()

_RAW_ID_PATTERN = re.compile(
    r"\{(chat_id|user_chat_id|owner_chat_id|sender_user_id|approver_chat_id"
    r"|identity\.user_id|approver_identity\.user_id|user_id)\}"
)
_offenders = [
    (lineno, line)
    for lineno, line in enumerate(_src.splitlines(), 1)
    if "logger." in line and _RAW_ID_PATTERN.search(line)
]
chk(
    "no unsanitized raw chat_id/user_id in any app.py logger.* call",
    len(_offenders) == 0,
)
if _offenders:
    for lineno, line in _offenders:
        print(f"    offending line {lineno}: {line.strip()}")

chk(
    "_sanitize_id helper is actually used at least once (fix is wired in, not just defined)",
    _src.count("_sanitize_id(") >= 10,
)


print("\n" + "=" * 50)
print(f"BUG-072 log sanitization tests: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
