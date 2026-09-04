from commercial_completion import ENTITY_CONTRACTS, InputType
from commercial_completion_routing import CommercialCompletionRouter
from commercial_completion_ux import (
    field_presentation,
    presentation_for,
    render_prompt,
    resolve_human_link,
)
from identity import Identity, Role
from unittest.mock import patch


def _owner_identity(tenant_id="boss_hq"):
    return Identity(user_id="owner-1", role=Role.OWNER, tenant_id=tenant_id)


def _partner_identity(allowed_domains, tenant_id="boss_hq"):
    return Identity(
        user_id="partner-1", role=Role.PARTNER, tenant_id=tenant_id,
        allowed_domains=allowed_domains,
    )


def _external_identity(role, tenant_id):
    return Identity(user_id="ext-1", role=role, tenant_id=tenant_id)


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
            "contact", "אבי חזן", scope="owner-1", identity=_owner_identity(), limit=6,
        )

    assert records[0]["id"] == "recContact1"
    list_records.assert_called_once()


# ── BUG 4 regression: lookup_human_reference() must apply the same
# identity/domain scope every other Airtable read goes through
# (tools.airtable_security.enforce_tenant_scope), not read the full table.

def test_lookup_human_reference_owner_sees_matching_record():
    import commercial_crm

    with patch(
        "commercial_crm.list_records",
        return_value=[{"id": "recDeal1", "fields": {"שם העסקה": "עסקת בדיקה"}}],
    ) as list_records:
        records = commercial_crm.lookup_human_reference(
            "deal", "עסקת בדיקה", scope="owner-1", identity=_owner_identity(), limit=6,
        )

    assert records[0]["id"] == "recDeal1"
    # owner/internal identities pass through unfiltered (matches every other
    # enforce_tenant_scope() call site), so no formula is forced onto the call.
    called_formula = list_records.call_args.args[1] if len(list_records.call_args.args) > 1 else ""
    assert called_formula == ""


def test_lookup_human_reference_restricted_partner_domain_is_scoped():
    import commercial_crm

    with patch("commercial_crm.list_records", return_value=[]) as list_records:
        commercial_crm.lookup_human_reference(
            "deal", "עסקת בדיקה", scope="partner-1",
            identity=_partner_identity(["import"]), limit=6,
        )

    called_formula = list_records.call_args.args[1]
    assert "import" in called_formula
    assert "Domain" in called_formula


def test_lookup_human_reference_partner_without_domain_field_fails_closed():
    """Organizations/Payment Terms/Charges have no partner-domain mapping in
    enforce_tenant_scope() — a partner identity must get no records, not the
    unfiltered table."""
    import commercial_crm

    with patch("commercial_crm.list_records", return_value=[
        {"id": "recOrg1", "fields": {"Organization Name": "Acme"}},
    ]) as list_records:
        records = commercial_crm.lookup_human_reference(
            "organization", "Acme", scope="partner-1",
            identity=_partner_identity(["import"]), limit=6,
        )

    assert records == []
    list_records.assert_not_called()


def test_lookup_human_reference_never_leaks_cross_tenant_records():
    import commercial_crm

    with patch("commercial_crm.list_records", return_value=[
        {"id": "recDeal1", "fields": {"שם עסקה": "עסקת לקוח אחר"}},
    ]) as list_records:
        commercial_crm.lookup_human_reference(
            "deal", "עסקת לקוח אחר", scope="client-1",
            identity=_external_identity(Role.LEAD, tenant_id="tenant-a"), limit=6,
        )

    called_formula = list_records.call_args.args[1]
    assert "tenant-a" in called_formula
    assert "tenant_id" in called_formula


def test_lookup_human_reference_fails_closed_without_identity():
    import commercial_crm

    with patch("commercial_crm.list_records") as list_records:
        records = commercial_crm.lookup_human_reference(
            "contact", "אבי חזן", scope="owner-1", identity=None, limit=6,
        )

    assert records == []
    list_records.assert_not_called()


def test_lookup_human_reference_fails_closed_without_scope():
    import commercial_crm

    with patch("commercial_crm.list_records") as list_records:
        records = commercial_crm.lookup_human_reference(
            "contact", "אבי חזן", scope="", identity=_owner_identity(), limit=6,
        )

    assert records == []
    list_records.assert_not_called()


def test_lookup_human_reference_fails_closed_external_without_tenant():
    import commercial_crm

    with patch("commercial_crm.list_records") as list_records:
        records = commercial_crm.lookup_human_reference(
            "deal", "עסקה", scope="ext-1",
            identity=_external_identity(Role.GUEST, tenant_id=""), limit=6,
        )

    assert records == []
    list_records.assert_not_called()


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


# ── BUG 3 regression: every manually-enterable field of every entity this
# completion flow actually supports (Deal, Organization, Payment Term,
# Charge, Payment) must have a real business-language prompt — never the
# generic "please complete the following detail" fallback, and never a raw
# storage key/field name in the rendered text.

def test_no_supported_entity_field_falls_back_to_the_generic_prompt():
    from commercial_completion_routing import SUPPORTED_COMPLETION_ENTITIES

    offenders = []
    for entity in SUPPORTED_COMPLETION_ENTITIES:
        contract = ENTITY_CONTRACTS[entity]
        for f in contract.fields:
            if f.is_computed or not f.manual_entry_allowed:
                continue
            presentation = field_presentation(entity, f)
            if presentation.prompt == "נא להשלים את הפרט הבא.":
                offenders.append((entity, f.field_name))
    assert offenders == []


