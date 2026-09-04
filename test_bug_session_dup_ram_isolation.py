# test_bug_session_dup_ram_isolation.py — BUG-SESSION-DUP-RAM regression
#
# PR #1203 review follow-up (04/09/2026). test_bug_session_dup_canonicalization.py
# locked in that the DB layer (Sessions table reads/writes) is scoped by
# tenant+channel+sender — but PersistentSessionStore's RAM cache
# (self._store) was still found keyed by bare sender only. A WhatsApp and a
# Telegram identity that happen to share the same raw sender-id string
# (the exact production shape that produced the 18 duplicate rows this repo
# already cleaned up once) could silently overwrite each other's RAM slot:
# a later request on one channel could read/mutate the OTHER channel's live
# session object in RAM, even though the eventual _sync_to_db() write would
# still correctly target that session's own Session ID — the DB layer being
# scoped does not help if the STATE it persists was already cross-channel
# contaminated before the write ever happened.
#
# The fix (session_store.py): the RAM cache key now uses the same canonical
# shape as persistence (tenant:channel:sender, via _canonical_session_key())
# whenever the channel is known — either passed explicitly (get_or_create())
# or supplied implicitly via set_request_channel(), a ContextVar stamped
# once per request at each of app.py's real channel-aware entry points
# (run_agent(), the Telegram webhook impl, the Twilio/Meta WhatsApp webhook
# impls) — see session_store.py's BUG-SESSION-DUP-RAM comment block for why
# that was chosen over threading `channel` through this store's ~20 other
# public methods and their ~60 call sites across the codebase.
#
# This suite proves the RAM-layer invariant the DB-layer suite could not:
# no request may read or mutate a Session belonging to another channel.

from __future__ import annotations

from unittest.mock import patch

from airtable_schema import SessionsFields as SF
from session_store import (
    PersistentSessionStore,
    _canonical_session_key,
    set_request_channel,
)
from tools import airtable_tools

SENDER = "7228089151"  # the exact production sender-id from BUG-SESSION-DUP


def _tracking_airtable():
    """Every _sync_to_db() call POSTs once (no pre-existing rows); records
    are tracked with the channel visible in the id so assertions can tell
    which channel's row each write actually targeted."""
    add_calls = []
    update_calls = []

    def fake_add(table, fields):
        rec_id = f"rec{fields[SF.CHANNEL].upper()}NEW"
        add_calls.append(dict(fields, _record_id=rec_id))
        return {"ok": True, "external_id": rec_id}

    def fake_update(table, record_id, fields):
        update_calls.append(dict(fields, _record_id=record_id))
        return {"ok": True, "external_id": record_id}

    return add_calls, update_calls, fake_add, fake_update


def _writes_for(calls, channel: str) -> list[dict]:
    return [c for c in calls if c.get(SF.CHANNEL) == channel]


# ── The exact required sequence (Telegram created first) ──────────────────

def test_cross_channel_ram_isolation_telegram_then_whatsapp():
    store = PersistentSessionStore()
    add_calls, update_calls, fake_add, fake_update = _tracking_airtable()

    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", side_effect=fake_add), \
         patch.object(airtable_tools, "airtable_update", side_effect=fake_update):

        # 1. create Telegram session for sender X
        set_request_channel("telegram")
        tg = store.get_or_create(SENDER, domain="general", channel="telegram")

        # 2. create WhatsApp session for the same sender X
        set_request_channel("whatsapp")
        wa = store.get_or_create(SENDER, domain="real_estate", channel="whatsapp")

        assert tg is not wa
        assert tg["channel"] == "telegram" and wa["channel"] == "whatsapp"

        # 3. mutate Telegram commercial_completion
        set_request_channel("telegram")
        store.set_commercial_completion(SENDER, {"frames": [{"target_entity": "deal"}]})

        # 4. assert WhatsApp session unchanged
        set_request_channel("whatsapp")
        assert store.get_commercial_completion(SENDER) is None
        assert wa.get("commercial_completion") is None

        # 5. mutate WhatsApp state
        store.update_step(SENDER, step=2, field_name="city", answer="תל אביב")

        # 6. assert Telegram session unchanged
        set_request_channel("telegram")
        assert tg.get("step") == 0
        assert tg.get("answers", {}).get("city") is None
        assert store.get_commercial_completion(SENDER) == {"frames": [{"target_entity": "deal"}]}

        # sanity: the RAM objects themselves never merged
        assert wa.get("commercial_completion") is None
        assert tg.get("answers", {}) == {}

    # 7. both DB writes targeted their own Session IDs
    tg_writes = _writes_for(add_calls, "telegram") + _writes_for(update_calls, "telegram")
    wa_writes = _writes_for(add_calls, "whatsapp") + _writes_for(update_calls, "whatsapp")
    assert tg_writes and wa_writes
    assert all(w[SF.SESSION_ID] == _canonical_session_key("telegram", SENDER) for w in tg_writes)
    assert all(w[SF.SESSION_ID] == _canonical_session_key("whatsapp", SENDER) for w in wa_writes)
    assert all(w[SF.SENDER_ID] == SENDER for w in tg_writes + wa_writes), (
        "SF.SENDER_ID must always be the raw sender, never the composite RAM key"
    )


# ── Reverse ordering (WhatsApp created first) ──────────────────────────────

