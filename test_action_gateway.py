# test_action_gateway.py — Regression tests for Stage B: ActionContract + Action Gateway
#
# DoD coverage:
#   §9 items: 11, 12, 13, 15, 16, 17 (Stage B items)
#   §9 items: 1-3, 6, 8 (regression for Stage A + core invariants)

import hashlib
import re
import sys
import time

from core.action_gateway import (
    ActionContract,
    ActionGateway,
    AgentObservation,
    DuplicateOverrideApproval,
    ExecutionLedger,
    GatewayResult,
    _hash_challenge,
    _gen_challenge_code,
    action_gateway,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _make_gw() -> ActionGateway:
    return ActionGateway(ledger=ExecutionLedger())


# ══════════════════════════════════════════════════
# DoD §1: same action from WhatsApp + Telegram → same fingerprint
# ══════════════════════════════════════════════════
print("\n── DoD §1: cross-channel fingerprint equality ───────────────")
gw = _make_gw()
fp_wa = gw.compute_business_fingerprint(
    "boss_hq", "boss_hq:user_42", "sheets_append",
    gw.normalize_payload({"spreadsheet_name": "Sales", "row": "VIP"}),
)
fp_tg = gw.compute_business_fingerprint(
    "boss_hq", "boss_hq:user_42", "sheets_append",
    gw.normalize_payload({"row": "VIP", "spreadsheet_name": "Sales"}),
)
chk("DoD1: WhatsApp fingerprint == Telegram fingerprint (same canonical user)", fp_wa == fp_tg)
fp_other = gw.compute_business_fingerprint(
    "boss_hq", "boss_hq:user_99", "sheets_append",
    gw.normalize_payload({"spreadsheet_name": "Sales", "row": "VIP"}),
)
chk("DoD1: different canonical_user_id → different fingerprint", fp_wa != fp_other)


# ══════════════════════════════════════════════════
# DoD §11: same business_fingerprint → only one pending approval
# ══════════════════════════════════════════════════
print("\n── DoD §11: one pending per business fingerprint ────────────")
gw = _make_gw()
r1 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:user_42",
    tool_name="sheets_append",
    tool_inputs={"spreadsheet_name": "Sales", "row": "VIP"},
    origin_channel="whatsapp", origin_chat_id="wa:97250",
    requires_approval=True,
    user_text="add VIP to Google Sheets",
)
chk("DoD11: first propose → ok=True", r1.ok)
chk("DoD11: first propose → contract_id assigned", r1.contract_id is not None)

r2 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:user_42",
    tool_name="sheets_append",
    tool_inputs={"row": "VIP", "spreadsheet_name": "Sales"},  # רשימה שונה, payload זהה
    origin_channel="telegram", origin_chat_id="tg:7228089151",
    requires_approval=True,
    user_text="add VIP to Google Sheets",
)
chk("DoD11: duplicate propose → ok=False (pending exists)", not r2.ok)
chk("DoD11: duplicate propose → same contract_id returned", r2.contract_id == r1.contract_id)
chk("DoD11: user_message mentions pending approval", "פתוח" in (r2.user_message or "") or "ממתינ" in (r2.user_message or ""))

# שליחת "מאשר" שלוש פעמים — DoD §12
print("\n── DoD §12: triple confirm → executed once ──────────────────")
gw = _make_gw()
executions = []

def _mock_executor(tool_name, tool_inputs, contract_id):
    executions.append(tool_name)
    return f"executed {tool_name}"

gw._tool_executor = _mock_executor
r = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="gmail_send_draft",
    tool_inputs={"to": "a@b.com"},
    origin_channel="telegram", origin_chat_id="tg:111",
    requires_approval=True,
)
cid = r.contract_id

gw.approve(cid, approver="boss_hq:owner_1", approver_role="owner")  # ביצוע ראשון
result2 = gw.approve(cid, approver="boss_hq:owner_1", approver_role="owner")  # שני — מצב כבר executed
result3 = gw.approve(cid, approver="boss_hq:owner_1", approver_role="owner")  # שלישי

chk("DoD12: tool executed exactly once", len(executions) == 1)
chk("DoD12: second approve returns warning", "אינה במצב" in result2)
chk("DoD12: third approve returns warning", "אינה במצב" in result3)


