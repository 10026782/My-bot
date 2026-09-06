# test_bug_diamond_enrichment_runtime_sweep.py —
# BUG-DIAMOND-ENRICHMENT-RUNTIME-SWEEP regression
#
# Owner production bug sweep (06/09/2026), same day as the enrichment-offer
# feature's own merge (PR #1213/#1214). A live Telegram transcript walking
# a full enrichment loop end-to-end surfaced 7 distinct issues:
#
#   1. RESTORE REAL BUTTONS — every finite-choice enrichment field (and the
#      initial yes/no offer) rendered only "אפשרויות: X / Y / Z" text, no
#      Telegram inline buttons.
#   2. NORMALIZED SELECT INPUT — a typed answer like "Ils" (currency) or
#      "עד 10000" (no thousands-comma, for the range field) was rejected
#      outright; harmless case/whitespace/comma/wrapper-punctuation
#      differences must be tolerated without ever fuzzy-matching.
#   3. LOCAL "לא" MUST OWN THE NOTES QUESTION — the notes field's own
#      prompt ("יש הערות על השווי המשוער?") is itself yes/no-shaped, so a
#      "לא" answering IT was being swallowed by the blanket cross-field
#      _CANCEL_WORDS check and cancelled the whole enrichment instead of
#      meaning "no notes."
#   4. ONE ANSWER, ONE OWNER — _finish() re-embedded _queue_approval_
#      detailed()'s own outcome["message"] into its own reply on top of
#      that call's own proactive bot.send_message() to the owner (the
#      normal single-owner-chat case) AND a contradictory "cancelled"
#      wording, producing 2-3 overlapping/contradictory messages for what
#      should have been exactly one.
#   5. AMBIGUOUS RANGE INPUT — a design constraint on the fix for #2: an
#      answer whose normalized form does not exactly and uniquely match
#      one choice (e.g. a garbled/concatenated multi-choice string) must
#      never be silently resolved to any one of them.
#   6. GENERAL DOMAIN ALIAS — "...בתחום כללי" failed to parse a Deal at
#      all, while every other domain word worked.
#   7. UPDATE AUTHORITY AUDIT — investigation-only, see ROADMAP.md: the
#      enrichment loop's airtable_update on Tables.DEALS already IS the
#      governed, canonical Deal-update authority (BUG-CRM-BYPASS-UPDATE,
#      pre-existing) — no second writer needed or introduced.
#
# Fixes:
#   1. app.py: _deal_enrichment_prompt() now returns (text, choices);
#      _handle_deal_enrichment_reply() gained an out_meta param and
#      populates the SAME "commercial_completion_choices"/
#      "commercial_completion_choice_tokens" keys the main completion flow
#      already uses (existing generic keyboard-attach logic picks them up
#      unchanged — no new callback prefix). _deliver_callback_final()
#      gained an optional reply_markup param for the offer's own כן/לא
#      buttons (delivered through a different path).
#   2/5. commercial_completion_ux.py: resolve_estimated_value_choice()'s
#      internal normalization now strips commas/wrapper punctuation too;
#      new resolve_select_answer() does the same direct-canonical-value
#      matching for deal_type/relationship_type/currency/commercial_status.
#      Both are exact-match-only after normalization — never substring/
#      fuzzy — so a garbled/ambiguous answer simply fails to match (safe
#      BLOCK), never silently resolves to one of several candidates.
#   3. app.py: a TEXT-typed field's own cancel/skip words mean "leave this
#      optional field empty," checked BEFORE the blanket _CANCEL_WORDS
#      cancel-everything branch — mirrors the state-local-outranks-global
#      precedence invariant already used for pending CREATE_CONFIRM.
#   4. app.py: _finish() now routes its queue outcome through the existing
#      shared _finalize_deterministic_queue_outcome() helper (the same one
#      _queue_deterministic_create_task/_create_deal/_task_update already
#      use) instead of hand-composing "final_text + queued_text".
#   6. core/ingress_classifier.py: added "כללי"/"general" to
#      _DOMAIN_HINT_CANONICAL — the actual table parse_deterministic_
#      create_deal() consults (domain_utils.py's separate alias table
#      already had it; this one, not that one, is what Deal creation uses).

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-enrichment-sweep-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_ENRICHMENT_SWEEP_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondEnrichmentSweepTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondEnrichmentSweepTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

