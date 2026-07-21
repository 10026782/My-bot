#!/usr/bin/env python3
"""
test_pr0c_action_gateway_adapters.py — Regression tests for PR-0C Phase 1:
media_save_to_memory / send_followup / send_recovery as real ActionGateway-
executable dispatcher tools.

Coverage:
  1. tools/approval_actions.py functions mirror the original event_bus
     .confirmed handlers' behavior (success/failure paths), returning the
     C53-A structured {ok, tool, external_id, evidence, user_message} contract.
  2. tool_registry: registered, roles_allowed=_INTERNAL, requires_approval=True.
  3. dispatcher: routes each tool name to the new approval_actions functions.
  4. Hidden from the Agent: not present in tools/schemas.py's TOOL_SCHEMAS.
  5. core/anti_hallucination.verify_execution accepts a valid result and
     fails closed on one missing evidence.
  6. End-to-end: ActionGateway.propose_action() -> approve() -> dispatch_tool()
     -> approval_actions.* -> verify_execution(), contract ends "executed".
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
# 1. tools/approval_actions.py — direct unit tests
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: approval_actions functions ────────────────────────")

import tools.approval_actions as approval_actions

with patch("tools.airtable_gateway.airtable_create", return_value={"id": "recMEM1"}):
    result = approval_actions.media_save_to_memory("hello transcript", "general", "voice")
chk("media_save_to_memory: ok=True on real record", result["ok"] is True)
chk("media_save_to_memory: external_id set", result["external_id"] == "recMEM1")
chk("media_save_to_memory: tool name in result", result["tool"] == "media_save_to_memory")

with patch("tools.airtable_gateway.airtable_create", return_value=None):
    result = approval_actions.media_save_to_memory("hello transcript", "general", "voice")
chk("media_save_to_memory: ok=False when Airtable returns nothing", result["ok"] is False)


_gw_result_ok = SimpleNamespace(audit_id="audit123", action_result=SimpleNamespace(delivery_success=True))

with patch("core.output_gateway.send_outbound", return_value=_gw_result_ok), \
     patch("lead_memory.lead_memory") as _lm:
    _lm.get.return_value = SimpleNamespace(followup_count=2)
    result = approval_actions.send_followup(
        chat_id="123", draft="draft text", contact_name="דני", channel="whatsapp", memory_key="mk1",
    )
chk("send_followup: ok=True on successful send", result["ok"] is True)
chk("send_followup: evidence carries audit_id", result["evidence"].get("audit_id") == "audit123")
chk("send_followup: followup_count incremented", _lm.update.call_args.kwargs.get("followup_count") == 3)

with patch("core.output_gateway.send_outbound", side_effect=RuntimeError("boom")):
    result = approval_actions.send_followup(chat_id="123", draft="x")
chk("send_followup: ok=False on send_outbound exception", result["ok"] is False)


with patch("core.output_gateway.send_outbound", return_value=_gw_result_ok):
    result = approval_actions.send_recovery(
        chat_id="123", draft="draft", contact_name="דני", channel="whatsapp", memory_key="mk1", tier="hot",
    )
chk("send_recovery: ok=True when owner delivery verified", result["ok"] is True)

_gw_result_unverified = SimpleNamespace(audit_id="audit999", action_result=SimpleNamespace(delivery_success=False))
with patch("core.output_gateway.send_outbound", return_value=_gw_result_unverified):
    result = approval_actions.send_recovery(chat_id="123", draft="draft")
chk("send_recovery: ok=False when owner delivery NOT verified", result["ok"] is False)


# ══════════════════════════════════════════════════════════════════
# 2. tool_registry — registration + roles
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: tool_registry entries ─────────────────────────────")

import tool_registry

for name in ("media_save_to_memory", "send_followup", "send_recovery"):
    meta = tool_registry.get(name)
    chk(f"{name}: registered in tool_registry", meta is not None)
    chk(f"{name}: requires_approval=True", bool(meta and meta.requires_approval))
    chk(f"{name}: owner allowed", bool(meta and "owner" in meta.roles_allowed))
    chk(f"{name}: lead NOT allowed", bool(meta and "lead" not in meta.roles_allowed))


# ══════════════════════════════════════════════════════════════════
# 3. dispatcher — routes to the new functions
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: dispatcher routing ────────────────────────────────")

import inspect
from tools.dispatcher import dispatch_tool

import emergency_stop_test_support
emergency_stop_test_support.configure_all_clear_emergency_stop()
src = inspect.getsource(dispatch_tool)
for name in ("media_save_to_memory", "send_followup", "send_recovery"):
    chk(f'dispatcher has case "{name}"', f'case "{name}"' in src)


# ══════════════════════════════════════════════════════════════════
# 4. Hidden from the Agent — not in TOOL_SCHEMAS
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: hidden from Agent tool_use ────────────────────────")

from tools.schemas import TOOL_SCHEMAS
schema_names = {s["name"] for s in TOOL_SCHEMAS}
for name in ("media_save_to_memory", "send_followup", "send_recovery"):
    chk(f"{name} NOT in TOOL_SCHEMAS (Agent can't call it directly)", name not in schema_names)


# ══════════════════════════════════════════════════════════════════
# 5. verify_execution — accepts valid evidence, fails closed without it
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: verify_execution evidence gate ────────────────────")

from core.anti_hallucination import verify_execution

ok_result = {"ok": True, "tool": "send_followup", "external_id": "", "evidence": {"audit_id": "a1"}, "user_message": "✅"}
check = verify_execution("send_followup", ok_result)
chk("send_followup: verify_execution ok with audit_id evidence", check.status == "ok")

bad_result = {"ok": True, "tool": "send_followup", "external_id": "", "evidence": {}, "user_message": "✅"}
check = verify_execution("send_followup", bad_result)
chk("send_followup: verify_execution fails closed without evidence", check.status == "failed")

mem_ok = {"ok": True, "tool": "media_save_to_memory", "external_id": "recX", "evidence": {}, "user_message": "✅"}
chk("media_save_to_memory: verify_execution ok with external_id",
    verify_execution("media_save_to_memory", mem_ok).status == "ok")


# ══════════════════════════════════════════════════════════════════
# 6. End-to-end: propose_action -> approve -> dispatch_tool -> verify
# ══════════════════════════════════════════════════════════════════
print("\n── Test 6: end-to-end through ActionGateway ──────────────────")

from core.action_gateway import ActionGateway, ExecutionLedger, _make_dispatch_executor
from identity import Identity, Role

ledger = ExecutionLedger()
gw = ActionGateway(ledger=ledger, tool_executor=_make_dispatch_executor(ledger))

owner_identity = Identity(
    user_id="owner_1", role=Role.OWNER, display_name="Owner",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="tg_owner_1",
)

with patch("core.output_gateway.send_outbound", return_value=_gw_result_ok), \
     patch("lead_memory.lead_memory") as _lm2:
    _lm2.get.return_value = SimpleNamespace(followup_count=0)
    propose = gw.propose_action(
        tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
        tool_name="send_followup",
        tool_inputs={"chat_id": "tg_owner_1", "draft": "hi", "contact_name": "דני", "channel": "whatsapp", "memory_key": ""},
        origin_channel="telegram", origin_chat_id="tg_owner_1",
        requires_approval=True, identity=owner_identity, trusted_source="followup_engine",
    )
    chk("E2E: propose_action ok", propose.ok)

    reply = gw.approve(propose.contract_id, approver="boss_hq:owner_1", approver_role=Role.OWNER)
    chk("E2E: approve returns success text (not an error)", "❌" not in reply and "⛔" not in reply)

contract = ledger.find_by_id(propose.contract_id)
chk("E2E: contract ends in 'executed' status", contract is not None and contract.status == "executed")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PR-0C adapter tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
