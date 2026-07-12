# test_bug_reconfirmation_oneshot_fsm.py
#
# Production verification of the global ingress gate (PR #312/#313) showed
# the FIRST reconfirmation round works: an interrupting message correctly
# forced a re-display instead of a silent execute. But it also exposed a
# second bug: after that reconfirmation prompt was shown once
# (reconfirmation_required=True), a SECOND intervening action (an unrelated
# /update wizard completing another business action) did NOT re-arm
# anything — the next "כן" executed the OLD lead directly, without
# re-displaying it. The old boolean design only distinguished "interrupted
# vs not" and, once reconfirmation_required latched True, permanently
# disabled the interrupt check for that contract's whole lifetime.
#
# Fix: bounded one-shot reconfirmation FSM (not a recursive/infinite chain):
#
#   PENDING
#     ├─ כן              → EXECUTED
#     ├─ לא              → CANCELLED
#     └─ unrelated event → RECONFIRM_REQUIRED (context_interrupted=True)
#
#   RECONFIRM_REQUIRED (reconfirmation_required=True, prompt already shown)
#     ├─ כן              → EXECUTED
#     ├─ לא              → CANCELLED
#     └─ ANY other event → SUPERSEDED (terminal — closed, not re-armed)
#
# A contract that reaches RECONFIRM_REQUIRED gets exactly one more chance;
# a second interruption closes it outright instead of opening a second
# reconfirmation round. mark_context_interrupted()/
# mark_context_integrity_unknown() implement this by checking
# reconfirmation_required before deciding whether to (re-)mark interrupted
# or supersede.
#
# Deliberately NOT implemented (per explicit instruction downgrading it to
# "audit-only, optional"): a monotonic context_generation/version counter.
# The bounded terminal "superseded" status achieves the same safety
# guarantee without it — see BUG_AUDIT_LOG.md for the full reasoning.

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

    def _mock_executor(tool_name, tool_inputs, contract_id):
        executions.append((tool_name, dict(tool_inputs)))
        return {"ok": True, "external_id": "recTEST123456789A", "tool": tool_name}

    return ActionGateway(ledger=ExecutionLedger(), tool_executor=_mock_executor), executions


LEAD_FIELDS = {"Name": "מני חזי", "phone": "050-9998877", "domain": "real_estate"}


def _propose_lead(gw, user):
    return gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=user,
        tool_name="airtable_add",
        tool_inputs={"table": "Leads", "fields": LEAD_FIELDS},
        origin_channel="telegram", origin_chat_id="tg:1",
        requires_approval=True,
    )


# ══════════════════════════════════════════════════
# Regression A: preview → unrelated → כן → כן
# Expected: first כן re-shows, second כן executes once.
# ══════════════════════════════════════════════════
print("\n── A: preview → unrelated → כן → כן -> re-show then execute once ─")
gw, executions = _make_gw()
r = _propose_lead(gw, "boss_hq:oneshot_a")
chk("setup: contract proposed", r.ok)

gw.mark_context_interrupted("boss_hq:oneshot_a")  # unrelated action #1
reply1 = gw.route_confirmation_word("boss_hq:oneshot_a", approver_role="owner")
chk("A: first כן does not execute", executions == [])
chk("A: first כן re-shows the business description", "לאשר אותה" in reply1 and "מני חזי" in reply1)
contract = gw.find_contract(r.contract_id)
chk("A: contract still pending after first כן", contract.status == "pending")
chk("A: reconfirmation_required now True", contract.reconfirmation_required is True)

reply2 = gw.route_confirmation_word("boss_hq:oneshot_a", approver_role="owner")
chk("A: second כן executes exactly once", len(executions) == 1)
chk("A: second כן reply reports success", "בוצע" in reply2)


# ══════════════════════════════════════════════════
# Regression B: preview → unrelated → כן → another action → כן
# Expected: old contract superseded; no execution on the final כן.
# ══════════════════════════════════════════════════
print("\n── B: second interruption after reconfirm shown -> superseded ────")
gw2, executions2 = _make_gw()
r2 = _propose_lead(gw2, "boss_hq:oneshot_b")
chk("setup: contract proposed", r2.ok)