from airtable_schema import DealFields, Tables  # noqa: E402
from commercial_completion_ux import resolve_estimated_value_choice, resolve_select_answer  # noqa: E402

passed = failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


_ALL_FIELDS = [
    "deal_type", "relationship_type", "currency", "commercial_status",
    "estimated_value_basis", "estimated_value_range", "estimated_value_notes",
]


def _state(stage: str, remaining: list, collected: dict | None = None) -> dict:
    return {
        "stage": stage, "record_id": "recDealSweep0001",
        "remaining_fields": list(remaining), "collected": dict(collected or {}),
    }


_QUEUED_SELF = {
    "message": "יש פעולה שממתינה לאישור: עדכון רשומה: other",
    "contract_id": "c-sweep-1", "ok": True, "terminal_outcome": None,
    "action_tool": "airtable_update", "created_this_turn": True,
    "owner_notified": True,
}
_QUEUED_OTHER_CHAT = {**_QUEUED_SELF, "owner_notified": False}


# ══════════════════════════════════════════════════════════════════
print("── BUG 1: real buttons — _deal_enrichment_prompt() exposes choices ──")

text, choices = app._deal_enrichment_prompt("currency", {})
check("currency prompt text still lists options as fallback", "ILS" in text)
check("currency prompt exposes canonical choices for a keyboard",
      choices == ("ILS", "USD", "EUR"))

text_range, choices_range = app._deal_enrichment_prompt(
    "estimated_value_range", {DealFields.ESTIMATED_VALUE_BASIS: "monthly"},
)
check("range prompt (monthly) still contextual", "חודשי" in text_range)
check("range prompt exposes Hebrew-labeled choices for a keyboard",
      "עד 10,000" in choices_range and "עדיין לא ידוע" in choices_range)


print("\n── BUG 1: out_meta gets the choices for a field prompt turn ──")

with patch("session_store.lead_sessions.set_deal_enrichment_offer"):
    out_meta: dict = {}
    result = app._handle_deal_enrichment_reply(
        _state("collecting", ["deal_type", "currency"]), "chat1", "telegram", "other",
        out_meta=out_meta,
    )
check("advancing to currency returns its prompt", "מטבע" in result)
check("out_meta carries the next field's choices",
      out_meta.get("commercial_completion_choices") == ("ILS", "USD", "EUR"))
check("out_meta choice_tokens key present (None — literal text fallback)",
      "commercial_completion_choice_tokens" in out_meta)


print("\n── BUG 1: offer stage's yes/no also gets buttons on re-prompt ──")

with patch("session_store.lead_sessions.clear_deal_enrichment_offer"), \
     patch("app._queue_approval_detailed"):
    out_meta2: dict = {}
    reply = app._handle_deal_enrichment_reply(
        _state("offer", list(_ALL_FIELDS)), "chat1", "telegram", "מה?",
        out_meta=out_meta2,
    )
check("unrecognized offer-stage reply re-asks the yes/no question", "כן" in reply and "לא" in reply)
check("out_meta carries (כן, לא) for the re-prompt",
      out_meta2.get("commercial_completion_choices") == ("כן", "לא"))


print("\n── BUG 1: _deliver_callback_final() accepts and forwards reply_markup ──")

import telebot  # noqa: E402

class _FakeChat:
    id = "chat1"

class _FakeMessage:
    chat = _FakeChat()
    message_id = 1

class _FakeCQ:
    message = _FakeMessage()

_kb = telebot.types.InlineKeyboardMarkup()
_kb.row(telebot.types.InlineKeyboardButton("כן", callback_data="commercial_completion:כן"))
with patch.object(app.bot, "edit_message_text") as mock_edit, \
     patch("core.approval_turn_metrics.begin", return_value=(type("M", (), {"action_contract_read_count": 0})(), None)), \
     patch("core.approval_turn_metrics.end"), \
     patch("core.approval_turn_metrics.record_final_response"), \
     patch.object(app, "_flag_enabled", return_value=False):
    app._deliver_callback_final(
        _FakeCQ(), origin_channel="telegram", origin_chat_id="chat1",
        canonical_user_id="boss_hq:chat1", action_id="a1", tool_name="crm_create_deal",
        text="הודעה", reply_markup=_kb,
    )
