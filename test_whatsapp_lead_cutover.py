from types import SimpleNamespace
from unittest.mock import patch

from core.lead_service import LeadCreateResult
from core.whatsapp_lead_cutover import create_whatsapp_inbound_lead


IDENTITY = SimpleNamespace(
    external_id="+972509876543",
    display_name="",
    tenant_id="boss_hq",
)


def test_whatsapp_create_passes_one_owner_aware_payload_to_canonical_service():
    created = LeadCreateResult(
        ok=True, action="created", record_id="rec1", owner_user_id="eliyahu"
    )
    with patch("core.whatsapp_lead_cutover.resolve_owner_user_id", return_value="eliyahu"), \
         patch("core.whatsapp_lead_cutover.create_lead", return_value=created) as writer:
        result = create_whatsapp_inbound_lead(
            IDENTITY, "Need a quote", "whatsapp:+972501234567", "real_estate"
        )

    assert result is created
    writer.assert_called_once()
    identity, payload = writer.call_args.args[:2]
    assert identity is IDENTITY
    assert payload.owner_user_id == "eliyahu"
    assert payload.phone == IDENTITY.external_id
    assert payload.source == "whatsapp_inbound"
    assert payload.channel == "whatsapp"


def test_whatsapp_update_or_dedup_result_is_returned_without_a_second_writer():
    updated = LeadCreateResult(
        ok=True, action="updated", record_id="rec1", owner_user_id="eliyahu"
    )
    with patch("core.whatsapp_lead_cutover.resolve_owner_user_id", return_value="eliyahu"), \
         patch("core.whatsapp_lead_cutover.create_lead", return_value=updated) as writer:
        result = create_whatsapp_inbound_lead(
            IDENTITY, "Follow-up", "whatsapp:+972501234567", "real_estate"
        )

    assert result.action == "updated"
    writer.assert_called_once()


def test_unmapped_whatsapp_fails_closed_before_canonical_or_legacy_write():
    with patch("core.whatsapp_lead_cutover.resolve_owner_user_id", return_value=None), \
         patch("core.whatsapp_lead_cutover.create_lead") as writer:
        result = create_whatsapp_inbound_lead(
            IDENTITY, "Need a quote", "whatsapp:+972500000000", "real_estate"
        )

    assert result.ok is False
    assert result.action == "blocked"
    writer.assert_not_called()
