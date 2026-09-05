from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch
import inspect

import pytest

import commercial_crm
from airtable_schema import (
    ChargeFields,
    ChargeStatus,
    CollectionState,
    ContactFields,
    Currency,
    Direction,
    DocumentRequirement,
    DocumentStatus,
    OrganizationFields,
    PaymentFields,
    PaymentStatus,
    Tables,
    VATRule,
)
from core.action_gateway import ActionGateway, ExecutionLedger
from identity import Identity, Role
from tool_registry import get as get_tool_meta
from tools import dispatcher
from tools.schemas import TOOL_SCHEMAS


DEAL_ID = "recDEAL0000000001"
TERM_ID = "recTERM0000000001"
CHARGE_ID = "recCHARGE00000001"
ORG_ID = "recORG00000000001"
CONTACT_ID = "recCONTACT0000001"
PAYMENT_ID = "recPAYMENT0000001"


def _created(record_id: str):
    return SimpleNamespace(status="created", record={"id": record_id}, error="")


def _charge_kwargs(**overrides):
    values = {
        "deal_id": DEAL_ID,
        "direction": Direction.RECEIVABLE,
        "amount": 1200,
        "currency": Currency.ILS,
        "status": ChargeStatus.ISSUED,
        "collection_state": CollectionState.NOT_DUE,
        "vat_rule": VATRule.NONE,
        "document_requirement": DocumentRequirement.NONE,
        "document_status": DocumentStatus.NOT_REQUIRED,
    }
    values.update(overrides)
    return values


def _payment_kwargs(**overrides):
    values = {
        "charge_id": CHARGE_ID,
        "deal_id": DEAL_ID,
        "direction": Direction.RECEIVABLE,
        "amount": 600,
        "currency": Currency.ILS,
        "paid_at": "2026-09-03",
        "status": PaymentStatus.RECEIVED,
        "document_requirement": DocumentRequirement.RECEIPT_REQUIRED,
        "document_status": DocumentStatus.RECEIVED,
    }
    values.update(overrides)
    return values


def _charge_record(**overrides):
    fields = {
        ChargeFields.DEAL: [DEAL_ID],
        ChargeFields.DIRECTION: Direction.RECEIVABLE,
        ChargeFields.CURRENCY_CODE: Currency.ILS,
        ChargeFields.BILLING_TERM: [TERM_ID],
    }
    fields.update(overrides)
    return fields


def _read_side_effect(table, record_id):
    if table == Tables.DEALS and record_id == DEAL_ID:
        return {}
    if table == Tables.CHARGES and record_id == CHARGE_ID:
        return _charge_record()
    if table == Tables.PAYMENT_TERMS and record_id == TERM_ID:
        return {"Deal": [DEAL_ID]}
    if (table, record_id) in {
        (Tables.ORGANIZATIONS, ORG_ID),
        (Tables.CONTACTS, CONTACT_ID),
    }:
        return {}
    raise RuntimeError("not found")


def test_organization_normalizes_exactly_and_preserves_display_spelling():
    assert commercial_crm.normalize_organization_name("  Acme\t Holdings  ") == (
        "Acme Holdings", "acme holdings"
    )
    with patch.object(commercial_crm, "list_records", return_value=[]), patch.object(
        commercial_crm, "airtable_create", return_value=_created(ORG_ID)
    ) as create:
        result = commercial_crm.find_or_create_organization("  Acme\t Holdings  ")
    assert result["ok"] is True
    create.assert_called_once_with(
        Tables.ORGANIZATIONS,
        {OrganizationFields.NAME: "Acme Holdings"},
        source="commercial_crm",
        return_outcome=True,
    )


@pytest.mark.parametrize(
    "records, expected_ok, expected_count",
    [
        ([{"id": ORG_ID, "fields": {OrganizationFields.NAME: "ACME HOLDINGS"}}], True, 0),
        ([
            {"id": ORG_ID, "fields": {OrganizationFields.NAME: "Acme Holdings"}},
            {"id": "recORG00000000002", "fields": {OrganizationFields.NAME: " acme  holdings "}},
        ], False, 0),
    ],
)
def test_organization_reuses_one_match_and_fails_closed_on_ambiguity(
    records, expected_ok, expected_count
):
    with patch.object(commercial_crm, "list_records", return_value=records), patch.object(
        commercial_crm, "airtable_create"
    ) as create:
        result = commercial_crm.find_or_create_organization("Acme Holdings")
    assert result["ok"] is expected_ok
    assert create.call_count == expected_count
    if expected_ok:
        assert result["external_id"] == ORG_ID