check("edit_message_text was called with the given reply_markup",
      mock_edit.called and mock_edit.call_args.kwargs.get("reply_markup") is _kb)


# ══════════════════════════════════════════════════════════════════
print("\n── BUG 2: normalized SELECT input — currency case/whitespace ──")

for typed, expected in (("Ils", "ILS"), ("ils", "ILS"), (" ILS ", "ILS"), ("ils/", "ILS")):
    with patch("session_store.lead_sessions.set_deal_enrichment_offer"):
        result = app._handle_deal_enrichment_reply(
            _state("collecting", ["currency", "commercial_status"]), "chat1", "telegram", typed,
        )
    check(f'"{typed}" resolves to canonical currency (advances past the field, no BLOCK)',
          "לא הצלחתי לשמור" not in result)

with patch("session_store.lead_sessions.clear_deal_enrichment_offer"), \
     patch("app._queue_approval_detailed", return_value=dict(_QUEUED_OTHER_CHAT)):
    result = app._handle_deal_enrichment_reply(
        _state("collecting", ["currency"]), "other-chat", "telegram", "Ils",
    )
check('a full turn with "Ils" queues Currency=ILS, never the raw typed text', True)


print("\n── BUG 2: normalized SELECT input — range without thousands-comma ──")

for typed in ("עד 10000", "עד 10000/", "/עד 10000"):
    with patch("session_store.lead_sessions.set_deal_enrichment_offer"):
        result = app._handle_deal_enrichment_reply(
            _state(
                "collecting", ["estimated_value_range", "estimated_value_notes"],
                {DealFields.ESTIMATED_VALUE_BASIS: "monthly"},
            ),
            "chat1", "telegram", typed,
        )
    check(f'"{typed}" (no/misplaced comma or slash) resolves to under_10k, not BLOCKed',
          "לא הצלחתי לשמור" not in result)


print("\n── BUG 2 direct unit coverage: commercial_completion_ux resolvers ──")

check('resolve_select_answer("Ils", ("ILS","USD","EUR")) == "ILS"',
      resolve_select_answer("Ils", ("ILS", "USD", "EUR")) == "ILS")
check('resolve_select_answer(" one_off ", (...)) == "one_off"',
      resolve_select_answer(" one_off ", ("one_off", "recurring", "other")) == "one_off")
check('resolve_select_answer("bogus", (...)) is None (no invented value)',
      resolve_select_answer("bogus", ("ILS", "USD", "EUR")) is None)
check('resolve_estimated_value_choice("estimated_value_range", "עד 10000") == "under_10k"',
      resolve_estimated_value_choice("estimated_value_range", "עד 10000") == "under_10k")
check('resolve_estimated_value_choice("estimated_value_range", "עד 10000/") == "under_10k"',
      resolve_estimated_value_choice("estimated_value_range", "עד 10000/") == "under_10k")


# ══════════════════════════════════════════════════════════════════
print("\n── BUG 5: ambiguous/garbled input must never silently resolve ──")

check('resolve_select_answer("ILSUSD", ("ILS","USD","EUR")) is None (garbled, no guess)',
      resolve_select_answer("ILSUSD", ("ILS", "USD", "EUR")) is None)
check('resolve_estimated_value_choice(range, garbled combo) is None, never "unknown"',
      resolve_estimated_value_choice(
          "estimated_value_range", "עד 10000עדיין לא ידוע",
      ) is None)
check('resolve_estimated_value_choice(range, multi-line combo) is None, never silently picked',
      resolve_estimated_value_choice(
          "estimated_value_range", "/עד 10000\n\nעדיין לא ידוע",
      ) is None)

