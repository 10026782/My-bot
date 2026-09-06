"""Pure tests for the unwired Commercial Completion Writer foundation."""

from dataclasses import replace

import pytest

from airtable_schema import (
    CommercialStatus,
    Currency,
    DealFields,
    DealType,
    Direction,
    DueRule,
    PaymentTermFields,
    PaymentTermCalcType,
    RelationshipType,
)
from commercial_completion import (
    CompletionBlockedError,
    CompletionSession,
    CommercialCompletionWriter,
    ContinuationRef,
    EntityContract,
    FieldContract,
    InputType,
    InvalidValueError,
    RequiredMode,
    ENTITY_CONTRACTS,
)


def _complete_deal(**overrides):
    values = {
        "name": "Direct deal",
        "domain": "import",
        "owner": "recOwner1",
        "counterparty_contact": "recContact1",
        "deal_type": DealType.SERVICE,
        "relationship_type": RelationshipType.ONE_OFF,
        "currency": Currency.ILS,
        "commercial_status": CommercialStatus.PROSPECT,
        "expected_value": 1000,
    }
    values.update(overrides)
    return values


def test_deal_from_sparse_lead_asks_only_for_missing_deal_fields():
    writer = CommercialCompletionWriter(
        "deal",
        current_values={"deal_type": DealType.SERVICE},
        source_context={
            "name": "Lead-derived deal",
            "domain": "saas",
            "owner_id": "recOwner1",
            "contact_id": "recContact1",
            "amount": 5000,
            "lead_id": "recLead1",
        },
    )
    assert [field.field_name for field in writer.missing_fields()] == [
        "relationship_type",
        "currency",
        "commercial_status",
    ]


def test_deal_created_directly_does_not_require_lead():
    writer = CommercialCompletionWriter("deal", _complete_deal())
    assert writer.is_complete()
    assert "Origin Lead" not in writer.complete_payload()


def test_inherited_domain_and_owner_are_not_asked_twice():
    values = _complete_deal()
    values.pop("domain")
    values.pop("owner")
    writer = CommercialCompletionWriter(
        "deal", values, source_context={"domain": "import", "owner_id": "recOwner1"}
    )
    assert "domain" not in [field.field_name for field in writer.missing_fields()]
    assert "owner" not in [field.field_name for field in writer.missing_fields()]


def test_select_fields_reject_invalid_options():
    writer = CommercialCompletionWriter("deal", _complete_deal())
    with pytest.raises(InvalidValueError):
        writer.apply_answer("currency", "GBP")


def test_custom_choice_opens_only_declared_followup_field():
    contract = EntityContract("example", (
        FieldContract(
            "kind", "Kind", InputType.SELECT,
            required=RequiredMode.ALWAYS,
            choices=("standard", "custom"),
            custom_values=("custom",),
            custom_followup="custom_description",
        ),
        FieldContract(
            "custom_description", "Custom Description", InputType.TEXT,
        ),
    ))
    writer = CommercialCompletionWriter("example", {"kind": "custom"}, contracts={"example": contract})
    assert [field.field_name for field in writer.missing_fields()] == ["custom_description"]
    standard = CommercialCompletionWriter("example", {"kind": "standard"}, contracts={"example": contract})
    assert standard.is_complete()


def test_examples_are_help_text_and_never_resolved_or_persisted():
    writer = CommercialCompletionWriter(
        "organization", contracts=ENTITY_CONTRACTS,
    )
    field = writer.next_field()
    assert field is not None and field.example == "Acme Ltd"
    assert "organization_name" not in writer.resolved_values()
    with pytest.raises(CompletionBlockedError):
        writer.complete_payload()


def test_conditional_fields_appear_only_when_applicable():
    fixed = CommercialCompletionWriter(
        "payment_term",
        {"calculation_type": PaymentTermCalcType.FIXED},
        source_context={"deal_id": "recDeal1", "direction": Direction.RECEIVABLE, "currency": Currency.ILS},
    )
    fixed_missing = [field.field_name for field in fixed.missing_fields()]
    assert "fixed_amount" in fixed_missing
    assert "rate_pct" not in fixed_missing
    percentage = fixed.apply_answer("calculation_type", PaymentTermCalcType.PERCENTAGE)
    percentage_missing = [field.field_name for field in percentage.missing_fields()]
    assert "fixed_amount" not in percentage_missing
    assert {"rate_pct", "calculation_basis"} <= set(percentage_missing)


