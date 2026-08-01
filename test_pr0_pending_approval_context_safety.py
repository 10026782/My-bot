# test_pr0_pending_approval_context_safety.py — PR-0 / BUG-PENDING-APPROVAL-B
#
# Contract Chain finding (see BUG_AUDIT_LOG.md): the reported scenario
# (preview → intervening message → "כן" → stale action executes) reproduces
# via core/action_gateway.py's ActionContract/ExecutionLedger — the live path
# for LCH's lead-write confirmations (core/lead_candidate_handler.py's
# _propose_lead_write, which always calls ActionGateway.propose_action()
# regardless of FEATURE_ACTION_GATEWAY). Scope for this PR is ActionGateway
# only (explicit user decision) — app.py's separate _pending_approvals dict
# and event_bus.py's PendingActionsStore have the same latent flaw but are
# out of scope here.
#
# DoD coverage (see PR-0 doc "Definition of Done"):
#   #1  preview -> כן (no intervening message) -> executes, unchanged.
#   #2  preview -> intervening message -> כן -> does NOT execute; re-shows
#       business description; reconfirmation_required flips True.
#   #3  the re-shown description is a readable business description, not
#       only an internal contract_id.
#   #4  a further כן (after reconfirmation) executes the SAME action once.
#   #5  לא after reconfirmation -> cancelled, not executed.
#   #6  a genuinely new action proposed while one is pending does not merge
#       with the old one (separate contract_id/fingerprint).
#   #7  2+ live contracts -> existing disambiguation continues to work
#       (route_disambiguation), unaffected by context_interrupted marking.
#   #8  contract lifecycle (dropping out of find_live_contracts on execution)
#       is unaffected by the new fields.
#   #9  see #3 — internal id is never the sole content of the reconfirm text.
#   #10 regression — see BUG_AUDIT_LOG.md entry for the separate full-suite
#       run of test_action_gateway.py / test_bug070_combined_wording.py /
#       test_bug099c_lead_clarification.py (unchanged, run alongside this file).

import sys

from core.action_gateway import (
    ActionGateway,
    ExecutionLedger,
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


def _make_gw():
    executions = []

    def _mock_executor(tool_name, tool_inputs, contract_id):
        executions.append((tool_name, dict(tool_inputs)))
        return {"ok": True, "external_id": "recTEST123", "tool": tool_name}

    gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_mock_executor)
    return gw, executions


LEAD_FIELDS = {
    "Name":   "יוסי כהן",
    "phone":  "050-1234567",
    "domain": "real_estate",
}


def _propose_lead(gw, user="boss_hq:owner_1", fields=None):
    return gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=user,
        tool_name="gmail_send_draft",
        tool_inputs=fields or {"to": "yossi@example.com", "subject": "x"},
        origin_channel="telegram", origin_chat_id="tg:111",
        requires_approval=True,
        trusted_source="test_harness",
    )


# ══════════════════════════════════════════════════
# DoD #1: direct כן, no intervening message -> executes, unchanged
# ══════════════════════════════════════════════════
print("\n── DoD #1: direct כן (no intervening) -> executes ────────────")
gw, executions = _make_gw()
r = _propose_lead(gw)
chk("DoD1: propose ok", r.ok)
reply = gw.route_confirmation_word("boss_hq:owner_1", approver_role="owner")
chk("DoD1: executed immediately", len(executions) == 1)
chk("DoD1: reply reports canonical success", "הפעולה הושלמה" in reply)


# ══════════════════════════════════════════════════
# DoD #2/#3/#9: intervening message -> כן -> NOT executed, re-shows description
# ══════════════════════════════════════════════════
print("\n── DoD #2/#3/#9: intervening message before כן ───────────────")
gw, executions = _make_gw()
r = _propose_lead(gw, user="boss_hq:owner_2",
                   fields={"to": "x@y.com", "subject": "z"})
contract_id = r.contract_id

# simulate an unrelated intervening message reaching app.py's new hook
gw.mark_context_interrupted("boss_hq:owner_2")

reply = gw.route_confirmation_word("boss_hq:owner_2", approver_role="owner")
chk("DoD2: NOT executed after interruption", len(executions) == 0)
contract = gw.find_contract(contract_id)
chk("DoD2: contract still pending (not consumed)", contract.status == "pending")
chk("DoD2: reconfirmation_required now True", contract.reconfirmation_required is True)
chk("DoD3/9: reply is a readable description, not only the contract_id",
    contract_id not in reply and "שליחת הודעת דוא״ל" in reply)
chk("DoD3/9: reply never leaks the raw tool_name (Reconfirmation tool_name leak fix)",
    "gmail_send_draft" not in reply)
chk("DoD3: reply asks for explicit reconfirmation", "לאשר אותה" in reply)


# ══════════════════════════════════════════════════
# DoD #3 (Leads case): matches the exact PR-0 example wording style
# ══════════════════════════════════════════════════
print("\n── DoD #3: Leads-table description shows name/phone/domain ──")
gw, executions = _make_gw()
r = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_3",
    tool_name="airtable_add",
    tool_inputs={"table": "Leads", "fields": LEAD_FIELDS},
    origin_channel="telegram", origin_chat_id="tg:222",
    requires_approval=True,
)
gw.mark_context_interrupted("boss_hq:owner_3")
reply = gw.route_confirmation_word("boss_hq:owner_3", approver_role="owner")
chk("DoD3: Leads description shows the lead name", "יוסי כהן" in reply)
chk("DoD3: Leads description shows the phone", "050-1234567" in reply)
chk("DoD3: Leads description not just an internal id", r.contract_id not in reply)


