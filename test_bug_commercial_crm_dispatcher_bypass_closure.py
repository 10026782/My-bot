#!/usr/bin/env python3
"""
test_bug_commercial_crm_dispatcher_bypass_closure.py — BUG-CRM-BYPASS
(closes the generic airtable_add bypass into Deals/Payment Terms/Payments).

Found during the R10 golden-writer full-path audit (01/09/2026):
tools/dispatcher.py's generic "airtable_add" case redirected raw writes to
the Contacts table into crm.create_contact_from_fields() (the canonical
writer), but had NO equivalent redirect for Deals/Payment Terms/Payments.
A raw airtable_add(table="עסקאות (Deals)"/"Payment Terms"/"Payments", ...)
fell straight through to the generic Airtable writer, skipping
commercial_crm.py's required-field/calc_type/VAT validation entirely.

Worse: airtable_add's own registry entry (roles_allowed=_INTERNAL, includes
"employee") is WIDER than crm_create_deal/crm_create_payment_term/
crm_create_payment's (roles_allowed=_MANAGEMENT, excludes "employee") — an
employee identity explicitly denied the dedicated tool by enforce() could
still reach the identical business mutation through airtable_add.

Fix: mirrors the existing Contacts pattern in tools/dispatcher.py — three
new interception blocks (Deals/Payment Terms/Payments) that (1) re-check
role authority via enforce("crm_create_X", identity) BEFORE anything else,
closing the wider-role gap; (2) map the raw Airtable field names onto the
canonical writer's own kwargs via a closed, explicit field map
(_DEAL_FIELD_MAP/_PAYMENT_TERM_FIELD_MAP/_PAYMENT_FIELD_MAP) that fails
closed on any field it doesn't recognize rather than silently dropping it;
(3) call the canonical writer itself for all business validation — no
validation rule is reimplemented in the dispatcher.

This file exercises the REAL dispatch_tool()/enforce()/field-mapping
functions end-to-end (commercial_crm.create_deal/_payment_term/_payment
are mocked, matching test_commercial_crm_dispatcher_wiring.py's existing
convention — no live Airtable access), plus one REAL (unmocked)
execution-proof test proving a post-approval payload tamper is still
caught through this new path exactly as it is for the dedicated tools.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-crmbypass-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:CRM_BYPASS_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patCrmBypassTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCrmBypassTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import tools.dispatcher as dispatcher_module  # noqa: E402
from tools.dispatcher import dispatch_tool  # noqa: E402
from airtable_schema import Tables, DealFields, PaymentTermFields, PaymentFields, DealStage  # noqa: E402
from identity import Identity, Role  # noqa: E402

_no_emergency_stop = patch.object(dispatcher_module._ff, "is_enabled", return_value=False)
_no_emergency_stop.start()

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


owner = Identity(
    user_id="owner-crmbypass", role=Role.OWNER, display_name="owner-crmbypass",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="owner-crmbypass",
)
manager = Identity(
    user_id="manager-crmbypass", role=Role.MANAGER, display_name="manager-crmbypass",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="manager-crmbypass",
)
employee = Identity(
    user_id="employee-crmbypass", role=Role.EMPLOYEE, display_name="employee-crmbypass",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="employee-crmbypass",
)

_OK_RESULT = {"ok": True, "tool": "crm_create_deal", "external_id": "recDEAL0000000001",
              "evidence": {"record_id": "recDEAL0000000001"}, "user_message": "✅ Deal נוצר"}


def _dispatch(name, inputs, identity, execution_context=None):
    """Bypasses _validate_execution_proof for case-routing tests, exactly
    like test_commercial_crm_dispatcher_wiring.py does — those semantics
    are re-verified separately, unmocked, in the "tampered payload" section
    below."""
    with patch.object(dispatcher_module, "_validate_execution_proof", return_value=None):
        return dispatch_tool(name, inputs, identity=identity, trusted_source="agent",
                              execution_context=execution_context or {"contract_id": "c1"})


# ══════════════════════════════════════════════════════════════════
print("── B/G: raw airtable_add for a management caller routes to the "
      "canonical writer, never the generic Airtable path ──")

with patch("commercial_crm.create_deal", return_value=_OK_RESULT) as mock_create_deal, \
     patch.object(dispatcher_module, "airtable_add") as mock_generic_add:
    result = _dispatch("airtable_add", {
        "table": Tables.DEALS,
        "fields": {
            DealFields.NAME: "עסקת בדיקה",
            DealFields.DOMAIN: "recruitment",
            DealFields.OWNER: ["recOWNER000000001"],
            DealFields.STAGE: DealStage.OPPORTUNITY,
        },
    }, owner)

chk("Deal: canonical create_deal() was called", mock_create_deal.call_count == 1)
chk("Deal: generic airtable_add() was NEVER called (no bypass)", mock_generic_add.call_count == 0)
chk("Deal: kwargs mapped correctly (name/domain/owner_id/stage)",
    mock_create_deal.call_args.kwargs.get("name") == "עסקת בדיקה"
    and mock_create_deal.call_args.kwargs.get("domain") == "recruitment"
    and mock_create_deal.call_args.kwargs.get("owner_id") == "recOWNER000000001"
    and mock_create_deal.call_args.kwargs.get("stage") == DealStage.OPPORTUNITY)
chk("Deal: result passed through unchanged (genuine evidence preserved)",
    result == _OK_RESULT)

with patch("commercial_crm.create_payment_term",
           return_value={"ok": True, "tool": "crm_create_payment_term", "external_id": "recPT01",
                          "evidence": {"record_id": "recPT01"}, "user_message": "✅"}) as mock_pt, \
     patch.object(dispatcher_module, "airtable_add") as mock_generic_add2:
    _dispatch("airtable_add", {
        "table": Tables.PAYMENT_TERMS,
        "fields": {
            PaymentTermFields.DEAL: ["recDEAL0000000001"],
            PaymentTermFields.CALC_TYPE: "fixed",
            PaymentTermFields.FIXED_AMOUNT: 5000,
        },
    }, manager)

chk("PaymentTerm: canonical create_payment_term() was called", mock_pt.call_count == 1)
chk("PaymentTerm: generic airtable_add() was NEVER called", mock_generic_add2.call_count == 0)
chk("PaymentTerm: linked deal_id unwrapped from single-element list",
    mock_pt.call_args.kwargs.get("deal_id") == "recDEAL0000000001")
chk("PaymentTerm: calc_type/fixed_amount mapped correctly",
    mock_pt.call_args.kwargs.get("calc_type") == "fixed"
    and mock_pt.call_args.kwargs.get("fixed_amount") == 5000)

with patch("commercial_crm.create_payment",
           return_value={"ok": True, "tool": "crm_create_payment", "external_id": "recPAY01",
                          "evidence": {"record_id": "recPAY01"}, "user_message": "✅"}) as mock_pay, \
     patch.object(dispatcher_module, "airtable_add") as mock_generic_add3:
    _dispatch("airtable_add", {
        "table": Tables.PAYMENTS,
        "fields": {
            PaymentFields.AMOUNT: 1200.5,
            PaymentFields.DOMAIN: "import",
            PaymentFields.OWNER: "recOWNER000000002",
        },
    }, owner)

chk("Payment: canonical create_payment() was called", mock_pay.call_count == 1)
chk("Payment: generic airtable_add() was NEVER called", mock_generic_add3.call_count == 0)
chk("Payment: linked owner_id accepted as a bare string too (not just a list)",
    mock_pay.call_args.kwargs.get("owner_id") == "recOWNER000000002")


# ══════════════════════════════════════════════════════════════════
print("\n── C/D: invalid/missing generic payload -> canonical validation "
      "failure, not a dispatcher-invented message ──")

# No mocking here — these payloads are missing/invalid on fields the
# canonical writer rejects before ever touching Airtable, so the real
# create_deal()/create_payment_term()/create_payment() can run unmocked.
result_missing_owner = _dispatch("airtable_add", {
    "table": Tables.DEALS,
    "fields": {DealFields.NAME: "עסקה בלי בעלים", DealFields.DOMAIN: "finance"},
}, owner)
chk("Deal: missing owner_id -> the canonical writer's OWN message, verbatim",
    result_missing_owner.get("user_message") == "❌ owner_id חסר.")
chk("Deal: missing-field rejection is ok=False", result_missing_owner.get("ok") is False)

result_bad_calc = _dispatch("airtable_add", {
    "table": Tables.PAYMENT_TERMS,
    "fields": {PaymentTermFields.DEAL: ["recDEAL0000000001"], PaymentTermFields.CALC_TYPE: "bogus"},
}, manager)
chk("PaymentTerm: invalid calc_type -> the canonical writer's OWN message",
    "calculation type" in result_bad_calc.get("user_message", ""))

result_missing_deal = _dispatch("airtable_add", {
    "table": Tables.PAYMENT_TERMS,
    "fields": {PaymentTermFields.CALC_TYPE: "fixed", PaymentTermFields.FIXED_AMOUNT: 100},
}, manager)
chk("PaymentTerm: missing required deal_id -> fail closed with the writer's own message",
    result_missing_deal.get("ok") is False and "deal_id" in result_missing_deal.get("user_message", ""))

result_bad_amount = _dispatch("airtable_add", {
    "table": Tables.PAYMENTS,
    "fields": {PaymentFields.DOMAIN: "general", PaymentFields.OWNER: "recOWNER000000001"},
}, owner)
chk("Payment: missing amount -> fail closed with the writer's own message",
    result_bad_amount.get("ok") is False and "סכום" in result_bad_amount.get("user_message", ""))


# ══════════════════════════════════════════════════════════════════
print("\n── E: an unmappable field fails closed — no silent field loss ──")

with patch("commercial_crm.create_deal") as mock_create_deal_unreached, \
     patch.object(dispatcher_module, "airtable_add") as mock_generic_unreached:
    result_bad_field = _dispatch("airtable_add", {
        "table": Tables.DEALS,
        "fields": {
            DealFields.NAME: "עסקה", DealFields.DOMAIN: "finance",
            DealFields.OWNER: ["recOWNER000000001"],
            "שדה_לא_קיים_בכלל": "value that must never be silently dropped",
        },
    }, owner)

chk("Deal: unrecognized field -> fail closed (ok=False)", result_bad_field.get("ok") is False)
chk("Deal: the unrecognized field name is named in the message (not silently dropped)",
    "שדה_לא_קיים_בכלל" in result_bad_field.get("user_message", ""))
chk("Deal: canonical writer was NEVER called for an unmappable payload",
    mock_create_deal_unreached.call_count == 0)
chk("Deal: generic airtable_add was NEVER called either (no fallback leak)",
    mock_generic_unreached.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── F: employee/non-management caller is denied before the writer "
      "is ever reached ──")

for _table, _fields in (
    (Tables.DEALS, {DealFields.NAME: "x", DealFields.DOMAIN: "finance", DealFields.OWNER: ["rec1"]}),
    (Tables.PAYMENT_TERMS, {PaymentTermFields.DEAL: ["rec1"], PaymentTermFields.CALC_TYPE: "fixed",
                             PaymentTermFields.FIXED_AMOUNT: 1}),
    (Tables.PAYMENTS, {PaymentFields.AMOUNT: 1, PaymentFields.DOMAIN: "finance",
                        PaymentFields.OWNER: "rec1"}),
):
    with patch("commercial_crm.create_deal") as m1, \
         patch("commercial_crm.create_payment_term") as m2, \
         patch("commercial_crm.create_payment") as m3, \
         patch.object(dispatcher_module, "airtable_add") as m4:
        result_employee = _dispatch("airtable_add", {"table": _table, "fields": _fields}, employee)
    chk(f"{_table}: employee denied (ok=False, access-denied message)",
        result_employee.get("ok") is False and "גישה נחסמה" in result_employee.get("user_message", ""))
    chk(f"{_table}: employee denial reached NO writer at all (canonical or generic)",
        m1.call_count == 0 and m2.call_count == 0 and m3.call_count == 0 and m4.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── I: a genuine writer failure is never reported as success ──")

_FAIL_RESULT = {"ok": False, "tool": "crm_create_deal", "external_id": "",
                "evidence": {"table": Tables.DEALS}, "user_message": "❌ יצירת עסקה נכשלה."}
with patch("commercial_crm.create_deal", return_value=_FAIL_RESULT):
    result_fail = _dispatch("airtable_add", {
        "table": Tables.DEALS,
        "fields": {DealFields.NAME: "x", DealFields.DOMAIN: "finance", DealFields.OWNER: ["rec1"]},
    }, owner)
chk("Deal: a writer-reported failure stays ok=False through the redirect",
    result_fail.get("ok") is False and result_fail == _FAIL_RESULT)


# ══════════════════════════════════════════════════════════════════
print("\n── H: a payload tampered with AFTER approval is still rejected — "
      "REAL execution-proof check, not mocked ──")

from core.action_gateway import action_gateway as _gw  # noqa: E402
from tools.dispatcher import _validate_execution_proof  # noqa: E402

_tamper_result = _gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=owner.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": Tables.DEALS, "fields": {
        DealFields.NAME: "עסקה מקורית", DealFields.DOMAIN: "finance",
        DealFields.OWNER: ["recOWNER000000001"],
    }},
    origin_channel="telegram", origin_chat_id=owner.user_id,
    requires_approval=True, identity=owner, trusted_source="agent",
)
assert _tamper_result.ok, f"setup: propose_action failed unexpectedly: {_tamper_result.reason}"
_tamper_contract = _gw.find_contract(_tamper_result.contract_id)

_tamper_execution_context = {
    "contract_id": _tamper_contract.contract_id,
    "approved_by": owner.memory_key,
    "tool_name": _tamper_contract.tool_name,
    "tenant_id": _tamper_contract.tenant_id,
    "canonical_user_id": _tamper_contract.canonical_user_id,
    "business_action_fingerprint": _tamper_contract.business_action_fingerprint,
    "status": "approved",
}
# The exact live-fire check: dispatch_tool()'s _validate_execution_proof
# recomputes the fingerprint from the payload ACTUALLY being dispatched.
# Untampered payload must validate...
_untampered_proof_error = _validate_execution_proof(
    "airtable_add", _tamper_contract.normalized_payload, owner,
    _tamper_execution_context, "agent",
)
chk("tamper-check setup: the untampered, approved payload validates cleanly",
    _untampered_proof_error is None)

# ...but a payload altered after approval (different Deal name) must not.
_tampered_payload = {"table": Tables.DEALS, "fields": {
    DealFields.NAME: "עסקה אחרת לגמרי", DealFields.DOMAIN: "finance",
    DealFields.OWNER: ["recOWNER000000001"],
}}
_tampered_proof_error = _validate_execution_proof(
    "airtable_add", _tampered_payload, owner, _tamper_execution_context, "agent",
)
chk("tampered post-approval payload: execution proof REJECTS (fail closed), "
    "same mechanism as every other requires_approval tool",
    _tampered_proof_error == "approval-sensitive execution proof does not match the action payload.")


print()
print("=" * 50)
print(f"BUG-CRM-BYPASS (Commercial CRM dispatcher bypass closure) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
