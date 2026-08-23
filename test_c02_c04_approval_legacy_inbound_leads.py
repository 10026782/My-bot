from types import SimpleNamespace
from unittest.mock import patch

from core.lead_service import LeadCreateResult


def _ok(record_id="recLEAD1"):
    return LeadCreateResult(ok=True, action="created", record_id=record_id, domain="general")


def _failed():
    return LeadCreateResult(ok=False, action="gateway_failed", reason="gateway_proposal_failed")


def test_whatsapp_capture_uses_canonical_writer_and_fails_closed():
    import lead_capture

    identity = SimpleNamespace(
        display_name="", external_id="+972500000000", channel="whatsapp",
        memory_key="boss_hq:+972500000000", domain_id="general",
    )
    with patch.object(lead_capture, "is_enabled", return_value=True), \
         patch("tools.airtable_tools.airtable_get", return_value=""), \
         patch("tools.airtable_tools.airtable_add", side_effect=AssertionError("legacy writer called")), \
         patch.object(lead_capture, "create_lead", return_value=_ok()) as canonical:
        result = lead_capture.capture_inbound_lead(identity, "need a quote", write_event=False)

    assert result.business_success
    canonical.assert_called_once()
    assert canonical.call_args.kwargs["write_event"] is False
    assert canonical.call_args.args[1].domain == "general"
    assert canonical.call_args.args[1].source == "whatsapp_inbound"

    with patch.object(lead_capture, "is_enabled", return_value=True), \
         patch("tools.airtable_tools.airtable_get", return_value=""), \
         patch("tools.airtable_tools.airtable_add", side_effect=AssertionError("legacy writer called")), \
         patch.object(lead_capture, "create_lead", return_value=_failed()):
        result = lead_capture.capture_inbound_lead(identity, "need a quote", write_event=False)
    assert not result.business_success


def test_email_and_furniture_always_use_canonical_writer_when_legacy_flags_are_off():
    import inbound_handler
    import furniture_lead_funnel

    with patch("core.noninteractive_lead_cutovers.create_email_inbound_lead", return_value=_ok()) as email, \
         patch("tools.airtable_tools.airtable_add", side_effect=AssertionError("legacy writer called")):
        inbound_handler._create_email_lead("lead@example.com", "Lead", "import", "hello", "gmail:1")
    email.assert_called_once()

    with patch("core.noninteractive_lead_cutovers.create_furniture_inbound_lead", return_value=_ok()) as furniture, \
         patch("tools.airtable_gateway.airtable_create", side_effect=AssertionError("legacy writer called")), \
         patch("tools.airtable_gateway.airtable_patch", side_effect=AssertionError("legacy writer called")):
        furniture_lead_funnel._save_lead(
            "+972500000000",
            {"answers": {"name": "Lead"}, "owner_destination": "whatsapp:+972501234567"},
        )
    furniture.assert_called_once()


def test_scoped_legacy_writer_functions_contain_no_direct_lead_mutation():
    import ast
    from pathlib import Path

    checks = {
        "inbound_handler.py": "_create_email_lead",
        "furniture_lead_funnel.py": "_save_lead",
    }
    for filename, function_name in checks.items():
        tree = ast.parse(Path(filename).read_text(encoding="utf-8"))
        function = next(node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name)
        source = ast.get_source_segment(Path(filename).read_text(encoding="utf-8"), function) or ""
        assert "airtable_add" not in source
        assert "airtable_create" not in source
        assert "airtable_patch" not in source
