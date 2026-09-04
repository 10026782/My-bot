# test_bug_session_dup_canonicalization.py — BUG-SESSION-DUP regression
#
# Owner-decided SESSION CANONICALIZATION fix (04/09/2026): production had 18
# Sessions rows for one Sender ID, 17 of them stale (June 25 - July 4)
# debris, one of them on a DIFFERENT channel (telegram) than the other 17
# (whatsapp) despite sharing the identical raw Sender ID string — the live
# dedup lookup was Sender-ID-only, with no channel scoping at all, and
# SessionsFields.SESSION_ID (a schema-defined canonical-key field) was never
# written or read by any code.
#
# This suite locks in the fix: session_store._canonical_session_key()
# (tenant:channel:sender), Session ID now stamped on every write, and
# channel-scoped lookup/creation so a same-sender-different-channel row can
# never be silently reused, created over, or resurrected.

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from airtable_schema import SessionsFields as SF, Tables
from session_store import (
    PersistentSessionStore,
    _canonical_session_key,
    _new_session,
)
from tools import airtable_tools

SENDER = "7228089151"


def _record(record_id: str, channel: str, updated_at: str = "", session_id: str = "") -> dict:
    fields = {SF.SENDER_ID: SENDER, SF.CHANNEL: channel, SF.CONTEXT_TYPE: "lead", SF.STATE_JSON: "{}"}
    if updated_at:
        fields[SF.UPDATED_AT] = updated_at
    if session_id:
        fields[SF.SESSION_ID] = session_id
    return {"id": record_id, "fields": fields}


def test_canonical_key_is_deterministic_and_channel_scoped():
    assert _canonical_session_key("whatsapp", SENDER) == f"boss_hq:whatsapp:{SENDER}"
    assert _canonical_session_key("telegram", SENDER) == f"boss_hq:telegram:{SENDER}"
    assert _canonical_session_key("whatsapp", SENDER) != _canonical_session_key("telegram", SENDER)


# ── Write behavior: 0 / 1 / >1 matches ────────────────────────────────────

def test_zero_matches_creates_one_new_row():
    store = PersistentSessionStore()
    session = _new_session("real_estate", "whatsapp")
    add = MagicMock(return_value={"ok": True, "external_id": "recNEW1"})
    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", add), \
         patch.object(airtable_tools, "airtable_update") as update:
        assert store._sync_to_db(SENDER, session)
    add.assert_called_once()
    update.assert_not_called()
    assert add.call_args.args[1][SF.SESSION_ID] == f"boss_hq:whatsapp:{SENDER}"


def test_one_match_updates_it_never_creates():
    store = PersistentSessionStore()
    session = _new_session("real_estate", "whatsapp")
    existing = [_record("recEXIST1", "whatsapp")]
    update = MagicMock(return_value={"ok": True, "external_id": "recEXIST1"})
    add = MagicMock()
    with patch.object(airtable_tools, "airtable_get_records", return_value=existing), \
         patch.object(airtable_tools, "airtable_update", update), \
         patch.object(airtable_tools, "airtable_add", add):
        assert store._sync_to_db(SENDER, session)
    update.assert_called_once()
    assert update.call_args.args[1] == "recEXIST1"
    add.assert_not_called()
    assert session["record_id"] == "recEXIST1"


def test_many_matches_choose_canonical_deterministically_never_creates():
    store = PersistentSessionStore()
    session = _new_session("real_estate", "whatsapp")
    dupes = [
        _record("recOLD", "whatsapp", updated_at="2026-06-25T10:00:00.000Z"),
        _record("recNEWEST", "whatsapp", updated_at="2026-07-04T22:17:26.000Z"),
        _record("recMID", "whatsapp", updated_at="2026-06-30T12:00:00.000Z"),
    ]
    update = MagicMock(return_value={"ok": True, "external_id": "recNEWEST"})
    add = MagicMock()
    with patch.object(airtable_tools, "airtable_get_records", return_value=dupes), \
         patch.object(airtable_tools, "airtable_update", update), \
         patch.object(airtable_tools, "airtable_add", add):
        assert store._sync_to_db(SENDER, session)
    assert update.call_args.args[1] == "recNEWEST"
    add.assert_not_called()


