# test_bug_diamond_optional_enrichment_gates_creation.py —
# BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION +
# BUG-DIAMOND-EXPECTED-VALUE-RANGE regression
#
# Owner architecture correction (06/09/2026): the Deal completion flow had
# drifted into a mandatory full-record gate — deal_type/relationship_type/
# currency/commercial_status/expected_value were required=ALWAYS in
# commercial_completion.py's "deal" EntityContract despite the canonical
# writer (commercial_crm.create_deal()) always treating every one of them
# as an optional kwarg. Core invariant: REQUIRED FIELDS gate creation;
# OPTIONAL FIELDS enrich after creation, and an optional field's failure
# must never invalidate the already-created Deal.
#
# A same-day follow-up correction (BUG-DIAMOND-EXPECTED-VALUE-RANGE)
# replaced the single scalar "expected_value" number with three fields —
# a basis (what the range is denominated in), a bucketed range (never an
# arbitrary number), and optional free-text notes — because a Deal's
# value is often only an estimate and can't be represented honestly as
# one number. This file covers both together since the second change
# only ever touches the same enrichment loop the first one introduced.
#
# The required/optional reclassification itself is covered by
# tests/test_commercial_completion.py, tests/test_commercial_completion_
# routing.py, and tests/test_commercial_completion_runtime_integration.py.
#
# app.py's _offer_deal_enrichment()/_handle_deal_enrichment_reply() persist
# and drive a lightweight offer/collection loop in its OWN session_store
# key ("deal_enrichment_offer" — deliberately separate from
# "commercial_completion", see set_deal_enrichment_offer()'s docstring),
# writing collected fields via ONE accumulated airtable_update() call
# through the exact same _queue_approval_detailed() boundary every other
# deterministic completion uses — never a second Deal writer, never a
# bypassed approval, never a rollback of the already-created Deal.

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-enrichment-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_ENRICHMENT_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondEnrichmentTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondEnrichmentTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

from airtable_schema import DealFields, EngagementDuration, Tables  # noqa: E402

passed = failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


# DIAMOND — BUSINESS FIELDS MIGRATION (06/09/2026): "deal_type"/
# "relationship_type" replaced by "business_deal_type"/"relationship_role"/
# "engagement_duration" in the enrichment offer/loop — see
# DealFields.BUSINESS_DEAL_TYPE's own comment in airtable_schema.py.
_ALL_FIELDS = [
    "business_deal_type", "relationship_role", "engagement_duration",
    "currency", "commercial_status",
    "estimated_value_basis", "estimated_value_range", "estimated_value_notes",
]

_FRESH_STATE = {
    "stage": "offer", "record_id": "recDealNEW00001",
    "remaining_fields": list(_ALL_FIELDS), "collected": {},
}


# ══════════════════════════════════════════════════════════════════
print("── _offer_deal_enrichment() persists the offer and returns the prompt ──")

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set:
    text = app._offer_deal_enrichment("chat1", "telegram", "recDealNEW00001")
check("offer text is non-empty", bool(text))
check("offer text asks the yes/no question", "כן" in text and "לא" in text)
check("offer is persisted with the record_id and full field list", mock_set.called)
if mock_set.called:
    _, written_state = mock_set.call_args[0]
    check("persisted state carries the record_id", written_state["record_id"] == "recDealNEW00001")
    check("persisted state starts at stage=offer", written_state["stage"] == "offer")
    check("persisted state lists all eight optional fields",
          written_state["remaining_fields"] == _ALL_FIELDS)
    check("persisted state starts with nothing collected", written_state["collected"] == {})


# ══════════════════════════════════════════════════════════════════
print("\n── Case 2 (F): user declines enrichment -> Deal remains valid ──")

with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed") as mock_queue:
    result = app._handle_deal_enrichment_reply(dict(_FRESH_STATE), "chat1", "telegram", "לא")
check("decline: non-empty final reply", bool(result))
check("decline: marker cleared", mock_clear.called)
check("decline: no airtable_update queued (nothing was collected)", not mock_queue.called)
check("decline: reply reassures the Deal is unchanged", "נוצרה" in result)


# ══════════════════════════════════════════════════════════════════
print("\n── Case 3: user accepts enrichment -> first optional field is asked ──")

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set, \
     patch("app._queue_approval_detailed") as mock_queue:
    result = app._handle_deal_enrichment_reply(dict(_FRESH_STATE), "chat1", "telegram", "כן")
