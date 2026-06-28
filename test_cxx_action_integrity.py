"""Minimal regression coverage for CXX Action Integrity wiring."""

from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# Keep this unit suite independent of optional runtime packages imported by
# tools/__init__.py. Submodules still load normally from the real tools path.
tools_package = types.ModuleType("tools")
tools_package.__path__ = [str(Path(__file__).with_name("tools"))]
sys.modules.setdefault("tools", tools_package)

from core.action_result import ActionResult, ClaimType
from core.claim_gate import check_claim
from core.output_gateway import (
    AudienceClass,
    OutboundEnvelope,
    OutputChannel,
    _gateway_context,
    send_outbound,
)
from core.request_context import RequestContext
from identity import Identity, Role
from tools.whatsapp_adapter import send_whatsapp


class ActionIntegrityTests(unittest.TestCase):
    def test_airtable_result_requires_structured_record_evidence(self):
        result = ActionResult.from_airtable_add(
            {"ok": True, "external_id": "rec123"}, source="test"
        )
        result.claim_type = ClaimType.CREATED
        self.assertTrue(check_claim(result).ok)

        malformed = ActionResult.from_airtable_add("rec123", source="test")
        malformed.claim_type = ClaimType.CREATED
        self.assertFalse(check_claim(malformed).ok)

    def test_stub_delivery_never_passes_sent_claim(self):
        _gateway_context.approved = True
        try:
            result = send_whatsapp("+972500000000", "hello")
        finally:
            _gateway_context.approved = False

        self.assertEqual(result.adapter_mode, "stub")
        self.assertTrue(result.delivery_attempted)
        self.assertFalse(result.delivery_success)
        self.assertFalse(check_claim(result).ok)

    def test_direct_adapter_bypass_is_rejected_in_production(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            _gateway_context.approved = False
            with self.assertRaises(AssertionError):
                send_whatsapp("+972500000000", "hello")

    def test_gateway_preserves_adapter_evidence(self):
        envelope = OutboundEnvelope(
            channel=OutputChannel.TWILIO_WHATSAPP,
            recipient="+972500000000",
            body="hello",
            audience=AudienceClass.CUSTOMER,
            source_module="test",
            source_ref="case-1",
            domain="general",
        )
        with patch("core.financial_gate.check") as financial_check:
            financial_check.return_value.shadow_only = True
            financial_check.return_value.escalated = False
            result = send_outbound(envelope)

        self.assertEqual(result.status, "APPROVED")
        self.assertIsNotNone(result.action_result)
        self.assertTrue(result.action_result.output_approved)
        self.assertTrue(result.action_result.audit_success)
        self.assertFalse(result.action_result.delivery_success)
        self.assertFalse(check_claim(result.action_result).ok)

    def test_stub_fallback_is_not_reported_as_delivered(self):
        envelope = OutboundEnvelope(
            channel=OutputChannel.TWILIO_WHATSAPP,
            recipient="+972500000000",
            body="financial commitment",
            audience=AudienceClass.CUSTOMER,
            source_module="test",
            source_ref="case-2",
            domain="general",
        )
        with (
            patch("core.financial_gate.check") as financial_check,
            patch("core.output_gateway._notify_owner_escalation"),
        ):
            financial_check.return_value.shadow_only = False
            financial_check.return_value.escalated = True
            financial_check.return_value.reason = "approval required"
            result = send_outbound(envelope)

        self.assertEqual(result.status, "ESCALATED")
        self.assertFalse(result.fallback_sent)

    def test_request_context_tracks_lead_session_and_domain(self):
        identity = Identity(
            user_id="+972500000000",
            role=Role.LEAD,
            channel="whatsapp",
            external_id="+972500000000",
        )
        context = RequestContext.from_identity(identity)
        context.lead_record_id = "recLead"
        context.mark_session_loaded({"step": "new"}, "recSession")
        context.update_domain("real_estate")

        self.assertEqual(context.memory_key, "boss_hq:+972500000000")
        self.assertEqual(context.lead_record_id, "recLead")
        self.assertTrue(context.session_loaded)
        self.assertEqual(context.session_record_id, "recSession")
        self.assertEqual(context.domain, "real_estate")
        self.assertEqual(identity.domain_id, "real_estate")


if __name__ == "__main__":
    unittest.main()
