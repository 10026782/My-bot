"""Permanent runtime-integration test pack — Diamond Path branch matrix.

Companion to test_commercial_completion_routing.py / test_commercial_completion_ux.py
(which cover the same contracts from other angles). This file exists
specifically to drive CommercialCompletionRouter through every branch in the
audited matrix end to end — LINK / SELECT / SCALAR / SESSION / COUNTERPARTY /
OUTPUT — and assert, for each one:

  1. no uncaught exception
  2. a deterministic outcome (CLARIFY / BLOCK / TOOL, never something else)
  3. the returned session/state is internally consistent
  4. no Agent fallback (there is no Agent in this path at all — this module
     never imports or calls anything from app.py's Claude tool-use loop)
  5. no internal identifiers (record ids, Python field_name) rendered in any
     user-visible text (prompt/reason/user_label/choices)
  6. no duplicate queue submission / duplicate final response for one answer

BUG-1 (duplicate CompletionRoute kwargs), BUG-5 (callback token mapping),
BUG-3 (missing prompts) and the VALIDATION-TEXT fix all live in the modules
this file drives — this is the regression net for the whole audited flow,
not just one bug's specific reproduction.
"""

from __future__ import annotations

import re

from commercial_completion import ENTITY_CONTRACTS, InputType
from commercial_completion_routing import (
    CommercialCompletionRouter,
    CompletionRoute,
    serialize_completion_session,
)

_VALID_OUTCOMES = {"CLARIFY", "BLOCK", "TOOL"}
# The real Airtable record-id shape used across this codebase (see
# commercial_crm._RECORD_ID_RE) — "rec" + exactly 14 alphanumerics. Strict on
# purpose: commercial_completion's own internal-value-passthrough regex is
# looser (`rec` + 1-or-more), which also matches legitimate business words
# like a "recurring" enum choice — not useful for a "no internal identifier
# leaked" check.
_AIRTABLE_RECORD_ID_RE = re.compile(r"^rec[A-Za-z0-9]{14}$")


def _deal_values(**overrides):
    values = {
        "name": "עסקת בדיקה", "domain": "import", "owner": "recOwner00000001",
        "counterparty_contact": "recContact0000001", "deal_type": "service",
        "relationship_type": "one_off", "currency": "ILS",
        "commercial_status": "prospect", "expected_value": 100,
    }
    values.update(overrides)
    return values


def _assert_well_formed(route: CompletionRoute, *, allow_internal_in_reason: bool = False):
    """Properties 1-2-5 from the module docstring, checked on every route."""
    assert isinstance(route, CompletionRoute)
    assert route.outcome in _VALID_OUTCOMES
    for text in (route.prompt, route.user_label, *[str(c) for c in route.choices]):
        if text:
            assert not _AIRTABLE_RECORD_ID_RE.fullmatch(text.strip())
    if not allow_internal_in_reason:
        # No raw Python repr of an internal tuple/enum-code list, and no bare
        # record id, ever reaches a user-visible reason string.
        assert "(" not in route.reason or "אפשרויות" in route.reason
        assert not re.search(r"\brec[A-Za-z0-9]{8,}\b", route.reason)


def _no_duplicate_queue_router():
    calls = []
    router = CommercialCompletionRouter(queue=lambda tool, payload: calls.append((tool, payload)))
    return router, calls


# ══════════════════════════════════════════════════════════════════
# LINK
# ══════════════════════════════════════════════════════════════════

