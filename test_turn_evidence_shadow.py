"""PR-RP4 tests for evidence accumulation and non-mutating shadow comparison."""

from __future__ import annotations

import logging

import pytest

from core.dispatcher_outcome import DispatcherOutcome
from core.turn_evidence import (
    TurnEvidenceSummary,
    compare_shadow_final_status,
    observe_shadow_finalizer,
)
from feature_flags import get_evidence_finalizer_state


def test_empty_response_without_evidence_is_not_shadow_success():
    summary = TurnEvidenceSummary()

    comparison = compare_shadow_final_status("", summary)

    assert summary.classification() == "no_evidence"
    assert comparison.evidence_status == "no_evidence"
    assert comparison.response_claim == "empty"
    assert "success" not in comparison.evidence_status


def test_generic_success_fallback_without_evidence_is_shadow_mismatch():
    comparison = compare_shadow_final_status(
        "✅ פעולה הושלמה.",
        TurnEvidenceSummary(),
    )

    assert comparison.evidence_status == "no_evidence"
    assert comparison.response_claim == "success"
    assert comparison.mismatch is True
    assert comparison.mismatch_code == "status_claim_mismatch"


def test_verified_write_produces_shadow_success_classification():
    summary = TurnEvidenceSummary()
    summary.record_verification("ok", read_only=False)

    assert summary.classification() == "verified_write_success"
    assert summary.verified_writes == 1


def test_failed_write_produces_shadow_failure_classification():
    summary = TurnEvidenceSummary()
    summary.record_verification("failed", read_only=False)

    assert summary.classification() == "failure"
    assert summary.failed_calls == 1
    assert summary.verified_writes == 0


def test_outcome_unknown_is_distinct_and_ignores_display_text():
    summary = TurnEvidenceSummary()
    summary.record_dispatcher_outcome(
        DispatcherOutcome(
            result="outcome_unknown",
            user_message="✅ completed recSECRET123456789 payload=private",
            external_id="recSECRET123456789",
            raw_response={"token": "secret-token"},
        ),
        read_only=False,
    )

    assert summary.classification() == "outcome_unknown"
    assert summary.outcome_unknown == 1
    assert summary.verified_writes == 0
    assert summary.failed_calls == 0


def test_approval_queued_is_pending_not_executed():
    summary = TurnEvidenceSummary()
    summary.record_approval_pending()

    assert summary.classification() == "approval_pending"
    assert summary.approvals_pending == 1
    assert summary.verified_writes == 0


def test_mixed_success_and_failure_is_not_collapsed_to_success():
    summary = TurnEvidenceSummary()
    summary.record_verification("ok", read_only=False)
    summary.record_verification("failed", read_only=False)

    assert summary.classification() == "mixed"
    assert summary.verified_writes == 1
    assert summary.failed_calls == 1


def test_read_only_evidence_cannot_support_mutation_success():
    summary = TurnEvidenceSummary()
    summary.record_verification("ok", read_only=True)

    assert summary.classification() == "verified_read_only"
    assert summary.verified_reads == 1
    assert summary.verified_writes == 0


@pytest.mark.parametrize("state", ["off", "shadow", "enforce"])
def test_shadow_observer_never_alters_final_user_text(state: str):
    final_text = "✅ הטקסט הקיים נשאר בדיוק כפי שהוא."
    summary = TurnEvidenceSummary(verified_writes=1)

    returned, comparison = observe_shadow_finalizer(final_text, summary, state=state)

    assert returned == final_text
    if state == "off":
        assert comparison is None
    else:
        assert comparison is not None


def test_shadow_logs_and_records_never_leak_sensitive_or_internal_values(
    caplog: pytest.LogCaptureFixture,
):
    secret = "sk-secret-RP4-marker"
    record_id = "recRP4SECRET12345"
    internal_tool = "airtable_update"
    payload = "customer_payload_private"
    final_text = f"✅ {internal_tool} {record_id} token={secret} payload={payload}"
    summary = TurnEvidenceSummary(failed_calls=1, unverified_effects=1)

    with caplog.at_level(logging.INFO, logger="core.turn_evidence"):
        returned, comparison = observe_shadow_finalizer(
            final_text,
            summary,
            state="shadow",
        )

    assert returned == final_text
    assert comparison is not None
    safe_blob = repr({
        "comparison": comparison.safe_record(),
        "evidence": summary.safe_record(),
    })
    combined = caplog.text + safe_blob
    for forbidden in (secret, record_id, internal_tool, payload):
        assert forbidden not in combined


def test_evidence_finalizer_flag_defaults_off_and_accepts_rollout_states(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("FEATURE_EVIDENCE_FINALIZER", raising=False)
    assert get_evidence_finalizer_state() == "off"

    for state in ("off", "shadow", "enforce"):
        monkeypatch.setenv("FEATURE_EVIDENCE_FINALIZER", state)
        assert get_evidence_finalizer_state() == state

    monkeypatch.setenv("FEATURE_EVIDENCE_FINALIZER", "unexpected")
    assert get_evidence_finalizer_state() == "off"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
