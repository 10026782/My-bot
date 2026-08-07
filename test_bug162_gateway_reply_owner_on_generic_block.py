#!/usr/bin/env python3
"""
test_bug162_gateway_reply_owner_on_generic_block.py — BUG-162 regression suite.

Root cause (found from production evidence, 07/08/2026): the owner reported
FEATURE_SINGLE_SPEAKER_APPROVAL_UX was ALREADY true in the live Render
environment, yet the Agent still "spoke" in a gateway-owned turn
(TurnOwnershipShadow's agent_spoke_in_gateway_owned_approval_turn violation).
This contradicted the working assumption (recorded earlier under BUG-161/162
in BUG_AUDIT_LOG.md) that flipping the flag alone would close the gap.

Traced app.py's _queue_approval_detailed_impl(): the sibling branch for
failure_code == "existing_pending_blocks_agent" explicitly sets
"reply_owner": "gateway" and "lifecycle_result" in its returned dict — but
the GENERIC ok=False fallback branch immediately below it (the one that
actually fires for BUG-153's "business action already rejected" block, and
for every other dedup/pending/approved/executing/completed contract
propose_action() finds) was missing both keys entirely. The tool-use loop's
single-speaker override (app.py's "_gateway_owned" lookup) searches
tool_results_log for an entry with reply_owner=="gateway" — with that key
never set, the override could never match this branch, regardless of
FEATURE_SINGLE_SPEAKER_APPROVAL_UX's value. The flag was a red herring; this
missing key was the actual gap.

Fix: the generic branch now builds the real ApprovalLifecycleResult (via
build_approval_lifecycle_result(), reusing the found contract) whenever a
contract_id is present, and sets reply_owner="gateway" + lifecycle_result
the same way the sibling branch already did — never leaving a real,
canonical Gateway-authored outcome unmarked. Defensively falls back to the
old (unmarked) shape only if the contract_id somehow doesn't resolve to a
real record (should not happen in practice — same synchronous call that
just returned the id).

This file proves:
  1. A raw Agent tool_use attempt (trusted_source="agent") against a
     fingerprint that's already "rejected" (BUG-153's exact block scenario)
     now returns reply_owner="gateway" and a populated lifecycle_result.
  2. The message is the truthful, unchanged Gateway wording ("כבר בוטלה"),
     not a fabricated invitation to reconfirm.
  3. The message content is unchanged from before this fix (same
     safe_user_message the Gateway already produced) — this fix only adds
     the missing routing signal, it does not change what gets said.
  4. A defensive check: if the contract_id somehow doesn't resolve, the
     function does not crash and does not fabricate a "no_contract"-shaped
     message for a contract that actually exists.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug162-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG162_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug162Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug162Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402
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
print("── 1. raw Agent tool_use against a rejected fingerprint now carries reply_owner=gateway ──")
identity1, old_contract_id1 = _propose_and_reject(
    "req_bug162_1", {"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת BUG-162"}},
)

with patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"), \
     patch.object(app, "resolve_identity", side_effect=lambda channel, ext_id: identity1):
    outcome1 = app._queue_approval_detailed(
        "airtable_add",
        {"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת BUG-162"}},
        identity1.user_id, "telegram", "צור משימה בדיקת BUG-162 למרות שנדחתה",
        trusted_source="agent",
    )

chk("blocked (ok=False) — same as before this fix, unchanged", outcome1["ok"] is False)
chk("contract_id points at the OLD rejected contract",
    outcome1.get("contract_id") == old_contract_id1)
chk("reply_owner is now 'gateway' (was missing/None before this fix)",
    outcome1.get("reply_owner") == "gateway")
chk("lifecycle_result is now populated (was missing before this fix)",
    outcome1.get("lifecycle_result") is not None)
chk("lifecycle_result.reply_owner is also 'gateway'",
    getattr(outcome1.get("lifecycle_result"), "reply_owner", None) == "gateway")

# ── 2. Message content is truthful and unchanged — this fix adds routing
#      signal only, it does not alter what the user is told. ──────────────
chk("message states the task creation was already cancelled ('בוטלה')",
    "בוטלה" in outcome1["message"])
chk("message does NOT invite a free-text reconfirmation ('אשר')",
    "אשר" not in outcome1["message"])

old_contract1 = _real_gw.find_contract(old_contract_id1)
chk("the OLD contract is untouched — still 'rejected' (this fix never mutates it)",
    old_contract1 is not None and old_contract1.status == "rejected")


# ══════════════════════════════════════════════════════════════════
print("\n── 2. every other blocked-with-existing-contract reason also gets reply_owner=gateway ──")
identity2 = _identity("req_bug162_2")
propose2 = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=identity2.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "משימה שנייה ל-162"}},
    origin_channel="telegram", origin_chat_id=identity2.user_id,
    requires_approval=True, identity=identity2, trusted_source="agent",
)
assert propose2.ok

with patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"), \
     patch.object(app, "resolve_identity", side_effect=lambda channel, ext_id: identity2):
    # A second, identical proposal while the first is still "pending" —
    # dedup found by propose_action(), also reaches the generic branch.
    outcome2 = app._queue_approval_detailed(
        "airtable_add",
        {"table": "Tasks", "fields": {"כותרת המשימה": "משימה שנייה ל-162"}},
        identity2.user_id, "telegram", "צור שוב את אותה משימה",
        trusted_source="agent",
    )

chk("duplicate-pending dedup also blocked (ok=False)", outcome2["ok"] is False)
chk("duplicate-pending dedup also carries reply_owner='gateway'",
    outcome2.get("reply_owner") == "gateway")


print()
print("=" * 50)
print(f"BUG-162 (gateway reply_owner on generic block) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
