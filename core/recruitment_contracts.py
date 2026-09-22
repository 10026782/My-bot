"""Typed, side-effect-free contracts and invariants for recruitment records.

Write contracts only produce fields for the existing ActionGateway Airtable
tools. This module never writes to Airtable directly.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping

from airtable_schema import (
    MonthlyCalculationBatchFields as BF,
    MonthlyCalculationBatchStatus,
    MonthlyCalculationBatchType,
    WorkerAssignmentFields as AF,
    WorkerAssignmentStatus,
    WorkerMonthlyResultFields as RF,
    WorkerPayoutStatus,
)


class RecruitmentValidationError(ValueError):
    pass


def recruitment_create_natural_key(action: Mapping[str, object]) -> str | None:
    """Return the durable idempotency key for one recruitment create action."""
    operation = str(action.get("operation", ""))
    if operation not in {"create_assignment", "create_canonical_batch", "create_adjustment_batch", "create_result"}:
        return None
    payload = action.get("payload")
    if not isinstance(payload, Mapping):
        raise RecruitmentValidationError("recruitment create requires a payload object")

    def required(name: str) -> str:
        value = str(payload.get(name, ""))
        if not value:
            raise RecruitmentValidationError(f"recruitment create requires {name}")
        return value

    if operation == "create_assignment":
        return f"WA:{required('contact_id')}:{required('organization_id')}:{date.fromisoformat(required('start_date')).isoformat()}"
    if operation == "create_canonical_batch":
        month = date.fromisoformat(required("month"))
        if month.day != 1:
            raise RecruitmentValidationError("batch month must be the first day of the month")
        return f"MCB:{required('organization_id')}:{month.strftime('%Y-%m')}"
    if operation == "create_adjustment_batch":
        try:
            sequence = int(required("adjustment_sequence"))
        except ValueError as exc:
            raise RecruitmentValidationError("adjustment_sequence must be a positive integer") from exc
        if sequence < 1:
            raise RecruitmentValidationError("adjustment_sequence must be a positive integer")
        return f"MCB-ADJ:{required('original_closed_batch_id')}:{sequence}"
    return f"WMR:{required('batch_id')}:{required('assignment_id')}"


def _one_link(value: object) -> str:
    return str(value[0]) if isinstance(value, list) and value else ""


def _record(record: Mapping[str, object]) -> tuple[str, Mapping[str, object]]:
    fields = record.get("fields", record)
    return str(record.get("id", "")), fields if isinstance(fields, Mapping) else {}


@dataclass(frozen=True)
class WorkerAssignmentRead:
    record_id: str
    reference: str
    contact_id: str
    organization_id: str
    status: str
    start_date: date
    end_date: date | None = None

    @classmethod
    def from_airtable(cls, record: Mapping[str, object]) -> "WorkerAssignmentRead":
        record_id, fields = _record(record)
        return cls(record_id, str(fields.get(AF.REFERENCE, "")),
                   _one_link(fields.get(AF.CONTACT)), _one_link(fields.get(AF.ORGANIZATION)),
                   str(fields.get(AF.STATUS, "")), date.fromisoformat(str(fields[AF.START_DATE])),
                   date.fromisoformat(str(fields[AF.END_DATE])) if fields.get(AF.END_DATE) else None)


@dataclass(frozen=True)
class WorkerAssignmentWrite:
    reference: str
    contact_id: str
    organization_id: str
    status: str
    start_date: date
    end_date: date | None = None
    work_type_role: str = ""
    region: str = ""
    notes: str = ""

    def to_airtable_fields(self) -> dict[str, object]:
        fields: dict[str, object] = {
            AF.REFERENCE: self.reference, AF.CONTACT: [self.contact_id],
            AF.ORGANIZATION: [self.organization_id], AF.STATUS: self.status,
            AF.START_DATE: self.start_date.isoformat(),
        }
        if self.end_date:
            fields[AF.END_DATE] = self.end_date.isoformat()
        if self.work_type_role:
            fields[AF.WORK_TYPE_ROLE] = self.work_type_role
        if self.region:
            fields[AF.REGION] = self.region
        if self.notes:
            fields[AF.NOTES] = self.notes
        return fields


@dataclass(frozen=True)
class MonthlyCalculationBatchRead:
    record_id: str
    reference: str
    organization_id: str
    month: date
    batch_type: str
    status: str
    original_closed_batch_id: str = ""

    @classmethod
    def from_airtable(cls, record: Mapping[str, object]) -> "MonthlyCalculationBatchRead":
        record_id, fields = _record(record)
        return cls(record_id, str(fields.get(BF.REFERENCE, "")),
                   _one_link(fields.get(BF.ORGANIZATION)), date.fromisoformat(str(fields[BF.MONTH])),
                   str(fields.get(BF.BATCH_TYPE, "")), str(fields.get(BF.STATUS, "")),
                   _one_link(fields.get(BF.ORIGINAL_CLOSED_BATCH)))


@dataclass(frozen=True)
class MonthlyCalculationBatchWrite:
    reference: str
    organization_id: str
    month: date
    batch_type: str = MonthlyCalculationBatchType.CANONICAL
    status: str = MonthlyCalculationBatchStatus.RECEIVED
    original_closed_batch_id: str = ""
    incoming_payment_id: str = ""
    source_file_ids: tuple[str, ...] = ()
    source_reference: str = ""
    variance_note: str = ""
    notes: str = ""

    def to_airtable_fields(self) -> dict[str, object]:
        fields: dict[str, object] = {
            BF.REFERENCE: self.reference, BF.ORGANIZATION: [self.organization_id],
            BF.MONTH: self.month.isoformat(), BF.BATCH_TYPE: self.batch_type, BF.STATUS: self.status,
        }
        optional = ((BF.ORIGINAL_CLOSED_BATCH, [self.original_closed_batch_id] if self.original_closed_batch_id else None),
                    (BF.INCOMING_PAYMENT, [self.incoming_payment_id] if self.incoming_payment_id else None),
                    (BF.SOURCE_FILES, list(self.source_file_ids) or None),
                    (BF.SOURCE_REFERENCE, self.source_reference or None),
                    (BF.VARIANCE_NOTE, self.variance_note or None), (BF.NOTES, self.notes or None))
        fields.update({key: value for key, value in optional if value is not None})
        return fields


@dataclass(frozen=True)
class WorkerMonthlyResultRead:
    record_id: str
    reference: str
    batch_id: str
    assignment_id: str
    attributed_revenue: Decimal
    worker_due: Decimal

    @property
    def poseidon_retained(self) -> Decimal:
        return self.attributed_revenue - self.worker_due

    @classmethod
    def from_airtable(cls, record: Mapping[str, object]) -> "WorkerMonthlyResultRead":
        record_id, fields = _record(record)
        return cls(record_id, str(fields.get(RF.REFERENCE, "")), _one_link(fields.get(RF.BATCH)),
                   _one_link(fields.get(RF.WORKER_ASSIGNMENT)),
                   Decimal(str(fields.get(RF.ATTRIBUTED_REVENUE, 0))),
                   Decimal(str(fields.get(RF.WORKER_DUE, 0))))


@dataclass(frozen=True)
class WorkerMonthlyResultWrite:
    reference: str
    batch_id: str
    assignment_id: str
    attributed_revenue: Decimal
    worker_due: Decimal
    allocation_rule_id: str = ""
    allocation_snapshot_id: str = ""
    calculation_notes: str = ""
    payout_status: str = WorkerPayoutStatus.PENDING
    outgoing_payment_id: str = ""
    review_notes: str = ""

    @property
    def poseidon_retained(self) -> Decimal:
        return self.attributed_revenue - self.worker_due

    def to_airtable_fields(self) -> dict[str, object]:
        fields: dict[str, object] = {
            RF.REFERENCE: self.reference, RF.BATCH: [self.batch_id],
            RF.WORKER_ASSIGNMENT: [self.assignment_id],
            RF.ATTRIBUTED_REVENUE: float(self.attributed_revenue),
            RF.WORKER_DUE: float(self.worker_due), RF.PAYOUT_STATUS: self.payout_status,
        }
        optional = ((RF.ALLOCATION_RULE, [self.allocation_rule_id] if self.allocation_rule_id else None),
                    (RF.ALLOCATION_SNAPSHOT, [self.allocation_snapshot_id] if self.allocation_snapshot_id else None),
                    (RF.CALCULATION_NOTES, self.calculation_notes or None),
                    (RF.OUTGOING_PAYMENT, [self.outgoing_payment_id] if self.outgoing_payment_id else None),
                    (RF.REVIEW_NOTES, self.review_notes or None))
        fields.update({key: value for key, value in optional if value is not None})
        return fields


def validate_assignment(candidate: WorkerAssignmentWrite, existing: Iterable[WorkerAssignmentRead], *,
                        current_record_id: str = "") -> None:
    if not all((candidate.reference, candidate.contact_id, candidate.organization_id)):
        raise RecruitmentValidationError("assignment reference, contact and organization are required")
    if candidate.end_date and candidate.end_date < candidate.start_date:
        raise RecruitmentValidationError("assignment end date cannot precede start date")
    if candidate.status not in {WorkerAssignmentStatus.TRAINING, WorkerAssignmentStatus.WAITING_START,
                                WorkerAssignmentStatus.ACTIVE, WorkerAssignmentStatus.PAUSED,
                                WorkerAssignmentStatus.ENDED}:
        raise RecruitmentValidationError("unknown assignment status")
    if candidate.status == WorkerAssignmentStatus.ACTIVE and any(
        item.record_id != current_record_id and item.status == WorkerAssignmentStatus.ACTIVE
        and item.contact_id == candidate.contact_id
        and item.organization_id == candidate.organization_id for item in existing
    ):
        raise RecruitmentValidationError("only one active assignment is allowed per contact and organization")


def validate_batch(candidate: MonthlyCalculationBatchWrite,
                   existing: Iterable[MonthlyCalculationBatchRead],
                   original: MonthlyCalculationBatchRead | None = None, *,
                   current_record_id: str = "") -> None:
    if candidate.month.day != 1:
        raise RecruitmentValidationError("batch month must be the first day of the month")
    if candidate.batch_type == MonthlyCalculationBatchType.CANONICAL:
        if candidate.original_closed_batch_id:
            raise RecruitmentValidationError("canonical batch cannot reference an original batch")
        if any(item.record_id != current_record_id
               and item.batch_type == MonthlyCalculationBatchType.CANONICAL
               and item.organization_id == candidate.organization_id
               and item.month == candidate.month for item in existing):
            raise RecruitmentValidationError("only one canonical batch is allowed per organization and month")
    elif candidate.batch_type == MonthlyCalculationBatchType.ADJUSTMENT:
        if not original or original.record_id != candidate.original_closed_batch_id:
            raise RecruitmentValidationError("adjustment batch must reference its original batch")
        if original.status != MonthlyCalculationBatchStatus.CLOSED:
            raise RecruitmentValidationError("adjustment batch must reference a closed original")
        if original.organization_id != candidate.organization_id:
            raise RecruitmentValidationError("adjustment and original organizations must match")
        if original.month != candidate.month:
            raise RecruitmentValidationError("adjustment and original months must match")
    else:
        raise RecruitmentValidationError("unknown batch type")


def validate_result(candidate: WorkerMonthlyResultWrite,
                    existing: Iterable[WorkerMonthlyResultRead],
                    assignment: WorkerAssignmentRead,
                    batch: MonthlyCalculationBatchRead, *, current_record_id: str = "") -> None:
    if any(item.record_id != current_record_id
           and item.batch_id == candidate.batch_id and item.assignment_id == candidate.assignment_id
           for item in existing):
        raise RecruitmentValidationError("only one result is allowed per batch and assignment")
    if candidate.assignment_id != assignment.record_id or candidate.batch_id != batch.record_id:
        raise RecruitmentValidationError("result links do not match supplied assignment and batch")
    month_end = date(batch.month.year, batch.month.month, monthrange(batch.month.year, batch.month.month)[1])
    if assignment.start_date > month_end or (assignment.end_date and assignment.end_date < batch.month):
        raise RecruitmentValidationError("result month is outside the assignment period")
    if candidate.allocation_rule_id and not candidate.allocation_snapshot_id:
        raise RecruitmentValidationError("allocation snapshot is required when an allocation rule drove the result")


BATCH_IMMUTABLE_FIELDS = frozenset({BF.ORGANIZATION, BF.MONTH, BF.BATCH_TYPE,
                                    BF.ORIGINAL_CLOSED_BATCH, BF.INCOMING_PAYMENT})
RESULT_IMMUTABLE_FIELDS = frozenset({RF.BATCH, RF.WORKER_ASSIGNMENT, RF.ATTRIBUTED_REVENUE,
                                     RF.WORKER_DUE, RF.ALLOCATION_RULE, RF.ALLOCATION_SNAPSHOT})


def validate_closed_update(current: Mapping[str, object], changes: Mapping[str, object], *,
                           batch_status: str, entity: str) -> None:
    if batch_status != MonthlyCalculationBatchStatus.CLOSED:
        return
    protected = BATCH_IMMUTABLE_FIELDS if entity == "batch" else RESULT_IMMUTABLE_FIELDS if entity == "result" else None
    if protected is None:
        raise RecruitmentValidationError("entity must be 'batch' or 'result'")
    if any(field in changes and changes[field] != current.get(field) for field in protected):
        raise RecruitmentValidationError(f"closed {entity} financial fields are immutable")
