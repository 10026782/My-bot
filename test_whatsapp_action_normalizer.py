from core.message_contract import InteractionType, MessageInteraction
from tools.whatsapp_adapter import normalize_whatsapp_action


def test_twilio_payload_maps_to_semantic_confirm_without_returning_provider_id():
    result = normalize_whatsapp_action(
        {"ButtonPayload": "wa_1", "ButtonText": "✅ אשר"},
        interaction=MessageInteraction(InteractionType.CONFIRM_CANCEL, ("✅ אשר", "↩️ בטל")),
    )
    assert result.action == "confirm"
    assert result.value is None
    assert "wa_1" not in repr(result)


def test_twilio_button_text_and_plain_text_map_to_edit_and_cancel():
    interaction = MessageInteraction(
        InteractionType.REVIEW_EDIT, ("✅ אשר", "✏️ ערוך", "↩️ בטל"), editable=True,
    )
    assert normalize_whatsapp_action({"ButtonText": "עריכה"}, interaction=interaction).action == "edit"
    assert normalize_whatsapp_action({"Body": "בטל"}, interaction=interaction).action == "cancel"


def test_meta_reply_and_choice_text_map_without_provider_identifier():
    interaction = MessageInteraction(InteractionType.SINGLE_CHOICE, options=("גיוס", "נדל\"ן"))
    result = normalize_whatsapp_action(
        {"interactive": {"list_reply": {"id": "provider-secret", "title": "גיוס"}}},
        interaction=interaction,
    )
    assert result.action == "choice" and result.value == "גיוס"
    assert "provider-secret" not in repr(result)


def test_unknown_payload_fails_closed_and_arbitrary_text_stays_text():
    interaction = MessageInteraction(InteractionType.CONFIRM_CANCEL, ("✅ אשר", "↩️ בטל"))
    assert normalize_whatsapp_action({"ButtonPayload": "foreign-id"}, interaction=interaction).action == "unknown"
    result = normalize_whatsapp_action({"Body": "פרט נוסף"}, interaction=interaction)
    assert result.action == "text" and result.value == "פרט נוסף"