# ══════════════════════════════════════════════════
# DoD §13: AgentObservation stored, never user-facing as execution status
# ══════════════════════════════════════════════════
print("\n── DoD §13: AgentObservation stored, not user-facing ────────")
gw = _make_gw()
r = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:user_1",
    tool_name="sheets_append", tool_inputs={"spreadsheet_name": "X", "row": "1"},
    origin_channel="telegram", origin_chat_id="tg:1",
    requires_approval=True,
    user_text="add row to Google Sheets",
)
obs = gw.record_agent_observation(r.contract_id, "uncertainty", "Agent חש אי-ודאות בשם הגיליון")
chk("DoD13: AgentObservation kind=uncertainty", obs.kind == "uncertainty")
chk("DoD13: AgentObservation stored on contract", len(gw.find_contract(r.contract_id).agent_observations) == 1)
# AgentObservation.text לא אמור להגיע ישירות כתוצאה של approve/propose
gw_result_text = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:user_2",
    tool_name="sheets_append", tool_inputs={"spreadsheet_name": "Y", "row": "2"},
    origin_channel="telegram", origin_chat_id="tg:2",
    requires_approval=True,
    user_text="add row to Google Sheets",
)
chk("DoD13: GatewayResult does not expose AgentObservation text", "uncertainty" not in (gw_result_text.user_message or ""))


# ══════════════════════════════════════════════════
# DoD §15 + §16: DuplicateOverrideApproval — חד-פעמי, hash only
# ══════════════════════════════════════════════════
print("\n── DoD §15/§16: override — one-shot, hash-only ──────────────")
executions2 = []

def _mock_exec2(tool_name, tool_inputs, contract_id):
    executions2.append(tool_name)
    return "done"

gw2 = _make_gw()
gw2._tool_executor = _mock_exec2

# הצע ובצע כדי להגיע למצב executed
r_orig = gw2.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="airtable_add", tool_inputs={"table": "Leads", "fields": {"Name": "X"}},
    origin_channel="telegram", origin_chat_id="tg:1",
    requires_approval=False,
)
chk("DoD15 setup: first propose ok", r_orig.ok)
# manually set to executed so duplicate check triggers
gw2._ledger.update_status(r_orig.contract_id, "executed")

# עכשיו הצע שוב — אמור להחזיר ok=False עם challenge code
r_dup = gw2.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="airtable_add", tool_inputs={"table": "Leads", "fields": {"Name": "X"}},
    origin_channel="telegram", origin_chat_id="tg:1",
    requires_approval=False,
)
chk("DoD15: duplicate executed → ok=False", not r_dup.ok)
chk("DoD15: user_message contains 'בצע שוב'", "בצע שוב" in (r_dup.user_message or ""))

# חלץ קוד מה-user_message
match = re.search(r"בצע שוב (\d+)", r_dup.user_message or "")
chk("DoD15: challenge code in user_message", match is not None)
if match:
    code = match.group(1)
    # DoD §16 — hash only (not raw code stored)
    override = next(iter(gw2._overrides.values()), None)
    chk("DoD16: challenge_hash != raw code", override and override.challenge_hash != code)
    chk("DoD16: challenge_hash == sha256(code)", override and override.challenge_hash == _hash_challenge(code))
    chk("DoD16: consumed=False before use", override and not override.consumed)

    # ביצוע ראשון עם קוד תקין
    result_override = gw2.route_override_word("boss_hq:owner_1", code)
    chk("DoD15: first override returns non-error result", result_override is not None and "שגוי" not in result_override and "אין" not in result_override)
    chk("DoD15: consumed=True after use", override and override.consumed)

    # ניסיון שני עם אותו קוד — consumed=True
    result_reuse = gw2.route_override_word("boss_hq:owner_1", code)
    chk("DoD15: second override attempt fails (consumed)", "override" not in result_reuse.lower() or "אין" in result_reuse)

    # ניסיון עם קוד שגוי
    result_bad = gw2.route_override_word("boss_hq:owner_1", "000000")
    chk("DoD15: wrong code rejected", "שגוי" in result_bad or "אין" in result_bad)


