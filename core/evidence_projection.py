from __future__ import annotations

import json
from typing import Any

from core.dispatcher_outcome import DispatcherOutcome
from core.router.ownership_contracts import EvidenceResult


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple, set)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(value)
    return str(value)


def build_evidence_result(
    contract: Any | None,
    *,
    provider_result: Any | None = None,
    evidence_ref: str = "",
    verified: bool = False,
    outcome_unknown: bool = False,
    error: str = "",
) -> EvidenceResult:
    """Construct a deterministic WS2 evidence projection from a contract.

    Success requires both a terminal successful contract and verified evidence.
    Any missing or ambiguous data fails closed to outcome_unknown instead of
    implying success.
    """
    if contract is None:
        return EvidenceResult(
            result="outcome_unknown",
            evidence_ref=evidence_ref,
            provider_result=_stringify(provider_result),
            verified=False,
            outcome_unknown=True,
            error=error or "missing_snapshot",
        )

    status = str(getattr(contract, "status", "") or "")
    provider_text = _stringify(provider_result)
    if status in {"completed", "executed"}:
        if verified and evidence_ref:
            return EvidenceResult(
                result="success",
                evidence_ref=evidence_ref,
                provider_result=provider_text,
                verified=True,
                outcome_unknown=False,
                error="",
            )
        return EvidenceResult(
            result="outcome_unknown",
            evidence_ref=evidence_ref,
            provider_result=provider_text,
            verified=False,
            outcome_unknown=True,
            error=error or "missing_verified_evidence",
        )

    if status == "failed":
        return EvidenceResult(
            result="failed",
            evidence_ref=evidence_ref,
            provider_result=provider_text,
            verified=False,
            outcome_unknown=False,
            error=error or "execution_failed",
        )

    if status in {"rejected", "cancelled"}:
        return EvidenceResult(
            result="failed",
            evidence_ref=evidence_ref,
            provider_result=provider_text,
            verified=False,
            outcome_unknown=False,
            error=error or "rejected",
        )

    if status == "outcome_unknown" or outcome_unknown:
        return EvidenceResult(
            result="outcome_unknown",
            evidence_ref=evidence_ref,
            provider_result=provider_text,
            verified=False,
            outcome_unknown=True,
            error=error or "outcome_unknown",
        )

    if status in {"pending", "approved", "executing"}:
        return EvidenceResult(
            result="outcome_unknown",
            evidence_ref=evidence_ref,
            provider_result=provider_text,
            verified=False,
            outcome_unknown=True,
            error=error or "pending",
        )

    return EvidenceResult(
        result="outcome_unknown",
        evidence_ref=evidence_ref,
        provider_result=provider_text,
        verified=False,
        outcome_unknown=True,
        error=error or "missing_snapshot",
    )


# ══════════════════════════════════════════════════
# TC7-A — exact-contract execution evidence
# ══════════════════════════════════════════════════
#
# build_evidence_result() above is deliberately conservative: called with no
# provider_result/evidence_ref/verified, a genuinely completed contract still
# fails closed to outcome_unknown (see its own docstring — "success requires
# both a terminal successful contract and verified evidence"). That is
# correct for a caller with contract state alone (e.g. a later "what's the
# status of my most recent action" query) and it is exactly why plain
# ActionGateway.execution_status()/terminal_status() must never be treated as
# an enforcement authority: they never have provider evidence to pass, so
# they can never legitimately report "success" even for a real one — using
# them for enforcement wouldn't just be under-correlated, it would be
# permanently wrong.
#
# build_evidence_result_from_outcome() is the one function allowed to turn
# real, same-turn, structured provider evidence (a DispatcherOutcome
# produced by executing THIS EXACT contract) into a "success" EvidenceResult.
# It never invents evidence from outcome.user_message, and it never defines
# its own, second notion of "what counts as real evidence" — evidence_ref is
# derived exclusively via core.anti_hallucination.extract_canonical_evidence_ref(),
# the exact same per-tool structured-field logic (record_id/event_id+htmlLink/
# draft_id/message_id/file_id/audit_id/etc., not just a top-level external_id)
# that verify_execution() itself already uses to accept/reject this same
# result. A tool's evidence shape can only ever be defined once, in one
# place (_EVIDENCE_VALIDATORS) — this function and verify_execution() both
# read from it, neither can drift from the other.

def build_evidence_result_from_outcome(
    contract: Any | None,
    outcome: DispatcherOutcome | None,
) -> EvidenceResult:
    """Exact-contract evidence projection: contract snapshot + same-turn outcome.

    `contract` must be the exact contract this `outcome` came from — never a
    "latest for user" lookup. `outcome` must be the DispatcherOutcome that
    executing this exact contract just produced (or None, when no structured
    evidence is available this turn, e.g. a pure identity/repository failure
    before dispatch was ever attempted).

    Falls back to the conservative contract-only projection when outcome is
    None. When outcome is a real DispatcherOutcome, a "success" result is
    only possible when outcome.is_completed() AND the exact contract's
    tool_name has a canonical structured evidence reference in
    outcome.raw_response (per extract_canonical_evidence_ref() — this may be
    a nested evidence.record_id/event_id/draft_id/etc., not only a top-level
    external_id) — a completed contract with no such reference still fails
    closed to outcome_unknown, never success.
    """
    if outcome is None:
        return build_evidence_result(contract)

    evidence_ref = ""
    if outcome.is_completed():
        from core.anti_hallucination import extract_canonical_evidence_ref

        tool_name = str(getattr(contract, "tool_name", "") or "")
        raw = outcome.raw_response if isinstance(outcome.raw_response, dict) else None
        if raw is None and outcome.external_id:
            # No full structured result captured this turn (e.g. a
            # DispatcherOutcome built with only external_id set) — build the
            # minimal shape the same extractor expects, so a bare external_id
            # still goes through the identical per-tool validation (Airtable
            # record-id shape, etc.) rather than bypassing it.
            raw = {"ok": True, "external_id": outcome.external_id}
        if raw is not None:
            evidence_ref = extract_canonical_evidence_ref(tool_name, raw)

    verified = bool(outcome.is_completed() and evidence_ref)
    return build_evidence_result(
        contract,
        provider_result=outcome.raw_response,
        evidence_ref=evidence_ref,
        verified=verified,
        outcome_unknown=outcome.is_outcome_unknown(),
        error=outcome.error or "",
    )
