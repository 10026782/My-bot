# test_bug073_approval_authority.py — BUG-074: ActionGateway.approve() must be
# the sole authorization enforcement boundary for every approval path.
#
# Before the fix: route_confirmation_word()/route_disambiguation()/
# route_combined_word() always call approve(contract_id, approver=canonical_user_id)
# with the SAME identity that requested the action (these routes only ever find
# contracts belonging to the confirming user's own canonical_user_id). approve()'s
# only mismatch check logged a warning and never blocked, so any role permitted to
# call a requires_approval=True tool (e.g. employee for airtable_add) could
# self-approve it via a bare "כן"/"מאשר", with zero real owner sign-off.
#
# After the fix: approve() takes an explicit approver_role and hard-fails unless
# that role is owner or holds "actions.approve" — regardless of who the original
# requester was, and regardless of whether requester == approver.
#
# BUG-076 (later, separate policy decision) carves out a narrow self-confirm
# exception for SAFE lead-capture writes specifically — see
# test_bug076_lead_confirmation_policy.py. The scenarios here intentionally
# use a NON-lead-capture tool (table="Deals") so they keep testing the
# general/strict rule, unaffected by that carve-out.

import sys

from core.action_gateway import ActionGateway, ExecutionLedger, _has_approval_authority
from identity import Identity, Role, ROLE_PERMISSIONS

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
# 1-3: employee requests a requires_approval tool, self-confirms via free
# text — must NOT dispatch.
# ══════════════════════════════════════════════════
print("\n── BUG-074: employee self-approval via free-text confirm is blocked ──")

executed = []


def _exec(tool_name, tool_inputs, contract_id):
    executed.append(tool_name)
    return {"ok": True, "external_id": "rec00000000000001"}


gw = _make_gw(_exec)
employee = _identity(Role.EMPLOYEE, "emp1")

r = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=employee.memory_key,
    tool_name="airtable_add", tool_inputs={"table": "Deals", "fields": {"Name": "Test"}},
    origin_channel="telegram", origin_chat_id=employee.external_id,
    requires_approval=True, identity=employee,
)
chk("propose_action ok for employee-requested airtable_add (Deals, not lead-capture)", r.ok)

reply = gw.route_confirmation_word(employee.memory_key, approver_role=employee.role)
chk("BUG-074: employee self-confirm is denied", "⛔" in reply and "בעלים" in reply)
chk("BUG-074: tool NOT dispatched on unauthorized self-approval", len(executed) == 0)

# 4. contract stays pending (not silently consumed) so a real approver can still act
live = gw.find_live_contracts(employee.memory_key)
chk("BUG-074: contract remains pending after denied approval", len(live) == 1)
chk("BUG-074: contract status is still 'pending'", live and live[0].status == "pending")

# repeated self-confirm attempts still don't leak through
gw.route_confirmation_word(employee.memory_key, approver_role=employee.role)
gw.route_confirmation_word(employee.memory_key, approver_role=employee.role)
chk("BUG-074: repeated unauthorized self-confirms still never dispatch", len(executed) == 0)


# ══════════════════════════════════════════════════
# 5. Owner (or another identity holding actions.approve) CAN approve the same
# pending contract.
# ══════════════════════════════════════════════════
print("\n── BUG-074: an identity with real approval authority can approve ──")

owner = _identity(Role.OWNER, "owner1")
pending_contract_id = live[0].contract_id
reply2 = gw.approve(pending_contract_id, approver=owner.memory_key, approver_role=owner.role)
chk("BUG-074: owner approval is not denied", "⛔" not in reply2)
chk("BUG-074: tool dispatched exactly once after authorized approval", len(executed) == 1)
chk("BUG-074: dispatched tool is airtable_add", executed == ["airtable_add"])