# ── Cross-channel isolation ───────────────────────────────────────────────

def test_same_sender_different_channel_never_reused_by_write_path():
    """The exact production shape: 17 whatsapp rows + 1 telegram row, same
    raw Sender ID. A whatsapp write must never match/patch the telegram row,
    and vice versa — this is what the Sender-ID-only formula got wrong."""
    store = PersistentSessionStore()
    session = _new_session("real_estate", "telegram")
    whatsapp_only = [_record("recWA1", "whatsapp"), _record("recWA2", "whatsapp")]

    captured_formula = {}

    def fake_get_records(table, formula):
        captured_formula["formula"] = formula
        # A real Airtable AND(Sender, Channel) filter would return [] here
        # since none of the fixture rows are Channel=telegram.
        return [] if "telegram" in formula else whatsapp_only

    add = MagicMock(return_value={"ok": True, "external_id": "recTG_NEW"})
    with patch.object(airtable_tools, "airtable_get_records", side_effect=fake_get_records), \
         patch.object(airtable_tools, "airtable_add", add), \
         patch.object(airtable_tools, "airtable_update") as update:
        assert store._sync_to_db(SENDER, session)

    assert "telegram" in captured_formula["formula"]
    add.assert_called_once()  # created a NEW telegram row, never patched a whatsapp one
    update.assert_not_called()
    assert session["record_id"] == "recTG_NEW"


def test_get_or_create_does_not_reuse_a_different_channels_ram_session():
    store = PersistentSessionStore()
    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", return_value={"ok": True, "external_id": "recWA"}):
        wa_session = store.get_or_create(SENDER, "real_estate", "whatsapp")
    assert wa_session["channel"] == "whatsapp"

    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", return_value={"ok": True, "external_id": "recTG"}):
        tg_session = store.get_or_create(SENDER, "real_estate", "telegram")
    assert tg_session["channel"] == "telegram"
    assert tg_session is not wa_session  # never handed back the other channel's object


# ── Duplicate detection is surfaced, not silently swallowed forever ──────

def test_duplicates_are_logged_with_a_greppable_signal(caplog):
    store = PersistentSessionStore()
    dupes = [_record("recA", "whatsapp"), _record("recB", "whatsapp"), _record("recC", "telegram")]
    with caplog.at_level(logging.WARNING), \
         patch.object(airtable_tools, "airtable_get_records", return_value=dupes):
        store._find_best_session_in_db(SENDER)
    assert "SESSION_DUPLICATE_DETECTED" in caplog.text
    assert "cross_channel=True" in caplog.text  # whatsapp + telegram in the same match set


def test_stale_duplicate_cannot_win_over_canonical():
    store = PersistentSessionStore()
    stale = _record("recSTALE", "whatsapp", updated_at="2026-06-25T10:00:00.000Z")
    canonical = _record("recCANON", "whatsapp", updated_at="2026-09-04T09:24:08.322Z")
    with patch.object(airtable_tools, "airtable_get_records", return_value=[stale, canonical]):
        selected, count, reason = store._find_best_session_in_db(SENDER, channel="whatsapp")
    assert selected == "recCANON"
    assert count == 2
    assert reason == "patch_existing"


# ── Legacy compatibility: rows without Session ID still resolve ──────────

def test_legacy_row_without_session_id_field_still_found_and_patched():
    store = PersistentSessionStore()
    session = _new_session("real_estate", "whatsapp")
    legacy_row = _record("recLEGACY", "whatsapp")  # no SF.SESSION_ID key at all
    assert SF.SESSION_ID not in legacy_row["fields"]
    update = MagicMock(return_value={"ok": True, "external_id": "recLEGACY"})
    with patch.object(airtable_tools, "airtable_get_records", return_value=[legacy_row]), \
         patch.object(airtable_tools, "airtable_update", update), \
         patch.object(airtable_tools, "airtable_add") as add:
        assert store._sync_to_db(SENDER, session)
    update.assert_called_once()
    assert update.call_args.args[1] == "recLEGACY"
    add.assert_not_called()
    # the row is healed forward: this same write now stamps a canonical key
    assert update.call_args.args[2][SF.SESSION_ID] == f"boss_hq:whatsapp:{SENDER}"


