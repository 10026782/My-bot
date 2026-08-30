from types import SimpleNamespace
from unittest.mock import Mock, patch

import cmd_decision
from core.draft_flow import DraftSpec
from identity import Identity, Role


def _msg(text):
    return SimpleNamespace(text=text, from_user=SimpleNamespace(id="u1"), chat=SimpleNamespace(id="c1"))


def _state():
    return cmd_decision._new_decision_state(SimpleNamespace(tenant_id="t", user_id="u"))


class _DecisionBot:
    def __init__(self):
        self.command = None
        self.messages = []
        self.callbacks = {}

    def message_handler(self, **kwargs):
        def register(fn):
            if kwargs.get("commands") == ["decision"]:
                self.command = fn
            return fn
        return register

    def callback_query_handler(self, **kwargs):
        def register(fn):
            self.callbacks[fn.__name__] = fn
            return fn
        return register

    def send_message(self, *args, **kwargs):
        self.messages.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.messages.append((args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        self.messages.append((args, kwargs))


def test_decision_capability_denies_unauthorized_role_before_flow():
    bot = _DecisionBot()
    identity = Identity(user_id="guest-1", role=Role.READONLY, tenant_id="tenant-a")
    with patch("feature_flags.is_enabled", return_value=True):
        cmd_decision.register_decision_command(bot, lambda *_: identity)

    bot.command(_msg("/decision status rec123"))

    assert bot.messages[-1][0][1] == "אין הרשאה לפקודה זו."


def test_decision_record_scope_rejects_other_tenant_and_partner_other_domain():
    other_tenant = {"id": "rec-other", "fields": {
        "tenant_id": "tenant-b", "Domain": "general", "Title": "Other",
    }}
    partner = Identity(
        user_id="partner-1", role=Role.PARTNER, tenant_id="tenant-a",
        allowed_domains=["real_estate"],
    )
    assert cmd_decision._decision_in_scope(other_tenant, partner) is False

    same_tenant_other_domain = {"id": "rec-domain", "fields": {
        "tenant_id": "tenant-a", "Domain": "general", "Title": "Other domain",
    }}
    assert cmd_decision._decision_in_scope(same_tenant_other_domain, partner) is False


def test_decision_record_scope_allows_existing_role_with_matching_tenant_domain():
    partner = Identity(
        user_id="partner-1", role=Role.PARTNER, tenant_id="tenant-a",
        allowed_domains=["real_estate"],
    )
    decision = {"id": "rec-own", "fields": {
        "tenant_id": "tenant-a", "Domain": "real_estate", "Title": "Own",
    }}
    assert cmd_decision._decision_in_scope(decision, partner) is True


def _callback(data, user_id="u1"):
    return SimpleNamespace(
        id="callback-1", data=data, from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id="c1"), message_id=4),
    )


def _registered_decision_bot(identity):
    bot = _DecisionBot()
    with patch("feature_flags.is_enabled", return_value=True):
        cmd_decision.register_decision_command(bot, lambda *_: identity)
    return bot


def test_decision_link_callback_rejects_cross_tenant_without_writes():
    identity = Identity(user_id="u1", role=Role.MANAGER, tenant_id="tenant-a")
    bot = _registered_decision_bot(identity)
    storage = Mock()
    decision = {"id": "rec-d", "fields": {"tenant_id": "tenant-b", "Domain": "general"}}
    inbox = {"id": "rec-i", "fields": {"tenant_id": "tenant-a", "Status": "Pending"}}
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch.object(
        cmd_decision, "_at_get_record", side_effect=[decision, inbox]
    ):
        bot.callbacks["cb_inbox_link"](_callback("dec_inbox_link:rec-i:rec-d"))
    storage.add.assert_not_called()
    storage.update.assert_not_called()


def test_decision_ignore_callback_rejects_unauthorized_role_without_writes():
    identity = Identity(user_id="u1", role=Role.READONLY, tenant_id="tenant-a")
    bot = _registered_decision_bot(identity)
    storage = Mock()
    with patch.object(cmd_decision, "_decision_storage", return_value=storage):
        bot.callbacks["cb_inbox_ignore"](_callback("dec_inbox_ignore:rec-i"))
    storage.update.assert_not_called()


def test_decision_ignore_callback_rejects_cross_tenant_and_stale_inbox():
    identity = Identity(user_id="u1", role=Role.MANAGER, tenant_id="tenant-a")
    bot = _registered_decision_bot(identity)
    storage = Mock()
    foreign = {"id": "rec-i", "fields": {"tenant_id": "tenant-b", "Status": "Pending"}}
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch.object(
        cmd_decision, "_at_get_record", return_value=foreign
    ):
        bot.callbacks["cb_inbox_ignore"](_callback("dec_inbox_ignore:rec-i"))
    storage.update.assert_not_called()

    stale = {"id": "rec-i", "fields": {"tenant_id": "tenant-a", "Status": "Linked"}}
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch.object(
        cmd_decision, "_at_get_record", return_value=stale
    ):
        bot.callbacks["cb_inbox_ignore"](_callback("dec_inbox_ignore:rec-i"))
    storage.update.assert_not_called()


