# test_restricted_tool_fake_forward_message.py — regression test for the
# fake-forwarding claim previously in app.py's Restricted-flow tool loop.
#
# When route.tool_allowed=False (Handler.RESTRICTED/BLOCK/ENGINEERING_NOTE/
# Tier-4), a blocked tool call used to get a synthetic tool_result claiming
# "הבקשה התקבלה ותועבר לטיפול." (request received, will be forwarded for
# handling) — but route.notify_owner is set and never consumed anywhere, so
# no forwarding mechanism actually exists. Fixed to say only what's true:
# "הבקשה נרשמה במערכת." This test drives the real app.run_agent() tool loop
# end-to-end (Identity/Router/Context/Anthropic mocked) to prove the honest
# message is what actually reaches the model/user, not just what's in the
# source file.

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-restricted-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:RESTRICTED_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patRestrictedTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appRestrictedTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision, Handler  # noqa: E402
from context import AgentContext  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _fake_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "toolu_1"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name=tool_name, input=tool_input, id=tool_id)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def _fake_text_response(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def _run_restricted_turn(chat_id: str) -> list:
    """
    Drives app.run_agent() with a RouteDecision matching the real Restricted
    flow (handler=AGENT, tool_allowed=False, restricted=True, notify_owner=True
    — exactly what core/router/router.py produces for Handler.RESTRICTED),
    Claude attempting one tool call. Returns the tool_result content list the
    real tool loop built for that blocked call.
    """
    identity = Identity(user_id=chat_id, role=Role.LEAD)
    fake_ctx = AgentContext(
        system_prompt  = "test system prompt",
        allowed_tools  = [],
        memory_key     = f"restrictedtest:{chat_id}",
        max_tokens     = 500,
        model          = "claude-haiku-test",
        identity_label = "lead",
    )
    restricted_route = RouteDecision(
        handler=Handler.AGENT, restricted=True, notify_owner=True, tool_allowed=False,
    )

    captured_messages: list = []

    def _capture_create(**kwargs):
        captured_messages.append(kwargs.get("messages"))
        if len(captured_messages) == 1:
            return _fake_tool_use_response("airtable_get", {"table": "Leads"})
        return _fake_text_response("קיבלתי.")

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=restricted_route), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app.client.messages, "create", side_effect=_capture_create):
        app.run_agent("שלח מייל ללקוח", chat_id, channel="telegram")

    # Second create() call's messages includes the tool_result block the
    # tool loop appended after the first (blocked) tool_use turn.
    second_call_messages = captured_messages[1]
    tool_result_turn = second_call_messages[-1]["content"]
    return tool_result_turn


result = _run_restricted_turn("restricted_t1")

chk("tool loop produced exactly one tool_result for the blocked call", len(result) == 1)

content = result[0]["content"]
chk(
    "blocked-tool tool_result no longer claims a forwarding that doesn't exist",
    content != "הבקשה התקבלה ותועבר לטיפול.",
)
chk(
    "blocked-tool tool_result says only what's true (received, logged)",
    content == "הבקשה נרשמה במערכת.",
)

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
