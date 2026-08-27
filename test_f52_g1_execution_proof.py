from types import SimpleNamespace
from unittest.mock import patch

from airtable_schema import ContactFields
from core.action_gateway import ActionGateway
from tools.dispatcher import dispatch_tool
import emergency_stop_test_support

emergency_stop_test_support.configure_all_clear_emergency_stop()

IDENTITY = SimpleNamespace(user_id="owner_1", role="owner", memory_key="boss_hq:owner_1", tenant_id="boss_hq", is_external=False, is_internal=True)
INPUTS = {"table": "Contacts", "fields": {ContactFields.NAME: "A", ContactFields.PHONE: "+972548212778"}}


def _proof(name, inputs, status="approved"):
    return {"contract_id": "contract-1", "approved_by": IDENTITY.memory_key, "tool_name": name, "tenant_id": IDENTITY.tenant_id, "canonical_user_id": IDENTITY.memory_key, "business_action_fingerprint": ActionGateway.compute_business_fingerprint(IDENTITY.tenant_id, IDENTITY.memory_key, name, ActionGateway.normalize_payload(inputs)), "status": status}


def test_sensitive_action_without_proof_is_blocked_before_provider():
    with patch("tools.dispatcher.airtable_add", side_effect=AssertionError("provider bypass")):
        assert dispatch_tool("airtable_add", INPUTS, IDENTITY)["ok"] is False


def test_valid_proof_allows_sensitive_action():
    inputs = {"to": "a@example.com", "subject": "S", "body": "B"}
    with patch("tools.dispatcher._ff.is_enabled", return_value=False), patch("tools.dispatcher.gmail_draft", return_value="draft") as provider:
        assert dispatch_tool("gmail_draft", inputs, IDENTITY, execution_context=_proof("gmail_draft", inputs)) == "draft"
    assert provider.call_count == 1


def test_role_alone_and_stale_or_wrong_proof_are_blocked():
    for proof in (_proof("airtable_add", INPUTS, "pending"), _proof("airtable_update", INPUTS), _proof("airtable_add", {"table": "Contacts", "fields": {"name": "B"}})):
        with patch("tools.dispatcher.airtable_add", side_effect=AssertionError("provider bypass")):
            assert dispatch_tool("airtable_add", INPUTS, IDENTITY, execution_context=proof)["ok"] is False


def test_read_only_tool_remains_unaffected():
    with patch("tools.dispatcher.airtable_get", return_value="records"):
        assert dispatch_tool("airtable_get", {"table": "Contacts"}, IDENTITY) == "records"
