# test_bug_s2c_stale_session_fresh_command_escape.py —
# BUG-S2C-STALE-SESSION-SWALLOWS-NEW-COMMAND regression
#
# Production-reported (05/09/2026, live Telegram transcript from the owner):
#
#   Eli:  צור משימה בדיקת דגימות לייבוא סיבים בתחום יבוא
#   BOSS: לא מצאתי את צור משימה בדיקת דגימות לייבוא סיבים בתחום יבוא.
#         ליצור איש קשר חדש?
#   Eli:  פתח משימה בדיקת דגימות בתחום יבוא
#   BOSS: (same "לא מצאתי..." / "ליצור איש קשר חדש?" text, byte-identical)
#
# Root cause: a stale/abandoned Commercial Completion (S2C) session was
# parked in session_store from an earlier, unrelated Deal/Organization flow.
# app.py's S2C resume block (run_agent(), section "1.7") runs BEFORE
# _safe_route()/create_task routing and force-feeds the ENTIRE incoming
# text into CommercialCompletionRouter.answer_human() as a literal answer
# to whatever field the stale session was parked on. BUG-S2C-NO-CANCEL-
# ESCAPE (04/09/2026) already fixed this for an explicit cancel word, but
# "צור משימה ..." is not a cancel word — it is a perfectly well-formed NEW
# command that was never given a chance to reach create_task routing at
# all. Worse, since the DIAMOND PATH confirm-to-create feature, the
# resulting no-match now offers "ליצור איש קשר חדש?" and traps any
# non-[כן]/[לא] reply in a loop that re-renders the exact same stale text
# forever (the second turn above) — there was no escape hatch for this at
# any level.
#
# Fix: before falling into answer_human(), also check whether the text
# deterministically parses as one of the same structured commands this
# exact function already special-cases below it (create_task, create_deal,
# or an S2C completion entity prefix) — using the same pure, already-tested
# parsers (parse_deterministic_create_task/_create_deal/
# _commercial_completion). A match is unambiguously a NEW command, never a
# plausible answer to a pending field: clear the stale completion and fall
# through to normal routing this same turn, exactly generalizing the
# cancel-word escape to a second, precise (never heuristic) trigger.
#
# This file covers the full acceptance matrix (owner-specified, 05/09/2026):
#   1. exact production case: stale completion + "צור משימה..."
#      -> no Contact/Organization lookup -> task routes normally
#   2. stale completion + new Deal -> old completion cleared -> new Deal starts
#   3. stale completion + normal field answer -> completion still resumes
#   4. stale CREATE_CONFIRM + "כן"/"לא" -> confirm/decline still works
#   5. stale CREATE_CONFIRM + fresh command -> confirm state cleared,
#      fresh command routes
#   6. no Agent fallback for recognized deterministic commands
#   7. exactly one final response
#   8. persisted commercial_completion is actually cleared, not only
#      bypassed for the current turn

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-s2c-stale-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:S2C_STALE_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patS2CStaleTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appS2CStaleTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from identity import Identity, Role  # noqa: E402
import session_store  # noqa: E402
from airtable_schema import CommercialStatus, Currency, DealType, RelationshipType  # noqa: E402
from commercial_completion_routing import (  # noqa: E402
    CommercialCompletionRouter, CompletionRoute, serialize_completion_session,
)

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


def _deal_needing_counterparty() -> dict:
    return {
        "name": "עסקת בדיקה", "domain": "import", "owner": "recOwner00000001",
        "deal_type": DealType.SERVICE, "relationship_type": RelationshipType.ONE_OFF,
        "currency": Currency.ILS, "commercial_status": CommercialStatus.PROSPECT,
        "expected_value": 100,
    }


def _parked_deal_session_state() -> dict:
    """A realistic persisted S2C state: a "create deal" flow parked on the
    counterparty question, exactly what an abandoned/stale flow would leave
    behind — the same fixture BUG-S2C-NO-CANCEL-ESCAPE's own test uses."""
    router = CommercialCompletionRouter(queue=lambda *_: None)
    route = router.start("deal", current_values={
        "name": "עסקת בדיקה", "domain": "import", "owner": "recOwner00000001",
    })
    assert route.outcome == "CLARIFY"
    return serialize_completion_session(route.session)


