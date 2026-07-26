#!/usr/bin/env python3
"""
test_bug149_action_resolution_projection.py — BUG-149 regression coverage
for the ActionResolutionEvent schema, its projection into memory_store's
distinct context-event channel, idempotent dedup, and the proven identity/
memory routing chain.

Deterministic, no model calls, no mocked LLM replies — see
test_bug149_multi_mutation_guard.py for the tool-loop guard's own coverage.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug149-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG149_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug149Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug149Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.action_gateway import ActionGateway, ExecutionLedger  # noqa: E402
from core.action_resolution_event import ActionResolutionEvent, ActionResolutionOutcome  # noqa: E402
from core.action_resolution_projection import project_resolution_event_to_memory  # noqa: E402
from core.dispatcher_outcome import DispatcherOutcome  # noqa: E402
from identity import Identity, Role  # noqa: E402
from memory_store import memory  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def make_identity(uid: str) -> Identity:
    return Identity(
        user_id=uid, role=Role.OWNER, display_name=uid,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=uid,
    )


def make_gateway(sink=None, executor=None) -> ActionGateway:
    return ActionGateway(ledger=ExecutionLedger(), tool_executor=executor, resolution_sink=sink)


def propose(gw: ActionGateway, identity: Identity, title: str):
    result = gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=identity.memory_key, tool_name="airtable_add",
        tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": title}},
        origin_channel="telegram", origin_chat_id=identity.user_id,
        requires_approval=True, identity=identity, trusted_source="agent",
        user_text=f"צור משימה {title}",
    )
    assert result.ok, f"propose_action failed unexpectedly: {result.reason}"
    return result.contract_id


# ══════════════════════════════════════════════════════════════════
print("\n── 7a/7e: reject/completed/failed/outcome_unknown are projected, terminal+rule marked ──")

_captured = []
gw1 = make_gateway(
    sink=lambda e: _captured.append(e),
    executor=lambda tool_name, tool_inputs, contract_id, identity=None, claim_execution_id=None: {
        "ok": True, "tool": tool_name, "external_id": "recXXXXXXXXXXXXXX", "user_message": "✅ נוצר",
    },
)
identity1 = make_identity("bug149-a-owner")
memory.clear(identity1.memory_key)

# reject
cid_reject = propose(gw1, identity1, "PM460-RETEST-REJECT")
reject_reply = gw1.reject(cid_reject, rejected_by=identity1.memory_key)
chk("reject() still returns its normal reply", reject_reply == "🚫 הפעולה בוטלה.")
rejected_events = [e for e in _captured if e.outcome == ActionResolutionOutcome.REJECTED]
chk("exactly one REJECTED event captured", len(rejected_events) == 1)
chk("REJECTED event is marked terminal", rejected_events and rejected_events[0].terminal is True)
chk("REJECTED event carries the no-retry rule text",
    rejected_events and "אל תציע או תבצע פעולה זו שוב" in rejected_events[0].no_retry_instruction)

# completed (approve + fake executor returning success)
cid_approve = propose(gw1, identity1, "PM460-RETEST-APPROVE")
gw1.approve(cid_approve, approver=identity1.memory_key, approver_role="owner")
completed_events = [e for e in _captured if e.outcome == ActionResolutionOutcome.COMPLETED]
chk("exactly one COMPLETED event captured", len(completed_events) == 1)
chk("COMPLETED event is marked terminal", completed_events and completed_events[0].terminal is True)

# failed (approve + fake executor returning a blocked/failed structured result)
gw2 = make_gateway(
    sink=lambda e: _captured.append(e),
    executor=lambda tool_name, tool_inputs, contract_id, identity=None, claim_execution_id=None: {
        "ok": False, "tool": tool_name, "user_message": "❌ נכשל",
    },
)
identity2 = make_identity("bug149-b-owner")
memory.clear(identity2.memory_key)
cid_failed = propose(gw2, identity2, "PM460-RETEST-FAILED")
gw2.approve(cid_failed, approver=identity2.memory_key, approver_role="owner")
failed_events = [e for e in _captured if e.outcome == ActionResolutionOutcome.FAILED
                 and e.routing_key == identity2.memory_key]
chk("exactly one FAILED event captured", len(failed_events) == 1)

# outcome_unknown (approve + fake executor returning a DispatcherOutcome)
gw3 = make_gateway(
    sink=lambda e: _captured.append(e),
    executor=lambda tool_name, tool_inputs, contract_id, identity=None, claim_execution_id=None:
        DispatcherOutcome(result="outcome_unknown", user_message="⚠️ לא ידוע", error="timeout"),
)
identity3 = make_identity("bug149-c-owner")
memory.clear(identity3.memory_key)
cid_unknown = propose(gw3, identity3, "PM460-RETEST-UNKNOWN")
gw3.approve(cid_unknown, approver=identity3.memory_key, approver_role="owner")
unknown_events = [e for e in _captured if e.outcome == ActionResolutionOutcome.OUTCOME_UNKNOWN
                  and e.routing_key == identity3.memory_key]
chk("exactly one OUTCOME_UNKNOWN event captured", len(unknown_events) == 1)

chk("approve() never emits for the non-terminal 'approved' state",
    not any(getattr(e, "outcome", None) == "approved" for e in _captured))

# Real projection into memory — confirm the rendered block carries the tags
project_resolution_event_to_memory(rejected_events[0])
_rendered = memory.get_context_events_for_claude(identity1.memory_key)
chk("rendered context event contains outcome tag", any("outcome=rejected" in b for b in _rendered))
chk("rendered context event contains terminal=true", any("terminal=true" in b for b in _rendered))
chk("rendered context event contains the action summary",
    any(rejected_events[0].action_summary in b for b in _rendered))
chk("rendered context event is NOT stored as ordinary conversation history",
    all("PM460-RETEST-REJECT" not in str(m) for m in memory.get_for_claude(identity1.memory_key)))


# ══════════════════════════════════════════════════════════════════
print("\n── 7b: approve()/reject() return values + durable state unchanged when the sink raises ──")

def _raising_sink(event):
    raise RuntimeError("boom — simulated projection failure")

gw_raise = make_gateway(
    sink=_raising_sink,
    executor=lambda tool_name, tool_inputs, contract_id, identity=None, claim_execution_id=None: {
        "ok": True, "tool": tool_name, "external_id": "recXXXXXXXXXXXXXX", "user_message": "✅ נוצר",
    },
)
gw_baseline = make_gateway(
    sink=None,
    executor=lambda tool_name, tool_inputs, contract_id, identity=None, claim_execution_id=None: {
        "ok": True, "tool": tool_name, "external_id": "recXXXXXXXXXXXXXX", "user_message": "✅ נוצר",
    },
)
identity4 = make_identity("bug149-raise-owner")
identity5 = make_identity("bug149-baseline-owner")
memory.clear(identity4.memory_key)
memory.clear(identity5.memory_key)

cid_r = propose(gw_raise, identity4, "same task")
cid_b = propose(gw_baseline, identity5, "same task")
result_raise = gw_raise.approve(cid_r, approver=identity4.memory_key, approver_role="owner")
result_baseline = gw_baseline.approve(cid_b, approver=identity5.memory_key, approver_role="owner")
chk("approve() return value identical whether the sink raises or is absent",
    result_raise == result_baseline)
_status_raise = gw_raise._ledger.find_by_id(cid_r).status
_status_baseline = gw_baseline._ledger.find_by_id(cid_b).status
chk("durable status identical regardless of sink failure, and genuinely terminal-success",
    _status_raise == _status_baseline and _status_raise in ("completed", "executed"))

cid_r2 = propose(gw_raise, identity4, "second task")
cid_b2 = propose(gw_baseline, identity5, "second task")
reject_raise = gw_raise.reject(cid_r2, rejected_by=identity4.memory_key)
reject_baseline = gw_baseline.reject(cid_b2, rejected_by=identity5.memory_key)
chk("reject() return value identical whether the sink raises or is absent",
    reject_raise == reject_baseline)


# ══════════════════════════════════════════════════════════════════
print("\n── 6.2: repeated resolution-event projection is deduplicated ──")

identity6 = make_identity("bug149-dedupe-owner")
memory.clear(identity6.memory_key)
event = ActionResolutionEvent(
    contract_id="fake-contract-id", routing_key=identity6.memory_key, tenant_id="boss_hq",
    tool_name="airtable_add", outcome=ActionResolutionOutcome.REJECTED, terminal=True,
    action_summary="בדיקת דדופ", contract_version=1,
)
first_write = memory.add_context_event(event.routing_key, event.dedupe_key, "block-A")
second_write = memory.add_context_event(event.routing_key, event.dedupe_key, "block-A")
third_write_different_key = memory.add_context_event(event.routing_key, event.dedupe_key + ":v2", "block-B")
chk("first projection of a given dedupe_key is recorded", first_write is True)
chk("repeated projection of the SAME dedupe_key is a no-op", second_write is False)
chk("a genuinely different dedupe_key still records normally", third_write_different_key is True)
chk("exactly one 'block-A' entry despite two write attempts",
    sum(1 for b in memory.get_context_events_for_claude(identity6.memory_key) if b == "block-A") == 1)

# Same scenario via the real ActionGateway path — a contract that somehow
# gets its terminal outcome re-emitted twice (e.g. a retried callback
# calling reject() on an already-rejected... no, reject() guards
# status!="pending", so simulate via two direct _emit_resolution() calls,
# which is the realistic shape a retried persistence attempt could take).
_captured2 = []
gw_dup = make_gateway(sink=lambda e: _captured2.append(e) or project_resolution_event_to_memory(e))
identity7 = make_identity("bug149-dedupe-real-owner")
memory.clear(identity7.memory_key)
cid_dup = propose(gw_dup, identity7, "PM460-DEDUPE-REAL")
gw_dup.reject(cid_dup, rejected_by=identity7.memory_key)
gw_dup._emit_resolution(cid_dup, ActionResolutionOutcome.REJECTED)  # simulated retry
chk("two emissions for the same terminal transition still project only once",
    len(memory.get_context_events_for_claude(identity7.memory_key)) == 1)


# ══════════════════════════════════════════════════════════════════
print("\n── 7f: identity routing — event written and read via the SAME derivation as run_agent() ──")

identity8 = make_identity("bug149-routing-owner")
memory.clear(identity8.memory_key)
gw8 = make_gateway(sink=lambda e: project_resolution_event_to_memory(e))
cid8 = propose(gw8, identity8, "PM460-ROUTING-PROOF")
gw8.reject(cid8, rejected_by=identity8.memory_key)

# Independently re-derive the key the exact way context.py:289 does
# (ctx.memory_key = identity.memory_key), NOT by reusing anything the
# event/gateway computed — this is the test that would fail if routing
# ever silently drifted from identity.memory_key.
_independently_derived_key = identity8.memory_key
chk("event routed to identity.memory_key is readable via that same independently-derived key",
    len(memory.get_context_events_for_claude(_independently_derived_key)) == 1)
chk("contract.canonical_user_id used for routing equals identity.memory_key (not re-derived)",
    gw8._ledger.find_by_id(cid8).canonical_user_id == identity8.memory_key)


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"BUG-149 projection/dedupe/routing regression: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
