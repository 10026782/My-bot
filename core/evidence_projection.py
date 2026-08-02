from __future__ import annotations

import json
from typing import Any

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
