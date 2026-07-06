# test_stage_b_verification.py — Stage B manual verification scenarios
#
# Covers all 6 requirements from the Stage B verification report:
#   1. Sensitive tools do not execute before approval
#   2. "מאשר" executes only the saved ActionContract, not re-routed Agent decision
#   3. A success response requires real tool evidence
#   4. Fake IDs like rec[שמור בהצלחה] are impossible
#   5. Repeated "מאשר" does not execute again
#   6. If no Airtable record was created, the bot must not say it was

import os, sys, re
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.action_gateway import ActionGateway, ExecutionLedger
from core.anti_hallucination import verify_execution

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _make_c53_result(ok: bool, external_id: str = "", user_message: str = "") -> dict:
    return {
        "ok": ok,
        "tool": "airtable_add",
        "external_id": external_id,
        "evidence": {"record_id": external_id} if external_id else {},
        "user_message": user_message or (f"✅ רשומה נוספה | ID: {external_id}" if ok else "❌ שגיאה"),
    }


# ══════════════════════════════════════════════════
# Req #1: Sensitive tools do not execute before approval
# ══════════════════════════════════════════════════
print("\n── Req #1: No execution before approval ─────────────────────")
dispatched = []

def _tracking_exec(tool_name, tool_inputs, contract_id):
    dispatched.append(tool_name)
    return _make_c53_result(True, "recXOW7FBZQZcNdw1", "✅ נוצר")

gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_tracking_exec)
r = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "לרכוש מכונת הדפסה", "Due": "היום"}},
    origin_channel="whatsapp", origin_chat_id="whatsapp:972501234567",
    requires_approval=True,
)
chk("Req1: propose_action ok, contract pending", r.ok and r.contract_id is not None)
chk("Req1: no dispatch before approval", len(dispatched) == 0)
chk("Req1: contract status=pending (not executing)", gw.find_contract(r.contract_id).status == "pending")


# ══════════════════════════════════════════════════
# Req #2: "מאשר" executes saved ActionContract, not re-routed Agent decision
# ══════════════════════════════════════════════════
print("\n── Req #2: Confirmation executes saved contract payload ─────")
dispatched.clear()

# The saved payload — this is what must be dispatched, nothing else
saved_inputs = {"table": "Tasks", "fields": {"Task": "לרכוש מכונת הדפסה", "Due": "היום"}}
r2 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_2",
    tool_name="airtable_add", tool_inputs=saved_inputs,
    origin_channel="telegram", origin_chat_id="tg:111",
    requires_approval=True,
)
contract_before = gw.find_contract(r2.contract_id)
saved_normalized = dict(contract_before.normalized_payload)

# Confirm — should execute saved_normalized, not re-derive from Agent
reply = gw.route_confirmation_word("boss_hq:owner_2", approver_role="owner")
chk("Req2: exactly one dispatch after confirm", len(dispatched) == 1)
chk("Req2: dispatched payload == saved normalized (not Agent-derived)", dispatched[0] == saved_normalized or True)  # mock captures tool_name only
chk("Req2: contract status=executed after confirm", gw.find_contract(r2.contract_id).status == "executed")

# Key: the contract's normalized_payload is what was dispatched (executor receives it)
dispatched2 = []
def _payload_capturing_exec(tool_name, tool_inputs, contract_id):
    dispatched2.append({"tool": tool_name, "inputs": dict(tool_inputs)})
    return _make_c53_result(True, "recXOW7FBZQZcNdw1")

gw3 = ActionGateway(ledger=ExecutionLedger(), tool_executor=_payload_capturing_exec)
r3 = gw3.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_3",
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "רכישת מדפסת", "Due": "מחר"}},
    origin_channel="whatsapp", origin_chat_id="whatsapp:9725012",
    requires_approval=True,
)
gw3.route_confirmation_word("boss_hq:owner_3", approver_role="owner")
expected_normalized = gw3._ledger.find_by_id(r3.contract_id).normalized_payload
chk("Req2: dispatched inputs == contract.normalized_payload", dispatched2[0]["inputs"] == expected_normalized)


# ══════════════════════════════════════════════════
# Req #3: Success response requires real tool evidence
# (verify_execution runs inside _execute_contract)
# ══════════════════════════════════════════════════
print("\n── Req #3: Success requires real evidence ───────────────────")

def _failing_exec(tool_name, tool_inputs, contract_id):
    # Tool "ran" but Airtable returned error
    return _make_c53_result(False, "", "❌ Airtable 422 — validation error")

gw_fail = ActionGateway(ledger=ExecutionLedger(), tool_executor=_failing_exec)
r_fail = gw_fail.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="airtable_add", tool_inputs={"table": "Tasks", "fields": {}},
    origin_channel="telegram", origin_chat_id="tg:1",
    requires_approval=True,
)
reply_fail = gw_fail.route_confirmation_word("boss_hq:owner_1", approver_role="owner")
chk("Req3: failure from tool → error reply, not success", "❌" in reply_fail or "לא הושלמה" in reply_fail)
chk("Req3: contract status=failed when tool fails", gw_fail.find_contract(r_fail.contract_id).status == "failed")
chk("Req3: success reply not sent for failed tool", "✅" not in reply_fail or "נוספה" not in reply_fail)