gw2.mark_context_interrupted("boss_hq:oneshot_b")  # unrelated action #1
reply1b = gw2.route_confirmation_word("boss_hq:oneshot_b", approver_role="owner")
chk("B: first כן re-shows (unaffected by the fix)", "לאשר אותה" in reply1b)
contract_b = gw2.find_contract(r2.contract_id)
chk("B: reconfirmation_required is now True", contract_b.reconfirmation_required is True)

# A SECOND, distinct unrelated action arrives (e.g. /update completing
# another business action) — this must supersede, not just re-flag.
gw2.mark_context_interrupted("boss_hq:oneshot_b")
chk("B: contract is now superseded (terminal, not pending)", contract_b.status == "superseded")
chk("B: superseded contract no longer live", gw2.find_live_contracts("boss_hq:oneshot_b") == [])

reply2b = gw2.route_confirmation_word("boss_hq:oneshot_b", approver_role="owner")
chk("B: final כן does NOT execute", executions2 == [])
chk("B: specific supersede message shown (not a generic 'nothing pending')",
    "בוטלה" in reply2b and "פעולה אחרת" in reply2b)
chk("B: supersede message names the actual superseded action", "מני חזי" in reply2b)
chk("B: message tells the user to resubmit", "מחדש" in reply2b)


# ══════════════════════════════════════════════════
# Regression C: a THIRD interruption after supersede is a no-op (bounded —
# no further degradation, no crash, nothing left to mark).
# ══════════════════════════════════════════════════
print("\n── C: further interruptions after supersede are a no-op ─────────")
gw2.mark_context_interrupted("boss_hq:oneshot_b")  # third interruption
contract_b_again = gw2.find_contract(r2.contract_id)
chk("C: still superseded, unaffected by further interruptions", contract_b_again.status == "superseded")


# ══════════════════════════════════════════════════
# Regression D: "לא" after a single reconfirmation still cancels cleanly
# (unaffected by the supersede fix — RECONFIRM_REQUIRED + לא -> CANCELLED).
# ══════════════════════════════════════════════════
print("\n── D: לא after reconfirmation still cancels (unaffected) ────────")
gw3, executions3 = _make_gw()
r3 = _propose_lead(gw3, "boss_hq:oneshot_d")
gw3.mark_context_interrupted("boss_hq:oneshot_d")
gw3.route_confirmation_word("boss_hq:oneshot_d", approver_role="owner")  # re-show
cancel_reply = gw3.route_cancellation_word("boss_hq:oneshot_d")
chk("D: cancellation reply returned", cancel_reply is not None and "בוטלה" in cancel_reply)
chk("D: never executed", executions3 == [])
contract_d = gw3.find_contract(r3.contract_id)
chk("D: contract status is rejected (not superseded)", contract_d.status == "rejected")


# ══════════════════════════════════════════════════
# Regression E: fail-closed fallback (context_integrity_unknown) obeys the
# same bounded one-shot rule — a marking failure after reconfirmation was
# already shown also supersedes, not just re-flags "unknown" forever.
# ══════════════════════════════════════════════════
print("\n── E: fail-closed fallback also supersedes after one reconfirm ──")
gw4, executions4 = _make_gw()
r4 = _propose_lead(gw4, "boss_hq:oneshot_e")
gw4.mark_context_interrupted("boss_hq:oneshot_e")
gw4.route_confirmation_word("boss_hq:oneshot_e", approver_role="owner")  # reconfirmation_required=True
gw4.mark_context_integrity_unknown("boss_hq:oneshot_e")  # fallback path, not the primary one
contract_e = gw4.find_contract(r4.contract_id)
chk("E: superseded via the fallback method too", contract_e.status == "superseded")



print(f"\n{'='*60}\nOne-shot reconfirmation FSM: {passed} passed, {failed} failed\n{'='*60}")
sys.exit(1 if failed else 0)
