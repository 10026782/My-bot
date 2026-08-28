import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("ELIYAHU_CHAT_ID", "n18_buttons_chat")

from types import SimpleNamespace
from unittest.mock import patch

import app
from core.action_gateway import action_gateway
from core.lead_service import LeadCreateResult
from core.lead_service import render_lead_draft_message
from session_store import lead_sessions


IDENTITY = SimpleNamespace(
    user_id="n18_buttons_owner", role="owner", tenant_id="boss_hq",
    memory_key="boss_hq:n18_buttons_owner", is_owner=True,
    is_internal=True, external_id="n18_buttons_chat",
    can=lambda self, permission: permission == "actions.approve",
)


def _callback(data):
    return SimpleNamespace(
        id="callback-1", data=data, from_user=SimpleNamespace(id="n18_buttons_chat"),
        message=SimpleNamespace(
            message_id=17, chat=SimpleNamespace(id="n18_buttons_chat"),
        ),
    )


def _draft(token):
    return {
        "name": "דנה כהן", "phone": "0501112233", "domain": "recruitment",
        "source": "", "note": "בדיקה", "channel": "telegram",
        "mode": "review", "awaiting_field": None, "callback_token": token,
    }


def test_lead_draft_buttons_use_existing_callback_and_gateway_once():
    token = "a" * 32
    lead_sessions.set_lead_draft("n18_buttons_chat", _draft(token))
    keyboard = app._lead_draft_keyboard(token)
    buttons = [button for row in keyboard.keyboard for button in row]
    assert [button.callback_data for button in buttons] == [
        f"lead_draft_approve:{token}", f"lead_draft_edit:{token}",
        f"lead_draft_cancel:{token}"
    ]

    writes = []
    result = LeadCreateResult(
        ok=True, action="created", record_id="recN18BUTTON", reason="",
        domain="recruitment", owner_user_id="n18_buttons_owner",
    )
    with patch.object(app, "resolve_identity", return_value=IDENTITY), \
         patch("core.lead_candidate_handler._at_find_lead", return_value=None), \
         patch("tma_api._resolve_profile_record_id", return_value="recOWNER"), \
         patch("core.lead_service.create_lead", side_effect=lambda *a, **kw: writes.append(1) or result), \
         patch.object(app.bot, "answer_callback_query") as answer, \
         patch.object(app.bot, "edit_message_text") as edit:
        app._handle_lead_draft_callback(_callback(f"lead_draft_approve:{token}"))
        app._handle_lead_draft_callback(_callback(f"lead_draft_approve:{token}"))

    assert writes == [1]
    assert lead_sessions.get_lead_draft("n18_buttons_chat") is None
    assert answer.call_args_list[0].args == ("callback-1", "✅ התקבל")
    assert edit.call_args_list[0].args[0]
    assert answer.call_args_list[0].args[1] != edit.call_args_list[0].args[0]
    assert len(edit.call_args_list) == 1


def test_lead_draft_cancel_button_writes_nothing():
    token = "b" * 32
    lead_sessions.set_lead_draft("n18_buttons_chat", _draft(token))
    with patch.object(app, "resolve_identity", return_value=IDENTITY), \
         patch("core.lead_service.create_lead", side_effect=AssertionError("write")), \
         patch.object(app.bot, "answer_callback_query") as answer, \
         patch.object(app.bot, "edit_message_text") as edit:
        app._handle_lead_draft_callback(_callback(f"lead_draft_cancel:{token}"))
    assert lead_sessions.get_lead_draft("n18_buttons_chat") is None
    assert answer.call_args_list[0].args == ("callback-1", "↩️ בוטל")
    assert edit.call_args_list[0].args[0] == "↩️ בוטל"


def test_lead_draft_contract_uses_business_labels_and_preserves_note():
    text = render_lead_draft_message(_draft("safe-token"))
    assert text.startswith("👤 ליד חדש")
    assert "תחום: גיוס" in text
    assert "הערה: בדיקה" in text
    assert "סטטוס: חדש" in text
    assert "safe-token" not in text
    assert "recruitment" not in text


def test_lead_draft_edit_button_uses_existing_bounded_edit_flow():
    token = "c" * 32
    lead_sessions.set_lead_draft("n18_buttons_chat", _draft(token))
    with patch.object(app, "resolve_identity", return_value=IDENTITY), \
         patch.object(app.bot, "answer_callback_query") as answer, \
         patch.object(app.bot, "edit_message_text") as edit:
        app._handle_lead_draft_callback(_callback(f"lead_draft_edit:{token}"))
    assert lead_sessions.get_lead_draft("n18_buttons_chat")["mode"] == "edit_choice"
    assert answer.call_args_list[0].args == ("callback-1", "✏️ עריכה")
    assert "איזה שדה לערוך" in edit.call_args_list[0].args[0]