def test_cross_channel_ram_isolation_whatsapp_then_telegram():
    store = PersistentSessionStore()
    add_calls, update_calls, fake_add, fake_update = _tracking_airtable()

    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", side_effect=fake_add), \
         patch.object(airtable_tools, "airtable_update", side_effect=fake_update):

        set_request_channel("whatsapp")
        wa = store.get_or_create(SENDER, domain="real_estate", channel="whatsapp")

        set_request_channel("telegram")
        tg = store.get_or_create(SENDER, domain="general", channel="telegram")

        assert wa is not tg

        set_request_channel("whatsapp")
        store.set_active_lead_candidate(SENDER, "אורי צדוק", record_id="recLEAD1")

        set_request_channel("telegram")
        assert store.get_active_lead_candidate(SENDER) is None
        assert tg.get("active_lead_candidate") is None

        store.set_last_prompted_contract(SENDER, "contractABC")

        set_request_channel("whatsapp")
        assert store.get_last_prompted_contract(SENDER) is None
        assert wa.get("active_lead_candidate", {}).get("name") == "אורי צדוק"

    wa_writes = _writes_for(add_calls, "whatsapp") + _writes_for(update_calls, "whatsapp")
    tg_writes = _writes_for(add_calls, "telegram") + _writes_for(update_calls, "telegram")
    assert all(w[SF.SESSION_ID] == _canonical_session_key("whatsapp", SENDER) for w in wa_writes)
    assert all(w[SF.SESSION_ID] == _canonical_session_key("telegram", SENDER) for w in tg_writes)


# ── get()/get_or_create() read paths directly ──────────────────────────────

def test_get_returns_only_the_matching_channels_session():
    store = PersistentSessionStore()
    _, _, fake_add, fake_update = _tracking_airtable()

    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", side_effect=fake_add), \
         patch.object(airtable_tools, "airtable_update", side_effect=fake_update):
        set_request_channel("telegram")
        store.get_or_create(SENDER, channel="telegram")
        set_request_channel("whatsapp")
        store.get_or_create(SENDER, channel="whatsapp")

        # explicit channel= always wins over whatever the request context says
        set_request_channel("whatsapp")
        tg_via_explicit = store.get(SENDER, channel="telegram")
        assert tg_via_explicit is not None and tg_via_explicit["channel"] == "telegram"

        # no explicit channel -> falls back to the request-context channel
        set_request_channel("telegram")
        via_context = store.get(SENDER)
        assert via_context is not None and via_context["channel"] == "telegram"


def test_get_or_create_never_returns_a_different_channels_session_object():
    store = PersistentSessionStore()
    _, _, fake_add, fake_update = _tracking_airtable()

    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", side_effect=fake_add), \
         patch.object(airtable_tools, "airtable_update", side_effect=fake_update):
        set_request_channel("telegram")
        tg = store.get_or_create(SENDER, channel="telegram")

        set_request_channel("whatsapp")
        wa = store.get_or_create(SENDER, channel="whatsapp")

        assert wa is not tg
        assert wa["channel"] == "whatsapp"
        # calling it again for telegram must return the SAME telegram
        # object, not silently create a third one or return wa's object
        set_request_channel("telegram")
        tg_again = store.get_or_create(SENDER, channel="telegram")
        assert tg_again is tg


# ── No-context fallback: create and read paths must never disagree ────────

def test_ram_key_precedence_explicit_then_context_then_whatsapp_default():
    """_ram_key()'s three-tier precedence, unit-tested directly: explicit
    channel arg > set_request_channel() context > "whatsapp" as the final
    default. Critically, that final default must be "whatsapp" and not a
    bare/unscoped key — a bare fallback here would silently reintroduce
    this exact bug: get_or_create() (which always resolves a concrete
    channel) would create under a scoped key while a context-free
    self.get(sender) call computed a different, unscoped key for the same
    session — a guaranteed miss, not merely a stale default."""
    store = PersistentSessionStore()

    set_request_channel("")  # no context at all
    assert store._ram_key("legacy-sender", "") == _canonical_session_key("whatsapp", "legacy-sender")

    set_request_channel("telegram")
    assert store._ram_key("legacy-sender", "") == _canonical_session_key("telegram", "legacy-sender")
    # explicit still wins over context
    assert store._ram_key("legacy-sender", "whatsapp") == _canonical_session_key("whatsapp", "legacy-sender")

    set_request_channel("")  # reset for other tests in this process


def test_create_then_read_agree_with_zero_channel_context():
    """The actual regression this locks in: get_or_create() (channel
    resolution ending in "whatsapp") and a later context-free read like
    get_commercial_completion()/get() (which calls self.get(sender) with no
    channel at all) must resolve to the SAME RAM slot when no request
    context was ever set — otherwise every such read after a context-free
    create is a silent, permanent miss (this was caught by
    test_bug_session_dup_canonicalization.py's commercial_completion tests,
    which call set/get_commercial_completion with no request context)."""
    store = PersistentSessionStore()
    _, _, fake_add, fake_update = _tracking_airtable()

    with patch.object(airtable_tools, "airtable_get_records", return_value=[]), \
         patch.object(airtable_tools, "airtable_add", side_effect=fake_add), \
         patch.object(airtable_tools, "airtable_update", side_effect=fake_update):
        set_request_channel("")
        s1 = store.get_or_create("legacy-sender")
        assert s1["channel"] == "whatsapp"
        assert store.get("legacy-sender", channel="whatsapp") is s1
        assert store.get("legacy-sender") is s1  # no channel arg either — must still agree

        store.set_commercial_completion("legacy-sender", {"frames": [{"target_entity": "deal"}]})
        assert store.get_commercial_completion("legacy-sender") == {"frames": [{"target_entity": "deal"}]}
