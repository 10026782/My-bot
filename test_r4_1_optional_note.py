import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import core.lead_candidate_handler as lch
from session_store import lead_sessions


IDENTITY = SimpleNamespace(is_internal=True, user_id="r4_1_owner")


def _reply(chat, text):
    return lch.handle_lead_candidate(
        IDENTITY, text, chat, "telegram",
        session=lead_sessions.get_or_create(chat),
    )


def test_guided_creation_accepts_note_before_review():
    chat = "r4_1_note"
    with patch("core.lead_service.create_lead") as create:
        assert _reply(chat, "ליד חדש") == "מה שם הליד?"
        assert _reply(chat, "דנה כהן") == "מה מספר הטלפון?"
        assert _reply(chat, "0501112233").startswith("מה התחום?")
        assert _reply(chat, "גיוס") == "יש הערה לליד? כתוב/י אותה או השב/י 'דלג'."
        review = _reply(chat, "שיחה ראשונה")
        create.assert_not_called()
    assert "הערה: שיחה ראשונה" in review
    assert lead_sessions.get_lead_draft(chat)["mode"] == "review"


def test_guided_creation_can_skip_note_without_blank_placeholder():
    chat = "r4_1_skip"
    _reply(chat, "ליד חדש")
    _reply(chat, "דנה כהן")
    _reply(chat, "0501112233")
    _reply(chat, "גיוס")
    review = _reply(chat, "דלג")
    assert "הערה:" not in review
    assert lead_sessions.get_lead_draft(chat)["mode"] == "review"


def test_edit_note_reuses_same_draft_field_and_writes_only_on_confirm():
    chat = "r4_1_edit"
    _reply(chat, "ליד חדש")
    _reply(chat, "דנה כהן")
    _reply(chat, "0501112233")
    _reply(chat, "גיוס")
    _reply(chat, "ללא הערה")
    assert "הערה:" not in _reply(chat, "ערוך")
    assert "הערה" in _reply(chat, "הערה")
    review = _reply(chat, "לקוח חוזר")
    assert "הערה: לקוח חוזר" in review

    with patch("core.lead_service.create_lead") as create:
        assert "הערה: לקוח חוזר" in _reply(chat, "כן")
        create.assert_called_once()
