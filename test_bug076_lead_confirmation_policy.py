# test_bug076_lead_confirmation_policy.py — BUG-076: split "confirmation"
# from "approval".
#
# Product decision (2026-07-06, following BUG-074): lead capture is low-risk
# and should not require owner approval. Two distinct concepts:
#   1. "confirmation" — the requester confirms the system understood the
#      draft/preview correctly (safe lead create, or a narrow safe-field
#      lead update). Self-confirm allowed for manager/partner/employee.
#   2. "approval" — a privileged identity (owner / "actions.approve") must
#      authorize a sensitive action. Unchanged BUG-074 rule for everything
#      else: any non-lead-capture tool, any Leads write touching a field
#      outside the safe allowlist (status/score/tier/owner/next-step),
#      deletion, financial/legal/deal mutation, outbound messaging.
#
# classify_approval_policy() computes this centrally from the actual
# tool_name/tool_inputs at propose time — never trusted from the caller.

import sys

from core.action_gateway import (
    ActionGateway, ExecutionLedger,
    classify_approval_policy, APPROVAL_POLICY_APPROVAL, APPROVAL_POLICY_SELF_CONFIRM,
)
from identity import Identity, Role

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _make_gw(executor=None) -> ActionGateway:
    gw = ActionGateway(ledger=ExecutionLedger())
    if executor is not None:
        gw._tool_executor = executor
    return gw


def _identity(role: str, uid: str) -> Identity:
    return Identity(
        user_id=uid, role=role, tenant_id="boss_hq", domain_id="general",
        channel="telegram", external_id=uid,
    )


# ══════════════════════════════════════════════════
# classify_approval_policy() — unit-level classification matrix
# ══════════════════════════════════════════════════
print("\n── classify_approval_policy(): classification matrix ──")

chk(
    "lead create, safe fields only → self_confirm",
    classify_approval_policy("airtable_add", {
        "table": "Leads",
        "fields": {"Name": "Dana Levi", "phone": "0501234567", "channel": "telegram",
                   "domain": "real_estate", "source": "owner_dictation", "status": "new",
                   "summary": "text", "Score": 0, "sender_id": "0501234567"},
    }) == APPROVAL_POLICY_SELF_CONFIRM,
)
chk(
    "lead update, safe fields only (phone/summary/domain) → self_confirm",
    classify_approval_policy("airtable_update", {
        "table": "Leads", "record_id": "recXXXXXXXXXXXXXXXX",
        "fields": {"phone": "0501234567", "summary": "text", "domain": "real_estate"},
    }) == APPROVAL_POLICY_SELF_CONFIRM,
)
chk(
    "lead update touching status → approval (protected field)",
    classify_approval_policy("airtable_update", {
        "table": "Leads", "record_id": "recXXXXXXXXXXXXXXXX",
        "fields": {"status": "won"},
    }) == APPROVAL_POLICY_APPROVAL,
)
chk(
    "lead update touching Owner (assignment) → approval",
    classify_approval_policy("airtable_update", {
        "table": "Leads", "record_id": "recXXXXXXXXXXXXXXXX",
        "fields": {"Owner": "recSOMEONE00000001"},
    }) == APPROVAL_POLICY_APPROVAL,
)
chk(
    "lead update touching Score → approval (protected field, not in update allowlist)",
    classify_approval_policy("airtable_update", {
        "table": "Leads", "record_id": "recXXXXXXXXXXXXXXXX",
        "fields": {"Score": 100},
    }) == APPROVAL_POLICY_APPROVAL,
)
chk(
    "non-Leads table → approval regardless of fields",
    classify_approval_policy("airtable_add", {"table": "Deals", "fields": {"phone": "x"}}) == APPROVAL_POLICY_APPROVAL,
)
chk(
    "non-lead-capture tool (gmail_send_draft) → approval",
    classify_approval_policy("gmail_send_draft", {"to": "a@b.com"}) == APPROVAL_POLICY_APPROVAL,
)
chk(
    "financial tool (crm_mark_payment_paid) → approval",
    classify_approval_policy("crm_mark_payment_paid", {"record_id": "recX"}) == APPROVAL_POLICY_APPROVAL,
)
chk(
    "empty fields dict → approval (nothing to allowlist-check, fail closed)",
    classify_approval_policy("airtable_add", {"table": "Leads", "fields": {}}) == APPROVAL_POLICY_APPROVAL,
)
chk(
    "missing fields key entirely → approval (fail closed)",
    classify_approval_policy("airtable_add", {"table": "Leads"}) == APPROVAL_POLICY_APPROVAL,
)


