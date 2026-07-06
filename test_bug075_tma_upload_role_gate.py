# test_bug075_tma_upload_role_gate.py — BUG-075: POST /api/tma/upload had
# @require_tma_auth (authentication) but no role check, unlike every other
# TMA write endpoint (which all gate on Role.OWNER/MANAGER/PARTNER). Any
# resolved identity — including lead/guest/readonly — could call it once
# FEATURE_MEDIA_UPLOAD is enabled.
#
# tma_upload() is called directly via its __wrapped__ (the function
# functools.wraps preserves under @require_tma_auth) so the role gate can be
# exercised without needing a real Telegram initData HMAC signature — the
# decorator's own auth behavior is untouched by this fix and is not what's
# under test here.

import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import sys
from dataclasses import dataclass

from flask import Flask

import feature_flags
import tma_api
from identity import Role

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


@dataclass
class MockIdentity:
    role: str
    user_id: str = "u1"
    domain_id: str = "general"


_upload = tma_api.tma_upload.__wrapped__  # raw function, bypasses @require_tma_auth's HMAC check
_app = Flask(__name__)


def _call(identity):
    with _app.test_request_context(
        "/api/tma/upload", method="POST", content_type="multipart/form-data",
    ):
        return _upload(identity=identity)


# ══════════════════════════════════════════════════
# 4. Feature flag off → unchanged "coming_soon" response, regardless of role
# (existing behavior — must not regress).
# ══════════════════════════════════════════════════
print("\n── BUG-075: FEATURE_MEDIA_UPLOAD off — unchanged disabled response ──")
feature_flags.set_flag("FEATURE_MEDIA_UPLOAD", False)
try:
    resp, status = _call(MockIdentity(role=Role.OWNER))
    chk("flag off: status 200", status == 200)
    chk("flag off: coming_soon=True even for owner", resp.get_json().get("coming_soon") is True)

    resp2, status2 = _call(MockIdentity(role=Role.GUEST))
    chk("flag off: coming_soon=True for guest too (unchanged from before this fix)",
        resp2.get_json().get("coming_soon") is True)
finally:
    feature_flags.set_flag("FEATURE_MEDIA_UPLOAD", False)


# ══════════════════════════════════════════════════
# 1. guest/lead/readonly cannot upload once the flag is enabled.
# ══════════════════════════════════════════════════
print("\n── BUG-075: FEATURE_MEDIA_UPLOAD on — unauthorized roles denied ──")
feature_flags.set_flag("FEATURE_MEDIA_UPLOAD", True)
try:
    for role in (Role.GUEST, Role.LEAD, Role.READONLY, Role.EMPLOYEE):
        result = _call(MockIdentity(role=role))
        resp, status = result
        chk(f"role={role}: forbidden (403), not authenticated-but-unchecked", status == 403)
        chk(f"role={role}: safe JSON error body", resp.get_json() == {"error": "forbidden"})

    # ══════════════════════════════════════════════════
    # 2/3. owner/manager/partner pass the role gate — they reach the actual
    # upload logic (proven by getting past 403 into the "missing file" 400,
    # not by the full Drive/Airtable upload pipeline, which is unrelated to
    # this authorization fix).
    # ══════════════════════════════════════════════════
    print("\n── BUG-075: owner/manager/partner pass the role gate ──")
    for role in (Role.OWNER, Role.MANAGER, Role.PARTNER):
        resp, status = _call(MockIdentity(role=role))
        chk(f"role={role}: not forbidden — passes role gate", status != 403)
        chk(f"role={role}: reaches upload logic (400 missing file, not 403)", status == 400)
finally:
    feature_flags.set_flag("FEATURE_MEDIA_UPLOAD", False)


print("\n" + "=" * 50)
print(f"BUG-075 tma_upload role gate tests: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
