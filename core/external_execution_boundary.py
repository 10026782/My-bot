"""Generic durable boundary for accepted external work and later polling."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Protocol

from core.dispatcher_outcome import DispatcherOutcome
from core.external_execution_repository import (
    ExternalExecutionJob,
    ExternalExecutionRepository,
    TERMINAL_JOB_STATES,
)
from core.external_poll_lease import ExternalPollLeaseRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubmitResult:
    status: str  # accepted | failed | outcome_unknown
    provider_job_id: str = ""
    evidence: dict | None = None
    failure_code: str = ""


@dataclass(frozen=True)
class PollResult:
    status: str  # submitted | completed | failed | outcome_unknown
    result_ref: str = ""
    evidence: dict | None = None
    failure_code: str = ""


class ExternalAdapter(Protocol):
    name: str

    def submit(self, request: dict) -> SubmitResult: ...
    def poll(self, job: ExternalExecutionJob) -> PollResult: ...


class UnconfiguredExternalAdapter:
    name = "unconfigured"

    def submit(self, request: dict) -> SubmitResult:
        return SubmitResult("failed", failure_code="adapter_not_configured")

    def poll(self, job: ExternalExecutionJob) -> PollResult:
        return PollResult("outcome_unknown", failure_code="adapter_not_configured")


class ExternalExecutionBoundary:
    def __init__(self, repository=None, lease_repository=None, adapter=None, *, poll_interval_seconds: int = 300):
        self.repository = repository or ExternalExecutionRepository()
        self.leases = lease_repository or ExternalPollLeaseRepository()
        self.adapter = adapter or UnconfiguredExternalAdapter()
        self.poll_interval_seconds = poll_interval_seconds

    def submit(self, *, contract_id: str, idempotency_key: str, payload: dict) -> DispatcherOutcome:
        try:
            existing = self.repository.get(contract_id)
        except Exception as exc:
            return DispatcherOutcome("outcome_unknown", "לא ניתן לקרוא את מצב ההרצה.", error=str(exc))
        if existing:
            if existing.status in {"submitted", "completed"}:
                return self._accepted(existing)
            if existing.status in {"failed", "outcome_unknown"}:
                return DispatcherOutcome(
                    result="outcome_unknown" if existing.status == "outcome_unknown" else "failed",
                    user_message="השליחה החיצונית כבר קיבלה תוצאה; אין לשלוח מחדש אוטומטית.",
                    external_id=existing.provider_job_id or None,
                    error_code=existing.failure_code or None,
                )
        job = existing or ExternalExecutionJob(contract_id=contract_id, adapter_name=self.adapter.name)
        if existing is None:
            try:
                self.repository.create(job)  # durable create-before-submit
            except Exception as exc:
                return DispatcherOutcome("outcome_unknown", "לא ניתן לשמור את עבודת ההרצה.", error=str(exc))

        try:
            result = self.adapter.submit({"contract_id": contract_id, "idempotency_key": idempotency_key, "payload": payload})
        except Exception as exc:
            result = SubmitResult("outcome_unknown", failure_code="adapter_exception")
            logger.warning("external submit outcome unknown: %s", exc)

        if result.status == "accepted":
            job.provider_job_id = result.provider_job_id
            job.status = "submitted"
            job.submitted_at = time.time()
            job.attempt_count += 1
            job.evidence = _bounded_evidence(result.evidence)
            try:
                self.repository.update(job)
            except Exception as exc:
                return DispatcherOutcome("outcome_unknown", "השליחה התקבלה אך מצב העבודה לא נשמר.", error=str(exc))
            return self._accepted(job)

        job.status = "failed" if result.status == "failed" else "outcome_unknown"
        job.failure_code = result.failure_code[:120]
        job.evidence = _bounded_evidence(result.evidence)
        try:
            self.repository.update(job)
        except Exception:
            return DispatcherOutcome("outcome_unknown", "תוצאת השליחה אינה ודאית; אין לנסות שוב אוטומטית.")
        return DispatcherOutcome(
            job.status,
            "ההרצה החיצונית נכשלה." if job.status == "failed" else "תוצאת ההרצה אינה ידועה; אין לנסות שוב אוטומטית.",
            error_code=job.failure_code or None,
        )

    def poll_due(self, *, poller_id: str | None = None) -> int:
        poller_id = poller_id or os.environ.get("HOSTNAME", "boss-scheduler")
        count = 0
        for candidate in self.repository.due_submitted(interval_seconds=self.poll_interval_seconds):
            lease = self.leases.acquire(candidate.contract_id, poller_id, lease_seconds=120)
            if not lease:
                continue
            try:
                try:
                    job = self.repository.get(candidate.contract_id)
                except Exception:
                    logger.warning("external job reread failed: %s", candidate.contract_id)
                    continue
                if not job or job.status != "submitted":
                    continue
                try:
                    result = self.adapter.poll(job)
                except Exception:
                    result = PollResult("outcome_unknown", failure_code="poll_exception")
                job.last_checked_at = time.time()
                job.attempt_count += 1
                if result.status in {"completed", "failed", "outcome_unknown"}:
                    job.status = result.status
                    job.result_ref = result.result_ref[:500]
                    job.failure_code = result.failure_code[:120]
                    job.evidence = _bounded_evidence(result.evidence)
                    if result.status in TERMINAL_JOB_STATES:
                        job.completed_at = time.time()
                try:
                    self.repository.update(job)
                    count += 1
                except Exception:
                    # Provider was already polled. Keep submitted state and never resubmit.
                    logger.warning("external poll result could not be persisted: %s", job.contract_id)
            finally:
                self.leases.release(lease)
        return count

    def completed_job(self, contract_id: str) -> ExternalExecutionJob | None:
        """Artifact guard: ActionContract completion alone is never enough."""
        try:
            job = self.repository.get(contract_id)
        except Exception:
            return None
        return job if job and job.status == "completed" else None

    @staticmethod
    def _accepted(job: ExternalExecutionJob) -> DispatcherOutcome:
        return DispatcherOutcome(
            "completed",
            "ההרצה החיצונית התקבלה לעיבוד.",
            external_id=job.contract_id,
            raw_response={"ok": True, "external_job_status": job.status, "provider_job_id": job.provider_job_id},
        )


def _bounded_evidence(evidence: dict | None) -> dict:
    if not isinstance(evidence, dict):
        return {}
    allowed = {"provider_job_id", "provider_status", "submitted_at", "completed_at", "result_checksum", "result_ref", "adapter_name", "checked_at", "script_sha256", "mime_type", "size"}
    return {str(k): str(v)[:200] for k, v in evidence.items() if k in allowed}


def _default_adapter():
    if os.environ.get("MPT_RUNTIME_ROOT"):
        from core.moneyprinterturbo_adapter import MoneyPrinterTurboAdapter
        return MoneyPrinterTurboAdapter()
    return UnconfiguredExternalAdapter()


_DEFAULT_BOUNDARY = ExternalExecutionBoundary(adapter=_default_adapter())


def get_default_boundary() -> ExternalExecutionBoundary:
    return _DEFAULT_BOUNDARY
