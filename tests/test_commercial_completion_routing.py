"""S2C deterministic completion routing contract tests."""

from airtable_schema import (
    CommercialStatus, Currency, DealType, Direction, EstimatedValueBasis,
    EstimatedValueRange, RelationshipType,
)
from commercial_completion_routing import (
    CommercialCompletionRouter,
    deserialize_completion_session, serialize_completion_session,
    MUTATION_TOOLS,
    NestedResumeOutcome,
    SUPPORTED_COMPLETION_ENTITIES,
)


def _deal():
    return {
        "name": "Deal", "domain": "import", "owner": "recOwner1",
        "counterparty_contact": "recContact1", "deal_type": DealType.SERVICE,
        "relationship_type": RelationshipType.ONE_OFF, "currency": Currency.ILS,
        "commercial_status": CommercialStatus.PROSPECT,
        # BUG-DIAMOND-EXPECTED-VALUE-RANGE: replaces the old "expected_value"
        # scalar field.
        "estimated_value_basis": EstimatedValueBasis.ONE_OFF,
        "estimated_value_range": EstimatedValueRange.RANGE_100K_300K,
        "estimated_value_notes": "תלוי בהיקף העבודה בפועל",
    }


def test_supported_entities_have_one_canonical_primitive_each():
    # DIAMOND PATH nested-entity approval continuation: "contact" has a
    # MUTATION_TOOLS primitive but is deliberately NOT a top-level
    # SUPPORTED_COMPLETION_ENTITIES member — router.start("contact", ...)
    # must keep failing closed; it is reachable only via begin_nested()
    # from an active parent completion. Every other entity still has
    # exactly one primitive each, symmetric in both sets.
    assert SUPPORTED_COMPLETION_ENTITIES == set(MUTATION_TOOLS) - {"contact"}
    assert "contact" not in SUPPORTED_COMPLETION_ENTITIES
    assert set(MUTATION_TOOLS.values()) == {
        "crm_create_deal", "crm_create_payment_term",
        "crm_find_or_create_organization", "crm_find_or_create_contact",
        "crm_create_charge", "crm_create_charge_payment",
    }


def test_optional_deal_fields_never_block_creation():
    # BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION (production-verified,
    # 06/09/2026): deal_type/relationship_type/currency/commercial_status/
    # estimated value fields are optional — dropping all of them must
    # queue crm_create_deal immediately, never a CLARIFY loop asking for
    # them one at a time before the Deal can be created.
    queued = []
    router = CommercialCompletionRouter(queue=lambda tool, payload: queued.append((tool, payload)))
    values = _deal()
    values.pop("deal_type")
    values.pop("relationship_type")
    values.pop("currency")
    values.pop("commercial_status")
    values.pop("estimated_value_basis")
    values.pop("estimated_value_range")
    values.pop("estimated_value_notes")
    result = router.start("deal", current_values=values, source_context={})
    assert result.outcome == "TOOL"
    assert result.tool_name == "crm_create_deal"
    assert queued == [("crm_create_deal", result.tool_inputs)]


def test_missing_business_required_field_still_clarifies_before_creation():
    # The business-required set (name/domain/owner/counterparty) still
    # gates creation — only the five optional V2 fields were declassified.
    queued = []
    router = CommercialCompletionRouter(queue=lambda tool, payload: queued.append((tool, payload)))
    values = _deal()
    values.pop("owner")
    first = router.start("deal", current_values=values, source_context={})
    assert first.outcome == "CLARIFY"
    assert first.field_name == "owner"
    assert queued == []


def test_payment_is_charge_required_and_never_agent_fallback():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    result = router.start(
        "payment",
        current_values={"amount": 10, "paid_at": "2026-09-03", "direction": Direction.RECEIVABLE, "currency": Currency.ILS},
    )
    assert result.outcome == "CLARIFY"
    assert result.field_name == "charge"


def test_allocation_and_economics_are_blocked_in_s2c():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    assert router.start("allocation_rule").outcome == "BLOCK"
    assert router.start("deal_economics").outcome == "BLOCK"


