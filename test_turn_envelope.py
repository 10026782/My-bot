#!/usr/bin/env python3
"""
test_turn_envelope.py — TurnCoordinator Phase 0 (core/turn_envelope.py +
app._build_and_log_turn_envelope). Phase 0 is observation-only: these tests
verify the snapshot/log builder is correct and, critically, that it can never
break run_agent() — a raising lookup must be swallowed, not propagated.

See docs/architecture/turn-coordinator/TURN_COORDINATOR_PROPOSAL_V2.md and
docs/architecture/f52-unified-approval-runtime/audits/phase-4c/
TURN_OWNERSHIP_EXTENSION.md for the design this is Phase 0 of.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-turnenv-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TURNENV_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patTurnEnvTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTurnEnvTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("ELIYAHU_CHAT_ID", "999999999")

from core.turn_envelope import (  # noqa: E402
    AgentAvailability,
    ExecutionKind,
    PendingItem,
    PendingQueueAwareness,
    build_ownership_signal,
    build_turn_envelope,
    detect_case_c2_signal,
    execution_kind_of,
    log_case_c_signal,
    log_ownership_signal,
    log_turn_envelope,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# build_turn_envelope() — pure function, no I/O
# ══════════════════════════════════════════════════

env_free = build_turn_envelope()
chk("no queues -> free_agent mode", env_free.turn_mode == "free_agent")
chk("no queues -> empty pending_queues", env_free.pending_queues == ())
chk("no queues -> active_queue_id is None", env_free.active_queue_id is None)
chk("no queues -> reply_owner is 'agent'", env_free.reply_owner == "agent")
chk("Phase 0 never sets resolved_reference", env_free.resolved_reference is None)
chk("Phase 0 never sets message_kind", env_free.message_kind is None)
chk("agent_availability defaults to PRIMARY in Phase 0",
    env_free.agent_availability.mode == AgentAvailability.PRIMARY)

_ac_queue = PendingQueueAwareness(
    queue_id="ac:u1", source="action_gateway", kind="action_contract",
    summary="1 live contract(s)",
    items=(PendingItem(index=1, id="c1", kind="action_contract", label=""),),
    approval_granularity="all_or_nothing", priority=3,
)
env_approval = build_turn_envelope(
    live_contract_reply_owner="gateway", action_gateway_queue=_ac_queue,
)
chk("live AC queue with no reconfirmation -> approval_pending",
    env_approval.turn_mode == "approval_pending")
chk("live AC queue -> active_queue_id points at it",
    env_approval.active_queue_id == "ac:u1")
chk("live AC queue -> reply_owner is what the caller passed",
    env_approval.reply_owner == "gateway")

env_reconfirm = build_turn_envelope(
    live_contract_reply_owner="gateway",
    reconfirmation_required=True,
    action_gateway_queue=_ac_queue,
)
chk("reconfirmation_required takes priority over plain approval_pending",
    env_reconfirm.turn_mode == "reconfirmation_required")

env_disambig = build_turn_envelope(disambiguation_active=True, action_gateway_queue=_ac_queue)
chk("disambiguation_active -> partial_selection_ambiguous",
    env_disambig.turn_mode == "partial_selection_ambiguous")

_lead_queue = PendingQueueAwareness(
    queue_id="lead_preview:c1", source="lead_capture", kind="lead_candidate",
    summary="5 candidate(s) pending",
    items=tuple(PendingItem(index=i + 1, id=f"05{i}", kind="lead_candidate", label=f"lead{i}")
                for i in range(5)),
    approval_granularity="all_or_nothing", priority=5,
)
env_multi = build_turn_envelope(
    live_contract_reply_owner="gateway",
    action_gateway_queue=_ac_queue,
    lead_capture_queue=_lead_queue,
)
chk("two simultaneous queues -> both present in pending_queues",
    len(env_multi.pending_queues) == 2)
chk("two simultaneous queues -> active_queue_id picks the lower-priority-number one",
    env_multi.active_queue_id == "ac:u1")

log_dict = env_multi.to_log_dict()
chk("to_log_dict has all Gate A required fields", set(log_dict.keys()) == {
    "turn_mode", "queue_count", "queue_sources", "active_queue_id",
    "resolved_reference", "reply_owner", "message_kind", "multi_contract_conflict",
    "policy_snapshot_version", "agent_availability_mode",
})
chk("to_log_dict queue_count matches", log_dict["queue_count"] == 2)
chk("to_log_dict queue_sources matches", log_dict["queue_sources"] == ["action_gateway", "lead_capture"])
chk("single live contract -> multi_contract_conflict is False",
    log_dict["multi_contract_conflict"] is False)

_ac_queue_conflict = PendingQueueAwareness(
    queue_id="ac:u1", source="action_gateway", kind="action_contract",
    summary="2 live contract(s)",
    items=(
        PendingItem(index=1, id="c1", kind="action_contract", label=""),
        PendingItem(index=2, id="c2", kind="action_contract", label=""),
    ),
    approval_granularity="single_choice", priority=3,
)
env_conflict = build_turn_envelope(action_gateway_queue=_ac_queue_conflict)
chk("Case C1 — two live contracts -> multi_contract_conflict is True",
    env_conflict.to_log_dict()["multi_contract_conflict"] is True)


# ══════════════════════════════════════════════════
# execution_kind_of() — static classification lookup
# ══════════════════════════════════════════════════

chk("confirm_word classified as deterministic",
    execution_kind_of("confirm_word") == ExecutionKind.DETERMINISTIC)
chk("agent_tool_call classified as agent_interpreted",
    execution_kind_of("agent_tool_call") == ExecutionKind.AGENT_INTERPRETED)
chk("background_job_llm_analysis classified as agent_interpreted (but not live-turn agent)",
    execution_kind_of("background_job_llm_analysis") == ExecutionKind.AGENT_INTERPRETED)
chk("unknown call_site_id returns None, never guessed",
    execution_kind_of("something_never_registered") is None)


# ══════════════════════════════════════════════════
# log_turn_envelope() — never raises
# ══════════════════════════════════════════════════

try:
    log_turn_envelope(env_free, canonical_user_id="tenant:u1")
    chk("log_turn_envelope() with a normal envelope does not raise", True)
except Exception:
    chk("log_turn_envelope() with a normal envelope does not raise", False)

with patch("core.turn_envelope.logger") as _broken_logger:
    _broken_logger.info.side_effect = RuntimeError("logging backend down")
    try:
        log_turn_envelope(env_free, canonical_user_id="tenant:u1")
        chk("log_turn_envelope() swallows a broken logging backend", True)
    except Exception:
        chk("log_turn_envelope() swallows a broken logging backend", False)


# ══════════════════════════════════════════════════
# app._build_and_log_turn_envelope() — wiring + fail-open guarantee
# ══════════════════════════════════════════════════

import app  # noqa: E402
from identity import Identity, Role  # noqa: E402


def _identity(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


_id1 = _identity("turnenv-user-1")

# No live contracts, no batch queue, no lead preview -> must not raise and
# must not touch session_store at all (session_snapshot is passed in, per
# LL-11's single-Sessions-read-per-turn invariant — see app.py's docstring
# on _build_and_log_turn_envelope).
with patch("core.action_gateway.action_gateway") as _mock_gw, \
     patch("event_bus.batch_queue") as _mock_bq, \
     patch("session_store.lead_sessions") as _mock_ls:
    _mock_gw.find_live_contracts.return_value = []
    _mock_bq.count_pending.return_value = 0
    try:
        app._build_and_log_turn_envelope(_id1, "chat-1", None)
        chk("_build_and_log_turn_envelope() with empty state does not raise", True)
    except Exception:
        chk("_build_and_log_turn_envelope() with empty state does not raise", False)
    chk("empty state: find_live_contracts() was consulted (read-only)",
        _mock_gw.find_live_contracts.called)
    chk("session_store.lead_sessions is never touched (LL-11 single-read invariant)",
        not _mock_ls.method_calls)

# A live contract + a nonzero batch queue + a lead preview all at once ->
# still must not raise, and must reflect them in the log payload. The
# preview comes from session_snapshot directly, not a fresh session read.
_fake_contract = MagicMock(contract_id="c-live-1", reconfirmation_required=False)
_snapshot_with_preview = {
    "pending_lead_preview": {
        "candidates": [{"name": "א", "phone": "0501"}, {"name": "ב", "phone": "0502"}],
        "set_at": __import__("time").time(),
    },
}
with patch("core.action_gateway.action_gateway") as _mock_gw2, \
     patch("event_bus.batch_queue") as _mock_bq2, \
     patch("session_store.lead_sessions") as _mock_ls2, \
     patch("core.turn_envelope.log_turn_envelope") as _mock_log:
    _mock_gw2.find_live_contracts.return_value = [_fake_contract]
    _mock_bq2.count_pending.return_value = 3
    try:
        app._build_and_log_turn_envelope(_id1, "chat-1", _snapshot_with_preview)
        chk("_build_and_log_turn_envelope() with 3 simultaneous sources does not raise", True)
    except Exception:
        chk("_build_and_log_turn_envelope() with 3 simultaneous sources does not raise", False)
    chk("log_turn_envelope() was called exactly once", _mock_log.call_count == 1)
    _logged_envelope = _mock_log.call_args[0][0]
    chk("all 3 pending sources landed in the envelope", len(_logged_envelope.pending_queues) == 3)
    chk("reply_owner reflects the live contract, not a guess",
        _logged_envelope.reply_owner == "gateway")
    chk("session_store.lead_sessions is still never touched with a snapshot passed in",
        not _mock_ls2.method_calls)
    chk("active_queue_id never contains the raw memory_key (PII boundary)",
        _id1.memory_key not in (_logged_envelope.active_queue_id or ""))
    chk("no PendingItem.id/label anywhere carries the raw phone number",
        all("0501" not in (i.id + i.label) and "0502" not in (i.id + i.label)
            for q in _logged_envelope.pending_queues for i in q.items))
    chk("no PendingItem.label anywhere carries the raw lead name",
        all("א" not in i.label and "ב" not in i.label
            for q in _logged_envelope.pending_queues for i in q.items))

# An expired preview (set_at > 1800s ago) must not surface as a pending
# queue, and must not be mutated/cleared (Phase 0 never writes).
_snapshot_with_expired_preview = {
    "pending_lead_preview": {
        "candidates": [{"name": "א", "phone": "0501"}],
        "set_at": __import__("time").time() - 9999,
    },
}
with patch("core.action_gateway.action_gateway") as _mock_gw2b, \
     patch("event_bus.batch_queue") as _mock_bq2b, \
     patch("core.turn_envelope.log_turn_envelope") as _mock_log2b:
    _mock_gw2b.find_live_contracts.return_value = []
    _mock_bq2b.count_pending.return_value = 0
    app._build_and_log_turn_envelope(_id1, "chat-1", _snapshot_with_expired_preview)
    _logged_envelope2b = _mock_log2b.call_args[0][0]
    chk("expired lead preview does not surface as a pending queue",
        _logged_envelope2b.pending_queues == ())
    chk("expired preview leaves turn_mode as free_agent",
        _logged_envelope2b.turn_mode == "free_agent")

# Every lookup raising -> must still not raise (fail-open, Phase 0's core
# guarantee: this instrumentation can never break a live turn) AND must not
# be silent about it — a visible, structured build_failed log is required.
with patch("core.action_gateway.action_gateway") as _mock_gw3, \
     patch("event_bus.batch_queue") as _mock_bq3, \
     patch.object(app, "logger") as _mock_app_logger:
    _mock_gw3.find_live_contracts.side_effect = KeyError("Airtable down")
    _mock_bq3.count_pending.side_effect = RuntimeError("lock error")
    try:
        app._build_and_log_turn_envelope(
            _id1, "chat-1", {"pending_lead_preview": "not-a-dict"}, entry_point="test_entry",
        )
        chk("_build_and_log_turn_envelope() fail-opens when every lookup raises", True)
    except Exception:
        chk("_build_and_log_turn_envelope() fail-opens when every lookup raises", False)
    chk("build_failed is logged at a visible level (not silent)",
        _mock_app_logger.warning.call_count == 1)
    _warn_args = _mock_app_logger.warning.call_args[0]
    _warn_msg = _warn_args[0] % _warn_args[1:]
    chk("build_failed log names the real error_type (KeyError), not a generic message",
        "error_type=KeyError" in _warn_msg)
    chk("build_failed log names the entry_point the caller passed",
        "entry_point=test_entry" in _warn_msg)
    chk("build_failed log does not contain the raw exception message text",
        "Airtable down" not in _warn_msg)
    chk("build_failed log fingerprints the user id, not the raw memory_key",
        _id1.memory_key not in _warn_msg)


# ══════════════════════════════════════════════════
# Case C — clarification continuity signals
# See docs/architecture/turn-coordinator/CASE_C_CLARIFICATION_CONTINUITY.md
# ══════════════════════════════════════════════════

chk("C2: pending-language reply with nothing pending and nothing queued -> True",
    detect_case_c2_signal(
        "5 הפריטים מוכנים, הפעולה ממתינה לאישור", queue_count=0, approval_queued_this_turn=False,
    ) is True)
chk("C2: same reply, but a queue is actually pending -> False (not a false claim)",
    detect_case_c2_signal(
        "5 הפריטים מוכנים, הפעולה ממתינה לאישור", queue_count=1, approval_queued_this_turn=False,
    ) is False)
chk("C2: same reply, but an approval WAS queued this turn -> False",
    detect_case_c2_signal(
        "5 הפריטים מוכנים, הפעולה ממתינה לאישור", queue_count=0, approval_queued_this_turn=True,
    ) is False)
chk("C2: ordinary reply with no pending-language at all -> False",
    detect_case_c2_signal(
        "בטח, אשמח לעזור עם זה", queue_count=0, approval_queued_this_turn=False,
    ) is False)
chk("C2: empty reply never signals",
    detect_case_c2_signal("", queue_count=0, approval_queued_this_turn=False) is False)

with patch("core.turn_envelope.logger") as _mock_c_logger:
    log_case_c_signal("C1", canonical_user_id="boss_hq:0501234567", detail="live_contracts=2")
    chk("log_case_c_signal uses WARNING level (visible by default)",
        _mock_c_logger.warning.call_count == 1)
    _c_args = _mock_c_logger.warning.call_args[0]
    _c_msg = _c_args[0] % _c_args[1:]
    chk("log_case_c_signal names the kind", "kind=C1" in _c_msg)
    chk("log_case_c_signal includes the detail", "detail=live_contracts=2" in _c_msg)
    chk("log_case_c_signal fingerprints canonical_user_id, never logs it raw",
        "0501234567" not in _c_msg)

with patch("core.turn_envelope.logger") as _mock_c_logger2:
    _mock_c_logger2.warning.side_effect = RuntimeError("logging backend down")
    try:
        log_case_c_signal("C2", canonical_user_id="u1")
        chk("log_case_c_signal never raises even if the logging backend breaks", True)
    except Exception:
        chk("log_case_c_signal never raises even if the logging backend breaks", False)

# Wiring: app._build_and_log_turn_envelope() must fire the C1 signal when
# find_live_contracts() reports more than one live contract for an identity
# — the exact BatchQueueStore invariant violation Case C1 describes — and
# must NOT fire it for the single-contract, ordinary-approval case.
_fake_contract_a = MagicMock(contract_id="c-a", reconfirmation_required=False)
_fake_contract_b = MagicMock(contract_id="c-b", reconfirmation_required=False)
with patch("core.action_gateway.action_gateway") as _mock_gw4, \
     patch("event_bus.batch_queue") as _mock_bq4, \
     patch("core.turn_envelope.log_case_c_signal") as _mock_c1_log:
    _mock_gw4.find_live_contracts.return_value = [_fake_contract_a, _fake_contract_b]
    _mock_bq4.count_pending.return_value = 0
    app._build_and_log_turn_envelope(_id1, "chat-1", None)
    chk("_build_and_log_turn_envelope(): 2 live contracts -> C1 signal fires exactly once",
        _mock_c1_log.call_count == 1)
    _c1_call_kwargs = _mock_c1_log.call_args
    chk("C1 signal call passes kind='C1'", _c1_call_kwargs[0][0] == "C1")

with patch("core.action_gateway.action_gateway") as _mock_gw5, \
     patch("event_bus.batch_queue") as _mock_bq5, \
     patch("core.turn_envelope.log_case_c_signal") as _mock_c1_log2:
    _mock_gw5.find_live_contracts.return_value = [_fake_contract_a]
    _mock_bq5.count_pending.return_value = 0
    app._build_and_log_turn_envelope(_id1, "chat-1", None)
    chk("_build_and_log_turn_envelope(): 1 live contract -> C1 signal does not fire",
        _mock_c1_log2.call_count == 0)


# ══════════════════════════════════════════════════
# Ownership signal — recognized_intent/selected_handler/tool_use_emitted/
# approval_queued/agent_claimed_approval/reply_owner
# ══════════════════════════════════════════════════

_hijack_signal = build_ownership_signal(
    recognized_intent="create_task", selected_handler="agent",
    tool_use_emitted=False, approval_queued=False,
    final_reply="הפעולה ממתינה לאישור.",
)
chk("hijack scenario: agent_claimed_approval is True (text matches pending language)",
    _hijack_signal.agent_claimed_approval is True)
chk("hijack scenario: is_hijack is True (claimed + no tool_use + nothing queued)",
    _hijack_signal.is_hijack is True)
chk("hijack scenario: fields match the requested log shape exactly",
    _hijack_signal.to_log_dict() == {
        "recognized_intent": "create_task", "selected_handler": "agent",
        "tool_use_emitted": False, "approval_queued": False,
        "agent_claimed_approval": True, "reply_owner": "agent",
    })

_legit_signal = build_ownership_signal(
    recognized_intent="create_task", selected_handler="agent",
    tool_use_emitted=True, approval_queued=True,
    final_reply="הפעולה ממתינה לאישור.",
)
chk("legit scenario: same claim text, but tool_use WAS emitted and approval WAS queued -> not a hijack",
    _legit_signal.is_hijack is False)

_ordinary_signal = build_ownership_signal(
    recognized_intent="general_chat", selected_handler="agent",
    tool_use_emitted=False, approval_queued=False,
    final_reply="בטח, אשמח לעזור.",
)
chk("ordinary reply (no pending-language claim at all) -> not a hijack",
    _ordinary_signal.is_hijack is False)
chk("ordinary reply -> agent_claimed_approval is False",
    _ordinary_signal.agent_claimed_approval is False)

_partial_signal = build_ownership_signal(
    recognized_intent="create_task", selected_handler="agent",
    tool_use_emitted=True, approval_queued=False,
    final_reply="הפעולה ממתינה לאישור.",
)
chk("tool_use WAS emitted (even though nothing got queued, e.g. denied) -> not classified as hijack",
    _partial_signal.is_hijack is False)

chk("build_ownership_signal defaults reply_owner to 'agent'",
    _hijack_signal.reply_owner == "agent")
chk("build_ownership_signal falls back to 'unknown' for empty intent/handler",
    build_ownership_signal(
        recognized_intent="", selected_handler="", tool_use_emitted=False,
        approval_queued=False, final_reply="",
    ).recognized_intent == "unknown")

with patch("core.turn_envelope.logger") as _mock_own_logger:
    log_ownership_signal(_hijack_signal, canonical_user_id="boss_hq:0501234567")
    chk("log_ownership_signal logs the routine INFO line",
        _mock_own_logger.info.call_count == 1)
    chk("log_ownership_signal ALSO logs a distinct WARNING when is_hijack is True",
        _mock_own_logger.warning.call_count == 1)
    _info_args = _mock_own_logger.info.call_args[0]
    _info_msg = _info_args[0] % _info_args[1:]
    chk("routine log fingerprints canonical_user_id, never logs it raw",
        "0501234567" not in _info_msg)
    chk("routine log carries recognized_intent=create_task",
        '"recognized_intent": "create_task"' in _info_msg)
    _warn_args = _mock_own_logger.warning.call_args[0]
    _warn_msg = _warn_args[0] % _warn_args[1:]
    chk("hijack WARNING line names the intent and handler",
        "intent=create_task" in _warn_msg and "handler=agent" in _warn_msg)

with patch("core.turn_envelope.logger") as _mock_own_logger2:
    log_ownership_signal(_legit_signal, canonical_user_id="u1")
    chk("log_ownership_signal logs routine INFO even for a non-hijack turn",
        _mock_own_logger2.info.call_count == 1)
    chk("log_ownership_signal does NOT emit the WARNING line when is_hijack is False",
        _mock_own_logger2.warning.call_count == 0)

with patch("core.turn_envelope.logger") as _mock_own_logger3:
    _mock_own_logger3.info.side_effect = RuntimeError("logging backend down")
    try:
        log_ownership_signal(_hijack_signal, canonical_user_id="u1")
        chk("log_ownership_signal never raises even if the logging backend breaks", True)
    except Exception:
        chk("log_ownership_signal never raises even if the logging backend breaks", False)


print(f"\n{'='*50}")
print(f"turn_envelope tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
