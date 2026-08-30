import pytest

from core.message_contract import InteractionType, MessageInteraction
from tools.whatsapp_adapter import normalize_whatsapp_action


CONFIRM = MessageInteraction(InteractionType.CONFIRM_CANCEL, ("✅ אשר", "↩️ בטל"))


@pytest.mark.parametrize("token", ["כן", "אשר", "מאשר", "מאשרת", "✅", "✅ אשר", "yes", "ok"])
@pytest.mark.parametrize("wrapper", [lambda value: value, lambda value: f"  {value}  "])
def test_confirm_requires_exact_normalized_token(token, wrapper):
    assert normalize_whatsapp_action({"Body": wrapper(token)}, interaction=CONFIRM).action == "confirm"


@pytest.mark.parametrize("token", ["ערוך", "✏️ ערוך", "עריכה", "edit"])
def test_edit_tokens_and_latin_case_are_deterministic(token):
    assert normalize_whatsapp_action({"Body": f"\n {token.upper()} \t"}, interaction=CONFIRM).action == "edit"


@pytest.mark.parametrize("token", ["לא", "בטל", "ביטול", "↩️ בטל", "cancel", "no"])
def test_cancel_tokens_and_latin_case_are_deterministic(token):
    assert normalize_whatsapp_action({"Body": f"  {token.upper()}  "}, interaction=CONFIRM).action == "cancel"


@pytest.mark.parametrize("body", [
    "כן בבקשה",
    "אישור נוסף",
    "cancel now",
    "בטל!",
    "מילה אחרת",
    "כן\nבבקשה",
])
def test_non_exact_reserved_text_remains_free_text(body):
    result = normalize_whatsapp_action({"Body": body}, interaction=CONFIRM)
    assert result.action == "text"
    assert result.value == " ".join(body.split()).casefold()


@pytest.mark.parametrize("event", [{"Body": ""}, {"Body": " \n\t "}, {}])
def test_empty_or_missing_text_fails_closed(event):
    assert normalize_whatsapp_action(event, interaction=CONFIRM).action == "unknown"


def test_invalid_event_type_is_rejected():
    with pytest.raises(TypeError):
        normalize_whatsapp_action(None, interaction=CONFIRM)
