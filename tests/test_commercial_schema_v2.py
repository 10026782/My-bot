"""Static guards for the add-only Commercial Schema V2 contract."""

from airtable_schema import (
    AllocationBasis,
    AllocationRuleFields,
    AllocationSnapshotFields,
    AllocationType,
    BillingTermStatus,
    ChargeFields,
    ChargeStatus,
    CollectionState,
    CommercialStatus,
    Currency,
    DealEconomicsFields,
    DealFields,
    Direction,
    DocumentRequirement,
    DocumentStatus,
    DueRule,
    OrganizationFields,
    PaymentFields,
    PaymentTermCalcType,
    PaymentTermFields,
    Tables,
)


def test_v2_tables_and_live_field_constants_are_exact():
    assert Tables.CHARGES == "Charges"
    assert Tables.ALLOCATION_RULES == "Allocation Rules"
    assert Tables.ALLOCATION_SNAPSHOTS == "Allocation Snapshots"
    assert Tables.DEAL_ECONOMICS == "Deal Economics"
    assert Tables.ORGANIZATIONS == "Organizations"
    assert OrganizationFields.NAME == "Organization Name"

    assert PaymentFields.CHARGE == "Charge"
    assert PaymentFields.CURRENCY == "Currency"
    assert PaymentFields.COUNTERPARTY_CONTACT == "Counterparty Contact"
    assert PaymentFields.COUNTERPARTY_ORGANIZATION == "Counterparty Organization"
    assert PaymentTermFields.CURRENCY == "Currency"
    assert DealFields.COUNTERPARTY_CONTACT == "Counterparty Contact"
    assert DealFields.COUNTERPARTY_ORGANIZATION == "Counterparty Organization"

    for field_group in (
        ChargeFields,
        AllocationRuleFields,
        AllocationSnapshotFields,
        DealEconomicsFields,
    ):
        values = [value for name, value in vars(field_group).items() if name.isupper()]
        assert values and all(value == value.strip() for value in values)


def test_canonical_enums_have_no_surrounding_whitespace():
    enum_groups = (
        Direction,
        Currency,
        PaymentTermCalcType,
        BillingTermStatus,
        ChargeStatus,
        CollectionState,
        CommercialStatus,
        AllocationType,
        AllocationBasis,
        DocumentRequirement,
        DocumentStatus,
        DueRule,
    )
    for group in enum_groups:
        values = [value for name, value in vars(group).items() if name.isupper()]
        assert values and all(value == value.strip() for value in values)

    assert {Currency.ILS, Currency.USD, Currency.EUR} == {"ILS", "USD", "EUR"}


def test_legacy_payment_contract_is_retained_and_distinct_from_charge():
    assert PaymentFields.REF == "reference"
    assert PaymentFields.AMOUNT == "amount"
    assert PaymentFields.STATUS == "status"
    assert PaymentFields.DEAL_LINK == "deal_id"
    assert ChargeFields.REFERENCE != PaymentFields.REF
    assert ChargeFields.AMOUNT != PaymentFields.AMOUNT
    assert PaymentFields.CHARGE == "Charge"


def test_allocation_rules_and_snapshots_are_separate_entities():
    assert Tables.ALLOCATION_RULES != Tables.ALLOCATION_SNAPSHOTS
    assert AllocationRuleFields.REFERENCE != AllocationSnapshotFields.REFERENCE
    assert AllocationRuleFields.BENEFICIARY == AllocationSnapshotFields.BENEFICIARY
    assert AllocationSnapshotFields.RESOLVED_AMOUNT == "Resolved Amount"

