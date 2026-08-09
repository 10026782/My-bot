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
from core.router.ownership_contracts import EvidenceResult


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


# ══════════════════════════════════════════════════
# TC7-B — RP4/RP5 shadow projection of TC7-A EvidenceResult
# ══════════════════════════════════════════════════
#
# TC7-A's EvidenceResult (core/evidence_projection.py) is the sole execution-
# evidence authority for approval-gated Gateway executions. This function is
# a thin, one-way, read-only projection of that already-correlated result
# into RP4/RP5's own aggregate shape -- it never re-derives evidence from a
# raw DispatcherOutcome a second time, never inspects user-facing text, and
# never widens what counts as "verified" beyond what TC7-A itself decided.
def project_evidence_result(evidence: EvidenceResult) -> TurnEvidenceSummary:
    """Project one TC7-A EvidenceResult into a fresh, single-component summary.

    Always returns a brand-new TurnEvidenceSummary scoped to exactly the one
    contract resolution this EvidenceResult came from -- callers must never
    reuse or accumulate this across turns or contracts (mirrors
    ActionGateway.evidence_for_contract()'s own exact-contract-only
    guarantee, never "latest for user"). A `result == "success"` without
    `verified == True` is treated as an anomaly -- TC7-A's own
    build_evidence_result_from_outcome() never constructs that combination --
    and falls closed to unverified_effect rather than being silently
    accepted as a verified write.
    """
    summary = TurnEvidenceSummary()
    if evidence.outcome_unknown or evidence.result == "outcome_unknown":
        summary.outcome_unknown += 1
    elif evidence.result == "success" and evidence.verified:
        summary.verified_writes += 1
    elif evidence.result == "failed":
        summary.failed_calls += 1
    else:
        # Anomalous/unrecognized shape (e.g. "success" without verified=True)
        # -- never manufacture success from something TC7-A didn't verify.
        summary.record_unverified_effect()
    return summary


@dataclass(frozen=True)
class ShadowFinalizerComparison:
    evidence_status: str
    response_claim: str
    mismatch: bool
    mismatch_code: str

    def safe_record(self) -> dict[str, str | bool]:
        return asdict(self)


# BUG-125 (RP5 shadow evidence): a bare ✅ used to be sufficient on its own to
# classify a reply as a "success" claim — but a checkmark is often purely
# decorative (a factual/arithmetic answer like "25 ✅", or "נכון ✅") and
# carries no business-action claim at all. Removed as a standalone trigger;
# success now requires an actual completion/mutation verb or phrase to be
# present (✅ next to one of those still matches immediately, no separate
# co-occurrence check needed — the verb alone is sufficient and ✅ next to it
# doesn't hurt).
#
# Hebrew verbs ending in a final-form letter (ם/ן/ך/ף/ץ) change to the
# regular form once a suffix follows (e.g. "הושלם" -> "הושלמה"/"הושלמו",
# "עודכן" -> "עודכנה"/"עודכנו") — the earlier single masculine-singular form
# does NOT match as a substring of its own feminine/plural conjugation
# (verified directly: "הושלם" is not a substring of "הושלמה" at all, they use
# different mem characters). Same class of gap as BUG-119's missing plural
# forms, caught here by removing the ✅ crutch that had been masking it for
# "הושלמה" specifically (see test_generic_success_fallback_without_evidence_is_shadow_mismatch,
# pre-existing and still expected to pass). Explicit conjugated forms added
# for both at-risk verbs; "נוצר"/"נשלח"/"נשמר" end in non-final letters so
# their existing single form already covers the feminine/plural conjugations
# as substrings ("נוצרה"/"נוצרו" both contain "נוצר", etc. — verified).
_MUTATION_SUCCESS = re.compile(
    r"(?:\b(?:done|completed|created|updated|sent|saved)\b|"
    r"בוצע|הושלם|הושלמה|הושלמו|נוצר|עודכן|עודכנה|עודכנו|נשלח|נשמר|"
    r"הוספתי|עדכנתי|יצרתי|שלחתי|שמרתי|מחקתי|נמחק|נמחקה|נמחקו)",
    re.IGNORECASE,
)
_FAILURE = re.compile(r"(?:❌|\b(?:failed|failure|error)\b|נכשל|שגיאה|לא הושלמ)", re.IGNORECASE)
_PENDING = re.compile(r"(?:⏳|\bpending\b|ממתינ|ממתין לאישור|ממתינה לאישור)", re.IGNORECASE)
_UNKNOWN = re.compile(r"(?:\boutcome[_ -]?unknown\b|לא ידוע|לא ניתן לאמת|דורש בדיקה)", re.IGNORECASE)