def test_organization_lookup_failure_and_empty_name_never_write():
    for name, side_effect in (("", None), ("Acme", RuntimeError("offline"))):
        with patch.object(commercial_crm, "list_records", side_effect=side_effect), patch.object(
            commercial_crm, "airtable_create"
        ) as create:
            result = commercial_crm.find_or_create_organization(name)
        assert result["ok"] is False
        create.assert_not_called()


def test_organization_contract_is_not_a_contact_or_generic_fields_api():
    with pytest.raises(TypeError):
        commercial_crm.find_or_create_organization("Acme", phone="+972500000000")
    source = inspect.getsource(commercial_crm.find_or_create_organization)
    assert "find_or_create_contact" not in source
    assert "ContactFields" not in source


# ── DIAMOND PATH nested-entity approval continuation: crm_find_or_create_contact ──

def test_contact_reuses_existing_via_the_one_canonical_writer():
    with patch.object(
        commercial_crm.crm, "create_contact_from_fields",
        return_value=SimpleNamespace(status="existing", record_id=CONTACT_ID, matches=(), error=""),
    ) as writer:
        result = commercial_crm.find_or_create_contact("Dana Cohen", phone="0501234567")
    assert result["ok"] is True
    assert result["external_id"] == CONTACT_ID
    writer.assert_called_once()
    fields_arg = writer.call_args.args[0]
    assert fields_arg[ContactFields.NAME] == "Dana Cohen"
    assert fields_arg[ContactFields.PHONE] == "0501234567"


def test_contact_creates_when_no_match():
    with patch.object(
        commercial_crm.crm, "create_contact_from_fields",
        return_value=SimpleNamespace(status="created", record_id=CONTACT_ID, matches=(), error=""),
    ):
        result = commercial_crm.find_or_create_contact(
            "Dana Cohen", phone="0501234567", email="dana@x.com",
            company="Acme", role_category="client",
        )
    assert result["ok"] is True
    assert result["external_id"] == CONTACT_ID
    assert result["user_message"] == "✅ איש הקשר נוצר"


def test_contact_ambiguous_or_invalid_never_report_ok():
    for status in ("ambiguous", "invalid_phone", "missing_name"):
        with patch.object(
            commercial_crm.crm, "create_contact_from_fields",
            return_value=SimpleNamespace(status=status, record_id="", matches=(), error=""),
        ):
            result = commercial_crm.find_or_create_contact("Dana Cohen", phone="bad")
        assert result["ok"] is False
        assert result["external_id"] == ""


def test_contact_outcome_unknown_fails_closed_with_its_own_message():
    with patch.object(
        commercial_crm.crm, "create_contact_from_fields",
        return_value=SimpleNamespace(status="outcome_unknown", record_id="", matches=(), error="timeout"),
    ):
        result = commercial_crm.find_or_create_contact("Dana Cohen", phone="0501234567")
    assert result["ok"] is False
    assert "לא ידוע" in result["user_message"] or "אינה ידועה" in result["user_message"]


def test_contact_empty_name_never_calls_the_writer():
    with patch.object(commercial_crm.crm, "create_contact_from_fields") as writer:
        result = commercial_crm.find_or_create_contact("   ")
    assert result["ok"] is False
    writer.assert_not_called()


def test_contact_reuses_the_one_writer_no_second_implementation():
    """Owner decision: 'reusing crm.create_contact_from_fields() internally
    ... do not invent a second writer'."""
    source = inspect.getsource(commercial_crm.find_or_create_contact)
    assert "create_contact_from_fields" in source
    assert "airtable_create(" not in source
    assert "airtable_gateway" not in source