# ══════════════════════════════════════════════════
# 1. employee CAN self-confirm a safe lead-create preview.
# ══════════════════════════════════════════════════
print("\n── 1. employee can self-confirm a safe lead-create preview ──")

executed = []


def _exec(tool_name, tool_inputs, contract_id):
    executed.append((tool_name, tool_inputs))
    return {"ok": True, "external_id": "rec00000000000010"}


gw = _make_gw(_exec)
employee = _identity(Role.EMPLOYEE, "emp_leads")

r = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=employee.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": "Leads", "fields": {
        "Name": "Dana Levi", "phone": "0501234567", "channel": "telegram",
        "domain": "real_estate", "source": "owner_dictation", "status": "new",
        "summary": "interested in a 3-room apartment", "Score": 0, "sender_id": "0501234567",
    }},
    origin_channel="telegram", origin_chat_id=employee.external_id,
    requires_approval=True, identity=employee,
)
chk("propose_action ok for employee lead-create preview", r.ok)

live = gw.find_live_contracts(employee.memory_key)
chk("contract classified as self_confirm", live and live[0].approval_policy == APPROVAL_POLICY_SELF_CONFIRM)

reply = gw.route_confirmation_word(employee.memory_key, approver_role=employee.role)
chk("employee self-confirm succeeds (no ⛔)", "⛔" not in reply)
chk("tool dispatched exactly once", len(executed) == 1)
chk("dispatched tool is airtable_add", executed[0][0] == "airtable_add")


# ══════════════════════════════════════════════════
# 2. employee CANNOT self-confirm a non-lead approval-required action.
# ══════════════════════════════════════════════════
print("\n── 2. employee cannot self-confirm a non-lead approval-required action ──")

executed2 = []


def _exec2(tool_name, tool_inputs, contract_id):
    executed2.append(tool_name)
    return {"ok": True, "external_id": "rec00000000000011"}


gw2 = _make_gw(_exec2)
r2 = gw2.propose_action(
    tenant_id="boss_hq", canonical_user_id=employee.memory_key,
    tool_name="airtable_add", tool_inputs={"table": "Deals", "fields": {"Name": "Big Deal"}},
    origin_channel="telegram", origin_chat_id=employee.external_id,
    requires_approval=True, identity=employee,
)
chk("propose_action ok for employee non-lead request", r2.ok)
reply2 = gw2.route_confirmation_word(employee.memory_key, approver_role=employee.role)
chk("employee self-confirm on non-lead action is denied", "⛔" in reply2)
chk("non-lead tool NOT dispatched", len(executed2) == 0)


# ══════════════════════════════════════════════════
# 3. employee CANNOT self-confirm a lead update that touches a protected
# field (status escalation / assignment) — even though the table is Leads.
# ══════════════════════════════════════════════════
print("\n── 3. employee cannot self-confirm lead status/protected-field update ──")

executed3 = []


def _exec3(tool_name, tool_inputs, contract_id):
    executed3.append(tool_name)
    return {"ok": True, "external_id": "rec00000000000012"}


