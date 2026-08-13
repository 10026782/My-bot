#!/usr/bin/env python3
"""
test_bug158_approval_callback_eventbus_ttl_recovery.py — BUG-158 (a Telegram
approve/reject callback whose event_bus.py PendingActionsStore item has
already aged out reports "not available" even when the underlying
ActionContract — the real source of truth, 24h TTL — is still live).

Problem (staging, owner manual test, 05-07/08/2026): a still-pending
ActionContract can outlive event_bus.py's own internal ~30-minute TTL for
its PendingActionsStore item. app.py::_handle_approval_callback_impl()'s
approve AND reject branches both call bus.pop(action_id) and, if it returns
None, immediately call _notify_missing_or_expired_callback() — "ℹ️ הפעולה
כבר אינה זמינה, ולכן לא בוצעה." — WITHOUT checking whether the button's own
callback_contract_id (embedded in callback_data independently of the
EventBus item, PR1 format) still resolves to a live pending contract. This
contradicts an EARLIER check in the SAME function (app.py:~2519-2536) that
already looks up the contract via callback_contract_id and only short-
circuits when it is terminal — when it's still pending, that check
deliberately falls through, assuming the normal bus.pop()-based flow will
handle it. That assumption breaks exactly when bus.pop() fails: the correct
knowledge ("still pending!") already computed in this very call is thrown
away and replaced with a false "not available."

Fix: app._recover_pending_item_from_contract(contract_id) reconstructs an
EventBus-shaped item straight from the ActionContract itself (already
authoritative for tool_name/normalized_payload/origin_channel/origin_chat_id/
canonical_user_id) when bus.pop() returns None. Both the "approve" and
"reject" branches call it before giving up. Returns None (unchanged "not
available" behavior) when the contract is missing or no longer pending — a
genuinely gone action still reports "not available", exactly as before.

See docs/architecture/action-gateway/
BUG-158_APPROVAL_CANCELLATION_EXPIRY_CANONICALIZATION_20260807.md for the
full design and Cross-Layer Impact Matrix.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug158-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG158_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug158Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug158Test")
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


def _identity(user_id: str, role: str = Role.OWNER) -> Identity:
    return Identity(
        user_id=user_id, role=role, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


def _fake_cq(approver_chat_id: str, data: str):
    return SimpleNamespace(
        id="cbq158",
        data=data,
        from_user=SimpleNamespace(id=approver_chat_id),
        message=SimpleNamespace(chat=SimpleNamespace(id="chat158"), message_id=1),
    )


def _ok_dispatch(*args, **kwargs):
    # external_id must look like a real Airtable record id
    # (^rec[A-Za-z0-9]{14}$) — airtable_add's own evidence check enforces
    # this, unlike some other tools.
    return {"ok": True, "tool": "airtable_add", "external_id": "recBUG158Test0001",
            "evidence": {"audit_id": "recBUG158Test0001"}, "user_message": "✅ בוצע"}


def _run_callback(
    *, requester: Identity, approver: Identity, action: str,
    drain_bus_item: bool, seed_contract: bool, tool_inputs: dict,
):
    """Proposes a real ActionContract (optionally), registers a real
    EventBus item pointing at it, optionally drains the EventBus item
    immediately (simulating its own internal TTL already having passed —
    bus.pop() inside the real callback handler will then see nothing, the
    exact BUG-158 trigger condition), then drives
    app._handle_approval_callback_impl() with Telegram/dispatch mocked."""
    contract_id = None
    if seed_contract:
        propose = _real_gw.propose_action(
            tenant_id="boss_hq", canonical_user_id=requester.memory_key,
            tool_name="airtable_add", tool_inputs=tool_inputs,
            origin_channel="telegram", origin_chat_id=requester.user_id,
            requires_approval=True, identity=requester, trusted_source="agent",
        )
        contract_id = propose.contract_id

    action_id, _ = _real_bus.request_approval(
        action="airtable_add",
        payload={
            "tool_name": "airtable_add",
            "tool_inputs": tool_inputs,
            "origin_channel": "telegram",
            "origin_chat_id": requester.user_id,
            "canonical_user_id": requester.memory_key,
            "user_chat_id": requester.user_id,
            "channel": "telegram",
            "contract_id": contract_id,
        },
        chat_id=requester.user_id,
        label="test BUG-158",
    )

    if drain_bus_item:
        # Simulates event_bus.py's own ~30-minute internal TTL having
        # already passed by the time the callback is actually pressed —
        # bus.pop() inside the real handler call below will see nothing.
        _real_bus.pop(action_id)

    def _resolve_identity_side_effect(channel, ext_id):
        return approver if ext_id == approver.user_id else requester

    callback_data = f"{action}:{action_id}:{contract_id or ''}"
    cq = _fake_cq(approver.user_id, callback_data)
    mock_bot = MagicMock()

    def _flag_side_effect(name):
        return name == "FEATURE_ACTION_GATEWAY"

    with patch.object(app, "bot", mock_bot), \
         patch.object(app, "resolve_identity", side_effect=_resolve_identity_side_effect), \
         patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_gw, \
         patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy, \
         patch.object(app, "_flag_enabled", side_effect=_flag_side_effect), \
         patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
        app._handle_approval_callback_impl(cq)

    total_dispatch_calls = _dt_gw.call_count + _dt_legacy.call_count
    final_contract = _real_gw._ledger.find_by_id(contract_id) if contract_id else None
    return total_dispatch_calls, final_contract, mock_bot


# ══════════════════════════════════════════════════════════════════
print("── 1. approve: bus item already gone, but callback_contract_id still "
      "resolves to a live pending contract — must recover and execute, not "
      "report 'not available' ──")

requester1 = _identity("req_bug158_approve_recover")
approver1 = _identity("appr_bug158_approve_recover")
calls1, contract1, bot1 = _run_callback(
    requester=requester1, approver=approver1, action="approve",
    drain_bus_item=True, seed_contract=True,
    tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת BUG-158"}},
)
chk("dispatch_tool WAS called (recovered, not falsely reported unavailable)",
    calls1 == 1)
chk("contract transitioned to a terminal success state (executed/completed)",
    contract1 is not None and contract1.status in ("executed", "completed"))
_sent_texts1 = [c.args[1] for c in bot1.send_message.call_args_list if len(c.args) > 1]
chk("the user was never told 'ℹ️ הפעולה כבר אינה זמינה' for this recovered action",
    not any(app._MISSING_OR_EXPIRED_CALLBACK_TEXT in t for t in _sent_texts1))


# ══════════════════════════════════════════════════════════════════
print("\n── 2. reject: bus item already gone, but callback_contract_id still "
      "resolves to a live pending contract — must recover and reject, not "
      "report 'not available' ──")

requester2 = _identity("req_bug158_reject_recover")
approver2 = _identity("appr_bug158_reject_recover")
calls2, contract2, bot2 = _run_callback(
    requester=requester2, approver=approver2, action="reject",
    drain_bus_item=True, seed_contract=True,
    tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת BUG-158 reject"}},
)
chk("dispatch_tool was NOT called (a reject must never execute)", calls2 == 0)
chk("contract transitioned to 'rejected' (recovered, not left dangling pending)",
    contract2 is not None and contract2.status == "rejected")
_sent_texts2 = [c.args[1] for c in bot2.send_message.call_args_list if len(c.args) > 1]
chk("the user was never told 'ℹ️ הפעולה כבר אינה זמינה' for this recovered reject",
    not any(app._MISSING_OR_EXPIRED_CALLBACK_TEXT in t for t in _sent_texts2))


# ══════════════════════════════════════════════════════════════════
print("\n── 3. regression: bus item present (normal case) — unchanged, "
      "recovery path never invoked ──")

requester3 = _identity("req_bug158_baseline")
approver3 = _identity("appr_bug158_baseline")
calls3, contract3, _ = _run_callback(
    requester=requester3, approver=approver3, action="approve",
    drain_bus_item=False, seed_contract=True,
    tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת מקרה רגיל"}},
)
chk("baseline (bus item present) still executes normally, exactly as before",
    calls3 == 1 and contract3 is not None and contract3.status in ("executed", "completed"))


# ══════════════════════════════════════════════════════════════════
print("\n── 4. genuinely gone: bus item gone AND contract already terminal "
      "(e.g. previously rejected) — recovery correctly declines, 'not "
      "available' still shown (no behavior change for a truly dead action) ──")

requester4 = _identity("req_bug158_truly_gone")
approver4 = _identity("appr_bug158_truly_gone")
propose4 = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester4.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת חוזה סגור"}},
    origin_channel="telegram", origin_chat_id=requester4.user_id,
    requires_approval=True, identity=requester4, trusted_source="agent",
)
_real_gw.reject(propose4.contract_id, rejected_by="test_setup")

action_id4, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add", "tool_inputs": {},
        "origin_channel": "telegram", "origin_chat_id": requester4.user_id,
        "canonical_user_id": requester4.memory_key, "user_chat_id": requester4.user_id,
        "channel": "telegram", "contract_id": propose4.contract_id,
    },
    chat_id=requester4.user_id, label="already rejected",
)
_real_bus.pop(action_id4)  # drain — simulates EventBus TTL already passed

cq4 = _fake_cq(approver4.user_id, f"approve:{action_id4}:{propose4.contract_id}")
mock_bot4 = MagicMock()


def _resolve4(channel, ext_id):
    return approver4 if ext_id == approver4.user_id else requester4


with patch.object(app, "bot", mock_bot4), \
     patch.object(app, "resolve_identity", side_effect=_resolve4), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt4, \
     patch.object(app, "_flag_enabled", side_effect=lambda n: n == "FEATURE_ACTION_GATEWAY"), \
     patch("feature_flags.is_enabled", side_effect=lambda n: n == "FEATURE_ACTION_GATEWAY"):
    app._handle_approval_callback_impl(cq4)

chk("a genuinely terminal contract is never (re-)executed via recovery", _dt4.call_count == 0)
_final4 = _real_gw._ledger.find_by_id(propose4.contract_id)
chk("the already-rejected contract stays 'rejected' (recovery never resurrects it)",
    _final4 is not None and _final4.status == "rejected")


# ══════════════════════════════════════════════════════════════════
print("\n── 5. no callback_contract_id at all (legacy 2-part callback_data) "
      "— recovery correctly declines, falls back to 'not available' exactly "
      "as before BUG-158 ──")

requester5 = _identity("req_bug158_no_contract_id")
approver5 = _identity("appr_bug158_no_contract_id")
action_id5, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add", "tool_inputs": {},
        "origin_channel": "telegram", "origin_chat_id": requester5.user_id,
        "canonical_user_id": requester5.memory_key, "user_chat_id": requester5.user_id,
        "channel": "telegram",
    },
    chat_id=requester5.user_id, label="legacy no contract_id",
)
_real_bus.pop(action_id5)

cq5 = _fake_cq(approver5.user_id, f"approve:{action_id5}")  # 2-part, no contract_id
mock_bot5 = MagicMock()


def _resolve5(channel, ext_id):
    return approver5 if ext_id == approver5.user_id else requester5


with patch.object(app, "bot", mock_bot5), \
     patch.object(app, "resolve_identity", side_effect=_resolve5), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt5, \
     patch.object(app, "_flag_enabled", side_effect=lambda n: n == "FEATURE_ACTION_GATEWAY"), \
     patch("feature_flags.is_enabled", side_effect=lambda n: n == "FEATURE_ACTION_GATEWAY"):
    app._handle_approval_callback_impl(cq5)

chk("without a contract_id to recover from, nothing is dispatched", _dt5.call_count == 0)
_sent_texts5 = [c.args[1] for c in mock_bot5.send_message.call_args_list if len(c.args) > 1]
chk("the 'not available' message is still shown (unchanged fallback, no regression)",
    any(app._MISSING_OR_EXPIRED_CALLBACK_TEXT in t for t in _sent_texts5))


print()
print("=" * 50)
print(f"BUG-158 (approval callback EventBus-TTL recovery) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