# ── Repeated writes / restart / no accidental duplication ────────────────

def test_repeated_writes_reuse_the_same_record():
    store = PersistentSessionStore()
    session = _new_session("real_estate", "whatsapp")
    add = MagicMock(return_value={"ok": True, "external_id": "recFIRST"})
    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", add):
        store._sync_to_db(SENDER, session)
    assert session["record_id"] == "recFIRST"

    update = MagicMock(return_value={"ok": True, "external_id": "recFIRST"})
    with patch.object(airtable_tools, "airtable_get_records") as get_records, \
         patch.object(airtable_tools, "airtable_update", update), \
         patch.object(airtable_tools, "airtable_add") as add2:
        for _ in range(5):
            store._sync_to_db(SENDER, session)
    # record_id is already known after the first sync — subsequent syncs
    # PATCH directly and never re-query or re-create.
    get_records.assert_not_called()
    add2.assert_not_called()
    assert update.call_count == 5


def test_restart_cache_loss_does_not_create_duplicate():
    """Simulates a process restart: a fresh PersistentSessionStore (empty
    RAM) syncing for a sender that already has exactly one row in the DB
    must PATCH it, never POST a second one — this is the core BUG-NEW-12
    guarantee, re-asserted here as part of the canonicalization suite."""
    store_after_restart = PersistentSessionStore()
    session = _new_session("real_estate", "whatsapp")  # record_id == "" — RAM has no memory of recEXIST1
    existing = [_record("recEXIST1", "whatsapp")]
    update = MagicMock(return_value={"ok": True, "external_id": "recEXIST1"})
    add = MagicMock()
    with patch.object(airtable_tools, "airtable_get_records", return_value=existing), \
         patch.object(airtable_tools, "airtable_update", update), \
         patch.object(airtable_tools, "airtable_add", add):
        assert store_after_restart._sync_to_db(SENDER, session)
    update.assert_called_once()
    add.assert_not_called()
    assert session["record_id"] == "recEXIST1"


def test_simultaneous_writes_do_not_create_two_active_sessions():
    """Two independent store instances (simulating two concurrent
    request-handling contexts with no shared RAM) both syncing for the same
    sender against a DB that already has a canonical row must both land on
    that same row — never each creating their own."""
    existing = [_record("recCANON", "whatsapp", updated_at="2026-09-04T09:00:00.000Z")]
    results = []
    for _ in range(2):
        store = PersistentSessionStore()
        session = _new_session("real_estate", "whatsapp")
        update = MagicMock(return_value={"ok": True, "external_id": "recCANON"})
        add = MagicMock()
        with patch.object(airtable_tools, "airtable_get_records", return_value=existing), \
             patch.object(airtable_tools, "airtable_update", update), \
             patch.object(airtable_tools, "airtable_add", add):
            store._sync_to_db(SENDER, session)
        results.append((session["record_id"], add.called))
    assert results == [("recCANON", False), ("recCANON", False)]


# ── commercial_completion survives normal resume; explicit new state replaces stale ──

def test_commercial_completion_survives_normal_resume():
    store = PersistentSessionStore()
    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", return_value={"ok": True, "external_id": "recCC1"}), \
         patch.object(airtable_tools, "airtable_update", return_value={"ok": True, "external_id": "recCC1"}):
        store.set_commercial_completion(SENDER, {"frames": [{"target_entity": "deal"}]})
        restored = store.get_commercial_completion(SENDER)
    assert restored == {"frames": [{"target_entity": "deal"}]}


def test_new_explicit_completion_cleanly_replaces_stale_one():
    store = PersistentSessionStore()
    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", return_value={"ok": True, "external_id": "recCC2"}), \
         patch.object(airtable_tools, "airtable_update", return_value={"ok": True, "external_id": "recCC2"}):
        store.set_commercial_completion(SENDER, {"frames": [{"target_entity": "deal"}]})
        # A fresh, unambiguous intent (e.g. a new "צור ארגון" completion)
        # must fully replace the stale one, never merge with it.
        store.set_commercial_completion(SENDER, {"frames": [{"target_entity": "organization"}]})
        restored = store.get_commercial_completion(SENDER)
    assert restored == {"frames": [{"target_entity": "organization"}]}
    assert "deal" not in str(restored)
