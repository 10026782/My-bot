#!/usr/bin/env python3
"""
test_first_pending_notification_failure_suppression.py — closes the
"missing test" item from the PR #546 staging validation report (03/08/2026):
fault injection for a failed FIRST pending-approval notification send.

Goal (from the staging report): prove that when the owner's pending-approval
notification send fails, duplicate_reply_suppressed does not also swallow
the fallback/error message — the user gets exactly ONE public reply, never
zero, never two.

No fault-injection env var or new production code path was needed to test
this: app._queue_approval_detailed_impl() already wraps its
bot.send_message(owner_chat_id, ...) call in a try/except (the "BOSS NEVER
FAKES" block) that — on failure — verifiably cancels the EventBus pending
item and revokes the just-created ActionContract (via the existing,
independently-tested core.approval_queue_recovery helpers), then returns a
structured failure dict with no "owner_notified" key. This test drives that
existing path with a real event_bus/ActionGateway (mocking only bot.send_
message to raise), and verifies the exact properties the staging report
asked for.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fault-injection-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:FAULT_INJECTION_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patFaultInjectionTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appFaultInjectionTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
# CodeRabbit follow-up: assignment (not setdefault) so an inherited/ambient
# value can never leave this test writing through to a real Airtable base —
# core/action_gateway.py's module-level singleton reads this flag once, at
# import time, to decide whether to wire a real ActionContractRepository.
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
from event_bus import bus as _real_bus  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


print("── Fault injection: first (and only) pending-notification send fails ──")

user_id = "req_fault_inject_1"
mock_bot = MagicMock()
mock_bot.send_message.side_effect = RuntimeError("simulated Telegram send failure")

with patch.object(app, "bot", mock_bot), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": user_id}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    outcome = app._queue_approval_detailed(
        "airtable_add",
        {"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת כשל שליחה ראשונה"}},
        user_id, "telegram", "צור משימה בדיקת כשל שליחה ראשונה",
    )

chk("send_message was attempted exactly once (no silent retry loop)",
    mock_bot.send_message.call_count == 1)
chk("outcome.ok is False", outcome.get("ok") is False)
chk("owner_notified is falsy — never claimed as sent when the send raised",
    not outcome.get("owner_notified"))
chk("terminal_outcome is a real failure code, not a phantom success",
    outcome.get("terminal_outcome") == "APPROVAL_QUEUE_ERROR")
chk("exactly one non-empty message is returned (the one public reply)",
    bool(outcome.get("message")) and outcome["message"].count("לא הצלחתי לשלוח") >= 1)
chk("created_this_turn is False — no orphaned 'created' claim",
    outcome.get("created_this_turn") is False)

# duplicate_reply_suppressed is app._queue_deterministic_create_task()'s own
# concept (`if outcome.get("owner_notified") and ...: return ""`) — verified
# here directly on the outcome dict this function returns, since
# owner_notified is falsy the suppression branch can never fire for this
# outcome, matching the staging report's "duplicate_reply_suppressed=false".
chk(
    "the suppression condition (owner_notified truthy) cannot fire on this "
    "outcome — duplicate_reply_suppressed=false, as required",
    not bool(outcome.get("owner_notified")),
)

# Verify no orphaned live state: the EventBus pending item and the
# ActionGateway contract must both be cleaned up, not left dangling.
live_contracts = _real_gw.find_live_contracts(f"boss_hq:{user_id}")
chk("no live ActionContract left behind after the failed-notify cleanup",
    len(live_contracts) == 0)

chk("no pending EventBus items left behind for this user",
    len(_real_bus._pending._store) == 0
    or all(item.get("chat_id") != user_id for item in _real_bus._pending._store.values()))


print()
print("── Regression: a SECOND, successful send is unaffected (only the first failed) ──")

user_id2 = "req_fault_inject_2"
mock_bot2 = MagicMock()  # no side_effect — succeeds normally

with patch.object(app, "bot", mock_bot2), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": user_id2}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    outcome2 = app._queue_approval_detailed(
        "airtable_add",
        {"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת שליחה תקינה"}},
        user_id2, "telegram", "צור משימה בדיקת שליחה תקינה",
    )

chk("a normal (non-failing) send succeeds and reports owner_notified=True",
    outcome2.get("ok") is True and outcome2.get("owner_notified") is True)
chk("send_message was called exactly once for the successful case too",
    mock_bot2.send_message.call_count == 1)


print()
print("── Same fault, driven through the real create_task caller "
      "(app._queue_deterministic_create_task(), not just the lower-level "
      "_queue_approval_detailed()) ──")

from core.router.router import parse_deterministic_create_task  # noqa: E402
from identity import Identity, Role  # noqa: E402

user_id3 = "req_fault_inject_3"
identity3 = Identity(
    user_id=user_id3, role=Role.OWNER, display_name=user_id3,
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id3,
)
task_parse3 = parse_deterministic_create_task("צור משימה בדיקת כשל דרך create_task עד 5/8/26")
assert task_parse3.certain

mock_bot3 = MagicMock()
mock_bot3.send_message.side_effect = RuntimeError("simulated Telegram send failure")

with patch.object(app, "bot", mock_bot3), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": user_id3}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    deterministic_message = app._queue_deterministic_create_task(
        task_parse3.title, user_id3, "telegram",
        "צור משימה בדיקת כשל דרך create_task עד 5/8/26", identity3,
        task_parse=task_parse3,
    )

chk("create_task path: send_message attempted exactly once (no retry)",
    mock_bot3.send_message.call_count == 1)
chk(
    "create_task path: the public response is non-empty and contains "
    "exactly one fallback failure reply (never suppressed as duplicate, "
    "never silently empty)",
    bool(deterministic_message)
    and deterministic_message.count("לא הצלחתי לשלוח") == 1,
)
chk(
    "create_task path: no live ActionContract left behind (same cleanup "
    "as the lower-level path)",
    len(_real_gw.find_live_contracts(identity3.memory_key)) == 0,
)


print()
print("=" * 50)
print(f"First-pending-notification-failure suppression tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