def test_queue_receives_the_same_mapping_that_route_reports():
    calls = []
    router = CommercialCompletionRouter(queue=lambda tool, payload: calls.append((tool, dict(payload))))
    result = router.start("organization", current_values={"organization_name": "Acme"})
    assert result.outcome == "TOOL"
    assert calls == [(result.tool_name, dict(result.tool_inputs))]


def test_completion_state_round_trips_and_preserves_all_deal_fields():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal())
    restored = router.restore(serialize_completion_session(first.session))
    assert restored.field_name == first.field_name
    payload = restored.session.active.complete_payload()
    assert set(payload) >= {
        "Counterparty Contact", "Deal Type Code", "Relationship Type",
        "Currency", "Commercial Status",
        "אופן הערכת שווי", "טווח שווי משוער", "הערות לשווי משוער",
    }
    assert "סכום" not in payload  # BUG-DIAMOND-EXPECTED-VALUE-RANGE: never written
    # The production adapter must hand every approved persisted contract field
    # to crm_create_deal, with links represented as primitive IDs.
    assert set(router._inspect(restored.session).tool_inputs) >= {
        "counterparty_contact_id", "deal_type_code", "relationship_type",
        "currency", "commercial_status",
        "estimated_value_basis", "estimated_value_range", "estimated_value_notes",
    }
    assert "amount" not in router._inspect(restored.session).tool_inputs


def test_app_resumes_persisted_state_through_answer_without_agent_fallback():
    import ast
    from pathlib import Path
    app = Path(__file__).parents[1] / "app.py"
    source = app.read_text(encoding="utf-8")
    tree = ast.parse(source)
    run_agent = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_agent")
    assert "commercial_completion" in source
    assert any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "answer_human" for n in ast.walk(run_agent))
    assert "_completion_router.answer_human" in source


def test_direct_and_lead_deal_paths_use_the_same_completion_entity():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert '"create_deal": "deal"' in source
    assert 'router.start(\n            "deal"' in source


def test_app_adapter_names_every_approved_deal_v2_field():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "commercial_completion_routing.py").read_text(encoding="utf-8")
    for field in (
        "counterparty_contact_id", "counterparty_organization_id", "deal_type_code",
        "relationship_type", "currency", "commercial_status", "start_date",
    ):
        assert field in source


def test_direct_deal_does_not_inherit_current_lead_context():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    direct_block = source.split('_completion_entities = {', 1)[1].split('# ── 3.6.', 1)[0]
    assert '"origin_lead"' not in direct_block
    assert "current_lead_record_id" not in direct_block


def test_invalid_answer_keeps_same_completion_session_for_correction():
    queued = []
    router = CommercialCompletionRouter(queue=lambda tool, payload: queued.append((tool, payload)))
    values = _deal()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)
    invalid = router.answer(first.session, first.field_name, "not-a-valid-record")
    assert invalid.outcome == "BLOCK"
    assert invalid.session == first.session
    corrected = router.answer(invalid.session, first.field_name, "recContact2")
    assert corrected.outcome in {"CLARIFY", "TOOL"}


# ── VALIDATION-TEXT regression: an invalid SELECT answer must not leak the
# internal field_name or a raw Python repr of the enum-code tuple into the
# user-visible BLOCK reason.

def test_invalid_select_answer_reason_is_business_safe():
    # "direction" is used here (not "deal_type") because Deal's own SELECT
    # fields were declassified to optional by
    # BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION — this regression is
    # about the general BLOCK-reason-safety behavior for any required
    # SELECT field, not specific to Deal.
    router = CommercialCompletionRouter(queue=lambda *_: None)
    values = {"deal": "recDeal1", "amount": 100, "currency": Currency.ILS}
    first = router.start("charge", current_values=values)
    assert first.field_name == "direction"

    blocked = router.answer(first.session, "direction", "not_a_real_direction")
    assert blocked.outcome == "BLOCK"
    assert "direction" not in blocked.reason
    assert "(" not in blocked.reason and ")" not in blocked.reason
    assert "'" not in blocked.reason
    assert "כיוון תשלום" in blocked.reason  # the business label, not the storage key


