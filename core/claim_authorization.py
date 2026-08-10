"""TC7-B1: pure claim-authorization decision logic.

Resolves the claim category a caller may assert for a turn from two
already-computed, already-authoritative signals: an optional WS2/TC6
lifecycle state and the TC7-A/RP4 evidence classification
(core.turn_evidence.TurnEvidenceSummary.classification()).

This module performs no execution, no verification, no dispatcher/provider
inspection, and no reply-owner selection or text classification -- it is a
pure projection over signals other layers have already produced.

It does NOT depend on core.message_contract.MessageState or MessageContract
at all. TC7-B's claim semantics are not MessageContract presentation
semantics: core.message_contract._state_from_lifecycle() currently maps
both "verified_write_success" and "verified_read_only" to the same
SUCCESS-equivalent presentation state, which TC7-B's claim policy
deliberately disagrees with (a verified read must never authorize a
mutation-success claim). Coupling to that enum would either inherit the
conflict or require a documented override living outside the enum's own
module -- a local, independently-owned vocabulary (ClaimCategory) avoids
that coupling entirely. This module neither imports nor modifies
core.message_contract in any way.

All inputs are treated as canonical, exact-match typed strings, not
free-form or user-authored text: lifecycle_state and evidence_status come
from other structural layers (WS2/TC6, TurnEvidenceSummary.classification()),
never from raw provider/dispatcher output or reply prose. No case-folding or
whitespace-stripping is performed -- a malformed or non-canonical signal
(e.g. " COMPLETED ", "Completed") is treated as an authority failure and
fails closed rather than being coerced into a valid value.
"""

from __future__ import annotations

from enum import Enum


class ClaimCategory(str, Enum):
    NEUTRAL = "neutral"
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"
    PENDING = "pending"
    MIXED = "mixed"


# core.turn_evidence.TurnEvidenceSummary.classification() vocabulary --
# exact-match only, never normalized.
_EVIDENCE_STATES = frozenset({
    "no_evidence",
    "verified_read_only",
    "verified_write_success",
    "failure",
    "outcome_unknown",
    "approval_pending",
    "unverified_effect",
    "mixed",
    "mixed_with_unknown",
})

# Lifecycle states a contract may report (core.lifecycle_projection's
# vocabulary, plus the "cancelled"/"executed" aliases used elsewhere in the
# WS2/TC6 family). Not imported -- treated as an opaque, exact-match string
# contract. lifecycle_state=None means "no lifecycle available" (e.g. RP4
# agent-loop surfaces that only ever compute TurnEvidenceSummary), which is
# a distinct, valid input -- not a failure.
_SUCCESS_ELIGIBLE_LIFECYCLE = frozenset({"completed", "executed"})
_TERMINAL_NON_SUCCESS_LIFECYCLE = frozenset({"rejected", "cancelled"})
_FAILED_LIFECYCLE = frozenset({"failed"})
_IN_PROGRESS_LIFECYCLE = frozenset({"pending", "approved", "executing"})
_UNRESOLVED_LIFECYCLE = frozenset({"missing", "expired"})
# TC7-B1.1: core.lifecycle_projection.build_action_lifecycle_result() emits
# lifecycle_state="outcome_unknown" for an ActionContract whose durable
# status is "outcome_unknown" -- a distinct, valid WS2/TC6 lifecycle value,
# not a malformed/unsupported one. It carries no positive signal either way
# (neither "execution didn't happen" nor "execution definitely failed"), so
# it wins outright over evidence, same as the other lifecycle-authority
# branches, and always resolves to UNKNOWN -- never SUCCESS.
_OUTCOME_UNKNOWN_LIFECYCLE = frozenset({"outcome_unknown"})
_KNOWN_LIFECYCLE_STATES = (
    _SUCCESS_ELIGIBLE_LIFECYCLE
    | _TERMINAL_NON_SUCCESS_LIFECYCLE
    | _FAILED_LIFECYCLE
    | _IN_PROGRESS_LIFECYCLE
    | _UNRESOLVED_LIFECYCLE
    | _OUTCOME_UNKNOWN_LIFECYCLE
)

# Evidence-only mapping: used verbatim when lifecycle_state is None, and
# reused (with two explicit overrides applied by the caller below) as the
# base table once a completed/executed lifecycle is confirmed. Only
# verified_write_success may ever resolve to SUCCESS.
_EVIDENCE_ONLY = {
    "no_evidence": (ClaimCategory.NEUTRAL, None),
    "verified_read_only": (ClaimCategory.NEUTRAL, "verified_read_only"),
    "verified_write_success": (ClaimCategory.SUCCESS, None),
    "failure": (ClaimCategory.FAILURE, "evidence_failure"),
    "outcome_unknown": (ClaimCategory.UNKNOWN, "evidence_outcome_unknown"),
    "approval_pending": (ClaimCategory.PENDING, "evidence_approval_pending"),
    "unverified_effect": (ClaimCategory.UNKNOWN, "evidence_unverified_effect"),
    "mixed": (ClaimCategory.MIXED, "evidence_mixed"),
    "mixed_with_unknown": (ClaimCategory.MIXED, "evidence_mixed_with_unknown"),
}