# ══════════════════════════════════════════════════
# manager also lacks approval authority by default permission map (only
# "actions.approve" grants it, and only Role.OWNER currently holds it) —
# same self-approval attempt on a fresh contract must also be denied.
# Uses table="Leads" but field "Name" — NOT in BUG-076's update-safe-fields
# allowlist ({phone, summary, domain}), so this still classifies as strict
# APPROVAL_POLICY_APPROVAL despite being on the Leads table.
# ══════════════════════════════════════════════════
print("\n── BUG-074: manager self-approval is also blocked (not owner-specific) ──")

executed2 = []


def _exec2(tool_name, tool_inputs, contract_id):
    executed2.append(tool_name)
    return {"ok": True, "external_id": "rec00000000000002"}


gw2 = _make_gw(_exec2)
manager = _identity(Role.MANAGER, "mgr1")
r2 = gw2.propose_action(
    tenant_id="boss_hq", canonical_user_id=manager.memory_key,
    tool_name="airtable_update",
    tool_inputs={"table": "Leads", "record_id": "recXXXXXXXXXXXXXXXX", "fields": {"Name": "X"}},
    origin_channel="telegram", origin_chat_id=manager.external_id,
    requires_approval=True, identity=manager,
)
chk("propose_action ok for manager-requested airtable_update", r2.ok)
reply3 = gw2.route_confirmation_word(manager.memory_key, approver_role=manager.role)
chk("BUG-074: manager self-confirm is denied", "⛔" in reply3)
chk("BUG-074: manager self-approval tool NOT dispatched", len(executed2) == 0)


# ══════════════════════════════════════════════════
# 7. FEATURE_ACTION_GATEWAY=false shadow-mode behavior is unaffected by this
# fix — propose_action() itself never blocked (shadow mode is a separate,
# pre-existing concern in app.py's caller, not in approve()); the flag
# still defaults off.
# ══════════════════════════════════════════════════
print("\n── BUG-074: shadow-mode default (FEATURE_ACTION_GATEWAY=false) unchanged ──")

import os
os.environ.pop("FEATURE_ACTION_GATEWAY", None)
from feature_flags import is_enabled
chk("FEATURE_ACTION_GATEWAY still defaults off", is_enabled("FEATURE_ACTION_GATEWAY") is False)

gw3 = _make_gw(_exec2)
r3 = gw3.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:someone",
    tool_name="airtable_add", tool_inputs={"table": "Leads", "fields": {"Name": "Y"}},
    origin_channel="telegram", origin_chat_id="someone",
    requires_approval=True,
)
chk("BUG-074: propose_action still succeeds regardless of approve()'s new gate", r3.ok)


# ══════════════════════════════════════════════════
# 6. Callback flow (app.py's _handle_approval_callback_impl) and the
# free-text flow (approve()) must share the same authorization outcome for
# every role. The callback flow's own check is:
#     approver_identity.is_owner or approver_identity.can("actions.approve")
# _has_approval_authority(role) must agree with that expression for every
# role in the system, and app.py's source must still contain that exact
# check (static regression guard — proves the callback flow's own gate
# was not weakened while fixing the free-text path).
# ══════════════════════════════════════════════════
print("\n── BUG-074: callback-flow and free-text-flow authorization parity ──")

for role in (Role.OWNER, Role.PARTNER, Role.MANAGER, Role.EMPLOYEE, Role.LEAD, Role.GUEST, Role.READONLY):
    callback_flow_check = (role == Role.OWNER) or ("actions.approve" in ROLE_PERMISSIONS.get(role, set()))
    gateway_check = _has_approval_authority(role)
    chk(f"parity for role={role}: callback-flow == Gateway.approve()", callback_flow_check == gateway_check)

with open("app.py", encoding="utf-8") as f:
    _app_src = f.read()
chk(
    "app.py callback flow still checks is_owner or can('actions.approve') before approving",
    'approver_identity.is_owner or approver_identity.can("actions.approve")' in _app_src,
)


print("\n" + "=" * 50)
print(f"BUG-074 approval authority tests: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
