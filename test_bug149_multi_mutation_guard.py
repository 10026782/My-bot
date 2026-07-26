#!/usr/bin/env python3
"""
test_bug149_multi_mutation_guard.py — BUG-149 regression coverage for the
deterministic MULTI_MUTATION_CONTEXT_MISMATCH pre-scan guard in
app.run_agent()'s tool loop.

Drives the real app.run_agent() end-to-end with Identity/Router/Context/
Anthropic mocked (same harness shape as test_a32_enforcement.py), so the
only real production code under test is the tool loop + the new guard.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug149-guard-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG149_GUARD_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug149GuardTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug149GuardTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

import event_bus  # noqa: E402
from context import AgentContext  # noqa: E402
from core.action_gateway import action_gateway  # noqa: E402
from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision  # noqa: E402


def _fake_ctx(memory_key: str) -> AgentContext:
    return AgentContext(
        system_prompt="test system prompt", allowed_tools=[], memory_key=memory_key,
        max_tokens=500, model="claude-haiku-test", identity_label="owner",
    )


def _fake_response(tool_calls: list[tuple[str, dict]], text_before: str | None = None):
    blocks = []
    if text_before:
        blocks.append(SimpleNamespace(type="text", text=text_before))
    for i, (name, inputs) in enumerate(tool_calls):
        blocks.append(SimpleNamespace(type="tool_use", id=f"tu_{i}", name=name, input=inputs))
    return SimpleNamespace(content=blocks, usage=SimpleNamespace(input_tokens=10, output_tokens=10))


passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
print("\n── 6c/6d: CANONICAL → REJECT → APPROVE in one response creates zero contracts, ──")
print("── not the first — and the reply says nothing was saved, restate the request ──")

identity = Identity(
    user_id="bug149-guard-a", role=Role.OWNER, display_name="bug149-guard-a",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="bug149-guard-a",
)

_resp = _fake_response([
    ("airtable_add", {"table": "Tasks", "fields": {"כותרת המשימה": "PM460-RETEST-CANONICAL"}}),
    ("airtable_add", {"table": "Tasks", "fields": {"כותרת המשימה": "PM460-RETEST-REJECT"}}),
    ("airtable_add", {"table": "Tasks", "fields": {"כותרת המשימה": "PM460-RETEST-APPROVE"}}),
], text_before="אני יוצר את שלוש המשימות ב-Airtable:")
# The model's plausible follow-up after seeing 3 identical "not saved,
# resend" tool_results for its own 3 tool_use blocks — a real model would
# relay this, since it's the only information available to it about what
# happened. Modeling that as a second, distinct call response (not a fixed
# return_value repeated forever) so the loop terminates with actual final
# text instead of hitting MAX_TOOL_TURNS's generic fallback message.
_resp_followup = _fake_response(
    [], text_before="⛔ הבקשה כללה כמה פעולות-כתיבה בו-זמנית ולא נשמרה אף אחת מהן. אנא שלח מחדש בקשה אחת בלבד.",
)

_contracts_before = len(action_gateway._ledger._store)

with patch.object(app, "resolve_identity", return_value=identity), \
     patch.object(app, "_safe_route", return_value=RouteDecision()), \
     patch.object(app, "build_context", return_value=_fake_ctx(f"bug149guard:{identity.user_id}")), \
     patch.object(app.client.messages, "create", side_effect=[_resp, _resp_followup]) as mock_create, \
     patch.object(app, "bot", MagicMock()), \
     patch.object(action_gateway, "propose_action") as mock_propose, \
     patch.object(app, "dispatch_tool") as mock_dispatch, \
     patch.object(event_bus.bus, "request_approval") as mock_pending, \
     patch.object(action_gateway, "_tool_executor") as mock_executor:
    reply = app.run_agent(
        "צור משימה PM460-RETEST-APPROVE עד ל-2026-07-27. תיאור: בדיקת approve לאחר deploy",
        identity.user_id, channel="telegram",
    )

chk("propose_action() is called zero times", mock_propose.call_count == 0)
chk("dispatch_tool() is called zero times", mock_dispatch.call_count == 0)
chk("event_bus.bus.request_approval() (pending-event registration) is called zero times",
    mock_pending.call_count == 0)
chk("the tool executor is invoked zero times", mock_executor.call_count == 0)

# Assert on the ACTUAL, deterministic tool_result content the code sent
# back to the model on the second call — not on the mocked model's own
# made-up final_reply text (that's the model's choice, not code behavior;
# testing it would only prove the test's own fixture, not the guard).
_second_call_messages = mock_create.call_args_list[1].kwargs["messages"]
_tool_result_block = _second_call_messages[-1]["content"]
_mismatch_contents = [b["content"] for b in _tool_result_block if isinstance(b, dict)]
chk("every tool_use_id got a tool_result (Anthropic API requirement)",
    len(_tool_result_block) == 3)
chk("the deterministic tool_result states nothing was saved",
    all("לא נשמרה" in c for c in _mismatch_contents))
chk("the deterministic tool_result asks the user to resend a single request",
    all("שלח מחדש" in c for c in _mismatch_contents))
chk("no ActionContract exists afterward (ledger unchanged)",
    len(action_gateway._ledger._store) == _contracts_before)
chk("reply does NOT claim any task was created",
    "✅ בוצע" not in reply and "PM460-RETEST-CANONICAL" not in reply)


# ══════════════════════════════════════════════════════════════════
print("\n── 6d (restated): the FIRST (stale) proposal specifically does not win ──")

identity_b = Identity(
    user_id="bug149-guard-b", role=Role.OWNER, display_name="bug149-guard-b",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="bug149-guard-b",
)
_resp_b = _fake_response([
    ("airtable_add", {"table": "Tasks", "fields": {"כותרת המשימה": "STALE-FIRST"}}),
    ("airtable_add", {"table": "Tasks", "fields": {"כותרת המשימה": "REAL-CURRENT-REQUEST"}}),
])
with patch.object(app, "resolve_identity", return_value=identity_b), \
     patch.object(app, "_safe_route", return_value=RouteDecision()), \
     patch.object(app, "build_context", return_value=_fake_ctx(f"bug149guard:{identity_b.user_id}")), \
     patch.object(app.client.messages, "create", return_value=_resp_b), \
     patch.object(app, "bot", MagicMock()), \
     patch.object(action_gateway, "propose_action") as mock_propose_b:
    reply_b = app.run_agent("צור משימה REAL-CURRENT-REQUEST", identity_b.user_id, channel="telegram")

chk("neither the stale-first nor the real-current tool_use is proposed",
    mock_propose_b.call_count == 0)
chk("the STALE task title never appears in the reply as an executed/created action",
    "✅ בוצע" not in reply_b)


# ══════════════════════════════════════════════════════════════════
print("\n── log line: MULTI_MUTATION_CONTEXT_MISMATCH is emitted, matching the mismatch ──")

with patch.object(app, "resolve_identity", return_value=identity), \
     patch.object(app, "_safe_route", return_value=RouteDecision()), \
     patch.object(app, "build_context", return_value=_fake_ctx(f"bug149guard:{identity.user_id}2")), \
     patch.object(app.client.messages, "create", return_value=_resp), \
     patch.object(app, "bot", MagicMock()), \
     patch.object(action_gateway, "propose_action"), \
     patch.object(app.logger, "warning") as mock_warn:
    app.run_agent("צור משימה שלישית", identity.user_id + "-log", channel="telegram")

chk("MULTI_MUTATION_CONTEXT_MISMATCH is logged at WARNING level",
    any("MULTI_MUTATION_CONTEXT_MISMATCH" in str(c) for c in mock_warn.call_args_list))


# ══════════════════════════════════════════════════════════════════
print("\n── 6g: one mutation + independent reads still follows the normal approval flow ──")

identity_c = Identity(
    user_id="bug149-guard-c", role=Role.OWNER, display_name="bug149-guard-c",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="bug149-guard-c",
)
_resp_c = _fake_response([
    ("airtable_get", {"table": "Tasks"}),
    ("airtable_add", {"table": "Tasks", "fields": {"כותרת המשימה": "PM460-SINGLE-VALID"}}),
])
_contracts_before_c = len(action_gateway._ledger._store)

with patch.object(app, "resolve_identity", return_value=identity_c), \
     patch.object(app, "_safe_route", return_value=RouteDecision()), \
     patch.object(app, "build_context", return_value=_fake_ctx(f"bug149guard:{identity_c.user_id}")), \
     patch.object(app.client.messages, "create", return_value=_resp_c), \
     patch.object(app, "bot", MagicMock()), \
     patch.object(app, "dispatch_tool", return_value="✅ 3 משימות נמצאו") as mock_dispatch_c:
    reply_c = app.run_agent(
        "צור משימה PM460-SINGLE-VALID עד ל-2026-07-27", identity_c.user_id, channel="telegram",
    )

chk("the single mutation IS proposed (ledger grew by exactly one contract)",
    len(action_gateway._ledger._store) == _contracts_before_c + 1)
chk("the read-only tool (airtable_get) was actually dispatched, not blocked",
    mock_dispatch_c.call_count == 1)
chk("reply reflects a normal queued-for-approval turn, not the mismatch message",
    "לא נשמרה" not in reply_c)


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"BUG-149 multi-mutation guard regression: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
