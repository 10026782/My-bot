# test_bug_diamond_optional_enrichment_gates_creation.py —
# BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION regression
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
# This file covers the "offer enrichment after creation" half — the
# required/optional reclassification itself is covered by
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

from airtable_schema import Tables  # noqa: E402

passed = failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


_FRESH_STATE = {
    "stage": "offer", "record_id": "recDealNEW00001",
    "remaining_fields": ["deal_type", "relationship_type", "currency", "commercial_status", "expected_value"],
    "collected": {},
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
    check("persisted state lists all five optional fields",
          written_state["remaining_fields"] == ["deal_type", "relationship_type", "currency",
                                                 "commercial_status", "expected_value"])
    check("persisted state starts with nothing collected", written_state["collected"] == {})


# ══════════════════════════════════════════════════════════════════
print("\n── Case 2: user declines enrichment -> Deal remains valid ──")

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
          advanced_state["remaining_fields"] == _FRESH_STATE["remaining_fields"])


# ══════════════════════════════════════════════════════════════════
print("\n── Case 4: invalid Expected Value -> field-level correction, Deal untouched ──")

_collecting_expected_value = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["expected_value"], "collected": {"Deal Type Code": "service"},
}

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set, \
     patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed") as mock_queue:
    result = app._handle_deal_enrichment_reply(
        dict(_collecting_expected_value), "chat1", "telegram", "לא מספר",
    )
check("invalid value: non-empty field-level message", bool(result))
check("invalid value: message says the Deal already exists", "העסקה כבר נוצרה" in result)
check("invalid value: offers retry or skip", "לדלג" in result)
check("invalid value: marker NOT cleared (still collecting)", not mock_clear.called)
check("invalid value: nothing queued (Deal write untouched)", not mock_queue.called)


# ══════════════════════════════════════════════════════════════════
print("\n── Case: skipping one field advances without adding it to collected ──")

_collecting_two_fields = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["currency", "expected_value"], "collected": {},
}

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set, \
     patch("app._queue_approval_detailed") as mock_queue:
    result = app._handle_deal_enrichment_reply(dict(_collecting_two_fields), "chat1", "telegram", "דלג")
check("skip: non-empty prompt for the next field", bool(result))
check("skip: nothing queued yet (fields remain)", not mock_queue.called)
if mock_set.called:
    _, skipped_state = mock_set.call_args[0]
    check("skip: currency removed from remaining_fields, not added to collected",
          skipped_state["remaining_fields"] == ["expected_value"] and "Currency" not in skipped_state["collected"])


# ══════════════════════════════════════════════════════════════════
print("\n── Case: a valid answer is coerced and accumulated, not yet queued ──")

_collecting_amount_last = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["expected_value"], "collected": {"Currency": "ILS"},
}

with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed", return_value={"message": "⏳ בקשת אישור נשלחה", "ok": True}) as mock_queue:
    result = app._handle_deal_enrichment_reply(
        dict(_collecting_amount_last), "chat1", "telegram", "100000",
    )
check("last field valid: non-empty final reply", bool(result))
check("last field valid: marker cleared (loop finished)", mock_clear.called)
check("last field valid: exactly one airtable_update queued", mock_queue.call_count == 1)
if mock_queue.called:
    _tool, _payload = mock_queue.call_args[0][0], mock_queue.call_args[0][1]
    check("queued tool is airtable_update (canonical Deal update authority, never a second writer)",
          _tool == "airtable_update")
    check("queued payload targets the created Deal's record_id",
          _payload["table"] == Tables.DEALS and _payload["record_id"] == "recDealNEW00001")
    check("queued payload folds BOTH the already-collected and the final field, coerced to a number",
          _payload["fields"].get("Currency") == "ILS" and _payload["fields"].get("סכום") == 100000)
    check("expected_value is coerced to a real number, not left as the free-text string",
          isinstance(_payload["fields"].get("סכום"), float))


# ══════════════════════════════════════════════════════════════════
print("\n── Case 5: enrichment abandoned halfway -> Deal remains created ──")

_collecting_with_partial = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["commercial_status", "expected_value"],
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

# Abandoning with NOTHING collected yet must not queue an empty update at all.
_collecting_nothing_yet = {
    "stage": "collecting", "record_id": "recDealNEW00001",
    "remaining_fields": ["deal_type", "relationship_type", "currency", "commercial_status", "expected_value"],
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
print("\n── exactly one final response per turn ──")

for label, state, text in (
    ("offer/decline", _FRESH_STATE, "לא"),
    ("offer/accept", _FRESH_STATE, "כן"),
    ("collecting/invalid", _collecting_expected_value, "not a number"),
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
print(f"BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