def test_payment_term_requires_deal():
    writer = CommercialCompletionWriter(
        "payment_term",
        {"calculation_type": PaymentTermCalcType.FIXED, "fixed_amount": 100,
         "direction": Direction.RECEIVABLE, "currency": Currency.ILS},
    )
    assert writer.next_field().field_name == "deal"


def test_charge_requires_deal():
    writer = CommercialCompletionWriter(
        "charge",
        {"direction": Direction.RECEIVABLE, "amount": 100, "currency": Currency.ILS},
    )
    assert writer.next_field().field_name == "deal"


def test_payment_requires_charge():
    writer = CommercialCompletionWriter(
        "payment",
        {"amount": 100, "paid_at": "2026-09-03", "direction": Direction.RECEIVABLE,
         "currency": Currency.ILS},
    )
    assert writer.next_field().field_name == "charge"


def test_payment_cannot_build_payload_without_charge():
    writer = CommercialCompletionWriter(
        "payment",
        {"amount": 100, "paid_at": "2026-09-03", "direction": Direction.RECEIVABLE,
         "currency": Currency.ILS},
    )
    with pytest.raises(CompletionBlockedError, match="charge"):
        writer.complete_payload()


def test_computed_formula_and_rollup_fields_are_never_requested():
    writer = CommercialCompletionWriter(
        "charge", {"deal": "recDeal1", "direction": Direction.RECEIVABLE,
                   "amount": 100, "currency": Currency.ILS}
    )
    missing = {field.field_name for field in writer.missing_fields()}
    assert {"total_paid", "remaining_balance"}.isdisjoint(missing)
    with pytest.raises(InvalidValueError):
        writer.apply_answer("total_paid", 100)


def test_completion_resumes_from_partial_progress():
    writer = CommercialCompletionWriter("deal", _complete_deal(currency=""))
    assert writer.next_field().field_name == "currency"
    resumed = writer.apply_answer("currency", Currency.USD)
    assert resumed.is_complete()
    assert resumed.complete_payload()["Currency"] == Currency.USD


def test_same_contract_supports_chat_and_multi_field_rendering():
    writer = CommercialCompletionWriter(
        "charge", {"deal": "recDeal1"}
    )
    all_fields = writer.missing_fields()
    chat_fields = writer.missing_fields(limit=1)
    assert len(all_fields) > 1
    assert chat_fields == all_fields[:1]


@pytest.mark.parametrize(
    ("nested_entity", "return_field", "answers", "record_id"),
    [
        ("organization", "counterparty_organization", {"organization_name": "Acme"}, "recOrg1"),
        ("contact", "counterparty_contact", {"name": "Dana", "phone": "0501234567"}, "recContact1"),
    ],
)
def test_nested_identity_completion_returns_and_resumes_deal(
    nested_entity, return_field, answers, record_id
):
    parent = CommercialCompletionWriter(
        "deal", _complete_deal(counterparty_contact="")
    )
    session = CompletionSession.start(parent).begin_nested(
        nested_entity, return_field=return_field
    )
    for name, value in answers.items():
        session = session.answer(name, value)
    resumed = session.resume_parent(record_id)
    assert resumed.active.resolved_values()[return_field] == record_id
    assert resumed.active.is_complete()


def test_abandon_nested_returns_to_parent_untouched():
    parent = CommercialCompletionWriter(
        "deal", _complete_deal(counterparty_contact="")
    )
    root = CompletionSession.start(parent)
    nested = root.begin_nested("contact", return_field="counterparty_contact")
    abandoned = nested.answer("name", "Dana").abandon_nested()
    assert abandoned.frames == root.frames
    assert abandoned.active.target_entity == "deal"
    # the LINK field was never touched — still missing, ready to be asked again
    assert "counterparty_contact" in {f.field_name for f in abandoned.active.missing_fields()}


def test_abandon_nested_without_a_nested_frame_blocks():
    parent = CommercialCompletionWriter("deal", _complete_deal())
    root = CompletionSession.start(parent)
    with pytest.raises(CompletionBlockedError):
        root.abandon_nested()


