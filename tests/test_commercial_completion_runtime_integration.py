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


def test_link_no_match():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    route = router.answer_human(
        first.session, "Nobody Real", link_lookup=lambda *_: [], scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome == "BLOCK"
    assert calls == []


def test_link_create_allowed_no_match():
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("counterparty_contact")
    first = router.start("deal", current_values=values)

    org_pick = router.answer_human(first.session, "ארגון", link_lookup=None, scope="")
    _assert_well_formed(org_pick)
    assert org_pick.outcome == "CLARIFY"

    route = router.answer_human(
        org_pick.session, "חברה חדשה שלא קיימת בעמ",
        link_lookup=lambda *_: [], scope="tenant1",
    )
    _assert_well_formed(route)
    assert route.outcome in {"CLARIFY", "BLOCK"}
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

def _deal_needing_select_field(field_name):
    values = _deal_values()
    values.pop(field_name)
    router, calls = _no_duplicate_queue_router()
    first = router.start("deal", current_values=values)
    assert first.field_name == field_name
    return router, calls, first


def test_select_valid_button_choice():
    router, calls, first = _deal_needing_select_field("deal_type")
    route = router.answer(first.session, "deal_type", "service")
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert len(calls) == 1


def test_select_valid_typed_choice():
    """Typed free text and a button click both go through the same answer()
    call with the literal choice value — parity is structural, not a
    separate code path to regress independently."""
    router, calls, first = _deal_needing_select_field("deal_type")
    route = router.answer(first.session, "deal_type", "service")
    _assert_well_formed(route)
    assert route.outcome == "TOOL"


def test_select_invalid_choice():
    router, calls, first = _deal_needing_select_field("deal_type")
    route = router.answer(first.session, "deal_type", "not_a_real_choice")
    _assert_well_formed(route)
    assert route.outcome == "BLOCK"
    assert calls == []
    assert "deal_type" not in route.reason  # VALIDATION-TEXT: no storage key


# ══════════════════════════════════════════════════════════════════
# SCALAR
# ══════════════════════════════════════════════════════════════════

def test_scalar_valid_value():
    router, calls, first = _deal_needing_select_field("expected_value")
    route = router.answer(first.session, "expected_value", 500)
    _assert_well_formed(route)
    assert route.outcome == "TOOL"
    assert len(calls) == 1


def test_scalar_invalid_value():
    router, calls, first = _deal_needing_select_field("expected_value")
    route = router.answer(first.session, "expected_value", -5)
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
    router, calls = _no_duplicate_queue_router()
    values = _deal_values()
    values.pop("deal_type")
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