def test_restore_is_side_effect_free():
    calls = []
    router = CommercialCompletionRouter(queue=lambda *args: calls.append(args))
    first = router.start("organization", current_values={"organization_name": "Acme"})
    calls.clear()
    restored = router.restore(serialize_completion_session(first.session))
    assert restored.outcome == "BLOCK"
    assert calls == []


# ── BUG 1 regression: answer_human() must never raise when constructing
# CompletionRoute, whatever the resolver returns (unique/ambiguous/no-match/
# create-allowed/canonical). The prior crash was a duplicate `choices`
# keyword — explicit `choices=` plus `**_presentation(...)` which also
# carries `choices` — raised unconditionally regardless of the values.

def _deal_needing_counterparty():
    values = _deal()
    values.pop("counterparty_contact")
    return values


def test_answer_human_unique_match_returns_tool_without_exception():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal_needing_counterparty())

    def lookup(query, scope, limit):
        return [{"id": "recContactX", "fields": {"Name": query}}]

    result = router.answer_human(
        first.session, "Dana Cohen", link_lookup=lookup, scope="tenant1",
    )
    assert result.outcome == "TOOL"


def test_answer_human_ambiguous_match_returns_clarify_without_exception():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal_needing_counterparty())

    def lookup(query, scope, limit):
        return [
            {"id": "recA", "fields": {"Name": "Dana Cohen"}},
            {"id": "recB", "fields": {"Name": "Dana Cohen 2"}},
        ]

    result = router.answer_human(
        first.session, "Dana", link_lookup=lookup, scope="tenant1",
    )
    assert result.outcome == "CLARIFY"
    assert result.choices == ("Dana Cohen", "Dana Cohen 2")


def test_answer_human_no_match_on_a_non_nested_link_returns_block_without_exception():
    """DIAMOND PATH: owner is a LINK field but not in _NESTED_CREATE_ENTITIES
    (only organization/contact offer confirm-to-create) — a no-match answer
    here must still BLOCK exactly like before, proving the confirm-to-create
    branch is scoped to those two entities and nothing else."""
    router = CommercialCompletionRouter(queue=lambda *_: None)
    values = _deal()
    values.pop("owner")
    first = router.start("deal", current_values=values)
    assert first.field_name == "owner"

    result = router.answer_human(
        first.session, "Nobody Here", link_lookup=lambda *_: [], scope="tenant1",
    )
    assert result.outcome == "BLOCK"
    assert result.reason


def test_answer_human_contact_no_picker_choice_defaults_to_contact_create_offer():
    """DIAMOND PATH parity: counterparty_contact with no prior "ארגון"/"איש
    קשר" picker choice defaults to entity="contact" (unchanged default) —
    which now ALSO offers confirm-to-create on no match, matching
    organization's existing behavior rather than blocking."""
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal_needing_counterparty())

    result = router.answer_human(
        first.session, "Nobody Here", link_lookup=lambda *_: [], scope="tenant1",
    )
    assert result.outcome == "CLARIFY"
    assert result.choices == ("כן", "לא")
    assert "איש קשר" in result.reason


def test_answer_human_create_allowed_no_match_returns_without_exception():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal_needing_counterparty())
    org_pick = router.answer_human(first.session, "ארגון", link_lookup=None, scope="")
    assert org_pick.outcome == "CLARIFY"

    result = router.answer_human(
        org_pick.session, "New Org Ltd", link_lookup=lambda *_: [], scope="tenant1",
    )
    assert result.outcome in {"CLARIFY", "BLOCK"}
    assert result.reason


def test_answer_human_canonical_internal_value_returns_without_exception():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal_needing_counterparty())

    result = router.answer_human(
        first.session, "recAlreadyCanonical1", link_lookup=None, scope="",
    )
    assert result.outcome == "TOOL"


# ── DIAMOND PATH: CommercialCompletionRouter.resume_nested() ───────────
# Reload+correlate+fold — the pure-router half of the approval-callback
# resume bridge (app.py's _resolve_diamond_path_continuation() is the other
# half, exercised separately at that layer). Every case here mirrors a
# distinct case in NestedResumeOutcome's own docstring.

def _nested_capable_router():
    calls = []

    def queue(tool, payload, continuation=None):
        calls.append((tool, payload, continuation))
        return None

    return CommercialCompletionRouter(queue=queue), calls


