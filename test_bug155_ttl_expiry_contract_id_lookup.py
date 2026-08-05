#!/usr/bin/env python3
"""
test_bug155_ttl_expiry_contract_id_lookup.py — BUG-155 (TTL expiry did not
close a live ActionContract when its fingerprint_payload diverged from its
tool_inputs).

Problem (staging, 03/08/2026): a deterministic create_task ActionContract is
proposed with fingerprint_payload=task_parse.business_identity() (includes
due_time) while its write tool_inputs/task_fields does NOT include due_time
(BUG-156 — the two payloads diverge whenever the task has a due_time).
app._reject_stale_telegram_approval() (the TTL-expired Telegram callback
path) used to identify the contract to reject by RECOMPUTING
business_action_fingerprint from payload["tool_inputs"] alone — for any
contract whose original fingerprint came from a different fingerprint_payload,
that recomputed fingerprint does not match the real one, find_by_fingerprint()
returns nothing, and reject() is silently never called. The user was told
"TTL expired — not executed" while the ActionContract stayed live/pending
indefinitely — it could later be approved and executed, or block a fresh
non-duplicate request via find_live_contracts()/BUG-122's boundary.

Fix: _reject_stale_telegram_approval() now looks the contract up directly by
the contract_id already saved on the bus payload at propose time (the same
id app.py's bus.request_approval() call already stores in
payload["contract_id"]) instead of recomputing a fingerprint. The fingerprint
recompute is kept only as a fallback for payloads with no stored contract_id.

This test reproduces the exact divergent-payload shape (fingerprint_payload
with due_time, tool_inputs without) and proves the TTL-expired callback path
now transitions the contract to 'rejected' — the same outcome test_bug112's
"seed_contract" harness always got right, because that harness never
constructs a fingerprint_payload distinct from tool_inputs and never omits
contract_id, so it could not have caught this class of bug.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug155-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG155_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug155Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug155Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
# CodeRabbit follow-up: assignment (not setdefault) so an inherited/ambient
# value can never leave this test writing through to a real Airtable base —
# core/action_gateway.py's module-level singleton reads this flag once, at
# import time, to decide whether to wire a real ActionContractRepository.
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

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
    return {"ok": True, "tool": "airtable_add", "external_id": "audit-ok",
            "evidence": {"audit_id": "audit-ok"}, "user_message": "✅ בוצע"}


print("── BUG-155: TTL-expired callback with divergent fingerprint_payload ──")

requester = _identity("req_bug155_1", Role.OWNER)
approver = _identity("appr_bug155_1", Role.OWNER)

# Mirrors _queue_deterministic_create_task(): the write payload (task_fields)
# has no due_time (BUG-156), but the fingerprint_payload used at propose time
# (task_parse.business_identity()) does — the exact divergence that broke the
# naive fingerprint-recompute lookup.
task_fields = {"table": "Tasks", "fields": {"כותרת המשימה": "לבדוק את אימות 546 המעודכן", "תאריך יעד": "2026-08-05"}}
fingerprint_payload = {
    "table": "Tasks",
    "fields": {"title": "לבדוק את אימות 546 המעודכן", "due_date": "2026-08-05", "due_time": "10:30"},
}

propose = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester.memory_key,
    tool_name="airtable_add", tool_inputs=task_fields,
    origin_channel="telegram", origin_chat_id=requester.user_id,
    requires_approval=True, identity=requester, trusted_source="agent",
    fingerprint_payload=fingerprint_payload,
)
chk("setup: contract proposed successfully", propose.ok and propose.contract_id)
contract_id = propose.contract_id

# Mirrors app._queue_approval_detailed_impl()'s real bus.request_approval()
# payload shape exactly — including the stored contract_id (app.py:1612) that
# the old code never consulted.
action_id, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add",
        "tool_inputs": task_fields,
        "origin_channel": "telegram",
        "origin_chat_id": requester.user_id,
        "canonical_user_id": requester.memory_key,
        "user_chat_id": requester.user_id,
        "channel": "telegram",
        "contract_id": contract_id,
    },
    chat_id=requester.user_id,
    label="לבדוק את אימות 546 המעודכן",
)

# Backdate past the 10-minute advertised TTL, well under event_bus's own
# 30-minute internal TTL (bus.pop() must still hand the item back).
backdated = (datetime.now() - timedelta(seconds=700)).isoformat()
_real_bus._pending._store[action_id]["created"] = backdated


def _resolve_identity_side_effect(channel, ext_id):
    return approver if ext_id == approver.user_id else requester


cq = _fake_cq(approver.user_id, f"approve:{action_id}")
mock_bot = MagicMock()


def _flag_side_effect(name):
    return name in ("FEATURE_ACTION_GATEWAY", "FEATURE_SINGLE_SPEAKER_APPROVAL_UX")

with patch.object(app, "bot", mock_bot), \
     patch.object(app, "resolve_identity", side_effect=_resolve_identity_side_effect), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_gw, \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy, \
     patch.object(app, "_flag_enabled", side_effect=_flag_side_effect), \
     patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
    app._handle_approval_callback_impl(cq)

total_dispatch_calls = _dt_gw.call_count + _dt_legacy.call_count
final_contract = _real_gw._ledger.find_by_id(contract_id)

chk("TTL-expired callback does not dispatch/execute", total_dispatch_calls == 0)
chk(
    "TTL-expired callback transitions the divergent-fingerprint contract to "
    "'rejected' (was silently staying 'pending' before the fix)",
    final_contract is not None and final_contract.status == "rejected",
)
chk(
    "the rejected contract is no longer counted as live",
    propose.contract_id not in {
        c.contract_id for c in _real_gw.find_live_contracts(requester.memory_key)
    },
)

# Regression guard: the fallback fingerprint-recompute path must still work
# for a payload with no stored contract_id at all (legacy/non-Gateway-tracked
# shape) — same-shaped tool_inputs/fingerprint_payload this time (no
# divergence), matching what that fallback path can actually resolve.
requester2 = _identity("req_bug155_2", Role.OWNER)
approver2 = _identity("appr_bug155_2", Role.OWNER)
plain_inputs = {"table": "Tasks", "fields": {"כותרת המשימה": "פשוט", "תאריך יעד": "2026-08-06"}}
propose2 = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester2.memory_key,
    tool_name="airtable_add", tool_inputs=plain_inputs,
    origin_channel="telegram", origin_chat_id=requester2.user_id,
    requires_approval=True, identity=requester2, trusted_source="agent",
)
action_id2, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add",
        "tool_inputs": plain_inputs,
        "origin_channel": "telegram",
        "origin_chat_id": requester2.user_id,
        "canonical_user_id": requester2.memory_key,
        "user_chat_id": requester2.user_id,
        "channel": "telegram",
        # deliberately no "contract_id" key — legacy/fallback shape
    },
    chat_id=requester2.user_id,
    label="פשוט",
)
backdated2 = (datetime.now() - timedelta(seconds=700)).isoformat()
_real_bus._pending._store[action_id2]["created"] = backdated2


def _resolve_identity_side_effect2(channel, ext_id):
    # Own resolver for scenario 2 — deliberately does not fall back to
    # scenario 1's module-scope requester/approver (CodeRabbit follow-up:
    # the original shared _resolve_identity_side_effect() resolved any
    # ext_id other than scenario 1's approver.user_id to scenario 1's
    # requester, silently misresolving scenario 2's identities whenever
    # this flow ever legitimately depends on resolve_identity()'s result).
    return approver2 if ext_id == approver2.user_id else requester2


cq2 = _fake_cq(approver2.user_id, f"approve:{action_id2}")
mock_bot2 = MagicMock()
with patch.object(app, "bot", mock_bot2), \
     patch.object(app, "resolve_identity", side_effect=_resolve_identity_side_effect2), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch), \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch), \
     patch.object(app, "_flag_enabled", side_effect=_flag_side_effect), \
     patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
    app._handle_approval_callback_impl(cq2)

final_contract2 = _real_gw._ledger.find_by_id(propose2.contract_id)
chk(
    "fallback path (no contract_id in payload, matching tool_inputs/fingerprint) "
    "still rejects correctly",
    final_contract2 is not None and final_contract2.status == "rejected",
)

print()
print("=" * 50)
print(f"BUG-155 (TTL expiry contract_id lookup) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