# Evidence states that describe an actual observed execution outcome
# (success, uncertainty, or effects). Asserting one of these while the
# lifecycle says execution has not yet completed is a genuine contradiction
# between two authority signals -- it must fail closed with an explicit
# reason, never be silently coerced into the in-progress baseline.
_CONTRADICTS_INCOMPLETE_LIFECYCLE = {
    "failure": "conflict_incomplete_lifecycle_with_failure_evidence",
    "outcome_unknown": "conflict_incomplete_lifecycle_with_uncertain_evidence",
    "unverified_effect": "conflict_incomplete_lifecycle_with_uncertain_evidence",
    "verified_write_success": "conflict_incomplete_lifecycle_with_completed_evidence",
    "verified_read_only": "conflict_incomplete_lifecycle_with_completed_evidence",
    "mixed": "conflict_incomplete_lifecycle_with_completed_evidence",
    "mixed_with_unknown": "conflict_incomplete_lifecycle_with_completed_evidence",
}


def authorize_claim(
    evidence_status: str,
    lifecycle_state: str | None = None,
) -> tuple[ClaimCategory, str | None]:
    """Resolve the ClaimCategory a reply may assert for this turn.

    lifecycle_state is an optional guard: when absent, the evidence
    classification alone determines the category (agent-loop surfaces
    that never compute a lifecycle result). When present, it must be
    compatible with the evidence -- a contradictory combination fails
    closed with a deterministic reason code rather than silently trusting
    one signal over the other.

    Fails closed on any unsupported, malformed, or non-canonical input:
    never returns ClaimCategory.SUCCESS unless evidence_status is exactly
    "verified_write_success" AND (lifecycle_state is None or is exactly
    "completed"/"executed"). Never raises.
    """
    if lifecycle_state is None:
        if evidence_status not in _EVIDENCE_STATES:
            return ClaimCategory.UNKNOWN, "unsupported_evidence_status"
        return _EVIDENCE_ONLY[evidence_status]

    if lifecycle_state not in _KNOWN_LIFECYCLE_STATES:
        return ClaimCategory.UNKNOWN, "unsupported_lifecycle_state"

    # Terminal lifecycle authority wins outright; evidence is never
    # consulted, matching the "terminal lifecycle discards evidence"
    # precedent used elsewhere in the WS2/TC6 family. Cancellation/rejection
    # means execution did not proceed -- that is not the same claim as
    # "execution was attempted and failed", so it resolves to NEUTRAL, not
    # FAILURE. Only an actually-failed lifecycle authorizes a FAILURE claim.
    if lifecycle_state in _TERMINAL_NON_SUCCESS_LIFECYCLE:
        return ClaimCategory.NEUTRAL, "lifecycle_terminal_non_success"

    if lifecycle_state in _FAILED_LIFECYCLE:
        return ClaimCategory.FAILURE, "lifecycle_failed"

    if lifecycle_state in _UNRESOLVED_LIFECYCLE:
        return ClaimCategory.UNKNOWN, "lifecycle_unresolved"

    if lifecycle_state in _OUTCOME_UNKNOWN_LIFECYCLE:
        return ClaimCategory.UNKNOWN, "lifecycle_outcome_unknown"

    if evidence_status not in _EVIDENCE_STATES:
        return ClaimCategory.UNKNOWN, "unsupported_evidence_status"

    if lifecycle_state in _IN_PROGRESS_LIFECYCLE:
        conflict_reason = _CONTRADICTS_INCOMPLETE_LIFECYCLE.get(evidence_status)
        if conflict_reason is not None:
            return ClaimCategory.UNKNOWN, conflict_reason
        # Only no_evidence/approval_pending remain -- both compatible with
        # "execution has not completed yet".
        reason = "lifecycle_pending" if lifecycle_state == "pending" else "lifecycle_in_progress"
        return ClaimCategory.PENDING, reason

    # lifecycle_state in _SUCCESS_ELIGIBLE_LIFECYCLE (completed/executed).
    if evidence_status == "approval_pending":
        return ClaimCategory.UNKNOWN, "conflict_completed_with_approval_pending"
    if evidence_status == "no_evidence":
        return ClaimCategory.UNKNOWN, "no_evidence"
    return _EVIDENCE_ONLY[evidence_status]


if __name__ == "__main__":
    assert authorize_claim("verified_write_success", "completed") == (ClaimCategory.SUCCESS, None)
    assert authorize_claim("verified_write_success") == (ClaimCategory.SUCCESS, None)
    assert authorize_claim("verified_read_only", "completed")[0] == ClaimCategory.NEUTRAL
    assert authorize_claim("verified_write_success", "rejected")[0] == ClaimCategory.NEUTRAL
    assert authorize_claim("failure", "cancelled")[0] == ClaimCategory.NEUTRAL
    assert authorize_claim("failure", "failed")[0] == ClaimCategory.FAILURE
    assert authorize_claim("verified_write_success", "outcome_unknown") == (ClaimCategory.UNKNOWN, "lifecycle_outcome_unknown")
    assert authorize_claim("verified_write_success", "pending")[0] != ClaimCategory.SUCCESS
    assert authorize_claim("failure", "pending")[0] != ClaimCategory.PENDING
    assert authorize_claim(" VERIFIED_WRITE_SUCCESS ", "completed")[0] != ClaimCategory.SUCCESS
    assert authorize_claim("verified_write_success", " COMPLETED ")[0] != ClaimCategory.SUCCESS
    assert authorize_claim(None, None)[0] == ClaimCategory.UNKNOWN
    print("core/claim_authorization.py self-check OK")