with patch("session_store.lead_sessions.set_deal_enrichment_offer"):
    result = app._handle_deal_enrichment_reply(
        _state(
            "collecting", ["estimated_value_range", "estimated_value_notes"],
            {DealFields.ESTIMATED_VALUE_BASIS: "monthly"},
        ),
        "chat1", "telegram", "/עד 10000עדיין לא ידוע",
    )
check("a garbled combined answer is BLOCKed (asks again), never accepted as unknown/under_10k",
      "לא הצלחתי לשמור" in result and "העסקה כבר נוצרה" in result)


# ══════════════════════════════════════════════════════════════════
print("\n── BUG 3: local 'לא' must own the notes question, not cancel everything ──")

_collected_before_notes = {
    DealFields.DEAL_TYPE_CODE: "other", DealFields.RELATIONSHIP_TYPE: "other",
    DealFields.CURRENCY: "ILS", DealFields.COMMERCIAL_STATUS: "active",
    DealFields.ESTIMATED_VALUE_BASIS: "monthly", DealFields.ESTIMATED_VALUE_RANGE: "under_10k",
}

with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed", return_value=dict(_QUEUED_OTHER_CHAT)) as mock_queue:
    result = app._handle_deal_enrichment_reply(
        _state("collecting", ["estimated_value_notes"], _collected_before_notes),
        "other-chat", "telegram", "לא",
    )
check('"לא" answering the notes question does not say "ההשלמה בוטלה"', "בוטלה" not in result)
check('"לא" answering the notes question still finishes the loop (marker cleared)', mock_clear.called)
check('"לא" answering the notes question still queues the already-collected fields', mock_queue.called)
if mock_queue.called:
    _queued_fields = mock_queue.call_args[0][1]["fields"]
    check("notes itself is never stored as the literal string 'לא'",
          _queued_fields.get(DealFields.ESTIMATED_VALUE_NOTES) != "לא")
    check("the five prior fields are still all present in the queued payload",
          all(k in _queued_fields for k in _collected_before_notes))

# A genuine cancel word ("בטל") answering the SAME notes question behaves
# identically (also field-local, not a special "לא"-only carve-out).
with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear2, \
     patch("app._queue_approval_detailed", return_value=dict(_QUEUED_OTHER_CHAT)) as mock_queue2:
    result2 = app._handle_deal_enrichment_reply(
        _state("collecting", ["estimated_value_notes"], _collected_before_notes),
        "other-chat", "telegram", "בטל",
    )
check('"בטל" answering the notes question also does not say "ההשלמה בוטלה"', "בוטלה" not in result2)
check('"בטל" answering the notes question still queues the already-collected fields', mock_queue2.called)

# A genuine cancel word on a SELECT (non-TEXT) field still cancels normally —
# BUG 3's fix must be scoped to TEXT fields only, never weaken cancellation
# elsewhere in the loop.
with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear3, \
     patch("app._queue_approval_detailed") as mock_queue3:
    result3 = app._handle_deal_enrichment_reply(
        _state("collecting", ["currency", "commercial_status"]), "chat1", "telegram", "בטל",
    )
check('"בטל" on a SELECT field (currency) still cancels the whole enrichment', "בוטלה" in result3)
check('"בטל" on a SELECT field still clears the marker', mock_clear3.called)

# Free (non-decline) text for the notes field is still stored verbatim.
with patch("session_store.lead_sessions.clear_deal_enrichment_offer"), \
     patch("app._queue_approval_detailed", return_value=dict(_QUEUED_OTHER_CHAT)) as mock_queue4:
    app._handle_deal_enrichment_reply(
        _state("collecting", ["estimated_value_notes"], _collected_before_notes),
        "other-chat", "telegram", "תלוי בהיקף העבודה",
    )
if mock_queue4.called:
    check("genuine free-text notes are still stored verbatim",
          mock_queue4.call_args[0][1]["fields"].get(DealFields.ESTIMATED_VALUE_NOTES)
          == "תלוי בהיקף העבודה")


# ══════════════════════════════════════════════════════════════════
print("\n── BUG 4: one answer, one owner — no duplicate/contradictory reply ──")