# ══════════════════════════════════════════════════
# DoD §17: "בצע שוב" doesn't reach Agent — intercepted at section 2.55
# (unit-level: route_override_word intercepts before agent loop)
# ══════════════════════════════════════════════════
print("\n── DoD §17: 'בצע שוב' intercepted before Agent ─────────────")
gw3 = _make_gw()
# ללא override פתוח — מחזיר הודעת שגיאה מתאימה, לא מגיע ל-Agent
result_no_override = gw3.route_override_word("boss_hq:nobody", "123456")
chk("DoD17: route_override_word returns message (not None)", result_no_override is not None)
chk("DoD17: no live override → message mentions 'override'/'אין'", "אין" in result_no_override or "override" in result_no_override.lower())


# ══════════════════════════════════════════════════
# DoD §3: "מאשר" ללא pending → "אין פעולה שממתינה"
# ══════════════════════════════════════════════════
print("\n── DoD §3: confirm word without pending ─────────────────────")
gw4 = _make_gw()
reply = gw4.route_confirmation_word("boss_hq:nobody", approver_role="owner")
chk("DoD3: route_confirmation_word returns 'אין פעולה'", "אין" in reply)


# ══════════════════════════════════════════════════
# DoD §6: approved_payload == executed_payload
# ══════════════════════════════════════════════════
print("\n── DoD §6: approved_payload == executed_payload ─────────────")
executed_payloads = []

def _capturing_exec(tool_name, tool_inputs, contract_id):
    executed_payloads.append(dict(tool_inputs))
    return "ok"

gw5 = _make_gw()
gw5._tool_executor = _capturing_exec
original_inputs = {"spreadsheet_name": "Budget", "row": "2026"}
r5 = gw5.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="sheets_append", tool_inputs=original_inputs,
    origin_channel="telegram", origin_chat_id="tg:1",
    requires_approval=True,
    user_text="add 2026 to Google Sheets",
)
gw5.approve(r5.contract_id, approver="boss_hq:owner_1", approver_role="owner")
chk("DoD6: exactly one execution", len(executed_payloads) == 1)
expected_norm = gw5.normalize_payload(original_inputs)
chk("DoD6: executed_payload == approved normalized_payload", executed_payloads[0] == expected_norm)


# ══════════════════════════════════════════════════
# singleton action_gateway importable and functional
# ══════════════════════════════════════════════════
print("\n── Singleton smoke test ──────────────────────────────────────")
chk("Singleton: action_gateway is ActionGateway", isinstance(action_gateway, ActionGateway))
chk("Singleton: compute_business_fingerprint callable", callable(action_gateway.compute_business_fingerprint))


# ══════════════════════════════════════════════════
# BUG-C89-APPROVAL-IDENTITY: approval execution must use the actor identity
# preserved on the contract at propose time, not re-resolve
# canonical_user_id/origin_chat_id (a memory_key like "boss_hq:eliyahu",
# not a channel external_id) through resolve_identity() — which silently
# falls back to readonly and denies the approved tool.
# ══════════════════════════════════════════════════
print("\n── BUG-C89-APPROVAL-IDENTITY: preserved actor identity on approve ──")

import tools.dispatcher as _dispatcher_mod
from identity import Identity, Role

_owner_identity = Identity(
    user_id="eliyahu", role=Role.OWNER, display_name="אליהו חזן",
    tenant_id="boss_hq", domain_id="general",
    channel="telegram", external_id="7228089151",
)

_captured_identity: dict = {}


def _fake_dispatch_tool(name, inputs, identity=None, trusted_source=None, execution_context=None):
    _captured_identity["role"]        = getattr(identity, "role", None)
    _captured_identity["external_id"] = getattr(identity, "external_id", None)
    _captured_identity["tenant_id"]   = getattr(identity, "tenant_id", None)
    _captured_identity["trusted_source"] = trusted_source
    _captured_identity["execution_context"] = execution_context
    return {"ok": True, "external_id": "rec12345678901234", "tool": name}


