#!/usr/bin/env python3
"""
test_bug_post_completion_callback_fallthrough.py — regression tests for a
live-incident bug (contract 9d835392-3e5d-4979-8bc1-0baa17a892af): a task was
approved and completed via a text confirmation ("מאשר"), but a stale Telegram
approval button for the *same* action was still showing (text confirmations
never touch the legacy event_bus item the button's callback_data points at).
Pressing that stale button re-entered the legacy direct-dispatch path and
re-ran airtable_add against the already-completed payload.

Root cause #1: app.py's SB-02 pre-check called `bus.get(action_id)` — EventBus
never exposed a `get()` method (only `pop()`); every call raised
AttributeError, silently logged as "non-blocking", so the pre-check never
actually ran. Fixed: EventBus.peek() (core/event_bus.py) is the real
non-destructive read; the call site now uses it.

Root cause #2: even with the pre-check working, the *execution* decision
point (right before choosing between ActionGateway.approve() and the legacy
dispatch_tool() call) only checked `contract.status == "pending"` to decide
whether to use the Gateway path — a contract found in any other state
(completed/executed/rejected) silently fell through to the legacy
dispatch_tool() branch as if no contract existed at all. Fixed: a contract in
a terminal state now short-circuits with a deterministic reply and never
reaches the legacy branch — this is authoritative regardless of whether the
earlier peek pre-check ran.

The dedup check inside dispatch_tool/airtable_gateway did prevent a second
Airtable POST, but its plain-string "already exists" response was then
misclassified by A32's verify_execution() as
"expected structured result dict with ok=true; got plain string" — a
misleading false-failure message. The real fix is to never reach that legacy
path at all once a contract is terminal, not to special-case its return
shape.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-postfix-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:POSTFIX_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPostfixTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPostfixTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from identity import Identity, Role  # noqa: E402
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


def _identity(user_id: str, role: str) -> Identity:
    return Identity(
        user_id=user_id, role=role, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


def _fake_cq(approver_chat_id: str, data: str):
    return SimpleNamespace(
        id="cbq1",
        data=data,
        from_user=SimpleNamespace(id=approver_chat_id),
        message=SimpleNamespace(chat=SimpleNamespace(id="chat1"), message_id=1),
    )


RECORD_ID = "recP8c6hYpYW7bjSG"


def _ok_dispatch(*args, **kwargs):
    return {"ok": True, "tool": "airtable_add", "external_id": RECORD_ID,
            "evidence": {"record_id": RECORD_ID}, "user_message": f"✅ רשומה נוספה | ID: {RECORD_ID}"}


# ══════════════════════════════════════════════════
# EventBus.peek() itself — the direct cause of the AttributeError
# ══════════════════════════════════════════════════
print("── EventBus.peek() ─────────────────────────────")

chk("EventBus exposes a peek() method (bus.get() never existed)", hasattr(_real_bus, "peek"))

_peek_action_id, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={"tool_name": "airtable_add", "tool_inputs": {"table": "Tasks"}},
    chat_id="peek-test-chat",
    label="peek test",
)
_peeked = _real_bus.peek(_peek_action_id)
chk("peek() returns the item without consuming it", _peeked is not None)
chk("peek() does not remove the item (a subsequent pop() still finds it)",
    _real_bus.pop(_peek_action_id) is not None)
chk("after pop(), the item is actually gone", _real_bus.peek(_peek_action_id) is None)


# ══════════════════════════════════════════════════
# Live-incident reproduction: text confirmation completes the contract,
# then a stale button callback for the same fingerprint must not re-dispatch.
# ══════════════════════════════════════════════════
print("\n── Post-completion callback fallthrough (live incident repro) ──")

requester = _identity("owner-pc1", Role.OWNER)
tool_inputs = {"table": "Tasks", "fields": {"Task": "לסגור עם אהרן"}}

# _queue_approval() registers both a legacy event_bus item (for the Telegram
# button) and a durable ActionContract (for the text-confirmation path) —
# reproduce both here, exactly as _queue_approval() does.
_legacy_action_id, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name":         "airtable_add",
        "tool_inputs":       tool_inputs,
        "origin_channel":    "telegram",
        "origin_chat_id":    requester.user_id,
        "canonical_user_id": requester.memory_key,
        "user_chat_id":      requester.user_id,
        "channel":           "telegram",
    },
    chat_id=requester.user_id,
    label="task test",
)

_propose = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester.memory_key,
    tool_name="airtable_add", tool_inputs=tool_inputs,
    origin_channel="telegram", origin_chat_id=requester.user_id,
    requires_approval=True, identity=requester, trusted_source="agent",
)
contract_id = _propose.contract_id

_flag_side_effect = lambda name: True if name == "FEATURE_ACTION_GATEWAY" else False

with patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_first, \
     patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
    # Step 1: first confirmation — the user types "מאשר" (text path). This
    # never touches the legacy event_bus item registered above.
    first_reply = _real_gw.route_confirmation_word(requester.memory_key, approver_role="owner")

chk("first confirmation dispatches exactly once", _dt_first.call_count == 1)
chk("first confirmation reports canonical success",
    first_reply.startswith("המשימה נוצרה:"))

_contract_after_first = _real_gw._ledger.find_by_id(contract_id)
chk("contract reached a terminal success status after first confirmation",
    _contract_after_first is not None and _contract_after_first.status in ("completed", "executed"))

# Step 2: the stale Telegram button (still showing — text confirmation never
# edited its markup) gets pressed. This must not re-dispatch, must not run
# the legacy dispatch_tool() branch, and must not emit the misleading
# "expected structured result dict" error.
cq = _fake_cq(requester.user_id, f"approve:{_legacy_action_id}")

_sent_messages = []
_edited_texts = []
_markup_cleared = {"called": False}


def _fake_send_message(chat_id, text, *a, **kw):
    _sent_messages.append(text)


def _fake_edit_message_text(text, chat_id, message_id, *a, **kw):
    _edited_texts.append(text)


def _fake_edit_reply_markup(chat_id, message_id, *a, **kw):
    _markup_cleared["called"] = True


mock_bot = MagicMock()
mock_bot.send_message.side_effect = _fake_send_message
mock_bot.edit_message_text.side_effect = _fake_edit_message_text
mock_bot.edit_message_reply_markup.side_effect = _fake_edit_reply_markup

with patch.object(app, "bot", mock_bot), \
     patch.object(app, "resolve_identity", return_value=requester), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_gw_second, \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy_second, \
     patch.object(app, "_flag_enabled", side_effect=_flag_side_effect), \
     patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
    app._handle_approval_callback_impl(cq)

_second_dispatch_calls = _dt_gw_second.call_count + _dt_legacy_second.call_count
chk("second confirmation (stale button) dispatches zero times",
    _second_dispatch_calls == 0)
chk("legacy dispatch_tool() branch never ran", _dt_legacy_second.call_count == 0)

_all_reply_text = " ".join(_sent_messages + _edited_texts)
chk("no structured-result error is emitted",
    "expected structured result dict" not in _all_reply_text)
chk("no false 'אושר אך נכשל בביצוע' failure message is emitted",
    "אושר אך נכשל בביצוע" not in _all_reply_text)
chk("callback answered with a deterministic already-done reply",
    mock_bot.answer_callback_query.call_args is not None and
    "כבר בוצעה" in mock_bot.answer_callback_query.call_args[0][1])
# BUG-STALE-CALLBACK-UX: the stale button's message is now edited to show
# its final state via edit_message_text() (which also clears the inline
# keyboard, since no reply_markup is passed) — edit_message_reply_markup()
# is only the fallback if that edit itself fails. Either one clearing the
# button is acceptable; requiring specifically the fallback path would be
# testing an implementation detail, not the actual requirement.
chk("stale button's message updated to reflect final state (edited text and/or markup cleared)",
    _markup_cleared["called"] or bool(_edited_texts))

_contract_after_second = _real_gw._ledger.find_by_id(contract_id)
chk("contract status is unchanged by the stale callback",
    _contract_after_second is not None and
    _contract_after_second.status == _contract_after_first.status)


# ══════════════════════════════════════════════════
# Backstop independence: even if the legacy bus payload is missing
# canonical_user_id (so the early SB-02 pre-check's `if _peek_tool and
# _peek_uid:` guard skips silently without returning), the later
# authoritative check right before the dispatch decision must still block
# the legacy fallthrough on its own.
# ══════════════════════════════════════════════════
print("\n── Backstop independence (early pre-check payload missing canonical_user_id) ──")

requester2 = _identity("owner-pc2", Role.OWNER)
tool_inputs2 = {"table": "Tasks", "fields": {"Task": "לבדוק מה קורה עם אבי"}}

_legacy_action_id2, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name":      "airtable_add",
        "tool_inputs":    tool_inputs2,
        "origin_channel": "telegram",
        "origin_chat_id": requester2.user_id,
        # canonical_user_id deliberately omitted — early SB-02 pre-check
        # requires it to compute a fingerprint and will skip without it.
        "user_chat_id":   requester2.user_id,
        "channel":        "telegram",
    },
    chat_id=requester2.user_id,
    label="task test 2",
)

_propose2 = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester2.memory_key,
    tool_name="airtable_add", tool_inputs=tool_inputs2,
    origin_channel="telegram", origin_chat_id=requester2.user_id,
    requires_approval=True, identity=requester2, trusted_source="agent",
)
contract_id2 = _propose2.contract_id

with patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_first2, \
     patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
    _real_gw.route_confirmation_word(requester2.memory_key, approver_role="owner")

chk("setup: first confirmation (2nd scenario) dispatched exactly once",
    _dt_first2.call_count == 1)

cq2 = _fake_cq(requester2.user_id, f"approve:{_legacy_action_id2}")
mock_bot2 = MagicMock()

with patch.object(app, "bot", mock_bot2), \
     patch.object(app, "resolve_identity", return_value=requester2), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_gw_third, \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy_third, \
     patch.object(app, "_flag_enabled", side_effect=_flag_side_effect), \
     patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
    app._handle_approval_callback_impl(cq2)

_third_dispatch_calls = _dt_gw_third.call_count + _dt_legacy_third.call_count
chk("backstop alone (early pre-check skipped) still blocks re-dispatch",
    _third_dispatch_calls == 0)
chk("backstop alone: legacy dispatch_tool() branch never ran",
    _dt_legacy_third.call_count == 0)

_contract2_after = _real_gw._ledger.find_by_id(contract_id2)
chk("backstop alone: contract status unchanged",
    _contract2_after is not None and _contract2_after.status in ("completed", "executed"))


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"post-completion callback fallthrough tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
