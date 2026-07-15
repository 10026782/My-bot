#!/usr/bin/env python3
"""
test_bug_batch_approval_preserved.py — regression tests for BUG-BATCH-DISCARD,
a regression from working multi-task batch behavior.

Root cause (commit 9ab4af7, 30/06/2026, BUG-043/BUG-V1-MULTI-PENDING-PAYLOAD-
CONTAMINATION): the tool loop in app.py blocked any second mutating-approval
tool call in the same agent turn outright, silently discarding every task
beyond the first in a multi-task request (e.g. "צור לי 5 משימות"). The
payload-contamination this cited was never actually reproduced — dict(tu.input)
already made an independent copy per call both before and after that fix, and
each _queue_approval() call already created its own independent EventBus item
+ ActionContract. The fix conflated "prevent a hypothetical shared-memory
hazard" with "prohibit more than one pending action per turn."

The naive restoration (just removing the block, letting every task become a
live ActionContract immediately) was tested and rejected before implementing:
once >1 contract is simultaneously "pending" for an identity,
route_confirmation_word() no longer directly executes a plain "מאשר" (it
falls into the len(live)>1 disambiguation branch instead — breaking the
already-working single-task flow), and picking one by number via
route_disambiguation()/route_combined_word() deliberately REJECTS every
sibling contract (§21, commit 6752ec0, "close all other pending contracts...
so no residual pending contracts linger") — a design built for disambiguating
between alternative interpretations of ONE request, not for preserving
independent batch items. Confirmed empirically (see conversation) that this
naive approach silently rejects the other 4 tasks the instant the first is
resolved.

Fix: every mutating tool call in a turn is durably preserved, but only the
first becomes a live ActionContract + sends a Telegram notification
(_queue_approval()). The rest are held in event_bus.batch_queue — NOT yet
live contracts — and promoted one at a time via
app._promote_next_batch_item(), only once no contract is currently live for
that identity. This never lets ActionGateway see more than one live contract
per identity for a batch, so route_confirmation_word()'s direct-execution
path and route_disambiguation()'s sibling-reject semantics are never
triggered by batch items at all. ActionGateway.approve()/reject()/
_execute_contract()/Atomic Claims are untouched — this is a queueing-layer
fix in app.py + a small in-memory queue in event_bus.py.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-batch-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BATCH_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBatchTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBatchTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("ELIYAHU_CHAT_ID", "999999999")  # so _queue_approval()'s
# owner_chat_id resolves non-empty and actually attempts bot.send_message()

import app  # noqa: E402
from identity import Identity, Role  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
from event_bus import batch_queue as _real_batch_queue  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str, role: str) -> Identity:
    return Identity(
        user_id=user_id, role=role, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


REQUESTER = _identity("owner-batch-1", Role.OWNER)
TASKS = [
    {"table": "Tasks", "fields": {"Task": "לסגור עם אהרן"}},
    {"table": "Tasks", "fields": {"Task": "לסיים 3 מודעות"}},
    {"table": "Tasks", "fields": {"Task": "לבדוק מה קורה עם אבי"}},
    {"table": "Tasks", "fields": {"Task": "לפנות למתווך על הדירה"}},
    {"table": "Tasks", "fields": {"Task": "לסיים עם דוחות 23-24"}},
]

_dispatched: list[dict] = []


def _tracking_dispatch_tool(tool_name, tool_inputs, *args, **kwargs):
    rec_id = f"recBATCH{len(_dispatched):09d}"  # "rec" + 14 chars, matches ^rec[A-Za-z0-9]{14}$
    _dispatched.append({"tool": tool_name, "inputs": tool_inputs})
    return {"ok": True, "tool": tool_name, "external_id": rec_id,
            "evidence": {"record_id": rec_id}, "user_message": f"✅ נוסף | {rec_id}"}


def _simulate_batch_turn(tasks: list[dict], requester: Identity) -> list[str]:
    """
    Mirrors app.py's tool-loop approval-gate logic exactly (see the
    BUG-BATCH-DISCARD comment there): first task -> _queue_approval();
    tasks 2..N -> batch_queue.enqueue(). Returns the tool_result content
    each would have produced.
    """
    from event_bus import batch_queue as _bq
    results = []
    for i, tool_inputs in enumerate(tasks):
        if i == 0:
            result = app._queue_approval(
                "airtable_add", tool_inputs, requester.user_id, "telegram", "צור לי 5 משימות",
            )
        else:
            _bq.enqueue(requester.memory_key, {
                "tool_name": "airtable_add", "tool_inputs": tool_inputs,
                "user_chat_id": requester.user_id, "channel": "telegram",
                "user_text": "צור לי 5 משימות",
            })
            label = app._describe_tool_call("airtable_add", tool_inputs)
            result = f"⏳ נשמר בתור לאישור אחרי הפעולה הראשונה: {label}"
        results.append(result)
    return results


mock_bot = MagicMock()
_flag_on = lambda name: name == "FEATURE_ACTION_GATEWAY"

with patch.object(app, "bot", mock_bot), \
     patch.object(app, "resolve_identity", return_value=REQUESTER), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    turn_results = _simulate_batch_turn(TASKS, REQUESTER)


# ══════════════════════════════════════════════════
# 1. 5 task tool uses produce 5 preserved actions
# ══════════════════════════════════════════════════
print("── 5 tasks in one turn: all preserved ──────────────────────")

chk("all 5 tool uses produced a tool_result (none silently dropped)",
    len(turn_results) == 5)
chk("none of the 5 tool_results is the old block message",
    all("לא ניתן לבצע מספר פעולות" not in r for r in turn_results))

_live_after_turn = _real_gw.find_live_contracts(REQUESTER.memory_key)
chk("exactly 1 ActionContract is live (pending) after the turn — the first task",
    len(_live_after_turn) == 1)
chk("the 4 remaining tasks are durably preserved in batch_queue, not discarded",
    _real_batch_queue.count_pending(REQUESTER.memory_key) == 4)


# ══════════════════════════════════════════════════
# 2. One user-facing approval prompt
# ══════════════════════════════════════════════════
print("\n── One canonical approval prompt per turn ──────────────────")

chk("exactly one Telegram notification (send_message) was sent this turn",
    mock_bot.send_message.call_count == 1)


# ══════════════════════════════════════════════════
# 3. Approve-all executes each action exactly once, none discarded, and the
# first task's direct "מאשר" flow is preserved (does not hit the
# len(live)>1 disambiguation branch, since only 1 contract is ever live).
# ══════════════════════════════════════════════════
print("\n── Approve-all: each action executes exactly once ──────────")

with patch.object(app, "resolve_identity", return_value=REQUESTER), \
     patch.object(app, "bot", mock_bot), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_tracking_dispatch_tool), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    # Confirming "מאשר" for task 1 must execute directly (not show a
    # numbered disambiguation list) — this is the exact regression the
    # naive "just remove the block" fix would have caused.
    reply1 = _real_gw.route_confirmation_word(REQUESTER.memory_key, approver_role="owner")
    chk("task 1: plain 'מאשר' executes directly (no disambiguation list)",
        "יש כמה פעולות" not in reply1)
    chk("task 1: reports success", "✅" in reply1 or "בוצע" in reply1)
    app._promote_next_batch_item(REQUESTER.memory_key)

    for i in range(2, 6):
        _live_now = _real_gw.find_live_contracts(REQUESTER.memory_key)
        chk(f"before confirming task {i}: exactly 1 contract is live (promoted from queue)",
            len(_live_now) == 1)
        reply_n = _real_gw.route_confirmation_word(REQUESTER.memory_key, approver_role="owner")
        chk(f"task {i}: plain 'מאשר' executes directly (no disambiguation list)",
            "יש כמה פעולות" not in reply_n)
        chk(f"task {i}: reports success", "✅" in reply_n or "בוצע" in reply_n)
        app._promote_next_batch_item(REQUESTER.memory_key)

chk("all 5 tasks dispatched, exactly once each (no duplicates)",
    len(_dispatched) == 5)
chk("batch_queue is empty after all 5 are resolved",
    _real_batch_queue.count_pending(REQUESTER.memory_key) == 0)
chk("no ActionContract remains live after all 5 are resolved",
    _real_gw.find_live_contracts(REQUESTER.memory_key) == [])

_notify_calls_total = mock_bot.send_message.call_count
chk("exactly 5 Telegram notifications sent in total across the whole batch "
    "(1 initial + 4 promotions, one per task, never more)",
    _notify_calls_total == 5)


# ══════════════════════════════════════════════════
# 4. Rejection/cancellation has deterministic batch behavior: rejecting the
# current active task does not discard the untouched, still-queued items,
# and promotes the next one correctly.
# ══════════════════════════════════════════════════
print("\n── Rejection/cancellation: deterministic batch behavior ────")

REQUESTER2 = _identity("owner-batch-2", Role.OWNER)
mock_bot2 = MagicMock()

with patch.object(app, "bot", mock_bot2), \
     patch.object(app, "resolve_identity", return_value=REQUESTER2), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    _simulate_batch_turn(TASKS[:3], REQUESTER2)  # 3 tasks: 1 live, 2 queued

chk("setup: 1 live contract, 2 queued", (
    len(_real_gw.find_live_contracts(REQUESTER2.memory_key)) == 1
    and _real_batch_queue.count_pending(REQUESTER2.memory_key) == 2
))

with patch.object(app, "bot", mock_bot2), \
     patch.object(app, "resolve_identity", return_value=REQUESTER2), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    _cancel_reply = _real_gw.route_cancellation_word(REQUESTER2.memory_key)
    chk("cancelling the current task returns a cancellation reply",
        _cancel_reply is not None and "בוטל" in _cancel_reply)
    _live_after_cancel = _real_gw.find_live_contracts(REQUESTER2.memory_key)
    chk("cancelling task 1 does not touch the still-queued (not-yet-live) tasks 2/3",
        _real_batch_queue.count_pending(REQUESTER2.memory_key) == 2)
    app._promote_next_batch_item(REQUESTER2.memory_key)
    chk("after cancelling task 1, task 2 is promoted to live (not discarded)",
        len(_real_gw.find_live_contracts(REQUESTER2.memory_key)) == 1)
    chk("batch_queue now holds only the last remaining task",
        _real_batch_queue.count_pending(REQUESTER2.memory_key) == 1)

    # Confirm task 2, then task 3 — deterministic, no duplication, nothing lost.
    with patch("tools.dispatcher.dispatch_tool", side_effect=_tracking_dispatch_tool):
        _reply2 = _real_gw.route_confirmation_word(REQUESTER2.memory_key, approver_role="owner")
        chk("task 2 executes directly after task 1's cancellation",
            "יש כמה פעולות" not in _reply2 and ("✅" in _reply2 or "בוצע" in _reply2))
        app._promote_next_batch_item(REQUESTER2.memory_key)
        chk("task 3 promoted after task 2 resolves",
            len(_real_gw.find_live_contracts(REQUESTER2.memory_key)) == 1)
        _reply3 = _real_gw.route_confirmation_word(REQUESTER2.memory_key, approver_role="owner")
        chk("task 3 executes directly", "✅" in _reply3 or "בוצע" in _reply3)
        app._promote_next_batch_item(REQUESTER2.memory_key)

chk("batch_queue empty at the end of the cancellation scenario",
    _real_batch_queue.count_pending(REQUESTER2.memory_key) == 0)
chk("no ActionContract left live at the end of the cancellation scenario",
    _real_gw.find_live_contracts(REQUESTER2.memory_key) == [])


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"batch approval preservation tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