def test_decision_link_callback_rejects_partner_inaccessible_domain_without_writes():
    identity = Identity(user_id="u1", role=Role.PARTNER, tenant_id="tenant-a", allowed_domains=["real_estate"])
    bot = _registered_decision_bot(identity)
    storage = Mock()
    decision = {"id": "rec-d", "fields": {"tenant_id": "tenant-a", "Domain": "general"}}
    inbox = {"id": "rec-i", "fields": {"tenant_id": "tenant-a", "Status": "Pending"}}
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch.object(
        cmd_decision, "_at_get_record", side_effect=[decision, inbox]
    ):
        bot.callbacks["cb_inbox_link"](_callback("dec_inbox_link:rec-i:rec-d"))
    storage.add.assert_not_called()
    storage.update.assert_not_called()


def test_dependent_reads_reject_unauthorized_parent_before_listing():
    identity = Identity(user_id="u1", role=Role.MANAGER, tenant_id="tenant-a")
    foreign = {"id": "rec-d", "fields": {"tenant_id": "tenant-b", "Domain": "general"}}
    with patch.object(cmd_decision, "_at_get_record", return_value=foreign), patch.object(cmd_decision, "_at_list") as listing:
        assert cmd_decision._list_stakeholders("rec-d", identity) == []
        assert cmd_decision._list_decision_events("rec-d", identity) == []
    listing.assert_not_called()


def test_decision_link_callback_writes_same_scope_event_with_tenant():
    identity = Identity(user_id="u1", role=Role.MANAGER, tenant_id="tenant-a")
    bot = _registered_decision_bot(identity)
    storage = Mock()
    storage.add.return_value = "rec-event"
    decision = {"id": "rec-d", "fields": {"tenant_id": "tenant-a", "Domain": "general", "Title": "Decision"}}
    inbox = {"id": "rec-i", "fields": {"tenant_id": "tenant-a", "Status": "Pending", "Raw Input": "update"}}
    outcome = {"halted_at": "delta", "result": SimpleNamespace(user_flag="", reason="")}
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch.object(
        cmd_decision, "_at_get_record", side_effect=[decision, inbox]
    ), patch("decision_pipeline.run_pipeline", return_value=outcome):
        bot.callbacks["cb_inbox_link"](_callback("dec_inbox_link:rec-i:rec-d"))
    event_fields = storage.add.call_args.args[1]
    assert event_fields["tenant_id"] == "tenant-a"
    storage.update.assert_called_once()


def test_decision_link_event_failure_does_not_mark_inbox_fully_linked():
    identity = Identity(user_id="u1", role=Role.MANAGER, tenant_id="tenant-a")
    bot = _registered_decision_bot(identity)
    storage = Mock()
    storage.add.return_value = None
    decision = {"id": "rec-d", "fields": {"tenant_id": "tenant-a", "Domain": "general", "Title": "Decision"}}
    inbox = {"id": "rec-i", "fields": {"tenant_id": "tenant-a", "Status": "Pending", "Raw Input": "update"}}
    outcome = {"halted_at": "delta", "result": SimpleNamespace(user_flag="", reason="")}
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch.object(
        cmd_decision, "_at_get_record", side_effect=[decision, inbox]
    ), patch("decision_pipeline.run_pipeline", return_value=outcome):
        bot.callbacks["cb_inbox_link"](_callback("dec_inbox_link:rec-i:rec-d"))

    storage.update.assert_not_called()
    assert "לא נשמר" in bot.messages[-2][0][0]


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


def test_decision_new_uses_shared_draftflow_spec_and_resolver():
    assert isinstance(cmd_decision._DECISION_NEW_DRAFT_SPEC, DraftSpec)
    bot = Mock()
    state = _state()
    with patch.object(cmd_decision, "resolve_draft_reply", wraps=cmd_decision.resolve_draft_reply) as resolver:
        cmd_decision._handle_new_step(bot, _msg("Decision"), state)
    resolver.assert_called_once_with("Decision", state, cmd_decision._DECISION_NEW_DRAFT_SPEC)
    assert state["step"] == "domain"


def test_decision_new_shared_edit_updates_one_field_without_writing():
    bot = Mock()
    state = _state()
    state.update({
        "step": "review", "mode": "review", "title": "Old",
        "domain": "כללי", "exposure": 1.0, "stakeholder_names": ["A"],
    })
    cmd_decision._handle_new_step(bot, _msg("ערוך"), state)
    cmd_decision._handle_new_step(bot, _msg("שם"), state)
    with patch.object(cmd_decision, "_create_decision") as create:
        cmd_decision._handle_new_step(bot, _msg("New"), state)
    assert state["step"] == "review"
    assert state["title"] == "New"
    assert state["domain"] == "כללי"
    assert state["exposure"] == 1.0
    assert state["stakeholder_names"] == ["A"]
    create.assert_not_called()
