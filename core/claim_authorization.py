"""TC7-B1: pure claim-authorization decision logic.

Resolves the MessageState a caller may claim for a turn from two
already-computed, already-authoritative signals: the WS2/TC6 lifecycle
state and the TC7-A/RP4 evidence classification
(core.turn_evidence.TurnEvidenceSummary.classification()).

This module performs no execution, no verification, no dispatcher/provider
inspection, and no reply-owner selection or text classification -- it is a
pure projection over signals other layers have already produced. It does
not import from core.message_contract or core.lifecycle_message_adapter
beyond the public MessageState type: those modules' internal helpers
(_state_from_lifecycle, _lifecycle_projection, _VERIFIED_SUCCESS_EVIDENCE,
etc.) are owned by the F52/TC9 track and are deliberately not depended on.

Known latent conflict (documented, not fixed here): core.message_contract's
own _state_from_lifecycle() currently maps both "verified_write_success"
and "verified_read_only" to MessageState.SUCCESS, and
_VERIFIED_SUCCESS_EVIDENCE contains both values, so MessageContract's own
__post_init__ currently permits SUCCESS with verified_read_only evidence.
TC7-B's claim-authorization policy is stricter: verified_read_only never
authorizes a mutation-success claim, so it resolves to MessageState.NEUTRAL
here regardless of what core.message_contract would independently allow.
This is a real conflict between the two tracks' semantics -- it belongs to
the F52/TC9 owner to reconcile, not to this module.
"""

from __future__ import annotations

from core.message_contract import MessageState

# core.turn_evidence.TurnEvidenceSummary.classification() vocabulary.
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
# WS2/TC6 family). Not imported -- treated as an opaque string contract.
_SUCCESS_ELIGIBLE_LIFECYCLE = frozenset({"completed", "executed"})
_TERMINAL_NON_SUCCESS_LIFECYCLE = frozenset({"rejected", "cancelled"})
_FAILED_LIFECYCLE = frozenset({"failed"})
_PENDING_LIFECYCLE = frozenset({"pending"})
_IN_PROGRESS_LIFECYCLE = frozenset({"approved", "executing"})
_UNRESOLVED_LIFECYCLE = frozenset({"missing", "expired"})

# Evidence status -> (claimable MessageState, reason code) once a contract
# has reached a success-eligible lifecycle state. Only verified_write_success
# may resolve to SUCCESS. approval_pending is not explicitly enumerated by
# name in the originating planning-gate mapping table but is part of the
# canonical 9-state vocabulary and must resolve deterministically; it is
# mapped to MessageState.APPROVAL_PENDING, consistent with the state's own
# name and with RP4's existing compare_shadow_final_status() expected-claim
# table.
_EVIDENCE_TO_CLAIM = {
    "verified_write_success": (MessageState.SUCCESS, None),
    "verified_read_only": (MessageState.NEUTRAL, "verified_read_only"),
    "failure": (MessageState.FAILURE, "evidence_failure"),
    "outcome_unknown": (MessageState.OUTCOME_UNKNOWN, "evidence_outcome_unknown"),
    "unverified_effect": (MessageState.UNVERIFIED_EFFECT, "evidence_unverified_effect"),
    "mixed": (MessageState.MIXED, "evidence_mixed"),
    "mixed_with_unknown": (MessageState.MIXED_WITH_UNKNOWN, "evidence_mixed_with_unknown"),
    "no_evidence": (MessageState.OUTCOME_UNKNOWN, "no_evidence"),
    "approval_pending": (MessageState.APPROVAL_PENDING, "evidence_approval_pending"),
}


def authorize_claim(
    evidence_status: str | None,
    lifecycle_state: str | None,
) -> tuple[MessageState, str | None]:
    """Resolve the MessageState a reply may claim for this turn.

    Fails closed on any unsupported, malformed, or missing input: never
    returns MessageState.SUCCESS unless lifecycle_state is success-eligible
    ("completed"/"executed") AND evidence_status is exactly
    "verified_write_success". Never raises.
    """
    lifecycle = lifecycle_state.strip().lower() if isinstance(lifecycle_state, str) else ""

    if lifecycle in _TERMINAL_NON_SUCCESS_LIFECYCLE:
        return MessageState.CANCELLED, "lifecycle_terminal_non_success"

    if lifecycle in _FAILED_LIFECYCLE:
        return MessageState.FAILURE, "lifecycle_failed"

    if lifecycle in _PENDING_LIFECYCLE:
        return MessageState.APPROVAL_PENDING, "lifecycle_pending"

    if lifecycle in _IN_PROGRESS_LIFECYCLE:
        # Matches core.message_contract._state_from_lifecycle()'s own
        # approved/executing -> APPROVED_PROCESSING mapping exactly (no
        # conflict with TC7-B policy here, unlike the read-only case above --
        # reuse the canonical value rather than inventing a divergent one).
        return MessageState.APPROVED_PROCESSING, "lifecycle_not_terminal"

    if lifecycle in _UNRESOLVED_LIFECYCLE:
        return MessageState.OUTCOME_UNKNOWN, "lifecycle_unresolved"

    if lifecycle not in _SUCCESS_ELIGIBLE_LIFECYCLE:
        return MessageState.OUTCOME_UNKNOWN, "unsupported_lifecycle_state"

    evidence = evidence_status.strip().lower() if isinstance(evidence_status, str) else "no_evidence"
    if evidence not in _EVIDENCE_STATES:
        return MessageState.OUTCOME_UNKNOWN, "unsupported_evidence_status"

    return _EVIDENCE_TO_CLAIM[evidence]


if __name__ == "__main__":
    assert authorize_claim("verified_write_success", "completed") == (MessageState.SUCCESS, None)
    assert authorize_claim("verified_read_only", "completed") == (MessageState.NEUTRAL, "verified_read_only")
    assert authorize_claim("verified_write_success", "rejected")[0] == MessageState.CANCELLED
    assert authorize_claim("verified_write_success", "pending")[0] != MessageState.SUCCESS
    assert authorize_claim(None, None)[0] == MessageState.OUTCOME_UNKNOWN
    print("core/claim_authorization.py self-check OK")