check("accept: non-empty prompt for the first field", bool(result))
check("accept: advances to stage=collecting, persisted", mock_set.called)
check("accept: does not queue anything yet (no field answered)", not mock_queue.called)
if mock_set.called:
    _, advanced_state = mock_set.call_args[0]
    check("accept: stage is now collecting", advanced_state["stage"] == "collecting")
    check("accept: remaining_fields unchanged (nothing answered yet)",
          advanced_state["remaining_fields"] == _ALL_FIELDS)


# ══════════════════════════════════════════════════════════════════
print("\n── Case A: ongoing Deal already establishes monthly -> basis never asked ──")

_recurring_state = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    # "commercial_status" sits in front of "estimated_value_basis" here,
    # matching the real _DEAL_ENRICHMENT_FIELDS order — engagement_duration
    # is already known (collected), so skipping commercial_status is what
    # advances the loop INTO basis, which is exactly the moment
    # _advance_past_derivable_deal_fields() must fire (it only ever runs
    # when about to ask the NEXT field, never when the user is answering
    # basis directly — that would be an explicit skip, not a derivation).
    "remaining_fields": ["commercial_status", "estimated_value_basis", "estimated_value_range", "estimated_value_notes"],
    "collected": {DealFields.ENGAGEMENT_DURATION: EngagementDuration.ONGOING},
}

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set, \
     patch("app._queue_approval_detailed") as mock_queue:
    # Skipping "commercial_status" (the field in front of basis) advances
    # the loop straight into _advance_past_derivable_deal_fields(), the
    # single shared path every advance (accept/skip/valid-answer) goes
    # through — proving basis is auto-derived, never asked, on this path.
    result = app._handle_deal_enrichment_reply(dict(_recurring_state), "chat1", "telegram", "דלג")
check("A: skipping straight past basis lands on the monthly-range prompt, not a basis question",
      "חודשי" in result and "הצפי מתאר" not in result)
check("A: nothing queued yet (range/notes remain)", not mock_queue.called)
if mock_set.called:
    _, state_after = mock_set.call_args[0]
    check("A: basis was auto-derived and recorded, never asked",
          state_after["collected"].get(DealFields.ESTIMATED_VALUE_BASIS) == "monthly")
    check("A: basis removed from remaining_fields without being answered",
          "estimated_value_basis" not in state_after["remaining_fields"])


# ══════════════════════════════════════════════════════════════════
print("\n── Case B: one-off Deal -> derives one_off, asks one-off range wording ──")

_one_off_state = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["commercial_status", "estimated_value_basis", "estimated_value_range", "estimated_value_notes"],
    "collected": {DealFields.ENGAGEMENT_DURATION: EngagementDuration.ONE_OFF},
}

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set:
    result = app._handle_deal_enrichment_reply(dict(_one_off_state), "chat1", "telegram", "דלג")
check("B: derives one_off and asks the one-off-specific range wording",
      "חד-פעמית" in result)
if mock_set.called:
    _, state_after = mock_set.call_args[0]
    check("B: basis derived from engagement_duration alone",
          state_after["collected"].get(DealFields.ESTIMATED_VALUE_BASIS) == "one_off")


# ══════════════════════════════════════════════════════════════════
print("\n── Case C: basis unknown -> asked once, then range ──")

_unknown_basis_precedes = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["commercial_status", "estimated_value_basis", "estimated_value_range", "estimated_value_notes"],
    "collected": {"Deal Type Code": "commission"},  # neither recurring nor one_off
}

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set:
    # Skipping "commercial_status" advances into basis via the same shared
    # path Cases A/B used — this time derivation returns None, so basis
    # must genuinely be asked, not skipped.
    result = app._handle_deal_enrichment_reply(dict(_unknown_basis_precedes), "chat1", "telegram", "דלג")
check("C: basis is genuinely asked (not auto-derived/skipped) when it can't be derived",
      "הצפי מתאר" in result)
if mock_set.called:
    _, state_after = mock_set.call_args[0]
    check("C: basis is untouched in collected — genuinely pending, not derived",
          DealFields.ESTIMATED_VALUE_BASIS not in state_after["collected"])
    check("C: basis is still the front of remaining_fields (really being asked)",
          state_after["remaining_fields"][0] == "estimated_value_basis")

# Now answer that genuinely-asked basis question with a Hebrew button
# label — it must resolve to the canonical value and move on to range
# with the matching contextual prompt.
_unknown_basis_now_asked = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["estimated_value_basis", "estimated_value_range", "estimated_value_notes"],
    "collected": {"Deal Type Code": "commission"},
}
with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set2:
    answered = app._handle_deal_enrichment_reply(
        dict(_unknown_basis_now_asked), "chat1", "telegram", "סכום כולל",
    )