def _parked_create_confirm_state() -> dict:
    """The exact persisted shape the production transcript's turn 1 produces:
    a Deal parked on counterparty_contact, no match found for a name, the
    DIAMOND PATH confirm-to-create offer pending (_ux_pending_nested_create
    marker set, still ONE frame -- begin_nested() is deliberately deferred
    until the user confirms)."""
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal_needing_counterparty())
    assert first.outcome == "CLARIFY"
    offer = router.answer_human(
        first.session, "יאיר ממן", link_lookup=lambda *_: [], scope="tenant1",
    )
    assert offer.outcome == "CLARIFY"
    assert offer.choices == ("כן", "לא")
    return serialize_completion_session(offer.session)


def _run_agent_with_stale_session(
    user_text: str, chat_id: str, *,
    persisted_state_factory=_parked_deal_session_state,
    answer_human_return=None,
    mock_answer_human=True,
):
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    if answer_human_return is None:
        session = CommercialCompletionRouter(queue=lambda *_: None).start(
            "deal", current_values={"name": "עסקת בדיקה", "domain": "import", "owner": "recOwner00000001"},
        ).session
        answer_human_return = CompletionRoute(
            "CLARIFY", "deal", session=session, field_name="deal_type",
            prompt="מה סוג העסקה?",
        )
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch("session_store.lead_sessions.get",
               return_value={"commercial_completion": persisted_state_factory()}), \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear, \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch.object(app, "_queue_deterministic_create_task",
                       return_value="✅ המשימה נוצרה") as mock_create_task, \
         patch.object(app.client.messages, "create") as mock_agent_call:
        if mock_answer_human:
            with patch.object(CommercialCompletionRouter, "answer_human",
                               return_value=answer_human_return) as mock_ah:
                reply = app.run_agent(user_text, chat_id, channel="telegram")
                return reply, mock_clear, mock_set, mock_ah, mock_create_task, mock_agent_call
        reply = app.run_agent(user_text, chat_id, channel="telegram")
    return reply, mock_clear, mock_set, None, mock_create_task, mock_agent_call


def test_1_exact_production_case():
    """1. exact production case: stale completion + "צור משימה..."
    -> no Contact/Organization lookup -> task routes normally."""
    user_text = "צור משימה בדיקת דגימות לייבוא סיבים בתחום יבוא"
    reply, mock_clear, mock_set, mock_answer_human, mock_create_task, mock_agent_call = \
        _run_agent_with_stale_session(user_text, "s2c_stale_create_task")

    check('1. "צור משימה ..." clears the stale S2C session', mock_clear.called)
    check('1. "צור משימה ..." never performs a Contact/Organization lookup '
          "(answer_human() is never reached)", not mock_answer_human.called)
    check('1. "צור משימה ..." does not re-persist the cleared session', not mock_set.called)
    check('1. "צור משימה ..." reaches real create_task routing this same turn',
          mock_create_task.called)
    if mock_create_task.called:
        check("1. the deterministic parser recovered the correct task title",
              mock_create_task.call_args[0][0] == "בדיקת דגימות לייבוא סיבים בתחום יבוא")
    check("1. the reply reflects the create_task path, not the stale contact-creation offer",
          bool(reply) and "איש קשר" not in reply)


