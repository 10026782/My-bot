from types import SimpleNamespace
from unittest.mock import Mock, patch

import cmd_update


def _identity():
    return SimpleNamespace(tenant_id="t", user_id="u", is_owner=True, role="owner")


def _state():
    return {
        "step": "review", "token": "tok", "identity": _identity(),
        "domain": "general", "entry_type": "Decision", "raw_text": "בדיקה",
        "created_at": cmd_update._now_ts(),
    }


def _call(data):
    return SimpleNamespace(
        id="cb", data=data, from_user=SimpleNamespace(id="u"),
        message=SimpleNamespace(chat=SimpleNamespace(id="c"), message_id=7),
    )


def test_update_review_is_business_facing_and_has_actions():
    review = cmd_update._update_review(_state())
    assert "כללי" in review
    assert "בדיקה" in review
    assert "✅" in review and "✏️" in review and "↩️" in review
    assert "record" not in review.lower()


def test_update_confirm_executes_once_and_cancel_does_not_write():
    state = _state()
    with patch.object(cmd_update, "_save_to_business_memory", return_value={"ok": True}) as save:
        result = cmd_update._execute_update(state, "u", lambda *_: _identity())
    assert result["ok"] is True
    save.assert_called_once()

    with patch.object(cmd_update, "_save_to_business_memory") as save:
        cmd_update._pending["u"] = _state()
        bot = Mock()
        cmd_update._resolve_update_callback(bot, _call("upd_review:tok:cancel"), lambda *_: _identity())
    save.assert_not_called()
    assert "u" not in cmd_update._pending


def test_update_replay_callback_is_stale_and_does_not_write():
    cmd_update._pending.pop("u", None)
    with patch.object(cmd_update, "_save_to_business_memory") as save:
        bot = Mock()
        cmd_update._resolve_update_callback(bot, _call("upd_review:tok:confirm"), lambda *_: _identity())
    save.assert_not_called()
    assert "כבר אינו זמין" in bot.answer_callback_query.call_args.args[1]


def test_update_edit_changes_only_selected_field_without_writing():
    state = _state()
    cmd_update._pending["u"] = state
    bot = Mock()
    cmd_update._start_update_edit(bot, _call("upd_edit:tok:text"))
    assert state["step"] == "edit_text"
    state["raw_text"] = "חדש"
    state["step"] = "review"
    with patch.object(cmd_update, "_save_to_business_memory") as save:
        cmd_update._handle_update_review_text(bot, SimpleNamespace(
            text="ערוך", from_user=SimpleNamespace(id="u"), chat=SimpleNamespace(id="c")
        ), state, lambda *_: _identity())
    save.assert_not_called()
    assert state["step"] == "edit_choice"
    cmd_update._pending.pop("u", None)


def test_update_callback_edit_enters_field_choice_without_writing():
    cmd_update._pending["u"] = _state()
    bot = Mock()
    cmd_update._resolve_update_callback(bot, _call("upd_review:tok:edit"), lambda *_: _identity())
    assert cmd_update._pending["u"]["step"] == "edit_choice"
    assert bot.edit_message_text.call_args.kwargs["reply_markup"] is not None
    cmd_update._pending.pop("u", None)