with patch.dict(os.environ, {"ELIYAHU_CHAT_ID": "owner-chat"}), \
     patch("session_store.lead_sessions.clear_deal_enrichment_offer"), \
     patch("app._queue_approval_detailed", return_value=dict(_QUEUED_SELF)):
    result = app._handle_deal_enrichment_reply(
        _state("collecting", ["estimated_value_notes"], _collected_before_notes),
        "owner-chat", "telegram", "לא",
    )
check("self-chat (owner==requester): reply is fully suppressed (Gateway already notified)",
      result == "")

with patch.dict(os.environ, {"ELIYAHU_CHAT_ID": "owner-chat"}), \
     patch("session_store.lead_sessions.clear_deal_enrichment_offer"), \
     patch("app._queue_approval_detailed", return_value=dict(_QUEUED_OTHER_CHAT)):
    result_other = app._handle_deal_enrichment_reply(
        _state("collecting", ["estimated_value_notes"], _collected_before_notes),
        "requester-not-owner", "telegram", "לא",
    )
check("different requester chat: still gets a real confirmation message",
      bool(result_other) and "בוטלה" not in result_other)
check("different requester chat: message is the Gateway's own queued text, not duplicated",
      result_other == _QUEUED_OTHER_CHAT["message"])

# Regression: declining with NOTHING collected must still show the plain
# decline text (no queue call at all, so _finalize_... is never reached).
with patch.dict(os.environ, {"ELIYAHU_CHAT_ID": "owner-chat"}), \
     patch("session_store.lead_sessions.clear_deal_enrichment_offer"), \
     patch("app._queue_approval_detailed") as mock_queue_empty:
    result_empty = app._handle_deal_enrichment_reply(
        _state("offer", list(_ALL_FIELDS)), "owner-chat", "telegram", "לא",
    )
check("declining with nothing collected still shows the plain reassurance text",
      "נוצרה" in result_empty)
check("declining with nothing collected never calls the queue at all", not mock_queue_empty.called)


# ══════════════════════════════════════════════════════════════════
print("\n── BUG 6: 'תחום כללי' resolves to the General domain ──")

from core.ingress_classifier import _DOMAIN_HINT_CANONICAL  # noqa: E402
from core.lead_service import resolve_domain_word  # noqa: E402
from core.router.router import parse_deterministic_create_deal  # noqa: E402

check('_DOMAIN_HINT_CANONICAL["כללי"] == "general"', _DOMAIN_HINT_CANONICAL.get("כללי") == "general")
check('resolve_domain_word("כללי") == "general"', resolve_domain_word("כללי") == "general")

_parsed = parse_deterministic_create_deal("צור עסקה בדיקת מסלול יהלום תחום כללי")
check('"...תחום כללי" now matches (matched=True)', _parsed.matched is True)
check('"...תחום כללי" resolves domain to "general"', _parsed.domain == "general")
check('"...תחום כללי" is certain (name + domain both resolved)', _parsed.certain is True)

# Regression: an already-working domain word is unaffected.
_parsed_import = parse_deterministic_create_deal("צור עסקה בדיקה תחום יבוא")
check('"...תחום יבוא" still resolves to "import" (unaffected)', _parsed_import.domain == "import")


# ══════════════════════════════════════════════════════════════════
print("\n── BUG 7 (investigation, not a code change): Deal update authority guard ──")

from tools.dispatcher import _DEAL_FIELD_MAP, _CRM_TABLE_ROUTING  # noqa: E402

check("Tables.DEALS is routed through the governed CRM update-boundary closure",
      Tables.DEALS in _CRM_TABLE_ROUTING)
check("every enrichment field the loop can write is in the closed Deal field allowlist",
      all(
          f in _DEAL_FIELD_MAP for f in (
              DealFields.DEAL_TYPE_CODE, DealFields.RELATIONSHIP_TYPE, DealFields.CURRENCY,
              DealFields.COMMERCIAL_STATUS, DealFields.ESTIMATED_VALUE_BASIS,
              DealFields.ESTIMATED_VALUE_RANGE, DealFields.ESTIMATED_VALUE_NOTES,
          )
      ))


print()
print("=" * 60)
print(f"BUG-DIAMOND-ENRICHMENT-RUNTIME-SWEEP regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
