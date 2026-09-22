#!/usr/bin/env python3
"""
test_phase0_commercial_crm_update_authority.py — Phase 0 (BusinessDraft
Commercial CRM Canonical Update Authority,
docs/architecture/BUSINESSDRAFT_UX_CONTRACT_FREEZE_20260922.md §16/§17/§27
Phase 0).

Exercises the NEW canonical update writers (commercial_crm.update_deal(),
update_payment_term(), update_payment()) and their dedicated dispatcher
entry points (crm_update_deal, crm_update_payment_term, crm_update_payment)
directly — the generic airtable_update REDIRECT into these same writers is
already covered end-to-end by test_bug_crm_bypass_airtable_update.py (which
this task also updated); this file does not duplicate that coverage.

Unit-level (commercial_crm.py functions called directly, Airtable I/O
mocked) plus dispatcher-level (real dispatch_tool()/enforce() routing,
matching the existing test_commercial_crm_dispatcher_wiring.py convention).
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-phase0-update-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PHASE0_UPDATE_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPhase0UpdateTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPhase0UpdateTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import commercial_crm  # noqa: E402
import tools.dispatcher as dispatcher_module  # noqa: E402
from tools.dispatcher import dispatch_tool  # noqa: E402
from airtable_schema import Tables, DealStage, PaymentTermFields  # noqa: E402
from identity import Identity, Role  # noqa: E402

_no_emergency_stop = patch.object(dispatcher_module._ff, "is_enabled", return_value=False)
_no_emergency_stop.start()

_DEAL_ID = "recDeal00000000A1"
_TERM_ID = "recTerm00000000A1"
_PAY_ID = "recPay000000000A1"
_CONTACT_ID = "recContact00000A1"
_ORG_ID = "recOrg000000000A1"


def chk(desc: str, cond: bool) -> None:
    assert cond, desc
    print(f"✅ {desc}")


owner = Identity(
    user_id="owner-p0-upd", role=Role.OWNER, display_name="owner-p0-upd",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="owner-p0-upd",
)
employee = Identity(
    user_id="employee-p0-upd", role=Role.EMPLOYEE, display_name="employee-p0-upd",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="employee-p0-upd",
)


def _dispatch(name, inputs, identity):
    with patch.object(dispatcher_module, "_validate_execution_proof", return_value=None):
        return dispatch_tool(name, inputs, identity=identity, trusted_source="agent",
                              execution_context={"contract_id": "c1"})


# ══════════════════════════════════════════════════════════════════
print("── DEAL: commercial_crm.update_deal() unit behavior ──")

with patch.object(commercial_crm, "airtable_patch", return_value=True) as mock_patch:
    result = commercial_crm.update_deal(_DEAL_ID, {"stage": DealStage.NEGOTIATION, "notes": "n"})
chk("Deal: supported update succeeds", result.get("ok") is True)
chk("Deal: exactly one Airtable mutation", mock_patch.call_count == 1)

with patch.object(commercial_crm, "airtable_patch") as mock_patch_rejected:
    result_bad = commercial_crm.update_deal(_DEAL_ID, {"origin_lead_id": "recLead000000A1"})
chk("Deal: unsupported field (origin_lead_id, immutable after create) rejected",
    result_bad.get("ok") is False)
chk("Deal: rejected field never reaches Airtable", mock_patch_rejected.call_count == 0)

with patch.object(commercial_crm, "airtable_patch") as mock_patch_empty:
    result_empty = commercial_crm.update_deal(_DEAL_ID, {})
chk("Deal: empty fields dict rejected (no silent no-op write)", result_empty.get("ok") is False)
chk("Deal: no write attempted for an empty update", mock_patch_empty.call_count == 0)

with patch.object(commercial_crm, "airtable_patch") as mock_patch_badid:
    result_badid = commercial_crm.update_deal("not-a-real-id", {"notes": "n"})
chk("Deal: malformed record id rejected", result_badid.get("ok") is False)
chk("Deal: malformed record id never reaches Airtable", mock_patch_badid.call_count == 0)

with patch.object(commercial_crm, "airtable_patch", return_value=True) as mock_patch_link:
    result_link = commercial_crm.update_deal(_DEAL_ID, {"counterparty_contact_id": _CONTACT_ID})
chk("Deal: linked-field (counterparty_contact_id) update succeeds with a valid record id",
    result_link.get("ok") is True)
chk("Deal: linked field written as a single-element list",
    mock_patch_link.call_args.args[2].get("Counterparty Contact") == [_CONTACT_ID])

with patch.object(commercial_crm, "airtable_patch") as mock_patch_badlink:
    result_badlink = commercial_crm.update_deal(_DEAL_ID, {"counterparty_contact_id": "not-valid"})
chk("Deal: malformed linked-record id rejected", result_badlink.get("ok") is False)
chk("Deal: malformed linked-record id never reaches Airtable", mock_patch_badlink.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── PAYMENT TERM: commercial_crm.update_payment_term() unit behavior ──")

with patch.object(commercial_crm, "get_record_fields", return_value={
    PaymentTermFields.CALC_TYPE_CODE: "fixed", PaymentTermFields.FIXED_AMOUNT: 100,
}), patch.object(commercial_crm, "airtable_patch", return_value=True) as mock_term_patch:
    result_term = commercial_crm.update_payment_term(_TERM_ID, {"notes": "corrected"})
chk("Payment Term: supported update succeeds", result_term.get("ok") is True)
chk("Payment Term: exactly one Airtable mutation", mock_term_patch.call_count == 1)

with patch.object(commercial_crm, "airtable_patch") as mock_term_rejected:
    result_term_bad = commercial_crm.update_payment_term(_TERM_ID, {"deal_id": "recDeal00000000A2"})
chk("Payment Term: unsupported field (deal_id, immutable after create) rejected",
    result_term_bad.get("ok") is False)
chk("Payment Term: rejected field never reaches Airtable", mock_term_rejected.call_count == 0)

with patch.object(commercial_crm, "get_record_fields", return_value={
    PaymentTermFields.CALC_TYPE_CODE: "fixed", PaymentTermFields.FIXED_AMOUNT: 100,
}), patch.object(commercial_crm, "airtable_patch") as mock_term_inconsistent:
    # Switching to percentage without supplying rate_pct/calc_basis must
    # fail the SAME cross-field invariant create_payment_term() enforces —
    # a partial update is re-validated against the merged (current + new)
    # state, not just the new keys in isolation.
    result_term_inconsistent = commercial_crm.update_payment_term(_TERM_ID, {"calc_type": "percentage"})
chk("Payment Term: partial update that breaks calc_type/rate_pct/calc_basis consistency fails closed",
    result_term_inconsistent.get("ok") is False)
chk("Payment Term: inconsistent update never reaches Airtable", mock_term_inconsistent.call_count == 0)

with patch.object(commercial_crm, "get_record_fields", side_effect=Exception("boom")):
    result_term_missing = commercial_crm.update_payment_term(_TERM_ID, {"notes": "x"})
chk("Payment Term: unreadable/nonexistent record fails closed",
    result_term_missing.get("ok") is False)


# ══════════════════════════════════════════════════════════════════
print("\n── PAYMENT: commercial_crm.update_payment() correction-boundary behavior ──")

with patch.object(commercial_crm, "airtable_patch", return_value=True) as mock_pay_patch:
    result_pay = commercial_crm.update_payment(_PAY_ID, {"reference": "REF-CORRECTED", "notes": "typo fix"})
chk("Payment: supported non-financial correction succeeds", result_pay.get("ok") is True)
chk("Payment: exactly one Airtable mutation", mock_pay_patch.call_count == 1)

for financial_field, value in (
    ("amount", 500), ("currency", "ILS"), ("direction", "receivable"),
    ("paid_at", "2026-09-22"), ("charge_id", "recCharge0000A1"),
    ("deal_id", _DEAL_ID), ("status", "received"),
):
    with patch.object(commercial_crm, "airtable_patch") as mock_pay_blocked:
        result_financial = commercial_crm.update_payment(_PAY_ID, {financial_field: value})
    chk(f"Payment: financial field '{financial_field}' is rejected, not silently ignored",
        result_financial.get("ok") is False)
    chk(f"Payment: financial field '{financial_field}' never reaches Airtable",
        mock_pay_blocked.call_count == 0)

with patch.object(commercial_crm, "airtable_patch") as mock_pay_unknown:
    result_pay_unknown = commercial_crm.update_payment(_PAY_ID, {"totally_unknown_field": "x"})
chk("Payment: unrecognized field fails closed", result_pay_unknown.get("ok") is False)
chk("Payment: unrecognized field never reaches Airtable", mock_pay_unknown.call_count == 0)

with patch.object(commercial_crm, "get_record_fields", return_value={"Document Requirement": "none"}), \
     patch.object(commercial_crm, "airtable_patch") as mock_pay_docmismatch:
    # Only document_status supplied; merged with current Document
    # Requirement=none, expects Document Status=not_required — a mismatch
    # must fail closed exactly like create_charge_payment()'s own check.
    result_doc_mismatch = commercial_crm.update_payment(_PAY_ID, {"document_status": "pending"})
chk("Payment: Document Status/Requirement merge-validation fails closed on conflict",
    result_doc_mismatch.get("ok") is False)
chk("Payment: conflicting document state never reaches Airtable", mock_pay_docmismatch.call_count == 0)

with patch.object(commercial_crm, "get_record_fields", return_value={_ORG_ID: None}) as mock_link_read:
    with patch.object(commercial_crm, "airtable_patch", return_value=True) as mock_pay_link:
        result_pay_link = commercial_crm.update_payment(_PAY_ID, {"counterparty_organization_id": _ORG_ID})
chk("Payment: counterparty organization update resolves the linked record and succeeds",
    result_pay_link.get("ok") is True)
chk("Payment: linked organization write goes through exactly one mutation", mock_pay_link.call_count == 1)


# ══════════════════════════════════════════════════════════════════
print("\n── DISPATCHER: dedicated crm_update_* tools route to the canonical writers ──")

with patch.object(commercial_crm, "airtable_patch", return_value=True) as mock_disp_deal:
    result_disp_deal = _dispatch("crm_update_deal", {"record_id": _DEAL_ID, "stage": DealStage.CLOSED_WIN}, owner)
chk("crm_update_deal: reaches update_deal()'s single mutation", mock_disp_deal.call_count == 1)
chk("crm_update_deal: result ok=True", result_disp_deal.get("ok") is True)

with patch.object(commercial_crm, "get_record_fields", return_value={
    PaymentTermFields.CALC_TYPE_CODE: "fixed", PaymentTermFields.FIXED_AMOUNT: 100,
}), patch.object(commercial_crm, "airtable_patch", return_value=True) as mock_disp_term:
    result_disp_term = _dispatch("crm_update_payment_term", {"record_id": _TERM_ID, "notes": "via dispatcher"}, owner)
chk("crm_update_payment_term: reaches update_payment_term()'s single mutation", mock_disp_term.call_count == 1)
chk("crm_update_payment_term: result ok=True", result_disp_term.get("ok") is True)

with patch.object(commercial_crm, "airtable_patch", return_value=True) as mock_disp_pay:
    result_disp_pay = _dispatch("crm_update_payment", {"record_id": _PAY_ID, "method": "wire"}, owner)
chk("crm_update_payment: reaches update_payment()'s single mutation", mock_disp_pay.call_count == 1)
chk("crm_update_payment: result ok=True", result_disp_pay.get("ok") is True)

with patch.object(commercial_crm, "airtable_patch") as mock_disp_pay_financial:
    result_disp_pay_bad = _dispatch("crm_update_payment", {"record_id": _PAY_ID, "amount": 999}, owner)
chk("crm_update_payment: financial field still blocked when called via the dedicated tool",
    result_disp_pay_bad.get("ok") is False)
chk("crm_update_payment: blocked financial field never reaches Airtable",
    mock_disp_pay_financial.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── DISPATCHER: role gate — employee denied before any writer is reached ──")

for tool_name, inputs in (
    ("crm_update_deal", {"record_id": _DEAL_ID, "notes": "x"}),
    ("crm_update_payment_term", {"record_id": _TERM_ID, "notes": "x"}),
    ("crm_update_payment", {"record_id": _PAY_ID, "notes": "x"}),
):
    with patch.object(commercial_crm, "airtable_patch") as mock_denied:
        result_denied = _dispatch(tool_name, inputs, employee)
    chk(f"{tool_name}: employee denied (no weaker than the matching create tool)",
        (isinstance(result_denied, dict) and result_denied.get("ok") is False)
        or (isinstance(result_denied, str) and "גישה" in result_denied))
    chk(f"{tool_name}: employee denial never reaches the writer", mock_denied.call_count == 0)


print()
print("=" * 50)
print("Phase 0 (BusinessDraft Commercial CRM Canonical Update Authority) tests: PASS")


def test_phase0_commercial_crm_update_authority_completed() -> None:
    """pytest entry point — the assertions above already ran at import time."""
    assert True
