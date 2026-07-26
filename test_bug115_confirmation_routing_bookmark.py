# test_bug115_confirmation_routing_bookmark.py — regression tests for BUG-115:
# a bare "כן"/"מאשר" reply to a just-shown approval prompt (lead preview or
# general ActionGateway proposal) was hijacked by ActionGateway's generic
# multi-contract disambiguation whenever OLD, unrelated pending contracts
# also happened to still be live — because route_confirmation_word() only
# ever counted live contracts, with no notion of "which one the user is
# actually replying to".
#
# See docs/architecture/action-gateway/
# BUG-115_CONFIRMATION_ROUTING_HIJACK_AUDIT.md for the full audit (why this
# is NOT a Tier-1/Tier-2 mixup, why TurnEnvelope.active_queue_id is not the
# actual cause, etc.).
#
# Fix, two independent parts:
# 1. A short-lived (600s, matching the approval prompt's own advertised
#    "פג תוקף בעוד 10 דקות" window) "last prompted contract" bookmark,
#    reusing session_store.py's existing pending_lead_preview pattern —
#    set whenever a real approval prompt is actually shown to the user
#    (core/lead_candidate_handler.py's lead preview, app.py's
#    _queue_approval_detailed_impl()'s general approval prompt). Checked
#    FIRST in route_confirmation_word(), before the live-contract count —
#    if it names a still-pending contract for the same user, that contract
#    is resolved directly, regardless of how many other unrelated
#    contracts are also live. Falls through to the existing count-based
#    logic exactly as before when the bookmark is missing/expired/stale/
#    points at a different user's or non-pending contract.
# 2. The generic multi-contract disambiguation list no longer shows raw
#    tool_name/contract_id — it reuses the existing
#    _describe_contract_for_reconfirmation() helper (already trusted one
#    branch above, for the single-contract reconfirmation message).
#
# Explicitly NOT touched: BUG-114's mark_context_interrupted() fix, F52,
# EvidenceFinalizer, ActionGateway's actual approve/dispatch semantics.

from __future__ import annotations

import time

from core.action_gateway import (
    ActionGateway,
    ExecutionLedger,
)
from identity import Identity
from session_store import lead_sessions

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

    def _executor(tool_name, tool_inputs, contract_id, **kwargs):
        executions.append((tool_name, contract_id))
        # Airtable-shaped record id (^rec[A-Za-z0-9]{14}$) — a fake-looking
        # id fails ActionGateway's own evidence verification and would mask
        # this file's actual assertions behind an unrelated "evidence
        # missing" failure.
        rec_id = "rec" + (contract_id.replace("-", "")[:14]).ljust(14, "0")
        return {
            "ok": True, "tool": tool_name,
            "external_id": rec_id,
            "evidence": {"record_id": rec_id},
            "user_message": f"✅ בוצע | ID: {rec_id}",
        }

    gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_executor)
    return gw, executions


def _propose(gw, user_id: str, *, table="Tasks", fields=None, tool_name="airtable_update"):
    identity = Identity(
        user_id=user_id.split(":")[-1], role="owner", tenant_id="boss_hq",
        channel="telegram", external_id=f"tg-{user_id}",
    )
    return gw.propose_action(
        tenant_id="boss_hq",
        canonical_user_id=user_id,
        tool_name=tool_name,
        tool_inputs={"table": table, "fields": fields or {"x": "y"}},
        origin_channel="telegram",
        origin_chat_id=user_id,
        requires_approval=True,
        identity=identity,
        trusted_source="test_harness",
    )


USER = "boss_hq:eliyahu"


def _bookmark(gw_result, kind="lead_preview"):
    lead_sessions.set_last_prompted_contract(USER, gw_result.contract_id, kind=kind)


def _clear_session(user_id: str = USER) -> None:
    lead_sessions.clear_last_prompted_contract(user_id)


# ══════════════════════════════════════════════════
# Test 1 — the core production scenario: N old unrelated live contracts +
# a fresh bookmarked one -> "כן" resolves the fresh one directly, not
# disambiguation.
# ══════════════════════════════════════════════════

_clear_session()
gw1, ex1 = _make_gw()
old_ids = [_propose(gw1, USER, table="Tasks", fields={"n": i}).contract_id for i in range(6)]
fresh = _propose(gw1, USER, table="Leads", fields={"Name": "לענף גיוס"}, tool_name="airtable_add")
_bookmark(fresh)

