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

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug153-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG153_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug153Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug153Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.action_gateway import action_gateway as _real_gw  # noqa: E402
from identity import Identity, Role  # noqa: E402

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


print()
print("=" * 50)
print(f"BUG-153 (create_task reconfirmation after rejection) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
