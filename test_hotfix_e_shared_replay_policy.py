#!/usr/bin/env python3
"""
test_hotfix_e_shared_replay_policy.py — Hotfix E regression suite.

CodeRabbit finding on PR #494 + owner-directed follow-up: patching only the
two app.py call sites (PR2's resolver, the legacy cancel-word site) left the
SHARED root unbounded — ActionGateway.describe_no_pending_reason() called
find_most_recent_by_user() (no age bound, any status) and replayed whatever
it found, reachable from THREE callers: the legacy Stage A bare-confirm
fallback (app.py, FEATURE_ACTION_GATEWAY off — the default), Action
Gateway.route_confirmation_word()'s own no-live branch (reached by both
Stage A and Stage B legacy call sites), and describe_pending_queue()'s
no-live branch.

Fix: describe_no_pending_reason() now has exactly one job — the canonical
no-pending response, no ledger query at all. The one legitimate same-turn
exception (BUG-PENDING-APPROVAL-B's "your previous action was superseded by
a second interruption" message) is preserved but moved to a separate,
narrow method, describe_superseded_reason() — callers that want it call it
explicitly and fall back to describe_no_pending_reason(); it is NOT called
from describe_pending_queue() (a pending-list/status question is not a
request for why a specific confirm word didn't resolve).

This file proves:
  1. describe_no_pending_reason() is pure — same output regardless of what
     terminal-status history exists for the user (approved/executing/
     rejected/completed/failed/outcome_unknown/superseded all included).
  2. describe_superseded_reason() only ever fires for status=="superseded",
     never for any other status, and is not used by describe_pending_queue().
  3. route_confirmation_word()'s no-live branch: canonical no-pending for
     every non-superseded history status; the specific supersede message
     only for status=="superseded".
  4. describe_pending_queue()'s no-live branch: canonical no-pending for
     every history status, including superseded (no exception there).
  5. Full app.run_agent() coverage for bare "כן"/"מאשר" with no live
     contract, both FEATURE_ACTION_GATEWAY on and off, proving identical
     canonical-no-pending output, zero mutation, zero Agent calls, one
     final response, cross-channel canonical identity.
  6. "יצרת?" (explicit status query) is unaffected — still uses the bounded
     24h find_recent_terminal_by_user() policy, unchanged from BUG-151.
  7. No Session-bookmark authority in the no-pending outcome.
  8. CodeRabbit finding on PR #497: describe_superseded_reason() itself is
     bounded by _SUPERSEDED_REASON_MAX_AGE_SECONDS (24h) — an old superseded
     contract with no newer contract since must NOT keep resurfacing on
     later, unrelated bare confirm words; it falls through to the canonical
     no-pending response once stale, same as any other history status.
"""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
os.environ["ANTHROPIC_API_KEY"] = "sk-hotfixe-test"
os.environ["TELEGRAM_TOKEN"] = "123456789:HOTFIXE_TEST_TOKEN"
os.environ["AIRTABLE_API_KEY"] = "patHotfixETest"
os.environ["AIRTABLE_BASE_ID"] = "appHotfixETest"
os.environ["RENDER_APP_URL"] = "https://example.com"
os.environ["SETUP_WEBHOOK"] = "0"

import app  # noqa: E402
import feature_flags  # noqa: E402
import core.action_gateway as action_gateway_module  # noqa: E402
from core.action_gateway import ActionContract, ActionGateway, ExecutionLedger  # noqa: E402
from identity import Identity, Role  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


_CANONICAL_NO_PENDING = "אין פעולה שממתינה לאישור"
_ALL_NON_LIVE_STATUSES = (
    "completed", "executed", "rejected", "approved", "executing",
    "failed", "outcome_unknown",
)


def _historical_contract(contract_id: str, canonical_user_id: str, status: str,
                          age_seconds: float = 20) -> ActionContract:
    return ActionContract(
        contract_id=contract_id, tenant_id="boss_hq", canonical_user_id=canonical_user_id,
        tool_name="airtable_add", normalized_payload={"table": "Leads", "fields": {}},
        business_action_fingerprint=f"fp-{contract_id}", origin_channel="telegram",
        origin_chat_id="hotfixe", requires_approval=True, status=status,
        created_at=time.time() - age_seconds,
    )


# ══════════════════════════════════════════════════
# 1. describe_no_pending_reason() is pure — no ledger query at all
# ══════════════════════════════════════════════════
print("── describe_no_pending_reason(): pure, history-free ────────────")

