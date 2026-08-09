import unittest
import os
import threading
from unittest.mock import MagicMock, patch

import crm
from airtable_schema import ContactFields, Tables
from identity import Identity, Role
from tools.airtable_gateway import AirtableCreateOutcome, airtable_create


class F14B2ContactIntegrationTests(unittest.TestCase):
    identity = Identity("u1", Role.OWNER)

    def test_gate_injected_writer_creates_without_legacy_post(self):
        writer = MagicMock(return_value=AirtableCreateOutcome("created", {"id": "recNEW"}))
        with patch.object(crm, "_creds_ok", return_value=True), \
                patch.object(crm, "_get", return_value=[]), \
                patch.object(crm, "_post") as legacy_post:
            result = crm.find_or_create_contact(
                "054-821-2778", "Dana", identity=self.identity, create_writer=writer)
        self.assertEqual((result.status, result.record_id), ("created", "recNEW"))
        writer.assert_called_once()
        legacy_post.assert_not_called()

    def test_gate_existing_does_not_write(self):
        writer = MagicMock()
        with patch.object(crm, "_creds_ok", return_value=True), \
                patch.object(crm, "_get", side_effect=[[{"id": "recOLD"}], [], [], []]):
            result = crm.find_or_create_contact(
                "+972548212778", "Dana", create_writer=writer)
        self.assertEqual((result.status, result.record_id), ("existing", "recOLD"))
        writer.assert_not_called()

    def test_uncertain_writer_is_distinct_and_not_retryable(self):
        writer = MagicMock(return_value=AirtableCreateOutcome("outcome_unknown", error="timeout"))
        with patch.object(crm, "_creds_ok", return_value=True), \
                patch.object(crm, "_get", return_value=[]):
            result = crm.find_or_create_contact(
                "+972548212778", "Dana", create_writer=writer)
        self.assertEqual(result.status, "outcome_unknown")
        self.assertEqual(result.error, "timeout")
        writer.assert_called_once()

    def test_ambiguous_invalid_and_lookup_error_never_call_writer(self):
        for status, get_side_effect, phone, expected_get_calls in (
            ("ambiguous", [[{"id": "rec1"}, {"id": "rec2"}], [], [], []], "+972548212778", 4),
            ("invalid", None, "not-a-phone", 0),
            ("lookup_error", RuntimeError("read failed"), "+972548212778", 4),
        ):
            with self.subTest(status=status), \
                    patch.object(crm, "_creds_ok", return_value=True), \
                    patch.object(crm, "_get", side_effect=get_side_effect) as get, \
                    patch.object(crm, "_post") as legacy_post:
                writer = MagicMock()
                result = crm.find_or_create_contact(
                    phone, "Dana", create_writer=writer)
            self.assertEqual(result.status, status)
            self.assertEqual(get.call_count, expected_get_calls)
            writer.assert_not_called()
            legacy_post.assert_not_called()

    def test_gateway_classifies_http_failure_and_transport_uncertainty(self):
        response = MagicMock(status_code=422, text="invalid")
        response.json.return_value = {"error": "invalid"}
        with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTEST", "AIRTABLE_API_KEY": "key"}), \
                patch("tools.airtable_gateway.httpx.post", return_value=response):
            rejected = airtable_create(
                Tables.CONTACTS,
                {ContactFields.NAME: "Dana", ContactFields.PHONE: "+972548212778"},
                return_outcome=True,
            )
        self.assertEqual(rejected.status, "failed")

        with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTEST", "AIRTABLE_API_KEY": "key"}), \
                patch("tools.airtable_gateway.httpx.post", side_effect=TimeoutError("timeout")):
            uncertain = airtable_create(
                Tables.CONTACTS,
                {ContactFields.NAME: "Dana", ContactFields.PHONE: "+972548212778"},
                return_outcome=True,
            )
        self.assertEqual(uncertain.status, "outcome_unknown")

    def test_gateway_structured_and_legacy_success_contracts(self):
        with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTEST", "AIRTABLE_API_KEY": "key"}):
            response = MagicMock(status_code=201)
            response.json.return_value = {"id": "recNEW", "fields": {"שם": "Dana"}}
            with patch("tools.airtable_gateway.httpx.post", return_value=response):
                structured = airtable_create(
                    Tables.CONTACTS, {ContactFields.NAME: "Dana"}, return_outcome=True)
            self.assertEqual(structured.status, "created")
            self.assertEqual(structured.record["id"], "recNEW")

            response.json.return_value = {"fields": {"שם": "Dana"}}
            with patch("tools.airtable_gateway.httpx.post", return_value=response):
                legacy = airtable_create(Tables.CONTACTS, {ContactFields.NAME: "Dana"})
                structured_without_id = airtable_create(
                    Tables.CONTACTS, {ContactFields.NAME: "Dana"}, return_outcome=True)
            self.assertEqual(legacy, {"fields": {"שם": "Dana"}})
            self.assertEqual(structured_without_id.status, "outcome_unknown")

    def test_gateway_malformed_4xx_is_definite_and_5xx_is_unknown(self):
        with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTEST", "AIRTABLE_API_KEY": "key"}):
            for code, expected in ((422, "failed"), (500, "outcome_unknown")):
                response = MagicMock(status_code=code, text="not-json")
                response.json.side_effect = ValueError("malformed")
                with self.subTest(code=code), patch("tools.airtable_gateway.httpx.post", return_value=response):
                    result = airtable_create(
                        Tables.CONTACTS,
                        {ContactFields.NAME: "Dana"},
                        return_outcome=True,
                    )
                self.assertEqual(result.status, expected)

    def test_generic_dispatch_uses_contact_gate(self):
        fields = {ContactFields.NAME: "Dana", ContactFields.PHONE: "+972548212778"}
        provider = AirtableCreateOutcome("created", {"id": "recNEW"})
        with patch.object(crm, "_creds_ok", return_value=True), \
                patch.object(crm, "_get", return_value=[]), \
                patch.object(crm, "_post") as legacy_post, \
                patch("tools.airtable_gateway.airtable_create", return_value=provider) as gateway, \
                patch("tools.dispatcher.airtable_add", side_effect=AssertionError("bypass")), \
                patch("tools.dispatcher._ff.is_enabled", return_value=False):
            from tools.dispatcher import dispatch_tool
            result = dispatch_tool("airtable_add", {"table": Tables.CONTACTS, "fields": fields}, self.identity)
        self.assertTrue(result["ok"])
        self.assertEqual(result["external_id"], "recNEW")
        gateway.assert_called_once()
        legacy_post.assert_not_called()

    def test_generic_uncertain_outcome_is_forwarded_without_retry(self):
        from core.dispatcher_outcome import DispatcherOutcome

        fields = {ContactFields.NAME: "Dana", ContactFields.PHONE: "+972548212778"}
        provider = AirtableCreateOutcome("outcome_unknown", error="timeout")
        with patch.object(crm, "_creds_ok", return_value=True), \
                patch.object(crm, "_get", return_value=[]), \
                patch("tools.airtable_gateway.airtable_create", return_value=provider) as gateway, \
                patch("tools.dispatcher._ff.is_enabled", return_value=False):
            from tools.dispatcher import dispatch_tool
            result = dispatch_tool("airtable_add", {"table": Tables.CONTACTS, "fields": fields}, self.identity)
        self.assertIsInstance(result, DispatcherOutcome)
        self.assertTrue(result.is_outcome_unknown())
        gateway.assert_called_once()

    def test_distinct_contracts_can_race_between_lookup_and_create(self):
        """Documents F14's known check-then-create limitation; no locking in B2."""
        writers_started = threading.Barrier(2)
        created = []

        def writer(fields):
            writers_started.wait(timeout=2)
            record_id = f"rec{len(created) + 1}"
            created.append(record_id)
            return AirtableCreateOutcome("created", {"id": record_id})

        def run():
            return crm.find_or_create_contact(
                "+972548212778", "Dana", create_writer=writer)

        with patch.object(crm, "_creds_ok", return_value=True), \
                patch.object(crm, "_get", return_value=[]):
            results = [threading.Thread(target=run) for _ in range(2)]
            for thread in results:
                thread.start()
            for thread in results:
                thread.join(timeout=3)

        # Both distinct approved Contracts may observe zero before either POST.
        self.assertEqual(created, ["rec1", "rec2"])

    def test_tma_contact_post_uses_the_same_gate(self):
        fields = {ContactFields.NAME: "Dana", ContactFields.PHONE: "+972548212778"}
        provider = AirtableCreateOutcome("created", {"id": "recTMA"})
        with patch.object(crm, "_creds_ok", return_value=True), \
                patch.object(crm, "_get", return_value=[]), \
                patch.object(crm, "_post") as legacy_post, \
                patch("tools.approval_actions._verify_active_execution_claim", return_value=True), \
                patch("tools.airtable_gateway.airtable_create",
                      side_effect=[provider, {"id": "recAUDIT"}, {"id": "recRECEIPT"}]) as gateway:
            from tools.approval_actions import tma_write
            result = tma_write(
                op="post", table=Tables.CONTACTS, fields=fields,
                identity=self.identity, trusted_source="tma_api",
                execution_context={"contract_id": "c1", "approved_by": "u1", "claim_execution_id": "e1"},
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["external_id"], "recTMA")
        self.assertEqual(gateway.call_args_list[0].kwargs["source"], "tma_write")
        legacy_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