def test_2_stale_completion_plus_new_deal():
    """2. stale completion + new Deal -> old completion cleared -> new Deal starts."""
    user_text = "צור עסקה בשם עסקה חדשה בתחום יבוא"
    identity = Identity(user_id="s2c_stale_new_deal", role=Role.OWNER)
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch("session_store.lead_sessions.get",
               return_value={"commercial_completion": _parked_deal_session_state()}), \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear, \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch.object(CommercialCompletionRouter, "answer_human") as mock_answer_human, \
         patch.object(app.client.messages, "create") as mock_agent_call:
        reply = app.run_agent(user_text, "s2c_stale_new_deal", channel="telegram")

    check("2. new Deal command clears the old stale completion", mock_clear.called)
    check("2. new Deal command never reaches the stale session's answer_human()",
          not mock_answer_human.called)
    check("2. a brand-new Deal completion session is started and persisted",
          mock_set.called)
    if mock_set.called:
        new_state = mock_set.call_args[0][1]
        from commercial_completion_routing import deserialize_completion_session
        restored = deserialize_completion_session(new_state)
        check("2. the new session starts completely fresh (single root frame, deal entity)",
              len(restored.frames) == 1 and restored.active.target_entity == "deal")
        check("2. the new session carries the freshly-parsed deal name, not the stale deal's",
              restored.active.current_values.get("name") == "עסקה חדשה")
    check("2. no Agent fallback was used to start the new Deal", not mock_agent_call.called)
    # NOTE: the new Deal's own first question ("עם מי העסקה? אפשרויות: איש
    # קשר / ארגון") legitimately mentions "איש קשר" as a valid counterparty-
    # kind choice -- that substring is not itself evidence of the stale bug.
    # The actual regression symptom is the specific "לא מצאתי" no-match text.
    check("2. the reply is a legitimate Deal-creation prompt, not the stale no-match text",
          bool(reply) and "לא מצאתי" not in reply)


def test_3_stale_completion_plus_normal_answer():
    """3. stale completion + normal field answer -> completion still resumes."""
    reply, mock_clear, mock_set, mock_answer_human, mock_create_task, mock_agent_call = \
        _run_agent_with_stale_session("ישראל ישראלי", "s2c_stale_normal_answer")

    check("3. a plausible free-text answer still reaches answer_human()",
          mock_answer_human.called)
    check("3. a plausible free-text answer does not spuriously clear the session",
          not mock_clear.called)
    check("3. a plausible free-text answer never reaches create_task routing",
          not mock_create_task.called)


def test_4_create_confirm_still_works():
    """4. stale CREATE_CONFIRM + "כן"/"לא" -> confirm/decline still works."""
    from commercial_completion_routing import deserialize_completion_session

    for choice, expect_nested in (("כן", True), ("לא", False)):
        chat_id = f"s2c_confirm_{choice}"
        identity = Identity(user_id=chat_id, role=Role.OWNER)
        with patch.object(app, "resolve_identity", return_value=identity), \
             patch("session_store.lead_sessions.get",
                   return_value={"commercial_completion": _parked_create_confirm_state()}), \
             patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear, \
             patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
             patch.object(app, "_queue_deterministic_create_task") as mock_create_task, \
             patch.object(app.client.messages, "create") as mock_agent_call:
            reply = app.run_agent(choice, chat_id, channel="telegram")

        check(f'4. "{choice}" never triggers the fresh-command escape (session not cleared)',
              not mock_clear.called)
        check(f'4. "{choice}" never reaches create_task routing', not mock_create_task.called)
        check(f'4. "{choice}" never falls back to the Agent', not mock_agent_call.called)
        check(f'4. "{choice}" re-persists the (correctly advanced) session', mock_set.called)
        if mock_set.called:
            new_state = mock_set.call_args[0][1]
            restored = deserialize_completion_session(new_state)
            has_nested = len(restored.frames) > 1
            check(f'4. "{choice}" {"begins" if expect_nested else "does not begin"} '
                  "a nested Contact completion", has_nested == expect_nested)
        check(f'4. "{choice}" reply never repeats the stale confirm question verbatim',
              bool(reply) and reply != "לא מצאתי את יאיר ממן. ליצור איש קשר חדש?")


def test_5_create_confirm_plus_fresh_command():
    """5. stale CREATE_CONFIRM + fresh command -> confirm state cleared,
    fresh command routes."""
    user_text = "צור משימה בדיקת דגימות בתחום יבוא"
    reply, mock_clear, mock_set, mock_answer_human, mock_create_task, mock_agent_call = \
        _run_agent_with_stale_session(
            user_text, "s2c_confirm_fresh_command",
            persisted_state_factory=_parked_create_confirm_state,
        )

    check("5. a fresh command clears the pending CREATE_CONFIRM state",
          mock_clear.called)
    check("5. a fresh command never re-renders the stale confirm question "
          "(answer_human() never reached)", not mock_answer_human.called)
    check("5. a fresh command does not re-persist the cleared confirm state",
          not mock_set.called)
    check("5. a fresh command reaches real create_task routing this same turn",
          mock_create_task.called)
    check("5. the reply is the task-creation outcome, not the repeated confirm question",
          bool(reply) and "ליצור איש קשר חדש" not in reply)


