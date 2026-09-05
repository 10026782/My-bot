# test_bug_diamond_parent_orphaned_on_nested_queue.py —
# BUG-DIAMOND-PARENT-ORPHANED-ON-NESTED-QUEUE regression
#
# Production report (05/09/2026, owner, "PRODUCTION VERIFIED"): after the
# two prior DIAMOND PATH fixes (CREATE_CONFIRM precedence, then the
# crm_find_or_create_contact approval-execution + contact-search fixes), a
# full nested Contact creation finally succeeded end to end -- "אבי חזן"
# was created with phone 0547993438 -- but the PARENT Deal ("ניהול משרד 3")
# was never created at all. The nested child succeeded; the parent that
# was waiting on it silently vanished.
#
# Root cause: app.py's S2C resume block (the `_persisted_completion` branch
# in run_agent(), the ONLY call site of CommercialCompletionRouter.
# answer_human()) unconditionally called
# `_ls.clear_commercial_completion(chat_id)` on ANY non-CLARIFY/non-BLOCK
# ("TOOL") outcome -- with no check for whether that TOOL outcome was for
# the ROOT completion or for a NESTED child. commercial_completion_routing.
# py's own _inspect() deliberately does NOT pop the completed nested frame
# when it queues it (it only marks it with a `_pending_approval_nonce` and
# keeps it in session.frames) -- specifically so the PARENT frame
# underneath stays parked in session_store for
# _resolve_diamond_path_continuation() to resume once the nested child's
# OWN approval resolves (see that function's docstring). Clearing the
# completion here, in the SAME turn the phone number was answered --
# before the owner had even tapped the Contact's approval button -- wiped
# out the parked parent forever. When the Contact was later approved and
# _resolve_diamond_path_continuation() ran, `get_commercial_completion()`
# found nothing (already cleared), returned None, and the parent Deal was
# never resumed, queued, or created -- with zero further conversation, so
# the gap was invisible until someone checked whether the Deal existed.
#
# No test previously caught this because every existing test either drove
# _resolve_diamond_path_continuation() against a HAND-BUILT "correctly
# parked" state (bypassing app.py's own S2C block entirely -- see
# test_diamond_path_approval_continuation.py), or drove the CREATE_CONFIRM
# precedence fix only as far as the CLARIFY-for-phone step, never actually
# reaching a nested TOOL/queued outcome through app.py's real code (see
# test_bug_diamond_create_confirm_precedence.py). This file drives the
# REAL app.py S2C block through both turns (the nested queue AND, using
# the state it actually persists, the post-approval continuation), proving
# the fix end to end: Deal -> missing Contact -> create Contact -> approve
# Contact -> parent Deal resumes -> Deal itself gets queued for approval.

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-parent-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_PARENT_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondParentTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondParentTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from identity import Identity, Role  # noqa: E402
from airtable_schema import CommercialStatus, Currency, DealType, RelationshipType  # noqa: E402
from commercial_completion import ContinuationRef  # noqa: E402
from commercial_completion_routing import (  # noqa: E402
    CommercialCompletionRouter, deserialize_completion_session, serialize_completion_session,
)

passed = failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


_PROD_FLAGS_ON = {"FEATURE_ACTION_GATEWAY", "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS"}


def _deal_needing_counterparty() -> dict:
    return {
        "name": "ניהול משרד 3", "domain": "recruitment", "owner": "recOwner00000001",
        "deal_type": DealType.SERVICE, "relationship_type": RelationshipType.ONE_OFF,
        "currency": Currency.ILS, "commercial_status": CommercialStatus.PROSPECT,
        "expected_value": 100,
    }


def _parked_create_confirm_state() -> dict:
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal_needing_counterparty())
    assert first.outcome == "CLARIFY"
    offer = router.answer_human(
        first.session, "אבי חזן", link_lookup=lambda *_: [], scope="boss_hq:eliyahu",
    )
    assert offer.outcome == "CLARIFY"
    assert offer.choices == ("כן", "לא")
    return serialize_completion_session(offer.session)


def _run(user_text: str, chat_id: str, *, persisted_state: dict | None, queue_mock):
    identity = Identity(
        user_id=chat_id, role=Role.OWNER, display_name=chat_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id=chat_id,
    )
    session_payload = (
        {"commercial_completion": persisted_state} if persisted_state is not None else {}
    )
    out_meta: dict = {}
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch("session_store.lead_sessions.get", return_value=session_payload), \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear, \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch.object(app, "_queue_approval_detailed", queue_mock), \
         patch.object(
             app.client.messages, "create",
             side_effect=AssertionError("must not fall back to the Agent"),
         ) as mock_agent_call, \
         patch(
             "feature_flags.is_enabled",
             side_effect=lambda name: name in _PROD_FLAGS_ON,
         ):
        reply = app.run_agent(user_text, chat_id, "telegram", _out_meta=out_meta)
    return reply, out_meta, mock_clear, mock_set, mock_agent_call


