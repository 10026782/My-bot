# test_bug106_session_determinism.py — BUG-106 (deterministic Session
# record selection for active_lead_candidate)
#
# Live production log: "[SessionStore] load sender=... found_count=18 --
# using first: rec3YS5Zcr2FenX7z" — 18 rows already match the same Sender
# ID filter, and record[0] (whatever Airtable's unsorted API response
# happened to return first) was picked with no schema-based justification.
#
# Prerequisite for BUG-099c: a clarification flow spans TWO separate
# messages/requests. If message 1 (saving active_lead_candidate) and
# message 2 (reading it back) can land on DIFFERENT Session records among
# several duplicates for the same sender, the clarification flow works
# "sometimes" depending on luck, not by design.
#
# Contract Chain findings (see BUG_AUDIT_LOG.md for the full writeup):
#   - No tenant/channel/context-type scoping in the lookup filter at all —
#     Sender-ID-only. Not the cause of the duplicates (confirmed: no
#     multi-worker/multi-thread race is structurally possible under this
#     repo's production start command, `gunicorn app:app`, default single
#     sync worker) — most likely historical accumulation from BUG-063's
#     now-fixed root cause (silent lookup failures triggering
#     POST-instead-of-PATCH), not a live/ongoing creation bug.
#   - No Status field exists on Sessions at all (already documented,
#     BUG-098) — Updated At is the only schema-provided signal for
#     "which record is current."
#
# Fix: _select_canonical_session_record() (session_store.py) — sorts by
# Updated At descending, stable, used by BOTH _find_best_session_in_db()
# (write-path lookup) and _load_from_db() (read-path restore). Same
# record wins in both places, given the same input.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import json
from unittest.mock import MagicMock, patch

from airtable_schema import SessionsFields as SF, Tables
from session_store import PersistentSessionStore, _select_canonical_session_record
from tools import airtable_tools

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


SENDER = "7228089151"


def _record(rec_id: str, updated_at: str = "", state: dict | None = None) -> dict:
    return {
        "id": rec_id,
        "fields": {
            SF.SENDER_ID: SENDER,
            SF.CONTEXT_TYPE: "lead",
            SF.CHANNEL: "telegram",
            SF.UPDATED_AT: updated_at,
            SF.STATE_JSON: json.dumps(state or {}, ensure_ascii=False),
        },
    }


# ── T1-T3: direct unit tests of the selection helper ──────────────────────
print("── Direct: _select_canonical_session_record() ──")

records_scrambled = [
    _record("recOLD", "2026-07-01T00:00:00.000Z"),
    _record("recNEWEST", "2026-07-12T03:50:00.000Z"),
    _record("recMID", "2026-07-05T00:00:00.000Z"),
]
chk("T1: most-recently-updated record wins regardless of input order",
    _select_canonical_session_record(records_scrambled)["id"] == "recNEWEST")

records_no_timestamp = [_record(f"recSESSION{i:02d}") for i in range(18)]
chk("T2: 18 records with NO Updated At all -> stable, first-in-list wins "
    "(backward compatible with pre-BUG-106 behavior, not reshuffled arbitrarily)",
    _select_canonical_session_record(records_no_timestamp)["id"] == "recSESSION00")

records_mixed = [
    _record("recA", ""),
    _record("recB", "2026-07-10T00:00:00.000Z"),
    _record("recC", ""),
]
chk("T3: a real timestamp always beats an empty one, regardless of position",
    _select_canonical_session_record(records_mixed)["id"] == "recB")


# ── T4-T6: session-record-ID CONSISTENCY across two separate "requests" ───
print()
print("── Session consistency: request 1 saves to X, request 2 loads X ──")

# Simulate message 1: an active_lead_candidate write lands on the record
# with the LATEST Updated At among several duplicates for this sender.
duplicates_at_write_time = [
    _record("recDUP_A", "2026-07-01T00:00:00.000Z"),
    _record("recDUP_B", "2026-07-11T12:00:00.000Z"),  # most recently updated
    _record("recDUP_C", "2026-07-03T00:00:00.000Z"),
]

store1 = PersistentSessionStore()
with patch.object(airtable_tools, "airtable_get_records", return_value=duplicates_at_write_time), \
     patch.object(airtable_tools, "airtable_update",
                  return_value={"ok": True, "external_id": "recDUP_B"}) as update_mock:
    existing_id, found_count, reason = store1._find_best_session_in_db(SENDER)

chk("T4: request 1's write-path lookup selects the most-recently-updated duplicate",
    existing_id == "recDUP_B" and found_count == 3 and reason == "patch_existing")

# Simulate message 2: a FRESH store instance (empty RAM — as if this landed
# after a restart/cache-miss, the scenario BUG-106 exists to protect) reads
# back the same sender. recDUP_B's Updated At is now even more recent
# (as it would be after request 1's own _sync_to_db PATCH updated it).
duplicates_at_read_time = [
    _record("recDUP_A", "2026-07-01T00:00:00.000Z"),
    _record("recDUP_B", "2026-07-12T03:51:59.000Z"),  # bumped by request 1's write
    _record("recDUP_C", "2026-07-03T00:00:00.000Z"),
]

store2 = PersistentSessionStore()  # fresh instance == empty RAM cache
with patch.object(airtable_tools, "airtable_get_records", return_value=duplicates_at_read_time):
    restored_session = store2._load_from_db(SENDER)

chk("T5: request 2's read-path restore (fresh store, simulating cache-miss) "
    "loads the SAME record ID that request 1 wrote to — not a different duplicate",
    restored_session is not None and restored_session["record_id"] == "recDUP_B")
chk("T6: this is genuinely the same Airtable record ID across two independent "
    "PersistentSessionStore instances/calls, not merely 'a value was found'",
    existing_id == restored_session["record_id"] == "recDUP_B")


# ── T7: regression guard — existing behavior with found_count=17 (BUG-063's
#        own test) is unaffected by the added sort ─────────────────────────
print()
print("── Regression: BUG-063's own scenario (17 duplicates, no timestamps) ──")

store3 = PersistentSessionStore()
from session_store import _new_session
session = _new_session("real_estate", "telegram")
update_mock2 = MagicMock(return_value={"ok": True, "external_id": "recSESSION00"})
add_mock2 = MagicMock(return_value={"ok": True, "external_id": "recSHOULD_NOT_EXIST"})
seventeen = [_record(f"recSESSION{i:02d}") for i in range(17)]

with patch.object(airtable_tools, "airtable_get_records", return_value=seventeen), \
     patch.object(airtable_tools, "airtable_update", update_mock2), \
     patch.object(airtable_tools, "airtable_add", add_mock2):
    ok = store3._sync_to_db(SENDER, session)

chk("T7: 17 duplicates (no Updated At) still PATCH the first one, never POST",
    ok and update_mock2.call_args.args[1] == "recSESSION00" and not add_mock2.called)


print(f"\n{'='*50}")
print(f"BUG-106 (session record determinism) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