def test_charge_writes_only_approved_canonical_fields_and_keeps_dates_distinct():
    with patch.object(commercial_crm, "get_record_fields", side_effect=_read_side_effect), patch.object(
        commercial_crm, "airtable_create", return_value=_created(CHARGE_ID)
    ) as create:
        result = commercial_crm.create_charge(
            **_charge_kwargs(
                billing_term_id=TERM_ID,
                original_due_date="2026-09-10",
                current_expected_date="2026-09-15",
                promised_payment_date="2026-09-20",
                promised_payment_amount=400,
            )
        )
    assert result["ok"] is True
    fields = create.call_args.args[1]
    assert fields[ChargeFields.DEAL] == [DEAL_ID]
    assert fields[ChargeFields.BILLING_TERM] == [TERM_ID]
    assert fields[ChargeFields.CURRENCY_CODE] == Currency.ILS
    assert fields[ChargeFields.ORIGINAL_DUE_DATE] == "2026-09-10"
    assert fields[ChargeFields.CURRENT_EXPECTED_DATE] == "2026-09-15"
    assert fields[ChargeFields.PROMISED_PAYMENT_DATE] == "2026-09-20"
    assert ChargeFields.TOTAL_PAID not in fields
    assert ChargeFields.REMAINING_BALANCE not in fields


def test_direct_charge_requires_no_billing_term():
    with patch.object(commercial_crm, "get_record_fields", side_effect=_read_side_effect), patch.object(
        commercial_crm, "airtable_create", return_value=_created(CHARGE_ID)
    ) as create:
        result = commercial_crm.create_charge(**_charge_kwargs())
    assert result["ok"] is True
    assert ChargeFields.BILLING_TERM not in create.call_args.args[1]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"deal_id": "bad"}, "Deal record id"),
        ({"direction": "incoming"}, "Direction"),
        ({"currency": "GBP"}, "Currency"),
        ({"status": "open"}, "Status"),
        ({"amount": 0}, "Amount"),
        ({"original_due_date": "03/09/2026"}, "YYYY-MM-DD"),
        ({"document_requirement": DocumentRequirement.NONE,
          "document_status": DocumentStatus.RECEIVED}, "conflicts"),
    ],
)
def test_charge_rejects_invalid_contracts_before_write(overrides, message):
    with patch.object(commercial_crm, "get_record_fields", side_effect=_read_side_effect), patch.object(
        commercial_crm, "airtable_create"
    ) as create:
        result = commercial_crm.create_charge(**_charge_kwargs(**overrides))
    assert result["ok"] is False
    assert message in result["user_message"]
    create.assert_not_called()


def test_charge_rejects_billing_term_from_another_deal():
    def read(table, record_id):
        if table == Tables.DEALS:
            return {}
        return {"Deal": ["recDEAL0000000002"]}

    with patch.object(commercial_crm, "get_record_fields", side_effect=read), patch.object(
        commercial_crm, "airtable_create"
    ) as create:
        result = commercial_crm.create_charge(**_charge_kwargs(billing_term_id=TERM_ID))
    assert result["ok"] is False
    assert "does not belong" in result["user_message"]
    create.assert_not_called()


def test_charge_payment_requires_matching_charge_deal_direction_and_currency():
    cases = [
        ({"deal_id": "recDEAL0000000002"}, _charge_record(), "Deal"),
        ({"direction": Direction.PAYABLE}, _charge_record(), "Direction"),
        ({"currency": Currency.USD}, _charge_record(), "Currency"),
        ({"status": PaymentStatus.PENDING}, _charge_record(), "received"),
    ]
    for inputs, charge, message in cases:
        with patch.object(
            commercial_crm, "get_record_fields",
            side_effect=lambda table, record_id, charge=charge: charge,
        ), patch.object(commercial_crm, "airtable_create") as create:
            result = commercial_crm.create_charge_payment(**_payment_kwargs(**inputs))
        assert result["ok"] is False
        assert message in result["user_message"]
        create.assert_not_called()


def test_charge_payment_writes_actual_movement_with_optional_counterparties():
    with patch.object(commercial_crm, "get_record_fields", side_effect=_read_side_effect), patch.object(
        commercial_crm, "airtable_create", return_value=_created(PAYMENT_ID)
    ) as create:
        result = commercial_crm.create_charge_payment(
            **_payment_kwargs(
                payment_term_id=TERM_ID,
                counterparty_contact_id=CONTACT_ID,
                counterparty_organization_id=ORG_ID,
                method="wire",
            )
        )
    assert result["ok"] is True
    fields = create.call_args.args[1]
    assert fields[PaymentFields.CHARGE] == [CHARGE_ID]
    assert fields[PaymentFields.DEAL_LINK] == [DEAL_ID]
    assert fields[PaymentFields.PAYMENT_TERM] == [TERM_ID]
    assert fields[PaymentFields.COUNTERPARTY_CONTACT] == [CONTACT_ID]
    assert fields[PaymentFields.COUNTERPARTY_ORGANIZATION] == [ORG_ID]
    assert fields[PaymentFields.STATUS] == PaymentStatus.RECEIVED
    assert PaymentFields.DATE not in fields


