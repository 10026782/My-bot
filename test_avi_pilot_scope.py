from types import SimpleNamespace
from unittest.mock import patch

import crm
from tools.airtable_security import TenantScopeViolation, enforce_tenant_scope


def _avi():
    return SimpleNamespace(
        role="partner",
        is_internal=True,
        tenant_id="boss_hq",
        allowed_domains=["recruitment"],
    )


def test_partner_reads_are_domain_scoped_and_contacts_fail_closed_without_scope():
    params = enforce_tenant_scope("airtable_get", _avi(), {"table": "Leads"})
    assert "{domain}='recruitment'" in params["filterByFormula"]

    try:
        enforce_tenant_scope("airtable_get", _avi(), {"table": "Contacts"})
    except TenantScopeViolation:
        pass
    else:
        raise AssertionError("unscoped Contacts read was allowed")


def test_partner_contacts_use_allowed_deal_and_task_relationships():
    def fake_list(table, formula, **kwargs):
        if table == crm.Tables.DEALS:
            return [{"fields": {crm.DealFields.CONTACTS_LINK: [{"id": "rec_contact"}]}}]
        if table == crm.Tables.TASKS:
            return []
        return [{"id": "rec_contact", "fields": {crm.ContactFields.NAME: "Avi"}}]

    with patch.object(crm, "list_records", side_effect=fake_list):
        records = crm._get(crm.Tables.CONTACTS, identity=_avi())

    assert [record["id"] for record in records] == ["rec_contact"]
