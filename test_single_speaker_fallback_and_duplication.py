# test_single_speaker_fallback_and_duplication.py — regression tests for a
# live-incident Single-Speaker defect pair
# (contract_id=9c6ff34e-4714-46c0-a385-0ac860c8c3e0, record_id=recP8c6hYpYW7bjSG).
#
# Finding A: sanitize_agent_response() replaced the agent's post-approval
# action-status text with the generic failure fallback ("לא הצלחתי לבצע את
# הפעולה. נסה שוב או נסח אחרת.") even though a pending-approval message had
# already been sent this turn — a contradictory second message implying
# failure when the action was, correctly, still pending. Fixed: when the
# __approval_queued__ sentinel (app.py's _queue_approval() call site) is
# present in tool_results, the Single-Speaker gate now suppresses the
# agent's redundant text entirely (returns "") instead of substituting the
# false-failure fallback. Without that sentinel, the pre-existing fallback
# behavior for a genuine hallucination is unchanged.
#
# Finding B: ActionGateway._execute_contract() appended the executor's own
# C53-A user_message as a second line after compose_status_reply()'s
# canonical "✅ בוצע: ..." text — two success statements composed into one
# reply. Fixed: only compose_status_reply()'s text is ever returned to the
# user; the executor's raw response (including user_message and
# external_id) remains available internally via ActionFact.raw_tool_response
# for verification/audit, it is just never surfaced a second time in the
# outgoing text.
#
# This fix touches only sanitize_agent_response()'s Single-Speaker branch,
# _execute_contract()'s reply composition, and the three app.py send call
# sites that must treat an empty reply as "send nothing". Dispatch, Atomic
# Claims, idempotency, and Req6 (repeated-confirm) behavior are unchanged —
# see the dispatch-count and repeated-confirm regressions below.
#
# Follow-up (post-PR #341 manual verification): a multi-turn task-creation
# flow (a required field completed on a later turn) still produced two
# messages — the official pending-approval message plus separate agent text
# narrating that the task is "ready and waiting for approval". That text is
# truthful and evidenced (not the false-completion claim Finding A covered),
# so _AGENT_ACTION_STATUS_PATTERN (completion verbs only) never caught it.
# Fixed: the Single-Speaker gate's trigger now also matches
# _AGENT_PENDING_STATUS_PATTERN (ready/pending-approval narration), routed
# through the same __approval_queued__-gated suppress-vs-fallback branch as
# Finding A.

from __future__ import annotations

from core.action_gateway import (
    ActionContract,
    ActionFact,
    ActionGateway,
    ExecutionLedger,
)
from core.anti_hallucination import sanitize_agent_response, _SINGLE_SPEAKER_FALLBACK
from identity import Identity

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# Finding A — sanitize_agent_response suppression, not a false-failure fallback
# ══════════════════════════════════════════════════

# The exact sentinel shape app.py's _queue_approval() call site injects into
# tool_results_log once a pending-approval message has actually been sent.
_approval_queued_evidence = [
    {"tool": "__approval_queued__", "content": "⏳ ממתין לאישור: הוספת משימה", "ok": True},
]

r_suppressed = sanitize_agent_response(
    "הבקשה נשלחה לאישור הבעלים.", _approval_queued_evidence, _gateway_active=True,
)
chk("Finding A: action-status text after approval queued -> suppressed entirely (empty string)",
    r_suppressed == "")
chk("Finding A: suppressed reply is NOT the false-failure fallback",
    r_suppressed != _SINGLE_SPEAKER_FALLBACK)
chk("Finding A: no fallback text present at all when suppressed",
    "לא הצלחתי" not in r_suppressed)

# Regression: without __approval_queued__ evidence, a genuine hallucinated
# action-status claim must still be caught and replaced exactly as before.
r_fallback_unchanged = sanitize_agent_response(
    "✅ הפעולה בוצעה בהצלחה.", [], _gateway_active=True,
)
chk("Finding A regression: no approval queued -> existing fallback behavior unchanged",
    r_fallback_unchanged == _SINGLE_SPEAKER_FALLBACK)

# Regression: gateway inactive -> the Single-Speaker gate itself never
# fires (unrelated to this fix's trigger condition) -> never suppressed.
r_gateway_off = sanitize_agent_response(
    "הבקשה נשלחה לאישור הבעלים.", _approval_queued_evidence, _gateway_active=False,
)
chk("Finding A regression: gateway_active=False -> gate does not fire -> not suppressed",
    r_gateway_off != "")
chk("Finding A regression: gateway_active=False -> not the Single-Speaker fallback either",
    r_gateway_off != _SINGLE_SPEAKER_FALLBACK)


# ══════════════════════════════════════════════════
# Finding A follow-up (multi-turn) — agent narrating "ready/pending approval"
# is ALSO a Single-Speaker violation, not just false completion claims.
# Live report: in a multi-turn task-creation flow (missing field completed on
# a later turn), the user received BOTH the official pending-approval message
# AND separate agent text explaining the task is "ready and waiting for
# approval" — a truthful, evidenced claim that _AGENT_ACTION_STATUS_PATTERN
# (completion verbs only) never caught, so PR #341's fix didn't cover it.
# ══════════════════════════════════════════════════

r_pending_suppressed = sanitize_agent_response(
    "המשימה מוכנה וממתינה לאישור הבעלים.", _approval_queued_evidence, _gateway_active=True,
)
chk("multi-turn: 'ready/pending approval' narration after approval queued -> suppressed entirely",
    r_pending_suppressed == "")