def test_abandon_nested_does_not_require_the_child_to_be_complete():
    """Unlike resume_parent(), abandoning a nested completion must work at
    any point mid-flow (e.g. a rejected approval after the child WAS
    completed and queued, but just as validly before it ever finished)."""
    parent = CommercialCompletionWriter(
        "deal", _complete_deal(counterparty_contact="")
    )
    nested = CompletionSession.start(parent).begin_nested(
        "contact", return_field="counterparty_contact",
    )
    assert not nested.active.is_complete()
    abandoned = nested.abandon_nested()
    assert abandoned.active.target_entity == "deal"


# ── ContinuationRef ────────────────────────────────────────────────────

def test_continuation_ref_round_trips_through_dict():
    ref = ContinuationRef.for_commercial_completion(
        session_key="7228089151",
        channel="telegram",
        nested_entity="contact",
        return_field="counterparty_contact",
        nonce="abc123",
    )
    restored = ContinuationRef.from_dict(ref.to_dict())
    assert restored == ref
    assert ref.to_dict() == {
        "version": 1, "type": "commercial_completion",
        "session_key": "7228089151", "channel": "telegram",
        "nested_entity": "contact", "return_field": "counterparty_contact",
        "nonce": "abc123",
    }


@pytest.mark.parametrize("raw", [
    None,
    {},
    {"version": 2, "type": "commercial_completion", "session_key": "x", "channel": "telegram",
     "nested_entity": "contact", "return_field": "counterparty_contact", "nonce": "n"},
    {"version": 1, "type": "something_else", "session_key": "x", "channel": "telegram",
     "nested_entity": "contact", "return_field": "counterparty_contact", "nonce": "n"},
    {"version": 1, "type": "commercial_completion", "session_key": "x", "channel": "telegram",
     "nested_entity": "contact", "return_field": "counterparty_contact"},  # missing nonce
    {"version": 1, "type": "commercial_completion", "session_key": "", "channel": "telegram",
     "nested_entity": "contact", "return_field": "counterparty_contact", "nonce": "n"},  # blank
    {"version": 1, "type": "commercial_completion", "session_key": "x", "channel": "",
     "nested_entity": "contact", "return_field": "counterparty_contact", "nonce": "n"},  # blank channel
    "not a dict",
])
def test_continuation_ref_from_dict_never_guesses_a_malformed_shape(raw):
    assert ContinuationRef.from_dict(raw) is None


def test_missing_field_decisions_need_no_agent_or_callback():
    writer = CommercialCompletionWriter("deal", _complete_deal(currency=""))
    assert writer.next_field().field_name == "currency"
    assert not hasattr(writer, "agent")
    assert not hasattr(writer, "llm")


@pytest.mark.parametrize(
    ("calculation", "required_field"),
    [
        (PaymentTermCalcType.TIERED, "tier_configuration"),
        (PaymentTermCalcType.CUSTOM, "custom_calculation_rule"),
    ],
)
def test_tiered_and_custom_terms_require_their_approved_detail_field(
    calculation, required_field
):
    writer = CommercialCompletionWriter(
        "payment_term",
        {"calculation_type": calculation, "calculation_basis": "deal_amount"},
        source_context={"deal_id": "recDeal1", "direction": Direction.RECEIVABLE,
                        "currency": Currency.ILS},
    )
    assert required_field in {field.field_name for field in writer.missing_fields()}


@pytest.mark.parametrize(
    ("due_rule", "required_field"),
    [
        (DueRule.SPECIFIC_DUE_DATE, "specific_due_date"),
        (DueRule.SCHEDULED, "schedule_anchor_date"),
        (DueRule.INSTALLMENTS, "schedule_anchor_date"),
    ],
)
def test_due_rules_require_deterministic_date_inputs(due_rule, required_field):
    writer = CommercialCompletionWriter(
        "payment_term",
        {"calculation_type": PaymentTermCalcType.FIXED, "fixed_amount": 100,
         "due_rule": due_rule},
        source_context={"deal_id": "recDeal1", "direction": Direction.RECEIVABLE,
                        "currency": Currency.ILS},
    )
    assert required_field in {field.field_name for field in writer.missing_fields()}


def test_completion_payload_uses_additive_canonical_fields_only():
    deal = CommercialCompletionWriter("deal", _complete_deal()).complete_payload()
    assert deal[DealFields.DEAL_TYPE_CODE] == DealType.SERVICE
    assert DealFields.DEAL_TYPE not in deal

    charge = CommercialCompletionWriter(
        "charge", {"deal": "recDeal1", "direction": Direction.RECEIVABLE,
                   "amount": 100, "currency": Currency.ILS}
    ).complete_payload()
    assert charge["Currency Code"] == Currency.ILS


