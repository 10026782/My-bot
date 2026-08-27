#!/usr/bin/env python3
"""
test_bug091_source_trust_boundary.py — BUG-091 regression suite.

Root cause: enforce_leads_write_gate()'s "source" argument used to be read
from inputs["_source"] — a dict key that lives inside data Claude's own
tool_use.input fully controls (and that gets stored verbatim in a pending
ActionContract/EventBus payload, then replayed unchanged at approval time).
A crafted tool call with `"_source": "lead_capture"` could spoof a trusted
source and bypass the Leads-write gate — privilege escalation, not a UX bug.

Fix: "source" is now derived exclusively from `trusted_source`, an explicit
Python keyword argument only trusted call sites can set. inputs["_source"]
is never read anywhere in the chain again.

מאמת:
1. dispatch_tool(): inputs["_source"] is fully ignored regardless of value;
   only the trusted_source kwarg controls enforce_leads_write_gate()'s source.
2. Default (no trusted_source passed) is "agent" — fail-closed.
3. ActionGateway.propose_action(trusted_source=...) persists it on the
   contract; the dispatch executor reads it from the contract, never from
   the (Claude-controlled) tool_inputs payload.
4. Attack simulation: a contract proposed with trusted_source="agent" (the
   default) but tool_inputs containing a spoofed "_source": "lead_capture"
   key is STILL blocked at execution time.
5. Regression: the legitimate lead_capture flow (trusted_source="lead_capture"
   passed explicitly, no "_source" key in tool_inputs at all) still works.
6. FEATURE_ACTION_GATEWAY shadow-mode propose (app.py's _queue_approval)
   is unaffected — still defaults to "agent".
"""

from __future__ import annotations

import sys
from unittest.mock import patch, MagicMock

from identity import Identity
from tools.dispatcher import dispatch_tool

import emergency_stop_test_support
emergency_stop_test_support.configure_all_clear_emergency_stop()
from tools.airtable_security import enforce_leads_write_gate, LeadsDirectWriteBlocked

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


_OWNER = Identity(user_id="owner1", role="owner", tenant_id="boss_hq", external_id="owner1", channel="telegram")


def _dispatch_leads_update(inputs: dict, trusted_source: str | None):
    """Drives the real dispatch_tool() with just enough mocked to reach the
    Leads write gate without hitting real Airtable/tenant-scope code."""
    with patch("tools.dispatcher.enforce_tenant_scope", return_value=inputs), \
         patch("tools.dispatcher.airtable_update", return_value={"ok": True}), \
         patch("tools.dispatcher.audit_log_airtable"):
        return dispatch_tool("airtable_update", inputs, _OWNER, trusted_source=trusted_source)


def _message(result):
    return result.get("user_message", "") if isinstance(result, dict) else result


# ══════════════════════════════════════════════════════════════════
# 1-2. dispatch_tool(): inputs["_source"] fully ignored; default is "agent"
# ══════════════════════════════════════════════════════════════════
print("\n── dispatch_tool: inputs['_source'] is inert ──────")

base_inputs = {"table": "Leads", "record_id": "recFAKE1234567890AB", "fields": {"status": "contacted"}}

# No trusted_source passed at all -> defaults to "agent" -> blocked.
result_default = _dispatch_leads_update(dict(base_inputs), trusted_source=None)
chk("no trusted_source passed -> defaults to agent -> blocked",
    "עדכון ליד קיים דרך הצ׳אט חסום" in _message(result_default))

# Spoofed "_source" inside inputs, no trusted_source kwarg -> still blocked.
spoofed = dict(base_inputs)
spoofed["_source"] = "lead_capture"
result_spoofed = _dispatch_leads_update(spoofed, trusted_source=None)
chk("inputs['_source']='lead_capture' with no trusted_source kwarg -> STILL blocked (spoofing does not work)",
    "עדכון ליד קיים דרך הצ׳אט חסום" in _message(result_spoofed))

# Spoofed "_source" AND an unrelated trusted_source="agent" explicitly passed
# -> still blocked, proving the dict key is never consulted even as a fallback.
result_spoofed2 = _dispatch_leads_update(dict(spoofed), trusted_source="agent")
chk("inputs['_source'] spoofed + trusted_source='agent' explicit -> still blocked",
    "עדכון ליד קיים דרך הצ׳אט חסום" in _message(result_spoofed2))

