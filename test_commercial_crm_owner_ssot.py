from unittest.mock import patch

from identity import Identity, Role
from tools import dispatcher


IDENTITY = Identity(
    user_id="eliyahu", display_name="אליהו חזן", role=Role.OWNER,
    tenant_id="boss_hq", channel="telegram", external_id="7228089151",
)


def test_owner_display_name_resolves_to_profile_record_id():
    with patch.object(dispatcher._owner_resolution, "resolve_profile_record_id",
                      return_value="recPROFILE123"):
        assert dispatcher._resolve_authenticated_crm_owner(
            IDENTITY, "אליהו חזן"
        ) == ("recPROFILE123", "")


def test_unknown_owner_and_telegram_id_fail_closed():
    assert dispatcher._resolve_authenticated_crm_owner(IDENTITY, "אורי") == (
        None, "Explicit CRM Owner must resolve through an authorized canonical identity."
    )
    assert dispatcher._resolve_authenticated_crm_owner(IDENTITY, "7228089151")[0] is None


def test_missing_profile_fails_closed():
    with patch.object(dispatcher._owner_resolution, "resolve_profile_record_id",
                      return_value=None):
        owner_id, error = dispatcher._resolve_authenticated_crm_owner(IDENTITY, "אליהו חזן")
    assert owner_id is None
    assert "No Profile record" in error


def test_dispatcher_passes_resolved_owner_to_deal_and_payment_writers():
    with patch.object(dispatcher, "_validate_execution_proof", return_value=None), \
         patch.object(dispatcher._ff, "is_enabled", return_value=False), \
         patch.object(dispatcher._owner_resolution, "resolve_profile_record_id",
                      return_value="recPROFILE123"), \
         patch("commercial_crm.create_deal", return_value={"ok": True}) as deal, \
         patch("commercial_crm.create_payment", return_value={"ok": True}) as payment:
        dispatcher.dispatch_tool(
            "crm_create_deal",
            {"name": "n", "domain": "import", "owner_id": "אליהו חזן"},
            IDENTITY, trusted_source="agent", execution_context={"contract_id": "c"},
        )
        dispatcher.dispatch_tool(
            "crm_create_payment",
            {"amount": 1, "domain": "import", "owner_id": "אליהו חזן"},
            IDENTITY, trusted_source="agent", execution_context={"contract_id": "c"},
        )
    assert deal.call_args.kwargs["owner_id"] == "recPROFILE123"
    assert payment.call_args.kwargs["owner_id"] == "recPROFILE123"


def test_generic_deal_aliases_map_before_owner_resolution():
    with patch.object(dispatcher, "_validate_execution_proof", return_value=None), \
         patch.object(dispatcher._ff, "is_enabled", return_value=False), \
         patch.object(dispatcher._owner_resolution, "resolve_profile_record_id",
                      return_value="recPROFILE123"), \
         patch("commercial_crm.create_deal", return_value={"ok": True}) as deal:
        result = dispatcher.dispatch_tool(
            "airtable_add",
            {"table": "Deals", "fields": {
                "שם העסקה": "Canary Test",
                "תחום": "Import",
                "בעלות": ["אליהו חזן"],
            }},
            IDENTITY, trusted_source="agent", execution_context={"contract_id": "c"},
        )
    assert result["ok"] is True
    assert deal.call_args.kwargs["domain"] == "Import"
    assert deal.call_args.kwargs["owner_id"] == "recPROFILE123"
