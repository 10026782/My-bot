from types import SimpleNamespace
from unittest.mock import Mock, patch

import cmd_decision


def _msg(text):
    return SimpleNamespace(text=text, from_user=SimpleNamespace(id="u1"), chat=SimpleNamespace(id="c1"))


def _state():
    return cmd_decision._new_decision_state(SimpleNamespace(tenant_id="t", user_id="u"))


def test_decision_new_collects_validates_reviews_without_writing():
    bot = Mock()
    state = _state()

    cmd_decision._handle_new_step(bot, _msg("Quarterly plan"), state)
    assert state["step"] == "domain"
    state["domain"] = "כללי"
    state["step"] = "exposure"
    cmd_decision._handle_new_step(bot, _msg("25000"), state)
    cmd_decision._handle_new_step(bot, _msg("Dana, Eli"), state)

    assert state["step"] == "review"
    assert state["exposure"] == 25000.0
    assert state["stakeholder_names"] == ["Dana", "Eli"]


def test_decision_new_rejects_invalid_input_before_review():
    bot = Mock()
    state = _state()

    cmd_decision._handle_new_step(bot, _msg(""), state)
    assert state["step"] == "title"
    cmd_decision._handle_new_step(bot, _msg("Decision"), state)
    state["domain"] = "כללי"
    state["step"] = "exposure"
    cmd_decision._handle_new_step(bot, _msg("not a number"), state)
    assert state["step"] == "exposure"


def test_decision_new_edit_updates_same_review_state():
    bot = Mock()
    state = _state()
    state.update({
        "step": "edit_value", "edit_field": "title", "title": "Old",
        "domain": "כללי", "exposure": 1.0, "stakeholder_names": ["A"],
    })

    cmd_decision._handle_new_step(bot, _msg("New"), state)
    assert state["step"] == "review"
    assert state["title"] == "New"


def test_decision_new_review_maps_internal_domain_to_business_label():
    state = _state()
    state.update({"title": "Decision", "domain": "real_estate", "exposure": 1.0, "stakeholder_names": ["A"]})

    review = cmd_decision._decision_new_review(state)

    assert "דומיין: נדל\"ן" in review
    assert "real_estate" not in review


def test_decision_new_confirm_writes_once_and_receipt_is_redacted():
    bot = Mock()
    state = _state()
    state.update({
        "step": "review", "title": "Decision", "domain": "כללי",
        "exposure": 1.0, "stakeholder_names": [],
    })
    with patch.object(cmd_decision, "_create_decision", return_value={"id": "rec-internal"}) as create:
        cmd_decision._handle_new_step(bot, _msg("כן"), state)

    create.assert_called_once()
    assert bot.send_message.call_args.args[1] == "✅ ההחלטה נשמרה: Decision"
    assert "rec-internal" not in bot.send_message.call_args.args[1]


def test_decision_new_cancel_writes_nothing():
    bot = Mock()
    state = _state()
    state.update({"step": "review", "title": "Decision", "domain": "כללי", "exposure": 1.0, "stakeholder_names": []})
    with patch.object(cmd_decision, "_create_decision") as create:
        cmd_decision._handle_new_step(bot, _msg("בטל"), state)
    create.assert_not_called()
    assert "בוטלה" in bot.send_message.call_args.args[1]


def test_decision_new_callback_confirm_and_cancel_are_terminal():
    bot = Mock()
    state = _state()
    state.update({"step": "review", "title": "Decision", "domain": "כללי", "exposure": 1.0, "stakeholder_names": []})
    uid = "u1"
    cmd_decision._pending[uid] = state
    call = SimpleNamespace(
        id="callback", data=f"dec_new_confirm:{state['token']}",
        from_user=SimpleNamespace(id=uid),
        message=SimpleNamespace(chat=SimpleNamespace(id="c1"), message_id=4),
    )
    with patch.object(cmd_decision, "_create_decision", return_value={"id": "internal"}) as create:
        cmd_decision._resolve_new_terminal_callback(bot, call, "confirm")
    create.assert_called_once()
    assert bot.answer_callback_query.call_args.args[1] == "✅ התקבל"
    assert "internal" not in bot.edit_message_text.call_args.args[0]

    state = _state()
    state.update({"step": "review", "title": "Decision", "domain": "כללי", "exposure": 1.0, "stakeholder_names": []})
    cmd_decision._pending[uid] = state
    call.data = f"dec_new_cancel:{state['token']}"
    with patch.object(cmd_decision, "_create_decision") as create:
        cmd_decision._resolve_new_terminal_callback(bot, call, "cancel")
    create.assert_not_called()
    assert bot.answer_callback_query.call_args.args[1] == "✅ התקבל"
    assert "בוטלה" in bot.edit_message_text.call_args.args[0]


def test_decision_new_failure_receipt_is_business_facing():
    receipt = cmd_decision._decision_new_receipt(None, "Decision")

    assert receipt == "⚠️ ההחלטה לא נשמרה."
    assert "logs" not in receipt
