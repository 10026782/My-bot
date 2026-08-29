from core.message_contract import (
    InteractionType,
    MessageInteraction,
    TurnContextSource,
    build_message_contract,
)
from tools.whatsapp_adapter import render_whatsapp_message


def _contract(interaction=None):
    return build_message_contract(
        state="approval_pending",
        reply_owner="gateway",
        turn_context_source=TurnContextSource.LEGACY_INGRESS,
        source_module="test_whatsapp_semantic_adapter",
        display_payload={
            "action": "create",
            "entity_type": "lead",
            "entity_name": "ישראל ישראלי",
            "key_fields": [{"label": "תחום", "value": "גיוס"}],
        },
        interaction=interaction,
    )


def test_plain_contract_keeps_current_text_only_behavior():
    result = render_whatsapp_message(_contract())
    assert result.interactive is None
    assert "ישראל ישראלי" in result.body


def test_confirm_cancel_maps_semantics_to_quick_replies_and_keeps_fallback():
    result = render_whatsapp_message(
        _contract(MessageInteraction(
            InteractionType.CONFIRM_CANCEL,
            actions=("✅ אשר", "↩️ בטל"),
        )),
        interactive_enabled=True,
    )
    assert result.interactive == {
        "type": "quick_reply",
        "buttons": [
            {"id": "wa_1", "title": "✅ אשר"},
            {"id": "wa_2", "title": "↩️ בטל"},
        ],
    }
    assert "✅ אשר" in result.body and "↩️ בטל" in result.body


def test_review_edit_and_choices_are_provider_data_only():
    review = render_whatsapp_message(
        _contract(MessageInteraction(
            InteractionType.REVIEW_EDIT,
            actions=("✅ אשר", "✏️ ערוך", "↩️ בטל"),
            editable=True,
        )),
        interactive_enabled=True,
    )
    choices = render_whatsapp_message(
        _contract(MessageInteraction(
            InteractionType.SINGLE_CHOICE,
            options=("גיוס", "נדל\"ן"),
        )),
        interactive_enabled=True,
    )
    assert [button["title"] for button in review.interactive["buttons"]] == [
        "✅ אשר", "✏️ ערוך", "↩️ בטל",
    ]
    assert [button["title"] for button in choices.interactive["buttons"]] == ["גיוס", "נדל\"ן"]
    assert "wa_" not in review.body and "wa_" not in choices.body


def test_capability_off_is_plain_text_without_false_interactive_claim():
    result = render_whatsapp_message(
        _contract(MessageInteraction(
            InteractionType.CONFIRM_CANCEL,
            actions=("confirm", "cancel"),
        )),
    )
    assert result.interactive is None
    assert "✅ אשר" in result.body and "↩️ בטל" in result.body
