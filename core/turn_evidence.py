"""Per-turn evidence accounting and a non-mutating shadow finalizer.

Execution truth enters through structured verification/dispatcher outcomes only.
Assistant text is inspected solely to compare its claim shape with that truth;
it never increments evidence counters or changes the returned response.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass

from core.dispatcher_outcome import DispatcherOutcome


logger = logging.getLogger(__name__)


@dataclass
class TurnEvidenceSummary:
    verified_reads: int = 0
    verified_writes: int = 0
    failed_calls: int = 0
    outcome_unknown: int = 0
    approvals_pending: int = 0
    unverified_effects: int = 0

    def record_verification(self, status: str, *, read_only: bool) -> None:
        """Consume an existing verify_execution status, never display text."""
        if status == "ok":
            if read_only:
                self.verified_reads += 1
            else:
                self.verified_writes += 1
        elif status == "failed":
            self.failed_calls += 1
        else:
            # Warnings and unknown verifier statuses cannot support success.
            self.unverified_effects += 1

    def record_dispatcher_outcome(
        self,
        outcome: DispatcherOutcome,
        *,
        read_only: bool,
    ) -> None:
        """Consume the structured dispatcher contract without reading user_message."""
        if outcome.is_completed():
            self.record_verification("ok", read_only=read_only)
        elif outcome.is_failed():
            self.failed_calls += 1
        else:
            self.outcome_unknown += 1

    def record_approval_pending(self) -> None:
        self.approvals_pending += 1

    def record_unverified_effect(self) -> None:
        self.unverified_effects += 1

    def classification(self) -> str:
        """Return a stable evidence-derived status; never a user-facing message."""
        total = sum(asdict(self).values())
        if total == 0:
            return "no_evidence"

        verified = self.verified_reads + self.verified_writes
        if self.outcome_unknown:
            if total == self.outcome_unknown:
                return "outcome_unknown"
            return "mixed_with_unknown"

        non_success = self.failed_calls + self.approvals_pending + self.unverified_effects
        if verified and non_success:
            return "mixed"
        if self.failed_calls and (self.approvals_pending or self.unverified_effects):
            return "mixed"
        if self.approvals_pending and self.unverified_effects:
            return "mixed"
        if self.failed_calls:
            return "failure"
        if self.unverified_effects:
            return "unverified_effect"
        if self.approvals_pending:
            return "approval_pending"
        if self.verified_writes:
            return "verified_write_success"
        return "verified_read_only"

    def safe_record(self) -> dict[str, int | str]:
        """Return counts/classification only: no IDs, payloads, tools, or secrets."""
        return {"classification": self.classification(), **asdict(self)}


@dataclass(frozen=True)
class ShadowFinalizerComparison:
    evidence_status: str
    response_claim: str
    mismatch: bool
    mismatch_code: str

    def safe_record(self) -> dict[str, str | bool]:
        return asdict(self)


_MUTATION_SUCCESS = re.compile(
    r"(?:✅|\b(?:done|completed|created|updated|sent|saved)\b|"
    r"בוצע|הושלם|נוצר|עודכן|נשלח|נשמר|הוספתי|עדכנתי|יצרתי|שלחתי|שמרתי)",
    re.IGNORECASE,
)
_FAILURE = re.compile(r"(?:❌|\b(?:failed|failure|error)\b|נכשל|שגיאה|לא הושלמ)", re.IGNORECASE)
_PENDING = re.compile(r"(?:⏳|\bpending\b|ממתינ|ממתין לאישור|ממתינה לאישור)", re.IGNORECASE)
_UNKNOWN = re.compile(r"(?:\boutcome[_ -]?unknown\b|לא ידוע|לא ניתן לאמת|דורש בדיקה)", re.IGNORECASE)


def _classify_response_claim(final_text: str) -> str:
    """Classify claim shape for comparison only; this is never execution truth."""
    if not final_text or not final_text.strip():
        return "empty"
    claims = {
        "success": bool(_MUTATION_SUCCESS.search(final_text)),
        "failure": bool(_FAILURE.search(final_text)),
        "pending": bool(_PENDING.search(final_text)),
        "unknown": bool(_UNKNOWN.search(final_text)),
    }
    present = [name for name, found in claims.items() if found]
    if len(present) > 1:
        return "mixed"
    return present[0] if present else "neutral"


def compare_shadow_final_status(
    final_text: str,
    evidence: TurnEvidenceSummary,
) -> ShadowFinalizerComparison:
    status = evidence.classification()
    claim = _classify_response_claim(final_text)
    expected_claim = {
        "no_evidence": "neutral",
        "verified_read_only": "neutral",
        "verified_write_success": "success",
        "failure": "failure",
        "outcome_unknown": "unknown",
        "approval_pending": "pending",
        "unverified_effect": "unknown",
        "mixed": "mixed",
        "mixed_with_unknown": "mixed",
    }[status]

    # Empty/no-evidence is neutral and explicitly not a shadow success.
    compatible = claim == expected_claim or (
        status == "no_evidence" and claim in ("empty", "neutral")
    )
    mismatch = not compatible
    return ShadowFinalizerComparison(
        evidence_status=status,
        response_claim=claim,
        mismatch=mismatch,
        mismatch_code="status_claim_mismatch" if mismatch else "match",
    )


def observe_shadow_finalizer(
    final_text: str,
    evidence: TurnEvidenceSummary,
    *,
    state: str,
) -> tuple[str, ShadowFinalizerComparison | None]:
    """Record a safe comparison and always return user text unchanged in RP4."""
    if state not in ("shadow", "enforce"):
        return final_text, None

    comparison = compare_shadow_final_status(final_text, evidence)
    log = logger.warning if comparison.mismatch else logger.info
    log(
        "[EvidenceFinalizerShadow] state=%s evidence_status=%s response_claim=%s "
        "mismatch=%s code=%s counts=%s",
        state,
        comparison.evidence_status,
        comparison.response_claim,
        str(comparison.mismatch).lower(),
        comparison.mismatch_code,
        evidence.safe_record(),
    )
    # RP4 invariant: no footer, replacement, fallback change, or other mutation.
    return final_text, comparison
