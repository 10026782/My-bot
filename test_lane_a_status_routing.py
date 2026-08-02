"""Lane A D-018/D-019 acceptance tests."""

from __future__ import annotations

import logging
import os
import time
import threading
from unittest.mock import patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-lane-a-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:LANE_A_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patLaneATest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appLaneATest")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app
from core.action_gateway import ActionContract, ActionGateway, ExecutionLedger, action_gateway
from core.agent_message_formatter import format_baseline_status_summary
from identity import Identity, Role


def _contract(contract_id: str, user: str, status: str, created_at: float = 1.0) -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id=user,
        tool_name="airtable_add",
        normalized_payload={"table": "Tasks", "fields": {"Name": "safe"}},
        business_action_fingerprint=f"fp-{contract_id}",
        origin_channel="telegram",
        origin_chat_id=user,
        requires_approval=True,
        status=status,
        created_at=created_at,
    )


def test_d019_baseline_vocabulary_and_verified_success_gate():
    assert format_baseline_status_summary("approval_pending") == "הפעולה ממתינה לאישור."
    assert format_baseline_status_summary("failure") == "הפעולה לא הושלמה."
    assert format_baseline_status_summary("cancelled") == "הפעולה בוטלה."
    assert format_baseline_status_summary("success", execution_verified=True) == "הפעולה הושלמה."
    assert format_baseline_status_summary("success") == "לא ניתן לאמת שהפעולה הושלמה."
    with pytest.raises(ValueError, match="unsupported baseline"):
        format_baseline_status_summary("internal_weird_state")


def test_query_execution_status_reads_only_identity_index(caplog):
    ledger = ExecutionLedger()
    for index in range(109):
        ledger.save(_contract(f"other-{index}", "other-user", "completed", float(index)))
    own = _contract("own", "target-user", "failed", time.time())
    ledger.save(own)
    gateway = ActionGateway(ledger=ledger, tool_executor=lambda **_: {})

    with caplog.at_level(logging.INFO):
        reply = gateway.query_execution_status("target-user", live_contracts=[])

    assert reply == "הפעולה לא הושלמה"
    assert "records_scanned=1" in caplog.text
    assert "records_scanned=109" not in caplog.text
    assert "status_route_owner=approval_runtime" in caplog.text


@pytest.mark.parametrize("query", ["מה מצב הפעולה?", "מה מצב הפעולה"])
def test_generic_status_question_never_invokes_agent_and_has_safe_fallback(query):
    identity = Identity(user_id="lane-a", role=Role.OWNER)
    meta = {}
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(action_gateway, "find_live_contracts", return_value=[]), \
         patch.object(action_gateway, "query_execution_status", return_value=None) as status_query, \
         patch.object(app, "_safe_route") as router_call, \
         patch.object(app.client.messages, "create") as agent_call:
        reply = app.run_agent(
            query, "lane-a", channel="telegram", _out_meta=meta,
        )

    assert reply == "לא מצאתי מידע עדכני על הפעולה."
    status_query.assert_called_once_with(identity.memory_key, live_contracts=[])
    router_call.assert_not_called()
    agent_call.assert_not_called()
    assert meta["status_route_owner"] == "approval_runtime"


def test_pending_query_precedes_generic_status_route_and_reuses_snapshot():
    identity = Identity(user_id="lane-a-pending", role=Role.OWNER)
    pending = _contract("pending-one", identity.memory_key, "pending")
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(action_gateway, "find_live_contracts", return_value=[pending]) as live_read, \
         patch.object(action_gateway, "describe_pending_queue", return_value="pending-safe") as pending_query, \
         patch.object(action_gateway, "query_execution_status") as status_query, \
         patch.object(app, "_safe_route") as router_call, \
         patch.object(app.client.messages, "create") as agent_call:
        reply = app.run_agent("מה ממתין לאישור?", "lane-a-pending", channel="telegram")

    assert reply == "pending-safe"
    live_read.assert_called_once()
    pending_query.assert_called_once_with(identity.memory_key, live_contracts=[pending])
    status_query.assert_not_called()
    router_call.assert_not_called()
    agent_call.assert_not_called()


