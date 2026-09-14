from unittest.mock import patch

import commercial_crm as crm
from airtable_schema import ChargeFields, LeadFields, PaymentTermFields, Tables
from identity import Identity, Role
from core.action_gateway import ActionGateway, ExecutionLedger, _make_dispatch_executor

DEAL, TERM, LEAD = "recDeal0000000001", "recTerm0000000001", "recLead0000000001"

def records(calc_type="fixed", lead_deal=DEAL, deal_domain="saas", lead_domain="saas"):
    return {
        (Tables.DEALS, DEAL): {"Domain": deal_domain},
        (Tables.PAYMENT_TERMS, TERM): {
            PaymentTermFields.DEAL: [DEAL], PaymentTermFields.CALC_TYPE: calc_type,
            PaymentTermFields.FIXED_AMOUNT: 100,
            # BUG-CHARGE-TERM-BYPASS live canary: Airtable's Percent-format
            # field API always returns the stored FRACTION (0.1 for a
            # UI-displayed "10%"), never percentage points — 0.1 here is
            # the realistic live shape, matching what crm_create_charge_
            # from_term() actually reads off a real Payment Term record.
            PaymentTermFields.RATE_PCT: 0.1,
            PaymentTermFields.VAT_RULE: "none",
        },
        (Tables.LEADS, LEAD): {LeadFields.DEAL_LINK: [lead_deal], "domain": lead_domain},
    }


def run_case(data, *, basis_value=None, existing=None, charge_result=None, readback=None):
    charge_result = charge_result or {"ok": True, "external_id": "C", "evidence": {}}
    def default_readback():
        fields = {
            ChargeFields.DEAL: [DEAL], ChargeFields.BILLING_TERM: [TERM],
            ChargeFields.LEAD: [LEAD], ChargeFields.REFERENCE: create.call_args.kwargs["reference"],
            ChargeFields.AMOUNT: create.call_args.kwargs["amount"],
        }
        return {"id": "C", "fields": fields}
    def get_fields(table, record_id):
        return data[(table, record_id)]
    with patch.object(crm, "get_record_fields", side_effect=get_fields), \
         patch.object(crm, "list_records", return_value=existing or []), \
         patch.object(crm, "create_charge", return_value=charge_result) as create, \
         patch.object(crm, "get_record", side_effect=lambda *_: readback or default_readback()):
        result = crm.crm_create_charge_from_term(TERM, DEAL, LEAD, basis_value=basis_value)
    return result, create


def test_fixed_percentage_and_validation():
    result, create = run_case(records())
    assert result["ok"] and create.call_args.kwargs["lead_id"] == LEAD
    data = records("percentage")
    missing, create = run_case(data)
    assert not missing["ok"] and not create.called
    result, create = run_case(data, basis_value=100)
    assert result["ok"]
    # BUG-CHARGE-TERM-BYPASS: raw Rate % 0.1 (Airtable Percent-fraction for
    # "10%") against a 100 basis must calculate 10.0 — never 0.1 (the raw
    # fraction misread as percentage points, the live production bug).
    assert create.call_args.kwargs["amount"] == 10.0
    assert create.call_args.kwargs["rate_pct"] == 0.1  # Charge snapshot stays raw/Airtable-native


def test_live_canary_percentage_amount_matches_the_reported_expectation():
    """Exact live canary: Deal "קבלנים דרך עמי מערכות", Term "עמלת פוסידון —
    10%...", basis 21,000 -> the bot showed "אחוז: 0.1%" / "21.00 ILS"
    instead of "10%" / "2,100.00 ILS". Locks in the fix at the writer
    boundary (describe_charge_from_term_preview() is covered separately)."""
    data = records("percentage")
    result, create = run_case(data, basis_value=21000)
    assert result["ok"]
    assert create.call_args.kwargs["amount"] == 2100.0
    assert create.call_args.kwargs["base_amount"] == 21000.0


def test_idempotency_check_is_a_targeted_query_not_a_full_table_scan():
    """BUG-CHARGE-TERM-BYPASS live canary follow-up: the duplicate-Reference
    check used to fetch the entire Charges table unbounded/paginated — a
    real scalability risk (and a plausible cause of the reported "אושר אך
    נכשל בביצוע" execution failure) never exercised against a real-sized
    table before the first live approval click. Must now be one small,
    Airtable-side-filtered request."""
    with patch.object(crm, "get_record_fields", side_effect=lambda t, r: records()[(t, r)]), \
         patch.object(crm, "list_records", return_value=[]) as list_records, \
         patch.object(crm, "create_charge", return_value={"ok": True, "external_id": "C", "evidence": {}}), \
         patch.object(crm, "get_record", side_effect=lambda *_: {"id": "C", "fields": {}}):
        crm.crm_create_charge_from_term(TERM, DEAL, LEAD)
    call = list_records.call_args
    assert call.args[0] == Tables.CHARGES
    assert ChargeFields.REFERENCE in call.args[1]  # an exact-match filterByFormula, not blank
    assert call.kwargs["max_records"] == 1
    assert call.kwargs["paginate"] is False


def test_links_domain_and_duplicate_fail_closed():
    for data in (records(lead_deal="X"), records(deal_domain="saas", lead_domain="finance")):
        result, create = run_case(data)
        assert not result["ok"] and not create.called
    first, create = run_case(records())
    existing = [{"id": "C", "fields": {ChargeFields.REFERENCE: create.call_args.kwargs["reference"]}}]
    with patch.object(crm, "get_record_fields", side_effect=lambda t, r: records()[(t, r)]), \
         patch.object(crm, "list_records", return_value=existing), \
         patch.object(crm, "create_charge") as duplicate:
        second = crm.crm_create_charge_from_term(TERM, DEAL, LEAD)
    assert first["ok"] and second["ok"] and second["evidence"]["idempotent"]
    assert not duplicate.called


