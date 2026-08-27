from unittest.mock import patch

import inbound_handler


def test_external_id_lookup_uses_structured_record_id():
    with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recSTRUCT", "fields": {}}]), \
         patch("tools.airtable_tools.airtable_get", side_effect=AssertionError("display lookup")):
        assert inbound_handler._find_by_external_id("gmail:1") == "recSTRUCT"


def test_external_id_display_text_cannot_change_lookup_result():
    with patch("tools.airtable_tools.airtable_get_records", return_value=[]), \
         patch("tools.airtable_tools.airtable_get", return_value="✅ נמצא | ID: recFAKE"):
        assert inbound_handler._find_by_external_id("gmail:1") is None


def test_external_id_missing_structured_identity_fails_closed():
    with patch("tools.airtable_tools.airtable_get_records", return_value=[{"fields": {}}]), \
         patch("tools.airtable_tools.airtable_get", side_effect=AssertionError("display fallback")):
        assert inbound_handler._find_by_external_id("gmail:1") is None


def test_external_id_structured_lookup_preserves_duplicate_decision():
    with patch.object(inbound_handler, "is_enabled", return_value=True), \
         patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recDUP", "fields": {}}]), \
         patch.object(inbound_handler, "_create_email_lead") as create:
        inbound_handler.handle_inbound(
            "sender@example.com", "hello", "email", "general", "gmail:1"
        )
    create.assert_not_called()


def test_external_id_normal_inbound_without_match_still_creates():
    with patch.object(inbound_handler, "is_enabled", return_value=True), \
         patch("tools.airtable_tools.airtable_get_records", return_value=[]), \
         patch.object(inbound_handler, "_create_email_lead") as create:
        inbound_handler.handle_inbound(
            "sender@example.com", "hello", "email", "general", "gmail:1"
        )
    create.assert_called_once()