def test_payment_term_payload_uses_canonical_code_selects():
    writer = CommercialCompletionWriter(
        "payment_term",
        {"calculation_type": PaymentTermCalcType.FIXED, "fixed_amount": 100},
        source_context={"deal_id": "recDeal1", "direction": Direction.RECEIVABLE,
                        "currency": Currency.ILS},
    )
    payload = writer.complete_payload()
    assert payload[PaymentTermFields.CALC_TYPE_CODE] == PaymentTermCalcType.FIXED
    assert payload[PaymentTermFields.CADENCE_CODE] == "once"
    assert payload[PaymentTermFields.TRIGGER_TYPE_CODE] == "immediate"
    assert PaymentTermFields.CALC_TYPE not in payload


def test_allocation_rule_accepts_contact_or_organization_beneficiary():
    common = {
        "deal": "recDeal1",
        "allocation_type": "percentage",
        "allocation_basis": "gross_amount",
        "rate_pct": 10,
    }
    for beneficiary in (
        {"beneficiary_contact": "recContact1"},
        {"beneficiary_organization": "recOrg1"},
    ):
        writer = CommercialCompletionWriter(
            "allocation_rule", {**common, **beneficiary}
        )
        assert writer.is_complete()


def test_existing_value_wins_over_inherited_and_default_value():
    writer = CommercialCompletionWriter(
        "deal",
        _complete_deal(currency=Currency.EUR),
        source_context={"currency": Currency.USD},
    )
    assert writer.resolved_values()["currency"] == Currency.EUR


# ══════════════════════════════════════════════════════════════════
# BUG-COMPLETION-NUMERIC-STRING-422 (production-verified, 06/09/2026):
# a Deal create failed with Airtable 422 INVALID_VALUE_FOR_COLUMN on
# "סכום" (DealFields.AMOUNT) after the owner answered the free-text
# amount prompt with "100000" — validate_value() validated the string as
# a valid number but apply_answer() stored the raw string itself, which
# then reached Airtable as a JSON string instead of a JSON number.
# ══════════════════════════════════════════════════════════════════

def test_free_text_currency_answer_is_coerced_to_a_number_not_left_as_a_string():
    writer = CommercialCompletionWriter("deal", _complete_deal(expected_value=None))
    answered = writer.apply_answer("expected_value", "100000")
    assert answered.current_values["expected_value"] == 100000
    assert isinstance(answered.current_values["expected_value"], float)
    assert not isinstance(answered.current_values["expected_value"], str)


def test_exact_production_reproduction_deal_amount_payload_is_numeric():
    writer = CommercialCompletionWriter("deal", _complete_deal(expected_value=None))
    answered = writer.apply_answer("expected_value", "100000")
    assert answered.is_complete()
    payload = answered.complete_payload()
    assert payload[DealFields.AMOUNT] == 100000
    assert isinstance(payload[DealFields.AMOUNT], float)
    assert not isinstance(payload[DealFields.AMOUNT], str)


def test_free_text_integer_field_answer_is_coerced_to_int_not_float_or_string():
    writer = CommercialCompletionWriter("allocation_rule", {})
    answered = writer.apply_answer("priority", "7")
    assert answered.current_values["priority"] == 7
    assert isinstance(answered.current_values["priority"], int)
    assert not isinstance(answered.current_values["priority"], (str, float))


def test_numeric_answer_already_a_number_is_unaffected():
    writer = CommercialCompletionWriter("deal", _complete_deal(expected_value=None))
    answered = writer.apply_answer("expected_value", 100000)
    assert answered.current_values["expected_value"] == 100000
    assert isinstance(answered.current_values["expected_value"], float)


def test_non_numeric_free_text_still_rejected_before_any_coercion():
    writer = CommercialCompletionWriter("deal", _complete_deal(expected_value=None))
    with pytest.raises(InvalidValueError):
        writer.apply_answer("expected_value", "לא מספר")


def test_select_and_link_answers_are_not_touched_by_numeric_coercion():
    writer = CommercialCompletionWriter("deal", _complete_deal())
    answered = writer.apply_answer("currency", Currency.USD)
    assert answered.current_values["currency"] == Currency.USD
    assert isinstance(answered.current_values["currency"], str)
