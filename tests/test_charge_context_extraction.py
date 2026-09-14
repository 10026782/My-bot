"""BUG-CHARGE-TERM-BYPASS follow-up #2 regression: a Deal/Payment Term/Lead
already named in the ORIGINAL message that starts a term-based Charge
completion must be extracted and handed to the resolver, never silently
dropped and re-asked as a blank free-text question.
"""

from unittest.mock import patch

from core.router.router import parse_deterministic_charge_context
from commercial_completion_routing import CommercialCompletionRouter
from airtable_schema import PaymentTermCalcType, PaymentTermFields, Currency


LIVE_CANARY_TEXT = (
    "צור חיוב לעסקה קבלנים דרך עמי מערכות "
    "לפי תנאי עמלת פוסידון — 10% לאחר קיזוז רכישת ציוד שחור "
    "עבור מאור אבוחצירה"
)


def test_extracts_deal_term_and_lead_from_the_exact_live_canary_text():
    result = parse_deterministic_charge_context(LIVE_CANARY_TEXT)
    assert result.deal_ref == "קבלנים דרך עמי מערכות"
    assert result.term_ref == "עמלת פוסידון — 10% לאחר קיזוז רכישת ציוד שחור"
    assert result.lead_ref == "מאור אבוחצירה"


def test_extracts_deal_only_when_no_other_markers_present():
    result = parse_deterministic_charge_context("צור חיוב לעסקה קבלנים דרך עמי מערכות")
    assert result.deal_ref == "קבלנים דרך עמי מערכות"
    assert result.term_ref is None
    assert result.lead_ref is None


def test_no_markers_extracts_nothing():
    result = parse_deterministic_charge_context("צור חיוב")
    assert result.deal_ref is None
    assert result.term_ref is None
    assert result.lead_ref is None


def test_bare_alone_marker_variant_still_resolves_term():
    # "לפי" alone (no "תנאי") is still recognized as the Term marker.
    result = parse_deterministic_charge_context(
        "צור חיוב לעסקה עסקת בדיקה לפי עמלת בדיקה"
    )
    assert result.deal_ref == "עסקת בדיקה"
    assert result.term_ref == "עמלת בדיקה"


# ── End-to-end: app.py's actual chase mechanism, exercised directly against
# CommercialCompletionRouter (mirrors _prefill_charge_context() in app.py,
# without importing the Flask app module) ──────────────────────────────────

DEAL_ID = "recDealPoseidon01"
TERM_ID = "recTermPoseidon01"


def _term_fields(calc_type=PaymentTermCalcType.PERCENTAGE, deal_id=DEAL_ID):
    return {
        PaymentTermFields.DEAL: [deal_id],
        PaymentTermFields.CALC_TYPE_CODE: calc_type,
        PaymentTermFields.RATE_PCT: 10,
        PaymentTermFields.CURRENCY: Currency.ILS,
    }


def _prefill(router, result, lookup):
    """Mirrors app.py's _prefill_charge_context() exactly, without the
    Flask/Telegram dependency, so this test exercises the real algorithm."""
    seen = set()
    while result.outcome == "CLARIFY" and result.session is not None:
        refs = dict(result.session.active.current_values.get("_charge_context_refs") or {})
        ref_text = refs.get(result.field_name)
        if not ref_text or result.field_name in seen:
            break
        seen.add(result.field_name)
        result = router.answer_human(result.session, ref_text, link_lookup=lookup, scope="tenant1")
    return result


