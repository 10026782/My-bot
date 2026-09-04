# test_diamond_path_approval_continuation.py — DIAMOND PATH nested-entity
# approval continuation regression (app.py's _resolve_diamond_path_continuation()).
#
# Production bug (04/09/2026 transcript): mid Deal-completion, a Contact
# no-match answer ("יאיר ממן") dead-ended with "לא מצאתי התאמה; נא לנסות שם
# אחר." and no path forward. The full fix spans commercial_completion.py
# (ContinuationRef, abandon_nested), commercial_completion_ux.py/
# commercial_completion_routing.py (confirm-to-create, deferred begin_nested,
# resume_nested — see tests/test_commercial_completion_routing.py and
# tests/test_commercial_completion_runtime_integration.py for those layers),
# core/action_gateway.py + core/action_contract_repository.py (continuation_ref
# persisted on the ActionContract itself), and app.py's approval callback,
# which this file exercises: after a nested create's approval executes,
# _resolve_diamond_path_continuation() reloads the parked parent
# CompletionSession, correlates it against the contract's continuation_ref,
# and either resumes+continues inspection or cleans up an orphaned frame --
# never a second writer, never a duplicate final reply, never an orphaned
# parent session left parked forever.

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-path-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_PATH_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondPathTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondPathTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

from airtable_schema import CommercialStatus, Currency, DealType, RelationshipType  # noqa: E402
from commercial_completion import ContinuationRef  # noqa: E402
from commercial_completion_routing import (  # noqa: E402
    CommercialCompletionRouter, serialize_completion_session,
)


def _deal_needing_counterparty():
    return {
        "name": "Deal", "domain": "import", "owner": "recOwner1",
        "deal_type": DealType.SERVICE,
        "relationship_type": RelationshipType.ONE_OFF, "currency": Currency.ILS,
        "commercial_status": CommercialStatus.PROSPECT, "expected_value": 100,
    }


def _deal_needing_counterparty_and_status():
    values = _deal_needing_counterparty()
    values.pop("commercial_status")
    return values


def _queued_nested_contact(deal_values):
    """Drive a real "no match -> כן -> nested Contact complete -> queued"
    sequence, exactly like the production transcript, and return
    (state_dict, nonce) for the parked session as app.py would persist it."""
    calls = []
    router = CommercialCompletionRouter(
        queue=lambda tool, payload, continuation=None: calls.append((tool, payload, continuation)) or None
    )
    first = router.start("deal", current_values=deal_values)
    offer = router.answer_human(
        first.session, "יאיר ממן", link_lookup=lambda *_: [], scope="tenant1",
    )
    ask_phone = router.answer_human(offer.session, "כן", link_lookup=None, scope="")
    queued = router.answer(ask_phone.session, "phone", "0501234567")
    assert queued.outcome == "TOOL"
    _, _, continuation = calls[0]
    return serialize_completion_session(queued.session), continuation["nonce"]


def _contract(continuation_ref=None, contract_id="contractDP1"):
    return SimpleNamespace(contract_id=contract_id, continuation_ref=continuation_ref)