def test_computed_or_unknown_fields_cannot_enter_writer_signatures():
    with pytest.raises(TypeError):
        commercial_crm.create_charge(**_charge_kwargs(total_paid=1))
    with pytest.raises(TypeError):
        commercial_crm.create_charge_payment(**_payment_kwargs(due_date="2026-09-04"))


def test_tools_are_internal_approval_gated_and_absent_from_agent_schemas():
    names = {
        "crm_find_or_create_organization",
        "crm_find_or_create_contact",
        "crm_create_charge",
        "crm_create_charge_payment",
    }
    exposed = {schema["name"] for schema in TOOL_SCHEMAS}
    assert not names & exposed
    for name in names:
        meta = get_tool_meta(name)
        assert meta is not None
        assert meta.model_exposed is False
        assert meta.requires_approval is True


def test_direct_dispatch_without_action_contract_proof_cannot_write():
    identity = Identity(user_id="owner", role=Role.OWNER)
    with patch.object(dispatcher._ff, "is_enabled", return_value=False), patch.object(
        commercial_crm, "airtable_create"
    ) as create:
        result = dispatcher.dispatch_tool(
            "crm_create_charge", _charge_kwargs(), identity=identity
        )
    assert result["ok"] is False
    assert "ActionContract" in result["user_message"]
    create.assert_not_called()


def test_dispatcher_rejects_v2_payment_without_charge_before_writer():
    identity = Identity(user_id="owner", role=Role.OWNER)
    payload = _payment_kwargs()
    payload.pop("charge_id")
    with patch.object(dispatcher._ff, "is_enabled", return_value=False), patch.object(
        dispatcher, "_validate_execution_proof", return_value=None
    ), patch.object(commercial_crm, "create_charge_payment") as writer:
        result = dispatcher.dispatch_tool(
            "crm_create_charge_payment", payload, identity=identity
        )
    assert result["ok"] is False
    assert "charge_id" in result["user_message"]
    writer.assert_not_called()


def test_dispatcher_routes_v2_generic_creates_and_blocks_generic_updates():
    identity = Identity(user_id="owner", role=Role.OWNER)
    ok = {"ok": True, "tool": "x", "external_id": CHARGE_ID,
          "evidence": {"record_id": CHARGE_ID}, "user_message": "ok"}
    with patch.object(dispatcher._ff, "is_enabled", return_value=False), patch.object(
        dispatcher, "_validate_execution_proof", return_value=None
    ), patch(
        "commercial_crm.create_charge", return_value=ok
    ) as canonical, patch.object(dispatcher, "airtable_add") as generic:
        result = dispatcher.dispatch_tool(
            "airtable_add",
            {"table": Tables.CHARGES, "fields": {
                ChargeFields.DEAL: [DEAL_ID],
                ChargeFields.DIRECTION: Direction.RECEIVABLE,
                ChargeFields.AMOUNT: 1200,
                ChargeFields.CURRENCY_CODE: Currency.ILS,
                ChargeFields.STATUS: ChargeStatus.ISSUED,
                ChargeFields.COLLECTION_STATE: CollectionState.NOT_DUE,
                ChargeFields.VAT_RULE: VATRule.NONE,
                ChargeFields.DOCUMENT_REQUIREMENT: DocumentRequirement.NONE,
                ChargeFields.DOCUMENT_STATUS: DocumentStatus.NOT_REQUIRED,
            }},
            identity=identity,
        )
    assert result is ok
    canonical.assert_called_once()
    generic.assert_not_called()

    with patch.object(dispatcher._ff, "is_enabled", return_value=False), patch.object(
        dispatcher, "_validate_execution_proof", return_value=None
    ), patch.object(
        dispatcher, "airtable_update"
    ) as generic_update:
        result = dispatcher.dispatch_tool(
            "airtable_update",
            {"table": Tables.ORGANIZATIONS, "record_id": ORG_ID,
             "fields": {OrganizationFields.NAME: "Renamed"}},
            identity=identity,
        )
    assert result["ok"] is False
    generic_update.assert_not_called()