chk("multi-turn: suppressed pending-narration is NOT the false-failure fallback",
    r_pending_suppressed != _SINGLE_SPEAKER_FALLBACK)

# Regression: without __approval_queued__ evidence, this is a fabricated
# pending-approval claim -> still blocked (now via the Single-Speaker gate
# rather than falling through unchecked).
r_pending_fake = sanitize_agent_response(
    "המשימה מוכנה וממתינה לאישור הבעלים.", [], _gateway_active=True,
)
chk("multi-turn regression: fabricated 'pending approval' claim with no evidence -> still blocked",
    r_pending_fake == _SINGLE_SPEAKER_FALLBACK)

# Regression: gateway inactive -> untouched, exactly like the completion-verb case.
r_pending_gateway_off = sanitize_agent_response(
    "המשימה מוכנה וממתינה לאישור הבעלים.", _approval_queued_evidence, _gateway_active=False,
)
chk("multi-turn regression: gateway_active=False -> pending narration passes through unchanged",
    r_pending_gateway_off == "המשימה מוכנה וממתינה לאישור הבעלים.")


# ══════════════════════════════════════════════════
# Finding B — exactly one success statement, live propose -> approve path
# ══════════════════════════════════════════════════

RECORD_ID = "recP8c6hYpYW7bjSG"
EXECUTOR_USER_MESSAGE = f"✅ רשומה נוספה | ID: {RECORD_ID}"

_dispatched: list[str] = []


def _tracking_executor(tool_name, tool_inputs, contract_id, **kwargs):
    _dispatched.append(tool_name)
    return {
        "ok": True,
        "tool": tool_name,
        "external_id": RECORD_ID,
        "evidence": {"record_id": RECORD_ID},
        "user_message": EXECUTOR_USER_MESSAGE,
    }


gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_tracking_executor)
identity = Identity(
    user_id="owner-1", role="owner", tenant_id="boss_hq",
    channel="telegram", external_id="tg-100",
)

propose_result = gw.propose_action(
    tenant_id="boss_hq",
    canonical_user_id="boss_hq:owner-1",
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "לרכוש מדפסת"}},
    origin_channel="telegram",
    origin_chat_id="tg-100",
    requires_approval=True,
    identity=identity,
)
chk("proposal produces exactly one pending contract (ok=True)", propose_result.ok)
chk("proposal's user_message contains no failure fallback text",
    "❌" not in (propose_result.user_message or "") and "לא הצלחתי" not in (propose_result.user_message or ""))
chk("dispatch has NOT happened yet at proposal time", _dispatched == [])

pending_contract = gw.find_contract(propose_result.contract_id)
chk("pending contract status is 'pending' before approval", pending_contract.status == "pending")

reply = gw.route_confirmation_word("boss_hq:owner-1", approver_role="owner")

chk("approval performs exactly one dispatch", _dispatched == ["airtable_add"])
chk("final reply reports success ('✅ בוצע')", "✅ בוצע" in reply)
chk("final reply contains exactly one success statement (single ✅ occurrence)",
    reply.count("✅") == 1)
chk("final reply does NOT also contain the executor's own success text",
    "רשומה נוספה" not in reply)
chk("record ID appears in the reply", RECORD_ID in reply)
chk("record ID appears exactly once (no duplication)", reply.count(RECORD_ID) == 1)

approved_contract = gw.find_contract(propose_result.contract_id)
chk("contract reached a terminal success status", approved_contract.status in ("completed", "executed"))


# ══════════════════════════════════════════════════
# Finding B — executor result (incl. user_message) remains available
# internally for verification/audit, even though it is never repeated in
# the outgoing text. compose_status_reply() is exercised directly here
# with the same ActionFact shape _execute_contract() builds internally.
# ══════════════════════════════════════════════════

audit_fact = ActionFact(
    tool_name="airtable_add",
    contract_id="audit-check",
    outcome="executed",
    record_id=RECORD_ID,
    error_code=None,
    raw_tool_response={
        "ok": True, "tool": "airtable_add",
        "external_id": RECORD_ID, "evidence": {"record_id": RECORD_ID},
        "user_message": EXECUTOR_USER_MESSAGE,
    },
)
audit_reply = gw.compose_status_reply(audit_fact)
chk("executor's raw response remains available internally via ActionFact.raw_tool_response",
    audit_reply.fact.raw_tool_response.get("user_message") == EXECUTOR_USER_MESSAGE)
chk("executor's external_id remains available internally via ActionFact.raw_tool_response",
    audit_reply.fact.raw_tool_response.get("external_id") == RECORD_ID)
chk("but the executor's user_message text is not repeated in the outgoing GatewayReply.text",
    "רשומה נוספה" not in audit_reply.text)
chk("the outgoing GatewayReply.text still carries the canonical single success statement",
    audit_reply.text.count("✅") == 1)


# ══════════════════════════════════════════════════
# Regression — Req6 (repeated confirm executes once only) unaffected
# ══════════════════════════════════════════════════

reply_repeat = gw.route_confirmation_word("boss_hq:owner-1", approver_role="owner")
chk("Req6 regression: a second confirm after completion does not dispatch again",
    _dispatched == ["airtable_add"])
chk("Req6 regression: second confirm reply is not a duplicate success statement",
    "✅ בוצע" not in reply_repeat)


print()
print("=" * 50)
print(f"Single-Speaker fallback/duplication tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