def _queued_nested_contact():
    """Drive a real "no match -> כן -> nested Contact complete -> queued"
    sequence and return (state_dict, nonce) for the parked, nonce-stamped
    session exactly as app.py would persist it via
    serialize_completion_session()."""
    router, calls = _nested_capable_router()
    values = _deal_needing_counterparty()
    first = router.start("deal", current_values=values)
    offer = router.answer_human(
        first.session, "יאיר ממן", link_lookup=lambda *_: [], scope="tenant1",
    )
    ask_phone = router.answer_human(offer.session, "כן", link_lookup=None, scope="")
    queued = router.answer(ask_phone.session, "phone", "0501234567")
    assert queued.outcome == "TOOL"
    _, _, continuation = calls[0]
    return serialize_completion_session(queued.session), continuation["nonce"]


def test_resume_nested_folds_record_id_and_continues_inspection():
    router, _ = _nested_capable_router()
    state, nonce = _queued_nested_contact()

    outcome = router.resume_nested(
        state, expected_nested_entity="contact",
        expected_return_field="counterparty_contact",
        expected_nonce=nonce, canonical_record_id="recContactNEW001",
    )
    assert outcome.status == "resumed"
    assert outcome.route.outcome == "TOOL"
    assert outcome.route.tool_name == "crm_create_deal"
    assert outcome.route.tool_inputs["counterparty_contact_id"] == "recContactNEW001"


def test_resume_nested_mismatch_when_no_session_parked():
    router, _ = _nested_capable_router()
    flat_deal = router.start("deal", current_values=_deal()).session
    state = serialize_completion_session(flat_deal)

    outcome = router.resume_nested(
        state, expected_nested_entity="contact",
        expected_return_field="counterparty_contact",
        expected_nonce="whatever", canonical_record_id="recX",
    )
    assert outcome.status == "mismatch"
    assert outcome.route is None and outcome.session_to_abandon is None
    assert outcome.reason


def test_resume_nested_mismatch_on_wrong_nonce_never_touches_state():
    router, _ = _nested_capable_router()
    state, nonce = _queued_nested_contact()

    outcome = router.resume_nested(
        state, expected_nested_entity="contact",
        expected_return_field="counterparty_contact",
        expected_nonce=nonce + "-different", canonical_record_id="recContactNEW001",
    )
    assert outcome.status == "mismatch"
    assert outcome.session_to_abandon is None  # fail-closed: nothing to clean up


def test_resume_nested_mismatch_on_wrong_entity_or_return_field():
    router, _ = _nested_capable_router()
    state, nonce = _queued_nested_contact()

    wrong_entity = router.resume_nested(
        state, expected_nested_entity="organization",
        expected_return_field="counterparty_contact",
        expected_nonce=nonce, canonical_record_id="recX",
    )
    assert wrong_entity.status == "mismatch"

    wrong_field = router.resume_nested(
        state, expected_nested_entity="contact",
        expected_return_field="counterparty_organization",
        expected_nonce=nonce, canonical_record_id="recX",
    )
    assert wrong_field.status == "mismatch"


def test_resume_nested_corrupted_when_no_evidence_record_id():
    router, _ = _nested_capable_router()
    state, nonce = _queued_nested_contact()

    outcome = router.resume_nested(
        state, expected_nested_entity="contact",
        expected_return_field="counterparty_contact",
        expected_nonce=nonce, canonical_record_id="",
    )
    assert outcome.status == "corrupted"
    assert outcome.route is None
    assert outcome.session_to_abandon is not None
    # The correlated session is exactly the parked one -- abandoning it
    # must return cleanly to the parent, still incomplete on the field.
    abandoned = outcome.session_to_abandon.abandon_nested()
    assert abandoned.active.target_entity == "deal"
    assert len(abandoned.frames) == 1


def test_resume_nested_never_raises_on_malformed_state():
    router, _ = _nested_capable_router()
    outcome = router.resume_nested(
        {"frames": "not-a-list-of-frames"}, expected_nested_entity="contact",
        expected_return_field="counterparty_contact",
        expected_nonce="n", canonical_record_id="recX",
    )
    assert outcome.status == "mismatch"
    assert outcome.reason
