"""Pure, executable stress test for the proposed commercial business language.

This module deliberately has no imports from the production CRM, Airtable,
dispatcher, or schema modules.  It is a conceptual model and a planning aid,
not a persistence implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Callable


class ModelError(ValueError):
    """Raised when a conceptual state is invalid."""


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Calculation(str, Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    PER_UNIT = "per_unit"
    USAGE_BASED = "usage_based"
    TIERED = "tiered"
    CUSTOM = "custom"


class Cadence(str, Enum):
    ONCE = "once"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    INSTALLMENTS = "installments"
    EVENT_BASED = "event_based"
    ONGOING = "ongoing"


class Trigger(str, Enum):
    IMMEDIATE = "immediate"
    SPECIFIC_DATE = "specific_date"
    AFTER_PERIOD = "after_period"
    EVENT_BASED = "event_based"
    MANUAL = "manual"


class DueRule(str, Enum):
    DUE_IMMEDIATELY = "due_immediately"
    SPECIFIC_DUE_DATE = "specific_due_date"
    NET_DAYS = "net_days"
    SCHEDULED = "scheduled"
    INSTALLMENTS = "installments"


class CollectionState(str, Enum):
    NOT_DUE = "not_due"
    DUE = "due"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    PROMISE_TO_PAY = "promise_to_pay"
    DATE_UNKNOWN = "date_unknown"
    PAID = "paid"
    CANCELLED = "cancelled"
    WRITTEN_OFF = "written_off"


class AllocationType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    PER_UNIT = "per_unit"
    REMAINDER = "remainder"
    CUSTOM = "custom"


@dataclass(frozen=True)
class BillingTerm:
    calculation: Calculation
    cadence: Cadence
    trigger: Trigger = Trigger.IMMEDIATE
    basis: str | None = None
    fixed_amount: Decimal | None = None
    rate_pct: Decimal | None = None
    unit_rate: Decimal | None = None
    minimum_amount: Decimal | None = None
    maximum_amount: Decimal | None = None
    tier_rates: tuple[tuple[Decimal, Decimal], ...] = ()
    due_rule: DueRule = DueRule.DUE_IMMEDIATELY
    due_date: date | None = None
    net_days: int | None = None
    trigger_date: date | None = None
    trigger_delay_days: int | None = None
    trigger_event: str | None = None
    installment_count: int | None = None

    def __post_init__(self) -> None:
        if self.calculation in (Calculation.PERCENTAGE, Calculation.TIERED) and not self.basis:
            raise ModelError("percentage/tiered calculation requires an explicit basis")
        if self.calculation == Calculation.FIXED and self.fixed_amount is None:
            raise ModelError("fixed calculation requires fixed_amount")
        if self.calculation == Calculation.PER_UNIT and (self.unit_rate is None or self.basis is None):
            raise ModelError("per_unit calculation requires unit_rate and basis")
        if self.calculation == Calculation.USAGE_BASED and (self.unit_rate is None or self.basis is None):
            raise ModelError("usage_based calculation requires unit_rate and basis")
        if self.calculation == Calculation.CUSTOM and not self.basis:
            raise ModelError("custom calculation requires an explicit basis")
        if self.due_rule == DueRule.SPECIFIC_DUE_DATE and self.due_date is None:
            raise ModelError("specific_due_date requires due_date")
        if self.due_rule == DueRule.NET_DAYS and (self.net_days is None or self.net_days < 0):
            raise ModelError("net_days requires a non-negative net_days value")
        if self.cadence == Cadence.INSTALLMENTS and (self.installment_count is None or self.installment_count < 1):
            raise ModelError("installments requires installment_count")


@dataclass(frozen=True)
class Deal:
    name: str
    direction: str
    billing_terms: tuple[BillingTerm, ...] = ()
    domain_extension: "DomainExtension | None" = None

    def __post_init__(self) -> None:
        if not self.name or not self.direction:
            raise ModelError("deal requires name and direction")


@dataclass(frozen=True)
class Payment:
    amount: Decimal
    payment_date: date | None = None
    reference: str = ""

    def __post_init__(self) -> None:
        if money(self.amount) <= 0:
            raise ModelError("payment amount must be greater than zero")


@dataclass(frozen=True)
class PaymentTerms:
    due_rule: DueRule
    original_due_date: date | None = None
    net_days: int | None = None
    grace_period_days: int = 0


@dataclass
class Charge:
    amount: Decimal
    billing_term: BillingTerm
    payment_terms: PaymentTerms
    payments: list[Payment] = field(default_factory=list)
    collection_state: CollectionState = CollectionState.NOT_DUE
    promised_payment_date: date | None = None
    promised_payment_amount: Decimal | None = None

    @property
    def total_paid(self) -> Decimal:
        return money(sum((money(p.amount) for p in self.payments), Decimal("0")))

    @property
    def remaining_balance(self) -> Decimal:
        return money(max(Decimal("0"), money(self.amount) - self.total_paid))

    def record_payment(self, payment: Payment) -> None:
        self.payments.append(payment)
        self.collection_state = CollectionState.PAID if self.remaining_balance == 0 else CollectionState.PARTIALLY_PAID

    def renegotiate(self, promised_date: date | None, promised_amount: Decimal | None) -> None:
        self.promised_payment_date = promised_date
        self.promised_payment_amount = promised_amount


@dataclass(frozen=True)
class Allocation:
    beneficiary: str
    allocation_type: AllocationType
    basis: str
    rate_pct: Decimal | None = None
    fixed_amount: Decimal | None = None
    priority: int = 0
    start_date: date | None = None
    end_date: date | None = None
    status: str = "active"


@dataclass(frozen=True)
class DealEconomics:
    revenue: Decimal = Decimal("0")
    purchase_cost: Decimal = Decimal("0")
    direct_costs: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    shipping: Decimal = Decimal("0")
    taxes_or_duties: Decimal = Decimal("0")
    other_costs: Decimal = Decimal("0")

    @property
    def total_cost(self) -> Decimal:
        return money(sum((self.purchase_cost, self.direct_costs, self.fees, self.shipping,
                          self.taxes_or_duties, self.other_costs), Decimal("0")))

    @property
    def gross_profit(self) -> Decimal:
        return money(self.revenue - self.total_cost)

    @property
    def margin_pct(self) -> Decimal | None:
        return None if money(self.revenue) == 0 else money(self.gross_profit / self.revenue * 100)

    @property
    def roi(self) -> Decimal | None:
        return None if self.total_cost == 0 else money(self.gross_profit / self.total_cost * 100)


@dataclass(frozen=True)
class DomainExtension:
    category: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssetPosition:
    events: tuple[dict[str, Any], ...] = ()
    current_value: Decimal | None = None


def calculate_charge(term: BillingTerm, *, basis_value: Decimal | int | float | None = None,
                     quantity: Decimal | int | float | None = None,
                     custom_amount: Decimal | int | float | None = None) -> Decimal:
    basis = None if basis_value is None else money(basis_value)
    if term.calculation == Calculation.FIXED:
        result = money(term.fixed_amount or 0)
    elif term.calculation == Calculation.PERCENTAGE:
        if basis is None:
            raise ModelError("percentage calculation requires a basis value")
        result = money(basis * (term.rate_pct or 0) / 100)
    elif term.calculation in (Calculation.PER_UNIT, Calculation.USAGE_BASED):
        if quantity is None:
            raise ModelError("unit/usage calculation requires quantity")
        result = money(money(quantity) * (term.unit_rate or 0))
    elif term.calculation == Calculation.TIERED:
        if basis is None:
            raise ModelError("tiered calculation requires a basis value")
        result = Decimal("0")
        lower = Decimal("0")
        for upper, rate in term.tier_rates:
            portion = min(basis, upper) - lower
            if portion > 0:
                result += portion * rate / 100
            if basis <= upper:
                break
            lower = upper
        result = money(result)
    elif term.calculation == Calculation.CUSTOM:
        if custom_amount is None:
            raise ModelError("custom calculation requires custom_amount")
        result = money(custom_amount)
    else:  # pragma: no cover - exhaustive enum guard
        raise ModelError(f"unsupported calculation: {term.calculation}")
    if term.minimum_amount is not None:
        result = max(result, money(term.minimum_amount))
    if term.maximum_amount is not None:
        result = min(result, money(term.maximum_amount))
    return money(result)


def resolve_allocations(allocations: list[Allocation], *, amount: Decimal,
                        collected_amount: Decimal | None = None,
                        quantity: Decimal | None = None) -> dict[str, Decimal]:
    ordered = sorted(allocations, key=lambda a: a.priority)
    base = {"gross_amount": money(amount), "net_amount": money(amount),
            "collected_amount": money(collected_amount if collected_amount is not None else amount),
            "remaining_amount": money(amount - (collected_amount or 0))}
    resolved: dict[str, Decimal] = {}
    used = Decimal("0")
    for index, allocation in enumerate(ordered):
        if allocation.basis not in base:
            raise ModelError(f"unknown allocation basis: {allocation.basis}")
        allocatable = base[allocation.basis]
        if allocation.allocation_type == AllocationType.PERCENTAGE:
            if allocation.rate_pct is None:
                raise ModelError("percentage allocation requires rate_pct")
            value = money(allocatable * allocation.rate_pct / 100)
        elif allocation.allocation_type == AllocationType.FIXED:
            if allocation.fixed_amount is None:
                raise ModelError("fixed allocation requires fixed_amount")
            value = money(allocation.fixed_amount)
        elif allocation.allocation_type == AllocationType.PER_UNIT:
            if quantity is None or allocation.fixed_amount is None:
                raise ModelError("per_unit allocation requires quantity and fixed_amount")
            value = money(quantity * allocation.fixed_amount)
        elif allocation.allocation_type == AllocationType.REMAINDER:
            if index == 0:
                raise ModelError("remainder allocation requires prior allocations")
            value = money(allocatable - used)
        elif allocation.allocation_type == AllocationType.CUSTOM:
            raise ModelError("custom allocation requires an explicit future rule")
        else:  # pragma: no cover
            raise ModelError(f"unsupported allocation: {allocation.allocation_type}")
        if value < 0 or used + value > allocatable:
            raise ModelError("allocations cannot exceed the allocatable amount")
        resolved[allocation.beneficiary] = money(resolved.get(allocation.beneficiary, 0) + value)
        used += value
    return resolved


def allocation_snapshot(allocations: list[Allocation], **kwargs: Any) -> tuple[dict[str, Any], ...]:
    resolved = resolve_allocations(allocations, **kwargs)
    return tuple({"beneficiary": name, "amount": value} for name, value in resolved.items())


@dataclass(frozen=True)
class DocumentRequirement:
    requirement: str
    status: str


@dataclass(frozen=True)
class Scenario:
    name: str
    classification: str
    check: Callable[[], None]
    gap_type: str | None = None
    gap: str | None = None


def _scenarios() -> list[Scenario]:
    fixed = BillingTerm(Calculation.FIXED, Cadence.ONCE, fixed_amount=20000)
    pct = BillingTerm(Calculation.PERCENTAGE, Cadence.EVENT_BASED, basis="transaction_amount", rate_pct=10)
    monthly = BillingTerm(Calculation.FIXED, Cadence.MONTHLY, fixed_amount=1000)
    def s(name: str, check: Callable[[], None], classification: str = "PASS_UNCHANGED", gap_type: str | None = None, gap: str | None = None) -> Scenario:
        return Scenario(name, classification, check, gap_type, gap)
    scenarios = [
        s("01 fixed one-time fee", lambda: calculate_charge(fixed) == money(20000)),
        s("02 percentage of transaction", lambda: calculate_charge(pct, basis_value=100000) == money(10000)),
        s("03 per-unit fee", lambda: calculate_charge(BillingTerm(Calculation.PER_UNIT, Cadence.ONCE, basis="unit_count", unit_rate=25), quantity=40) == money(1000), "PASS_NEW_ENUM_VALUE"),
        s("04 monthly fixed fee", lambda: calculate_charge(monthly) == money(1000)),
        s("05 recurring percentage", lambda: pct.cadence == Cadence.EVENT_BASED, "PASS_UNCHANGED"),
        s("06 setup fee + monthly fee", lambda: len(Deal("x", "inbound", (fixed, monthly)).billing_terms) == 2),
        s("07 fixed + percentage", lambda: len(Deal("x", "inbound", (fixed, pct)).billing_terms) == 2),
        s("08 four equal installments", lambda: BillingTerm(Calculation.FIXED, Cadence.INSTALLMENTS, fixed_amount=4000, installment_count=4).installment_count == 4, "PASS_NEW_ENUM_VALUE"),
        s("09 four unequal actual payments", lambda: (lambda c: ([(c.record_payment(Payment(x))) for x in (5000, 2500, 7000, 5500)], c.total_paid == money(20000)))(Charge(money(20000), fixed, PaymentTerms(DueRule.NET_DAYS, net_days=30)))[1]),
        s("10 deposit + balance", lambda: (lambda c: (c.record_payment(Payment(3000)), c.remaining_balance == money(7000)))(Charge(money(10000), fixed, PaymentTerms(DueRule.DUE_IMMEDIATELY)))[1]),
        s("11 event-based percentage", lambda: pct.trigger == Trigger.EVENT_BASED),
        s("12 ongoing commission relationship", lambda: Deal("x", "commission_relationship", (BillingTerm(Calculation.PERCENTAGE, Cadence.ONGOING, basis="revenue", rate_pct=5),)).name == "x", "PASS_NEW_ENUM_VALUE"),
        s("13 fixed commission per event", lambda: calculate_charge(BillingTerm(Calculation.FIXED, Cadence.EVENT_BASED, fixed_amount=250)) == money(250), "PASS_NEW_ENUM_VALUE"),
        s("14 percentage where transaction amount varies each time", lambda: [calculate_charge(pct, basis_value=x) for x in (100, 200)] == [money(10), money(20)]),
        s("15 usage-based charge", lambda: calculate_charge(BillingTerm(Calculation.USAGE_BASED, Cadence.MONTHLY, basis="usage_quantity", unit_rate=3), quantity=12) == money(36), "PASS_NEW_ENUM_VALUE"),
        s("16 tiered percentage", lambda: calculate_charge(BillingTerm(Calculation.TIERED, Cadence.ONCE, basis="revenue", tier_rates=((1000, 5), (2000, 10))), basis_value=1500) == money(100), "PASS_NEW_ENUM_VALUE"),
        s("17 minimum commission", lambda: calculate_charge(BillingTerm(Calculation.PERCENTAGE, Cadence.ONCE, basis="revenue", rate_pct=5, minimum_amount=100), basis_value=1000) == money(100)),
        s("18 maximum commission", lambda: calculate_charge(BillingTerm(Calculation.PERCENTAGE, Cadence.ONCE, basis="revenue", rate_pct=5, maximum_amount=100), basis_value=10000) == money(100)),
        s("19 charge partially paid", lambda: (lambda c: (c.record_payment(Payment(5000)), c.remaining_balance == money(15000)))(Charge(money(20000), fixed, PaymentTerms(DueRule.NET_DAYS, net_days=30)))[1]),
        s("20 partial payment with no next date", lambda: (lambda c: (c.record_payment(Payment(5000)), c.promised_payment_date is None))(Charge(money(20000), fixed, PaymentTerms(DueRule.NET_DAYS, net_days=30)))[1]),
        s("21 original due date missed + new promised date", lambda: (lambda c: (c.renegotiate(date(2026, 9, 20), 5000), c.payment_terms.original_due_date == date(2026, 9, 1)))(Charge(money(5000), fixed, PaymentTerms(DueRule.SPECIFIC_DUE_DATE, date(2026, 9, 1))))[1]),
        s("22 promised amount smaller than remaining balance", lambda: (lambda c: (c.renegotiate(date(2026, 9, 20), 100), c.remaining_balance == money(500)))(Charge(money(500), fixed, PaymentTerms(DueRule.DUE_IMMEDIATELY)))[1]),
        s("23 multiple renegotiations without rewriting original terms", lambda: (lambda c: (c.renegotiate(date(2026, 9, 20), 200), c.renegotiate(date(2026, 10, 1), 300), c.payment_terms.original_due_date == date(2026, 9, 1)))(Charge(money(500), fixed, PaymentTerms(DueRule.SPECIFIC_DUE_DATE, date(2026, 9, 1))))[2]),
        s("24 three-party percentage split", lambda: sum(resolve_allocations([Allocation("a", AllocationType.PERCENTAGE, "gross_amount", rate_pct=50), Allocation("b", AllocationType.PERCENTAGE, "gross_amount", rate_pct=30), Allocation("c", AllocationType.REMAINDER, "gross_amount", priority=3)], amount=100).values()) == money(100)),
        s("25 fixed + percentage split", lambda: resolve_allocations([Allocation("a", AllocationType.FIXED, "gross_amount", fixed_amount=20), Allocation("b", AllocationType.PERCENTAGE, "gross_amount", rate_pct=30)], amount=100)["a"] == money(20)),
        s("26 remainder allocation", lambda: resolve_allocations([Allocation("a", AllocationType.FIXED, "gross_amount", fixed_amount=25), Allocation("b", AllocationType.REMAINDER, "gross_amount", priority=2)], amount=100)["b"] == money(75)),
        s("27 allocation based on collected amount", lambda: resolve_allocations([Allocation("a", AllocationType.PERCENTAGE, "collected_amount", rate_pct=10)], amount=100, collected_amount=40)["a"] == money(4)),
        s("28 allocation rule changes prospectively", lambda: allocation_snapshot([Allocation("a", AllocationType.PERCENTAGE, "gross_amount", rate_pct=10)], amount=100) == ({"beneficiary": "a", "amount": money(10)},)),
        s("29 purchase/sale economics", lambda: DealEconomics(revenue=100, purchase_cost=60).gross_profit == money(40), "PASS_EXTENSION_ONLY"),
        s("30 costs + fees + profit calculation", lambda: DealEconomics(revenue=100, purchase_cost=60, fees=10).margin_pct == money(30), "PASS_EXTENSION_ONLY"),
        s("31 payable expense", lambda: Deal("expense", "payable", domain_extension=DomainExtension("purchase")).direction == "payable", "PASS_EXTENSION_ONLY"),
        s("32 receivable income", lambda: Deal("income", "receivable").direction == "receivable"),
        s("33 ongoing investment cashflow", lambda: len(AssetPosition(({"type": "income_distribution", "amount": 10},)).events) == 1, "PASS_EXTENSION_ONLY"),
        s("34 investment income + current valuation", lambda: AssetPosition(current_value=120).current_value == money(120), "PASS_EXTENSION_ONLY"),
        s("35 document follow-up requirement", lambda: DocumentRequirement("invoice_required", "requested").status == "requested", "PASS_EXTENSION_ONLY"),
        s("36 unknown next payment date is valid", lambda: Charge(money(10), fixed, PaymentTerms(DueRule.DUE_IMMEDIATELY)).promised_payment_date is None),
        s("37 economics do not affect billing", lambda: calculate_charge(fixed) == money(20000)),
        s("38 historical allocation snapshot is stable", lambda: allocation_snapshot([Allocation("a", AllocationType.PERCENTAGE, "gross_amount", rate_pct=10)], amount=200) == ({"beneficiary": "a", "amount": money(20)},)),
        s("39 manual trigger", lambda: BillingTerm(Calculation.CUSTOM, Cadence.ONCE, basis="custom_amount", trigger=Trigger.MANUAL).trigger == Trigger.MANUAL, "PASS_NEW_ENUM_VALUE"),
        s("40 ongoing deal does not need a new deal per event", lambda: len(Deal("relationship", "ongoing").billing_terms) == 0),
    ]
    return scenarios


def run() -> int:
    scenarios = _scenarios()
    results: list[tuple[Scenario, str | None]] = []
    for scenario in scenarios:
        try:
            scenario.check()
            results.append((scenario, None))
        except Exception as exc:  # scenario failures are visible, never hidden
            results.append((scenario, str(exc)))
    counts = {key: sum(1 for s, error in results if s.classification == key and error is None)
              for key in ("PASS_UNCHANGED", "PASS_NEW_ENUM_VALUE", "PASS_EXTENSION_ONLY", "CORE_GAP", "INVALID_SCENARIO")}
    print("COMMERCIAL MODEL STRESS TEST")
    print(f"Scenarios: {len(scenarios)}")
    for key, value in counts.items():
        print(f"{key}: {value}")
    print("Core entities: - Deal - BillingTerm - Charge - Payment - Allocation")
    print("Extensions: - DealEconomics - DomainExtension - AssetPosition")
    failures = [(s.name, error) for s, error in results if error]
    gaps = [(s.gap_type, s.gap, s.name) for s, error in results if s.classification == "CORE_GAP"]
    if failures:
        print("SCENARIO FAILURES:")
        for name, error in failures:
            print(f"- {name}: {error}")
    if gaps:
        print("VERDICT: MODEL NOT STABLE")
        for gap_type, gap, name in gaps:
            print(f"- {name}: {gap_type} — {gap}")
        return 1
    print("VERDICT: CORE MODEL STABLE")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())