def test_generic_v2_payment_create_redirects_to_charge_required_writer():
    identity = Identity(user_id="owner", role=Role.OWNER)
    ok = {"ok": True, "tool": "crm_create_charge_payment", "external_id": PAYMENT_ID,
          "evidence": {"record_id": PAYMENT_ID}, "user_message": "ok"}
    fields = {
        PaymentFields.CHARGE: [CHARGE_ID],
        PaymentFields.DEAL_LINK: [DEAL_ID],
        PaymentFields.DIRECTION: Direction.RECEIVABLE,
        PaymentFields.AMOUNT: 600,
        PaymentFields.CURRENCY: Currency.ILS,
        PaymentFields.PAID_AT: "2026-09-03",
        PaymentFields.STATUS: PaymentStatus.RECEIVED,
        PaymentFields.DOCUMENT_REQUIREMENT: DocumentRequirement.NONE,
        PaymentFields.DOCUMENT_STATUS: DocumentStatus.NOT_REQUIRED,
    }
    with patch.object(dispatcher._ff, "is_enabled", return_value=False), patch.object(
        dispatcher, "_validate_execution_proof", return_value=None
    ), patch("commercial_crm.create_charge_payment", return_value=ok) as canonical, patch(
        "commercial_crm.create_payment"
    ) as legacy, patch.object(dispatcher, "airtable_add") as generic:
        result = dispatcher.dispatch_tool(
            "airtable_add", {"table": Tables.PAYMENTS, "fields": fields},
            identity=identity,
        )
    assert result is ok
    canonical.assert_called_once()
    legacy.assert_not_called()
    generic.assert_not_called()


@pytest.mark.parametrize(
    "tool_name, payload",
    [
        ("crm_find_or_create_organization", {"organization_name": "Acme"}),
        ("crm_find_or_create_contact", {"name": "Dana Cohen", "phone": "0501234567"}),
        ("crm_create_charge", _charge_kwargs()),
        ("crm_create_charge_payment", _payment_kwargs()),
    ],
)
def test_action_gateway_deduplicates_each_business_action(tool_name, payload):
    gateway = ActionGateway(ledger=ExecutionLedger())
    first = gateway.propose_action(
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner",
        tool_name=tool_name,
        tool_inputs=payload,
        origin_channel="internal",
        origin_chat_id="s2b",
        requires_approval=True,
    )
    second = gateway.propose_action(
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner",
        tool_name=tool_name,
        tool_inputs=dict(reversed(list(payload.items()))),
        origin_channel="internal",
        origin_chat_id="s2b-retry",
        requires_approval=True,
    )
    assert first.ok is True
    assert second.ok is False
    assert second.contract_id == first.contract_id


@pytest.mark.parametrize(
    "tool_name, payload",
    [
        ("crm_find_or_create_organization", {"organization_name": "Acme"}),
        ("crm_find_or_create_contact", {"name": "Dana Cohen", "phone": "0501234567"}),
        ("crm_create_charge", _charge_kwargs()),
        ("crm_create_charge_payment", _payment_kwargs()),
    ],
)
def test_action_gateway_executes_the_exact_approved_payload_once(tool_name, payload):
    executions = []

    def executor(tool_name, tool_inputs, contract_id, **_kwargs):
        executions.append((tool_name, tool_inputs, contract_id))
        return "executed"

    gateway = ActionGateway(ledger=ExecutionLedger(), tool_executor=executor)
    proposed = gateway.propose_action(
        tenant_id="boss_hq", canonical_user_id="boss_hq:owner",
        tool_name=tool_name, tool_inputs=payload,
        origin_channel="internal", origin_chat_id="s2b",
        requires_approval=True,
    )
    contract = gateway.find_contract(proposed.contract_id)
    gateway.approve(
        proposed.contract_id, approver="boss_hq:owner", approver_role=Role.OWNER
    )
    gateway.approve(
        proposed.contract_id, approver="boss_hq:owner", approver_role=Role.OWNER
    )
    assert len(executions) == 1
    assert executions[0][0] == tool_name
    assert executions[0][1] == contract.normalized_payload