def test_link_exact_unique_match():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    route = router.answer_human(
        first.session, "Dana Cohen",
        link_lookup=lambda q, s, l: [{"id": "recExactMatch001", "fields": {"Name": q}}],
        scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert len(calls) == 1  # exactly one queue submission for this one answer


def test_link_ambiguous_match():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    route = router.answer_human(
        first.session, "Dana",
        link_lookup=lambda q, s, l: [
            {"id": "recA00000000001", "fields": {"Name": "Dana Cohen"}},
            {"id": "recB00000000002", "fields": {"Name": "Dana Levy"}},
        ],
        scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome == "CLARIFY"
    assert route.choices == ("Dana Cohen", "Dana Levy")
    assert calls == []  # a clarification must never itself queue anything


def test_link_no_match_offers_confirm_to_create():
    """DIAMOND PATH: counterparty_contact (defaulting to entity="contact")
    no-match now offers confirm-to-create, matching organization — never a
    bare BLOCK, and never queues anything before the user confirms."""
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    route = router.answer_human(
        first.session, "Nobody Real", link_lookup=lambda *_: [], scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome == "CLARIFY"
    assert route.choices == ("כן", "לא")
    assert calls == []


def test_link_no_match_on_non_nested_entity_still_blocks():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("owner")
    first = router.start("deal", current_values=values)
    assert first.field_name == "owner"

    route = router.answer_human(
        first.session, "Nobody Real", link_lookup=lambda *_: [], scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome == "BLOCK"
    assert calls == []


def _nested_capable_router():
    """Like _no_duplicate_queue_router(), but the queue callable accepts the
    optional 3rd continuation-hint arg _inspect() passes for a nested
    completion — a plain 2-arg lambda would TypeError on that call."""
    calls = []

    def queue(tool, payload, continuation=None):
        calls.append((tool, payload, continuation))
        return None

    router = CommercialCompletionRouter(queue=queue)
    return router, calls


def test_link_no_match_confirm_creates_nested_contact_and_resumes_parent():
    """DIAMOND PATH full lifecycle, Contact: no match -> [כן]/[לא] confirm ->
    כן -> begin_nested() -> ask remaining Contact fields -> nested complete
    -> queued with a continuation hint (never before confirmation) ->
    simulated approval (resume_parent) -> parent Deal completes and queues
    its own final write. Exactly the sequence the owner's design review
    specified, driven at the pure-router level (no app.py/session_store)."""
    router, calls = _nested_capable_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    offer = router.answer_human(
        first.session, "יאיר ממן", link_lookup=lambda *_: [], scope="tenant1",
    )
    _assert_well_formed(offer)
    assert offer.outcome == "CLARIFY"
    assert offer.choices == ("כן", "לא")
    assert "יאיר ממן" in offer.reason and "איש קשר" in offer.reason
    assert calls == []  # no queue submission before confirmation

    ask_phone = router.answer_human(offer.session, "כן", link_lookup=None, scope="")
    _assert_well_formed(ask_phone)
    assert ask_phone.outcome == "CLARIFY"
    assert ask_phone.entity == "contact"
    assert ask_phone.field_name == "phone"
    assert len(ask_phone.session.frames) == 2  # nested frame now exists
    assert calls == []  # still not complete -- no queue submission yet

    queued = router.answer(ask_phone.session, "phone", "0501234567")
    _assert_well_formed(queued)
    assert queued.outcome == "TOOL"
    assert queued.tool_name == "crm_find_or_create_contact"
    assert queued.tool_inputs == {"name": "יאיר ממן", "phone": "0501234567"}
    assert len(calls) == 1
    tool, payload, continuation = calls[0]
    assert tool == "crm_find_or_create_contact" and payload == queued.tool_inputs
    assert continuation == {
        "nested_entity": "contact", "return_field": "counterparty_contact",
        "nonce": continuation["nonce"],
    }
    assert continuation["nonce"]
    assert len(queued.session.frames) == 2  # parked, not collapsed -- awaiting approval
    assert queued.session.active.current_values["_pending_approval_nonce"] == continuation["nonce"]

    # Simulate the approval callback's own resume step (Task: approval
    # callback wiring) directly against the pure session API.
    resumed = queued.session.resume_parent("recContactNEW001")
    assert len(resumed.frames) == 1
    assert resumed.active.resolved_values()["counterparty_contact"] == "recContactNEW001"

    final = router._inspect(resumed)
    _assert_well_formed(final)
    assert final.outcome == "TOOL"
    assert final.tool_name == "crm_create_deal"
    assert final.tool_inputs["counterparty_contact_id"] == "recContactNEW001"
    assert len(calls) == 2  # nested contact queued once, parent deal queued once
    # the parent's own queue call is the plain 2-arg shape -- confirms
    # non-nested queuing is completely unaffected by this feature.
    assert calls[1][2] is None


def test_link_no_match_confirm_creates_nested_organization_and_resumes_parent():
    """Same lifecycle, Organization — proves the bridge is entity-agnostic,
    not something that only happens to work for Contact."""
    router, calls = _nested_capable_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    org_pick = router.answer_human(first.session, "ארגון", link_lookup=None, scope="")
    assert org_pick.outcome == "CLARIFY"

    offer = router.answer_human(
        org_pick.session, "חברה חדשה בעמ", link_lookup=lambda *_: [], scope="tenant1",
    )
    _assert_well_formed(offer)
    assert offer.outcome == "CLARIFY"
    assert offer.choices == ("כן", "לא")
    assert "חברה חדשה בעמ" in offer.reason and "ארגון" in offer.reason

    confirmed = router.answer_human(offer.session, "כן", link_lookup=None, scope="")
    _assert_well_formed(confirmed)
    # organization's only required field (organization_name) was already
    # supplied as the candidate name -- nested completion is immediately
    # complete, straight to TOOL, no further CLARIFY round-trip needed.
    assert confirmed.outcome == "TOOL"
    assert confirmed.tool_name == "crm_find_or_create_organization"
    assert confirmed.tool_inputs == {"display_name": "חברה חדשה בעמ"}
    assert len(calls) == 1
    _, _, continuation = calls[0]
    assert continuation["nested_entity"] == "organization"
    assert continuation["return_field"] == "counterparty_organization"

    resumed = confirmed.session.resume_parent("recNewOrg000001")
    final = router._inspect(resumed)
    assert final.outcome == "TOOL"
    assert final.tool_name == "crm_create_deal"
    assert final.tool_inputs["counterparty_organization_id"] == "recNewOrg000001"
    assert len(calls) == 2


def test_link_no_match_decline_keeps_parent_alive_no_nested_frame():
    """[לא] must never push a nested frame at all — begin_nested() is
    deliberately deferred to confirmation, so declining needs no rollback:
    the parent is simply asked again for the same field."""
    router, calls = _nested_capable_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    offer = router.answer_human(
        first.session, "יאיר ממן", link_lookup=lambda *_: [], scope="tenant1",
    )
    assert offer.outcome == "CLARIFY"

    declined = router.answer_human(offer.session, "לא", link_lookup=None, scope="")
    _assert_well_formed(declined)
    assert declined.outcome == "CLARIFY"
    assert declined.field_name == "counterparty_contact"
    assert len(declined.session.frames) == 1  # never nested
    assert "_ux_pending_nested_create" not in declined.session.active.current_values
    assert calls == []


def test_link_no_match_unrecognized_reply_re_renders_same_confirm_question():
    router, calls = _nested_capable_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    offer = router.answer_human(
        first.session, "יאיר ממן", link_lookup=lambda *_: [], scope="tenant1",
    )
    confused = router.answer_human(offer.session, "מה זה אומר", link_lookup=None, scope="")
    _assert_well_formed(confused)
    assert confused.outcome == "CLARIFY"
    assert confused.choices == ("כן", "לא")
    assert confused.reason == offer.reason  # exact same question, not reinterpreted
    assert len(confused.session.frames) == 1
    assert calls == []


def test_link_already_canonical_internal_value():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    route = router.answer_human(
        first.session, "recAlreadyCanonical01", link_lookup=None, scope="",
    )
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert len(calls) == 1
    # the canonical id itself is legitimate INTERNAL payload data, not
    # user-rendered text — confirm it landed in tool_inputs, not in prompt/reason
    assert "recAlreadyCanonical01" not in route.prompt
    assert "recAlreadyCanonical01" not in route.reason


# ══════════════════════════════════════════════════════════════════
# SELECT
# ══════════════════════════════════════════════════════════════════

# BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION (06/09/2026): Deal's own
# deal_type/expected_value are no longer required=ALWAYS (they're
# post-creation enrichment now — see commercial_completion.py), so they can
# no longer be used here to force a CLARIFY on a specific field. "charge"'s
# "direction" (SELECT) and "amount" (CURRENCY) are still ALWAYS-required
# and exercise the exact same generic answer-mechanics these tests target.

def _charge_values(**overrides):
    values = {"deal": "recDeal0000000001", "direction": "receivable",
              "amount": 100, "currency": "ILS"}
    values.update(overrides)
    return values


def _charge_needing_field(field_name):
    values = _charge_values()
    values.pop(field_name)
    router, calls = _no_duplicate_queue_router()
    first = router.start("charge", current_values=values)
    assert first.field_name == field_name
    return router, calls, first


def test_select_valid_button_choice():
    router, calls, first = _charge_needing_field("direction")
    route = router.answer(first.session, "direction", "receivable")
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert len(calls) == 1


def test_select_valid_typed_choice():
    """Typed free text and a button click both go through the same answer()
    call with the literal choice value — parity is structural, not a
    separate code path to regress independently."""
    router, calls, first = _charge_needing_field("direction")
    route = router.answer(first.session, "direction", "receivable")
    _assert_well_formed(route)
    assert route.outcome == "TOOL"


def test_select_invalid_choice():
    router, calls, first = _charge_needing_field("direction")
    route = router.answer(first.session, "direction", "not_a_real_choice")
    _assert_well_formed(route)
    assert route.outcome == "BLOCK"
    assert calls == []
    assert "direction" not in route.reason  # VALIDATION-TEXT: no storage key


# ══════════════════════════════════════════════════════════════════
# SCALAR
# ══════════════════════════════════════════════════════════════════

def test_scalar_valid_value():
    router, calls, first = _charge_needing_field("amount")
    route = router.answer(first.session, "amount", 500)
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert len(calls) == 1


def test_scalar_invalid_value():
    router, calls, first = _charge_needing_field("amount")
    route = router.answer(first.session, "amount", -5)
    _assert_well_formed(route)
    assert route.outcome == "BLOCK"
    assert calls == []


# ══════════════════════════════════════════════════════════════════
# SESSION
# ══════════════════════════════════════════════════════════════════

def test_session_fresh_start():
    router, calls = _no_duplicate_queue_router()
    route = router.start("deal", current_values=_deal_values())
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert len(calls) == 1


def test_session_restored_continues_correctly():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)
    persisted = serialize_completion_session(first.session)

    restored = router.restore(persisted)
    _assert_well_formed(restored)
    assert restored.outcome == "CLARIFY"
    assert restored.field_name == first.field_name

    route = router.answer_human(
        restored.session, "Dana Cohen",
        link_lookup=lambda q, s, l: [{"id": "recRestored0001", "fields": {"Name": q}}],
        scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert len(calls) == 1


def test_session_invalid_answer_then_correction():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    invalid = router.answer(first.session, first.field_name, "not-a-valid-record")
    _assert_well_formed(invalid)
    assert invalid.outcome == "BLOCK"
    assert invalid.session == first.session  # state preserved, not advanced

    corrected = router.answer(invalid.session, first.field_name, "recCorrected00001")
    _assert_well_formed(corrected)
    assert corrected.outcome == "TOOL"
    assert len(calls) == 1  # the invalid attempt never queued anything


def test_session_completed_restore():
    router, calls = _no_duplicate_queue_router()
    first = router.start("organization", current_values={"organization_name": "Acme"})
    assert first.outcome == "TOOL"
    calls.clear()

    restored = router.restore(serialize_completion_session(first.session))
    _assert_well_formed(restored)
    assert restored.outcome == "BLOCK"
    assert calls == []  # restoring an already-complete session must not re-queue


# ══════════════════════════════════════════════════════════════════
# COUNTERPARTY
# ══════════════════════════════════════════════════════════════════

def test_counterparty_contact_path():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    pick = router.answer_human(first.session, "איש קשר", link_lookup=None, scope="")
    _assert_well_formed(pick)
    assert pick.outcome == "CLARIFY"

    route = router.answer_human(
        pick.session, "Dana Cohen",
        link_lookup=lambda q, s, l: [{"id": "recContactPath001", "fields": {"Name": q}}],
        scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert "counterparty_contact_id" in route.tool_inputs
    assert len(calls) == 1


def test_counterparty_organization_path():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    pick = router.answer_human(first.session, "ארגון", link_lookup=None, scope="")
    _assert_well_formed(pick)
    assert pick.outcome == "CLARIFY"

    route = router.answer_human(
        pick.session, "Acme Ltd",
        link_lookup=lambda q, s, l: [{"id": "recOrgPath0000001", "fields": {"Organization Name": q}}],
        scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert "counterparty_organization_id" in route.tool_inputs
    assert "counterparty_contact_id" not in route.tool_inputs
    assert len(calls) == 1


# ══════════════════════════════════════════════════════════════════
# OUTPUT
# ══════════════════════════════════════════════════════════════════

def test_output_clarify():
    # deal_type is optional now (BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-
    # CREATION) — drop a still business-required field (owner) instead to
    # exercise the same CLARIFY-output-shape contract.
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("owner")
    route = router.start("deal", current_values=values)
    _assert_well_formed(route)
    assert route.outcome == "CLARIFY"
    assert calls == []


def test_output_block():
    router, calls = _no_duplicate_queue_router()
    route = router.start("allocation_rule")  # not in SUPPORTED_COMPLETION_ENTITIES
    _assert_well_formed(route)
    assert route.outcome == "BLOCK"
    assert calls == []


def test_output_tool_queues_exactly_once():
    router, calls = _no_duplicate_queue_router()
    route = router.start("deal", current_values=_deal_values())
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert calls == [(route.tool_name, dict(route.tool_inputs))]