check("C: answering the basis question with a Hebrew label advances to the range question",
      "טווח" in answered)
if mock_set2.called:
    _, state_after2 = mock_set2.call_args[0]
    check("C: the Hebrew label 'סכום כולל' resolved to canonical 'total'",
          state_after2["collected"].get(DealFields.ESTIMATED_VALUE_BASIS) == "total")
    check("C: total-basis range prompt names 'total', not monthly/one-off wording",
          "כולל" in answered and "חודשי" not in answered)


# ══════════════════════════════════════════════════════════════════
print("\n── Case D: user selects a Hebrew range label -> stored as canonical enum ──")

_collecting_range = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["estimated_value_range"],
    "collected": {"Deal Type Code": "recurring", "אופן הערכת שווי": "monthly"},
}

with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed", return_value={"message": "⏳ בקשת אישור נשלחה", "ok": True}) as mock_queue:
    result = app._handle_deal_enrichment_reply(
        dict(_collecting_range), "chat1", "telegram", "100,000–300,000",
    )
check("D: non-empty final reply", bool(result))
check("D: exactly one airtable_update queued", mock_queue.call_count == 1)
if mock_queue.called:
    _tool, _payload = mock_queue.call_args[0][0], mock_queue.call_args[0][1]
    check("D: queued tool is airtable_update (canonical Deal update authority)", _tool == "airtable_update")
    check("D: Airtable receives the canonical select value '100k_300k', never the Hebrew label",
          _payload["fields"].get(DealFields.ESTIMATED_VALUE_RANGE) == "100k_300k")


# ══════════════════════════════════════════════════════════════════
print("\n── Case E: user selects 'עדיין לא ידוע' -> range=unknown, valid ──")

with patch("session_store.lead_sessions.clear_deal_enrichment_offer"), \
     patch("app._queue_approval_detailed", return_value={"message": "", "ok": True}) as mock_queue:
    result = app._handle_deal_enrichment_reply(
        dict(_collecting_range), "chat1", "telegram", "עדיין לא ידוע",
    )
check("E: non-empty final reply", bool(result))
if mock_queue.called:
    _payload = mock_queue.call_args[0][1]
    check("E: canonical value is 'unknown', accepted as valid",
          _payload["fields"].get(DealFields.ESTIMATED_VALUE_RANGE) == "unknown")


# ══════════════════════════════════════════════════════════════════
print("\n── Case 4/G: invalid basis/range answer -> field-level correction, Deal untouched ──")

_collecting_basis_invalid = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["estimated_value_basis", "estimated_value_range"],
    "collected": {"Deal Type Code": "commission"},
}

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set, \
     patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed") as mock_queue:
    result = app._handle_deal_enrichment_reply(
        dict(_collecting_basis_invalid), "chat1", "telegram", "משהו שלא קיים",
    )
check("invalid basis: non-empty field-level message", bool(result))
check("invalid basis: message says the Deal already exists", "העסקה כבר נוצרה" in result)
check("invalid basis: offers retry or skip", "לדלג" in result)
check("invalid basis: marker NOT cleared (still collecting)", not mock_clear.called)
check("invalid basis: nothing queued (Deal write untouched)", not mock_queue.called)


# ══════════════════════════════════════════════════════════════════
print("\n── Case skip: skipping one field advances without adding it to collected ──")

_collecting_two_fields = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["currency", "estimated_value_notes"], "collected": {},
}

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set, \
     patch("app._queue_approval_detailed") as mock_queue:
    result = app._handle_deal_enrichment_reply(dict(_collecting_two_fields), "chat1", "telegram", "דלג")
check("skip: non-empty prompt for the next field", bool(result))
check("skip: nothing queued yet (fields remain)", not mock_queue.called)
if mock_set.called:
    _, skipped_state = mock_set.call_args[0]
    check("skip: currency removed from remaining_fields, not added to collected",
          skipped_state["remaining_fields"] == ["estimated_value_notes"] and "Currency" not in skipped_state["collected"])


# ══════════════════════════════════════════════════════════════════
print("\n── Case: free-text notes are collected as-is (never a select field) ──")

_collecting_notes_last = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["estimated_value_notes"],
    "collected": {"טווח שווי משוער": "100k_300k"},
}

