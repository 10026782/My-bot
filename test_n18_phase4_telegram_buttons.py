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
        f"lead_draft_approve:{token}", f"lead_draft_cancel:{token}"
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
         patch.object(app.bot, "answer_callback_query"), \
         patch.object(app.bot, "edit_message_text"):
        app._handle_lead_draft_callback(_callback(f"lead_draft_approve:{token}"))
        app._handle_lead_draft_callback(_callback(f"lead_draft_approve:{token}"))

    assert writes == [1]
    assert lead_sessions.get_lead_draft("n18_buttons_chat") is None


def test_lead_draft_cancel_button_writes_nothing():
    token = "b" * 32
    lead_sessions.set_lead_draft("n18_buttons_chat", _draft(token))
    with patch.object(app, "resolve_identity", return_value=IDENTITY), \
         patch("core.lead_service.create_lead", side_effect=AssertionError("write")), \
         patch.object(app.bot, "answer_callback_query"), \
         patch.object(app.bot, "edit_message_text"):
        app._handle_lead_draft_callback(_callback(f"lead_draft_cancel:{token}"))
    assert lead_sessions.get_lead_draft("n18_buttons_chat") is None
