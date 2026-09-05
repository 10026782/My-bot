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
from commercial_completion_routing import (  # noqa: E402
    CommercialCompletionRouter, CompletionRoute, serialize_completion_session,
)


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


def _run_agent_with_stale_session(user_text: str, chat_id: str, *, answer_human_return=None):
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
               return_value={"commercial_completion": _parked_deal_session_state()}), \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear, \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch.object(CommercialCompletionRouter, "answer_human",
                       return_value=answer_human_return) as mock_answer_human, \
         patch.object(app, "_queue_deterministic_create_task",
                       return_value="✅ המשימה נוצרה") as mock_create_task:
        reply = app.run_agent(user_text, chat_id, channel="telegram")
    return reply, mock_clear, mock_set, mock_answer_human, mock_create_task


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

    # The exact message from the production transcript.
    user_text = "צור משימה בדיקת דגימות לייבוא סיבים בתחום יבוא"
    reply, mock_clear, mock_set, mock_answer_human, mock_create_task = \
        _run_agent_with_stale_session(user_text, "s2c_stale_create_task")

    check('a fresh "צור משימה ..." command clears the stale S2C session',
          mock_clear.called)
    check('a fresh "צור משימה ..." command never reaches answer_human() '
          "(never treated as a literal field answer)",
          not mock_answer_human.called)
    check('a fresh "צור משימה ..." command does not re-persist the cleared session',
          not mock_set.called)
    check('a fresh "צור משימה ..." command reaches real create_task routing this same turn',
          mock_create_task.called)
    if mock_create_task.called:
        check("the deterministic parser recovered the correct task title",
              mock_create_task.call_args[0][0] == "בדיקת דגימות לייבוא סיבים בתחום יבוא")
    check("the reply reflects the create_task path, not the stale contact-creation offer",
          bool(reply) and "איש קשר" not in reply)

    # Sanity: a genuinely ambiguous free-text reply (a real candidate name,
    # not a structured command) must still reach answer_human() as before —
    # the new escape must not swallow legitimate answers to a pending field.
    reply2, mock_clear2, mock_set2, mock_answer_human2, mock_create_task2 = \
        _run_agent_with_stale_session("ישראל ישראלי", "s2c_stale_normal_answer")
    check("a plausible free-text answer still reaches answer_human()",
          mock_answer_human2.called)
    check("a plausible free-text answer does not spuriously clear the session",
          not mock_clear2.called)
    check("a plausible free-text answer never reaches create_task routing",
          not mock_create_task2.called)

    print("=" * 40)
    print(f"S2C stale-session fresh-command escape regression: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