def test_supported_entity_prompts_never_expose_storage_field_names():
    """The internal snake_case field_name (e.g. "counterparty_contact") must
    never leak into rendered text — unlike Airtable's own column name, which
    in this codebase is itself Hebrew business text and legitimately
    overlaps with a human prompt (e.g. Deal Name's Hebrew column name IS
    "שם העסקה", the same words a prompt asking for it would use)."""
    from commercial_completion_routing import SUPPORTED_COMPLETION_ENTITIES

    for entity in SUPPORTED_COMPLETION_ENTITIES:
        contract = ENTITY_CONTRACTS[entity]
        for f in contract.fields:
            if f.is_computed or not f.manual_entry_allowed:
                continue
            rendered = render_prompt(field_presentation(entity, f))
            assert f.field_name not in rendered


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


# ── BUG 5 regression: callback_data must never exceed Telegram's 64 UTF-8
# byte limit, must still display the full human label, must resolve back to
# the intended candidate, and duplicate labels must stay distinguishable.

def _app():
    import os
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-s2d-test")
    os.environ.setdefault("TELEGRAM_TOKEN", "123456789:s2d-test")
    os.environ.setdefault("AIRTABLE_API_KEY", "pat-s2d-test")
    os.environ.setdefault("AIRTABLE_BASE_ID", "appS2DTest")
    import app
    return app


def test_completion_keyboard_realistic_long_hebrew_label_fits_telegram_limit():
    app = _app()
    long_label = "החברה הישראלית לפיתוח ותשתיות בעמ"  # 84 bytes with the raw prefix
    assert len((app._COMPLETION_CALLBACK_PREFIX + long_label).encode("utf-8")) > 64

    keyboard = app._completion_keyboard((long_label,))
    button = keyboard.keyboard[0][0]
    assert button.text == long_label  # displayed label stays full human text
    assert len(button.callback_data.encode("utf-8")) <= 64


def test_completion_keyboard_uses_router_tokens_when_available():
    app = _app()
    label = "החברה הישראלית לפיתוח ותשתיות בעמ"
    keyboard = app._completion_keyboard((label,), ("7",))
    button = keyboard.keyboard[0][0]
    assert button.text == label
    assert button.callback_data == "commercial_completion:7"


def test_completion_keyboard_duplicate_labels_get_distinguishable_callback_data():
    app = _app()
    keyboard = app._completion_keyboard(("דוד כהן", "דוד כהן"), ("1", "2"))
    payloads = [button.callback_data for row in keyboard.keyboard for button in row]
    assert payloads[0] != payloads[1]


def test_router_choice_tokens_resolve_back_to_the_exact_candidate_shown():
    """End-to-end: two candidates share a label; the token from the first
    CLARIFY route must pick the SAME candidate on the next turn, not
    whichever one a fresh free-text search happens to return first."""
    router = CommercialCompletionRouter(queue=lambda *_: None)
    values = {
        "name": "עסקת בדיקה", "domain": "import", "owner": "owner-1",
        "deal_type": "service", "relationship_type": "one_off",
        "currency": "ILS", "commercial_status": "prospect", "expected_value": 100,
    }
    first = router.start("deal", current_values=values)

    def lookup(query, scope, limit):
        return [
            {"record_id": "recDup1", "fields": {"Name": "דוד כהן"}},
            {"record_id": "recDup2", "fields": {"Name": "דוד כהן"}},
        ]

    clarify = router.answer_human(first.session, "דוד", link_lookup=lookup, scope="owner-1")
    assert clarify.outcome == "CLARIFY"
    assert clarify.choice_tokens == ("1", "2")

    picked_second = router.answer_human(
        clarify.session, clarify.choice_tokens[1], link_lookup=lookup, scope="owner-1",
    )
    assert picked_second.outcome == "TOOL"
    assert picked_second.tool_inputs["counterparty_contact_id"] == "recDup2"

    picked_first = router.answer_human(
        clarify.session, clarify.choice_tokens[0], link_lookup=lookup, scope="owner-1",
    )
    assert picked_first.outcome == "TOOL"
    assert picked_first.tool_inputs["counterparty_contact_id"] == "recDup1"


def test_completion_keyboard_send_falls_back_to_text_when_keyboard_rejected(monkeypatch):
    app = _app()
    import telebot

    calls = []

    def fake_send(chat_id, text, **kwargs):
        calls.append(kwargs)
        if "reply_markup" in kwargs:
            raise telebot.apihelper.ApiTelegramException(
                "sendMessage", None,
                {"ok": False, "error_code": 400, "description": "Bad Request: BUTTON_DATA_INVALID"},
            )
        return "sent"

    monkeypatch.setattr(app.bot, "send_message", fake_send)
    result = app._send_with_keyboard_fallback(
        "chat1", "hello", reply_markup=app._completion_keyboard(("x",)),
    )
    assert result == "sent"
    assert len(calls) == 2  # first attempt (with keyboard) failed, retried without it
    assert "reply_markup" not in calls[-1]


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
