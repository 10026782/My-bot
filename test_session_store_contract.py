"""Regression coverage for BUG-SESSIONS-ROOT."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from airtable_schema import SessionsFields as SF, Tables
from session_store import PersistentSessionStore, _new_session
from tools import airtable_tools


SENDER = "7228089151"


def _records(count: int) -> list[dict]:
    return [
        {
            "id": f"recSESSION{i:02d}",
            "fields": {
                SF.SENDER_ID: SENDER,
                SF.CONTEXT_TYPE: "lead",
                SF.CHANNEL: "telegram",
                SF.STATE_JSON: "{}",
            },
        }
        for i in range(count)
    ]


def test_multiple_structured_records_select_existing_and_normalize_sender() -> None:
    store = PersistentSessionStore()
    lookup = MagicMock(return_value=_records(3))

    with patch.object(airtable_tools, "airtable_get_records", lookup):
        selected, found_count, reason = store._find_best_session_in_db(7228089151)

    assert selected == "recSESSION00"
    assert found_count == 3
    assert reason == "patch_existing"
    lookup.assert_called_once_with(
        Tables.SESSIONS, f"{{{SF.SENDER_ID}}}='{SENDER}'"
    )


def test_seventeen_duplicates_patch_existing_and_never_post(caplog) -> None:
    store = PersistentSessionStore()
    session = _new_session("real_estate", "telegram")
    update = MagicMock(return_value={"ok": True, "external_id": "recSESSION00"})
    add = MagicMock(return_value={"ok": True, "external_id": "recSHOULD_NOT_EXIST"})

    with caplog.at_level(logging.INFO), \
         patch.object(airtable_tools, "airtable_get_records", return_value=_records(17)), \
         patch.object(airtable_tools, "airtable_update", update), \
         patch.object(airtable_tools, "airtable_add", add):
        assert store._sync_to_db(7228089151, session)

    update.assert_called_once()
    assert update.call_args.args[1] == "recSESSION00"
    assert update.call_args.args[2][SF.SENDER_ID] == SENDER
    add.assert_not_called()
    assert session["record_id"] == "recSESSION00"
    assert (
        "[SessionStore] lookup sender=7228089151 found_count=17 "
        "selected=recSESSION00 action=patch_existing"
    ) in caplog.text


def test_lookup_contract_mismatch_fails_closed_without_post(caplog) -> None:
    store = PersistentSessionStore()
    session = _new_session()
    malformed = _records(1) + [{"fields": {SF.SENDER_ID: SENDER}}]
    update = MagicMock()
    add = MagicMock()

    with caplog.at_level(logging.ERROR), \
         patch.object(airtable_tools, "airtable_get_records", return_value=malformed), \
         patch.object(airtable_tools, "airtable_update", update), \
         patch.object(airtable_tools, "airtable_add", add):
        assert not store._sync_to_db(SENDER, session)

    update.assert_not_called()
    add.assert_not_called()
    assert "SESSION_LOOKUP_CONTRACT_MISMATCH" in caplog.text
    assert "raw_count=2 parsed_count=1" in caplog.text


def test_raw_records_reader_follows_airtable_pagination() -> None:
    first = MagicMock(status_code=200)
    first.json.return_value = {"records": _records(10), "offset": "next-page"}
    second = MagicMock(status_code=200)
    second.json.return_value = {"records": _records(7)}

    with patch.object(airtable_tools.httpx, "get", side_effect=[first, second]) as get, \
         patch.object(airtable_tools, "_base", return_value="appTEST"), \
         patch.object(airtable_tools, "_audit"):
        records = airtable_tools.airtable_get_records(
            Tables.SESSIONS, f"{{{SF.SENDER_ID}}}='{SENDER}'"
        )

    assert len(records) == 17
    assert get.call_count == 2
    assert get.call_args_list[1].kwargs["params"]["offset"] == "next-page"
