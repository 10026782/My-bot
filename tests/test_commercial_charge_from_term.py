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
            PaymentTermFields.FIXED_AMOUNT: 100, PaymentTermFields.RATE_PCT: 10,
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
