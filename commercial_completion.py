"""Pure deterministic foundation for commercial field completion.

This module owns no persistence, approval, routing, or channel behavior.  It
turns entity field contracts into deterministic missing-field and validation
decisions.  A later integration may hand a *complete* payload to a narrow
canonical writer through ActionGateway; this module must never call either.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import Enum
import math
import re
from typing import Any, Callable, Mapping

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
    ContactFields,
    Currency,
    DealType,
    DealEconomicsFields,
    DealFields,
    DealStage,
    Direction,
    DocumentRequirement,
    DocumentStatus,
    DueRule,
    LeadFields,
    OrganizationFields,
    PaymentFields,
    PaymentStatus,
    PaymentTermBasis,
    PaymentTermCadence,
    PaymentTermCalcType,
    PaymentTermFields,
    PaymentTermTrigger,
    RelationshipType,
    VATRule,
)


class CompletionError(ValueError):
    """Base class for deterministic completion failures."""


class UnknownEntityError(CompletionError):
    pass


class UnknownFieldError(CompletionError):
    pass


class InvalidValueError(CompletionError):
    pass


class CompletionBlockedError(CompletionError):
    pass


class InputType(str, Enum):
    SELECT = "select"
    LINK = "link"
    NUMBER = "number"
    CURRENCY = "currency"
    PERCENT = "percent"
    DATE = "date"
    DATETIME = "datetime"
    TEXT = "text"
    COMPUTED = "computed"


class RequiredMode(str, Enum):
    ALWAYS = "true"
    OPTIONAL = "false"
    CONDITIONAL = "conditional"


class ValueSource(str, Enum):
    EXISTING = "existing"
    INHERITED = "inherited"
    DERIVED = "derived"
    DEFAULT = "default"
    USER = "user"


NO_DEFAULT = object()
_RECORD_ID_RE = re.compile(r"^rec[A-Za-z0-9]+$")


def _class_values(namespace: type) -> tuple[str, ...]:
    return tuple(
        value for name, value in vars(namespace).items()
        if name.isupper() and isinstance(value, str)
    )


@dataclass(frozen=True)
class Condition:
    """A small, serializable requiredness predicate; no arbitrary code."""

    field_name: str
    values: tuple[Any, ...]

    def matches(self, values: Mapping[str, Any]) -> bool:
        return values.get(self.field_name) in self.values


@dataclass(frozen=True)
class FieldContract:
    field_name: str
    airtable_field: str
    input_type: InputType
    required: RequiredMode = RequiredMode.OPTIONAL
    required_when: tuple[Condition, ...] = ()
    require_all_conditions: bool = True
    source_priority: tuple[ValueSource, ...] = (
        ValueSource.EXISTING,
        ValueSource.INHERITED,
        ValueSource.DERIVED,
        ValueSource.DEFAULT,
        ValueSource.USER,
    )
    choices: tuple[str, ...] = ()
    inherited_from: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = ()
    default: Any = NO_DEFAULT
    manual_entry_allowed: bool = True
    custom_values: tuple[str, ...] = ()
    custom_followup: str | None = None
    example: str = ""
    validation: str = "type"
    help_text: str = ""
    persisted: bool = True

    @property
    def is_computed(self) -> bool:
        return self.input_type == InputType.COMPUTED

    def is_required(self, values: Mapping[str, Any]) -> bool:
        if self.required == RequiredMode.ALWAYS:
            return True
        if self.required == RequiredMode.OPTIONAL:
            return False
        if not self.required_when:
            return False
        matches = (condition.matches(values) for condition in self.required_when)
        return all(matches) if self.require_all_conditions else any(matches)


@dataclass(frozen=True)
class EntityContract:
    entity: str
    fields: tuple[FieldContract, ...]
    one_of_required: tuple[tuple[str, ...], ...] = ()
    system_only: bool = False
    unresolved_rules: tuple[str, ...] = ()

    def field(self, name: str) -> FieldContract:
        for contract in self.fields:
            if contract.field_name == name:
                return contract
        raise UnknownFieldError(f"{self.entity!r} has no field {name!r}")


def _f(
    name: str,
    airtable_field: str,
    input_type: InputType,
    *,
    required: RequiredMode = RequiredMode.OPTIONAL,
    when: tuple[Condition, ...] = (),
    require_all_conditions: bool = True,
    choices: tuple[str, ...] = (),
    inherit: tuple[str, ...] = (),
    derived: tuple[str, ...] = (),
    default: Any = NO_DEFAULT,
    manual: bool = True,
    custom_values: tuple[str, ...] = (),
    custom_followup: str | None = None,
    example: str = "",
    validation: str = "type",
    help_text: str = "",
    persisted: bool = True,
) -> FieldContract:
    return FieldContract(
        field_name=name,
        airtable_field=airtable_field,
        input_type=input_type,
        required=required,
        required_when=when,
        require_all_conditions=require_all_conditions,
        choices=choices,
        inherited_from=inherit,
        derived_from=derived,
        default=default,
        manual_entry_allowed=manual,
        custom_values=custom_values,
        custom_followup=custom_followup,
        example=example,
        validation=validation,
        help_text=help_text,
        persisted=persisted,
    )


ALWAYS = RequiredMode.ALWAYS
CONDITIONAL = RequiredMode.CONDITIONAL

_DIRECTIONS = _class_values(Direction)
_CURRENCIES = _class_values(Currency)
_RELATIONSHIPS = _class_values(RelationshipType)
_COMMERCIAL_STATUSES = _class_values(CommercialStatus)
_DEAL_TYPES = _class_values(DealType)
_CALC_TYPES = _class_values(PaymentTermCalcType)
_CALC_BASES = _class_values(PaymentTermBasis)
_CADENCES = _class_values(PaymentTermCadence)
_TRIGGERS = _class_values(PaymentTermTrigger)
_DUE_RULES = _class_values(DueRule)
_TERM_STATUSES = _class_values(BillingTermStatus)
_CHARGE_STATUSES = _class_values(ChargeStatus)
_COLLECTION_STATES = _class_values(CollectionState)
_ALLOCATION_TYPES = _class_values(AllocationType)
_ALLOCATION_BASES = _class_values(AllocationBasis)
_DOCUMENT_REQUIREMENTS = _class_values(DocumentRequirement)
_DOCUMENT_STATUSES = _class_values(DocumentStatus)
_VAT_RULES = _class_values(VATRule)


ENTITY_CONTRACTS: dict[str, EntityContract] = {
    "lead": EntityContract("lead", (
        _f("name", LeadFields.NAME, InputType.TEXT, required=ALWAYS, example="Dana Cohen"),
        _f("phone", LeadFields.PHONE, InputType.TEXT, required=ALWAYS, validation="phone", example="050-123-4567"),
        _f("domain", LeadFields.DOMAIN, InputType.TEXT, inherit=("domain",)),
        _f("owner", LeadFields.OWNER, InputType.LINK, inherit=("owner", "owner_id"), validation="record_id"),
        _f("source", LeadFields.SOURCE, InputType.TEXT, inherit=("source",)),
        _f("channel", LeadFields.CHANNEL, InputType.TEXT, inherit=("channel",)),
    ), unresolved_rules=("Lead intake remains owned by the existing lead capture contract.",)),
    "contact": EntityContract("contact", (
        _f("name", ContactFields.NAME, InputType.TEXT, required=ALWAYS, inherit=("name",), example="Dana Cohen"),
        _f("phone", ContactFields.PHONE, InputType.TEXT, required=ALWAYS, inherit=("phone",), validation="phone", example="050-123-4567"),
        _f("email", ContactFields.EMAIL, InputType.TEXT, inherit=("email",), validation="email"),
        _f("company", ContactFields.COMPANY, InputType.TEXT, inherit=("company", "organization_name")),
        _f("role_category", ContactFields.ROLE_CATEGORY, InputType.SELECT, choices=("lead", "broker", "expert", "supplier", "operator", "partner", "investor", "client", "other")),
    ), unresolved_rules=("Contact Notes are rejected by the current canonical Contact gate.",)),
    "organization": EntityContract("organization", (
        _f("organization_name", OrganizationFields.NAME, InputType.TEXT, required=ALWAYS, inherit=("organization_name", "company"), example="Acme Ltd"),
    )),
    "deal": EntityContract("deal", (
        # BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION (production-verified,
        # 06/09/2026): deal_type/relationship_type/currency/commercial_status/
        # expected_value used to be required=ALWAYS here, turning the Deal
        # completion flow into a mandatory full-record gate — the canonical
        # writer (commercial_crm.create_deal()) has always treated every one
        # of these as optional kwargs (`if x: fields[...] = x`), so this was
        # a completion-contract-only over-restriction, never a real writer/
        # schema requirement. A Deal now only gates creation on name/domain/
        # owner/counterparty (business-required); these five are collected
        # as post-creation enrichment instead (see the "deal_enrichment"
        # contract below and commercial_completion_routing.py's enrichment
        # offer/loop) and never block or roll back the already-created Deal.
        _f("name", DealFields.NAME, InputType.TEXT, required=ALWAYS, inherit=("deal_name", "name"), example="Annual maintenance agreement"),
        _f("domain", DealFields.DOMAIN, InputType.TEXT, required=ALWAYS, inherit=("domain",)),
        _f("owner", DealFields.OWNER, InputType.LINK, required=ALWAYS, inherit=("owner", "owner_id"), validation="record_id"),
        _f("origin_lead", DealFields.ORIGIN_LEAD, InputType.LINK, inherit=("lead_id", "origin_lead_id"), validation="record_id"),
        _f("counterparty_contact", DealFields.COUNTERPARTY_CONTACT, InputType.LINK, inherit=("contact_id", "counterparty_contact"), validation="record_id"),
        _f("counterparty_organization", DealFields.COUNTERPARTY_ORGANIZATION, InputType.LINK, inherit=("organization_id", "counterparty_organization"), validation="record_id"),
        _f("deal_type", DealFields.DEAL_TYPE_CODE, InputType.SELECT, choices=_DEAL_TYPES, example=DealType.SERVICE),
        _f("relationship_type", DealFields.RELATIONSHIP_TYPE, InputType.SELECT, choices=_RELATIONSHIPS),
        _f("currency", DealFields.CURRENCY, InputType.SELECT, choices=_CURRENCIES),
        _f("commercial_status", DealFields.COMMERCIAL_STATUS, InputType.SELECT, choices=_COMMERCIAL_STATUSES),
        _f("expected_value", DealFields.AMOUNT, InputType.CURRENCY, inherit=("expected_value", "amount"), validation="positive"),
        _f("stage", DealFields.STAGE, InputType.SELECT, choices=(DealStage.OPPORTUNITY, DealStage.NEGOTIATION, DealStage.CLOSED_WIN, DealStage.CLOSED_LOSS), default=DealStage.OPPORTUNITY),
        _f("start_date", DealFields.START_DATE, InputType.DATE),
        _f("notes", DealFields.NOTES, InputType.TEXT),
        _f("total_charged", DealFields.TOTAL_CHARGED, InputType.COMPUTED, manual=False, persisted=False),
        _f("total_collected", DealFields.TOTAL_COLLECTED, InputType.COMPUTED, manual=False, persisted=False),
        _f("outstanding", DealFields.OUTSTANDING, InputType.COMPUTED, manual=False, persisted=False),
    ), one_of_required=(("counterparty_contact", "counterparty_organization"),)),
    "payment_term": EntityContract("payment_term", (
        _f("deal", PaymentTermFields.DEAL, InputType.LINK, required=ALWAYS, inherit=("deal_id", "deal"), validation="record_id"),
        _f("name", PaymentTermFields.NAME, InputType.TEXT, default="Payment Term"),
        _f("direction", PaymentTermFields.DIRECTION, InputType.SELECT, required=ALWAYS, inherit=("direction",), choices=_DIRECTIONS),
        _f("calculation_type", PaymentTermFields.CALC_TYPE_CODE, InputType.SELECT, required=ALWAYS, choices=_CALC_TYPES),
        _f("fixed_amount", PaymentTermFields.FIXED_AMOUNT, InputType.CURRENCY, required=CONDITIONAL, when=(Condition("calculation_type", (PaymentTermCalcType.FIXED,)),), validation="positive"),
        _f("rate_pct", PaymentTermFields.RATE_PCT, InputType.PERCENT, required=CONDITIONAL, when=(Condition("calculation_type", (PaymentTermCalcType.PERCENTAGE,)),), validation="positive_percent"),
        _f("calculation_basis", PaymentTermFields.CALC_BASIS_CODE, InputType.SELECT, required=CONDITIONAL, when=(Condition("calculation_type", (PaymentTermCalcType.PERCENTAGE, PaymentTermCalcType.PER_UNIT, PaymentTermCalcType.USAGE_BASED, PaymentTermCalcType.TIERED, PaymentTermCalcType.CUSTOM)),), choices=_CALC_BASES),
        _f("tier_configuration", PaymentTermFields.TIER_CONFIGURATION, InputType.TEXT, required=CONDITIONAL, when=(Condition("calculation_type", (PaymentTermCalcType.TIERED,)),)),
        _f("custom_calculation_rule", PaymentTermFields.CUSTOM_CALCULATION_RULE, InputType.TEXT, required=CONDITIONAL, when=(Condition("calculation_type", (PaymentTermCalcType.CUSTOM,)),)),
        _f("unit_rate", PaymentTermFields.UNIT_RATE, InputType.CURRENCY, required=CONDITIONAL, when=(Condition("calculation_type", (PaymentTermCalcType.PER_UNIT, PaymentTermCalcType.USAGE_BASED)),), validation="positive"),
        _f("minimum_amount", PaymentTermFields.MINIMUM_AMOUNT, InputType.CURRENCY, validation="non_negative"),
        _f("maximum_amount", PaymentTermFields.MAXIMUM_AMOUNT, InputType.CURRENCY, validation="non_negative"),
        _f("cadence", PaymentTermFields.CADENCE_CODE, InputType.SELECT, choices=_CADENCES, default=PaymentTermCadence.ONCE),
        _f("installment_count", PaymentTermFields.INSTALLMENT_COUNT, InputType.NUMBER, required=CONDITIONAL, when=(Condition("cadence", (PaymentTermCadence.INSTALLMENTS,)), Condition("due_rule", (DueRule.INSTALLMENTS,))), require_all_conditions=False, validation="positive_integer"),
        _f("trigger_type", PaymentTermFields.TRIGGER_TYPE_CODE, InputType.SELECT, choices=_TRIGGERS, default=PaymentTermTrigger.IMMEDIATE),
        _f("trigger_date", PaymentTermFields.TRIGGER_DATE, InputType.DATE, required=CONDITIONAL, when=(Condition("trigger_type", (PaymentTermTrigger.SPECIFIC_DATE,)),)),
        _f("trigger_delay_days", PaymentTermFields.TRIGGER_DELAY_DAYS, InputType.NUMBER, required=CONDITIONAL, when=(Condition("trigger_type", (PaymentTermTrigger.AFTER_PERIOD,)),), validation="non_negative_integer"),
        _f("trigger_event", PaymentTermFields.TRIGGER_EVENT, InputType.TEXT, required=CONDITIONAL, when=(Condition("trigger_type", (PaymentTermTrigger.EVENT_BASED,)),)),
        _f("due_rule", PaymentTermFields.DUE_RULE, InputType.SELECT, choices=_DUE_RULES, default=DueRule.DUE_IMMEDIATELY),
        _f("specific_due_date", PaymentTermFields.SPECIFIC_DUE_DATE, InputType.DATE, required=CONDITIONAL, when=(Condition("due_rule", (DueRule.SPECIFIC_DUE_DATE,)),)),
        _f("schedule_anchor_date", PaymentTermFields.SCHEDULE_ANCHOR_DATE, InputType.DATE, required=CONDITIONAL, when=(Condition("due_rule", (DueRule.SCHEDULED, DueRule.INSTALLMENTS)),)),
        _f("net_days", PaymentTermFields.NET_DAYS, InputType.NUMBER, required=CONDITIONAL, when=(Condition("due_rule", (DueRule.NET_DAYS,)),), validation="non_negative_integer"),
        _f("grace_period_days", PaymentTermFields.GRACE_PERIOD_DAYS, InputType.NUMBER, default=0, validation="non_negative_integer"),
        _f("currency", PaymentTermFields.CURRENCY, InputType.SELECT, required=ALWAYS, inherit=("currency",), choices=_CURRENCIES),
        _f("status", PaymentTermFields.STATUS, InputType.SELECT, choices=_TERM_STATUSES, default=BillingTermStatus.DRAFT),
        _f("next_due_date", PaymentTermFields.NEXT_DUE_DATE, InputType.COMPUTED, derived=("due_rule", "trigger", "cadence"), manual=False),
        _f("vat_rule", PaymentTermFields.VAT_RULE, InputType.SELECT, choices=_VAT_RULES, default=VATRule.NONE),
        _f("start_date", PaymentTermFields.START_DATE, InputType.DATE),
        _f("end_date", PaymentTermFields.END_DATE, InputType.DATE),
        _f("notes", PaymentTermFields.NOTES, InputType.TEXT),
    )),
    "charge": EntityContract("charge", (
        _f("reference", ChargeFields.REFERENCE, InputType.TEXT),
        _f("deal", ChargeFields.DEAL, InputType.LINK, required=ALWAYS, inherit=("deal_id", "deal"), validation="record_id"),
        _f("billing_term", ChargeFields.BILLING_TERM, InputType.LINK, inherit=("payment_term_id", "billing_term"), validation="record_id"),
        _f("direction", ChargeFields.DIRECTION, InputType.SELECT, required=ALWAYS, inherit=("direction",), choices=_DIRECTIONS),
        _f("amount", ChargeFields.AMOUNT, InputType.CURRENCY, required=ALWAYS, validation="positive"),
        _f("currency", ChargeFields.CURRENCY_CODE, InputType.SELECT, required=ALWAYS, inherit=("currency",), choices=_CURRENCIES),
        _f("original_due_date", ChargeFields.ORIGINAL_DUE_DATE, InputType.DATE, inherit=("original_due_date", "due_date")),
        _f("current_expected_date", ChargeFields.CURRENT_EXPECTED_DATE, InputType.DATE),
        _f("status", ChargeFields.STATUS, InputType.SELECT, choices=_CHARGE_STATUSES, default=ChargeStatus.DRAFT),
        _f("collection_state", ChargeFields.COLLECTION_STATE, InputType.SELECT, choices=_COLLECTION_STATES, default=CollectionState.NOT_DUE),
        _f("base_amount", ChargeFields.BASE_AMOUNT, InputType.CURRENCY, validation="non_negative"),
        _f("rate_pct", ChargeFields.RATE_PCT, InputType.PERCENT),
        _f("quantity", ChargeFields.QUANTITY, InputType.NUMBER, validation="positive"),
        _f("unit_rate", ChargeFields.UNIT_RATE, InputType.CURRENCY, validation="positive"),
        _f("vat_rule", ChargeFields.VAT_RULE, InputType.SELECT, choices=_VAT_RULES, default=VATRule.NONE),
        _f("vat_amount", ChargeFields.VAT_AMOUNT, InputType.CURRENCY, validation="non_negative"),
        _f("trigger_evidence", ChargeFields.TRIGGER_EVIDENCE, InputType.TEXT, manual=False, derived=("billing_term", "trigger_context")),
        _f("original_terms_snapshot", ChargeFields.ORIGINAL_TERMS_SNAPSHOT, InputType.TEXT, manual=False, derived=("billing_term",)),
        _f("total_paid", ChargeFields.TOTAL_PAID, InputType.COMPUTED, manual=False),
        _f("remaining_balance", ChargeFields.REMAINING_BALANCE, InputType.COMPUTED, manual=False),
        _f("promised_payment_date", ChargeFields.PROMISED_PAYMENT_DATE, InputType.DATE),
        _f("promised_payment_amount", ChargeFields.PROMISED_PAYMENT_AMOUNT, InputType.CURRENCY, validation="positive"),
        _f("document_requirement", ChargeFields.DOCUMENT_REQUIREMENT, InputType.SELECT, choices=_DOCUMENT_REQUIREMENTS, default=DocumentRequirement.NONE),
        _f("document_status", ChargeFields.DOCUMENT_STATUS, InputType.SELECT, choices=_DOCUMENT_STATUSES, derived=("document_requirement",), manual=False),
        _f("notes", ChargeFields.NOTES, InputType.TEXT),
    )),
    "payment": EntityContract("payment", (
        _f("charge", PaymentFields.CHARGE, InputType.LINK, required=ALWAYS, inherit=("charge_id", "charge"), validation="record_id"),
        _f("amount", PaymentFields.AMOUNT, InputType.CURRENCY, required=ALWAYS, validation="positive"),
        _f("paid_at", PaymentFields.PAID_AT, InputType.DATE, required=ALWAYS),
        _f("direction", PaymentFields.DIRECTION, InputType.SELECT, required=ALWAYS, inherit=("direction",), choices=_DIRECTIONS),
        _f("currency", PaymentFields.CURRENCY, InputType.SELECT, required=ALWAYS, inherit=("currency",), choices=_CURRENCIES),
        _f("status", PaymentFields.STATUS, InputType.SELECT, choices=(PaymentStatus.RECEIVED,), default=PaymentStatus.RECEIVED, manual=False),
        _f("reference", PaymentFields.REF, InputType.TEXT),
        _f("method", PaymentFields.METHOD, InputType.TEXT),
        _f("deal", PaymentFields.DEAL_LINK, InputType.LINK, inherit=("deal_id", "deal"), validation="record_id"),
        _f("payment_term", PaymentFields.PAYMENT_TERM, InputType.LINK, inherit=("payment_term_id", "billing_term"), validation="record_id"),
        _f("counterparty_contact", PaymentFields.COUNTERPARTY_CONTACT, InputType.LINK, inherit=("counterparty_contact", "contact_id"), validation="record_id"),
        _f("counterparty_organization", PaymentFields.COUNTERPARTY_ORGANIZATION, InputType.LINK, inherit=("counterparty_organization", "organization_id"), validation="record_id"),
        _f("document_requirement", PaymentFields.DOCUMENT_REQUIREMENT, InputType.SELECT, choices=_DOCUMENT_REQUIREMENTS, default=DocumentRequirement.NONE),
        _f("document_status", PaymentFields.DOCUMENT_STATUS, InputType.SELECT, choices=_DOCUMENT_STATUSES, derived=("document_requirement",), manual=False),
        _f("notes", PaymentFields.NOTES, InputType.TEXT),
    ), unresolved_rules=("The existing create_payment writer is legacy-shaped and must not receive this payload.",)),
    "allocation_rule": EntityContract("allocation_rule", (
        _f("reference", AllocationRuleFields.REFERENCE, InputType.TEXT),
        _f("deal", AllocationRuleFields.DEAL, InputType.LINK, required=ALWAYS, inherit=("deal_id", "deal"), validation="record_id"),
        _f("billing_term", AllocationRuleFields.BILLING_TERM, InputType.LINK, inherit=("payment_term_id", "billing_term"), validation="record_id"),
        _f("charge", AllocationRuleFields.CHARGE, InputType.LINK, inherit=("charge_id", "charge"), validation="record_id"),
        _f("beneficiary_contact", AllocationRuleFields.BENEFICIARY_CONTACT, InputType.LINK, inherit=("beneficiary_contact", "contact_id"), validation="record_id"),
        _f("beneficiary_organization", AllocationRuleFields.BENEFICIARY_ORGANIZATION, InputType.LINK, inherit=("beneficiary_organization", "organization_id"), validation="record_id"),
        _f("allocation_type", AllocationRuleFields.ALLOCATION_TYPE, InputType.SELECT, required=ALWAYS, choices=_ALLOCATION_TYPES),
        _f("allocation_basis", AllocationRuleFields.ALLOCATION_BASIS, InputType.SELECT, required=ALWAYS, choices=_ALLOCATION_BASES),
        _f("rate_pct", AllocationRuleFields.RATE_PCT, InputType.PERCENT, required=CONDITIONAL, when=(Condition("allocation_type", (AllocationType.PERCENTAGE,)),), validation="positive_percent"),
        _f("fixed_amount", AllocationRuleFields.FIXED_AMOUNT, InputType.CURRENCY, required=CONDITIONAL, when=(Condition("allocation_type", (AllocationType.FIXED,)),), validation="positive"),
        _f("unit_rate", AllocationRuleFields.UNIT_RATE, InputType.CURRENCY, required=CONDITIONAL, when=(Condition("allocation_type", (AllocationType.PER_UNIT,)),), validation="positive"),
        _f("priority", AllocationRuleFields.PRIORITY, InputType.NUMBER, default=0, validation="non_negative_integer"),
        _f("start_date", AllocationRuleFields.START_DATE, InputType.DATE),
        _f("end_date", AllocationRuleFields.END_DATE, InputType.DATE),
        _f("status", AllocationRuleFields.STATUS, InputType.SELECT, choices=_TERM_STATUSES, default=BillingTermStatus.DRAFT),
        _f("notes", AllocationRuleFields.NOTES, InputType.TEXT),
    ), one_of_required=(("beneficiary_contact", "beneficiary_organization"),), unresolved_rules=("custom allocation has no approved explicit custom-rule field",)),
    "allocation_snapshot": EntityContract("allocation_snapshot", (
        _f("reference", AllocationSnapshotFields.REFERENCE, InputType.COMPUTED, manual=False),
        _f("charge", AllocationSnapshotFields.CHARGE, InputType.COMPUTED, required=ALWAYS, derived=("charge",), manual=False),
        _f("allocation_rule", AllocationSnapshotFields.ALLOCATION_RULE, InputType.COMPUTED, required=ALWAYS, derived=("allocation_rule",), manual=False),
        _f("beneficiary_contact", AllocationSnapshotFields.BENEFICIARY_CONTACT, InputType.COMPUTED, derived=("allocation_rule.beneficiary_contact",), manual=False),
        _f("beneficiary_organization", AllocationSnapshotFields.BENEFICIARY_ORGANIZATION, InputType.COMPUTED, derived=("allocation_rule.beneficiary_organization",), manual=False),
        _f("resolved_amount", AllocationSnapshotFields.RESOLVED_AMOUNT, InputType.COMPUTED, required=ALWAYS, derived=("allocation_rule", "basis_amount"), manual=False),
        _f("basis_amount", AllocationSnapshotFields.BASIS_AMOUNT, InputType.COMPUTED, required=ALWAYS, derived=("charge", "allocation_basis"), manual=False),
        _f("resolved_at", AllocationSnapshotFields.RESOLVED_AT, InputType.COMPUTED, required=ALWAYS, derived=("clock",), manual=False),
        _f("snapshot_data", AllocationSnapshotFields.SNAPSHOT_DATA, InputType.COMPUTED, derived=("allocation_rule",), manual=False),
    ), system_only=True),
    "deal_economics": EntityContract("deal_economics", (
        _f("reference", DealEconomicsFields.REFERENCE, InputType.TEXT),
        _f("deal", DealEconomicsFields.DEAL, InputType.LINK, required=ALWAYS, inherit=("deal_id", "deal"), validation="record_id"),
        _f("revenue", DealEconomicsFields.REVENUE, InputType.CURRENCY, default=0, validation="non_negative"),
        _f("purchase_cost", DealEconomicsFields.PURCHASE_COST, InputType.CURRENCY, default=0, validation="non_negative"),
        _f("direct_costs", DealEconomicsFields.DIRECT_COSTS, InputType.CURRENCY, default=0, validation="non_negative"),
        _f("fees", DealEconomicsFields.FEES, InputType.CURRENCY, default=0, validation="non_negative"),
        _f("shipping", DealEconomicsFields.SHIPPING, InputType.CURRENCY, default=0, validation="non_negative"),
        _f("taxes_duties", DealEconomicsFields.TAXES_DUTIES, InputType.CURRENCY, default=0, validation="non_negative"),
        _f("other_costs", DealEconomicsFields.OTHER_COSTS, InputType.CURRENCY, default=0, validation="non_negative"),
        _f("total_cost", DealEconomicsFields.TOTAL_COST, InputType.COMPUTED, manual=False),
        _f("gross_profit", DealEconomicsFields.GROSS_PROFIT, InputType.COMPUTED, manual=False),
        _f("margin_pct", DealEconomicsFields.MARGIN_PCT, InputType.COMPUTED, manual=False),
        _f("roi", DealEconomicsFields.ROI, InputType.COMPUTED, manual=False),
        _f("notes", DealEconomicsFields.NOTES, InputType.TEXT),
    ), unresolved_rules=("Margin % and ROI are live percent fields, not formulas; derive before any future write.",)),
}


def _is_present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != ()


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise InvalidValueError("boolean is not a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidValueError("value must be numeric") from exc
    if not math.isfinite(result):
        raise InvalidValueError("value must be finite")
    return result


def _validate_date(value: Any, *, with_time: bool = False) -> None:
    if not isinstance(value, str):
        raise InvalidValueError("date values must use ISO text")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00")) if with_time else date.fromisoformat(value)
    except ValueError as exc:
        expected = "ISO datetime" if with_time else "YYYY-MM-DD"
        raise InvalidValueError(f"value must be {expected}") from exc


def validate_value(contract: FieldContract, value: Any) -> None:
    """Validate one value against one contract; return None or fail closed."""

    if contract.is_computed or not contract.manual_entry_allowed:
        raise InvalidValueError(f"{contract.field_name} is not user-entered")
    if not _is_present(value):
        raise InvalidValueError(f"{contract.field_name} may not be empty")
    if contract.input_type == InputType.SELECT:
        if value not in contract.choices:
            raise InvalidValueError(
                f"{contract.field_name} must be one of {contract.choices!r}"
            )
    elif contract.input_type == InputType.LINK:
        if not isinstance(value, str) or not _RECORD_ID_RE.fullmatch(value):
            raise InvalidValueError(f"{contract.field_name} must be a canonical record id")
    elif contract.input_type in (InputType.NUMBER, InputType.CURRENCY, InputType.PERCENT):
        number = _number(value)
        if contract.validation in ("positive", "positive_integer", "positive_percent") and number <= 0:
            raise InvalidValueError(f"{contract.field_name} must be greater than zero")
        if contract.validation in ("non_negative", "non_negative_integer") and number < 0:
            raise InvalidValueError(f"{contract.field_name} may not be negative")
        if contract.validation in ("positive_integer", "non_negative_integer") and not number.is_integer():
            raise InvalidValueError(f"{contract.field_name} must be an integer")
        if contract.input_type == InputType.PERCENT and not 0 <= number <= 100:
            raise InvalidValueError(f"{contract.field_name} must be between 0 and 100")
    elif contract.input_type == InputType.DATE:
        _validate_date(value)
    elif contract.input_type == InputType.DATETIME:
        _validate_date(value, with_time=True)
    elif contract.input_type == InputType.TEXT:
        if not isinstance(value, str) or not value.strip():
            raise InvalidValueError(f"{contract.field_name} must be non-empty text")

    if contract.validation == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value)):
        raise InvalidValueError("invalid email")
    if contract.validation == "phone" and len(re.sub(r"\D", "", str(value))) < 7:
        raise InvalidValueError("invalid phone")
    if contract.validation == "record_id" and not _RECORD_ID_RE.fullmatch(str(value)):
        raise InvalidValueError("invalid record id")


def _coerce_value(contract: FieldContract, value: Any) -> Any:
    """
    BUG-COMPLETION-NUMERIC-STRING-422 (production-verified, 06/09/2026): a
    Deal create failed with Airtable 422 INVALID_VALUE_FOR_COLUMN on "סכום"
    (DealFields.AMOUNT) after the owner answered the free-text amount
    prompt with "100000". Root cause: validate_value() above calls
    _number(value) purely to VALIDATE a NUMBER/CURRENCY/PERCENT answer —
    it never returns the coerced number — so apply_answer() stored the
    original, un-coerced value (the raw user-text digit string) straight
    into current_values. That string then flowed unchanged through
    resolved_values()/complete_payload() into the Airtable writer, which
    sent it to a Number/Currency column as a JSON string; Airtable's API
    requires a JSON number there and rejects a string with a 422.

    Coerce here, once validate_value() has already proven the value is a
    valid number, so every persisted/resolved value for a NUMBER/CURRENCY/
    PERCENT field is the correctly-typed Python number — never the raw
    input text — regardless of caller (free-text answer_human(), a direct
    canonical answer(), or a test fixture passing an int/float already).
    "_integer" validations coerce to int (matching what those Airtable
    fields — installment counts, day counts, priority — actually expect);
    everything else stays float, matching crm_create_deal()'s own
    `amount: float | None` signature.
    """
    if contract.input_type in (InputType.NUMBER, InputType.CURRENCY, InputType.PERCENT):
        number = _number(value)
        if contract.validation in ("positive_integer", "non_negative_integer"):
            return int(number)
        return number
    return value


def _derive_document_status(values: Mapping[str, Any]) -> Any:
    requirement = values.get("document_requirement")
    if requirement == DocumentRequirement.NONE:
        return DocumentStatus.NOT_REQUIRED
    if requirement in _DOCUMENT_REQUIREMENTS:
        return DocumentStatus.REQUIRED
    return None


_DERIVERS: dict[str, Callable[[Mapping[str, Any]], Any]] = {
    "document_status": _derive_document_status,
}


@dataclass(frozen=True)
class CommercialCompletionWriter:
    """Deterministic completion state for exactly one target entity."""

    target_entity: str
    current_values: Mapping[str, Any] = field(default_factory=dict)
    source_context: Mapping[str, Any] = field(default_factory=dict)
    identity: Mapping[str, Any] = field(default_factory=dict)
    contracts: Mapping[str, EntityContract] = field(default_factory=lambda: ENTITY_CONTRACTS)

    @property
    def contract(self) -> EntityContract:
        try:
            return self.contracts[self.target_entity]
        except KeyError as exc:
            raise UnknownEntityError(self.target_entity) from exc

    def resolved_values(self) -> dict[str, Any]:
        current = dict(self.current_values)
        values: dict[str, Any] = {}
        context = {**dict(self.source_context), **dict(self.identity)}
        for contract in self.contract.fields:
            for source in contract.source_priority:
                if source in (ValueSource.EXISTING, ValueSource.USER):
                    candidate = current.get(contract.field_name)
                elif source == ValueSource.INHERITED:
                    candidate = next(
                        (context[key] for key in contract.inherited_from if _is_present(context.get(key))),
                        None,
                    )
                elif source == ValueSource.DERIVED:
                    deriver = _DERIVERS.get(contract.field_name)
                    candidate = deriver(values) if deriver is not None and contract.derived_from else None
                elif source == ValueSource.DEFAULT:
                    candidate = contract.default if contract.default is not NO_DEFAULT else None
                else:  # pragma: no cover - exhaustive enum guard
                    candidate = None
                if _is_present(candidate):
                    values[contract.field_name] = candidate
                    break
        return values

    def _assert_supported(self, values: Mapping[str, Any]) -> None:
        """Fail closed for approved enums whose extra field contract is absent."""

        if self.target_entity == "allocation_rule":
            if values.get("allocation_type") == AllocationType.CUSTOM:
                raise CompletionBlockedError(
                    "custom allocation has no approved explicit detail-field contract"
                )
            if values.get("allocation_basis") == AllocationBasis.CUSTOM:
                raise CompletionBlockedError(
                    "custom allocation basis has no approved explicit detail-field contract"
                )

    def missing_fields(self, *, limit: int | None = None) -> tuple[FieldContract, ...]:
        if self.contract.system_only:
            raise CompletionBlockedError(f"{self.target_entity} is system-generated")
        values = self.resolved_values()
        self._assert_supported(values)
        missing: list[FieldContract] = []
        for contract in self.contract.fields:
            if contract.is_computed or not contract.manual_entry_allowed:
                continue
            if contract.is_required(values) and not _is_present(values.get(contract.field_name)):
                missing.append(contract)

        for controller in self.contract.fields:
            if (
                controller.custom_followup
                and values.get(controller.field_name) in controller.custom_values
                and not _is_present(values.get(controller.custom_followup))
            ):
                followup = self.contract.field(controller.custom_followup)
                if followup not in missing:
                    missing.append(followup)

        for group in self.contract.one_of_required:
            if any(_is_present(values.get(name)) for name in group):
                continue
            representative = self.contract.field(group[0])
            if representative not in missing:
                missing.append(representative)

        ordered = tuple(
            contract for contract in self.contract.fields if contract in missing
        )
        return ordered if limit is None else ordered[: max(0, limit)]

    def next_field(self) -> FieldContract | None:
        missing = self.missing_fields(limit=1)
        return missing[0] if missing else None

    def apply_answer(self, field_name: str, value: Any) -> "CommercialCompletionWriter":
        contract = self.contract.field(field_name)
        validate_value(contract, value)
        values = dict(self.current_values)
        values[field_name] = _coerce_value(contract, value)
        return replace(self, current_values=values)

    def is_complete(self) -> bool:
        return not self.missing_fields()

    def complete_payload(self) -> dict[str, Any]:
        missing = self.missing_fields()
        if missing:
            raise CompletionBlockedError(
                "missing required fields: " + ", ".join(field.field_name for field in missing)
            )
        values = self.resolved_values()
        return {
            field.airtable_field: values[field.field_name]
            for field in self.contract.fields
            if field.persisted and not field.is_computed and _is_present(values.get(field.field_name))
        }


@dataclass(frozen=True)
class _CompletionFrame:
    writer: CommercialCompletionWriter
    return_field: str | None = None


_CONTINUATION_REF_VERSION = 1
_CONTINUATION_REF_TYPE_COMMERCIAL_COMPLETION = "commercial_completion"


@dataclass(frozen=True)
class ContinuationRef:
    """Typed, versioned pointer from a queued approval (ActionContract) back
    to the exact nested CompletionSession it will resume — never a
    duplicate/serialized copy of the session itself (that stays owned by
    session_store, the single source of truth). Deliberately a closed,
    explicit shape rather than a free dict on ActionContract, so a future
    field never silently drifts between the writer and reader side.

    session_key: the exact identifier session_store.lead_sessions'
        commercial-completion API (get_commercial_completion/
        set_commercial_completion) expects as its `sender` argument — in
        production today, the raw chat_id string the parent completion's
        queue() callback already closes over, NOT session_store's internal
        composite "tenant:channel:sender" key (that key is an
        implementation detail computed inside PersistentSessionStore from
        this same raw sender; passing the composite string here would
        double-encode it and silently fail every lookup). Captured once
        when the nested entity's create is queued, stored verbatim, never
        recomputed at resume time.
    channel: the origin channel ("telegram"/"whatsapp") the parent
        completion is running on — captured alongside session_key for the
        same reason: PersistentSessionStore's RAM cache is channel-scoped
        (BUG-SESSION-DUP-RAM), and the queued create's approval is always
        resolved via the OWNER's Telegram inline keyboard regardless of
        which channel the parent completion itself started on. Without
        this, resuming a WhatsApp-originated parent from a Telegram
        approval callback would silently look in the wrong channel's slot.
    nonce: minted fresh each time a nested completion is queued for
        approval and embedded in the nested frame's own current_values
        (key "_pending_approval_nonce") at the same moment. This is the
        actual correlation key at resume time — matching
        (nested_entity, return_field) alone only proves "a nested
        completion of this shape is parked here", not "it's the one THIS
        contract was queued for"; the nonce proves the latter.
    """

    version: int
    type: str
    session_key: str
    channel: str
    nested_entity: str
    return_field: str
    nonce: str

    @classmethod
    def for_commercial_completion(
        cls, *, session_key: str, channel: str, nested_entity: str,
        return_field: str, nonce: str,
    ) -> "ContinuationRef":
        return cls(
            version=_CONTINUATION_REF_VERSION,
            type=_CONTINUATION_REF_TYPE_COMMERCIAL_COMPLETION,
            session_key=session_key,
            channel=channel,
            nested_entity=nested_entity,
            return_field=return_field,
            nonce=nonce,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version, "type": self.type,
            "session_key": self.session_key, "channel": self.channel,
            "nested_entity": self.nested_entity,
            "return_field": self.return_field, "nonce": self.nonce,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "ContinuationRef | None":
        """Never guesses a shape: an absent/malformed/unrecognized-version
        payload returns None (treated as "no continuation") rather than
        raising or partially trusting it — a future version bump is safe
        by construction, an old reader just stops recognizing it instead
        of misinterpreting its fields."""
        if not isinstance(raw, Mapping):
            return None
        if raw.get("version") != _CONTINUATION_REF_VERSION:
            return None
        if raw.get("type") != _CONTINUATION_REF_TYPE_COMMERCIAL_COMPLETION:
            return None
        try:
            session_key = str(raw["session_key"])
            channel = str(raw["channel"])
            nested_entity = str(raw["nested_entity"])
            return_field = str(raw["return_field"])
            nonce = str(raw["nonce"])
        except KeyError:
            return None
        if not (session_key and channel and nested_entity and return_field and nonce):
            return None
        return cls(
            version=_CONTINUATION_REF_VERSION,
            type=_CONTINUATION_REF_TYPE_COMMERCIAL_COMPLETION,
            session_key=session_key, channel=channel, nested_entity=nested_entity,
            return_field=return_field, nonce=nonce,
        )


@dataclass(frozen=True)
class CompletionSession:
    """Pure stack for nested Contact/Organization completion and resumption."""

    frames: tuple[_CompletionFrame, ...]

    @classmethod
    def start(cls, writer: CommercialCompletionWriter) -> "CompletionSession":
        return cls((_CompletionFrame(writer),))

    @property
    def active(self) -> CommercialCompletionWriter:
        return self.frames[-1].writer

    def answer(self, field_name: str, value: Any) -> "CompletionSession":
        frames = list(self.frames)
        frames[-1] = replace(frames[-1], writer=self.active.apply_answer(field_name, value))
        return CompletionSession(tuple(frames))

    def begin_nested(
        self,
        target_entity: str,
        *,
        return_field: str,
        current_values: Mapping[str, Any] | None = None,
        source_context: Mapping[str, Any] | None = None,
    ) -> "CompletionSession":
        parent_field = self.active.contract.field(return_field)
        if parent_field.input_type != InputType.LINK:
            raise CompletionBlockedError("nested completion must return into a link field")
        child = CommercialCompletionWriter(
            target_entity,
            current_values or {},
            source_context or {},
            self.active.identity,
            self.active.contracts,
        )
        return CompletionSession(self.frames + (_CompletionFrame(child, return_field),))

    def resume_parent(self, canonical_record_id: str) -> "CompletionSession":
        if len(self.frames) < 2:
            raise CompletionBlockedError("there is no nested completion to resume")
        if not self.active.is_complete():
            raise CompletionBlockedError("nested entity is incomplete")
        return_field = self.frames[-1].return_field
        frames = list(self.frames[:-1])
        frames[-1] = replace(
            frames[-1],
            writer=frames[-1].writer.apply_answer(return_field or "", canonical_record_id),
        )
        return CompletionSession(tuple(frames))

    def abandon_nested(self) -> "CompletionSession":
        """Pop the active nested frame without folding any value into the
        parent — the mirror image of resume_parent() for a nested
        completion that will never produce a record: the approver rejected
        the queued create, or a resumed approval proved (by continuation
        nonce) to belong to a nested frame that is no longer live. The
        parent frame is returned exactly as it was before begin_nested()
        was called on it — no LINK field is touched, so the parent simply
        goes back to being incomplete on that field, ready to be asked
        again. Deliberately not needed on the pre-confirm decline path
        ("לא" to "ליצור איש קשר חדש?") — begin_nested() is only called
        after that confirmation, so declining before it never has a nested
        frame to abandon in the first place.
        """
        if len(self.frames) < 2:
            raise CompletionBlockedError("there is no nested completion to abandon")
        return CompletionSession(self.frames[:-1])
