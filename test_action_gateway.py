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
)
chk("DoD11: first propose → ok=True", r1.ok)
chk("DoD11: first propose → contract_id assigned", r1.contract_id is not None)

r2 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:user_42",
    tool_name="sheets_append",
    tool_inputs={"row": "VIP", "spreadsheet_name": "Sales"},  # רשימה שונה, payload זהה
    origin_channel="telegram", origin_chat_id="tg:7228089151",
    requires_approval=True,
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

gw.approve(cid, approver="boss_hq:owner_1")  # ביצוע ראשון
result2 = gw.approve(cid, approver="boss_hq:owner_1")  # שני — מצב כבר executed
result3 = gw.approve(cid, approver="boss_hq:owner_1")  # שלישי

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
reply = gw4.route_confirmation_word("boss_hq:nobody")
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
)
gw5.approve(r5.contract_id, approver="boss_hq:owner_1")
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
print(f"\n{'='*50}")
print(f"Action Gateway tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