for status in _ALL_NON_LIVE_STATUSES + ("superseded",):
    gw = ActionGateway(ledger=ExecutionLedger())
    gw._ledger.save(_historical_contract(f"hfe-{status}", "boss_hq:hfe-owner", status))
    reply = gw.describe_no_pending_reason("boss_hq:hfe-owner")
    chk(f"describe_no_pending_reason() ignores status={status!r} -> canonical no-pending",
        reply == _CANONICAL_NO_PENDING)

_empty_gw = ActionGateway(ledger=ExecutionLedger())
chk("describe_no_pending_reason() with truly empty ledger -> canonical no-pending",
    _empty_gw.describe_no_pending_reason("boss_hq:hfe-empty") == _CANONICAL_NO_PENDING)


# ══════════════════════════════════════════════════
# 2. describe_superseded_reason() — narrow, superseded-only
# ══════════════════════════════════════════════════
print("\n── describe_superseded_reason(): narrow, superseded-only ───────")

for status in _ALL_NON_LIVE_STATUSES:
    gw = ActionGateway(ledger=ExecutionLedger())
    gw._ledger.save(_historical_contract(f"hfe-sup-{status}", "boss_hq:hfe-owner2", status))
    chk(f"describe_superseded_reason() returns None for status={status!r}",
        gw.describe_superseded_reason("boss_hq:hfe-owner2") is None)

_sup_gw = ActionGateway(ledger=ExecutionLedger())
_sup_gw._ledger.save(_historical_contract("hfe-superseded", "boss_hq:hfe-owner3", "superseded"))
_sup_reply = _sup_gw.describe_superseded_reason("boss_hq:hfe-owner3")
chk("describe_superseded_reason() fires for status='superseded'",
    _sup_reply is not None and "בוטלה" in _sup_reply and "פעולה אחרת" in _sup_reply)

# CodeRabbit finding on PR #497: a superseded contract older than the
# bound must NOT resurface — falls through to canonical no-pending, same
# as any other stale history status.
_stale_max_age = action_gateway_module._SUPERSEDED_REASON_MAX_AGE_SECONDS
_stale_sup_gw = ActionGateway(ledger=ExecutionLedger())
_stale_sup_gw._ledger.save(_historical_contract(
    "hfe-superseded-stale", "boss_hq:hfe-owner4", "superseded",
    age_seconds=_stale_max_age + 60,
))
chk("describe_superseded_reason() returns None for a superseded contract past the age bound",
    _stale_sup_gw.describe_superseded_reason("boss_hq:hfe-owner4") is None)
chk("route_confirmation_word() no live + stale superseded -> canonical no-pending (not the supersede message)",
    _stale_sup_gw.route_confirmation_word("boss_hq:hfe-owner4", approver_role="owner")
    == _CANONICAL_NO_PENDING)


# ══════════════════════════════════════════════════
# 3. route_confirmation_word() no-live branch
# ══════════════════════════════════════════════════
print("\n── route_confirmation_word(): no-live branch ────────────────────")

for status in _ALL_NON_LIVE_STATUSES:
    gw = ActionGateway(ledger=ExecutionLedger())
    gw._ledger.save(_historical_contract(f"hfe-rcw-{status}", "boss_hq:hfe-rcw", status))
    reply = gw.route_confirmation_word("boss_hq:hfe-rcw", approver_role="owner")
    chk(f"route_confirmation_word() no live + history status={status!r} -> canonical no-pending",
        reply == _CANONICAL_NO_PENDING)

_rcw_sup_gw = ActionGateway(ledger=ExecutionLedger())
_rcw_sup_gw._ledger.save(_historical_contract("hfe-rcw-superseded", "boss_hq:hfe-rcw2", "superseded"))
_rcw_sup_reply = _rcw_sup_gw.route_confirmation_word("boss_hq:hfe-rcw2", approver_role="owner")
chk("route_confirmation_word() no live + superseded -> specific supersede message preserved",
    _rcw_sup_reply is not None and "בוטלה" in _rcw_sup_reply and _rcw_sup_reply != _CANONICAL_NO_PENDING)


# ══════════════════════════════════════════════════
# 4. describe_pending_queue() no-live branch — no exception for superseded
# ══════════════════════════════════════════════════
print("\n── describe_pending_queue(): no-live branch (no supersede exception) ──")

for status in _ALL_NON_LIVE_STATUSES + ("superseded",):
    gw = ActionGateway(ledger=ExecutionLedger())
    gw._ledger.save(_historical_contract(f"hfe-pq-{status}", "boss_hq:hfe-pq", status))
    reply = gw.describe_pending_queue("boss_hq:hfe-pq")
    chk(f"describe_pending_queue() no live + history status={status!r} -> canonical no-pending "
        f"(no historical replay, not even for superseded)",
        reply.startswith(_CANONICAL_NO_PENDING))

