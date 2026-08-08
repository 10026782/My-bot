import unittest
from unittest.mock import patch

import crm
import lead_conversion
from airtable_schema import LeadFields, LeadStatus


class F14B1LegacyMigrationTests(unittest.TestCase):
    def test_crm_add_contact_delegates_to_gate(self):
        expected = crm.ContactResult("existing", record_id="recCONTACT")
        with patch.object(crm, "find_or_create_contact", return_value=expected) as gate:
            result = crm.crm_add_contact(
                name="Dana", phone="054-821-2778", email="dana@example.com",
                company="Acme", lead_source_id="recLEAD")
        self.assertEqual(result, expected)
        gate.assert_called_once_with(
            "054-821-2778", "Dana", email="dana@example.com", company="Acme",
            contact_type="Client", notes="", lead_source_id="recLEAD",
            source="crm_add_contact")

    def _convert(self, contact_result):
        lead = {"id": "recLEAD", "fields": {
            LeadFields.NAME: "Dana",
            LeadFields.PHONE: "054-821-2778",
        }}
        with patch.object(lead_conversion, "is_enabled", return_value=True), \
                patch("tma_api._at_list", return_value=[lead]), \
                patch("tma_api._at_patch", return_value=True) as patch_lead, \
                patch.object(lead_conversion, "crm_add_contact",
                             return_value=contact_result), \
                patch("tools.airtable_security.audit_log_airtable"):
            result = lead_conversion.convert_lead_to_contact("Dana")
        return result, patch_lead

    def test_existing_continues_without_new_contact(self):
        (ok, message), patch_lead = self._convert(
            crm.ContactResult("existing", record_id="recCONTACT"))
        self.assertTrue(ok)
        self.assertIn("קיים", message)
        self.assertEqual(patch_lead.call_count, 1)
        self.assertEqual(patch_lead.call_args.args[2][LeadFields.STATUS], LeadStatus.DONE)

    def test_created_continues(self):
        (ok, message), patch_lead = self._convert(
            crm.ContactResult("created", record_id="recCONTACT"))
        self.assertTrue(ok)
        self.assertIn("חדש", message)
        self.assertEqual(patch_lead.call_count, 1)

    def test_fail_closed_statuses_do_not_update_lead(self):
        for status in ("ambiguous", "invalid", "lookup_error"):
            with self.subTest(status=status):
                (ok, _), patch_lead = self._convert(crm.ContactResult(status))
                self.assertFalse(ok)
                patch_lead.assert_not_called()


if __name__ == "__main__":
    unittest.main()
