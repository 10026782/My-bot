from commercial_completion import ENTITY_CONTRACTS, InputType
from commercial_completion_routing import CommercialCompletionRouter
from commercial_completion_ux import (
    field_presentation,
    presentation_for,
    render_prompt,
    resolve_human_link,
)


def _contact(field_name="Name"):
    return lambda query, scope, limit: [
        {"record_id": "recContact1", "fields": {field_name: query}}
    ]


def test_human_contact_name_resolves_without_exposing_id():
    result = resolve_human_link("contact", "אבי חזן", _contact(), scope="owner-1")
    assert result.status == "resolved"
    assert result.canonical_value == "recContact1"
    assert "recContact1" not in result.reason


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