_orig_dispatch_tool = _dispatcher_mod.dispatch_tool
_dispatcher_mod.dispatch_tool = _fake_dispatch_tool
try:
    r_id = action_gateway.propose_action(
        tenant_id         = "boss_hq",
        canonical_user_id = _owner_identity.memory_key,   # "boss_hq:eliyahu"
        tool_name         = "airtable_update",
        tool_inputs       = {"table": "Leads", "record_id": "recABCDEFGHIJKLM", "fields": {"Name": "Test"}},
        origin_channel    = "telegram",
        # BUG-C89 root cause reproduction: origin_chat_id is the canonical
        # memory_key, NOT a real Telegram chat_id — this is exactly what
        # broke resolve_identity() before the fix.
        origin_chat_id    = _owner_identity.memory_key,
        requires_approval = True,
        identity          = _owner_identity,
    )
    chk("BUG-C89: propose_action (with identity) ok", r_id.ok)

    logger_output = action_gateway.approve(r_id.contract_id, approver=_owner_identity.memory_key, approver_role="owner")
    chk("BUG-C89: approve() executes without denial", "❌" not in logger_output)
    chk("BUG-C89: dispatcher receives role=owner (not readonly)",
        _captured_identity.get("role") == Role.OWNER)
    chk("BUG-C89: dispatcher receives preserved external_id",
        _captured_identity.get("external_id") == "7228089151")
    chk("BUG-C89: dispatcher receives correct tenant_id",
        _captured_identity.get("tenant_id") == "boss_hq")
    # Phase 4B-2 follow-up: _make_dispatch_executor() must supply
    # execution_context (contract_id + approved_by) on every real approve()
    # -> dispatch_tool() call, from the durable contract itself.
    ec = _captured_identity.get("execution_context")
    chk("BUG-C89: execution_context.contract_id matches the approved contract",
        ec is not None and ec.get("contract_id") == r_id.contract_id)
    chk("BUG-C89: execution_context.approved_by is the approver, not the requester",
        ec is not None and ec.get("approved_by") == _owner_identity.memory_key)
finally:
    _dispatcher_mod.dispatch_tool = _orig_dispatch_tool

# Legacy contract (no identity passed to propose_action) must still fall
# back to resolve_identity(origin_channel, origin_chat_id) — no regression
# for callers that haven't been updated yet.
gw_legacy = _make_gw()
r_legacy = gw_legacy.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="airtable_update",
    tool_inputs={"table": "Leads", "record_id": "recABCDEFGHIJKLM"},
    origin_channel="telegram", origin_chat_id="tg:1",
    requires_approval=True,
)
legacy_contract = gw_legacy.find_contract(r_legacy.contract_id)
chk("BUG-C89: legacy contract (no identity) has empty actor_role", legacy_contract.actor_role == "")


# ══════════════════════════════════════════════════
# BUG-077 root cause: propose_action() cross-checks requires_approval
# against tool_registry.needs_approval() — fail-closed, caller cannot
# under-declare it for a tool the registry marks as requiring approval.
# ══════════════════════════════════════════════════
print("\n── BUG-077: propose_action() overrides caller-declared requires_approval ──")

gw_bug077 = _make_gw()
r_override = gw_bug077.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:user_bug077a",
    tool_name="sheets_append",  # registry: requires_approval=True
    tool_inputs={"spreadsheet_name": "Sales", "row": "test"},
    origin_channel="telegram", origin_chat_id="tg:bug077a",
    requires_approval=False,  # caller under-declares
    user_text="add test to Google Sheets",
)
contract_override = gw_bug077.find_contract(r_override.contract_id)
chk("BUG-077: contract forced to pending when registry requires approval",
    contract_override.status == "pending")
chk("BUG-077: contract.requires_approval overridden to True",
    contract_override.requires_approval is True)

gw_bug077b = _make_gw()
r_match = gw_bug077b.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:user_bug077b",
    tool_name="sheets_append",
    tool_inputs={"spreadsheet_name": "Sales", "row": "test2"},
    origin_channel="telegram", origin_chat_id="tg:bug077b",
    requires_approval=True,  # caller correctly declares — no change expected
    user_text="add test2 to Google Sheets",
)
contract_match = gw_bug077b.find_contract(r_match.contract_id)
chk("BUG-077: no behavior change when caller already declares True",
    contract_match.status == "pending")

gw_bug077c = _make_gw()
r_noop = gw_bug077c.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:user_bug077c",
    tool_name="airtable_get",  # registry: requires_approval not set (False)
    tool_inputs={"table": "Leads"},
    origin_channel="telegram", origin_chat_id="tg:bug077c",
    requires_approval=False,
)
contract_noop = gw_bug077c.find_contract(r_noop.contract_id)
chk("BUG-077: no override for a tool the registry does NOT require approval for",
    contract_noop.status == "approved")


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Action Gateway tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
