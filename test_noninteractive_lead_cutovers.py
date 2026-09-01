from types import SimpleNamespace
from unittest.mock import patch

from core.lead_service import LeadCreateResult
from core.noninteractive_lead_cutovers import (
    create_email_inbound_lead,
    create_furniture_inbound_lead,
    create_voice_inbound_lead,
)


OK = LeadCreateResult(ok=True, action="created", record_id="rec1", owner_user_id="owner-1")


def test_email_uses_recipient_owner_mapping_and_canonical_writer():
    with patch("core.noninteractive_lead_cutovers.resolve_owner_user_id", return_value="owner-1"), \
         patch("core.noninteractive_lead_cutovers.create_lead", return_value=OK) as writer:
        result = create_email_inbound_lead("lead@example.com", "sales@boss.co.il", "Lead", "Hello", "general")
    assert result is OK
    assert writer.call_args.args[1].owner_user_id == "owner-1"
    writer.assert_called_once()


def test_email_without_recipient_mapping_fails_closed():
    with patch("core.noninteractive_lead_cutovers.resolve_owner_user_id", return_value=None), \
         patch("core.noninteractive_lead_cutovers.create_lead") as writer:
        result = create_email_inbound_lead("lead@example.com", "unknown@boss.co.il", "Lead", "Hello", "general")
    assert result.action == "blocked"
    writer.assert_not_called()


def test_furniture_reuses_whatsapp_destination_mapping():
    with patch("core.noninteractive_lead_cutovers.resolve_furniture_owner_user_id", return_value="owner-1"), \
         patch("core.noninteractive_lead_cutovers.create_lead", return_value=OK) as writer:
        result = create_furniture_inbound_lead("+972500000000", "whatsapp:+972501234567", "Lead", "Bed", "{}")
    assert result is OK
    # BUG-LEAD-DOMAIN-FURNITURE-NOT-A-DOMAIN (02/09/2026, owner correction):
    # furniture is a product example within the "import" business, not its
    # own Lead domain -- the funnel's routing key stays "furniture_import"
    # internally, but the Lead record's domain field is "import".
    assert writer.call_args.args[1].domain == "import"
    assert writer.call_args.args[1].owner_user_id == "owner-1"


def test_voice_uses_destination_owner_mapping():
    session = SimpleNamespace(
        from_num="+972500000000", to_num="+972501234567", domain="general",
        answers={"name": "Lead"},
    )
    with patch("core.noninteractive_lead_cutovers.resolve_owner_user_id", return_value="owner-1"), \
         patch("core.noninteractive_lead_cutovers.create_lead", return_value=OK) as writer:
        result = create_voice_inbound_lead(session, session.to_num)
    assert result is OK
    assert writer.call_args.args[1].channel == "voice"
    assert writer.call_args.args[1].owner_user_id == "owner-1"