reply1 = gw1.route_confirmation_word(USER, approver_role="owner")
chk("Test 1: 6 old unrelated contracts don't prevent direct resolution of the bookmarked one",
    ex1 == [("airtable_add", fresh.contract_id)])
chk("Test 1: reply reports success, not a disambiguation menu",
    "הפעולה הושלמה" in reply1 and "יש כמה פעולות" not in reply1)
chk("Test 1: the 6 old contracts are all still untouched/pending",
    all(gw1.find_contract(cid).status == "pending" for cid in old_ids))

# ══════════════════════════════════════════════════
# Test 2 — regression: no bookmark, multiple live contracts -> existing
# disambiguation behavior preserved exactly, including human-readable
# labels (not raw tool_name/id).
# ══════════════════════════════════════════════════

_clear_session()
gw2, ex2 = _make_gw()
c2a = _propose(gw2, USER, table="Tasks", fields={"a": 1})
c2b = _propose(gw2, USER, table="Tasks", fields={"b": 2})

reply2 = gw2.route_confirmation_word(USER, approver_role="owner")
chk("Test 2: no bookmark + 2 live contracts -> generic disambiguation shown",
    "יש כמה פעולות שממתינות לאישור" in reply2)
chk("Test 2: nothing executed yet (still ambiguous)", ex2 == [])
chk("Test 2: disambiguation text does NOT contain the raw tool name 'airtable_update'",
    "airtable_update" not in reply2)
chk("Test 2: disambiguation text does NOT contain a raw 8-char contract id",
    c2a.contract_id[:8] not in reply2 and c2b.contract_id[:8] not in reply2)

# ══════════════════════════════════════════════════
# Test 3 — bookmark present but EXPIRED (>600s old) -> falls through to
# existing count-based logic (here: disambiguation, since 2 are live).
# ══════════════════════════════════════════════════

_clear_session()
gw3, ex3 = _make_gw()
c3a = _propose(gw3, USER, table="Tasks", fields={"a": 1})
c3b = _propose(gw3, USER, table="Tasks", fields={"b": 2})
lead_sessions.set_last_prompted_contract(USER, c3a.contract_id)
# Backdate the bookmark past the 600s TTL directly in the session store.
_sess = lead_sessions.get(USER)
_sess["last_prompted_contract"]["set_at"] = time.time() - 700

reply3 = gw3.route_confirmation_word(USER, approver_role="owner")
chk("Test 3: expired bookmark (>600s) falls through to generic disambiguation",
    "יש כמה פעולות שממתינות לאישור" in reply3)
chk("Test 3: nothing executed (fell through, still ambiguous)", ex3 == [])

# ══════════════════════════════════════════════════
# Test 4 — bookmark points at a contract that is no longer "pending"
# (already resolved through some other path) -> falls through cleanly,
# does not error, does not resurrect the resolved contract.
# ══════════════════════════════════════════════════

_clear_session()
gw4, ex4 = _make_gw()
c4_resolved = _propose(gw4, USER, table="Tasks", fields={"a": 1})
gw4.reject(c4_resolved.contract_id, rejected_by=USER)
c4_other = _propose(gw4, USER, table="Tasks", fields={"b": 2})
lead_sessions.set_last_prompted_contract(USER, c4_resolved.contract_id)

reply4 = gw4.route_confirmation_word(USER, approver_role="owner")
chk("Test 4: bookmark pointing at an already-rejected contract falls through cleanly "
    "(1 live contract left -> direct approve, not an error)",
    ex4 == [("airtable_update", c4_other.contract_id)])
chk("Test 4: the rejected contract stays rejected (not resurrected)",
    gw4.find_contract(c4_resolved.contract_id).status == "rejected")

# ══════════════════════════════════════════════════
# Test 5 — bookmark belongs to a DIFFERENT canonical_user_id -> never
# matches (bookmarks are per-user by construction, this is a sanity check).
# ══════════════════════════════════════════════════

_clear_session("boss_hq:someone_else")
_clear_session()
gw5, ex5 = _make_gw()
c5_mine = _propose(gw5, USER, table="Tasks", fields={"a": 1})
_propose(gw5, "boss_hq:someone_else", table="Tasks", fields={"b": 2})
lead_sessions.set_last_prompted_contract("boss_hq:someone_else", c5_mine.contract_id)

