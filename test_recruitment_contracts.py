from datetime import date
from decimal import Decimal

import pytest

from airtable_schema import (
    MonthlyCalculationBatchFieldIds,
    MonthlyCalculationBatchFields as BF,
    MonthlyCalculationBatchStatus,
    MonthlyCalculationBatchType,
    TableIds,
    WorkerAssignmentFieldIds,
    WorkerAssignmentFields as AF,
    WorkerAssignmentStatus,
    WorkerMonthlyResultFieldIds,
    WorkerMonthlyResultFields as RF,
)
from core.recruitment_contracts import (
    MonthlyCalculationBatchRead,
    MonthlyCalculationBatchWrite,
    RecruitmentValidationError,
    WorkerAssignmentRead,
    WorkerAssignmentWrite,
    WorkerMonthlyResultRead,
    WorkerMonthlyResultWrite,
    recruitment_create_natural_key,
    validate_assignment,
    validate_batch,
    validate_closed_update,
    validate_result,
)


def assignment(record_id="wa1", organization="org1", status=WorkerAssignmentStatus.ACTIVE,
               start=date(2026, 1, 1), end=None):
    return WorkerAssignmentRead(record_id, "WA", "contact1", organization, status, start, end)


def batch(record_id="batch1", organization="org1", status="reviewed",
          batch_type=MonthlyCalculationBatchType.CANONICAL):
    return MonthlyCalculationBatchRead(record_id, "MCB", organization, date(2026, 8, 1), batch_type, status)


def result(batch_id="batch1", assignment_id="wa1"):
    return WorkerMonthlyResultRead("result1", "WMR", batch_id, assignment_id, Decimal("100"), Decimal("40"))


def test_live_schema_ids_are_registered_exactly():
    assert TableIds.WORKER_ASSIGNMENTS == "tblCGYKsbFSXiVSBG"
    assert TableIds.MONTHLY_CALCULATION_BATCHES == "tblR3H5BTZeHi2gYq"
    assert TableIds.WORKER_MONTHLY_RESULTS == "tblFetHIZuK9hAtDN"
    assert WorkerAssignmentFieldIds.REFERENCE == "fldYZ1rg6MZNnYkum"
    assert MonthlyCalculationBatchFieldIds.ORIGINAL_CLOSED_BATCH == "fldB6XYs54PHEQyHO"
    assert WorkerMonthlyResultFieldIds.POSEIDON_RETAINED == "fldJceACNOtsDAWKY"


def test_write_contracts_never_write_derived_retained_amount():
    write = WorkerMonthlyResultWrite("WMR", "batch1", "wa1", Decimal("100"), Decimal("40"))
    assert write.poseidon_retained == Decimal("60")
    assert RF.POSEIDON_RETAINED not in write.to_airtable_fields()


@pytest.mark.parametrize(("action", "expected"), [
    ({"operation": "create_assignment", "payload": {
        "contact_id": "contact1", "organization_id": "org1", "start_date": "2026-08-01",
    }}, "WA:contact1:org1:2026-08-01"),
    ({"operation": "create_canonical_batch", "payload": {
        "organization_id": "org1", "month": "2026-08-01",
    }}, "MCB:org1:2026-08"),
    ({"operation": "create_adjustment_batch", "payload": {
        "original_closed_batch_id": "batch1", "adjustment_sequence": "2",
    }}, "MCB-ADJ:batch1:2"),
    ({"operation": "create_result", "payload": {
        "batch_id": "batch1", "assignment_id": "assignment1",
    }}, "WMR:batch1:assignment1"),
])
def test_recruitment_create_natural_keys_are_deterministic(action, expected):
    assert recruitment_create_natural_key(action) == expected


def test_adjustment_natural_key_requires_a_positive_sequence():
    with pytest.raises(RecruitmentValidationError, match="adjustment_sequence"):
        recruitment_create_natural_key({"operation": "create_adjustment_batch", "payload": {
            "original_closed_batch_id": "batch1",
        }})


def test_assignment_rejects_duplicate_active_contact_and_organization():
    candidate = WorkerAssignmentWrite("WA2", "contact1", "org1", "active", date(2026, 8, 1))
    with pytest.raises(RecruitmentValidationError, match="only one active"):
        validate_assignment(candidate, [assignment()])


def test_batch_requires_unique_canonical_or_closed_original_for_adjustment():
    canonical = MonthlyCalculationBatchWrite("MCB2", "org1", date(2026, 8, 1))
    with pytest.raises(RecruitmentValidationError, match="only one canonical"):
        validate_batch(canonical, [batch()])

    adjustment = MonthlyCalculationBatchWrite(
        "ADJ1", "org1", date(2026, 8, 1), MonthlyCalculationBatchType.ADJUSTMENT,
        original_closed_batch_id="batch1",
    )
    with pytest.raises(RecruitmentValidationError, match="closed original"):
        validate_batch(adjustment, [], batch(status="reviewed"))
    validate_batch(adjustment, [], batch(status=MonthlyCalculationBatchStatus.CLOSED))
    with pytest.raises(RecruitmentValidationError, match="months must match"):
        validate_batch(adjustment, [], MonthlyCalculationBatchRead(
            "batch1", "MCB", "org1", date(2026, 7, 1), "canonical", "closed"))


def test_result_enforces_identity_period_uniqueness_and_snapshot():
    candidate = WorkerMonthlyResultWrite("WMR2", "batch1", "wa1", Decimal("100"), Decimal("40"))
    with pytest.raises(RecruitmentValidationError, match="only one result"):
        validate_result(candidate, [result()], assignment(), batch())

    # A worker is employed by Poseidon; the batch is from the work/payment provider.
    validate_result(candidate, [], assignment(organization="Poseidon"),
                    batch(organization="עמי מערכות"))
    with pytest.raises(RecruitmentValidationError, match="links do not match"):
        validate_result(WorkerMonthlyResultWrite("WMR2", "batch1", "other", Decimal("100"), Decimal("40")),
                        [], assignment(), batch())
    with pytest.raises(RecruitmentValidationError, match="outside"):
        validate_result(candidate, [], assignment(start=date(2026, 9, 1)), batch())
    with pytest.raises(RecruitmentValidationError, match="snapshot is required"):
        validate_result(WorkerMonthlyResultWrite("WMR2", "batch1", "wa1", Decimal("100"),
                                                 Decimal("40"), allocation_rule_id="rule1"),
                        [], assignment(), batch())
    validate_result(candidate, [], assignment(), batch())


def test_closed_batch_and_result_financial_fields_are_immutable():
    with pytest.raises(RecruitmentValidationError, match="closed batch"):
        validate_closed_update({BF.INCOMING_PAYMENT: ["pay1"]}, {BF.INCOMING_PAYMENT: ["pay2"]},
                               batch_status="closed", entity="batch")
    with pytest.raises(RecruitmentValidationError, match="closed result"):
        validate_closed_update({RF.WORKER_DUE: 40}, {RF.WORKER_DUE: 41},
                               batch_status="closed", entity="result")
    validate_closed_update({RF.WORKER_DUE: 40}, {RF.REVIEW_NOTES: "ok"},
                           batch_status="closed", entity="result")


def test_read_contracts_parse_airtable_link_shapes():
    parsed = WorkerAssignmentRead.from_airtable({"id": "wa1", "fields": {
        AF.REFERENCE: "WA", AF.CONTACT: ["contact1"], AF.ORGANIZATION: ["org1"],
        AF.STATUS: "active", AF.START_DATE: "2026-08-01",
    }})
    assert parsed == assignment(start=date(2026, 8, 1))
