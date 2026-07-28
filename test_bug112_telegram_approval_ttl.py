#!/usr/bin/env python3
"""
test_bug112_telegram_approval_ttl.py — BUG-112 (Telegram approval button TTL
not enforced before execution).

Problem: the Telegram inline approval button says "פג תוקף בעוד 10 דקות"
("expires in 10 minutes") — app.py's _PENDING_APPROVAL_TTL (600s), the same
constant the router-level free-text "מאשר" pending-approval gate uses. But
app.py's _handle_approval_callback_impl() only ever called
event_bus.bus.pop(action_id), which enforces event_bus.py's OWN, separate,
longer TTL (PendingActionsStore.PENDING_TTL_MINUTES = 30 minutes) — a
general cleanup horizon for the whole store, unrelated to what any specific
approval message advertises. A button press between minute 10 and minute 30
still executed the tool, even though the user had been told it would have
expired by minute 10.

Fix: _handle_approval_callback_impl() now independently checks the popped
item's "created" timestamp against the SAME _PENDING_APPROVAL_TTL (600s)
right after popping it from the bus, for every "approve" callback (tool and
non-tool), before any dispatch/execute decision. A stale callback:
  - never dispatches/executes (_reject_stale_telegram_approval() returns
    before any dispatch_tool()/ActionGateway.approve() call)
  - rejects the matching live ActionGateway contract, if one exists and can
    be positively verified (never a blind "assume it worked")
  - notifies the approver with a PERSISTENT chat message ("⏰ פג תוקף — הפעולה
    לא בוצעה"), not only the transient answer_callback_query() popup
  - edits the original approval message so it no longer looks actionable
  - never falls through to legacy dispatch_tool()

Regression note: the router-level (free-text "מאשר") pending-approval TTL
gate inside run_agent() already used _PENDING_APPROVAL_TTL correctly and is
untouched by this fix — Section 2 below is a regression guard proving that
mechanism still behaves exactly as before, using the SAME direct-helper-
function testing convention test_bug070_pending_approval_multi.py already
established for this block (too heavy to invoke run_agent() directly for a
single-branch check — the TTL comparison itself is mirrored by hand here,
exactly as that file's _classify() mirrors the classification branch).

Explicitly NOT touched by this fix, verified not to regress: BUG-111 lead
parsing, F52/agent_message_formatter, FEATURE_UNIFIED_STATUS_FORMATTER, RP5,
and tool execution semantics for anything other than stale-approval
blocking (a live, non-expired callback still executes exactly as before —
see Section 1, Tests 1-2).

── BUG-112 production follow-up (Section 4, Tests 8b-8d, 4b/14-18) ──

A real production transcript showed a repeated/duplicate press on an
already-TTL-expired button producing THREE overlapping-but-different
"this didn't happen" phrasings for one event: the first press correctly
showed "⏰ פג תוקף — הפעולה לא בוצעה" (the fix above), but the SECOND press
(bus.pop() now returns None — item already consumed) fell through to the
GENERIC _notify_stale_or_resolved_callback() helper (built for "already
executed"/"already rejected", each with its own genuinely distinct
wording) with a placeholder label and a third state_text
("פגה או כבר לא קיימת"), producing yet another differently-worded notice
right after the first. Safety was never in question — bus.pop() returning
None already guarantees zero dispatch either way — this was a wording-only
redundancy. Fixed with a new, dedicated app._notify_missing_or_expired_
callback(), reusing ONE literal phrase identically across the popup, the
persistent chat message, and the edited original message — never built
from the generic label/state_text template. The two call sites that
legitimately need distinct wording ("כבר בוצעה"/"כבר בוטלה") still use the
original _notify_stale_or_resolved_callback() unchanged. The two callback
paths remain intentionally separate (a known-and-now-expired item vs. a
not-found/already-consumed one) — this fix does not merge their wording
into a single shared literal, only removes the redundancy WITHIN the
not-found path itself.

── Follow-up UX patch (business-facing wording pass) ──

The original single literal phrase ("ℹ️ הפעולה כבר פגה או אינה קיימת, ולכן
לא בוצעה.") still had its own internal redundancy — "פגה" (expired) and
"אינה קיימת" (doesn't exist) read as the same thing to a business user, and
"קיימת" describes internal record state rather than a business outcome.
Reworded to app._MISSING_OR_EXPIRED_CALLBACK_TEXT = "ℹ️ הפעולה כבר אינה
זמינה, ולכן לא בוצעה." — one non-redundant, business-facing statement.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug112-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG112_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug112Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug112Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from identity import Identity, Role  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
from event_bus import bus as _real_bus  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str, role: str) -> Identity:
    return Identity(
        user_id=user_id, role=role, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


def _fake_cq(approver_chat_id: str, data: str):
    return SimpleNamespace(
        id="cbq1",
        data=data,
        from_user=SimpleNamespace(id=approver_chat_id),
        message=SimpleNamespace(chat=SimpleNamespace(id="chat1"), message_id=1),
    )


def _ok_dispatch(*args, **kwargs):
    return {"ok": True, "tool": "send_followup", "external_id": "audit-ok",
            "evidence": {"audit_id": "audit-ok"}, "user_message": "✅ בוצע"}


def _run_callback(
    *, requester: Identity, approver: Identity, dispatch_mock,
    seed_contract: bool, feature_gw: bool, tool_inputs: dict,
    age_seconds: float = 0.0,
):
    """Queues a real event_bus item (+ optionally a real ActionGateway
    contract), optionally backdates the item's "created" timestamp to
    simulate a stale (but not yet event_bus-internally-expired) callback,
    then drives app._handle_approval_callback_impl() with everything else
    mocked — mirrors test_pr0c_telegram_callback_gateway.py's _run_callback,
    extended with age_seconds for BUG-112."""
    action_id, _ = _real_bus.request_approval(
        action="send_followup",
        payload={
            "tool_name": "send_followup",
            "tool_inputs": tool_inputs,
            "origin_channel": "telegram",
            "origin_chat_id": requester.user_id,
            "canonical_user_id": requester.memory_key,
            "user_chat_id": requester.user_id,
            "channel": "telegram",
        },
        chat_id=requester.user_id,
        label="test followup",
    )

    if age_seconds:
        # Backdate "created" only — deliberately NOT "expires", so this stays
        # well within event_bus.py's own 30-minute PendingActionsStore TTL
        # (bus.pop() must still hand back the item) while landing beyond the
        # 10-minute window this fix enforces separately.
        backdated = (datetime.now() - timedelta(seconds=age_seconds)).isoformat()
        _real_bus._pending._store[action_id]["created"] = backdated

    contract_id = None
    if seed_contract:
        propose = _real_gw.propose_action(
            tenant_id="boss_hq", canonical_user_id=requester.memory_key,
            tool_name="send_followup", tool_inputs=tool_inputs,
            origin_channel="telegram", origin_chat_id=requester.user_id,
            requires_approval=True, identity=requester, trusted_source="agent",
        )
        contract_id = propose.contract_id

    def _resolve_identity_side_effect(channel, ext_id):
        return approver if ext_id == approver.user_id else requester

    cq = _fake_cq(approver.user_id, f"approve:{action_id}")
    mock_bot = MagicMock()

    _flag_side_effect = lambda name: (
        feature_gw if name == "FEATURE_ACTION_GATEWAY"
        else name == "FEATURE_SINGLE_SPEAKER_APPROVAL_UX"
    )

    with patch.object(app, "bot", mock_bot), \
         patch.object(app, "resolve_identity", side_effect=_resolve_identity_side_effect), \
         patch("tools.dispatcher.dispatch_tool", side_effect=dispatch_mock) as _dt_gw, \
         patch.object(app, "dispatch_tool", side_effect=dispatch_mock) as _dt_legacy, \
         patch.object(app, "_flag_enabled", side_effect=_flag_side_effect), \
         patch("feature_flags.is_enabled", side_effect=_flag_side_effect):
        app._handle_approval_callback_impl(cq)

    total_dispatch_calls = _dt_gw.call_count + _dt_legacy.call_count
    final_contract = _real_gw._ledger.find_by_id(contract_id) if contract_id else None
    return total_dispatch_calls, final_contract, mock_bot


# ══════════════════════════════════════════════════════════════════
# 1. Live callback (within TTL) — execution is UNCHANGED
# ══════════════════════════════════════════════════════════════════
print("── 1. callback approve WITHIN TTL still executes ──────────────")

print("\n── Test 1: flag off, fresh callback — legacy dispatch still fires ──")
requester1 = _identity("req_bug112_1", Role.OWNER)
approver1 = _identity("appr_bug112_1", Role.OWNER)
calls1, contract1, bot1 = _run_callback(
    requester=requester1, approver=approver1, dispatch_mock=_ok_dispatch,
    seed_contract=False, feature_gw=False, tool_inputs={"chat_id": "req_bug112_1", "draft": "a"},
    age_seconds=60,  # 1 minute — well within the 10-minute window
)
chk("Test1: dispatch_tool called exactly once (fresh callback, unaffected)", calls1 == 1)

print("\n── Test 2: flag on + live contract, fresh callback — Gateway path fires ──")
requester2 = _identity("req_bug112_2", Role.OWNER)
approver2 = _identity("appr_bug112_2", Role.OWNER)
calls2, contract2, bot2 = _run_callback(
    requester=requester2, approver=approver2, dispatch_mock=_ok_dispatch,
    seed_contract=True, feature_gw=True, tool_inputs={"chat_id": "req_bug112_2", "draft": "b"},
    age_seconds=60,
)
chk("Test2: dispatch_tool called exactly once (via Gateway executor)", calls2 == 1)
chk("Test2: contract ends 'executed'", contract2 is not None and contract2.status == "executed")

print("\n── Test 2b: right at the boundary (9 minutes) still executes ──")
requester2b = _identity("req_bug112_2b", Role.OWNER)
approver2b = _identity("appr_bug112_2b", Role.OWNER)
calls2b, contract2b, _ = _run_callback(
    requester=requester2b, approver=approver2b, dispatch_mock=_ok_dispatch,
    seed_contract=True, feature_gw=True, tool_inputs={"chat_id": "req_bug112_2b", "draft": "b2"},
    age_seconds=540,  # 9 minutes — under the 600s cutoff
)
chk("Test2b: 9-minute-old callback (still under 10-minute TTL) executes",
    calls2b == 1 and contract2b is not None and contract2b.status == "executed")


# ══════════════════════════════════════════════════════════════════
# 2. Expired callback (past the advertised 10-minute TTL, but still within
#    event_bus's own 30-minute internal TTL) — must NOT execute
# ══════════════════════════════════════════════════════════════════
print()
print("── 2. callback approve AFTER TTL does not execute ─────────────")

print("\n── Test 3: flag off, expired callback — no legacy dispatch ────")
requester3 = _identity("req_bug112_3", Role.OWNER)
approver3 = _identity("appr_bug112_3", Role.OWNER)
calls3, contract3, bot3 = _run_callback(
    requester=requester3, approver=approver3, dispatch_mock=_ok_dispatch,
    seed_contract=False, feature_gw=False, tool_inputs={"chat_id": "req_bug112_3", "draft": "c"},
    age_seconds=700,  # 11m40s — past the 10-minute advertised TTL, well under the 30-minute bus TTL
)
chk("Test3: expired callback does not call dispatch_tool", calls3 == 0)

print("\n── Test 4: flag on + live contract, expired callback — no Gateway execution ──")
requester4 = _identity("req_bug112_4", Role.OWNER)
approver4 = _identity("appr_bug112_4", Role.OWNER)
calls4, contract4, bot4 = _run_callback(
    requester=requester4, approver=approver4, dispatch_mock=_ok_dispatch,
    seed_contract=True, feature_gw=True, tool_inputs={"chat_id": "req_bug112_4", "draft": "d"},
    age_seconds=700,
)
chk("Test4: expired callback does not call dispatch_tool (no fallthrough execution)",
    calls4 == 0)
chk("Test4: expired callback does not leave the contract 'executed' — "
    "ActionGateway.approve() was never reached",
    contract4 is not None and contract4.status != "executed")
chk("Test4: expired callback clears/rejects the matching ActionGateway "
    "pending contract — no live pending contract/button left behind",
    contract4 is not None and contract4.status == "rejected")

print("\n── Test 4b: same, driven with the real ActionGateway.approve() "
      "patched to prove it is never called at all ──")
requester4b = _identity("req_bug112_4b", Role.OWNER)
approver4b = _identity("appr_bug112_4b", Role.OWNER)
action_id_4b, _ = _real_bus.request_approval(
    action="send_followup",
    payload={
        "tool_name": "send_followup",
        "tool_inputs": {"chat_id": "req_bug112_4b", "draft": "e"},
        "origin_channel": "telegram",
        "origin_chat_id": requester4b.user_id,
        "canonical_user_id": requester4b.memory_key,
        "user_chat_id": requester4b.user_id,
        "channel": "telegram",
    },
    chat_id=requester4b.user_id,
    label="test followup 4b",
)
_real_bus._pending._store[action_id_4b]["created"] = (
    datetime.now() - timedelta(seconds=700)
).isoformat()
_real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=requester4b.memory_key,
    tool_name="send_followup", tool_inputs={"chat_id": "req_bug112_4b", "draft": "e"},
    origin_channel="telegram", origin_chat_id=requester4b.user_id,
    requires_approval=True, identity=requester4b, trusted_source="agent",
)
cq_4b = _fake_cq(approver4b.user_id, f"approve:{action_id_4b}")
mock_bot_4b = MagicMock()
_flag_on_only = lambda name: name in {
    "FEATURE_ACTION_GATEWAY", "FEATURE_SINGLE_SPEAKER_APPROVAL_UX",
}
with patch.object(app, "bot", mock_bot_4b), \
     patch.object(app, "resolve_identity",
                   side_effect=lambda ch, ext_id: approver4b if ext_id == approver4b.user_id else requester4b), \
     patch.object(_real_gw, "approve", wraps=_real_gw.approve) as _approve_spy, \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch), \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch), \
     patch.object(app, "_flag_enabled", side_effect=_flag_on_only), \
     patch("feature_flags.is_enabled", side_effect=_flag_on_only):
    app._handle_approval_callback_impl(cq_4b)
chk("Test4b: expired callback does not call ActionGateway.approve()",
    _approve_spy.call_count == 0)


# ══════════════════════════════════════════════════════════════════
# 3. Persistent notification, not just the transient popup
# ══════════════════════════════════════════════════════════════════
print()
print("── 3. expired callback gives a persistent user-visible message ─")

chk("Test5: expired callback still answers the callback query (immediate ack)",
    bot4.answer_callback_query.called)
chk("Test5: expired callback ALSO sends a persistent chat message — "
    "not only answer_callback_query()",
    bot4.send_message.called)
_persistent_text_4 = bot4.send_message.call_args[0][1]
chk("Test5: persistent message matches the required exact wording "
    "'פג תוקף — הפעולה לא בוצעה'",
    "פג תוקף — הפעולה לא בוצעה" in _persistent_text_4)
_popup_text_4 = bot4.answer_callback_query.call_args[0][1]
chk("Test5: the popup itself also carries the same wording",
    "פג תוקף" in _popup_text_4)
chk("Test6: the original approval message is edited so it no longer "
    "looks actionable",
    bot4.edit_message_text.called or bot4.edit_message_reply_markup.called)


# ══════════════════════════════════════════════════════════════════
# 4. No live pending contract/button left behind after an expired press
# ══════════════════════════════════════════════════════════════════
print()
print("── 4. expired callback leaves no live, still-approvable state ──")

chk("Test7: the EventBus item is gone after the expired press "
    "(bus.pop() already consumed it)",
    _real_bus.peek(action_id_4b) is None)

# Pressing the SAME (already-consumed, already-expired) button a second time
# must not execute either — bus.pop() on an already-popped id returns None,
# hitting the pre-existing "not found" branch (unrelated to this fix, still
# must never execute a second time).
cq_4b_again = _fake_cq(approver4b.user_id, f"approve:{action_id_4b}")
mock_bot_4b_again = MagicMock()
with patch.object(app, "bot", mock_bot_4b_again), \
     patch.object(app, "resolve_identity",
                   side_effect=lambda ch, ext_id: approver4b if ext_id == approver4b.user_id else requester4b), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_again, \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy_again, \
     patch.object(app, "_flag_enabled", side_effect=_flag_on_only), \
     patch("feature_flags.is_enabled", side_effect=_flag_on_only):
    app._handle_approval_callback_impl(cq_4b_again)
chk("Test8: re-pressing the same expired button a second time still "
    "dispatches zero times",
    _dt_again.call_count == 0 and _dt_legacy_again.call_count == 0)

chk("Test9: after an expired press, the matching contract is durably "
    "'rejected' — re-approving it later via a different route "
    "(e.g. free-text) is no longer possible from a 'pending' state",
    contract4 is not None and contract4.status == "rejected")

# BUG-112 production follow-up: the SECOND press above (already-consumed,
# bus.pop() returns None) used to produce a differently-worded "missing"
# notice ("⏰ פג תוקף — הפעולה לא קיימת יותר" popup + "ℹ️ הפעולה המבוקשת /
# פגה או כבר לא קיימת, ולכן לא בוצעה שוב." persistent message) right after
# the FIRST press had already shown "⏰ פג תוקף — הפעולה לא בוצעה" — three
# overlapping-but-different phrasings read together as one confusing event.
# Both presses must now use ONE single, consistent-with-itself phrase.
chk("Test8b: the second (missing/already-consumed) press's popup uses the "
    "single normalized phrase, not the old '...לא קיימת יותר' wording",
    mock_bot_4b_again.answer_callback_query.called
    and "הפעולה כבר אינה זמינה, ולכן לא בוצעה" in mock_bot_4b_again.answer_callback_query.call_args[0][1])
chk("Test8c: the second press uses the edited approval message as its one final response",
    not mock_bot_4b_again.send_message.called
    and mock_bot_4b_again.edit_message_text.call_count == 1
    and mock_bot_4b_again.edit_message_text.call_args[0][0] == mock_bot_4b_again.answer_callback_query.call_args[0][1])
chk("Test8d: the first press's message ('⏰ פג תוקף — הפעולה לא בוצעה', "
    "captured earlier as _persistent_text_4) and the second press's message "
    "are DIFFERENT strings from each other — the two paths stay distinct "
    "(a genuinely-known TTL expiry vs. a not-found/already-consumed "
    "callback), each internally single/non-redundant, not merged into one "
    "shared literal",
    mock_bot_4b_again.edit_message_text.call_args[0][0] != _persistent_text_4)


# ══════════════════════════════════════════════════════════════════
# 4b. Standalone "missing/never-registered" callback (independent of a
# prior press) — proves _notify_missing_or_expired_callback() directly,
# not only via the repeated-press scenario above.
# ══════════════════════════════════════════════════════════════════
print()
print("── 4b. standalone missing/unknown callback — one consistent message ──")

approver6 = _identity("appr_bug112_6", Role.OWNER)
cq_6 = _fake_cq(approver6.user_id, "approve:never-existed-action-id")
mock_bot_6 = MagicMock()
with patch.object(app, "bot", mock_bot_6), \
     patch.object(app, "resolve_identity", return_value=approver6), \
     patch("tools.dispatcher.dispatch_tool", side_effect=_ok_dispatch) as _dt_6, \
     patch.object(app, "dispatch_tool", side_effect=_ok_dispatch) as _dt_legacy_6, \
     patch.object(app, "_flag_enabled", side_effect=_flag_on_only), \
     patch("feature_flags.is_enabled", side_effect=_flag_on_only):
    app._handle_approval_callback_impl(cq_6)

chk("Test14: a callback for an action_id that was never queued at all "
    "never dispatches",
    _dt_6.call_count == 0 and _dt_legacy_6.call_count == 0)
chk("Test15: the popup uses the single normalized 'missing' phrase",
    mock_bot_6.answer_callback_query.called
    and mock_bot_6.answer_callback_query.call_args[0][1] == app._MISSING_OR_EXPIRED_CALLBACK_TEXT)
chk("Test16: an unknown callback sends no duplicate persistent message",
    not mock_bot_6.send_message.called)
chk("Test17: the original message is the one final response and uses the popup's semantic phrase",
    mock_bot_6.edit_message_text.called
    and mock_bot_6.edit_message_text.call_args[0][0] == app._MISSING_OR_EXPIRED_CALLBACK_TEXT)
chk("Test18: the normalized phrase itself is a single, self-contained "
    "sentence naming both facts (no longer available AND not executed) — "
    "not glued from a separate label + state_text pair, and no longer "
    "duplicates the same meaning twice ('expired' vs. 'doesn't exist')",
    "אינה זמינה" in app._MISSING_OR_EXPIRED_CALLBACK_TEXT
    and "לא בוצעה" in app._MISSING_OR_EXPIRED_CALLBACK_TEXT
    and "פגה" not in app._MISSING_OR_EXPIRED_CALLBACK_TEXT
    and "קיימת" not in app._MISSING_OR_EXPIRED_CALLBACK_TEXT)


# ══════════════════════════════════════════════════════════════════
# 5. Regression: router-level (free-text "מאשר") TTL gate is untouched
# ══════════════════════════════════════════════════════════════════
print()
print("── 5. regression: text-confirm TTL behavior remains unchanged ──")

chk("Test9b: _PENDING_APPROVAL_TTL is still 600 seconds (10 minutes) — "
    "the value the button wording advertises and BUG-112 now also enforces "
    "on the Telegram callback path",
    app._PENDING_APPROVAL_TTL == 600)

# Mirrors run_agent()'s "2.5 Pending Approval Gate" TTL check by hand — same
# convention test_bug070_pending_approval_multi.py already established for
# this block (too heavy to invoke run_agent() directly for a single-branch
# check). Exercises the REAL _add_pending_approval/_pop_pending_approval
# helpers, not a reimplementation of them.
chat_id_ttl = "bug112_text_confirm_ttl"
app._pending_approvals.pop(chat_id_ttl, None)

fresh_id = app._add_pending_approval(
    chat_id_ttl, {"text": "פעולה טרייה", "created_at": time.time()},
)
stale_id = app._add_pending_approval(
    chat_id_ttl, {"text": "פעולה ישנה", "created_at": time.time() - 700},
)

fresh_entry = app._pending_approvals[chat_id_ttl][fresh_id]
stale_entry = app._pending_approvals[chat_id_ttl][stale_id]

chk("Test10: a fresh (1-minute-implicit, i.e. just-created) pending entry "
    "is NOT past the TTL",
    time.time() - fresh_entry["created_at"] <= app._PENDING_APPROVAL_TTL)
chk("Test11: a 700-second-old pending entry IS past the TTL — matches "
    "run_agent()'s own comparison expression exactly",
    time.time() - stale_entry["created_at"] > app._PENDING_APPROVAL_TTL)

# Same expiry-then-pop sequence run_agent() performs for the router-level
# gate: expired entries are popped and treated as "nothing pending" (falls
# through to normal message handling), never executed as a stale confirm.
if time.time() - stale_entry["created_at"] > app._PENDING_APPROVAL_TTL:
    app._pop_pending_approval(chat_id_ttl, stale_id)
chk("Test12: the expired entry is removed from _pending_approvals after "
    "the TTL check (same _pop_pending_approval() helper the callback path "
    "reuses none of — separate mechanisms, both correctly enforcing 600s)",
    stale_id not in app._pending_approvals.get(chat_id_ttl, {}))
chk("Test13: the fresh entry is untouched by the expired-sibling's cleanup",
    fresh_id in app._pending_approvals.get(chat_id_ttl, {}))

app._pending_approvals.pop(chat_id_ttl, None)


print(f"\n{'='*50}")
print(f"BUG-112 (Telegram approval TTL) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
