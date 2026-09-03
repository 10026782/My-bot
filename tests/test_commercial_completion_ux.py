from commercial_completion import ENTITY_CONTRACTS, InputType
from commercial_completion_routing import CommercialCompletionRouter
from commercial_completion_ux import (
    field_presentation,
    presentation_for,
    render_prompt,
    resolve_human_link,
)
from unittest.mock import patch


def _contact(field_name="Name"):
    return lambda query, scope, limit: [
        {"record_id": "recContact1", "fields": {field_name: query}}
    ]


def test_human_contact_name_resolves_without_exposing_id():
    result = resolve_human_link("contact", "אבי חזן", _contact(), scope="owner-1")
    assert result.status == "resolved"
    assert result.canonical_value == "recContact1"
    assert "recContact1" not in result.reason


def test_production_lookup_human_reference_resolves_contact_name():
    import commercial_crm

    with patch(
        "commercial_crm.list_records",
        return_value=[
            {"id": "recContact1", "fields": {"שם": "אבי חזן"}},
        ],
    ) as list_records:
        records = commercial_crm.lookup_human_reference(
            "contact", "אבי חזן", scope="owner-1", limit=6
        )

    assert records[0]["id"] == "recContact1"
    list_records.assert_called_once()


def test_ambiguous_contact_produces_human_choices_not_silent_selection():
    def lookup(query, scope, limit):
        return [
            {"record_id": "recA", "fields": {"Name": "אבי חזן"}},
            {"record_id": "recB", "fields": {"Name": "אבי חזן"}},
        ]

    result = resolve_human_link("contact", "אבי חזן", lookup, scope="owner-1")
    assert result.status == "clarify"
    assert result.canonical_value == ""
    assert [choice.label for choice in result.choices] == ["אבי חזן", "אבי חזן"]
    assert all("rec" not in choice.token for choice in result.choices)


def test_prompts_use_business_labels_and_enum_choices_only():
    field = ENTITY_CONTRACTS["deal"].field("currency")
    presentation = field_presentation("deal", field)
    rendered = render_prompt(presentation)
    assert presentation.user_label == "מטבע"
    assert "Currency" not in rendered
    assert "counterparty" not in rendered
    assert set(field.choices) <= set(rendered.split("אפשרויות: ", 1)[1].split(" / "))


def test_deal_counterparty_is_business_language_with_choices():
    presentation = presentation_for("deal", "counterparty_contact")
    assert presentation.prompt == "עם מי העסקה?"
    assert presentation.choices == ("איש קשר", "ארגון")
    assert "counterparty_contact" not in render_prompt(presentation)


def test_counterparty_choice_selects_one_sibling_field_in_same_session():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    values = {
        "name": "עסקת בדיקה", "domain": "import", "owner": "owner-1",
        "deal_type": "service", "relationship_type": "one_off",
        "currency": "ILS", "commercial_status": "prospect", "expected_value": 100,
    }
    first = router.start("deal", current_values=values)
    selected = router.answer_human(first.session, "ארגון")
    assert selected.outcome == "CLARIFY"
    assert selected.prompt == "מה שם הארגון?"
    resolved = router.answer_human(
        selected.session, "Acme Ltd",
        link_lookup=lambda query, scope, limit: [
            {"record_id": "recOrg1", "fields": {"Organization Name": query}}
        ],
        scope="owner-1",
    )
    assert resolved.outcome == "TOOL"
    assert resolved.tool_inputs["counterparty_organization_id"] == "recOrg1"
    assert "counterparty_contact_id" not in resolved.tool_inputs


def test_app_wires_human_answer_and_telegram_choice_controls():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "_completion_router.answer_human" in source
    assert "commercial_completion:" in source
    assert "InlineKeyboardButton" in source


def test_telegram_keyboard_contains_deterministic_choice_buttons():
    import os
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-s2d-test")
    os.environ.setdefault("TELEGRAM_TOKEN", "123456789:s2d-test")
    os.environ.setdefault("AIRTABLE_API_KEY", "pat-s2d-test")
    os.environ.setdefault("AIRTABLE_BASE_ID", "appS2DTest")
    import app

    keyboard = app._completion_keyboard(("ILS", "USD", "EUR"))
    button_labels = [button.text for row in keyboard.keyboard for button in row]
    assert button_labels == ["ILS", "USD", "EUR"]
    assert all(button.callback_data.startswith("commercial_completion:")
               for row in keyboard.keyboard for button in row)


def test_human_link_answer_reuses_canonical_completion_session_and_payload():
    queued = []
    router = CommercialCompletionRouter(queue=lambda tool, payload: queued.append((tool, payload)))
    values = {
        "name": "עסקת בדיקה", "domain": "import", "owner": "owner-1",
        "deal_type": "service",
        "relationship_type": "one_off", "currency": "ILS",
        "commercial_status": "prospect", "expected_value": 100,
    }
    first = router.start("deal", current_values=values)
    assert first.field_type == InputType.LINK
    resumed = router.answer_human(
        first.session, "אבי חזן", link_lookup=_contact(), scope="owner-1"
    )
    assert resumed.outcome == "TOOL"
    assert resumed.session.active.target_entity == first.session.active.target_entity
    assert resumed.tool_inputs["counterparty_contact_id"] == "recContact1"
    assert queued[0][1]["counterparty_contact_id"] == "recContact1"


def test_router_route_prompt_does_not_expose_storage_field_name():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    result = router.start("deal", current_values={"name": "x", "domain": "import", "owner": "owner-1"})
    assert "counterparty_contact" not in result.prompt
    assert "record_id" not in result.prompt