gw3 = _make_gw(_exec3)
r3 = gw3.propose_action(
    tenant_id="boss_hq", canonical_user_id=employee.memory_key,
    tool_name="airtable_update",
    tool_inputs={"table": "Leads", "record_id": "recXXXXXXXXXXXXXXXX", "fields": {"status": "won"}},
    origin_channel="telegram", origin_chat_id=employee.external_id,
    requires_approval=True, identity=employee,
)
chk("propose_action ok for employee status-change request", r3.ok)
live3 = gw3.find_live_contracts(employee.memory_key)
chk("contract classified as approval (protected field), not self_confirm",
    live3 and live3[0].approval_policy == APPROVAL_POLICY_APPROVAL)
reply3 = gw3.route_confirmation_word(employee.memory_key, approver_role=employee.role)
chk("employee self-confirm on lead status escalation is denied", "⛔" in reply3)
chk("status-change tool NOT dispatched", len(executed3) == 0)

# also verify a hypothetical "delete" tool never qualifies for self_confirm
# even on the Leads table, purely by not being in the lead-capture tool set
chk(
    "a hypothetical airtable_delete on Leads is never self_confirm (tool not allowlisted)",
    classify_approval_policy("airtable_delete", {"table": "Leads", "fields": {"phone": "x"}}) == APPROVAL_POLICY_APPROVAL,
)


# ══════════════════════════════════════════════════
# 4. owner / actions.approve CAN approve a true approval-required action
# (unaffected by the self-confirm carve-out).
# ══════════════════════════════════════════════════
print("\n── 4. owner can still approve true approval-required actions ──")

owner = _identity(Role.OWNER, "owner_1")
pending = gw3.find_live_contracts(employee.memory_key)[0]
reply4 = gw3.approve(pending.contract_id, approver=owner.memory_key, approver_role=owner.role)
chk("owner approval of the status-change contract succeeds", "⛔" not in reply4)
chk("status-change tool dispatched exactly once after owner approval", len(executed3) == 1)
chk("dispatched tool is airtable_update", executed3 == ["airtable_update"])


# ══════════════════════════════════════════════════
# 5. approve() remains the central boundary for approval-policy actions —
# a DIFFERENT non-owner identity may not "self-confirm" someone else's
# approval-required contract, and self_confirm contracts still require the
# SAME requester (not just any internal role) to confirm.
# ══════════════════════════════════════════════════
print("\n── 5. approve() remains the central boundary ──")

executed5 = []


def _exec5(tool_name, tool_inputs, contract_id):
    executed5.append(tool_name)
    return {"ok": True, "external_id": "rec00000000000013"}


gw5 = _make_gw(_exec5)
manager = _identity(Role.MANAGER, "mgr_other")
r5 = gw5.propose_action(
    tenant_id="boss_hq", canonical_user_id=employee.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": "Leads", "fields": {"Name": "Another Lead", "phone": "0507654321"}},
    origin_channel="telegram", origin_chat_id=employee.external_id,
    requires_approval=True, identity=employee,
)
chk("propose_action ok for employee lead-create (second scenario)", r5.ok)
pending5 = gw5.find_live_contracts(employee.memory_key)[0]
chk("self_confirm classification confirmed", pending5.approval_policy == APPROVAL_POLICY_SELF_CONFIRM)

# a DIFFERENT internal identity (manager) is not the requester — approve()
# must still reject them for a self_confirm contract, since self_confirm
# means "the requester confirms their own draft," not "any internal role
# may confirm anyone's draft."
reply5a = gw5.approve(pending5.contract_id, approver=manager.memory_key, approver_role=manager.role)
chk("a different manager cannot self-confirm someone else's lead preview", "⛔" in reply5a)
chk("tool still not dispatched", len(executed5) == 0)

# the actual requester (employee) confirming their own draft still works
reply5b = gw5.approve(pending5.contract_id, approver=employee.memory_key, approver_role=employee.role)
chk("the original requester can confirm their own draft", "⛔" not in reply5b)
chk("tool dispatched exactly once", len(executed5) == 1)


print("\n" + "=" * 50)
print(f"BUG-076 lead confirmation policy tests: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
