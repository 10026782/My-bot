"""Tests for the isolated conceptual commercial model stress test."""

from datetime import date
from decimal import Decimal

import pytest

from tools.commercial_model_simulation import (
    Allocation, AllocationType, BillingTerm, Cadence, Calculation, Charge,
    Deal, DueRule, ModelError, Payment, PaymentTerms, _scenarios,
    calculate_charge, resolve_allocations,
)


def test_all_required_scenarios_pass():
    assert len(_scenarios()) >= 35
    for scenario in _scenarios():
        scenario.check()


def test_four_unequal_payments_total_exactly_twenty_thousand():
    term = BillingTerm(Calculation.FIXED, Cadence.ONCE, fixed_amount=20000)
    charge = Charge(Decimal("20000"), term, PaymentTerms(DueRule.DUE_IMMEDIATELY))
    for amount in (5000, 2500, 7000, 5500):
        charge.record_payment(Payment(Decimal(str(amount))))
    assert charge.total_paid == Decimal("20000.00")
    assert charge.remaining_balance == Decimal("0.00")


def test_partial_payment_preserves_agreed_amount_and_original_due_date():
    term = BillingTerm(Calculation.FIXED, Cadence.ONCE, fixed_amount=20000)
    charge = Charge(Decimal("20000"), term, PaymentTerms(DueRule.SPECIFIC_DUE_DATE, date(2026, 9, 1)))
    charge.record_payment(Payment(5000))
    charge.renegotiate(date(2026, 9, 20), 5000)
    assert charge.amount == Decimal("20000.00")
    assert charge.remaining_balance == Decimal("15000.00")
    assert charge.payment_terms.original_due_date == date(2026, 9, 1)


def test_invalid_calculations_fail_closed():
    with pytest.raises(ModelError):
        BillingTerm(Calculation.PERCENTAGE, Cadence.ONCE, rate_pct=10)
    with pytest.raises(ModelError):
        calculate_charge(BillingTerm(Calculation.PERCENTAGE, Cadence.ONCE, basis="revenue", rate_pct=10))
    with pytest.raises(ModelError):
        Payment(0)


def test_multiple_terms_and_allocation_remainder():
    deal = Deal("hybrid", "receivable", (
        BillingTerm(Calculation.FIXED, Cadence.ONCE, fixed_amount=100),
        BillingTerm(Calculation.PERCENTAGE, Cadence.MONTHLY, basis="revenue", rate_pct=5),
    ))
    assert len(deal.billing_terms) == 2
    result = resolve_allocations([
        Allocation("first", AllocationType.PERCENTAGE, "gross_amount", rate_pct=60),
        Allocation("last", AllocationType.REMAINDER, "gross_amount", priority=2),
    ], amount=100)
    assert result == {"first": Decimal("60.00"), "last": Decimal("40.00")}


def test_allocation_overflow_and_first_remainder_fail_closed():
    with pytest.raises(ModelError):
        resolve_allocations([
            Allocation("a", AllocationType.PERCENTAGE, "gross_amount", rate_pct=70),
            Allocation("b", AllocationType.PERCENTAGE, "gross_amount", rate_pct=40),
        ], amount=100)
    with pytest.raises(ModelError):
        resolve_allocations([Allocation("remainder", AllocationType.REMAINDER, "gross_amount")], amount=100)


def test_cli_scenarios_have_no_core_gaps():
    assert not [s for s in _scenarios() if s.classification == "CORE_GAP"]

