#!/usr/bin/env python3
"""
test_bug122_pending_queue_ux.py — BUG-122 regression suite.

Live incident: Router confidently recognized a contract-requiring intent
(create_task, confidence=0.95) while 5 live (status="pending") ActionContracts
already existed for the identity. The agent turn made zero tool calls and
queued no new approval, but sanitize_agent_response()'s Single-Speaker gate
replaced its free text with the generic _SINGLE_SPEAKER_FALLBACK ("לא הצלחתי
לבצע את הפעולה") — misleading, since nothing was actually attempted, and it
gives the user no path forward.

Fix (app.py, right after sanitize_agent_response()): when that exact
combination occurs — _SINGLE_SPEAKER_FALLBACK + zero tool calls + no approval
queued this turn + the router's intent is contract-required
(core.router.risk_router.intent_requires_contract_for_success(), PA-01's own
single policy source, reused not duplicated) + at least one live contract —
the reply is replaced with an explicit queue-resolution message instead.
Logs pending_gate_decision=ask_queue_resolution/bypass_new_action.

Scope: Pending Approval Gate / TurnEnvelope routing only. No RP5/F52
enforcement change, no approval execution bypass, no production flag
activation.

Tests:
  (a) A confirm word ("מאשר") with one live pending contract is still
      intercepted and resolved by the pre-existing ActionGateway confirmation
      routing — unchanged by this fix (regression lock).
  (b) A confidently-recognized new create_task request with 5 live pending
      contracts and zero tool calls gets the explicit queue-resolution
      message, not the generic "I failed" fallback.
  (c) Non-pending contracts (approved/rejected) are excluded from the live
      count — ExecutionLedger.find_live_by_user()'s existing status filter,
      exercised directly.
  (d) The override never fires when there are no live contracts at all — the
      pre-existing Single-Speaker fallback behavior is untouched in that
      case (scope-containment regression).
"""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug121-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG121_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug121Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug121Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
import feature_flags  # noqa: E402
import session_store  # noqa: E402
from identity import Identity, Role  # noqa: E402
from context import AgentContext  # noqa: E402
from core.router.route_decision import RouteDecision, Intent  # noqa: E402
from core.anti_hallucination import _SINGLE_SPEAKER_FALLBACK  # noqa: E402
from core.action_gateway import ActionContract, ExecutionLedger, ActionGateway  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _fake_anthropic_response(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


_real_is_enabled = feature_flags.is_enabled


def _flag_side_effect(name: str) -> bool:
    # BUG-122's override only matters when the Single-Speaker gate is even
    # active (_gateway_active=_flag_enabled("FEATURE_ACTION_GATEWAY")) — force
    # it on for this test only, delegate every other flag to the real reader
    # so nothing else in run_agent()'s many other _flag_enabled() call sites
    # is silently changed by this test.
    if name == "FEATURE_ACTION_GATEWAY":
        return True
    return _real_is_enabled(name)


def _make_contract(contract_id: str, canonical_user_id: str, status: str = "pending") -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id=canonical_user_id,
        tool_name="airtable_add",
        normalized_payload={"table": "Tasks", "fields": {"Task": "test"}},
        business_action_fingerprint=f"fp-{contract_id}",
        origin_channel="telegram",
        origin_chat_id="chat-121",
        requires_approval=True,
        status=status,
        created_at=time.time(),
    )


def _run_agent_with_intent(
    chat_id: str, user_text: str, *, intent: str, agent_reply_text: str,
    live_contracts_snapshot,
) -> str:
    """Drives the real app.run_agent() end-to-end (Identity/Router/Context/
    Anthropic mocked, same pattern as test_a32_enforcement.py and
    test_pending_contract_read_amplification.py) — the only real production
    code under test is the BUG-122 override right after
    sanitize_agent_response()."""
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test", allowed_tools=[], memory_key=f"bug121test:{chat_id}",
        max_tokens=500, model="claude-haiku-test", identity_label="owner",
    )
    route = RouteDecision(
        channel="telegram", intent=intent, domain="general",
        risk="normal", handler="agent", confidence=0.95, matched_rule="test",
    )
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=route), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app, "_flag_enabled", side_effect=_flag_side_effect), \
         patch.object(app.client.messages, "create",
                       return_value=_fake_anthropic_response(agent_reply_text)), \
         patch.object(session_store.lead_sessions, "get", return_value=None):
        return app.run_agent(
            user_text, chat_id, channel="telegram",
            _live_contracts_snapshot=live_contracts_snapshot,
        )


