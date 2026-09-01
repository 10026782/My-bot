from types import SimpleNamespace
from unittest.mock import patch

import abandoned_lead_worker as worker
from core.action_gateway import APPROVAL_POLICY_SELF_CONFIRM, classify_approval_policy
from identity import Role


class FakeGateway:
    def __init__(self, status="completed", record_id="rec-task"):
        self.status = status
        self.record_id = record_id
        self.proposal = None
        self.approval = None

    def propose_action(self, **kwargs):
        self.proposal = kwargs
        return SimpleNamespace(ok=True, contract_id="contract-1", reason="accepted")

    def approve(self, *args, **kwargs):
        self.approval = (args, kwargs)
        return "misleading display text"

    def find_by_id(self, _contract_id):
        return SimpleNamespace(
            status=self.status,
            agent_observations=(
                [{"kind": "execution_fact", "record_id": self.record_id}]
                if self.record_id else []
            ),
        )


def _lead():
    return worker.AbandonedLead(
        sender="+972500000000", channel="voice", domain="import",
        step=3, total_steps=5, minutes_silent=12.0,
        answers={"product": "steel"},
    )


def test_task_writer_uses_gateway_identity_payload_and_structured_result():
    gateway = FakeGateway()
    with patch("core.action_gateway.action_gateway", gateway), patch.object(worker, "_notify_human_pipeline"):
        assert worker.create_human_pipeline_task(_lead(), "owner") is True
    assert gateway.proposal["trusted_source"] == "abandoned_lead_scheduler"
    identity = gateway.proposal["identity"]
    assert identity.user_id == "abandoned_lead_scheduler"
    assert identity.role == Role.MANAGER
    assert identity.channel == "scheduler"
    assert gateway.proposal["tool_inputs"]["table"] == "משימות (Tasks)"
    assert gateway.proposal["tool_inputs"]["fields"] == {
        "כותרת המשימה": "📞 ליד נטוש — +972500000000",
        "סטטוס": "ממתין",
        "תיאור": "ערוץ: voice | דומיין: import\nעדיפות: high\nשלב נטישה: 3/5\nזמן שתיקה: 12 דקות\nתשובות: product=steel",
    }
    assert gateway.approval is not None


def test_task_policy_is_exact_and_display_text_is_not_authority():
    fields = {"כותרת המשימה": "x", "סטטוס": "ממתין", "תיאור": "y"}
    assert classify_approval_policy(
        "airtable_add", {"table": "Tasks", "fields": fields},
        "abandoned_lead_scheduler",
    ) == APPROVAL_POLICY_SELF_CONFIRM
    assert classify_approval_policy(
        "airtable_add", {"table": "Tasks", "fields": {**fields, "Owner": "x"}},
        "abandoned_lead_scheduler",
    ) != APPROVAL_POLICY_SELF_CONFIRM


def test_missing_structured_execution_fails_closed_without_notification():
    gateway = FakeGateway(status="failed", record_id="")
    with patch("core.action_gateway.action_gateway", gateway), patch.object(worker, "_notify_human_pipeline") as notify:
        assert worker.create_human_pipeline_task(_lead(), "owner") is False
    notify.assert_not_called()


def test_direct_provider_write_is_not_imported_or_called():
    gateway = FakeGateway()
    with patch("core.action_gateway.action_gateway", gateway), patch("tools.airtable_tools.airtable_add") as direct, patch.object(worker, "_notify_human_pipeline"):
        assert worker.create_human_pipeline_task(_lead(), "owner") is True
    direct.assert_not_called()


def test_replay_fails_closed_when_gateway_reports_duplicate():
    gateway = FakeGateway(status="completed", record_id="")
    gateway.propose_action = lambda **kwargs: SimpleNamespace(
        ok=False, contract_id="contract-old", reason="duplicate",
    )
    with patch("core.action_gateway.action_gateway", gateway), patch.object(worker, "_notify_human_pipeline") as notify:
        assert worker.create_human_pipeline_task(_lead(), "owner") is False
    notify.assert_not_called()


def test_retry_with_different_elapsed_silence_is_a_new_identity():
    # BUG-CRM-BYPASS-FINGERPRINT-PARITY follow-up (02/09/2026): this test
    # used to assert the OPPOSITE — that a retry with a different
    # minutes_silent produced the SAME fingerprint_payload, via a custom
    # "abandoned_event" identity object distinct from the real dispatched
    # fields. That object became the contract's stored
    # business_action_fingerprint (core/action_gateway.py's propose_action()),
    # but tools/dispatcher.py's _validate_execution_proof() always recomputes
    # from the real dispatched tool_inputs (whose DESCRIPTION embeds
    # minutes_silent) at execution time — the two could never match, so
    # every one of these tasks failed execution 100% of the time. No retry
    # was ever actually deduped, because no task was ever actually created.
    #
    # Fix: no custom fingerprint_payload — the fingerprint is always the real
    # dispatched payload, so execution now succeeds. Acknowledged trade-off:
    # since DESCRIPTION legitimately shows the human-facing elapsed-silence
    # minutes (not a debug breadcrumb like interaction_engine.py's Memory ID
    # was — see test_f52_g4_s4), two calls for the same abandoned-lead event
    # with a different minutes_silent are no longer recognized as the same
    # logical identity, and retry-dedup insensitive to elapsed time is not
    # provided by this mechanism. A working write beats a perfectly-deduped
    # write that never happens; true elapsed-time-insensitive dedup (if
    # wanted) needs a separate, dedicated check keyed on
    # (sender, channel, domain, step) BEFORE propose_action() is ever
    # called, not a second fingerprint representation.
    first = FakeGateway()
    second = FakeGateway()
    with patch("core.action_gateway.action_gateway", first), patch.object(worker, "_notify_human_pipeline"):
        assert worker.create_human_pipeline_task(_lead(), "owner") is True
    with patch("core.action_gateway.action_gateway", second), patch.object(worker, "_notify_human_pipeline"):
        assert worker.create_human_pipeline_task(
            worker.AbandonedLead(**{**_lead().__dict__, "minutes_silent": 99.0}), "owner"
        ) is True
    assert "fingerprint_payload" not in first.proposal
    assert first.proposal["tool_inputs"] != second.proposal["tool_inputs"]
