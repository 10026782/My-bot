# test_bug070_pending_approval_multi.py — BUG-070 (gap #2 of 3)
#
# app.py's _pending_approvals used to be dict[chat_id -> single entry]: a
# second Handler.APPROVAL-routed message for the same chat_id silently
# overwrote the first pending action, with no way to target either one
# individually. Fix: _pending_approvals is now dict[chat_id -> {approval_id:
# entry}], each entry carrying a display_index (1, 2, ...), with
# _add_pending_approval()/_resolve_pending_reply()/_pop_pending_approval()
# as the real (not reimplemented) helpers exercised below.
#
# These tests call the actual app.py functions directly — not a
# reimplementation — to avoid logic drift between the test and production
# code. The "which action word was this" classification block itself lives
# inside run_agent()'s Pending Approval Gate (too heavy to invoke directly:
# full Identity/Router/Agent pipeline), so _classify() below is a thin,
# explicitly-labeled mirror of exactly that block (app.py, "2.5 Pending
# Approval Gate") — kept in sync by hand, not by import, since the real
# block only runs inside run_agent().
#
# Regression this file guards against specifically: a bare digit (e.g. "1")
# must NOT be treated as an implicit approval-confirm when only one item is
# pending — that would silently execute a pending action (e.g. "send this
# email") in response to a completely unrelated numeric reply (a quantity,
# a price, a day-of-month) elsewhere in the conversation. Bare-digit
# selection is only meaningful once there are 2+ queued items and the bot
# has shown the user a numbered list to disambiguate.

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug070-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG070_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug070Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug070Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)


def _classify(bucket: dict, user_text: str):
    """Mirrors app.py's run_agent() '2.5 Pending Approval Gate' classification
    (first_token vs _CONFIRM_WORDS/_CANCEL_WORDS, then the len(bucket)>1-gated
    bare-digit branch) — see app.py for the authoritative version."""
    stripped = user_text.strip()
    lower = stripped.lower()
    first_token = lower.split()[0] if lower.split() else ""
    if first_token in app._CONFIRM_WORDS:
        return "confirm"
    if first_token in app._CANCEL_WORDS:
        return "cancel"
    if len(bucket) > 1 and re.fullmatch(r"\d+", stripped):
        return "confirm"
    return None


def test_second_pending_does_not_overwrite_first():
    chat_id = "bug070_t1"
    app._pending_approvals.pop(chat_id, None)
    id1 = app._add_pending_approval(chat_id, {"text": "פעולה א", "created_at": time.time()})
    id2 = app._add_pending_approval(chat_id, {"text": "פעולה ב", "created_at": time.time()})

    assert len(app._pending_approvals[chat_id]) == 2, "second pending must not overwrite the first"
    assert app._pending_approvals[chat_id][id1]["text"] == "פעולה א"
    assert app._pending_approvals[chat_id][id2]["text"] == "פעולה ב"


def test_numbered_reply_targets_specific_item():
    chat_id = "bug070_t2"
    app._pending_approvals.pop(chat_id, None)
    app._add_pending_approval(chat_id, {"text": "פעולה א", "created_at": time.time()})
    app._add_pending_approval(chat_id, {"text": "פעולה ב", "created_at": time.time()})

    bucket = app._pending_approvals[chat_id]
    action = _classify(bucket, "כן 2")
    resolved = app._resolve_pending_reply(chat_id, "כן 2")

    assert action == "confirm"
    assert resolved is not None
    approval_id, entry = resolved
    assert entry["text"] == "פעולה ב"
    app._pop_pending_approval(chat_id, approval_id)
    assert len(app._pending_approvals.get(chat_id, {})) == 1, "only the targeted item is removed"


def test_cancel_specific_item_leaves_others_pending():
    chat_id = "bug070_t3"
    app._pending_approvals.pop(chat_id, None)
    app._add_pending_approval(chat_id, {"text": "השאר", "created_at": time.time()})
    app._add_pending_approval(chat_id, {"text": "לבטל", "created_at": time.time()})

    bucket = app._pending_approvals[chat_id]
    action = _classify(bucket, "לא 2")
    resolved = app._resolve_pending_reply(chat_id, "לא 2")

    assert action == "cancel"
    approval_id, entry = resolved
    assert entry["text"] == "לבטל"
    app._pop_pending_approval(chat_id, approval_id)
    remaining = app._pending_approvals.get(chat_id, {})
    assert len(remaining) == 1
    assert next(iter(remaining.values()))["text"] == "השאר"