_pq_live_gw = ActionGateway(ledger=ExecutionLedger())
_pq_live_contract = _historical_contract("hfe-pq-live", "boss_hq:hfe-pq-live", "pending", age_seconds=0)
_pq_live_gw._ledger.save(_pq_live_contract)
_pq_live_reply = _pq_live_gw.describe_pending_queue("boss_hq:hfe-pq-live")
chk("describe_pending_queue() renders live contracts when they exist",
    "1" in _pq_live_reply and "ActionContracts" in _pq_live_reply)


print(f"\n{'='*50}")
print(f"Hotfix E — unit-level: {passed} passed, {failed} failed so far")


# ══════════════════════════════════════════════════
# 5. Full app.run_agent() coverage — bare confirm words, no live contract,
# unrelated historical contract present, both FEATURE_ACTION_GATEWAY states.
# ══════════════════════════════════════════════════
print("\n── app.run_agent(): bare confirm words end-to-end ────────────────")

_real_is_enabled = feature_flags.is_enabled


def _agent_must_not_be_called(*args, **kwargs):
    raise AssertionError("Agent (Anthropic) must not be called for this turn")


def _run_bare_confirm(
    word: str, chat_id: str, channel: str, *, action_gateway_flag: bool,
    pr2_flag: bool,
) -> tuple[str, ActionGateway]:
    gw = ActionGateway(ledger=ExecutionLedger())
    identity = Identity(user_id=chat_id, role=Role.OWNER, channel=channel, external_id=chat_id)
    unrelated = _historical_contract(
        f"hfe-e2e-{chat_id}", identity.memory_key, "completed", age_seconds=20,
    )
    gw._ledger.save(unrelated)

    def _flag_side_effect(name):
        if name == "FEATURE_ACTION_GATEWAY":
            return action_gateway_flag
        if name == "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS":
            return pr2_flag
        return _real_is_enabled(name)

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(action_gateway_module, "action_gateway", gw), \
         patch("feature_flags.is_enabled", side_effect=_flag_side_effect), \
         patch.object(app.client.messages, "create", side_effect=_agent_must_not_be_called):
        reply = app.run_agent(word, chat_id, channel)
    return reply, gw


for word in ("כן", "מאשר"):
    for ag_flag, ag_label in ((True, "FEATURE_ACTION_GATEWAY=on"), (False, "FEATURE_ACTION_GATEWAY=off")):
        chat_id = f"hfe-{word}-{ag_flag}"
        try:
            reply, gw = _run_bare_confirm(
                word, chat_id, "telegram", action_gateway_flag=ag_flag, pr2_flag=False,
            )
            chk(f"run_agent({word!r}, {ag_label}, legacy path): canonical no-pending, zero Agent calls",
                reply == _CANONICAL_NO_PENDING)
        except AssertionError as e:
            chk(f"run_agent({word!r}, {ag_label}, legacy path): canonical no-pending, zero Agent calls "
                f"-- {e}", False)
            continue
        unrelated_after = gw.find_contract(f"hfe-e2e-{chat_id}")
        chk(f"run_agent({word!r}, {ag_label}): unrelated historical contract left untouched",
            unrelated_after is not None and unrelated_after.status == "completed")

# PR2's own resolver (FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS=on) — same
# invariant via a different call path, with request-local metrics available.
for word in ("כן", "מאשר"):
    chat_id = f"hfe-pr2-{word}"
    gw = ActionGateway(ledger=ExecutionLedger())
    identity = Identity(user_id=chat_id, role=Role.OWNER, channel="telegram", external_id=chat_id)
    unrelated = _historical_contract(f"hfe-pr2-e2e-{chat_id}", identity.memory_key, "completed", age_seconds=20)
    gw._ledger.save(unrelated)

    def _flag_side_effect_pr2(name):
        if name in ("FEATURE_ACTION_GATEWAY", "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS"):
            return True
        return _real_is_enabled(name)

    _captured_pr2 = {}

    import core.approval_turn_metrics as approval_turn_metrics_module
    _real_atm_end = approval_turn_metrics_module.end

    def _capturing_end(token, ingress):
        m = approval_turn_metrics_module.current()
        if m is not None:
            _captured_pr2["agent_call_count"] = m.agent_call_count
            _captured_pr2["final_response_count"] = m.final_response_count
        _real_atm_end(token, ingress)

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(action_gateway_module, "action_gateway", gw), \
         patch("feature_flags.is_enabled", side_effect=_flag_side_effect_pr2), \
         patch.object(approval_turn_metrics_module, "end", _capturing_end), \
         patch.object(app.client.messages, "create", side_effect=_agent_must_not_be_called):
        reply_pr2 = app.run_agent(word, chat_id, "telegram")
    chk(f"run_agent({word!r}, PR2 resolver): canonical no-pending",
        reply_pr2 == _CANONICAL_NO_PENDING)
    chk(f"run_agent({word!r}, PR2 resolver): agent_call_count == 0",
        _captured_pr2.get("agent_call_count") == 0)
    chk(f"run_agent({word!r}, PR2 resolver): final_response_count == 1",
        _captured_pr2.get("final_response_count") == 1)
    unrelated_after_pr2 = gw.find_contract(f"hfe-pr2-e2e-{chat_id}")
    chk(f"run_agent({word!r}, PR2 resolver): unrelated historical contract untouched",
        unrelated_after_pr2 is not None and unrelated_after_pr2.status == "completed")


