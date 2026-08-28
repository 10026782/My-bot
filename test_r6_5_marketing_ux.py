from types import SimpleNamespace
from unittest.mock import patch

import cmd_marketing


class FakeBot:
    def __init__(self):
        self.messages, self.callbacks = [], []
        self.sent, self.edited, self.acks = [], [], []

    def message_handler(self, **kwargs):
        def register(fn):
            self.messages.append((kwargs, fn))
            return fn
        return register

    def callback_query_handler(self, **kwargs):
        def register(fn):
            self.callbacks.append((kwargs, fn))
            return fn
        return register

    def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))

    def edit_message_text(self, text, chat_id, message_id, **kwargs):
        self.edited.append((text, chat_id, message_id, kwargs))

    def edit_message_reply_markup(self, *args, **kwargs):
        self.edited.append(("markup", args, kwargs))

    def answer_callback_query(self, callback_id, text=None):
        self.acks.append((callback_id, text))


def _message(uid, text):
    return SimpleNamespace(from_user=SimpleNamespace(id=uid), chat=SimpleNamespace(id=uid), text=text)


def _call(uid, data):
    return SimpleNamespace(
        id=f"cb-{uid}-{data}", data=data, from_user=SimpleNamespace(id=uid),
        message=SimpleNamespace(chat=SimpleNamespace(id=uid), message_id=7),
    )


def _registered(bot, kind, prefix):
    items = bot.callbacks if kind == "callback" else bot.messages
    for metadata, fn in items:
        if kind == "callback" and metadata["func"](_call("u", prefix + "x")):
            return fn
        if kind == "message" and prefix in metadata["commands"]:
            return fn
    raise AssertionError(prefix)


class Identity:
    user_id = "u"
    is_owner = True
    role = "owner"


def _start(bot, uid="u"):
    _registered(bot, "message", "marketing_new")(_message(uid, "/marketing_new"))
    _registered(bot, "callback", "mkt_domain:")(_call(uid, "mkt_domain:general"))
    _registered(bot, "callback", "mkt_type:")(_call(uid, "mkt_type:recruitment"))
    capture = next(fn for metadata, fn in bot.messages if "func" in metadata)
    for value in ("מגייס", "מרכז", "3 עד סוף החודש", "אין"):
        capture(_message(uid, value))


def test_marketing_new_has_review_edit_confirm_and_cancel_boundary():
    bot = FakeBot()
    with patch("feature_flags.is_enabled", return_value=True), \
         patch.object(cmd_marketing, "_create_marketing_execution_context", return_value=None), \
         patch.object(cmd_marketing, "_create_demand_and_generate_ideas", return_value={
             "ok": True, "creative_id": "hidden", "ideas": ["א", "ב", "ג"],
         }) as execute:
        cmd_marketing._pending.clear()
        cmd_marketing.register_marketing_command(bot, lambda *_: Identity())
        _start(bot)
        assert cmd_marketing._pending["u"]["step"] == "review"
        assert "תחום: כללי" in bot.sent[-1][1]
        assert execute.call_count == 0

        review = _registered(bot, "callback", "mkt_review:")
        review(_call("u", "mkt_review:edit"))
        edit_field = _registered(bot, "callback", "mkt_edit_field:")
        edit_field(_call("u", "mkt_edit_field:role_experience"))
        capture = next(fn for metadata, fn in bot.messages if "func" in metadata)
        capture(_message("u", "מגייס בכיר"))
        assert cmd_marketing._pending["u"]["step"] == "review"
        assert "מגייס בכיר" in bot.sent[-1][1]
        assert execute.call_count == 0

        review(_call("u", "mkt_review:confirm"))
        assert execute.call_count == 1
        assert len([text for text, *_ in bot.edited if "נשמר" in text]) == 1
        review(_call("u", "mkt_review:confirm"))
        assert execute.call_count == 1


def test_marketing_new_cancel_clears_pending_without_execution():
    bot = FakeBot()
    with patch("feature_flags.is_enabled", return_value=True), \
         patch.object(cmd_marketing, "_create_demand_and_generate_ideas") as execute:
        cmd_marketing._pending.clear()
        cmd_marketing.register_marketing_command(bot, lambda *_: Identity())
        _start(bot, uid="cancel")
        review = _registered(bot, "callback", "mkt_review:")
        review(_call("cancel", "mkt_review:cancel"))
        assert "cancel" not in cmd_marketing._pending
        assert any("בוטל" in text for text, *_ in bot.edited)
        execute.assert_not_called()


if __name__ == "__main__":
    test_marketing_new_has_review_edit_confirm_and_cancel_boundary()
    test_marketing_new_cancel_clears_pending_without_execution()
    print("test_r6_5_marketing_ux.py: 2/2 passed")