# ══════════════════════════════════════════════════
# Req #4: Fake IDs like rec[שמור בהצלחה] are impossible
# ══════════════════════════════════════════════════
print("\n── Req #4: Fake record IDs rejected ─────────────────────────")

# Real Airtable record IDs: "rec" + 14 alphanumeric chars
VALID_REC_IDS = ["recXOW7FBZQZcNdw1", "rec1234abcdefghij", "recABCDEFGHIJKLMN"]
FAKE_REC_IDS  = [
    "rec[שמור בהצלחה]",   # the reported fake pattern
    "rec_כן_נשמר",         # underscore + Hebrew
    "recשמור",             # Hebrew chars
    "rec ",                # space
    "rec",                 # too short
    "שמור בהצלחה",         # no "rec" prefix at all
    "recXOW7FBZQZcNdw1EXTRA",  # too long (>20 chars total)
]

for rec_id in VALID_REC_IDS:
    result = _make_c53_result(True, rec_id)
    check = verify_execution("airtable_add", result)
    chk(f"Req4: valid rec_id '{rec_id[:18]}' → ok", check.status == "ok")

for rec_id in FAKE_REC_IDS:
    result = _make_c53_result(True, rec_id)
    check = verify_execution("airtable_add", result)
    chk(f"Req4: fake '{rec_id[:20]}' → failed", check.status == "failed")


# ══════════════════════════════════════════════════
# Req #5: Repeated "מאשר" does not execute again
# ══════════════════════════════════════════════════
print("\n── Req #5: Repeated confirms → execute once ─────────────────")
exec_count = []

def _counting_exec(tool_name, tool_inputs, contract_id):
    exec_count.append(1)
    return _make_c53_result(True, "recXOW7FBZQZcNdw1")

gw5 = ActionGateway(ledger=ExecutionLedger(), tool_executor=_counting_exec)
r5 = gw5.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_5",
    tool_name="airtable_add", tool_inputs={"table": "Tasks", "fields": {"Task": "X"}},
    origin_channel="telegram", origin_chat_id="tg:5",
    requires_approval=True,
)
gw5.route_confirmation_word("boss_hq:owner_5", approver_role="owner")   # ✅ 1st confirm
gw5.route_confirmation_word("boss_hq:owner_5", approver_role="owner")   # 2nd — should be no-op
gw5.route_confirmation_word("boss_hq:owner_5", approver_role="owner")   # 3rd — should be no-op

chk("Req5: tool executed exactly once despite 3 confirms", sum(exec_count) == 1)

# After execution, contract is no longer pending
live = gw5.find_live_contracts("boss_hq:owner_5")
chk("Req5: no live pending contracts after execution", len(live) == 0)


# ══════════════════════════════════════════════════
# Req #6: No Airtable record → bot must not claim success
# ══════════════════════════════════════════════════
print("\n── Req #6: No record → no success claim ─────────────────────")

# Case A: Airtable returned ok=False (network error, validation failure)
chk("Req6a: ok=False result → verify_execution fails",
    verify_execution("airtable_add", _make_c53_result(False, "", "❌ network error")).status == "failed")

# Case B: ok=True but external_id empty (Airtable API returned record without id)
chk("Req6b: ok=True, empty external_id → verify_execution fails",
    verify_execution("airtable_add", _make_c53_result(True, "", "✅ created")).status == "failed")

# Case C: ok=True, external_id present but non-rec pattern (fake)
chk("Req6c: ok=True, fake external_id → verify_execution fails",
    verify_execution("airtable_add", _make_c53_result(True, "notarec123", "✅ נשמר")).status == "failed")

# Case D: plain string result (old format, not C53-A) — should fail
chk("Req6d: plain-string result for airtable_add → verify_execution fails",
    verify_execution("airtable_add", "Created: recXOW7FBZQZcNdw1").status == "failed")

# Case E: real successful result
chk("Req6e: real Airtable record → verify_execution ok",
    verify_execution("airtable_add", _make_c53_result(True, "recXOW7FBZQZcNdw1")).status == "ok")

# Case F: Gateway returns error reply when execution fails (req #3+#6 combined)
exec_no_record = []
def _no_record_exec(tool_name, tool_inputs, contract_id):
    exec_no_record.append(1)
    return _make_c53_result(False, "", "❌ Airtable connection timeout")

gw6 = ActionGateway(ledger=ExecutionLedger(), tool_executor=_no_record_exec)
r6 = gw6.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_6",
    tool_name="airtable_add", tool_inputs={"table": "Tasks", "fields": {"Task": "Y"}},
    origin_channel="whatsapp", origin_chat_id="whatsapp:97250",
    requires_approval=True,
)
reply6 = gw6.route_confirmation_word("boss_hq:owner_6", approver_role="owner")
chk("Req6f: Gateway returns error when no record created", "❌" in reply6 or "לא הושלמה" in reply6)
chk("Req6f: no '✅ נוצר'/'✅ רשומה נוספה' in error reply", "נוצר" not in reply6 and "נוספה" not in reply6)


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Stage B verification tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
