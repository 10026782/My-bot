#!/usr/bin/env python3
"""BUG-122 regression: deferred batch work is never retained or promoted."""

from __future__ import annotations

import inspect
import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-batch-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BATCH_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBatchTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBatchTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from core.action_gateway import action_gateway  # noqa: E402
from core.router.intent_router import detect_intent  # noqa: E402
from core.router.route_decision import Intent  # noqa: E402
from event_bus import batch_queue, pending  # noqa: E402
from identity import Identity, Role  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(("✅" if cond else "❌") + " " + desc)
        passed += 1
    else:
        print("❌ " + desc)
        failed += 1


user = "boss_hq:bug122-batch"
batch_queue.clear(user)
batch_queue.enqueue(user, {
    "tool_name": "airtable_add",
    "tool_inputs": {"table": "Tasks", "fields": {"Task": "must not resurrect"}},
    "user_chat_id": "bug122-batch",
    "channel": "telegram",
})

queued_calls = []
with patch.object(app, "_queue_approval", side_effect=lambda *a, **k: queued_calls.append((a, k))):
    app._promote_next_batch_item(user)

chk("legacy deferred item is discarded after resolution", batch_queue.count_pending(user) == 0)
chk("discard cleanup creates no new approval contract", queued_calls == [])

promotion_src = inspect.getsource(app._promote_next_batch_item)
chk("resolution cleanup contains no queue pop", ".pop_next(" not in promotion_src)
chk("resolution cleanup contains no approval creation", "_queue_approval(" not in promotion_src)

run_agent_src = inspect.getsource(app.run_agent)
chk("tool loop no longer enqueues deferred items", ".enqueue(" not in run_agent_src)
chk("same-turn second mutation is classified as blocked", "APPROVAL_BLOCKED_PENDING" in run_agent_src)
chk("blocked mutation tells the user to resend", "לשלוח את הבקשה מחדש" in run_agent_src)

print("\n── BUG-122: unknown-intent Agent proposal boundary ───────────")

unknown_text = "ספר לי משהו מעניין"
unknown_intent, _, _ = detect_intent(unknown_text)
chk("regression setup: Router intent is unknown", unknown_intent == Intent.UNKNOWN)

identity = Identity(
    user_id="bug122-unknown", role=Role.OWNER,
    display_name="bug122-unknown", tenant_id="boss_hq",
    domain_id="general", channel="telegram", external_id="bug122-unknown",
)
batch_queue.clear(identity.memory_key)

with patch.object(app, "resolve_identity", return_value=identity), \
     patch.object(app, "bot", MagicMock()), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    first = app._queue_approval_detailed(
        "airtable_add",
        {"table": "Tasks", "fields": {"כותרת המשימה": "first pending"}},
        identity.user_id, "telegram", "צור משימה ראשונה",
    )
    event_items_after_first = pending.list_for_chat(identity.user_id)
    second = app._queue_approval_detailed(
        "airtable_add",
        {"table": "Tasks", "fields": {"כותרת המשימה": "different mutation"}},
        identity.user_id, "telegram", unknown_text,
    )

live = action_gateway.find_live_contracts(identity.memory_key)
event_items_after_second = pending.list_for_chat(identity.user_id)
chk("first mutation creates exactly one pending ActionContract",
    first["ok"] is True and len(live) == 1)
chk("unknown-intent Agent mutation creates no second ActionContract",
    second["ok"] is False and len(live) == 1)
chk("unknown-intent Agent mutation creates no EventBus item",
    len(event_items_after_first) == 1 and len(event_items_after_second) == 1)
chk("unknown-intent Agent mutation leaves BatchQueue at zero",
    batch_queue.count_pending(identity.memory_key) == 0)
chk("blocked proposal instructs the user to resolve and resend",
    "לשלוח מחדש" in second["message"] and "לא נשמרה" in second["message"])

print(f"\nBUG-122 batch policy tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
