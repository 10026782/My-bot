"""Focused F52-G4-S4 checks for the complete interaction Task writer."""

import inspect
from types import SimpleNamespace
from unittest.mock import patch

import interaction_engine
from airtable_schema import Tables, TaskFields
from core.action_gateway import (
    APPROVAL_POLICY_SELF_CONFIRM,
    classify_approval_policy,
)
from identity import Role


class FakeGateway:
    def __init__(self, outcomes=None):
        self.proposals = []
        self.contracts = {}
        self._ledger = self
        self.outcomes = iter(outcomes or [("completed", "rec-task")])

    def propose_action(self, **kwargs):
        self.proposals.append(kwargs)
        status, record_id = next(self.outcomes)
        contract_id = f"contract-{len(self.proposals)}"
        self.contracts[contract_id] = SimpleNamespace(
            status=status,
            agent_observations=(
                [{"kind": "execution_fact", "record_id": record_id}]
                if record_id else []
            ),
        )
        return SimpleNamespace(
            ok=status != "proposal_failed", contract_id=contract_id,
            reason="test",
        )

    def approve(self, *_args, **_kwargs):
        return "misleading display text"

    def find_by_id(self, contract_id):
        return self.contracts.get(contract_id)


def _inputs(tasks):
    return (
        interaction_engine.InteractionAnalysis(tasks=tasks, sentiment="negative"),
        interaction_engine.InteractionSchema(
            source_channel="calendar", raw_id="event-42", title="Supplier meeting",
            domain="import", metadata={"tenant_id": "tenant-1"},
        ),
    )


def test_writer_has_no_direct_provider_mutation():
    source = inspect.getsource(
        interaction_engine.create_tasks_from_analysis
    )
    assert "from tools.airtable_tools import airtable_add" not in source
    assert "airtable_add(Tables.TASKS" not in source


def test_all_tasks_share_action_principal_and_policy():
    analysis, interaction = _inputs([
        {"title": "Call supplier", "owner": "Eli"},
        {"title": "Send quote", "owner": "Eli", "due": "2026-09-01"},
    ])
    gateway = FakeGateway([("completed", "rec-1"), ("completed", "rec-2")])
    with patch("core.action_gateway.action_gateway", gateway):
        assert interaction_engine.create_tasks_from_analysis(analysis, interaction) == 2
    assert {p["tool_name"] for p in gateway.proposals} == {"airtable_add"}
    assert {p["trusted_source"] for p in gateway.proposals} == {"interaction_engine_scheduler"}
    assert {p["identity"].user_id for p in gateway.proposals} == {"interaction_engine_scheduler"}


def test_due_date_and_no_due_date_use_one_policy():
    required = {
        TaskFields.NAME: "x", TaskFields.STATUS: "ממתין", TaskFields.DESCRIPTION: "d",
    }
    with_due = dict(required, **{TaskFields.DUE_DATE: "2026-09-01"})
    for fields in (required, with_due):
        assert classify_approval_policy(
            "airtable_add", {"table": Tables.TASKS, "fields": fields},
            "interaction_engine_scheduler",
        ) == APPROVAL_POLICY_SELF_CONFIRM


def test_fingerprint_ignores_transient_memory_id_and_changes_for_logical_task():
    # BUG-CRM-BYPASS-FINGERPRINT-PARITY follow-up (02/09/2026): this used to
    # assert on a custom fingerprint_payload built to exclude Memory ID from
    # a separate "identity" object — core/action_gateway.py's propose_action()
    # stores THAT as the contract's business_action_fingerprint, but
    # tools/dispatcher.py's _validate_execution_proof() always recomputes
    # from the real dispatched tool_inputs (which DID include "Memory ID:
    # ..." in DESCRIPTION) at execution time — the two could never match, so
    # every proposed task failed execution. Fixed at the source: Memory ID is
    # no longer embedded in the dispatched DESCRIPTION at all, so tool_inputs
    # itself is now memory-id-invariant — no separate fingerprint object
    # needed, and the exact same two properties this test checks (memory-a
    # vs memory-b -> identical; a different task title -> different) still
    # hold, now via tool_inputs directly.
    tasks = [{"title": "Call supplier", "owner": "Eli", "due": "2026-09-01"}]
    analysis, interaction = _inputs(tasks)
    first = FakeGateway()
    second = FakeGateway()
    with patch("core.action_gateway.action_gateway", first):
        interaction_engine.create_tasks_from_analysis(analysis, interaction, "memory-a")
    with patch("core.action_gateway.action_gateway", second):
        interaction_engine.create_tasks_from_analysis(analysis, interaction, "memory-b")
    assert first.proposals[0]["tool_inputs"] == second.proposals[0]["tool_inputs"]
    assert "fingerprint_payload" not in first.proposals[0]
    assert "Memory ID" not in first.proposals[0]["tool_inputs"]["fields"][TaskFields.DESCRIPTION]

    changed_analysis, _ = _inputs([{"title": "Different task", "owner": "Eli", "due": "2026-09-01"}])
    changed = FakeGateway()
    with patch("core.action_gateway.action_gateway", changed):
        interaction_engine.create_tasks_from_analysis(changed_analysis, interaction, "memory-a")
    assert changed.proposals[0]["tool_inputs"] != first.proposals[0]["tool_inputs"]


def test_structured_result_controls_success_not_display_text():
    analysis, interaction = _inputs([{"title": "Call supplier", "owner": "Eli"}])
    failed = FakeGateway([("failed", "rec-ignored")])
    with patch("core.action_gateway.action_gateway", failed):
        assert interaction_engine.create_tasks_from_analysis(analysis, interaction) == 0

    succeeded = FakeGateway([("completed", "rec-structured")])
    with patch("core.action_gateway.action_gateway", succeeded):
        assert interaction_engine.create_tasks_from_analysis(analysis, interaction) == 1


def test_partial_failure_continues_processing():
    analysis, interaction = _inputs([
        {"title": "First", "owner": "Eli"},
        {"title": "Second", "owner": "Eli"},
        {"title": "Third", "owner": "Eli"},
    ])
    gateway = FakeGateway([
        ("completed", "rec-1"), ("failed", ""), ("completed", "rec-3"),
    ])
    with patch("core.action_gateway.action_gateway", gateway):
        assert interaction_engine.create_tasks_from_analysis(analysis, interaction) == 2
    assert len(gateway.proposals) == 3
