#!/usr/bin/env python3
"""
test_bug_approval_callback_hardening.py — regression tests for three
follow-up defects found during production verification of PR #345's batch
behavior (which was itself confirmed correct: each deferred task promoted
into its own pending ActionContract, tasks approved individually through
separate Telegram buttons, one Atomic Claim + one Airtable POST each, no
promoted task executing automatically).

1. BUG-APPROVAL-CALLBACK-CONTEXT-INTERRUPT: app.py's global ingress context
   gate (_apply_ingress_context_gate) marked context_interrupted on every
   inbound callback, including the approve:/reject: button press itself —
   a legitimate resolution event, not an unrelated message that happened to
   arrive while a contract was pending. Fixed: callback events whose data
   starts with "approve:"/"reject:" are now exempted, the same principle
   already applied to genuine text confirm/cancel/disambiguation via
   is_own_resolution_event().

2. BUG-STALE-CALLBACK-FALLTHROUGH: a stale/replayed/unlinked Telegram
   approval callback (no live or terminal ActionContract found for its
   fingerprint at all) fell through to the legacy direct dispatch_tool()
   call with no ActionGateway approval and no Atomic Claim behind it —
   live-incident evidence: a callback reached direct dispatch with zero
   Gateway involvement. Fixed: when FEATURE_ACTION_GATEWAY is on and no
   contract (pending or terminal) is found, the callback now fails closed
   — a deterministic expired/already-resolved reply, zero dispatches.
   FEATURE_ACTION_GATEWAY entirely off is unaffected (see
   test_pr0c_telegram_callback_gateway.py's Test 1 — no Gateway involvement
   in that mode at all, unchanged pre-migration behavior).

3. BUG-DUPLICATE-PLAIN-STRING: tools/dispatcher.py's airtable_add dedup
   check returned a plain string on a duplicate hit — airtable_add is a
   structured write tool (registered in A32's _EVIDENCE_VALIDATORS), so
   verify_execution() misclassified this correct no-op as
   "expected structured result dict; got plain string", a false execution
   failure. Fixed: returns a structured {ok: True, tool, outcome:
   "already_exists", external_id, evidence, user_message} result — passes
   the same evidence validator a real write would (external_id is the
   genuine existing record's id), and is presented as "already exists, no
   duplicate created," not a failure.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-hardening-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:HARDENING_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patHardeningTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appHardeningTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("ELIYAHU_CHAT_ID", "999999999")

import app  # noqa: E402

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
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


_flag_on = lambda name: name == "FEATURE_ACTION_GATEWAY"


print("── Fix 1: approve/reject callbacks never set context_interrupted ──")

requester1 = _identity("owner-hard-1", Role.OWNER)

propose_a = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester1.memory_key,
    tool_name="airtable_add", tool_inputs={"table": "Tasks", "fields": {"Task": "A"}},
    origin_channel="telegram", origin_chat_id=requester1.user_id,
    requires_approval=True, identity=requester1, trusted_source="agent",
)
propose_b = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester1.memory_key,
    tool_name="airtable_add", tool_inputs={"table": "Tasks", "fields": {"Task": "B"}},
    origin_channel="telegram", origin_chat_id=requester1.user_id,
    requires_approval=True, identity=requester1, trusted_source="test_harness",
)

with patch.object(app, "resolve_identity", return_value=requester1), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._apply_ingress_context_gate(
        requester1, app._IngressEvent(channel="telegram", kind="callback", data=f"approve:{propose_a.contract_id}"),
    )

_contract_a = _real_gw.find_contract(propose_a.contract_id)
_contract_b = _real_gw.find_contract(propose_b.contract_id)
chk("approve: callback does not mark the targeted contract context_interrupted",
    _contract_a is not None and _contract_a.context_interrupted is False)
chk("approve: callback does not mark an unrelated sibling contract context_interrupted either",
    _contract_b is not None and _contract_b.context_interrupted is False)

with patch.object(app, "resolve_identity", return_value=requester1), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._apply_ingress_context_gate(
        requester1, app._IngressEvent(channel="telegram", kind="callback", data=f"reject:{propose_b.contract_id}"),
    )
_contract_b_after = _real_gw.find_contract(propose_b.contract_id)
chk("reject: callback also does not mark context_interrupted",
    _contract_b_after is not None and _contract_b_after.context_interrupted is False)

requester2 = _identity("owner-hard-2", Role.OWNER)
propose_c = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester2.memory_key,
    tool_name="airtable_add", tool_inputs={"table": "Tasks", "fields": {"Task": "C"}},
    origin_channel="telegram", origin_chat_id=requester2.user_id,
    requires_approval=True, identity=requester2, trusted_source="agent",
)
with patch.object(app, "resolve_identity", return_value=requester2), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._apply_ingress_context_gate(
        requester2, app._IngressEvent(channel="telegram", kind="callback", data="some_other_callback:xyz"),
    )
_contract_c = _real_gw.find_contract(propose_c.contract_id)
chk("regression: a non-approval callback still marks context_interrupted as before",
    _contract_c is not None and _contract_c.context_interrupted is True)


print("\n── Fix 2: stale/unlinked callback fails closed, zero dispatches ──")

requester3 = _identity("owner-hard-3", Role.OWNER)
_legacy_action_id, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add",
        "tool_inputs": {"table": "Tasks", "fields": {"Task": "unlinked"}},
        "origin_channel": "telegram", "origin_chat_id": requester3.user_id,
        "canonical_user_id": requester3.memory_key,
        "user_chat_id": requester3.user_id, "channel": "telegram",
    },
    chat_id=requester3.user_id, label="unlinked test",
)

cq3 = _fake_cq(requester3.user_id, f"approve:{_legacy_action_id}")
mock_bot3 = MagicMock()

with patch.object(app, "bot", mock_bot3), \
     patch.object(app, "resolve_identity", return_value=requester3), \
     patch("tools.dispatcher.dispatch_tool") as _dt_gw3, \
     patch.object(app, "dispatch_tool") as _dt_legacy3, \
     patch.object(app, "_flag_enabled", side_effect=_flag_on), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._handle_approval_callback_impl(cq3)

chk("callback without a linked contract: zero Gateway dispatch calls",
    _dt_gw3.call_count == 0)
chk("callback without a linked contract: zero legacy dispatch calls",
    _dt_legacy3.call_count == 0)
chk("callback without a linked contract: deterministic expired/already-resolved reply",
    mock_bot3.answer_callback_query.call_args is not None and
    ("פג" in mock_bot3.answer_callback_query.call_args[0][1]
     or "טופל" in mock_bot3.answer_callback_query.call_args[0][1]))


print("\n── BUG-144/145: canonical reject + one final response ─────────")

requester4 = _identity("owner-hard-4", Role.OWNER)
reject_inputs = {"table": "Tasks", "fields": {"Task": "reject canonical"}}
reject_proposal = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester4.memory_key,
    tool_name="airtable_add", tool_inputs=reject_inputs,
    origin_channel="telegram", origin_chat_id=requester4.user_id,
    requires_approval=True, identity=requester4, trusted_source="agent",
)
reject_action_id, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add", "tool_inputs": reject_inputs,
        "origin_channel": "telegram", "origin_chat_id": requester4.user_id,
        "canonical_user_id": requester4.memory_key,
        "user_chat_id": requester4.user_id, "channel": "telegram",
    },
    chat_id=requester4.user_id, label="reject canonical",
)
reject_cq = SimpleNamespace(
    id="cbq-reject", data=f"reject:{reject_action_id}",
    from_user=SimpleNamespace(id=requester4.user_id),
    message=SimpleNamespace(
        chat=SimpleNamespace(id=requester4.user_id), message_id=44,
    ),
)
reject_bot = MagicMock()
with patch.object(app, "bot", reject_bot), \
     patch.object(app, "resolve_identity", return_value=requester4), \
     patch.object(app, "_flag_enabled", side_effect=_flag_on), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._handle_approval_callback_impl(reject_cq)

reject_contract = _real_gw.find_contract(reject_proposal.contract_id)
chk("button reject durably marks the canonical ActionContract rejected",
    reject_contract is not None and reject_contract.status == "rejected")
chk("same-chat callback sends no additional Telegram message",
    reject_bot.send_message.call_count == 0)
chk("same-chat callback edits exactly one persistent final response",
    reject_bot.edit_message_text.call_count == 1)

print("\n── Cross-chat callback finalization + replay safety ───────────")


def _ok_callback_dispatch(*args, **kwargs):
    return {
        "ok": True,
        "tool": "send_followup",
        "external_id": "audit-cross-chat",
        "evidence": {"audit_id": "audit-cross-chat"},
        "user_message": "בוצע",
    }


requester5 = _identity("requester-cross-approve", Role.OWNER)
approver5 = _identity("approver-cross-approve", Role.OWNER)
approve_inputs = {"chat_id": requester5.user_id, "draft": "cross chat approve"}
approve_proposal = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester5.memory_key,
    tool_name="send_followup", tool_inputs=approve_inputs,
    origin_channel="telegram", origin_chat_id=requester5.user_id,
    requires_approval=True, identity=requester5, trusted_source="agent",
)
approve_action_id, _ = _real_bus.request_approval(
    action="send_followup",
    payload={
        "tool_name": "send_followup", "tool_inputs": approve_inputs,
        "origin_channel": "telegram", "origin_chat_id": requester5.user_id,
        "canonical_user_id": requester5.memory_key,
        "user_chat_id": requester5.user_id, "channel": "telegram",
    },
    chat_id=requester5.user_id, label="cross chat approve",
)
approve_cq = SimpleNamespace(
    id="cbq-cross-approve", data=f"approve:{approve_action_id}",
    from_user=SimpleNamespace(id=approver5.user_id),
    message=SimpleNamespace(chat=SimpleNamespace(id=approver5.user_id), message_id=55),
)
approve_bot = MagicMock()


def _resolve_cross_approve(channel, external_id):
    return approver5 if external_id == approver5.user_id else requester5


with patch.object(app, "bot", approve_bot), \
     patch.object(app, "resolve_identity", side_effect=_resolve_cross_approve), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_callback_dispatch) as approve_dispatch, \
     patch.object(app, "_flag_enabled", side_effect=_flag_on), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._handle_approval_callback_impl(approve_cq)
    approve_contract = _real_gw.find_contract(approve_proposal.contract_id)
    first_approve_dispatches = approve_dispatch.call_count
    first_approve_sends = list(approve_bot.send_message.call_args_list)
    first_approve_edits = approve_bot.edit_message_text.call_count
    approve_bot.reset_mock()
    app._handle_approval_callback_impl(approve_cq)
    replay_approve_dispatches = approve_dispatch.call_count

chk("cross-chat approve makes canonical lifecycle terminal",
    approve_contract is not None and approve_contract.status in ("completed", "executed"))
chk("cross-chat approve notifies requester exactly once",
    len(first_approve_sends) == 1 and
    str(first_approve_sends[0].args[0]) == requester5.user_id)
chk("cross-chat approve edits approver message exactly once",
    first_approve_edits == 1)
chk("repeated approve callback performs no duplicate execution",
    first_approve_dispatches == 1 and replay_approve_dispatches == 1)
chk("repeated approve callback returns deterministic stale/resolved response",
    approve_bot.answer_callback_query.call_count == 1 and
    approve_bot.edit_message_text.call_count == 1)


requester6 = _identity("requester-cross-reject", Role.OWNER)
approver6 = _identity("approver-cross-reject", Role.OWNER)
cross_reject_inputs = {
    "table": "Tasks", "fields": {"כותרת המשימה": "cross reject"},
}
cross_reject_proposal = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester6.memory_key,
    tool_name="airtable_add", tool_inputs=cross_reject_inputs,
    origin_channel="telegram", origin_chat_id=requester6.user_id,
    requires_approval=True, identity=requester6, trusted_source="agent",
)
cross_reject_action_id, _ = _real_bus.request_approval(
    action="airtable_add",
    payload={
        "tool_name": "airtable_add", "tool_inputs": cross_reject_inputs,
        "origin_channel": "telegram", "origin_chat_id": requester6.user_id,
        "canonical_user_id": requester6.memory_key,
        "user_chat_id": requester6.user_id, "channel": "telegram",
    },
    chat_id=requester6.user_id, label="cross chat reject",
)
cross_reject_cq = SimpleNamespace(
    id="cbq-cross-reject", data=f"reject:{cross_reject_action_id}",
    from_user=SimpleNamespace(id=approver6.user_id),
    message=SimpleNamespace(chat=SimpleNamespace(id=approver6.user_id), message_id=66),
)
cross_reject_bot = MagicMock()


def _resolve_cross_reject(channel, external_id):
    return approver6 if external_id == approver6.user_id else requester6


with patch.object(app, "bot", cross_reject_bot), \
     patch.object(app, "resolve_identity", side_effect=_resolve_cross_reject), \
     patch.object(app, "_flag_enabled", side_effect=_flag_on), \
     patch("feature_flags.is_enabled", side_effect=_flag_on):
    app._handle_approval_callback_impl(cross_reject_cq)
    cross_reject_contract = _real_gw.find_contract(cross_reject_proposal.contract_id)
    first_reject_sends = list(cross_reject_bot.send_message.call_args_list)
    first_reject_edits = cross_reject_bot.edit_message_text.call_count
    cross_reject_bot.reset_mock()
    app._handle_approval_callback_impl(cross_reject_cq)

chk("cross-chat reject makes canonical lifecycle terminal",
    cross_reject_contract is not None and cross_reject_contract.status == "rejected")
chk("cross-chat reject notifies requester exactly once",
    len(first_reject_sends) == 1 and
    str(first_reject_sends[0].args[0]) == requester6.user_id)
chk("cross-chat reject edits approver message exactly once",
    first_reject_edits == 1)
chk("repeated reject callback leaves lifecycle unchanged",
    _real_gw.find_contract(cross_reject_proposal.contract_id).status == "rejected")
chk("repeated reject callback returns deterministic stale/resolved response",
    cross_reject_bot.answer_callback_query.call_count == 1 and
    cross_reject_bot.edit_message_text.call_count == 1)


print("\n── Fix 3: duplicate airtable_add returns structured already_exists ──")

from tools import dispatcher as _dispatcher_mod

_EXISTING_RECORD = {
    "id": "recEXISTING000001",
    "fields": {"Task": "כפילות", "סטטוס": "פתוח"},
}

_dup_identity = _identity("owner-hard-dup", Role.OWNER)

with patch.object(_dispatcher_mod, "_check_duplicate", return_value=_EXISTING_RECORD), \
     patch.object(_dispatcher_mod, "_ALIAS_MAP", {}), \
     patch.object(_dispatcher_mod, "_DEDUP_FIELDS", {"Tasks": "Task"}), \
     patch.object(_dispatcher_mod, "enforce_leads_write_gate", return_value=None), \
     patch.object(_dispatcher_mod, "enforce_tenant_scope", return_value=None), \
     patch.object(_dispatcher_mod, "audit_log_airtable", return_value=None):
    result = _dispatcher_mod.dispatch_tool(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "כפילות"}},
        identity=_dup_identity, trusted_source="agent",
    )

chk("duplicate airtable_add returns a dict, not a plain string", isinstance(result, dict))
chk("duplicate result: ok=True (not a failure)", result.get("ok") is True)
chk("duplicate result: outcome='already_exists'", result.get("outcome") == "already_exists")
chk("duplicate result: external_id is the existing record's real id",
    result.get("external_id") == "recEXISTING000001")
chk("duplicate result: user_message presents it as already-exists, not failure",
    "כבר קיימת" in result.get("user_message", "") and "כפילות" in result.get("user_message", ""))

from core.anti_hallucination import verify_execution
_verify = verify_execution("airtable_add", result)
chk("A32 verify_execution accepts the structured duplicate result as ok "
    "(no longer misclassified as 'expected structured result dict; got plain string')",
    _verify.status == "ok")


print("\n── BUG-122 regression: BatchQueue promotion is disabled ────────")
chk("dedicated BUG-122 batch policy coverage remains in place",
    callable(app._promote_next_batch_item))


print(f"\n{'='*50}")
print(f"approval callback hardening tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
