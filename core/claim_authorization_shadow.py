"""TC7-B2: dual-signal shadow comparison between TC7-B1's ClaimCategory and
RP4's legacy regex-derived claim classification.

Observability only. Never mutates final_reply/safe_user_message, never
influences execution, ActionContract lifecycle, or reply ownership. Runs at
the same FEATURE_EVIDENCE_FINALIZER off/shadow/enforce gate RP4 already
uses -- reused, not a new flag -- and stays non-enforcing even when that
flag reports "enforce": B3 (not this module) will own any future
user-visible enforcement.

Dependency direction is one-way: this module consumes core.turn_evidence's
already-computed ShadowFinalizerComparison (RP4's legacy regex-vs-evidence
result) and core.claim_authorization's authorize_claim() -- it never gets
imported back into either of those modules. It never calls
_classify_response_claim(), never inspects final_text, never runs its own
regex, never inspects DispatcherOutcome/provider output, and never
recomputes a TurnEvidenceSummary -- the legacy claim and evidence status it
compares against are both already sitting in the ShadowFinalizerComparison
the caller passes in.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from core.claim_authorization import authorize_claim
from core.turn_evidence import ShadowFinalizerComparison


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaimAuthorizationShadowComparison:
    evidence_status: str
    lifecycle_state: str | None
    canonical_claim: str
    authorization_reason: str | None
    legacy_response_claim: str
    legacy_rp4_mismatch: bool
    divergent: bool
    divergence_code: str

    def safe_record(self) -> dict[str, str | bool | None]:
        """Structural enums/booleans/reason codes only -- no text/IDs/payload."""
        return asdict(self)

    @property
    def authorized(self) -> bool:
        """TC7-B3: True iff the response's claim is authorized by TC7-B1's
        evidence+lifecycle decision (authorize_claim()). Exact inverse of
        `divergent` -- exposed under this name so a caller records/consumes
        an explicit authorization verdict instead of re-deriving it from
        `divergent`'s shadow-comparison framing."""
        return not self.divergent


# ClaimCategory value -> compatible legacy ShadowFinalizerComparison.response_claim
# values. The two RP4-precedent exceptions (no_evidence+empty, narrow
# mixed+sent_for_approval) are conditional on legacy_comparison fields
# beyond the claim strings themselves, so they're applied separately in
# compare_claim_authorization_shadow() rather than folded into this table.
_COMPATIBLE_LEGACY_CLAIMS = {
    "neutral": {"neutral"},
    "success": {"success"},
    "failure": {"failure"},
    "unknown": {"unknown"},
    "pending": {"pending", "sent_for_approval"},
    "mixed": {"mixed"},
}


def compare_claim_authorization_shadow(
    legacy_comparison: ShadowFinalizerComparison,
    *,
    lifecycle_state: str | None = None,
) -> ClaimAuthorizationShadowComparison:
    """Compare TC7-B1's ClaimCategory against RP4's already-computed legacy claim.

    Never re-derives either signal: evidence_status and the legacy claim
    both come from legacy_comparison, already produced by
    core.turn_evidence.compare_shadow_final_status(). "legacy_rp4_mismatch"
    (RP4's own evidence-vs-text verdict) and "divergent" (this module's
    typed-vs-legacy verdict) are independent judgments over the same turn
    and must never be equated -- a lifecycle-aware ClaimCategory can agree
    with the legacy claim even when RP4 itself flagged a mismatch, and vice
    versa.
    """
    canonical_claim, reason = authorize_claim(legacy_comparison.evidence_status, lifecycle_state)
    claim_value = canonical_claim.value
    legacy_claim = legacy_comparison.response_claim

    compatible = legacy_claim in _COMPATIBLE_LEGACY_CLAIMS.get(claim_value, set())
    if not compatible and claim_value == "neutral" and legacy_claim == "empty":
        # RP4 precedent: empty final_text is neutral only with no evidence
        # at all -- deliberately not broadened to verified-read turns.
        compatible = legacy_comparison.evidence_status == "no_evidence"
    if not compatible and claim_value == "mixed" and legacy_claim == "sent_for_approval":
        # RP4 precedent (F52 PR6): "sent_for_approval" is a legitimate mixed
        # claim only when RP4's own comparison already found this turn's
        # mixed evidence+text combination non-mismatching -- delegates that
        # count-based proof to RP4 instead of re-deriving it here.
        compatible = (
            legacy_comparison.evidence_status == "mixed"
            and legacy_comparison.mismatch is False
        )

    return ClaimAuthorizationShadowComparison(
        evidence_status=legacy_comparison.evidence_status,
        lifecycle_state=lifecycle_state,
        canonical_claim=claim_value,
        authorization_reason=reason,
        legacy_response_claim=legacy_claim,
        legacy_rp4_mismatch=legacy_comparison.mismatch,
        divergent=not compatible,
        divergence_code="match" if compatible else "claim_category_mismatch",
    )


def observe_claim_authorization_shadow(
    legacy_comparison: ShadowFinalizerComparison | None,
    *,
    lifecycle_state: str | None,
    state: str,
) -> ClaimAuthorizationShadowComparison | None:
    """Record a safe TC7-B2 comparison; never mutates or enforces anything.

    B2 is shadow-only even when state=="enforce" -- that state name governs
    RP4/RP5's own future enforcement (owned elsewhere), not this module;
    a future B3 owns any TC7-B enforcement decision, not this function."""
    if state not in ("shadow", "enforce") or legacy_comparison is None:
        return None

    comparison = compare_claim_authorization_shadow(
        legacy_comparison, lifecycle_state=lifecycle_state,
    )
    log = logger.warning if comparison.divergent else logger.info
    log(
        "[ClaimAuthorizationShadow] state=%s evidence_status=%s lifecycle_state=%s "
        "canonical_claim=%s authorization_reason=%s legacy_response_claim=%s "
        "legacy_rp4_mismatch=%s divergent=%s code=%s",
        state,
        comparison.evidence_status,
        comparison.lifecycle_state if comparison.lifecycle_state is not None else "none",
        comparison.canonical_claim,
        comparison.authorization_reason if comparison.authorization_reason is not None else "-",
        comparison.legacy_response_claim,
        str(comparison.legacy_rp4_mismatch).lower(),
        str(comparison.divergent).lower(),
        comparison.divergence_code,
    )
    return comparison


if __name__ == "__main__":
    from core.turn_evidence import ShadowFinalizerComparison as _SFC

    _match = compare_claim_authorization_shadow(
        _SFC(evidence_status="verified_write_success", response_claim="success", mismatch=False, mismatch_code="match"),
    )
    assert _match.divergent is False and _match.divergence_code == "match"

    _lifecycle_only_divergence = compare_claim_authorization_shadow(
        _SFC(evidence_status="failure", response_claim="failure", mismatch=True, mismatch_code="status_claim_mismatch"),
        lifecycle_state="pending",
    )
    assert _lifecycle_only_divergence.legacy_rp4_mismatch is True
    assert _lifecycle_only_divergence.canonical_claim == "unknown"
    assert _lifecycle_only_divergence.divergent is True

    assert observe_claim_authorization_shadow(None, lifecycle_state=None, state="shadow") is None
    assert observe_claim_authorization_shadow(_match, lifecycle_state=None, state="off") is None
    print("core/claim_authorization_shadow.py self-check OK")