def test_provider_and_readback_failures_are_not_success():
    failed, _ = run_case(records(), charge_result={"ok": False, "user_message": "failed", "evidence": {}})
    assert not failed["ok"]
    mismatch, _ = run_case(records(), readback={"id": "C", "fields": {ChargeFields.DEAL: ["X"]}})
    assert not mismatch["ok"]


def test_optional_lead_omitted_does_not_block_creation():
    # BUG-CHARGE-TERM-BYPASS invariant #9: Lead is optional for this writer —
    # an absent lead_id must never be treated as an invalid/missing Lead
    # record, must never block creation, and must never fail the read-back
    # verification (which only asserts Lead linkage when one was supplied).
    data = {
        (Tables.DEALS, DEAL): {"Domain": "saas"},
        (Tables.PAYMENT_TERMS, TERM): {
            PaymentTermFields.DEAL: [DEAL], PaymentTermFields.CALC_TYPE: "fixed",
            PaymentTermFields.FIXED_AMOUNT: 100, PaymentTermFields.VAT_RULE: "none",
        },
    }
    charge_result = {"ok": True, "external_id": "C", "evidence": {}}

    def get_fields(table, record_id):
        return data[(table, record_id)]

    def readback():
        fields = {
            ChargeFields.DEAL: [DEAL], ChargeFields.BILLING_TERM: [TERM],
            ChargeFields.REFERENCE: create.call_args.kwargs["reference"],
            ChargeFields.AMOUNT: create.call_args.kwargs["amount"],
        }
        return {"id": "C", "fields": fields}

    with patch.object(crm, "get_record_fields", side_effect=get_fields), \
         patch.object(crm, "list_records", return_value=[]), \
         patch.object(crm, "create_charge", return_value=charge_result) as create, \
         patch.object(crm, "get_record", side_effect=lambda *_: readback()):
        result = crm.crm_create_charge_from_term(TERM, DEAL, "")

    assert result["ok"]
    assert create.call_args.kwargs["lead_id"] == ""


def test_describe_preview_shows_percentage_points_not_the_raw_airtable_fraction():
    """BUG-CHARGE-TERM-BYPASS live canary: the pending-approval preview
    showed "אחוז: 0.1%" / "חיוב מחושב: 21.00 ILS" for a Term whose own name
    says 10% and a 21,000 basis -- must show "10%" / "2,100.00 ILS"."""
    deal_fields = {crm.DealFields.NAME: "קבלנים דרך עמי מערכות"}
    term_fields = {
        PaymentTermFields.NAME: "עמלת פוסידון — 10% לאחר קיזוז רכישת ציוד שחור",
        PaymentTermFields.CALC_TYPE_CODE: "percentage",
        PaymentTermFields.RATE_PCT: 0.1,  # Airtable Percent-fraction for "10%"
        PaymentTermFields.VAT_RULE: "none",
        PaymentTermFields.CURRENCY: "ILS",
    }
    with patch.object(
        crm, "get_record_fields",
        side_effect=lambda table, rid: deal_fields if table == Tables.DEALS else term_fields,
    ):
        preview = crm.describe_charge_from_term_preview(TERM, DEAL, 21000)
    assert "אחוז: 10%" in preview
    assert "0.1%" not in preview
    assert "סכום בסיס: 21,000.00" in preview
    assert "חיוב מחושב: 2,100.00 ILS" in preview
    assert "21.00 ILS" not in preview


def test_create_payment_term_writes_the_airtable_percent_fraction_not_raw_points():
    """The completion UI/Agent schema both collect rate_pct as percentage
    POINTS (10, validated 0-100) -- create_payment_term() must store the
    Airtable Percent-field fraction (0.1), never the raw points value,
    or a NEW Term created through this flow would show "1000%" in Airtable."""
    with patch.object(crm, "airtable_create") as airtable_create:
        airtable_create.return_value.status = "created"
        airtable_create.return_value.record = {"id": "recNewTerm000001"}
        crm.create_payment_term(
            DEAL, "New Term", "percentage", rate_pct=10, calc_basis="deal_amount",
        )
    written_fields = airtable_create.call_args.args[1]
    assert written_fields[PaymentTermFields.RATE_PCT] == 0.1


def test_action_gateway_approval_reaches_dispatcher():
    ledger = ExecutionLedger()
    gateway = ActionGateway(ledger=ledger)
    identity = Identity("owner", Role.OWNER, tenant_id="boss_hq", domain_id="saas")
    with patch("tools.dispatcher.dispatch_tool", return_value={"ok": True, "tool": "crm_create_charge_from_term", "external_id": "C", "evidence": {"record_id": "C"}, "user_message": "ok"}) as dispatch:
        gateway._tool_executor = _make_dispatch_executor(ledger)
        proposal = gateway.propose_action(
            tenant_id="boss_hq", canonical_user_id=identity.memory_key,
            tool_name="crm_create_charge_from_term", tool_inputs={"payment_term_id": TERM, "deal_id": DEAL, "lead_id": LEAD},
            origin_channel="telegram", origin_chat_id="tg:1", requires_approval=True, identity=identity,
        )
        gateway.approve(proposal.contract_id, approver="owner", approver_role=Role.OWNER)
    assert dispatch.call_args.args[0] == "crm_create_charge_from_term"
