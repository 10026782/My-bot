#!/usr/bin/env python3
"""
test_bug_crm_bypass_airtable_update.py — BUG-CRM-BYPASS-UPDATE
(closes the generic airtable_update bypass into Deals/Payments/Payment
Terms via _CRM_TABLE_ROUTING, and into Tasks via _TASK_ALLOWED_UPDATE_FIELDS).

Found during an external read-only audit of origin/main (02/09/2026),
immediately after BUG-CRM-BYPASS/BUG-CRM-BYPASS-DOMAIN-TRANSLATION closed
the equivalent gaps for airtable_add and the deterministic create_deal
route: tools/dispatcher.py's "airtable_update" case had the Contacts
redirect (crm.update_contact()) but NO equivalent for Deals/Payment
Terms/Payments — a raw airtable_update(table="Deals"/"Payments"/
"Payment Terms", ...) fell straight through to the generic Airtable write,
with no role re-check narrower than airtable_update's own (wider) grant,
no field allowlist, and no domain canonicalization on a Domain field edit.

Unlike Contacts, there is no general canonical "update_deal()"-style writer
to redirect to, and Intent.UPDATE_DEAL_STAGE legitimately relies on this
same generic airtable_update today (core/router/risk_router.py's
contract-required-tool mapping) -- so the fix cannot simply block these
tables outright. Instead it reuses the SAME closed field maps the create
path already validates against (_DEAL_FIELD_MAP/_PAYMENT_TERM_FIELD_MAP/
_PAYMENT_FIELD_MAP), re-checks the canonical tool's role authority the same
way airtable_add's redirect does, and canonicalizes a Domain field edit
through core.lead_service.resolve_domain_word() -- the same shared resolver
Leads and (as of BUG-CRM-BYPASS-DOMAIN-TRANSLATION) the deterministic Deal
parser already use.

Follow-up (owner rule, 02/09/2026): "airtable_update may only write system/
infrastructure data directly; business records must be blocked or
redirected" extended to Tasks. Tasks has no dedicated create-tool narrower
than airtable_add/airtable_update to under-cut (Task creation itself goes
through the SAME airtable_add, gated only by deterministic routing, not
tool identity), so there is no role-gap to re-check -- only the same
missing field-allowlist/domain-canonicalization gap, closed the same way
via a plain field-name allowlist (_TASK_ALLOWED_UPDATE_FIELDS).

This file exercises the REAL dispatch_tool()/enforce()/field-allowlist
logic end-to-end; the underlying airtable_update() call is mocked (no live
Airtable access), matching test_bug_commercial_crm_dispatcher_bypass_closure.py's
existing convention for the create-path equivalent of this test.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-crmbypass-update-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:CRM_BYPASS_UPDATE_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patCrmBypassUpdateTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCrmBypassUpdateTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import tools.dispatcher as dispatcher_module  # noqa: E402
from tools.dispatcher import dispatch_tool  # noqa: E402
from airtable_schema import Tables, DealFields, PaymentFields, DealStage, TaskFields  # noqa: E402
from identity import Identity, Role  # noqa: E402

_no_emergency_stop = patch.object(dispatcher_module._ff, "is_enabled", return_value=False)
_no_emergency_stop.start()


def chk(desc: str, cond: bool) -> None:
    assert cond, desc
    print(f"✅ {desc}")


owner = Identity(
    user_id="owner-crmbypass-upd", role=Role.OWNER, display_name="owner-crmbypass-upd",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="owner-crmbypass-upd",
)
employee = Identity(
    user_id="employee-crmbypass-upd", role=Role.EMPLOYEE, display_name="employee-crmbypass-upd",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="employee-crmbypass-upd",
)


def _dispatch(name, inputs, identity, execution_context=None):
    """Bypasses _validate_execution_proof for case-routing tests, exactly
    like test_bug_commercial_crm_dispatcher_bypass_closure.py does."""
    with patch.object(dispatcher_module, "_validate_execution_proof", return_value=None):
        return dispatch_tool(name, inputs, identity=identity, trusted_source="agent",
                              execution_context=execution_context or {"contract_id": "c1"})


# ══════════════════════════════════════════════════════════════════
print("── legitimate use: Intent.UPDATE_DEAL_STAGE's own field passes through ──")

with patch.object(dispatcher_module, "airtable_update", return_value={
    "ok": True, "tool": "airtable_update", "external_id": "recDEAL01",
    "evidence": {"record_id": "recDEAL01"}, "user_message": "✅",
}) as mock_generic_update:
    result = _dispatch("airtable_update", {
        "table": Tables.DEALS, "record_id": "recDEAL01",
        "fields": {DealFields.STAGE: DealStage.CLOSED_WIN},
    }, owner)
chk("Deal stage update: still reaches the generic writer (no writer to redirect to)",
    mock_generic_update.call_count == 1)
chk("Deal stage update: table/record_id/fields forwarded unchanged",
    mock_generic_update.call_args.args == (Tables.DEALS, "recDEAL01", {DealFields.STAGE: DealStage.CLOSED_WIN}))
chk("Deal stage update: result passed through", result.get("ok") is True)


# ══════════════════════════════════════════════════════════════════
print("\n── domain canonicalization: raw Hebrew word rejected, canonical slug written ──")

with patch.object(dispatcher_module, "airtable_update", return_value={
    "ok": True, "tool": "airtable_update", "external_id": "recDEAL01",
    "evidence": {}, "user_message": "✅",
}) as mock_update_raw:
    result_raw_domain = _dispatch("airtable_update", {
        "table": Tables.DEALS, "record_id": "recDEAL01",
        "fields": {DealFields.DOMAIN: "יבוא"},
    }, owner)
chk("Deal domain update: raw Hebrew word never reaches Airtable directly unmapped",
    mock_update_raw.call_args.args[2][DealFields.DOMAIN] == "import")
chk("Deal domain update: succeeds once canonicalized", result_raw_domain.get("ok") is True)

with patch.object(dispatcher_module, "airtable_update") as mock_update_bad:
    result_bad_domain = _dispatch("airtable_update", {
        "table": Tables.PAYMENTS, "record_id": "recPAY01",
        "fields": {PaymentFields.DOMAIN: "שטויות"},
    }, owner)
chk("Payment domain update: unrecognized word fails closed (ok=False)",
    result_bad_domain.get("ok") is False)
chk("Payment domain update: unrecognized word never reaches Airtable",
    mock_update_bad.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── BUG-CRM-BYPASS-DOMAIN-SELECT-CASING: canonical slug -> live Airtable value ──")
# Same fix as commercial_crm.py's create_deal()/create_payment() (this
# update path has no canonical writer to redirect to, so the mapping
# happens directly in the dispatcher instead).

with patch.object(dispatcher_module, "airtable_update", return_value={
    "ok": True, "tool": "airtable_update", "external_id": "recDEAL01",
    "evidence": {}, "user_message": "✅",
}) as mock_update_live, \
     patch("core.runtime_schema_provider.resolve_live_select_value", return_value="Import") as resolve:
    result_live_domain = _dispatch("airtable_update", {
        "table": Tables.DEALS, "record_id": "recDEAL01",
        "fields": {DealFields.DOMAIN: "Import"},
    }, owner)
chk("Deal domain update: resolve_live_select_value called with the canonical slug",
    resolve.call_args.args == (Tables.DEALS, DealFields.DOMAIN, "import"))
chk("Deal domain update: the LIVE resolved value is written, not the raw canonical slug",
    mock_update_live.call_args.args[2][DealFields.DOMAIN] == "Import")
chk("Deal domain update: succeeds once the live value resolves", result_live_domain.get("ok") is True)

with patch.object(dispatcher_module, "airtable_update") as mock_update_unresolvable, \
     patch("core.runtime_schema_provider.resolve_live_select_value", return_value=None):
    result_unresolvable = _dispatch("airtable_update", {
        "table": Tables.DEALS, "record_id": "recDEAL01",
        "fields": {DealFields.DOMAIN: "import"},
    }, owner)
chk("Deal domain update: a value resolve_live_select_value can't match fails closed",
    result_unresolvable.get("ok") is False)
chk("Deal domain update: never reaches Airtable when the live value can't be resolved",
    mock_update_unresolvable.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── field allowlist: unmappable field fails closed — no silent field loss ──")

with patch.object(dispatcher_module, "airtable_update") as mock_update_unmapped:
    result_bad_field = _dispatch("airtable_update", {
        "table": Tables.DEALS, "record_id": "recDEAL01",
        "fields": {"שדה_לא_קיים_בכלל": "value that must never be silently written"},
    }, owner)
chk("Deal update: unrecognized field -> fail closed (ok=False)", result_bad_field.get("ok") is False)
chk("Deal update: the unrecognized field name is named in the message",
    "שדה_לא_קיים_בכלל" in result_bad_field.get("user_message", ""))
chk("Deal update: generic airtable_update was NEVER called for an unmappable payload",
    mock_update_unmapped.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── role gate: employee denied before the writer is ever reached ──")

# Unlike airtable_add (roles_allowed=_INTERNAL, includes "employee"),
# airtable_update's OWN registry entry is already roles_allowed=_MANAGEMENT
# (tool_registry.py) -- the same bar as crm_create_deal/_payment_term/
# _payment. So an employee is denied by dispatch_tool()'s own top-level
# enforce(name, identity) call before this case statement is ever reached,
# returning a plain string (not this block's _tool_result() dict) -- this
# new code's own enforce(_canonical_tool, identity) re-check is inert today
# (there is no role currently in airtable_update's allowed set but excluded
# from the canonical tool's), kept only as defense-in-depth against a future
# widening of airtable_update's role set, mirroring the create path exactly.
with patch.object(dispatcher_module, "airtable_update") as mock_update_denied:
    result_employee = _dispatch("airtable_update", {
        "table": Tables.DEALS, "record_id": "recDEAL01",
        "fields": {DealFields.STAGE: DealStage.CLOSED_WIN},
    }, employee)
chk("Deal update: employee denied (plain-string access-denied message)",
    isinstance(result_employee, str) and "גישה נחסמה" in result_employee)
chk("Deal update: employee denial never reaches the writer at all",
    mock_update_denied.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── protected aliases resolve the same way as the create path ──")

for alias in ("Deals", " deals ", "DEALS", Tables.DEALS):
    with patch.object(dispatcher_module, "airtable_update", return_value={
        "ok": True, "tool": "airtable_update", "external_id": "recDEAL01",
        "evidence": {}, "user_message": "✅",
    }) as m_writer:
        _dispatch("airtable_update", {
            "table": alias, "record_id": "recDEAL01", "fields": {DealFields.STAGE: DealStage.CLOSED_WIN},
        }, owner)
    chk(f"Deal alias {alias!r}: resolves to the protected table's field map", m_writer.call_count == 1)

with patch.object(dispatcher_module, "airtable_update") as m_bad_alias:
    result_bad_alias = _dispatch("airtable_update", {
        "table": "DealsXYZ", "record_id": "recDEAL01", "fields": {},
    }, owner)
chk("Non-protected table name: passes through as a normal (non-CRM) update",
    m_bad_alias.call_count == 1)

with patch.object(dispatcher_module, "airtable_update") as m_ambiguous:
    result_ambiguous = _dispatch("airtable_update", {
        "table": "PaymentTerms", "record_id": "recPT01", "fields": {},
    }, owner)
chk("Ambiguous protected-looking alias ('PaymentTerms', no space): fails closed",
    result_ambiguous.get("ok") is False)
chk("Ambiguous protected-looking alias: never reaches any writer",
    m_ambiguous.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── Tasks: legitimate updates still work, unsupported fields fail closed ──")

with patch.object(dispatcher_module, "airtable_update", return_value={
    "ok": True, "tool": "airtable_update", "external_id": "recTASK01",
    "evidence": {}, "user_message": "✅",
}) as m_task:
    result_task = _dispatch("airtable_update", {
        "table": "משימות (Tasks)", "record_id": "recTASK01",
        "fields": {TaskFields.STATUS: "בוצע"},
    }, owner)
chk("Task status update: still reaches the generic writer (allowed field)",
    m_task.call_count == 1 and result_task.get("ok") is True)

for alias in ("Tasks", "משימות (Tasks)", Tables.TASKS):
    with patch.object(dispatcher_module, "airtable_update", return_value={
        "ok": True, "tool": "airtable_update", "external_id": "recTASK01",
        "evidence": {}, "user_message": "✅",
    }) as m_task_alias:
        _dispatch("airtable_update", {
            "table": alias, "record_id": "recTASK01",
            "fields": {TaskFields.DESCRIPTION: "d"},
        }, owner)
    chk(f"Task alias {alias!r}: resolves to the Tasks allowlist", m_task_alias.call_count == 1)

with patch.object(dispatcher_module, "airtable_update") as m_task_unmapped:
    result_task_bad_field = _dispatch("airtable_update", {
        "table": "משימות (Tasks)", "record_id": "recTASK01",
        "fields": {"שדה_לא_קיים_בכלל": "value that must never be silently written"},
    }, owner)
chk("Task update: unrecognized field -> fail closed (ok=False)",
    result_task_bad_field.get("ok") is False)
chk("Task update: the unrecognized field name is named in the message",
    "שדה_לא_קיים_בכלל" in result_task_bad_field.get("user_message", ""))
chk("Task update: generic airtable_update was NEVER called for an unmappable payload",
    m_task_unmapped.call_count == 0)

with patch.object(dispatcher_module, "airtable_update", return_value={
    "ok": True, "tool": "airtable_update", "external_id": "recTASK01",
    "evidence": {}, "user_message": "✅",
}) as m_task_domain:
    result_task_domain = _dispatch("airtable_update", {
        "table": "משימות (Tasks)", "record_id": "recTASK01",
        "fields": {TaskFields.DOMAIN: "יבוא"},
    }, owner)
chk("Task domain update: raw Hebrew word canonicalized before the write",
    m_task_domain.call_args.args[2][TaskFields.DOMAIN] == "import")
chk("Task domain update: succeeds once canonicalized", result_task_domain.get("ok") is True)

with patch.object(dispatcher_module, "airtable_update") as m_task_bad_domain:
    result_task_bad_domain = _dispatch("airtable_update", {
        "table": "משימות (Tasks)", "record_id": "recTASK01",
        "fields": {TaskFields.DOMAIN: "שטויות"},
    }, owner)
chk("Task domain update: unrecognized word fails closed (ok=False)",
    result_task_bad_domain.get("ok") is False)
chk("Task domain update: unrecognized word never reaches Airtable",
    m_task_bad_domain.call_count == 0)

with patch.object(dispatcher_module, "airtable_update", return_value={
    "ok": True, "tool": "airtable_update", "external_id": "recTASK01",
    "evidence": {}, "user_message": "✅",
}) as m_task_live, \
     patch("core.runtime_schema_provider.resolve_live_select_value", return_value="Import") as resolve_task:
    result_task_live = _dispatch("airtable_update", {
        "table": "משימות (Tasks)", "record_id": "recTASK01",
        "fields": {TaskFields.DOMAIN: "Import"},
    }, owner)
chk("Task domain update: resolve_live_select_value called with the canonical slug",
    resolve_task.call_args.args == (Tables.TASKS, TaskFields.DOMAIN, "import"))
chk("Task domain update: the LIVE resolved value is written, not the raw canonical slug",
    m_task_live.call_args.args[2][TaskFields.DOMAIN] == "Import")
chk("Task domain update: succeeds once the live value resolves", result_task_live.get("ok") is True)

with patch.object(dispatcher_module, "airtable_update") as m_task_unresolvable, \
     patch("core.runtime_schema_provider.resolve_live_select_value", return_value=None):
    result_task_unresolvable = _dispatch("airtable_update", {
        "table": "משימות (Tasks)", "record_id": "recTASK01",
        "fields": {TaskFields.DOMAIN: "import"},
    }, owner)
chk("Task domain update: a value resolve_live_select_value can't match fails closed",
    result_task_unresolvable.get("ok") is False)
chk("Task domain update: never reaches Airtable when the live value can't be resolved",
    m_task_unresolvable.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── non-protected tables are entirely unaffected ──")

with patch.object(dispatcher_module, "airtable_update", return_value={
    "ok": True, "tool": "airtable_update", "external_id": "recX01",
    "evidence": {}, "user_message": "✅",
}) as m_other:
    result_other = _dispatch("airtable_update", {
        "table": "Expenses", "record_id": "recX01", "fields": {"כל שדה שהוא": "value"},
    }, owner)
chk("A table with no registered allowlist (Expenses): any field passes through unchanged",
    m_other.call_count == 1 and result_other.get("ok") is True)


print()
print("=" * 50)
print("BUG-CRM-BYPASS-UPDATE (Commercial CRM airtable_update closure) tests: PASS")


def test_crm_bypass_update_closure_completed() -> None:
    """pytest entry point — the assertions above already ran at import time."""
    assert True