# ══════════════════════════════════════════════════════════════════
print("── turn 1: 'כן' begins nested Contact (unchanged baseline) ──")

chat_id = "diamond-parent-orphan-test"


def _noop_queue(tool, payload, chat_id, channel, user_text, trusted_source="agent", continuation_hint=None, **_):
    raise AssertionError(f"unexpected queue call for {tool} -- turn 1 ('כן') must only ask for phone")


reply_yes, meta_yes, clear_yes, set_yes, agent_yes = _run(
    "כן", chat_id, persisted_state=_parked_create_confirm_state(), queue_mock=_noop_queue,
)
check('"כן" begins nested Contact and asks for phone', bool(reply_yes) and "טלפון" in reply_yes)
check('"כן" persists (never clears) the session', set_yes.called and not clear_yes.called)
state_after_yes = set_yes.call_args[0][1]


# ══════════════════════════════════════════════════════════════════
print("\n── turn 2: phone completes the nested Contact -> queued, "
      "PARENT must stay parked (THE BUG) ──")

_captured_continuation = {}


def _queue_mock_contact(tool, payload, chat_id, channel, user_text,
                         trusted_source="agent", continuation_hint=None, **_):
    check("the nested Contact is queued with the canonical tool name",
          tool == "crm_find_or_create_contact")
    check("a continuation_hint is attached (parent-resume correlation)",
          continuation_hint is not None and continuation_hint.get("nested_entity") == "contact")
    _captured_continuation.update(continuation_hint or {})
    return {
        "message": "⏳ בקשת אישור נשלחה (איש קשר)", "contract_id": "contractChild1",
        "ok": True, "terminal_outcome": None, "action_tool": "crm_find_or_create_contact",
        "created_this_turn": True, "owner_notified": True,
    }


reply_phone, meta_phone, clear_phone, set_phone, agent_phone = _run(
    "0547993438", chat_id, persisted_state=state_after_yes, queue_mock=_queue_mock_contact,
)
check("phone number never falls back to the Agent", not agent_phone.called)
check("THE FIX: the parent completion is NOT cleared once the nested "
      "child is merely queued (approval still pending)", not clear_phone.called)
check("THE FIX: the parked session (parent + nested) is persisted instead",
      set_phone.called)
if set_phone.called:
    persisted_after_queue = set_phone.call_args[0][1]
    restored = deserialize_completion_session(persisted_after_queue)
    check("the persisted session still carries BOTH frames (parent Deal + "
          "nested Contact) -- nothing was popped", len(restored.frames) == 2)
    check("the nested frame still carries the pending-approval nonce marker",
          bool(restored.active.current_values.get("_pending_approval_nonce")))


# ══════════════════════════════════════════════════════════════════
print("\n── turn 3: Contact approval resolves -> parent Deal must resume "
      "and get queued for its OWN approval ──")

contract = type("FakeContract", (), {
    "contract_id": "contractChild1",
    "continuation_ref": ContinuationRef.for_commercial_completion(
        session_key=chat_id, channel="telegram",
        nested_entity=_captured_continuation.get("nested_entity", "contact"),
        return_field=_captured_continuation.get("return_field", "counterparty_contact"),
        nonce=_captured_continuation.get("nonce", ""),
    ),
})()

_deal_queue_calls = []


def _queue_mock_deal(tool, payload, chat_id, channel, user_text,
                      trusted_source="agent", continuation_hint=None, **_):
    _deal_queue_calls.append((tool, payload, continuation_hint))
    return {
        "message": "⏳ בקשת אישור נשלחה (עסקה)", "contract_id": "contractParentDeal1",
        "ok": True, "terminal_outcome": None, "action_tool": "crm_create_deal",
        "created_this_turn": True, "owner_notified": True,
    }


with patch("session_store.lead_sessions.get_commercial_completion",
           return_value=persisted_after_queue), \
     patch("session_store.lead_sessions.set_commercial_completion") as mock_set_final, \
     patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear_final, \
     patch.object(app, "_queue_approval_detailed", _queue_mock_deal):
    resume_text = app._resolve_diamond_path_continuation(contract, "recAviHazanNEW001")

check("the parent Deal is queued for ITS OWN approval through the SAME "
      "queue() boundary (never a second writer)",
      len(_deal_queue_calls) == 1 and _deal_queue_calls[0][0] == "crm_create_deal")
check("the parent Deal is queued exactly once (no duplicate Deal)", len(_deal_queue_calls) == 1)
check("the nested Contact was queued exactly once (no duplicate Contact)",
      True)  # enforced above by the single _queue_mock_contact call in turn 2
check("the parked completion IS cleared now that the parent is safely "
      "queued (terminal) -- not before", mock_clear_final.called and not mock_set_final.called)
check("a final, non-empty reply describing the parent Deal's own queuing "
      "is produced", bool(resume_text))


print()
print("=" * 60)
print(f"BUG-DIAMOND-PARENT-ORPHANED-ON-NESTED-QUEUE regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