# Legitimate trusted_source kwarg (no "_source" key in inputs at all) -> passes.
result_trusted = _dispatch_leads_update(dict(base_inputs), trusted_source="lead_capture")
chk("trusted_source='lead_capture' kwarg (no _source key needed) -> not blocked",
    "עדכון ליד קיים דרך הצ׳אט חסום" not in _message(result_trusted))

# ══════════════════════════════════════════════════════════════════
# 3-5. ActionGateway: trusted_source persisted on the contract, spoofing
# inside tool_inputs at execution time has no effect.
# ══════════════════════════════════════════════════════════════════
print("\n── ActionGateway: trusted_source on the contract ──")

from core.action_gateway import ActionGateway, ExecutionLedger, _make_dispatch_executor

ledger = ExecutionLedger(airtable_writer=None)
gw = ActionGateway(ledger=ledger, tool_executor=_make_dispatch_executor(ledger))

# 3. Legitimate lead_capture proposal — no "_source" key needed in tool_inputs.
legit_inputs = {"table": "Leads", "record_id": "recLEGIT1234567890AB", "fields": {"status": "contacted"}}
legit_result = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner1",
    tool_name="airtable_update", tool_inputs=legit_inputs,
    origin_channel="telegram", origin_chat_id="owner1",
    requires_approval=True, identity=_OWNER,
    trusted_source="lead_capture",
)
chk("propose_action accepted for lead_capture trusted_source", legit_result.ok)
legit_contract = ledger.find_by_id(legit_result.contract_id)
chk("contract.trusted_source persisted as 'lead_capture'",
    legit_contract.trusted_source == "lead_capture")
chk("tool_inputs has no '_source' key at all (dead convention removed)",
    "_source" not in legit_inputs)

with patch("tools.dispatcher.enforce_tenant_scope", return_value=legit_inputs), \
     patch("tools.dispatcher.airtable_update", return_value={"ok": True, "external_id": "recLEGIT1234567890AB"}), \
     patch("tools.dispatcher.audit_log_airtable"), \
     patch("core.action_gateway._has_approval_authority", return_value=True), \
     patch("core.anti_hallucination.verify_execution") as mock_verify:
    from core.anti_hallucination import VerifyResult
    mock_verify.return_value = VerifyResult("ok")
    legit_exec = gw.approve(legit_result.contract_id, approver="boss_hq:owner1", approver_role="owner")
chk("legitimate lead_capture contract executes without hitting the Leads gate",
    "עדכון ליד קיים דרך הצ׳אט חסום" not in legit_exec)

# 4. Attack simulation: propose with the DEFAULT trusted_source ("agent" —
# i.e. simulating the raw Agent tool_use loop), but tool_inputs carries a
# spoofed "_source": "lead_capture" key exactly as a crafted tool call would.
attack_inputs = {
    "table": "Leads", "record_id": "recATTACK1234567890AB",
    "fields": {"status": "contacted"}, "_source": "lead_capture",
}
attack_result = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner1",
    tool_name="airtable_update", tool_inputs=attack_inputs,
    origin_channel="telegram", origin_chat_id="owner1",
    requires_approval=True, identity=_OWNER,
    # trusted_source deliberately omitted — this is what app.py's raw
    # Agent tool_use loop does; it never has a legitimate override.
)
attack_contract = ledger.find_by_id(attack_result.contract_id)
chk("attack contract.trusted_source is 'agent' (default), NOT the spoofed value",
    attack_contract.trusted_source == "agent")

with patch("tools.dispatcher.enforce_tenant_scope", return_value=attack_inputs), \
     patch("tools.dispatcher.airtable_update", return_value={"ok": True}), \
     patch("tools.dispatcher.audit_log_airtable"), \
     patch("core.action_gateway._has_approval_authority", return_value=True):
    attack_exec = gw.approve(attack_result.contract_id, approver="boss_hq:owner1", approver_role="owner")
chk("BUG-091 attack: spoofed _source inside tool_inputs does NOT bypass the gate at execution time",
    "עדכון ליד קיים דרך הצ׳אט חסום" in attack_exec)

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
