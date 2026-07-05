# test_bug070_combined_wording.py — BUG-070 (C90-VERIFY-01), gap #1 of 3
#
# ActionGateway.route_disambiguation() only parsed a bare ordinal ("1",
# "ראשונה") — combined wording like "כן 1"/"אשר 3" fell through unrecognized
# (not disambiguation, since _parse_ordinal("כן 1") is neither a digit nor
# a known ordinal word) and reached the Agent as a plain message. There was
# also no way at all to reject one specific pending contract by index — the
# only cancel path (route_cancellation_word) always rejected every live
# contract for the user.
#
# Fix: ActionGateway._parse_combined() + ActionGateway.route_combined_word()
# parse "<confirm/cancel word> <ordinal>" and target exactly one live
# contract — approving it (closing siblings, same as route_disambiguation)
# or rejecting only it (siblings stay pending).
#
# These tests call the real ActionGateway methods directly — not a
# reimplementation.

import sys

from core.action_gateway import ActionGateway, ExecutionLedger

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _make_gw():
    executions = []

    def _executor(tool_name, tool_inputs, contract_id):
        executions.append(tool_name)
        return {"ok": True, "external_id": "rec00000000000001", "tool": tool_name}

    gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_executor)
    return gw, executions


def _propose(gw, user_id, tool_name, chat_id="tg:1"):
    return gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=user_id,
        tool_name=tool_name, tool_inputs={"table": "Leads", "row": tool_name},
        origin_channel="telegram", origin_chat_id=chat_id,
        requires_approval=True,
    )


# ══════════════════════════════════════════════════
# _parse_combined — pure parsing behavior
# ══════════════════════════════════════════════════
print("\n── _parse_combined: pattern parsing ─────────────────────────")
chk('"כן 1" → ("confirm", 1)', ActionGateway._parse_combined("כן 1") == ("confirm", 1))
chk('"אשר 3" → ("confirm", 3)', ActionGateway._parse_combined("אשר 3") == ("confirm", 3))
chk('"מאשר 2" → ("confirm", 2)', ActionGateway._parse_combined("מאשר 2") == ("confirm", 2))
chk('"לא 2" → ("cancel", 2)', ActionGateway._parse_combined("לא 2") == ("cancel", 2))
chk('"בטל 1" → ("cancel", 1)', ActionGateway._parse_combined("בטל 1") == ("cancel", 1))
chk('"כן ראשונה" → ("confirm", 1) (ordinal word)', ActionGateway._parse_combined("כן ראשונה") == ("confirm", 1))
chk('plain "כן" (no ordinal) → None', ActionGateway._parse_combined("כן") is None)
chk('plain "1" (no keyword) → None', ActionGateway._parse_combined("1") is None)
chk('unrelated "שלום עולם" → None', ActionGateway._parse_combined("שלום עולם") is None)
chk('"כן 99" (out of range handled by caller, still parses) → ("confirm", 99)',
    ActionGateway._parse_combined("כן 99") == ("confirm", 99))


# ══════════════════════════════════════════════════
# route_combined_word — confirm targeting ("כן 1"/"אשר 3")
# ══════════════════════════════════════════════════
print("\n── route_combined_word: targeted confirm ─────────────────────")
gw, executions = _make_gw()
r1 = _propose(gw, "boss_hq:u1", "airtable_add")
r2 = _propose(gw, "boss_hq:u1", "gmail_send_draft")
r3 = _propose(gw, "boss_hq:u1", "calendar_create_event")

reply = gw.route_combined_word("boss_hq:u1", "כן 2")
chk("combined confirm: reply is not None", reply is not None)
chk("combined confirm: executes exactly the targeted contract", executions == ["gmail_send_draft"])
chk("combined confirm: targeted contract now executed",
    gw.find_contract(r2.contract_id).status == "executed")
chk("combined confirm: sibling #1 closed (rejected)",
    gw.find_contract(r1.contract_id).status == "rejected")
chk("combined confirm: sibling #3 closed (rejected)",
    gw.find_contract(r3.contract_id).status == "rejected")


# ══════════════════════════════════════════════════
# route_combined_word — cancel targeting ("לא 2") leaves siblings pending
# ══════════════════════════════════════════════════
print("\n── route_combined_word: targeted cancel (gap ב) ──────────────")
gw2, executions2 = _make_gw()
c1 = _propose(gw2, "boss_hq:u2", "airtable_add")
c2 = _propose(gw2, "boss_hq:u2", "gmail_send_draft")
c3 = _propose(gw2, "boss_hq:u2", "calendar_create_event")

reply2 = gw2.route_combined_word("boss_hq:u2", "לא 2")
chk("combined cancel: reply is not None", reply2 is not None)
chk("combined cancel: targeted contract rejected",
    gw2.find_contract(c2.contract_id).status == "rejected")
chk("combined cancel: sibling #1 still pending (not touched)",
    gw2.find_contract(c1.contract_id).status == "pending")
chk("combined cancel: sibling #3 still pending (not touched)",
    gw2.find_contract(c3.contract_id).status == "pending")
chk("combined cancel: no tool executed", executions2 == [])
chk("combined cancel: reply mentions remaining count", "2" in reply2 and "נשארו" in reply2)


# ══════════════════════════════════════════════════
# route_combined_word — out-of-range / no-live-contracts / non-matching text
# ══════════════════════════════════════════════════
print("\n── route_combined_word: edge cases ───────────────────────────")
gw3, _ = _make_gw()
_propose(gw3, "boss_hq:u3", "airtable_add")

chk("out-of-range index → warning, not a crash",
    "אין פעולה מספר" in (gw3.route_combined_word("boss_hq:u3", "כן 9") or ""))
chk("no live contracts for unrelated user → None (falls through)",
    gw3.route_combined_word("boss_hq:nobody", "כן 1") is None)
chk("non-matching text ('מה קורה') → None (falls through to Agent)",
    gw3.route_combined_word("boss_hq:u3", "מה קורה") is None)
chk("bare ordinal without keyword ('2') → None (unchanged — still route_disambiguation's job)",
    gw3.route_combined_word("boss_hq:u3", "2") is None)


# ══════════════════════════════════════════════════
# Single live contract — combined wording still targets it correctly
# (regression guard: must not require 2+ pending, unlike bare-digit rules
# in app.py's separate _pending_approvals gate)
# ══════════════════════════════════════════════════
print("\n── route_combined_word: single pending contract ──────────────")
gw4, executions4 = _make_gw()
single = _propose(gw4, "boss_hq:u4", "airtable_update")
reply4 = gw4.route_combined_word("boss_hq:u4", "אשר 1")
chk("single pending + 'אשר 1' → executes it", executions4 == ["airtable_update"])
chk("single pending contract now executed",
    gw4.find_contract(single.contract_id).status == "executed")


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"BUG-070 gap #1 (combined wording) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