with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed", return_value={"message": "⏳ בקשת אישור נשלחה", "ok": True}) as mock_queue:
    result = app._handle_deal_enrichment_reply(
        dict(_collecting_notes_last), "chat1", "telegram", "תלוי במספר הצוותים בפועל",
    )
check("notes: non-empty final reply", bool(result))
check("notes: marker cleared (loop finished)", mock_clear.called)
if mock_queue.called:
    _payload = mock_queue.call_args[0][1]
    check("notes: free text stored verbatim in Estimated Value Notes",
          _payload["fields"].get(DealFields.ESTIMATED_VALUE_NOTES) == "תלוי במספר הצוותים בפועל")
    check("H: legacy 'סכום' field is never part of the enrichment payload",
          "סכום" not in _payload["fields"])


# ══════════════════════════════════════════════════════════════════
print("\n── Case 5/G: enrichment abandoned halfway -> Deal remains created ──")

_collecting_with_partial = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["commercial_status", "estimated_value_basis"],
    "collected": {"Deal Type Code": "service", "Relationship Type": "one_off"},
}

with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed", return_value={"message": "⏳ בקשת אישור נשלחה", "ok": True}) as mock_queue:
    result = app._handle_deal_enrichment_reply(
        dict(_collecting_with_partial), "chat1", "telegram", "בטל",
    )
check("abandon mid-flow: non-empty final reply", bool(result))
check("abandon mid-flow: marker cleared", mock_clear.called)
check("abandon mid-flow: whatever was already validated is still queued (not discarded)", mock_queue.called)
if mock_queue.called:
    _payload = mock_queue.call_args[0][1]
    check("abandon mid-flow: only the already-collected fields are queued, nothing more requested",
          set(_payload["fields"]) == {"Deal Type Code", "Relationship Type"})
    check("H: legacy 'סכום' never appears even on abandonment", "סכום" not in _payload["fields"])

# Abandoning with NOTHING collected yet must not queue an empty update at all.
_collecting_nothing_yet = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": list(_ALL_FIELDS),
    "collected": {},
}
with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear2, \
     patch("app._queue_approval_detailed") as mock_queue2:
    result2 = app._handle_deal_enrichment_reply(
        dict(_collecting_nothing_yet), "chat1", "telegram", "בטל",
    )
check("abandon with nothing collected: marker cleared", mock_clear2.called)
check("abandon with nothing collected: no empty airtable_update queued", not mock_queue2.called)


# ══════════════════════════════════════════════════════════════════
print("\n── Case I: no duplicate semantic question once monthly/one_off is known ──")

# If deal_type is ALREADY "recurring" by the time we reach basis, and the
# user is later asked to (re-)answer deal_type itself, the basis question
# must never appear a second time for the SAME loop -- covered structurally
# by _advance_past_derivable_deal_fields() always running as part of
# _persist_and_ask(), the single path every advance goes through (accept /
# skip / valid answer) -- there is no separate code path that could ask
# basis again once it has been derived and removed from remaining_fields.
_post_derivation_state = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["estimated_value_range"],  # basis already derived+removed
    "collected": {"Deal Type Code": "recurring", "אופן הערכת שווי": "monthly"},
}
with patch("session_store.lead_sessions.set_deal_enrichment_offer"):
    result = app._handle_deal_enrichment_reply(dict(_post_derivation_state), "chat1", "telegram", "דלג")
check("I: basis is not re-asked once already derived/removed from remaining_fields",
      "הצפי מתאר" not in result)


# ══════════════════════════════════════════════════════════════════
print("\n── exactly one final response per turn ──")

for label, state, text in (
    ("offer/decline", _FRESH_STATE, "לא"),
    ("offer/accept", _FRESH_STATE, "כן"),
    ("collecting/invalid", _collecting_basis_invalid, "not a real basis"),
    ("collecting/skip", _collecting_two_fields, "דלג"),
    ("collecting/abandon", _collecting_with_partial, "בטל"),
):
    with patch("session_store.lead_sessions.set_deal_enrichment_offer"), \
         patch("session_store.lead_sessions.clear_deal_enrichment_offer"), \
         patch("app._queue_approval_detailed", return_value={"message": "", "ok": True}):
        out = app._handle_deal_enrichment_reply(dict(state), "chat1", "telegram", text)
    check(f"{label}: return value is a single str", isinstance(out, str))


print()
print("=" * 60)
print(f"BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION / "
      f"BUG-DIAMOND-EXPECTED-VALUE-RANGE regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