# ══════════════════════════════════════════════════
# (a) Confirm word with one live contract — pre-existing interception,
#     regression-locked (unrelated to and unmodified by this fix).
# ══════════════════════════════════════════════════

print("── (a) confirm word intercepted by pending gate ────────")

# A confirm word must be routed straight to ActionGateway.approve() for the
# single live contract — proven here by observing the *executor-missing*
# fail-closed message (ActionGateway(ledger=...) with no tool_executor),
# which is only reachable once approve() has found the contract, checked
# approver authority, and passed both — i.e. the pending gate genuinely
# intercepted and resolved it, rather than falling through to a generic
# new-action/queue-resolution message.
_ledger_a = ExecutionLedger()
_gw_a = ActionGateway(ledger=_ledger_a)
_user_a = "boss_hq:bug121_a"
_contract_a = _make_contract("c-a1", _user_a, status="pending")
_ledger_a.save(_contract_a)

with patch.object(session_store.lead_sessions, "get_last_prompted_contract", return_value=None):
    _reply_a = _gw_a.route_confirmation_word(_user_a, approver_role="owner")

chk(
    "confirm word with exactly one live contract reaches approve() "
    "(executor-missing fail-closed reply, not a permission denial)",
    "Gateway executor" in _reply_a,
)
chk("confirm word reply is not the generic queue-resolution message",
    "בקשות הממתינות לאישור" not in _reply_a)
# approve() fails closed BEFORE any status mutation when no executor is
# wired (see core/action_gateway.py's own "§§3/#6 fail-closed" comment) —
# the contract correctly stays "pending", not silently marked approved
# without ever having actually run.
chk("contract stays 'pending' when executor is missing (no phantom approval)",
    _ledger_a.find_by_id("c-a1").status == "pending")


# ══════════════════════════════════════════════════
# (b) New create_task intent, 5 live contracts, zero tool calls -> explicit
#     queue-resolution message, not the generic "I failed" fallback.
# ══════════════════════════════════════════════════

print("\n── (b) new-action intent bypasses queue suppression ────")

_live_5 = [_make_contract(f"c-b{i}", "boss_hq:bug121_b") for i in range(5)]

reply_b = _run_agent_with_intent(
    "bug121_b", "צור משימה חדשה: להתקשר ללקוח מחר",
    intent=Intent.CREATE_TASK,
    agent_reply_text="המשימה נוספה בהצלחה.",
    live_contracts_snapshot=_live_5,
)

chk(
    "confidently-recognized create_task + 5 live contracts + 0 tool calls "
    "-> NOT the generic single-speaker fallback",
    reply_b != _SINGLE_SPEAKER_FALLBACK,
)
chk("reply mentions the pending-requests count (5)", "5" in reply_b)
chk('reply gives an explicit path forward ("מאשר"/"בטל")', "מאשר" in reply_b and "בטל" in reply_b)


# ══════════════════════════════════════════════════
# (c) Non-pending contracts excluded from the live count.
# ══════════════════════════════════════════════════

print("\n── (c) find_live_by_user excludes non-pending status ───")

_ledger_c = ExecutionLedger()
_user_c = "boss_hq:bug121_c"
_ledger_c.save(_make_contract("c-c1", _user_c, status="pending"))
_ledger_c.save(_make_contract("c-c2", _user_c, status="approved"))
_ledger_c.save(_make_contract("c-c3", _user_c, status="rejected"))
_ledger_c.save(_make_contract("c-c4", _user_c, status="completed"))

_live_c = _ledger_c.find_live_by_user(_user_c)
chk("find_live_by_user: only the single 'pending' contract counts as live",
    len(_live_c) == 1 and _live_c[0].contract_id == "c-c1")


# ══════════════════════════════════════════════════
# (d) No live contracts at all -> override must never fire (pre-existing
#     Single-Speaker fallback behavior is untouched — scope containment).
# ══════════════════════════════════════════════════

print("\n── (d) no override without live contracts (scope containment) ──")

reply_d = _run_agent_with_intent(
    "bug121_d", "צור משימה חדשה: להתקשר ללקוח מחר",
    intent=Intent.CREATE_TASK,
    agent_reply_text="המשימה נוספה בהצלחה.",
    live_contracts_snapshot=[],
)

chk(
    "confidently-recognized create_task + 0 live contracts + 0 tool calls "
    "-> unchanged pre-existing single-speaker fallback (override does not "
    "overreach beyond its intended scope)",
    reply_d == _SINGLE_SPEAKER_FALLBACK,
)


# ══════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
