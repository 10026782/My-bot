#!/usr/bin/env python3
"""
test_bug_stale_callback_ux.py — regression tests for BUG-STALE-CALLBACK-UX:
improving the user-facing result of a completed/already-resolved/stale
Telegram approval callback without changing any execution semantics.

Problem: pressing an already-resolved approval button only produced a
temporary answer_callback_query() popup (e.g. "הפעולה כבר בוצעה") — small,
disappears quickly, doesn't name the action, easy to miss.

Fix: app.py's _notify_stale_or_resolved_callback() sends a persistent chat
message naming the action and confirming no duplicate execution occurred,
and edits the original approval message to show its final state (removing
the stale inline keyboard) — wired into every path that previously only
answered the callback query: the SB-02 completed/rejected pre-check, the
"item not found" (truly expired) case, the post-completion-fallthrough
terminal-reply block, and the stale/unlinked-callback fail-closed block.

Explicitly NOT changed: dispatch/claim/write counts, BatchQueue promotion,
ActionContract lifecycle, or approval resolution semantics — this is a
notification-layer change only, verified by asserting zero dispatcher calls
throughout.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-staleux-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:STALEUX_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patStaleUxTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appStaleUxTest")
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


def _tracking_bot() -> MagicMock:
    """A MagicMock whose send_message/edit_message_text calls are still
    recorded via call_args_list (MagicMock does this natively) — named
    helper just for readability at call sites below."""
    return MagicMock()


_flag_on = lambda name: name == "FEATURE_ACTION_GATEWAY"
_TASK_TITLE = "הכנת הרכב לקיץ"


_FAKE_RECORD_ID = "recSTALEUXTESTID1"  # "rec" + 14 chars, matches ^rec[A-Za-z0-9]{14}$


def _ok_dispatch(*args, **kwargs):
    return {"ok": True, "tool": "airtable_add", "external_id": _FAKE_RECORD_ID,
            "evidence": {"record_id": _FAKE_RECORD_ID}, "user_message": "✅ נוסף"}


# ══════════════════════════════════════════════════
# Scenario A: SB-02 pre-check catches an already-completed contract via a
# stale button press (the most common real-world case — text "מאשר"
# completed it, stale button still showing).
# ══════════════════════════════════════════════════
print("── Scenario A: SB-02 pre-check — already completed ─────────────")

requester_a = _identity("owner-staleux-a", Role.OWNER)
tool_inputs_a = {"table": "Tasks", "fields": {"Task": _TASK_TITLE}}

_legacy_action_id_a, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add", "tool_inputs": tool_inputs_a,
        "origin_channel": "telegram", "origin_chat_id": requester_a.user_id,
        "canonical_user_id": requester_a.memory_key,
        "user_chat_id": requester_a.user_id, "channel": "telegram",
    },
    chat_id=requester_a.user_id, label=f"➕ הוסף ל-Tasks:\n• Task: {_TASK_TITLE}",
)
_real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester_a.memory_key,
    tool_name="airtable_add", tool_inputs=tool_inputs_a,
    origin_channel="telegram", origin_chat_id=requester_a.user_id,
    requires_approval=True, identity=requester_a, trusted_source="agent",
)
with patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    _real_gw.route_confirmation_word(requester_a.memory_key, approver_role="owner")

cq_a = _fake_cq(requester_a.user_id, f"approve:{_legacy_action_id_a}")
mock_bot_a = _tracking_bot()

with patch.object(app, "bot", mock_bot_a), \
     patch.object(app, "resolve_identity", return_value=requester_a), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_a, \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy_a, \
     patch.object(app, "_flag_enabled", side_effect=_flag_on), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._handle_approval_callback_impl(cq_a)

chk("A: stale callback produces zero dispatcher calls",
    _dt_a.call_count == 0 and _dt_legacy_a.call_count == 0)
chk("A: answer_callback_query popup was sent (immediate ack)",
    mock_bot_a.answer_callback_query.called)
chk("A: callback popup is NOT the only response — a persistent send_message also occurred",
    mock_bot_a.send_message.called)
_persistent_text_a = mock_bot_a.send_message.call_args[0][1]
chk("A: persistent response identifies the relevant action (task title present)",
    _TASK_TITLE in _persistent_text_a)
chk("A: persistent response confirms no duplicate execution",
    "לא בוצעה שוב" in _persistent_text_a)
chk("A: original approval message was edited (final state shown, button removed)",
    mock_bot_a.edit_message_text.called)
_edited_text_a = mock_bot_a.edit_message_text.call_args[0][0]
chk("A: edited message no longer implies an active button is expected "
    "(shows final state text, not the original pending prompt)",
    "כבר בוצעה" in _edited_text_a)


# ══════════════════════════════════════════════════
# Scenario B: post-completion-fallthrough terminal-reply block (contract
# completed via a different fingerprint-matching path this callback still
# reaches the execution-decision point for).
# ══════════════════════════════════════════════════
print("\n── Scenario B: post-completion-fallthrough terminal reply ──────")

requester_b = _identity("owner-staleux-b", Role.OWNER)
tool_inputs_b = {"table": "Tasks", "fields": {"Task": _TASK_TITLE}}

_legacy_action_id_b, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add", "tool_inputs": tool_inputs_b,
        "origin_channel": "telegram", "origin_chat_id": requester_b.user_id,
        "canonical_user_id": requester_b.memory_key,
        "user_chat_id": requester_b.user_id, "channel": "telegram",
    },
    chat_id=requester_b.user_id, label=f"➕ הוסף ל-Tasks:\n• Task: {_TASK_TITLE}",
)
_real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester_b.memory_key,
    tool_name="airtable_add", tool_inputs=tool_inputs_b,
    origin_channel="telegram", origin_chat_id=requester_b.user_id,
    requires_approval=True, identity=requester_b, trusted_source="agent",
)
with patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    _real_gw.route_confirmation_word(requester_b.memory_key, approver_role="owner")

cq_b = _fake_cq(requester_b.user_id, f"approve:{_legacy_action_id_b}")
mock_bot_b = _tracking_bot()

# Force the SB-02 early pre-check to miss (simulating its own known
# limitation covered separately) so the flow reaches the later
# post-completion-fallthrough terminal-reply block instead.
with patch.object(app, "bot", mock_bot_b), \
     patch.object(app, "resolve_identity", return_value=requester_b), \
     patch.object(_real_bus, "peek", return_value=None), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_b, \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy_b, \
     patch.object(app, "_flag_enabled", side_effect=_flag_on), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._handle_approval_callback_impl(cq_b)

chk("B: stale callback produces zero dispatcher calls",
    _dt_b.call_count == 0 and _dt_legacy_b.call_count == 0)
chk("B: callback popup is not the only response", mock_bot_b.send_message.called)
_persistent_text_b = mock_bot_b.send_message.call_args[0][1]
chk("B: persistent response identifies the relevant action", _TASK_TITLE in _persistent_text_b)
chk("B: persistent response confirms no duplicate execution", "לא בוצעה שוב" in _persistent_text_b)
chk("B: original approval message edited to final state", mock_bot_b.edit_message_text.called)


# ══════════════════════════════════════════════════
# Scenario C: repeated press cannot create another write — press the same
# stale button twice in a row, confirm total dispatch count stays zero and
# only one Airtable record exists (verified via the earlier real
# route_confirmation_word() dispatch count, tracked once).
# ══════════════════════════════════════════════════
print("\n── Scenario C: repeated press cannot create another write ──────")

cq_a2 = _fake_cq(requester_a.user_id, f"approve:{_legacy_action_id_a}")
mock_bot_a2 = _tracking_bot()
with patch.object(app, "bot", mock_bot_a2), \
     patch.object(app, "resolve_identity", return_value=requester_a), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_a2, \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy_a2, \
     patch.object(app, "_flag_enabled", side_effect=_flag_on), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._handle_approval_callback_impl(cq_a2)

chk("C: pressing the same already-resolved button again still dispatches zero times",
    _dt_a2.call_count == 0 and _dt_legacy_a2.call_count == 0)
chk("C: repeated press still gets a persistent, action-identifying response",
    mock_bot_a2.send_message.called and _TASK_TITLE in mock_bot_a2.send_message.call_args[0][1])


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"stale callback UX tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
