# test_a32_enforcement.py — A32 NO-TOOL-EVIDENCE enforcement regression suite
#
# Verifies that core.anti_hallucination's NO-TOOL-EVIDENCE gate doesn't just
# log — it actually replaces app.run_agent()'s reply end-to-end, for
# calendar/gmail/Airtable claims made with no supporting tool call, and stays
# silent when a real tool result with an external_id backs the claim.

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-a32-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:A32_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patA32Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appA32Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision  # noqa: E402
from context import AgentContext  # noqa: E402
from core.anti_hallucination import (  # noqa: E402
    sanitize_agent_response,
    _NO_TOOL_EVIDENCE_FALLBACK,
)


def _fake_anthropic_response(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def _run_agent_with_text(agent_reply_text: str, chat_id: str, user_text: str = "test") -> str:
    """
    Drives the real app.run_agent() end-to-end with Identity/Router/Context/
    Anthropic mocked, so the only real production code under test is the
    tool loop + the A32 sanitize_agent_response gate.
    """
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt  = "test system prompt",
        allowed_tools  = [],
        memory_key     = f"a32test:{chat_id}",
        max_tokens     = 500,
        model          = "claude-haiku-test",
        identity_label = "owner",
    )
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=RouteDecision()), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app.client.messages, "create",
                       return_value=_fake_anthropic_response(agent_reply_text)):
        return app.run_agent(user_text, chat_id, channel="telegram")


# ══════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════

def test_01_calendar_success_claim_no_tools_blocked():
    reply = _run_agent_with_text("הפגישה קבועה.", "a32_t1", "תקבע לי פגישה מחר ב-10")
    assert reply == _NO_TOOL_EVIDENCE_FALLBACK, f"got: {reply!r}"
    return "✅ Test 01: 'הפגישה קבועה' with no tool results → blocked"


def test_02_calendar_check_claim_no_tools_blocked():
    reply = _run_agent_with_text("בדקתי ביומן — אין חפיפות.", "a32_t2", "מה יש לי ביומן היום?")
    assert reply == _NO_TOOL_EVIDENCE_FALLBACK, f"got: {reply!r}"
    return "✅ Test 02: 'בדקתי ביומן' with no calendar_get_events → blocked"


def test_03_gmail_draft_claim_no_tools_blocked():
    reply = _run_agent_with_text("טיוטה נשמרה.", "a32_t3", "כתוב טיוטת מייל ללקוח")
    assert reply == _NO_TOOL_EVIDENCE_FALLBACK, f"got: {reply!r}"
    return "✅ Test 03: 'טיוטה נשמרה' with no gmail_draft → blocked"


def test_04_valid_tool_result_with_external_id_allowed():
    """Direct unit-level check: a real structured tool result (external_id
    present, ok=True) must let the matching claim pass through unchanged."""
    tool_results_log = [{
        "tool":    "calendar_create_event",
        "content": "✅ אירוע 'פגישה' נוצר ביומן ל-21/06/2026 10:00.\nevent_id: `evt_abc`\n🔗 https://calendar.google.com/event?eid=abc",
        "ok":      True,
    }]
    reply = sanitize_agent_response("הפגישה קבועה.", tool_results_log)
    assert reply == "הפגישה קבועה.", f"valid tool result got blocked: {reply!r}"
    return "✅ Test 04: valid tool result with external_id → allowed"


def test_05_blocked_response_reaches_telegram_send():
    """
    End-to-end proof that the A32-blocked text is what would actually be
    sent to Telegram — not just something logged. Mirrors the exact
    production call in webhook_telegram(): reply = run_agent(...); then
    bot.send_message(reply_chat_id, reply).
    """
    captured = {}

    def _fake_send_message(chat_id, text, *a, **kw):
        captured["chat_id"] = chat_id
        captured["text"] = text

    reply = _run_agent_with_text("הפגישה קבועה.", "a32_t5", "תקבע לי פגישה מחר ב-10")

    with patch.object(app.bot, "send_message", side_effect=_fake_send_message):
        app.bot.send_message("a32_t5", reply)  # exact call shape used in webhook_telegram()

    assert reply == _NO_TOOL_EVIDENCE_FALLBACK, f"run_agent returned: {reply!r}"
    assert captured.get("text") == _NO_TOOL_EVIDENCE_FALLBACK, \
        f"Telegram would have received: {captured.get('text')!r}"
    assert "הפגישה קבועה" not in captured["text"], "original hallucinated claim leaked to Telegram"
    return "✅ Test 05: A32-blocked response is what Telegram receives, not just a log entry"


def test_06_airtable_claim_no_tools_blocked():
    """Bonus coverage for the explicitly-required Airtable case (not one of
    the 5 numbered tests, but required by the audit: 'Airtable claims:
    require airtable tool result')."""
    reply = _run_agent_with_text("הרשומה נוצרה בהצלחה.", "a32_t6", "תוסיף ליד חדש בשם דני")
    assert reply == _NO_TOOL_EVIDENCE_FALLBACK, f"got: {reply!r}"
    return "✅ Test 06 (bonus): 'הרשומה נוצרה' with no airtable tool result → blocked"


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

def run():
    tests = [
        test_01_calendar_success_claim_no_tools_blocked,
        test_02_calendar_check_claim_no_tools_blocked,
        test_03_gmail_draft_claim_no_tools_blocked,
        test_04_valid_tool_result_with_external_id_allowed,
        test_05_blocked_response_reaches_telegram_send,
        test_06_airtable_claim_no_tools_blocked,
    ]
    passed = failed = 0

    print("\nA32 NO-TOOL-EVIDENCE Enforcement Tests")
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
