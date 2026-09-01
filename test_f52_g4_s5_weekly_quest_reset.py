"""Focused F52-G4-S5 checks for the weekly Quest reset writer."""

import inspect
import os
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import scheduler
from core.action_gateway import APPROVAL_POLICY_SELF_CONFIRM, classify_approval_policy
from identity import Role


class FakeGateway:
    def __init__(self, status="completed", record_id="rec-q1"):
        self.status = status
        self.record_id = record_id
        self.proposals = []
        self.contracts = {}

    def propose_action(self, **kwargs):
        self.proposals.append(kwargs)
        contract_id = f"contract-{len(self.proposals)}"
        self.contracts[contract_id] = SimpleNamespace(
            status=self.status,
            agent_observations=(
                [{"kind": "execution_fact", "record_id": self.record_id}]
                if self.record_id else []
            ),
        )
        return SimpleNamespace(ok=True, contract_id=contract_id, reason="registered")

    def approve(self, *_args, **_kwargs):
        return "misleading display text"

    def find_by_id(self, contract_id):
        return self.contracts.get(contract_id)


def test_weekly_reset_has_no_direct_provider_patch():
    assert "_at_patch" not in inspect.getsource(scheduler._job_weekly_quest_reset)


def test_weekly_reset_uses_explicit_system_identity_and_policy():
    fields = {"Status": "Todo", "Week_Start": "2026-09-01"}
    assert classify_approval_policy(
        "airtable_update",
        {"table": "Quests", "record_id": "rec-q1", "fields": fields},
        "weekly_quest_reset_scheduler",
    ) == APPROVAL_POLICY_SELF_CONFIRM


def test_same_week_and_target_have_same_logical_identity():
    # BUG-CRM-BYPASS-FINGERPRINT-PARITY follow-up (02/09/2026): this used to
    # assert on a custom fingerprint_payload with extra "action"/"week" keys
    # not present in the real dispatched tool_inputs — core/action_gateway.py's
    # propose_action() stores THAT as the contract's business_action_fingerprint,
    # but tools/dispatcher.py's _validate_execution_proof() always recomputes
    # from the real tool_inputs at execution time, so the two could never
    # match and this job failed every single run. _apply_weekly_quest_mutation()
    # no longer passes a custom fingerprint_payload at all — but the logical
    # identity property this test cares about is unaffected: last_monday/
    # target_id are fully deterministic (never volatile), so tool_inputs
    # alone already has the same "same params -> same identity" property,
    # with no separate representation left to diverge.
    gateway = FakeGateway()
    with patch("core.action_gateway.action_gateway", gateway):
        scheduler._apply_weekly_quest_mutation("2026-08-24", "2026-08-31", "rec-q1")
        scheduler._apply_weekly_quest_mutation("2026-08-24", "2026-08-31", "rec-q1")
    assert gateway.proposals[0]["tool_inputs"] == gateway.proposals[1]["tool_inputs"]
    assert "fingerprint_payload" not in gateway.proposals[0]


def test_week_or_target_changes_logical_identity():
    gateway = FakeGateway()
    with patch("core.action_gateway.action_gateway", gateway):
        scheduler._apply_weekly_quest_mutation("2026-08-24", "2026-08-31", "rec-q1")
        scheduler._apply_weekly_quest_mutation("2026-08-31", "2026-09-07", "rec-q1")
        scheduler._apply_weekly_quest_mutation("2026-08-24", "2026-08-31", "rec-q2")
    identities = [repr(p["tool_inputs"]) for p in gateway.proposals]
    assert len(set(identities)) == 3


def test_structured_failure_is_not_aggregate_success():
    gateway = FakeGateway(status="failed", record_id="")
    with patch("core.action_gateway.action_gateway", gateway):
        result = scheduler._apply_weekly_quest_mutation("2026-08-24", "2026-08-31", "rec-q1")
    assert result["ok"] is False
    assert result["status"] == "failed"


def test_system_identity_is_manager_scheduler():
    gateway = FakeGateway()
    with patch("core.action_gateway.action_gateway", gateway):
        scheduler._apply_weekly_quest_mutation("2026-08-24", "2026-08-31", "rec-q1")
    identity = gateway.proposals[0]["identity"]
    assert (identity.user_id, identity.role, identity.channel) == (
        "weekly_quest_reset_scheduler", Role.MANAGER, "scheduler"
    )


def test_weekly_reset_reports_partial_failure_without_false_success():
    gateway = FakeGateway()
    gateway.statuses = iter(("completed", "failed"))

    def propose(**kwargs):
        gateway.proposals.append(kwargs)
        status = next(gateway.statuses)
        contract_id = f"contract-{len(gateway.proposals)}"
        gateway.contracts[contract_id] = SimpleNamespace(
            status=status,
            agent_observations=(
                [{"kind": "execution_fact", "record_id": kwargs["tool_inputs"]["record_id"]}]
                if status == "completed" else []
            ),
        )
        return SimpleNamespace(ok=True, contract_id=contract_id, reason="registered")

    gateway.propose_action = propose
    last_week = (date.today() - timedelta(days=6)).isoformat()
    records = [
        {"id": "rec-q1", "fields": {"Week_Start": last_week, "Status": "Todo", "Coins": 1}},
        {"id": "rec-q2", "fields": {"Week_Start": last_week, "Status": "Todo", "Coins": 1}},
    ]

    def listed(table, *_args, **_kwargs):
        if table == "Quests":
            return records
        return []

    with patch("core.action_gateway.action_gateway", gateway), \
            patch("feature_flags.is_enabled", return_value=True), \
            patch("tma_api._at_list", side_effect=listed), \
            patch.object(scheduler, "_game_bot_send"), \
            patch.dict(os.environ, {"TELEGRAM_TOKEN": "token", "DIGEST_CHAT_ID": "chat"}):
        result = scheduler._job_weekly_quest_reset()
    assert result["ok"] is False
    assert result["status"] == "partial"
    assert [item["ok"] for item in result["results"]] == [True, False]