# ══════════════════════════════════════════════════
# 6. Cross-channel canonical identity — telegram vs whatsapp map through the
# same canonical_user_id/memory_key and behave identically.
# ══════════════════════════════════════════════════
print("\n── Cross-channel canonical identity ─────────────────────────────")

_cross_gw = ActionGateway(ledger=ExecutionLedger())
_tg_identity = Identity(user_id="hfe-cross", role=Role.OWNER, channel="telegram", external_id="hfe-cross")
_cross_gw._ledger.save(_historical_contract(
    "hfe-cross-hist", _tg_identity.memory_key, "rejected", age_seconds=20,
))
_wa_identity = Identity(user_id="hfe-cross", role=Role.OWNER, channel="whatsapp", external_id="hfe-cross")
chk("telegram/whatsapp identities for the same user_id share canonical_user_id",
    _tg_identity.memory_key == _wa_identity.memory_key)
_cross_reply = _cross_gw.route_confirmation_word(_wa_identity.memory_key, approver_role="owner")
chk("cross-channel: whatsapp-resolved identity sees the same no-pending answer",
    _cross_reply == _CANONICAL_NO_PENDING)


# ══════════════════════════════════════════════════
# 7. No Session-bookmark authority in the no-pending outcome
# ══════════════════════════════════════════════════
print("\n── No Session-bookmark authority ─────────────────────────────────")

_bm_gw = ActionGateway(ledger=ExecutionLedger())
_bm_gw._ledger.save(_historical_contract("hfe-bm-hist", "boss_hq:hfe-bm", "completed", age_seconds=20))
with patch("session_store.lead_sessions.get_last_prompted_contract", return_value=None):
    _bm_reply = _bm_gw.route_confirmation_word("boss_hq:hfe-bm", approver_role="owner")
chk("no session bookmark + no live + history -> canonical no-pending (bookmark not consulted for outcome)",
    _bm_reply == _CANONICAL_NO_PENDING)


# ══════════════════════════════════════════════════
# 8. "יצרת?" explicit status query — unaffected, still bounded 24h
# ══════════════════════════════════════════════════
print("\n── \"יצרת?\" explicit status query — unaffected ─────────────────")

feature_flags.set_flag("FEATURE_ACTION_GATEWAY", True)
feature_flags.set_flag("FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS", True)
feature_flags.set_flag("FEATURE_SINGLE_SPEAKER_APPROVAL_UX", True)
try:
    _sq_gw = ActionGateway(ledger=ExecutionLedger())
    _sq_identity = Identity(user_id="hfe-sq", role=Role.OWNER)
    _sq_gw._ledger.save(_historical_contract(
        "hfe-sq-hist", _sq_identity.memory_key, "completed", age_seconds=3600,  # 1h old
    ))
    with patch.object(action_gateway_module, "action_gateway", _sq_gw):
        _sq_reply = app._resolve_pr2_deterministic_approval(
            user_text="יצרת?", identity=_sq_identity, live_contracts=[], out_meta={},
        )
    chk("'יצרת?' still answers from bounded 24h history (unaffected by Hotfix E)",
        _sq_reply is not None and _sq_reply != "לא מצאתי פעולה אחרונה ב־24 השעות האחרונות.")
finally:
    feature_flags.set_flag("FEATURE_ACTION_GATEWAY", False)
    feature_flags.set_flag("FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS", False)
    feature_flags.set_flag("FEATURE_SINGLE_SPEAKER_APPROVAL_UX", False)


print(f"\n{'='*50}")
print(f"Hotfix E — shared replay policy: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