def run():
    passed = failed = 0

    def check(label, condition):
        nonlocal passed, failed
        if condition:
            print(f"✅ {label}")
            passed += 1
        else:
            print(f"❌ {label}")
            failed += 1

    # 1. No continuation_ref at all — the overwhelming common case.
    with patch("session_store.lead_sessions.get_commercial_completion") as mock_get:
        result = app._resolve_diamond_path_continuation(_contract(None), "recX")
    check("no continuation_ref -> returns None", result is None)
    check("no continuation_ref -> never touches session_store", not mock_get.called)

    ref = ContinuationRef.for_commercial_completion(
        session_key="7228089151", channel="telegram",
        nested_entity="contact", return_field="counterparty_contact", nonce="",
    )

    # 2. continuation_ref present, but nothing parked (already resolved/cleared).
    with patch("session_store.lead_sessions.get_commercial_completion", return_value=None) as mock_get, \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear:
        result = app._resolve_diamond_path_continuation(_contract(ref), "recX")
    check("nothing parked -> returns None", result is None)
    check("nothing parked -> never writes back", not mock_set.called and not mock_clear.called)

    state, nonce = _queued_nested_contact(_deal_needing_counterparty_and_status())

    # 3. Correlated session exists, but the contract's nonce doesn't match
    #    (a different/newer continuation now occupies this slot) -- must
    #    fail closed and NEVER touch session_store.
    mismatched_ref = ContinuationRef.for_commercial_completion(
        session_key="7228089151", channel="telegram",
        nested_entity="contact", return_field="counterparty_contact",
        nonce=nonce + "-stale",
    )
    with patch("session_store.lead_sessions.get_commercial_completion", return_value=state) as mock_get, \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear:
        result = app._resolve_diamond_path_continuation(_contract(mismatched_ref), "recX")
    check("nonce mismatch -> returns None", result is None)
    check("nonce mismatch -> never mutates the (unrelated) parked session",
          not mock_set.called and not mock_clear.called)

    correlated_ref = ContinuationRef.for_commercial_completion(
        session_key="7228089151", channel="telegram",
        nested_entity="contact", return_field="counterparty_contact", nonce=nonce,
    )

    # 4. Correlated, but no evidence record id (rejected approval, or a
    #    successful execution with no verified evidence) -- must clean up
    #    (abandon_nested + persist), never leave the frame parked forever.
    with patch("session_store.lead_sessions.get_commercial_completion", return_value=state), \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear:
        result = app._resolve_diamond_path_continuation(_contract(correlated_ref), "")
    check("no evidence -> returns None (nothing extra to say)", result is None)
    check("no evidence -> cleans up the parked frame via set_commercial_completion",
          mock_set.called and not mock_clear.called)
    if mock_set.called:
        _, written_state = mock_set.call_args[0]
        check("cleanup persists a session with the nested frame popped (1 frame)",
              len(written_state.get("frames", [])) == 1)

    # 5. Correlated, real evidence record id, parent still needs another
    #    field (CLARIFY) -- must persist the resumed session and surface
    #    the next prompt as the ONE extra piece of text.
    with patch("session_store.lead_sessions.get_commercial_completion", return_value=state), \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear, \
         patch.object(app, "_queue_approval_detailed") as mock_queue_unused:
        result = app._resolve_diamond_path_continuation(_contract(correlated_ref), "recContactNEW001")
    check("resumed with evidence -> non-empty follow-up text", bool(result))
    check("resumed with evidence -> persists the resumed session, never clears it",
          mock_set.called and not mock_clear.called)
    check("resumed to CLARIFY -> the parent's own approval is never queued yet",
          not mock_queue_unused.called)

    # 6. Same, but folding the record id completes the PARENT deal too --
    #    it gets queued for its OWN approval through the SAME queue()
    #    boundary (never a second writer), and the parked completion is
    #    cleared (terminal), not re-persisted.
    complete_state, complete_nonce = _queued_nested_contact(_deal_needing_counterparty())
    complete_ref = ContinuationRef.for_commercial_completion(
        session_key="7228089151", channel="telegram",
        nested_entity="contact", return_field="counterparty_contact", nonce=complete_nonce,
    )
    with patch("session_store.lead_sessions.get_commercial_completion", return_value=complete_state), \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear, \
         patch.object(app, "_queue_approval_detailed", return_value={
             "message": "⏳ בקשת אישור נשלחה", "contract_id": "contractParent1",
             "ok": True, "terminal_outcome": None, "action_tool": "crm_create_deal",
             "created_this_turn": True, "owner_notified": True,
         }) as mock_queue:
        result = app._resolve_diamond_path_continuation(_contract(complete_ref), "recContactNEW001")
    check("parent auto-completes -> the SAME queue() boundary is used for its own approval",
          mock_queue.called and mock_queue.call_args[0][0] == "crm_create_deal")
    check("parent auto-completes -> parked completion is cleared, not re-persisted",
          mock_clear.called and not mock_set.called)

    print("=" * 50)
    print(f"DIAMOND PATH approval-continuation regression: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
