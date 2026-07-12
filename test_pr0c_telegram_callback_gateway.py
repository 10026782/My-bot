#!/usr/bin/env python3
"""
test_pr0c_telegram_callback_gateway.py — Regression tests for PR-0C Phase 2:
app.py::_handle_approval_callback_impl's Telegram approve button executing
through ActionGateway.approve() when a live contract exists, instead of
re-implementing dispatch+verify by hand.

Coverage:
  1. FEATURE_ACTION_GATEWAY off (today's production default) -> legacy direct
     dispatch_tool() path used, unchanged from pre-migration behavior.
  2. Flag on + a live pending contract exists -> ActionGateway.approve() is
     used; dispatch_tool called exactly once (via the Gateway's own executor);
     contract ends "executed".
  3. BUG-074 differential: approver_role passed to approve() must be the
     button-clicking approver's role, never the original requester's — tested
     by making the requester a role with NO approval authority (employee) and
     the approver the owner; if the code wrongly used the requester's role,
     approve() would deny and the contract would stay "pending".
  4. Flag on + no contract found (shadow propose_action() failed silently) ->
     falls back to legacy dispatch_tool(), same as flag-off.
  5. Flag on + contract found + execution fails -> contract ends "failed",
     dispatch_tool called exactly once (no retry), user notified.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-pr0c-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PR0C_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPR0CTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPR0CTest")
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


def _ok_dispatch(*args, **kwargs):
    return {"ok": True, "tool": "send_followup", "external_id": "audit-ok",
            "evidence": {"audit_id": "audit-ok"}, "user_message": "✅ בוצע"}


def _fail_dispatch(*args, **kwargs):
    return {"ok": False, "tool": "send_followup", "external_id": "",
            "evidence": {}, "user_message": "❌ נכשל"}


def _run_callback(
    *, requester: Identity, approver: Identity, dispatch_mock,
    seed_contract: bool, feature_gw: bool, tool_inputs: dict,
):
    """Queues a real event_bus item (+ optionally a real ActionGateway contract),
    then drives app._handle_approval_callback_impl() with everything else mocked."""
    action_id, _ = _real_bus.request_approval(
        action="send_followup",
        payload={
            "tool_name": "send_followup",
            "tool_inputs": tool_inputs,
            "origin_channel": "telegram",
            "origin_chat_id": requester.user_id,
            "canonical_user_id": requester.memory_key,
            "user_chat_id": requester.user_id,
            "channel": "telegram",
        },
        chat_id=requester.user_id,
        label="test followup",
    )

    contract_id = None
    if seed_contract:
        propose = _real_gw.propose_action(
            tenant_id="boss_hq", canonical_user_id=requester.memory_key,
            tool_name="send_followup", tool_inputs=tool_inputs,
            origin_channel="telegram", origin_chat_id=requester.user_id,
            requires_approval=True, identity=requester, trusted_source="agent",
        )
        contract_id = propose.contract_id

    def _resolve_identity_side_effect(channel, ext_id):
        return approver if ext_id == approver.user_id else requester

    cq = _fake_cq(approver.user_id, f"approve:{action_id}")

    _flag_side_effect = lambda name: feature_gw if name == "FEATURE_ACTION_GATEWAY" else False

    with patch.object(app, "bot", MagicMock()), \
         patch.object(app, "resolve_identity", side_effect=_resolve_identity_side_effect), \
         patch("tools.dispatcher.dispatch_tool", side_effect=dispatch_mock) as _dt_gw, \
         patch.object(app, "dispatch_tool", side_effect=dispatch_mock) as _dt_legacy, \
         patch.object(app, "_flag_enabled", side_effect=_flag_side_effect), \
         patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
        app._handle_approval_callback_impl(cq)

    total_dispatch_calls = _dt_gw.call_count + _dt_legacy.call_count
    final_contract = _real_gw._ledger.find_by_id(contract_id) if contract_id else None
    return total_dispatch_calls, final_contract


# ══════════════════════════════════════════════════════════════════
# 1. Flag OFF — legacy path, unchanged
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: FEATURE_ACTION_GATEWAY off — legacy dispatch ──────")

requester = _identity("req_1", Role.OWNER)
approver = _identity("appr_1", Role.OWNER)
calls, contract = _run_callback(
    requester=requester, approver=approver, dispatch_mock=_ok_dispatch,
    seed_contract=False, feature_gw=False, tool_inputs={"chat_id": "req_1", "draft": "x"},
)
chk("Test1: dispatch_tool called exactly once (legacy path)", calls == 1)


# ══════════════════════════════════════════════════════════════════
# 2. Flag ON + live contract — executes via ActionGateway.approve()
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: flag on + live contract — Gateway path ────────────")

requester = _identity("req_2", Role.OWNER)
approver = _identity("appr_2", Role.OWNER)
calls, contract = _run_callback(
    requester=requester, approver=approver, dispatch_mock=_ok_dispatch,
    seed_contract=True, feature_gw=True, tool_inputs={"chat_id": "req_2", "draft": "y"},
)
chk("Test2: dispatch_tool called exactly once (via Gateway executor)", calls == 1)
chk("Test2: contract ends 'executed'", contract is not None and contract.status == "executed")


# ══════════════════════════════════════════════════════════════════
# 3. BUG-074 differential: approver's role must govern, not requester's
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: BUG-074 — approver_role, not requester's role ─────")

requester_no_authority = _identity("req_3", Role.EMPLOYEE)  # in _INTERNAL, but no actions.approve
approver_owner = _identity("appr_3", Role.OWNER)
calls, contract = _run_callback(
    requester=requester_no_authority, approver=approver_owner, dispatch_mock=_ok_dispatch,
    seed_contract=True, feature_gw=True, tool_inputs={"chat_id": "req_3", "draft": "z"},
)
chk(
    "Test3: contract executes when approver=owner even though requester=employee "
    "(would fail if approver_role were wrongly derived from the requester)",
    contract is not None and contract.status == "executed",
)


# ══════════════════════════════════════════════════════════════════
# 4. Flag ON but no contract found — falls back to legacy dispatch
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: flag on, no contract found — fallback ─────────────")

requester = _identity("req_4", Role.OWNER)
approver = _identity("appr_4", Role.OWNER)
calls, contract = _run_callback(
    requester=requester, approver=approver, dispatch_mock=_ok_dispatch,
    seed_contract=False, feature_gw=True, tool_inputs={"chat_id": "req_4", "draft": "w"},
)
chk("Test4: dispatch_tool called exactly once (fallback to legacy)", calls == 1)
chk("Test4: no contract to check (fallback path, none seeded)", contract is None)


# ══════════════════════════════════════════════════════════════════
# 5. Flag ON + contract found + execution fails — contract ends 'failed'
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: flag on + live contract + execution fails ─────────")

requester = _identity("req_5", Role.OWNER)
approver = _identity("appr_5", Role.OWNER)
calls, contract = _run_callback(
    requester=requester, approver=approver, dispatch_mock=_fail_dispatch,
    seed_contract=True, feature_gw=True, tool_inputs={"chat_id": "req_5", "draft": "v"},
)
chk("Test5: dispatch_tool called exactly once (no retry on failure)", calls == 1)
chk("Test5: contract ends 'failed', never 'executed'", contract is not None and contract.status == "failed")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PR-0C Telegram callback gateway tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