def test_deal_and_term_auto_resolve_leaving_only_the_basis_question():
    refs = {
        "deal": "קבלנים דרך עמי מערכות",
        "billing_term": "עמלת פוסידון — 10% לאחר קיזוז רכישת ציוד שחור",
    }

    def lookup(query, scope, limit):
        entity, _, _rest = scope.partition(":")
        if entity == "deal":
            return [{"id": DEAL_ID, "fields": {"שם העסקה": query}}]
        if entity == "payment_term":
            return [{"id": TERM_ID, "fields": {"Name": query}}]
        return []

    queued = []
    router = CommercialCompletionRouter(
        queue=lambda tool, payload, hint=None: queued.append((tool, payload))
    )
    with patch("tools.airtable_read_adapter.get_record_fields", return_value=_term_fields()):
        first = router.start(
            "charge_from_term",
            current_values={"owner": "owner1", "_charge_context_refs": refs},
        )
        result = _prefill(router, first, lookup)
        assert result.outcome == "CLARIFY"
        assert result.field_name == "basis_value"
        assert result.prompt == "מה בסיס החישוב לעמלה?"

        final = router.answer(result.session, "basis_value", 23418.15)
    assert final.outcome == "TOOL"
    assert final.tool_name == "crm_create_charge_from_term"
    assert final.tool_inputs == {
        "deal_id": DEAL_ID, "payment_term_id": TERM_ID, "basis_value": 23418.15,
    }
    assert queued and queued[0][0] == "crm_create_charge_from_term"


def test_ambiguous_deal_then_manual_retype_still_auto_resolves_the_term():
    """Secondary issue: once the Deal needs disambiguation and the user
    manually retypes it, the Term reference from the ORIGINAL message must
    still auto-resolve on the very next turn — never re-asked."""
    refs = {
        "deal": "קבלנים דרך עמי מערכות",
        "billing_term": "עמלת פוסידון — 10% לאחר קיזוז רכישת ציוד שחור",
    }

    def ambiguous_deal_lookup(query, scope, limit):
        return [
            {"id": "recDealA", "fields": {"שם העסקה": "קבלנים דרך עמי מערכות - צפון"}},
            {"id": "recDealB", "fields": {"שם העסקה": "קבלנים דרך עמי מערכות - דרום"}},
        ]

    def unique_deal_lookup(query, scope, limit):
        return [{"id": DEAL_ID, "fields": {"שם העסקה": query}}]

    def term_lookup(query, scope, limit):
        return [{"id": TERM_ID, "fields": {"Name": query}}]

    from commercial_completion_routing import serialize_completion_session

    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start(
        "charge_from_term",
        current_values={"owner": "owner1", "_charge_context_refs": refs},
    )
    turn1 = _prefill(router, first, ambiguous_deal_lookup)
    assert turn1.outcome == "CLARIFY" and turn1.field_name == "deal"
    assert turn1.choices  # real ambiguous choices shown, not a silent pick

    persisted = serialize_completion_session(turn1.session)
    restored = router.restore(persisted)
    answered = router.answer_human(
        restored.session, "קבלנים דרך עמי מערכות",
        link_lookup=unique_deal_lookup, scope="tenant1",
    )
    assert answered.field_name == "billing_term"

    with patch("tools.airtable_read_adapter.get_record_fields", return_value=_term_fields()):
        turn2 = _prefill(router, answered, term_lookup)
    assert turn2.outcome == "CLARIFY"
    assert turn2.field_name == "basis_value"


def test_no_refs_seeded_falls_back_to_normal_questions_unchanged():
    """No "_charge_context_refs" marker at all (e.g. a bare "צור חיוב") must
    behave exactly as before this fix — normal per-field CLARIFY, no chase."""
    router = CommercialCompletionRouter(queue=lambda *_: None)
    result = router.start("charge_from_term", current_values={"owner": "owner1"})
    assert result.outcome == "CLARIFY"
    assert result.field_name == "deal"
    # _prefill's loop is a no-op here since there is no marker to read.
    chased = _prefill(router, result, lambda *_: [])
    assert chased is result


def test_app_wires_the_prefill_chase_at_both_completion_entry_points():
    """Structural check that app.py actually calls _prefill_charge_context()
    right after both the initial start() and the persisted-session
    answer_human() continuation — a regression here would silently restore
    the exact live bug (Deal/Term named in the original message ignored)
    without any of the pure-router tests above ever catching it, since they
    exercise the router directly rather than through app.py's wiring."""
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "parse_deterministic_charge_context" in source
    assert '_current_values["_charge_context_refs"]' in source
    assert source.count("_prefill_charge_context(_completion_router, _completion_result") >= 2