def test_ambiguous_reply_with_no_number_does_not_guess():
    chat_id = "bug070_t4"
    app._pending_approvals.pop(chat_id, None)
    app._add_pending_approval(chat_id, {"text": "פעולה ג", "created_at": time.time()})
    app._add_pending_approval(chat_id, {"text": "פעולה ד", "created_at": time.time()})

    bucket = app._pending_approvals[chat_id]
    action = _classify(bucket, "כן")
    resolved = app._resolve_pending_reply(chat_id, "כן")

    assert action == "confirm"
    assert resolved is None, "must not silently guess which of 2+ pending items to confirm"
    assert len(app._pending_approvals[chat_id]) == 2, "nothing is popped on an ambiguous reply"


def test_single_pending_bare_confirm_word_still_works():
    """Backward compatibility: bare 'כן'/'לא' with exactly one pending item
    resolves that item, same as before BUG-070."""
    chat_id = "bug070_t5"
    app._pending_approvals.pop(chat_id, None)
    app._add_pending_approval(chat_id, {"text": "פעולה יחידה", "created_at": time.time()})

    bucket = app._pending_approvals[chat_id]
    action = _classify(bucket, "כן")
    resolved = app._resolve_pending_reply(chat_id, "כן")

    assert action == "confirm"
    assert resolved is not None
    assert resolved[1]["text"] == "פעולה יחידה"


def test_single_pending_bare_unrelated_digit_does_not_auto_confirm():
    """Regression guard for the review-time safety fix: with only ONE
    pending approval, a bare digit (e.g. answering an unrelated "how many?"
    with "1") must NOT be treated as an implicit confirm — that would
    silently execute the pending action with no real confirmation intent."""
    chat_id = "bug070_t6"
    app._pending_approvals.pop(chat_id, None)
    app._add_pending_approval(chat_id, {"text": "שלח מייל ללקוח", "created_at": time.time()})

    bucket = app._pending_approvals[chat_id]
    action = _classify(bucket, "1")

    assert action is None, "bare digit must not auto-confirm when only 1 item is pending"
    assert len(app._pending_approvals[chat_id]) == 1, "the pending item must remain untouched"


def test_multi_pending_bare_digit_does_target_specific_item():
    """With 2+ pending items, a bare digit IS a valid disambiguation reply
    (the bot has shown a numbered list and explicitly asked for a number)."""
    chat_id = "bug070_t7"
    app._pending_approvals.pop(chat_id, None)
    app._add_pending_approval(chat_id, {"text": "פעולה א", "created_at": time.time()})
    app._add_pending_approval(chat_id, {"text": "פעולה ב", "created_at": time.time()})

    bucket = app._pending_approvals[chat_id]
    action = _classify(bucket, "2")
    resolved = app._resolve_pending_reply(chat_id, "2")

    assert action == "confirm"
    assert resolved is not None
    assert resolved[1]["text"] == "פעולה ב"


def test_unmatched_number_does_not_touch_pending():
    chat_id = "bug070_t8"
    app._pending_approvals.pop(chat_id, None)
    app._add_pending_approval(chat_id, {"text": "פעולה ה", "created_at": time.time()})
    app._add_pending_approval(chat_id, {"text": "פעולה ו", "created_at": time.time()})

    resolved = app._resolve_pending_reply(chat_id, "99")
    assert resolved is None
    assert len(app._pending_approvals[chat_id]) == 2


def test_clarification_message_lists_all_pending_by_index():
    chat_id = "bug070_t9"
    app._pending_approvals.pop(chat_id, None)
    app._add_pending_approval(chat_id, {"text": "פעולה א", "created_at": time.time()})
    app._add_pending_approval(chat_id, {"text": "פעולה ב", "created_at": time.time()})

    msg = app._pending_clarification_message(chat_id)
    assert "1." in msg and "2." in msg
    assert "פעולה א" in msg and "פעולה ב" in msg


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
