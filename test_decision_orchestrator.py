#!/usr/bin/env python3
"""Regression tests for Decision Hub Stage 6 lifecycle orchestration."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

from airtable_schema import (
    DecisionDomain as DOMAIN,
    DecisionFields as DF,
    DecisionReadiness as DR,
    DecisionStakeholderFields as SF,
    DecisionStakeholderPosition as SP,
    DecisionStakeholderRole as SR,
    DecisionStatus as DS,
)
from decision_confidence import ConfidenceResult
from decision_orchestrator import (
    PHASE_AWAITING,
    PHASE_BLOCKED,
    PHASE_CLOSED,
    PHASE_COLLECTING,
    PHASE_DECIDED,
    PHASE_REVIEW,
    append_orchestrator_to_card,
    format_orchestrator_card,
    orchestrate,
)

passed = 0
failed = 0


def check(description: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"OK {description}")
        passed += 1
    else:
        print(f"FAIL {description}")
        failed += 1


def decision(*, status=DS.OPEN, readiness="", **extra) -> dict:
    fields = {
        DF.TITLE: "Blue View",
        DF.STATUS: status,
        DF.READINESS: readiness,
        DF.DOMAIN: DOMAIN.GENERAL,
    }
    fields.update(extra)
    return {"id": "recDecision", "fields": fields}


def confidence(score: float, missing=None) -> ConfidenceResult:
    return ConfidenceResult(score=score, missing=missing or [])


def stakeholder(role: str, position: str, name: str) -> dict:
    return {
        "id": f"stakeholder-{name}",
        "fields": {
            SF.ROLE: role,
            SF.POSITION: position,
            SF.POSITION_DETAILS: name,
        },
    }


owner = stakeholder(SR.DECIDER, SP.FOR, "אליהו")

result = orchestrate(
    decision(readiness=DR.NOT_READY),
    events=[{"id": "event-1", "fields": {}}],
    stakeholders=[owner],
    precomputed_confidence=confidence(0.9, ["מסמך תומך"]),
    require_feature_flag=False,
)
check("NOT_READY routes to BLOCKED before high confidence", result.phase == PHASE_BLOCKED)
check("NOT_READY assigns the decider when present", result.next_step.responsible == "אליהו")

pending = stakeholder(SR.ADVISOR, SP.UNKNOWN, "היועץ")
result = orchestrate(
    decision(readiness=DR.READY),
    events=[{"id": "event-1", "fields": {}}],
    stakeholders=[owner, pending],
    precomputed_confidence=confidence(0.95),
    require_feature_flag=False,
)
check("pending stakeholder blocks READY decision", result.phase == PHASE_BLOCKED)
check("pending stakeholder is named in blockers", any("היועץ" in item for item in result.blockers))

result = orchestrate(
    decision(),
    events=[{"id": "event-1", "fields": {}}],
    stakeholders=[owner],
    precomputed_confidence=confidence(0.59),
    require_feature_flag=False,
)
check("confidence below 60 percent routes to REVIEW", result.phase == PHASE_REVIEW)
check("low confidence awaits owner", result.awaiting_owner is True)

result = orchestrate(
    decision(readiness=DR.REVIEW),
    events=[{"id": "event-1", "fields": {}}],
    stakeholders=[owner],
    precomputed_confidence=confidence(0.7),
    require_feature_flag=False,
)
check("REVIEW readiness waits for readiness approval", result.phase == PHASE_REVIEW)

result = orchestrate(
    decision(readiness=DR.READY, **{DF.ESTIMATED_EXPOSURE: 500000}),
    events=[{"id": "event-1", "fields": {}}],
    stakeholders=[owner],
    precomputed_confidence=confidence(0.8),
    require_feature_flag=False,
)
check("READY or confidence at least 75 percent routes to AWAITING", result.phase == PHASE_AWAITING)
check("AWAITING card contains decision context", "500,000₪" in result.next_step.detail)

result = orchestrate(
    decision(),
    events=[],
    stakeholders=[owner],
    precomputed_confidence=confidence(0.0, ["מסמך תומך"]),
    require_feature_flag=False,
)
check("empty evidence remains COLLECTING", result.phase == PHASE_COLLECTING)

yes_result = orchestrate(
    decision(status=DS.DECIDED_YES),
    precomputed_confidence=confidence(0.0),
    require_feature_flag=False,
)
no_result = orchestrate(
    decision(status=DS.DECIDED_NO),
    precomputed_confidence=confidence(0.0),
    require_feature_flag=False,
)
cancelled_result = orchestrate(
    decision(status=DS.CANCELLED),
    precomputed_confidence=confidence(0.0),
    require_feature_flag=False,
)
check("DECIDED_YES routes to DECIDED", yes_result.phase == PHASE_DECIDED)
check("DECIDED_NO routes to DECIDED", no_result.phase == PHASE_DECIDED)
check("CANCELLED routes to CLOSED", cancelled_result.phase == PHASE_CLOSED)

card = format_orchestrator_card(result)
check("formatted card contains lifecycle and next-step labels", "מצב תהליך" in card and "צעד הבא" in card)

with patch("decision_orchestrator.orchestrate", side_effect=RuntimeError("boom")):
    safe_block = append_orchestrator_to_card(decision(), [], [])
check("append helper fails open with an empty string", safe_block == "")

# Integration contract: cmd_decision must route on the readiness calculated
# during this card render and must reuse the confidence result already computed.
stale_decision = decision(readiness=DR.NOT_READY)
current_confidence = confidence(0.8)
with (
    patch("cmd_decision._list_stakeholders", return_value=[owner]),
    patch("cmd_decision._list_decision_events", return_value=[]),
    patch("cmd_decision._latest_event", return_value=None),
    patch(
        "cmd_decision._format_confidence_block",
        return_value=("confidence block", current_confidence),
    ),
    patch(
        "cmd_decision._format_readiness_block",
        return_value=("readiness block", SimpleNamespace(status=DR.READY)),
    ),
    patch(
        "decision_orchestrator.append_orchestrator_to_card",
        return_value="\nORCHESTRATOR BLOCK",
    ) as append_mock,
):
    from cmd_decision import _format_decision_card

    integrated_card = _format_decision_card(stale_decision)

orchestrator_snapshot = append_mock.call_args.args[0]
check("decision card appends the orchestrator block", integrated_card.endswith("ORCHESTRATOR BLOCK"))
check(
    "decision card routes with freshly calculated readiness",
    orchestrator_snapshot["fields"][DF.READINESS] == DR.READY,
)
check(
    "decision card reuses precomputed confidence",
    append_mock.call_args.kwargs["precomputed_confidence"] is current_confidence,
)
check(
    "decision card does not mutate the fetched readiness",
    stale_decision["fields"][DF.READINESS] == DR.NOT_READY,
)

print(f"\nDecision Orchestrator: {passed}/{passed + failed} passed")
sys.exit(0 if failed == 0 else 1)
