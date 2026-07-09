# test_bug091_preflight_no_pending_approval.py — BUG-091 DoD #1/#2.
#
# A tool call that enforce_leads_write_gate() will provably block must never
# become a pending approval at all — previously nothing stopped it from
# being queued, producing the observed "אושר אך נכשל בביצוע" sequence
# (approve a doomed action, only find out it fails after the fact). This
# drives the real app.run_agent() tool loop end-to-end (Identity/Router/
# Context/Anthropic mocked) to prove:
#   1. Claude requesting airtable_update on Leads (source=agent) is blocked
#      immediately, before any pending approval is created.
#   2. bus.request_approval() (the pending-approval queue) is never called.
#   3. The user-facing message is the gate's message, not "⏳ אישור נדרש".

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug091-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG091_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug091Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug091Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
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


def _run_agent_leads_update(chat_id: str):
    """Drives a normal (not Restricted) Agent turn where Claude's tool_use
    requests an airtable_update on Leads — meta.requires_approval=True for
    this tool, so this exercises the new preflight inside the approval-gate
    branch, not the earlier route.tool_allowed=False branch."""
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test system prompt", allowed_tools=[],
        memory_key=f"bug091test:{chat_id}", max_tokens=500,
        model="claude-haiku-test", identity_label="owner",
    )
    normal_route = RouteDecision(handler=Handler.AGENT, tool_allowed=True)

    captured_messages: list = []

    def _capture_create(**kwargs):
        captured_messages.append(kwargs.get("messages"))
        if len(captured_messages) == 1:
            return _fake_tool_use_response(
                "airtable_update",
                {"table": "Leads", "record_id": "recBUG091test1234", "fields": {"status": "contacted"}},
            )
        return _fake_text_response("קיבלתי.")

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=normal_route), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app.client.messages, "create", side_effect=_capture_create), \
         patch("event_bus.bus.request_approval") as mock_request_approval:
        app.run_agent("עדכן ליד קיים — הלל זקין מעוניין שיחזרו אליו", chat_id, channel="telegram")

    second_call_messages = captured_messages[1]
    tool_result_turn = second_call_messages[-1]["content"]
    return tool_result_turn, mock_request_approval


result, mock_request_approval = _run_agent_leads_update("bug091_t1")

chk("tool loop produced exactly one tool_result for the blocked airtable_update", len(result) == 1)

content = result[0]["content"]
chk("blocked at preflight — message is the LeadsWriteGate block, not '⏳ אישור נדרש'",
    "כתיבה ישירה ל-Leads חסומה" in content and "אישור" not in content)

chk("BUG-091 DoD #2: bus.request_approval() was NEVER called — no pending approval created",
    mock_request_approval.call_count == 0)

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
