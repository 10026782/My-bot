"""Canonical recruitment mutations; reachable only through ActionGateway/dispatcher."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from airtable_schema import (
    MonthlyCalculationBatchFields as BF,
    MonthlyCalculationBatchStatus as BS,
    MonthlyCalculationBatchType as BT,
    PaymentFields,
    Direction,
    Tables,
    WorkerAssignmentFields as AF,
    WorkerAssignmentStatus as AS,
    WorkerMonthlyResultFields as RF,
    WorkerPayoutStatus,
)
from core.recruitment_contracts import (
    MonthlyCalculationBatchRead,
    MonthlyCalculationBatchWrite,
    RecruitmentValidationError,
    WorkerAssignmentRead,
    WorkerAssignmentWrite,
    WorkerMonthlyResultRead,
    WorkerMonthlyResultWrite,
    validate_assignment,
    validate_batch,
    validate_closed_update,
    validate_result,
)
from tools.airtable_gateway import airtable_create, airtable_patch, escape_formula_value
from tools.airtable_read_adapter import get_record, get_record_fields, list_records
from tools.airtable_tools import _tool_result


TOOL = "recruitment_write"
_LOCK = threading.RLock()
_ASSIGNMENT_TRANSITIONS = {
    AS.TRAINING: {AS.WAITING_START, AS.ACTIVE, AS.ENDED},
    AS.WAITING_START: {AS.ACTIVE, AS.PAUSED, AS.ENDED},
    AS.ACTIVE: {AS.PAUSED, AS.ENDED},
    AS.PAUSED: {AS.ACTIVE, AS.ENDED},
    AS.ENDED: set(),
}
_BATCH_TRANSITIONS = {
    BS.RECEIVED: {BS.PROCESSING, BS.REVIEWED},
    BS.PROCESSING: {BS.REVIEWED},
    BS.REVIEWED: set(),
    BS.CLOSED: set(),
}


def _ok(record_id: str, operation: str, *, idempotent: bool = False) -> dict:
    return _tool_result(ok=True, tool=TOOL, external_id=record_id,
                        evidence={"record_id": record_id, "operation": operation,
                                  "idempotent": idempotent},
                        user_message="✅ פעולת הגיוס נשמרה.")


def _fail(message: str) -> dict:
    return _tool_result(ok=False, tool=TOOL, user_message=f"❌ {message}")


def _unsupported(payload: dict[str, Any], allowed: set[str]) -> dict | None:
    extra = set(payload) - allowed
    return _fail(f"unsupported fields: {sorted(extra)!r}") if extra else None


def _links(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item.get("id", "") if isinstance(item, dict) else item) for item in value]


def _by_reference(table: str, field: str, reference: str) -> list[dict]:
    return list_records(table, f"{{{field}}}='{escape_formula_value(reference)}'",
                        max_records=2, fields=[field], paginate=False)


def _linked(table: str, field: str, record_id: str, fields: list[str]) -> list[dict]:
    return list_records(table, f"FIND('{escape_formula_value(record_id)}', ARRAYJOIN({{{field}}}))",
                        max_records=None, fields=fields, paginate=True)


def _create(table: str, fields: dict[str, Any], reference_field: str,
            operation: str, source: str) -> dict:
    existing = _by_reference(table, reference_field, str(fields[reference_field]))
    if len(existing) > 1:
        return _fail("duplicate reference already exists; manual review required")
    if existing:
        record_id = existing[0].get("id", "")
        current = get_record_fields(table, record_id)
        if any(current.get(key) != value for key, value in fields.items()):
            return _fail("reference already exists with different data")
        return _ok(record_id, operation, idempotent=True)
    outcome = airtable_create(table, fields, source=source, return_outcome=True)
    if outcome.status != "created":
        return _fail(outcome.error or "Airtable write failed")
    return _ok(outcome.record.get("id", ""), operation)


def _patch(table: str, record_id: str, fields: dict[str, Any], operation: str, source: str) -> dict:
    current = get_record_fields(table, record_id)
    changes = {key: value for key, value in fields.items() if current.get(key) != value}
    if not changes:
        return _ok(record_id, operation, idempotent=True)
    if not airtable_patch(table, record_id, changes, source=source):
        return _fail("Airtable update failed")
    return _ok(record_id, operation)


def _assignment(record_id: str) -> tuple[WorkerAssignmentRead, dict]:
    record = get_record(Tables.WORKER_ASSIGNMENTS, record_id)
    return WorkerAssignmentRead.from_airtable(record), record.get("fields", {})


def _batch(record_id: str) -> tuple[MonthlyCalculationBatchRead, dict]:
    record = get_record(Tables.MONTHLY_CALCULATION_BATCHES, record_id)
    return MonthlyCalculationBatchRead.from_airtable(record), record.get("fields", {})


def _result(record_id: str) -> tuple[WorkerMonthlyResultRead, dict]:
    record = get_record(Tables.WORKER_MONTHLY_RESULTS, record_id)
    return WorkerMonthlyResultRead.from_airtable(record), record.get("fields", {})


def _incoming_payment(payment_id: str, organization_id: str) -> tuple[dict | None, dict]:
    payment = get_record_fields(Tables.PAYMENTS, payment_id)
    if payment.get(PaymentFields.DIRECTION) != Direction.RECEIVABLE:
        return _fail("linked payment must be receivable"), payment
    if organization_id not in _links(payment.get(PaymentFields.COUNTERPARTY_ORGANIZATION)):
        return _fail("incoming payment organization must match the batch"), payment
    return None, payment


def _assignment_write(payload: dict[str, Any]) -> WorkerAssignmentWrite:
    return WorkerAssignmentWrite(
        str(payload["reference"]), str(payload["contact_id"]), str(payload["organization_id"]),
        str(payload["status"]), date.fromisoformat(str(payload["start_date"])),
        date.fromisoformat(str(payload["end_date"])) if payload.get("end_date") else None,
        str(payload.get("work_type_role", "")), str(payload.get("region", "")),
        str(payload.get("notes", "")),
    )


def _batch_write(payload: dict[str, Any], batch_type: str) -> MonthlyCalculationBatchWrite:
    return MonthlyCalculationBatchWrite(
        str(payload["reference"]), str(payload["organization_id"]),
        date.fromisoformat(str(payload["month"])), batch_type, str(payload.get("status", BS.RECEIVED)),
        str(payload.get("original_closed_batch_id", "")), str(payload.get("incoming_payment_id", "")),
        tuple(payload.get("source_file_ids", ())), str(payload.get("source_reference", "")),
        str(payload.get("variance_note", "")), str(payload.get("notes", "")),
    )


def _result_write(payload: dict[str, Any]) -> WorkerMonthlyResultWrite:
    return WorkerMonthlyResultWrite(
        str(payload["reference"]), str(payload["batch_id"]), str(payload["assignment_id"]),
        Decimal(str(payload["attributed_revenue"])), Decimal(str(payload["worker_due"])),
        str(payload.get("allocation_rule_id", "")), str(payload.get("allocation_snapshot_id", "")),
        str(payload.get("calculation_notes", "")), str(payload.get("payout_status", WorkerPayoutStatus.PENDING)),
        str(payload.get("outgoing_payment_id", "")), str(payload.get("review_notes", "")),
    )


def _close_batch(record_id: str, actor_role: str, source: str) -> dict:
    batch, fields = _batch(record_id)
    if batch.status == BS.CLOSED:
        return _ok(record_id, "close_batch", idempotent=True)
    if batch.status != BS.REVIEWED:
        return _fail("batch must be reviewed before closing")
    payment_ids = _links(fields.get(BF.INCOMING_PAYMENT))
    if len(payment_ids) != 1:
        return _fail("batch requires exactly one incoming payment before closing")
    error, payment = _incoming_payment(payment_ids[0], batch.organization_id)
    if error:
        return error
    incoming = Decimal(str(payment.get(PaymentFields.AMOUNT, 0)))
    result_records = _linked(Tables.WORKER_MONTHLY_RESULTS, RF.BATCH, record_id,
                             [RF.ATTRIBUTED_REVENUE])
    attributed = sum((Decimal(str(item.get("fields", {}).get(RF.ATTRIBUTED_REVENUE, 0)))
                      for item in result_records), Decimal("0"))
    variance = incoming - attributed
    if variance and not str(fields.get(BF.VARIANCE_NOTE, "")).strip():
        return _fail("non-zero variance requires a variance note")
    if variance and actor_role not in {"owner", "manager"}:
        return _fail("non-zero variance closure requires owner or manager authority")
    return _patch(Tables.MONTHLY_CALCULATION_BATCHES, record_id, {BF.STATUS: BS.CLOSED},
                  "close_batch", source)


def execute_recruitment_write(operation: str, payload: dict[str, Any], *,
                              actor_role: str, source: str = "recruitment") -> dict:
    """Execute one validated mutation after dispatcher execution-proof checks."""
    try:
        with _LOCK:  # ponytail: process lock; provider uniqueness is unavailable in Airtable.
            if operation == "create_assignment":
                if error := _unsupported(payload, {"reference", "contact_id", "organization_id", "status",
                                                   "start_date", "end_date", "work_type_role", "region", "notes"}):
                    return error
                candidate = _assignment_write(payload)
                existing = [WorkerAssignmentRead.from_airtable(row) for row in _linked(
                    Tables.WORKER_ASSIGNMENTS, AF.CONTACT, candidate.contact_id,
                    [AF.REFERENCE, AF.CONTACT, AF.ORGANIZATION, AF.STATUS, AF.START_DATE, AF.END_DATE])]
                validate_assignment(candidate, existing)
                return _create(Tables.WORKER_ASSIGNMENTS, candidate.to_airtable_fields(), AF.REFERENCE,
                               operation, source)

            if operation in {"update_assignment", "end_assignment"}:
                allowed = ({"record_id", "end_date", "notes"} if operation == "end_assignment" else
                           {"record_id", "reference", "status", "start_date", "end_date",
                            "work_type_role", "region", "notes"})
                if error := _unsupported(payload, allowed):
                    return error
                record_id = str(payload["record_id"])
                current, _ = _assignment(record_id)
                status = AS.ENDED if operation == "end_assignment" else str(payload.get("status", current.status))
                candidate = replace(current, record_id="", reference=str(payload.get("reference", current.reference)),
                                    status=status,
                                    start_date=date.fromisoformat(str(payload.get("start_date", current.start_date))),
                                    end_date=date.fromisoformat(str(payload["end_date"])) if payload.get("end_date") else current.end_date)
                write = WorkerAssignmentWrite(candidate.reference, candidate.contact_id, candidate.organization_id,
                                              candidate.status, candidate.start_date, candidate.end_date,
                                              str(payload.get("work_type_role", "")), str(payload.get("region", "")),
                                              str(payload.get("notes", "")))
                if status != current.status and status not in _ASSIGNMENT_TRANSITIONS.get(current.status, set()):
                    return _fail("invalid assignment lifecycle transition")
                if operation == "end_assignment" and not write.end_date:
                    return _fail("ending an assignment requires end_date")
                existing = [WorkerAssignmentRead.from_airtable(row) for row in _linked(
                    Tables.WORKER_ASSIGNMENTS, AF.CONTACT, current.contact_id,
                    [AF.REFERENCE, AF.CONTACT, AF.ORGANIZATION, AF.STATUS, AF.START_DATE, AF.END_DATE])]
                validate_assignment(write, existing, current_record_id=record_id)
                return _patch(Tables.WORKER_ASSIGNMENTS, record_id, write.to_airtable_fields(), operation, source)

            if operation in {"create_canonical_batch", "create_adjustment_batch"}:
                if error := _unsupported(payload, {"reference", "organization_id", "month",
                                                   "original_closed_batch_id", "incoming_payment_id",
                                                   "source_file_ids", "source_reference", "variance_note", "notes"}):
                    return error
                batch_type = BT.CANONICAL if operation == "create_canonical_batch" else BT.ADJUSTMENT
                candidate = _batch_write(payload, batch_type)
                if candidate.status != BS.RECEIVED:
                    return _fail("new batches must start as received")
                if candidate.incoming_payment_id:
                    error, _ = _incoming_payment(candidate.incoming_payment_id,
                                                 candidate.organization_id)
                    if error:
                        return error
                existing = [MonthlyCalculationBatchRead.from_airtable(row) for row in _linked(
                    Tables.MONTHLY_CALCULATION_BATCHES, BF.ORGANIZATION, candidate.organization_id,
                    [BF.REFERENCE, BF.ORGANIZATION, BF.MONTH, BF.BATCH_TYPE, BF.STATUS, BF.ORIGINAL_CLOSED_BATCH])]
                original = _batch(candidate.original_closed_batch_id)[0] if candidate.original_closed_batch_id else None
                validate_batch(candidate, existing, original)
                return _create(Tables.MONTHLY_CALCULATION_BATCHES, candidate.to_airtable_fields(), BF.REFERENCE,
                               operation, source)

            if operation == "update_batch":
                if error := _unsupported(payload, {"record_id", "status", "incoming_payment_id",
                                                   "source_reference", "variance_note", "notes"}):
                    return error
                record_id = str(payload["record_id"])
                current, fields = _batch(record_id)
                if current.status == BS.CLOSED:
                    return _fail("closed batch is immutable; create an adjustment")
                changes: dict[str, Any] = {}
                if "status" in payload:
                    new_status = str(payload["status"])
                    if new_status == BS.CLOSED:
                        return _fail("use close_batch for the closed transition")
                    if new_status != current.status and new_status not in _BATCH_TRANSITIONS.get(current.status, set()):
                        return _fail("invalid batch status transition")
                    changes[BF.STATUS] = new_status
                for key, field, linked in (("incoming_payment_id", BF.INCOMING_PAYMENT, True),
                                           ("source_reference", BF.SOURCE_REFERENCE, False),
                                           ("variance_note", BF.VARIANCE_NOTE, False), ("notes", BF.NOTES, False)):
                    if key in payload:
                        changes[field] = [str(payload[key])] if linked and payload[key] else payload[key]
                if "incoming_payment_id" in payload and payload["incoming_payment_id"]:
                    error, _ = _incoming_payment(str(payload["incoming_payment_id"]),
                                                 current.organization_id)
                    if error:
                        return error
                return _patch(Tables.MONTHLY_CALCULATION_BATCHES, record_id, changes, operation, source)

            if operation == "close_batch":
                if error := _unsupported(payload, {"record_id"}):
                    return error
                return _close_batch(str(payload["record_id"]), actor_role, source)

            if operation == "create_result":
                if error := _unsupported(payload, {"reference", "batch_id", "assignment_id",
                                                   "attributed_revenue", "worker_due", "allocation_rule_id",
                                                   "allocation_snapshot_id", "calculation_notes", "payout_status",
                                                   "outgoing_payment_id", "review_notes"}):
                    return error
                candidate = _result_write(payload)
                if candidate.payout_status not in {WorkerPayoutStatus.PENDING, WorkerPayoutStatus.PARTIAL,
                                                   WorkerPayoutStatus.PAID, WorkerPayoutStatus.HOLD}:
                    return _fail("invalid payout status")
                assignment, _ = _assignment(candidate.assignment_id)
                batch, _ = _batch(candidate.batch_id)
                if batch.status == BS.CLOSED:
                    return _fail("cannot add a result to a closed batch")
                existing = [WorkerMonthlyResultRead.from_airtable(row) for row in _linked(
                    Tables.WORKER_MONTHLY_RESULTS, RF.BATCH, candidate.batch_id,
                    [RF.REFERENCE, RF.BATCH, RF.WORKER_ASSIGNMENT, RF.ATTRIBUTED_REVENUE, RF.WORKER_DUE])]
                validate_result(candidate, existing, assignment, batch)
                return _create(Tables.WORKER_MONTHLY_RESULTS, candidate.to_airtable_fields(), RF.REFERENCE,
                               operation, source)

            if operation in {"update_result", "update_result_payout"}:
                record_id = str(payload["record_id"])
                current, fields = _result(record_id)
                batch, _ = _batch(current.batch_id)
                allowed = ({"payout_status", "outgoing_payment_id", "review_notes"}
                           if operation == "update_result_payout" else
                           {"attributed_revenue", "worker_due", "allocation_rule_id", "allocation_snapshot_id",
                            "calculation_notes", "review_notes"})
                if set(payload) - {"record_id"} - allowed:
                    return _fail("unsupported result fields")
                candidate = WorkerMonthlyResultWrite(
                    current.reference, current.batch_id, current.assignment_id,
                    Decimal(str(payload.get("attributed_revenue", current.attributed_revenue))),
                    Decimal(str(payload.get("worker_due", current.worker_due))),
                    str(payload.get("allocation_rule_id", _links(fields.get(RF.ALLOCATION_RULE))[0] if _links(fields.get(RF.ALLOCATION_RULE)) else "")),
                    str(payload.get("allocation_snapshot_id", _links(fields.get(RF.ALLOCATION_SNAPSHOT))[0] if _links(fields.get(RF.ALLOCATION_SNAPSHOT)) else "")),
                    str(payload.get("calculation_notes", fields.get(RF.CALCULATION_NOTES, ""))),
                    str(payload.get("payout_status", fields.get(RF.PAYOUT_STATUS, WorkerPayoutStatus.PENDING))),
                    str(payload.get("outgoing_payment_id", _links(fields.get(RF.OUTGOING_PAYMENT))[0] if _links(fields.get(RF.OUTGOING_PAYMENT)) else "")),
                    str(payload.get("review_notes", fields.get(RF.REVIEW_NOTES, ""))),
                )
                if candidate.payout_status not in {WorkerPayoutStatus.PENDING, WorkerPayoutStatus.PARTIAL,
                                                   WorkerPayoutStatus.PAID, WorkerPayoutStatus.HOLD}:
                    return _fail("invalid payout status")
                assignment, _ = _assignment(current.assignment_id)
                validate_result(candidate, [], assignment, batch, current_record_id=record_id)
                changes = candidate.to_airtable_fields()
                changes = {field: value for field, value in changes.items() if field not in {RF.REFERENCE, RF.BATCH, RF.WORKER_ASSIGNMENT}}
                validate_closed_update(fields, changes, batch_status=batch.status, entity="result")
                return _patch(Tables.WORKER_MONTHLY_RESULTS, record_id, changes, operation, source)

            return _fail("unknown recruitment operation")
    except (KeyError, ValueError, ArithmeticError, RecruitmentValidationError) as exc:
        return _fail(str(exc))
    except Exception:
        return _fail("recruitment state could not be verified; no write performed")