def _classify_response_claim(final_text: str, *, approval_prompt_sent: bool = False) -> str:
    """Classify claim shape for comparison only; this is never execution truth.

    F52 PR6: an empty final_text is not always evidence of nothing having
    been told to the user. When an approval was queued this turn, A32's
    Single-Speaker gate deliberately returns "" for the agent's own text
    (see anti_hallucination.sanitize_agent_response's __approval_queued__
    branch) — the real, user/owner-visible "⏳ בקשת אישור..." message was
    already sent this turn through a separate side channel (a direct
    bot.send_message call in app.py's _queue_approval_detailed_impl(), not
    the agent's returned text). Before this fix, that correct suppression
    made EvidenceFinalizerShadow see response_claim=empty against
    evidence_status=approval_pending — a false mismatch, not a real one.
    approval_prompt_sent (proven by the caller, never guessed here — see
    app.py's owner_notified plumbing) turns that into the honest
    "sent_for_approval" claim instead."""
    if not final_text or not final_text.strip():
        return "sent_for_approval" if approval_prompt_sent else "empty"
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
    *,
    approval_prompt_sent: bool = False,
) -> ShadowFinalizerComparison:
    status = evidence.classification()
    claim = _classify_response_claim(final_text, approval_prompt_sent=approval_prompt_sent)
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
    # F52 PR6: "sent_for_approval" is compatible with approval_pending —
    # a real message was already sent this turn, just not via final_text.
    #
    # F52 PR6 follow-up (production-validated): a turn that ALSO did a
    # verified read this turn (e.g. looked up a record) before queuing the
    # approval classifies as evidence_status="mixed" (verified_reads>0 AND
    # approvals_pending>0 — see TurnEvidenceSummary.classification()'s first
    # "mixed" branch), not "approval_pending" — so the check above alone
    # still reported a false mismatch for that turn shape even though
    # "sent_for_approval" is exactly as legitimate a claim there as it is
    # for a bare approval_pending turn. Narrowly widened: "sent_for_approval"
    # is ALSO compatible with status=="mixed" specifically when the only
    # "non-success" contributor to that mix is approvals_pending itself —
    # zero failed_calls, zero unverified_effects, zero outcome_unknown.
    # Deliberately does NOT extend to a "mixed" turn that also has a real
    # failure or an unverified/unknown effect mixed in — those genuinely
    # need their own claim in the text, "sent_for_approval" alone would
    # hide them. (Given TurnEvidenceSummary.classification()'s own logic,
    # this combination of zeros can only reach "mixed" via its first branch
    # — verified reads/writes plus approvals_pending — never via the
    # failed_calls/unverified_effects branches, so verified>0 is implied
    # here, not re-checked separately.)
    compatible = claim == expected_claim or (
        status == "no_evidence" and claim in ("empty", "neutral")
    ) or (
        status == "approval_pending" and claim == "sent_for_approval"
    ) or (
        status == "mixed" and claim == "sent_for_approval"
        and evidence.failed_calls == 0
        and evidence.unverified_effects == 0
        and evidence.outcome_unknown == 0
        and evidence.approvals_pending > 0
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
    approval_prompt_sent: bool = False,
) -> tuple[str, ShadowFinalizerComparison | None]:
    """Record a safe comparison and always return user text unchanged in RP4.

    approval_prompt_sent: True when this turn's approval-pending message was
    actually sent to the owner through the side channel (app.py's
    _queue_approval_detailed_impl() owner notification), proven by the
    caller via owner_notified — never inferred here. See
    _classify_response_claim()'s docstring for why this matters."""
    if state not in ("shadow", "enforce"):
        return final_text, None

    comparison = compare_shadow_final_status(
        final_text, evidence, approval_prompt_sent=approval_prompt_sent,
    )
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
