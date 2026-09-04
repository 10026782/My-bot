# test_bug_s2c_cancel_escape.py — BUG-S2C-NO-CANCEL-ESCAPE regression
#
# Production-reported (04/09/2026): once a Commercial Completion (S2C)
# session was parked mid-flow (e.g. the user never answered a "who is this
# deal with?" prompt) and then abandoned, EVERY later message — including an
# unrelated, brand-new "create deal" request — was force-fed into
# answer_human() as a literal answer to the stale question. A fresh command
# obviously isn't a real contact/organization name, so it always failed
# with "לא מצאתי התאמה; נא לנסות שם אחר.", and there was no cancel-word
# escape hatch either: the owner was stuck in an unrecoverable loop with no
# way to text their way out. This verifies the fix — a bare cancel word now
# clears the persisted completion before any restore()/answer_human() call.

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-s2c-cancel-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:S2C_CANCEL_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patS2CCancelTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appS2CCancelTest")
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
    counterparty question, exactly what a user abandoning that prompt would
    leave behind."""
    router = CommercialCompletionRouter(queue=lambda *_: None)
    route = router.start("deal", current_values={
        "name": "עסקת בדיקה", "domain": "import", "owner": "recOwner00000001",
    })
    assert route.outcome == "CLARIFY"
    return serialize_completion_session(route.session)


def _run_agent_with_persisted_completion(user_text: str, chat_id: str, *, answer_human_return=None):
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    session = CommercialCompletionRouter(queue=lambda *_: None).start(
        "deal", current_values={"name": "עסקת בדיקה", "domain": "import", "owner": "recOwner00000001"},
    ).session
    if answer_human_return is None:
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
                       return_value=answer_human_return) as mock_answer_human:
        reply = app.run_agent(user_text, chat_id, channel="telegram")
    return reply, mock_clear, mock_set, mock_answer_human


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

    for cancel_word in ("בטל", "ביטול", "לא", "cancel"):
        reply, mock_clear, mock_set, mock_answer_human = _run_agent_with_persisted_completion(
            cancel_word, f"s2c_cancel_{cancel_word}",
        )
        check(f'cancel word "{cancel_word}" clears the persisted session',
              mock_clear.called)
        check(f'cancel word "{cancel_word}" never reaches answer_human() '
              "(no stale search, no Agent fallback)",
              not mock_answer_human.called)
        check(f'cancel word "{cancel_word}" gets an explicit cancellation reply',
              bool(reply) and "בוטל" in reply)
        check(f'cancel word "{cancel_word}" does not re-persist the cleared session',
              not mock_set.called)

    # Sanity: a real, non-cancel answer to the parked question must still
    # reach answer_human() as before — the cancel check must not swallow
    # everything.
    reply, mock_clear, mock_set, mock_answer_human = _run_agent_with_persisted_completion(
        "ארגון", "s2c_normal_answer",
    )
    check("a normal answer still reaches answer_human() (fix is scoped to cancel words only)",
          mock_answer_human.called)
    check("a normal answer does not spuriously clear the session",
          not mock_clear.called)

    print("=" * 40)
    print(f"S2C cancel-escape regression: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
