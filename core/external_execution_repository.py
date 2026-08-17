"""Durable ExternalExecutionJob repository backed by the Airtable gateway."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time

from airtable_schema import ExternalExecutionJobFields, Tables
from tools.airtable_gateway import (
    AirtableLookupError,
    at_get_by_field,
    at_list_by_formula,
    airtable_create,
    airtable_patch,
)


TERMINAL_JOB_STATES = frozenset({"completed", "failed", "outcome_unknown"})


@dataclass
class ExternalExecutionJob:
    contract_id: str
    adapter_name: str
    provider_job_id: str = ""
    status: str = "created"
    submitted_at: float | None = None
    last_checked_at: float | None = None
    completed_at: float | None = None
    attempt_count: int = 0
    result_ref: str = ""
    evidence: dict | None = None
    failure_code: str = ""


def _fields(job: ExternalExecutionJob) -> dict:
    f = ExternalExecutionJobFields
    return {
        f.CONTRACT_ID: job.contract_id,
        f.ADAPTER_NAME: job.adapter_name,
        f.PROVIDER_JOB_ID: job.provider_job_id,
        f.STATUS: job.status,
        f.SUBMITTED_AT: job.submitted_at,
        f.LAST_CHECKED_AT: job.last_checked_at,
        f.COMPLETED_AT: job.completed_at,
        f.ATTEMPT_COUNT: job.attempt_count,
        f.RESULT_REF: job.result_ref,
        f.EVIDENCE: json.dumps(dict(job.evidence or {}), ensure_ascii=False),
        f.FAILURE_CODE: job.failure_code,
    }


def _job(record: dict) -> ExternalExecutionJob:
    f = record.get("fields", {})
    return ExternalExecutionJob(
        contract_id=str(f.get(ExternalExecutionJobFields.CONTRACT_ID, "")),
        adapter_name=str(f.get(ExternalExecutionJobFields.ADAPTER_NAME, "")),
        provider_job_id=str(f.get(ExternalExecutionJobFields.PROVIDER_JOB_ID, "") or ""),
        status=str(f.get(ExternalExecutionJobFields.STATUS, "created")),
        submitted_at=f.get(ExternalExecutionJobFields.SUBMITTED_AT),
        last_checked_at=f.get(ExternalExecutionJobFields.LAST_CHECKED_AT),
        completed_at=f.get(ExternalExecutionJobFields.COMPLETED_AT),
        attempt_count=int(f.get(ExternalExecutionJobFields.ATTEMPT_COUNT) or 0),
        result_ref=str(f.get(ExternalExecutionJobFields.RESULT_REF, "") or ""),
        evidence=_decode_evidence(f.get(ExternalExecutionJobFields.EVIDENCE)),
        failure_code=str(f.get(ExternalExecutionJobFields.FAILURE_CODE, "") or ""),
    )


def _decode_evidence(value) -> dict:
    if isinstance(value, dict):
        return value
    try:
        decoded = json.loads(value or "{}")
        return decoded if isinstance(decoded, dict) else {}
    except (TypeError, ValueError):
        return {}


class ExternalExecutionRepository:
    table = Tables.EXTERNAL_EXECUTION_JOBS

    def get(self, contract_id: str) -> ExternalExecutionJob | None:
        record = at_get_by_field(self.table, ExternalExecutionJobFields.CONTRACT_ID, contract_id)
        return _job(record) if record else None

    def create(self, job: ExternalExecutionJob) -> ExternalExecutionJob:
        record = airtable_create(self.table, _fields(job), source="external_execution")
        if not record:
            raise AirtableLookupError("external execution job create failed")
        return job

    def update(self, job: ExternalExecutionJob) -> ExternalExecutionJob:
        current = at_get_by_field(self.table, ExternalExecutionJobFields.CONTRACT_ID, job.contract_id)
        if not current or not airtable_patch(self.table, current["id"], _fields(job), source="external_execution"):
            raise AirtableLookupError("external execution job update failed")
        return job

    def list_submitted(self) -> list[ExternalExecutionJob]:
        records = at_list_by_formula(
            self.table,
            "{" + ExternalExecutionJobFields.STATUS + "}='submitted'",
            max_records=100,
        )
        return [_job(record) for record in records]

    def list_for_adapter(self, adapter_name: str) -> list[ExternalExecutionJob]:
        records = at_list_by_formula(
            self.table,
            "{" + ExternalExecutionJobFields.ADAPTER_NAME + "}='" + adapter_name + "'",
            max_records=1000,
        )
        return [_job(record) for record in records]

    def due_submitted(self, now: float | None = None, interval_seconds: int = 300) -> list[ExternalExecutionJob]:
        now = time.time() if now is None else now
        return [
            job for job in self.list_submitted()
            if job.last_checked_at is None or now - float(job.last_checked_at) >= interval_seconds
        ]