# ══════════════════════════════════════════════════
# DoD #4: further כן after reconfirmation -> executes the SAME action once
# ══════════════════════════════════════════════════
print("\n── DoD #4: second כן after reconfirmation -> executes once ──")
gw, executions = _make_gw()
r = _propose_lead(gw, user="boss_hq:owner_4",
                   fields={"to": "a@b.com", "subject": "q"})
gw.mark_context_interrupted("boss_hq:owner_4")
gw.route_confirmation_word("boss_hq:owner_4", approver_role="owner")  # 1st כן -> reconfirm prompt
chk("DoD4: not executed yet after first post-interrupt כן", len(executions) == 0)
reply2 = gw.route_confirmation_word("boss_hq:owner_4", approver_role="owner")  # 2nd כן -> executes
chk("DoD4: executed exactly once after second כן", len(executions) == 1)
chk("DoD4: executed the original payload unchanged",
    executions[0] == ("gmail_send_draft", {"to": "a@b.com", "subject": "q"}))
chk("DoD4: reply reports canonical success", "הפעולה הושלמה" in reply2)


# ══════════════════════════════════════════════════
# DoD #5: לא after reconfirmation -> cancelled, not executed
# ══════════════════════════════════════════════════
print("\n── DoD #5: לא after reconfirmation -> cancelled ──────────────")
gw, executions = _make_gw()
r = _propose_lead(gw, user="boss_hq:owner_5",
                   fields={"to": "c@d.com", "subject": "w"})
contract_id = r.contract_id
gw.mark_context_interrupted("boss_hq:owner_5")
gw.route_confirmation_word("boss_hq:owner_5", approver_role="owner")  # reconfirm prompt
cancel_reply = gw.route_cancellation_word("boss_hq:owner_5")
chk("DoD5: cancellation reply returned", cancel_reply is not None and "בוטלה" in cancel_reply)
chk("DoD5: never executed", len(executions) == 0)
contract = gw.find_contract(contract_id)
chk("DoD5: contract status is rejected", contract.status == "rejected")


# ══════════════════════════════════════════════════
# DoD #6: a genuinely new Agent action is blocked while one is pending
# ══════════════════════════════════════════════════
print("\n── DoD #6: new Agent action during pending is not retained ─")
gw, executions = _make_gw()
r1 = _propose_lead(gw, user="boss_hq:owner_6",
                    fields={"to": "old@x.com", "subject": "old"})
gw.mark_context_interrupted("boss_hq:owner_6")  # intervening message arrives
r2 = gw.propose_action(  # ...and that intervening message is itself a new request
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_6",
    tool_name="gmail_send_draft",
    tool_inputs={"to": "new@x.com", "subject": "new"},
    origin_channel="telegram", origin_chat_id="tg:111",
    requires_approval=True,
)
chk("DoD6: later Agent proposal is blocked", not r2.ok)
chk("DoD6: block points to the existing contract", r2.contract_id == r1.contract_id)
c1 = gw.find_contract(r1.contract_id)
chk("DoD6: old contract carries the interruption flag", c1.context_interrupted is True)
chk("DoD6: only the original contract remains live",
    [c.contract_id for c in gw.find_live_contracts("boss_hq:owner_6")] == [r1.contract_id])


# ══════════════════════════════════════════════════
# DoD #7: 2+ live contracts -> existing disambiguation still works
# ══════════════════════════════════════════════════
print("\n── DoD #7: disambiguation unaffected by interruption marking ─")
gw, executions = _make_gw()
r1 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_7",
    tool_name="gmail_send_draft", tool_inputs={"to": "1@x.com", "subject": "a"},
    origin_channel="telegram", origin_chat_id="tg:1", requires_approval=True,
)
r2 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:owner_7",
    tool_name="gmail_send_draft", tool_inputs={"to": "2@x.com", "subject": "b"},
    origin_channel="telegram", origin_chat_id="tg:1", requires_approval=True,
    trusted_source="test_harness",
)
gw.mark_context_interrupted("boss_hq:owner_7")  # both now context_interrupted=True
list_reply = gw.route_confirmation_word("boss_hq:owner_7", approver_role="owner")
chk("DoD7: shows numbered disambiguation list, not a reconfirm prompt",
    "יש כמה פעולות שממתינות לאישור" in list_reply and "לאשר אותה" not in list_reply)
chk("DoD7: nothing executed yet", len(executions) == 0)
pick_reply = gw.route_disambiguation("boss_hq:owner_7", "1", approver_role="owner")
chk("DoD7: disambiguation pick executes directly (unaffected by interruption flag)",
    len(executions) == 1 and "הפעולה הושלמה" in pick_reply)


# ══════════════════════════════════════════════════
# DoD #8: executed contract drops out of find_live_contracts (lifecycle intact)
# ══════════════════════════════════════════════════
print("\n── DoD #8: executed contract no longer 'live' ────────────────")
gw, executions = _make_gw()
r = _propose_lead(gw, user="boss_hq:owner_8",
                   fields={"to": "e@f.com", "subject": "v"})
gw.route_confirmation_word("boss_hq:owner_8", approver_role="owner")
chk("DoD8: no longer live after execution", gw.find_live_contracts("boss_hq:owner_8") == [])


print(f"\n{'='*60}\nPR-0 (BUG-PENDING-APPROVAL-B): {passed} passed, {failed} failed\n{'='*60}")
sys.exit(1 if failed else 0)