reply5 = gw5.route_confirmation_word(USER, approver_role="owner")
chk("Test 5: a bookmark stored under a different user is simply never read for this user "
    "(1 live contract for USER -> direct approve)",
    ex5 == [("airtable_update", c5_mine.contract_id)])

# ══════════════════════════════════════════════════
# Test 6 — bookmark hit, but the bookmarked contract's context was
# interrupted since the prompt was shown -> reconfirmation required, NOT
# an immediate approve. The bookmark must be KEPT (not cleared) so the
# actual second "כן" still resolves this same contract directly.
# ══════════════════════════════════════════════════

_clear_session()
gw6, ex6 = _make_gw()
old6 = [_propose(gw6, USER, table="Tasks", fields={"n": i}).contract_id for i in range(3)]
c6 = _propose(gw6, USER, table="Leads", fields={"Name": "בדיקה"}, tool_name="airtable_add")
_bookmark(c6)
gw6.mark_context_interrupted(USER)  # simulates an unrelated message arriving

reply6a = gw6.route_confirmation_word(USER, approver_role="owner")
chk("Test 6a: interrupted bookmarked contract -> reconfirmation requested, not executed",
    ex6 == [] and "לאשר אותה" in reply6a)
chk("Test 6a: reconfirmation text is human-readable (uses the description helper)",
    "airtable_add" not in reply6a and c6.contract_id[:8] not in reply6a)
chk("Test 6a: bookmark is still present after the bounce-back (not cleared)",
    lead_sessions.get_last_prompted_contract(USER) is not None)

reply6b = gw6.route_confirmation_word(USER, approver_role="owner")
chk("Test 6b: second 'כן' resolves the SAME bookmarked contract directly, "
    "still ignoring the 3 old unrelated ones", ex6 == [("airtable_add", c6.contract_id)])
chk("Test 6b: bookmark is cleared now that the contract reached a terminal state",
    lead_sessions.get_last_prompted_contract(USER) is None)
chk("Test 6: the 3 old unrelated contracts were never touched",
    all(gw6.find_contract(cid).status == "pending" for cid in old6))

# ══════════════════════════════════════════════════
# Test 7 — bookmark cleared after a successful direct approve (terminal).
# ══════════════════════════════════════════════════

_clear_session()
gw7, ex7 = _make_gw()
c7 = _propose(gw7, USER, table="Tasks", fields={"a": 1})
_bookmark(c7)
gw7.route_confirmation_word(USER, approver_role="owner")
chk("Test 7: bookmark cleared after a terminal (approved) resolution",
    lead_sessions.get_last_prompted_contract(USER) is None)

# ══════════════════════════════════════════════════
# Test 8 — integration: core/lead_candidate_handler.py's lead preview path
# (_handle_single_candidate(), the Tier-1 handler _propose_lead_write()'s
# actual caller) actually SETS the bookmark, not just the mechanism in
# isolation tested above.
# ══════════════════════════════════════════════════

_clear_session()
from core.lead_candidate_handler import _handle_single_candidate  # noqa: E402
from identity import Identity as _Identity  # noqa: E402

_identity8 = _Identity(
    user_id="eliyahu", role="owner", tenant_id="boss_hq",
    channel="telegram", external_id="tg-eliyahu",
)
chk("Test 8 setup: identity.memory_key matches this file's USER constant",
    _identity8.memory_key == USER)
_candidate8 = {"name": "לענף גיוס", "phone": "0548442163", "context": []}
_reply8 = _handle_single_candidate(
    _identity8, _candidate8, "צור ליד חדש לענף גיוס 0548442163",
    "chat-8", "telegram", "general", auto_write=False,
)
chk("Test 8: _handle_single_candidate() returned the expected preview text",
    _reply8 is not None and "זיהיתי ליד" in _reply8)
_bm8 = lead_sessions.get_last_prompted_contract(USER)
chk("Test 8: the lead preview path set the BUG-115 bookmark",
    _bm8 is not None and _bm8.get("kind") == "lead_preview")


print()
print("=" * 50)
print(f"BUG-115 confirmation-routing bookmark tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
