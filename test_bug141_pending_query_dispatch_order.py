#!/usr/bin/env python3
"""
test_bug141_pending_query_dispatch_order.py — BUG-141 (AG-01) regression suite.

Live finding: a natural-language pending-queue question ("מה ממתין כרגע
לאישור?") was expected to route deterministically to
ActionGateway.describe_pending_queue(), but fell through to the general
Agent instead, which guessed at airtable_get on Tasks/Deals/Payments (422s
on the latter two) and had its final reply replaced by A32's generic
failure fallback.

Root cause (app.py's run_agent(), inside `if pending_entry is None:`): a
single if/elif/elif/elif chain had `if "?" in _stripped:` as its FIRST
branch, with only past-tense completion-verb patterns
(_STATUS_QUERY_PATTERNS) checked inside it. Since the trailing "?" is
present in "מה ממתין כרגע לאישור?", that branch always claimed the message
first, and the `elif _PENDING_QUERY_RE.search(_stripped):` branch further
down the chain was never reached — regardless of whether the regex would
have matched.

Fix: _PENDING_QUERY_RE is now checked in its own `if` block BEFORE the
general "?" branch, so a trailing "?" no longer matters. The old `elif
_PENDING_QUERY_RE...` branch (now unreachable dead code) was removed. No
regex change. No change to BUG-142/143/144/145/122 or Cost Telemetry code.

This suite drives the real app.run_agent() end-to-end (Identity/Router/
Context/Anthropic mocked, same harness pattern as
test_bug122_pending_queue_ux.py / test_a32_enforcement.py) — the only real
production code under test is the dispatch-order fix in run_agent().

Tests:
  (a) "מה ממתין כרגע לאישור?" (with "?"), one live contract -> routes to
      describe_pending_queue(), Agent/tools never called.
  (b) "מה ממתין כרגע לאישור" (no "?"), one live contract -> same behavior
      as (a) — proves the "?" no longer matters.
  (c) Empty queue, with "?" -> the "no pending" reply, Agent/tools never
      called.
  (d) Three live contracts, with "?" -> reply mentions the count (3),
      Agent/tools never called.
  (e) Scope containment: an unrelated new-task request with an empty queue
      still reaches the Agent as before (the new branch does not hijack
      normal traffic).
"""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug141-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG141_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug141Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug141Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
import session_store  # noqa: E402
from identity import Identity, Role  # noqa: E402

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from context import AgentContext  # noqa: E402
from core.router.route_decision import RouteDecision, Intent  # noqa: E402
from core.action_gateway import ActionContract, ExecutionLedger, ActionGateway  # noqa: E402
import core.action_gateway as action_gateway_module  # noqa: E402
import tools.dispatcher as dispatcher_module  # noqa: E402

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


def _make_contract(contract_id: str, canonical_user_id: str) -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id=canonical_user_id,
        tool_name="airtable_add",
        normalized_payload={"table": "Tasks", "fields": {"Task": "test"}},
        business_action_fingerprint=f"fp-{contract_id}",
        origin_channel="telegram",
        origin_chat_id="chat-141",
        requires_approval=True,
        status="pending",
        created_at=time.time(),
    )


def _run(chat_id: str, user_text: str, *, gateway: ActionGateway, agent_reply_text: str = "המשימה נוספה בהצלחה.") -> str:
    """Drives the real app.run_agent() end-to-end. Only Identity/Router/
    Context/Anthropic/dispatch_tool are mocked — the dispatch-order branch
    under test (app.py, right before the '?' status-query branch) is real
    production code, reading the module-level `core.action_gateway.action_gateway`
    singleton, which we point at a per-test ActionGateway instance."""
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test", allowed_tools=[], memory_key=f"bug141test:{chat_id}",
        max_tokens=500, model="claude-haiku-test", identity_label="owner",
    )
    route = RouteDecision(
        channel="telegram", intent=Intent.CREATE_TASK, domain="general",
        risk="normal", handler="agent", confidence=0.95, matched_rule="test",
    )
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=route), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(action_gateway_module, "action_gateway", gateway), \
         patch.object(app.client.messages, "create",
                       return_value=_fake_anthropic_response(agent_reply_text)) as _anthropic_mock, \
         patch.object(dispatcher_module, "dispatch_tool") as _dispatch_mock, \
         patch.object(session_store.lead_sessions, "get", return_value=None):
        reply = app.run_agent(user_text, chat_id, channel="telegram")
        return reply, _anthropic_mock, _dispatch_mock