def test_6_no_agent_fallback():
    """6. no Agent fallback for recognized deterministic commands."""
    for user_text, label in (
        ("צור משימה בדיקת דגימות לייבוא סיבים בתחום יבוא", "create_task"),
        ("צור עסקה בשם עסקה חדשה בתחום יבוא", "create_deal"),
    ):
        identity = Identity(user_id=f"s2c_no_agent_{label}", role=Role.OWNER)
        with patch.object(app, "resolve_identity", return_value=identity), \
             patch("session_store.lead_sessions.get",
                   return_value={"commercial_completion": _parked_deal_session_state()}), \
             patch("session_store.lead_sessions.clear_commercial_completion"), \
             patch("session_store.lead_sessions.set_commercial_completion"), \
             patch.object(app, "_queue_deterministic_create_task", return_value="✅ המשימה נוצרה"), \
             patch.object(app.client.messages, "create") as mock_agent_call:
            app.run_agent(user_text, f"s2c_no_agent_{label}", channel="telegram")
        check(f"6. {label} never invokes the Anthropic Agent loop", not mock_agent_call.called)


def test_7_exactly_one_final_response():
    """7. exactly one final response."""
    reply, *_ = _run_agent_with_stale_session(
        "צור משימה בדיקת דגימות לייבוא סיבים בתחום יבוא", "s2c_one_response",
    )
    check("7. run_agent() returns exactly one non-empty reply string",
          isinstance(reply, str) and bool(reply))
    check("7. the reply is exactly the create_task outcome, nothing concatenated/prepended",
          reply == "✅ המשימה נוצרה")


def test_8_persisted_completion_actually_cleared():
    """8. persisted commercial_completion is actually cleared, not only
    bypassed for the current turn -- verified against the REAL
    PersistentSessionStore (network layer mocked, RAM cache real), not a
    mock of clear_commercial_completion itself."""
    chat_id = "s2c_really_cleared"
    identity = Identity(user_id=chat_id, role=Role.OWNER)

    # Seed the real RAM cache directly, exactly as a genuine parked session
    # would sit after a restart-restore -- no clear_commercial_completion()
    # mock this time, the real store method runs for real.
    key = session_store._canonical_session_key("telegram", chat_id)
    session_store.lead_sessions._store[key] = {
        "sender": chat_id, "channel": "telegram",
        "commercial_completion": _parked_deal_session_state(),
    }
    try:
        with patch.object(app, "resolve_identity", return_value=identity), \
             patch.object(session_store.PersistentSessionStore, "_sync_to_db", return_value=True), \
             patch.object(session_store.PersistentSessionStore, "_load_from_db", return_value=None), \
             patch.object(CommercialCompletionRouter, "answer_human") as mock_answer_human, \
             patch.object(app, "_queue_deterministic_create_task", return_value="✅ המשימה נוצרה"), \
             patch.object(app.client.messages, "create"):
            app.run_agent(
                "צור משימה בדיקת דגימות לייבוא סיבים בתחום יבוא", chat_id, channel="telegram",
            )
        check("8. answer_human() was never reached", not mock_answer_human.called)
        still_there = session_store.lead_sessions.get_commercial_completion(chat_id, channel="telegram")
        check("8. the REAL store's commercial_completion is genuinely gone afterward "
              "(not just bypassed for this turn)", still_there is None)
    finally:
        session_store.lead_sessions._store.pop(key, None)


def run():
    test_1_exact_production_case()
    test_2_stale_completion_plus_new_deal()
    test_3_stale_completion_plus_normal_answer()
    test_4_create_confirm_still_works()
    test_5_create_confirm_plus_fresh_command()
    test_6_no_agent_fallback()
    test_7_exactly_one_final_response()
    test_8_persisted_completion_actually_cleared()

    print("=" * 40)
    print(f"S2C stale-session fresh-command escape regression: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
