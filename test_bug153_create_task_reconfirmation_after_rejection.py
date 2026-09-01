#!/usr/bin/env python3
"""
test_bug153_create_task_reconfirmation_after_rejection.py — BUG-153
(explicit new create_task request after rejection was blocked forever).

Problem (staging, 03/08/2026): after a user rejected a create_task
ActionContract, sending the exact same request again — even as a brand-new,
explicit inbound message — was blocked forever with "יצירת המשימה כבר
בוטלה" ("ActionGateway] propose blocked: business action already
rejected"). propose_action() only ever checked existing.status == "rejected"
and blocked unconditionally, with no way to distinguish an explicit new user
request from the Agent's own autonomous replay.

Fix (see docs/architecture/action-gateway/
BUG-153_CREATE_TASK_EXPLICIT_RECONFIRMATION_POLICY_20260804.md for the full
design/Cross-Layer Impact Matrix): propose_action()'s rejected-branch check
now carves out exactly one trusted_source value —
"deterministic_create_task" — set only by app.py's
_queue_deterministic_create_task() (the create_task router path, which never
runs from the Agent tool_use loop and is already protected upstream from
webhook-redelivery duplicates by the idempotency guard). Every other
trusted_source, especially "agent" (the raw Agent tool_use loop — autonomous
replay), keeps being blocked exactly as before.

This test proves:
  1. trusted_source="deterministic_create_task" opens a NEW contract when the
     fingerprint matches an existing "rejected" one.
  2. The old rejected contract is untouched — still "rejected", still
     independently retrievable by its own contract_id.
  3. trusted_source="agent" (autonomous replay) is still unconditionally
     blocked for the identical fingerprint — the guard this whole policy
     must never weaken.
  4. Every other trusted_source (e.g. "lead_capture") is also still blocked
     — the carve-out is scoped to exactly one string, not "any non-agent
     source".
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug153-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG153_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug153Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug153Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
# CodeRabbit follow-up: assignment (not setdefault) so an inherited/ambient
# value can never leave this test writing through to a real Airtable base —
# core/action_gateway.py's module-level singleton reads this flag once, at
# import time, to decide whether to wire a real ActionContractRepository.
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
from core.router.router import parse_deterministic_create_task  # noqa: E402
from event_bus import bus as _real_bus  # noqa: E402
from identity import Identity, Role  # noqa: E402
from types import SimpleNamespace  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


def _propose_and_reject(user_id: str, tool_inputs: dict):
    identity = _identity(user_id)
    propose = _real_gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=identity.memory_key,
        tool_name="airtable_add", tool_inputs=tool_inputs,
        origin_channel="telegram", origin_chat_id=user_id,
        requires_approval=True, identity=identity, trusted_source="agent",
    )
    assert propose.ok, f"setup propose failed: {propose.reason}"
    result = _real_gw.reject(propose.contract_id, rejected_by="test_user")
    assert result.startswith("🚫"), f"setup reject failed: {result}"
    return identity, propose.contract_id


# ══════════════════════════════════════════════════════════════════
print("── 1. explicit deterministic create_task reconfirmation opens a new contract ──")
identity1, old_contract_id1 = _propose_and_reject(
    "req_bug153_1", {"table": "Tasks", "fields": {"כותרת המשימה": "לבדוק את אימות 546"}},
)
retry1 = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=identity1.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "לבדוק את אימות 546"}},
    origin_channel="telegram", origin_chat_id="req_bug153_1",
    requires_approval=True, identity=identity1,
    trusted_source="deterministic_create_task",
)
chk("explicit create_task retry after rejection succeeds (ok=True)", retry1.ok)
chk("explicit create_task retry opens a DIFFERENT contract_id",
    retry1.contract_id and retry1.contract_id != old_contract_id1)

old_contract1 = _real_gw.find_contract(old_contract_id1)
chk("the OLD rejected contract is untouched — still 'rejected'",
    old_contract1 is not None and old_contract1.status == "rejected")

new_contract1 = _real_gw.find_contract(retry1.contract_id)
chk("the NEW contract is 'pending'",
    new_contract1 is not None and new_contract1.status == "pending")


# ══════════════════════════════════════════════════════════════════
print("\n── 2. autonomous Agent replay (trusted_source='agent') stays blocked ──")
identity2, old_contract_id2 = _propose_and_reject(
    "req_bug153_2", {"table": "Tasks", "fields": {"כותרת המשימה": "פעולה שנדחתה"}},
)
retry2 = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=identity2.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "פעולה שנדחתה"}},
    origin_channel="telegram", origin_chat_id="req_bug153_2",
    requires_approval=True, identity=identity2,
    trusted_source="agent",
)
chk("autonomous Agent replay is still blocked (ok=False)", not retry2.ok)
chk("autonomous Agent replay reason is 'business action already rejected'",
    retry2.reason == "business action already rejected")
chk("autonomous Agent replay returns the OLD contract_id, not a new one",
    retry2.contract_id == old_contract_id2)


# ══════════════════════════════════════════════════════════════════
print("\n── 3. every other trusted_source stays blocked (carve-out is scoped to one exact string) ──")
identity3, old_contract_id3 = _propose_and_reject(
    "req_bug153_3", {"table": "Tasks", "fields": {"כותרת המשימה": "עוד פעולה"}},
)
for other_source in ("lead_capture", "tma_api", "followup_engine", "test_harness"):
    retry3 = _real_gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=identity3.memory_key,
        tool_name="airtable_add",
        tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "עוד פעולה"}},
        origin_channel="telegram", origin_chat_id="req_bug153_3",
        requires_approval=True, identity=identity3,
        trusted_source=other_source,
    )
    chk(f"trusted_source={other_source!r} is still blocked after rejection", not retry3.ok)


# ══════════════════════════════════════════════════════════════════
# CodeRabbit follow-up: sections 1-3 above call ActionGateway.propose_action()
# directly with an explicit trusted_source="deterministic_create_task" — they
# do not prove app._queue_deterministic_create_task() actually FORWARDS that
# exact value through _queue_approval_detailed()/_queue_approval_detailed_impl().
# If that forwarding regressed back to the "agent" default, this whole test
# file would stay green while BUG-153 silently returned in production. This
# section drives the REAL end-to-end queue path instead.
# ══════════════════════════════════════════════════════════════════
print("\n── 4. end-to-end: app._queue_deterministic_create_task() forwards "
      "trusted_source correctly through the real queue chain ──")

identity4 = _identity("req_bug153_4")
title4 = "לבדוק את התקדמות הפרויקט"
task_parse4 = parse_deterministic_create_task(f"צור משימה {title4}")
assert task_parse4.certain

mock_bot4 = MagicMock()


def _resolve_identity4(channel, ext_id):
    return identity4


with patch.object(app, "bot", mock_bot4), \
     patch.object(app, "resolve_identity", side_effect=_resolve_identity4), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": identity4.user_id}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    first_outcome = app._queue_deterministic_create_task(
        title4, identity4.user_id, "telegram", f"צור משימה {title4}", identity4,
        task_parse=task_parse4,
    )

chk("end-to-end: first request creates a live contract",
    len(_real_gw.find_live_contracts(identity4.memory_key)) == 1)
first_contract4 = _real_gw.find_live_contracts(identity4.memory_key)[0]

# Reject through the REAL production callback path (_handle_approval_callback_
# impl(), action="reject") rather than calling ActionGateway.reject() directly
# — the latter only clears the ActionGateway contract and leaves the separate
# EventBus pending item (created by the same _queue_deterministic_create_task()
# call above) live, which would then make the second request below hit
# EventBus's OWN "כבר ממתינה לאישור הבעלים" cross-channel-duplicate guard
# before it ever reaches propose_action()'s BUG-153 branch at all — a false
# pass/fail that wouldn't reflect how a real Telegram "❌ בטל" press behaves.
_pending_action_id4 = next(
    action_id for action_id, entry in _real_bus._pending._store.items()
    if entry.get("chat_id") == identity4.user_id
)
_reject_cq4 = SimpleNamespace(
    id="cbq-bug153-4",
    data=f"reject:{_pending_action_id4}:{first_contract4.contract_id}",
    from_user=SimpleNamespace(id=identity4.user_id),
    message=SimpleNamespace(chat=SimpleNamespace(id="chat-bug153-4"), message_id=1),
)
with patch.object(app, "bot", MagicMock()), \
     patch.object(app, "resolve_identity", side_effect=_resolve_identity4), \
     patch.object(app, "_flag_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"), \
     patch.object(app, "_tc8_claim_contract", return_value=None), \
     patch.object(app, "_tc8_finish_contract"):
    # Fixture isolation: this test targets BUG-153's ActionGateway/callback
    # contract. TC8 is a separate durable coordination boundary and requires
    # PostgreSQL; keeping it out here makes the focused regression deterministic
    # in the same no-DB environment used by the persistence-off setup above.
    app._handle_approval_callback_impl(_reject_cq4)

chk(
    "end-to-end: setup rejection (real callback path) leaves the contract "
    "'rejected'",
    _real_gw.find_contract(first_contract4.contract_id).status == "rejected",
)

mock_bot4b = MagicMock()
with patch.object(app, "bot", mock_bot4b), \
     patch.object(app, "resolve_identity", side_effect=_resolve_identity4), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": identity4.user_id}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    second_outcome = app._queue_deterministic_create_task(
        title4, identity4.user_id, "telegram", f"צור משימה {title4}", identity4,
        task_parse=task_parse4,
    )

live_after4 = _real_gw.find_live_contracts(identity4.memory_key)
chk(
    "end-to-end: the identical request, resent through the real deterministic "
    "queue path after rejection, opens a NEW live (pending) contract — proves "
    "trusted_source='deterministic_create_task' actually reaches "
    "propose_action() through _queue_approval_detailed()/_impl(), not just "
    "when set directly in a unit test",
    len(live_after4) == 1 and live_after4[0].contract_id != first_contract4.contract_id,
)
chk(
    "end-to-end: the old rejected contract is still 'rejected', untouched",
    _real_gw.find_contract(first_contract4.contract_id).status == "rejected",
)
chk(
    "end-to-end: the second (post-rejection) response never claims the "
    "action was already cancelled/blocked",
    "כבר בוטלה" not in (second_outcome or ""),
)


print()
print("=" * 50)
print(f"BUG-153 (create_task reconfirmation after rejection) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