def _make_gateway(chat_id: str, n_contracts: int) -> ActionGateway:
    # identity.memory_key == f"{tenant_id}:{user_id}" (identity.py) — Identity(user_id=chat_id)
    # below defaults tenant_id to "boss_hq", which is what describe_pending_queue()'s
    # find_live_contracts(identity.memory_key) actually looks up in app.py.
    canonical_user_id = f"boss_hq:{chat_id}"
    ledger = ExecutionLedger()
    gw = ActionGateway(ledger=ledger)
    for i in range(n_contracts):
        ledger.save(_make_contract(f"c-{chat_id}-{i}", canonical_user_id))
    return gw


# ══════════════════════════════════════════════════
# (a) "?" variant, one live contract
# ══════════════════════════════════════════════════

print("── (a) pending-query WITH trailing '?', one live contract ──")

_chat_a = "bug141_a"
_gw_a = _make_gateway(_chat_a, 1)

reply_a, anthropic_a, dispatch_a = _run(_chat_a, "מה ממתין כרגע לאישור?", gateway=_gw_a)

chk("(a) reply comes from describe_pending_queue() (ActionContracts-scoped text)",
    "ActionContracts" in reply_a and "1 בקשות ממתינות" in reply_a)
chk("(a) Agent (Anthropic) never called", not anthropic_a.called)
chk("(a) no tool dispatch (Tasks/Deals/Payments) ever called", not dispatch_a.called)


# ══════════════════════════════════════════════════
# (b) no "?" variant, one live contract — must behave like (a)
# ══════════════════════════════════════════════════

print("\n── (b) pending-query WITHOUT trailing '?', one live contract ──")

_chat_b = "bug141_b"
_gw_b = _make_gateway(_chat_b, 1)

reply_b, anthropic_b, dispatch_b = _run(_chat_b, "מה ממתין כרגע לאישור", gateway=_gw_b)

chk("(b) reply comes from describe_pending_queue() (ActionContracts-scoped text)",
    "ActionContracts" in reply_b and "1 בקשות ממתינות" in reply_b)
chk("(b) Agent (Anthropic) never called", not anthropic_b.called)
chk("(b) no tool dispatch (Tasks/Deals/Payments) ever called", not dispatch_b.called)
chk("(b) '?' vs no-'?' produce the same lead-in line (structural equivalence)",
    reply_a.split("\n")[0] == reply_b.split("\n")[0])


# ══════════════════════════════════════════════════
# (c) empty queue, "?" variant
# ══════════════════════════════════════════════════

print("\n── (c) pending-query, empty queue ──")

_chat_c = "bug141_c"
_gw_c = _make_gateway(_chat_c, 0)

reply_c, anthropic_c, dispatch_c = _run(_chat_c, "מה ממתין כרגע לאישור?", gateway=_gw_c)

chk("(c) empty-queue reply is the deterministic 'no pending' message",
    "לא מצאתי בקשות ממתינות" in reply_c or "ActionContracts" in reply_c)
chk("(c) Agent (Anthropic) never called", not anthropic_c.called)
chk("(c) no tool dispatch (Tasks/Deals/Payments) ever called", not dispatch_c.called)


# ══════════════════════════════════════════════════
# (d) multiple (3) live contracts, "?" variant
# ══════════════════════════════════════════════════

print("\n── (d) pending-query, 3 live contracts ──")

_chat_d = "bug141_d"
_gw_d = _make_gateway(_chat_d, 3)

reply_d, anthropic_d, dispatch_d = _run(_chat_d, "מה ממתין כרגע לאישור?", gateway=_gw_d)

chk("(d) reply mentions the pending count (3)", "3 בקשות ממתינות" in reply_d)
chk("(d) Agent (Anthropic) never called", not anthropic_d.called)
chk("(d) no tool dispatch (Tasks/Deals/Payments) ever called", not dispatch_d.called)


# ══════════════════════════════════════════════════
# (e) scope containment — unrelated message still reaches the Agent
# ══════════════════════════════════════════════════

print("\n── (e) scope containment: unrelated message still reaches Agent ──")

_chat_e = "bug141_e"
_gw_e = _make_gateway(_chat_e, 0)

# Neutral clarifying-question reply (not an action-status claim) so A32's
# NO-TOOL-EVIDENCE gate doesn't rewrite it — irrelevant to what this test
# is proving (dispatch reaches the Agent at all), and rewriting it here
# would just be exercising a different, unrelated gate.
reply_e, anthropic_e, dispatch_e = _run(
    _chat_e, "צור משימה חדשה: להתקשר ללקוח מחר", gateway=_gw_e,
    agent_reply_text="באיזה תאריך תרצה שאקבע את המשימה הזו?",
)

chk("(e) unrelated new-task request (no pending-query wording) still reaches the Agent",
    anthropic_e.called)
chk("(e) unrelated request gets the Agent's own reply text, not the pending-queue reply",
    reply_e == "באיזה תאריך תרצה שאקבע את המשימה הזו?")


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
