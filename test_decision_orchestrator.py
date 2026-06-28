#!/usr/bin/env python3
"""Regression tests for Decision Hub Stage 6 lifecycle orchestration."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from airtable_schema import (
    DecisionDomain as Domain,
    DecisionFields as DF,
    DecisionReadiness as Readiness,
    DecisionStakeholderFields as SF,
    DecisionStakeholderPosition as StakeholderPosition,
    DecisionStakeholderRole as StakeholderRole,
    DecisionStatus,
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


def decision(status=DecisionStatus.OPEN, readiness="", **extra) -> dict:
    fields = {
        DF.TITLE: "Blue View",
        DF.STATUS: status,
        DF.READINESS: readiness,
        DF.DOMAIN: Domain.GENERAL,
    }
    fields.update(extra)
    return {"id": "recDecision", "fields": fields}


def confidence(score: float, missing=None) -> ConfidenceResult:
    return ConfidenceResult(score=score, missing=list(missing or []))


def stakeholder(role: str, position: str, name: str) -> dict:
    return {
        "id": f"stakeholder-{name}",
        "fields": {
            SF.ROLE: role,
            SF.POSITION: position,
            SF.POSITION_DETAILS: name,
        },
    }


OWNER = stakeholder(StakeholderRole.DECIDER, StakeholderPosition.FOR, "אליהו")
EVENTS = [{"id": "event-1", "fields": {}}]


class OrchestratorRoutingTests(unittest.TestCase):
    def route(self, record, score, events=None, stakeholders=None, missing=None):
        return orchestrate(
            record,
            EVENTS if events is None else events,
            [OWNER] if stakeholders is None else stakeholders,
            precomputed_confidence=confidence(score, missing),
            require_feature_flag=False,
        )

    def test_not_ready_blocks_before_high_confidence(self):
        result = self.route(
            decision(readiness=Readiness.NOT_READY),
            0.95,
            missing=["מסמך תומך"],
        )
        self.assertEqual(PHASE_BLOCKED, result.phase)
        self.assertEqual("אליהו", result.next_step.responsible)

    def test_pending_stakeholder_blocks_ready_decision(self):
        pending = stakeholder(
            StakeholderRole.ADVISOR,
            StakeholderPosition.UNKNOWN,
            "היועץ",
        )
        result = self.route(
            decision(readiness=Readiness.READY),
            0.95,
            stakeholders=[OWNER, pending],
        )
        self.assertEqual(PHASE_BLOCKED, result.phase)
        self.assertIn("היועץ", result.blockers[0])

    def test_low_confidence_requires_review(self):
        result = self.route(decision(), 0.59)
        self.assertEqual(PHASE_REVIEW, result.phase)
        self.assertTrue(result.awaiting_owner)

    def test_review_readiness_waits_for_owner(self):
        result = self.route(decision(readiness=Readiness.REVIEW), 0.70)
        self.assertEqual(PHASE_REVIEW, result.phase)
        self.assertEqual("ממתין לאישור מוכנות", result.current_state)

    def test_ready_or_high_confidence_awaits_decision(self):
        result = self.route(
            decision(
                readiness=Readiness.READY,
                **{DF.ESTIMATED_EXPOSURE: 500000},
            ),
            0.80,
        )
        self.assertEqual(PHASE_AWAITING, result.phase)
        self.assertIn("500,000₪", result.next_step.detail)

    def test_no_events_remains_collecting(self):
        result = self.route(
            decision(),
            0.0,
            events=[],
            missing=["מסמך תומך"],
        )
        self.assertEqual(PHASE_COLLECTING, result.phase)

    def test_decided_and_cancelled_are_terminal(self):
        yes = self.route(decision(status=DecisionStatus.DECIDED_YES), 0.0)
        no = self.route(decision(status=DecisionStatus.DECIDED_NO), 0.0)
        cancelled = self.route(decision(status=DecisionStatus.CANCELLED), 0.0)
        self.assertEqual(PHASE_DECIDED, yes.phase)
        self.assertEqual(PHASE_DECIDED, no.phase)
        self.assertEqual(PHASE_CLOSED, cancelled.phase)


class OrchestratorContractTests(unittest.TestCase):
    def test_precomputed_confidence_skips_stage2_recalculation(self):
        with patch("decision_confidence.calc_confidence") as calc:
            result = orchestrate(
                decision(),
                [],
                [],
                precomputed_confidence=confidence(0.8),
                require_feature_flag=False,
            )
        calc.assert_not_called()
        self.assertEqual(0.8, result.confidence_score)

    def test_fallback_confidence_is_deterministic(self):
        with patch(
            "decision_confidence.calc_confidence",
            return_value=confidence(0.6),
        ) as calc:
            orchestrate(
                decision(),
                EVENTS,
                [],
                require_feature_flag=False,
            )
        calc.assert_called_once_with(EVENTS, conflicts=[], domain=Domain.GENERAL)

    def test_append_helper_fails_open(self):
        with patch(
            "decision_orchestrator.orchestrate",
            side_effect=RuntimeError("boom"),
        ):
            self.assertEqual("", append_orchestrator_to_card(decision(), [], []))

    def test_confidence_failure_omits_orchestrator_block(self):
        with (
            patch("decision_orchestrator._feature_enabled", return_value=True),
            patch(
                "decision_confidence.calc_confidence",
                side_effect=RuntimeError("confidence unavailable"),
            ),
        ):
            self.assertEqual(
                "",
                append_orchestrator_to_card(decision(), EVENTS, []),
            )

    def test_formatter_contains_required_sections(self):
        result = orchestrate(
            decision(),
            [],
            [],
            precomputed_confidence=confidence(0.0),
            require_feature_flag=False,
        )
        card = format_orchestrator_card(result)
        self.assertIn("מצב תהליך", card)
        self.assertIn("צעד הבא", card)

    def test_cmd_decision_uses_current_readiness_and_existing_confidence(self):
        stale_record = decision(readiness=Readiness.NOT_READY)
        current_confidence = confidence(0.8)

        with (
            patch("cmd_decision._list_stakeholders", return_value=[OWNER]),
            patch("cmd_decision._list_decision_events", return_value=[]),
            patch("cmd_decision._latest_event", return_value=None),
            patch(
                "cmd_decision._format_confidence_block",
                return_value=("confidence block", current_confidence),
            ),
            patch(
                "cmd_decision._format_readiness_block",
                return_value=(
                    "readiness block",
                    SimpleNamespace(status=Readiness.READY),
                ),
            ),
            patch(
                "decision_orchestrator.append_orchestrator_to_card",
                return_value="\nORCHESTRATOR BLOCK",
            ) as append,
        ):
            from cmd_decision import _format_decision_card

            card = _format_decision_card(stale_record)

        snapshot = append.call_args.args[0]
        self.assertTrue(card.endswith("ORCHESTRATOR BLOCK"))
        self.assertEqual(Readiness.READY, snapshot["fields"][DF.READINESS])
        self.assertIs(
            current_confidence,
            append.call_args.kwargs["precomputed_confidence"],
        )
        self.assertEqual(
            Readiness.NOT_READY,
            stale_record["fields"][DF.READINESS],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
