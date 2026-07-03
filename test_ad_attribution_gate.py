#!/usr/bin/env python3
# test_ad_attribution_gate.py — BUG-057 regression test
#
# LL-14 root cause: app.py called ad_attribution's _inject_utm() unconditionally
# on every inbound WhatsApp message, regardless of the AD_ATTRIBUTION flag, and
# swallowed the resulting Airtable write failure at logger.debug level (the
# utm_source/utm_medium/utm_campaign/platform fields don't exist on the live
# Leads table). This test proves the gate added in app.py's
# _webhook_whatsapp_impl() actually works: AD_ATTRIBUTION off (the default)
# means _inject_utm is never called; on means it is.

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug057-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG057_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug057Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug057Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
import feature_flags  # noqa: E402
from identity import Identity, Role  # noqa: E402


def _invoke_webhook_with_flag(ad_attribution_on: bool) -> MagicMock:
    """
    Drives app._webhook_whatsapp_impl() end-to-end with signature check,
    idempotency, identity resolution, the furniture-funnel intercept, and the
    customer output gateway all mocked — so the only real production code
    under test is the `_inject_utm and _flag_enabled("AD_ATTRIBUTION")` gate
    itself. Returns the mock standing in for ad_attribution's
    inject_source_to_incoming_lead.
    """
    feature_flags.set_flag("AD_ATTRIBUTION", ad_attribution_on)
    fake_identity = Identity(user_id="+972500000000", role=Role.LEAD)
    inject_mock = MagicMock(return_value=None)

    try:
        with app.app.test_request_context(
            "/whatsapp", method="POST",
            data={
                "Body":      "שלום, מתעניין בדירה",
                "From":      "whatsapp:+972500000000",
                "To":        "whatsapp:+972500000001",
                "MessageSid": "SMtest_bug057",
            },
        ), \
             patch.object(app, "_validate_twilio_signature", return_value=True), \
             patch.object(app.idempotency, "is_duplicate", return_value=False), \
             patch.object(app, "resolve_identity", return_value=fake_identity), \
             patch.object(app, "_inject_utm", inject_mock), \
             patch("furniture_lead_funnel.handle_furniture_lead_message",
                   return_value="stub reply — funnel intercept stops the test before run_agent"), \
             patch("core.output_gateway.send_outbound",
                   return_value=MagicMock(status="APPROVED")):
            app._webhook_whatsapp_impl()
    finally:
        feature_flags._RUNTIME.pop("AD_ATTRIBUTION", None)

    return inject_mock


def test_01_ad_attribution_off_inject_utm_not_called():
    inject_mock = _invoke_webhook_with_flag(ad_attribution_on=False)
    assert inject_mock.call_count == 0, f"expected 0 calls, got {inject_mock.call_count}"
    return "✅ Test 01: AD_ATTRIBUTION off (default) → _inject_utm not called"


def test_02_ad_attribution_on_inject_utm_called():
    inject_mock = _invoke_webhook_with_flag(ad_attribution_on=True)
    assert inject_mock.call_count == 1, f"expected 1 call, got {inject_mock.call_count}"
    return "✅ Test 02: AD_ATTRIBUTION on → _inject_utm called"


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

def run() -> bool:
    tests = [
        test_01_ad_attribution_off_inject_utm_not_called,
        test_02_ad_attribution_on_inject_utm_called,
    ]
    passed = failed = 0

    print("\nBUG-057 AD_ATTRIBUTION Gate Regression Tests")
    print("═" * 45)

    for t in tests:
        try:
            msg = t()
            print(msg)
            passed += 1
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {t.__name__} EXCEPTION: {e}")
            failed += 1

    print(f"\n{'═' * 45}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