def test_recent_rejected_contract_returns_cancellation_status():
    ledger = ExecutionLedger()
    ledger.save(_contract("rejected-own", "target-user", "rejected", time.time()))
    gateway = ActionGateway(ledger=ledger, tool_executor=lambda **_: {})

    reply = gateway.query_execution_status("target-user", live_contracts=[])
    assert "בוטלה" in reply
    assert "rejected" not in reply
    assert "rejected-own" not in reply
    assert "airtable_add" not in reply


def test_rejected_status_is_not_lost_after_status_window():
    ledger = ExecutionLedger()
    rejected = _contract(
        "rejected-aged", "target-user-aged", "rejected", time.time() - 601,
    )
    ledger.save(rejected)
    gateway = ActionGateway(ledger=ledger, tool_executor=lambda **_: {})

    reply = gateway.query_execution_status("target-user-aged", live_contracts=[])

    assert reply == "הפעולה בוטלה."
    assert rejected.status == "rejected"


def test_cancel_word_replays_only_latest_rejected_terminal_without_mutation():
    ledger = ExecutionLedger()
    rejected = _contract(
        "rejected-replay", "target-user-replay", "rejected", time.time(),
    )
    ledger.save(rejected)
    gateway = ActionGateway(ledger=ledger, tool_executor=lambda **_: {})

    reply = gateway.route_cancellation_word(
        "target-user-replay", live_contracts=[], recent_terminal=rejected,
    )

    assert reply == "הפעולה כבר בוטלה"
    assert rejected.status == "rejected"


def test_pr2_cancel_path_supplies_bounded_rejected_terminal_replay():
    identity = Identity(user_id="lane-a-replay", role=Role.OWNER)
    rejected = _contract(
        "rejected-pr2", identity.memory_key, "rejected", time.time(),
    )
    with patch("feature_flags.is_enabled", return_value=True), \
         patch.object(action_gateway, "find_recent_terminal_by_user", return_value=rejected) as recent_lookup, \
         patch.object(
             action_gateway,
             "route_cancellation_word",
             return_value="הפעולה כבר בוטלה",
         ) as cancel_route:
        reply = app._resolve_pr2_deterministic_approval(
            user_text="לא",
            identity=identity,
            live_contracts=[],
            out_meta={},
        )

    assert reply == "הפעולה כבר בוטלה"
    recent_lookup.assert_called_once()
    cancel_route.assert_called_once_with(
        identity.memory_key,
        live_contracts=[],
        recent_terminal=rejected,
        safe_multiple=True,
    )


def test_pending_lock_expiry_cleanup_and_duplicate_release(caplog):
    chat_id = "lane-a-expired-lock"
    with app._pending_approvals_lock:
        app._pending_approvals.pop(chat_id, None)
        approval_id = app._add_pending_approval(chat_id, {
            "text": "safe request", "created_at": time.time() - app._PENDING_APPROVAL_TTL - 1,
        })
        with caplog.at_level(logging.INFO):
            assert app._release_expired_pending_approvals(chat_id) == 1
        assert chat_id not in app._pending_approvals
        assert app._pop_pending_approval(chat_id, approval_id) is None
    assert "lock_release_reason=expired" in caplog.text
    assert "stuck_lock_age_seconds=" in caplog.text


def test_status_snapshot_unavailable_fails_closed_without_agent():
    identity = Identity(user_id="lane-a-unavailable", role=Role.OWNER)
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(action_gateway, "find_live_contracts", side_effect=RuntimeError("down")), \
         patch.object(app, "_safe_route") as router_call, \
         patch.object(app.client.messages, "create") as agent_call:
        reply = app.run_agent(
            "מה מצב הפעולה?", "lane-a-unavailable", channel="telegram",
        )

    assert reply == "לא ניתן לבדוק כרגע את מצב הפעולה."
    router_call.assert_not_called()
    agent_call.assert_not_called()


def test_pending_lock_concurrent_terminal_release_has_single_winner():
    chat_id = "lane-a-concurrent-lock"
    with app._pending_approvals_lock:
        app._pending_approvals.pop(chat_id, None)
        approval_id = app._add_pending_approval(chat_id, {
            "text": "safe request", "created_at": time.time(),
        })
    winners = []

    def release() -> None:
        with app._pending_approvals_lock:
            winners.append(app._pop_pending_approval(
                chat_id, approval_id, release_reason="cancelled",
            ))

    threads = [threading.Thread(target=release) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(item is not None for item in winners) == 1
    assert chat_id not in app._pending_approvals
