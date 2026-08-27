from types import SimpleNamespace
from unittest.mock import patch

from ad_attribution import UTMParams, record_lead_source
from core.lead_service import LeadCreateResult, update_lead_fields
from identity import Identity, Role


IDENTITY = Identity(
    user_id="+972500000000",
    role=Role.LEAD,
    channel="whatsapp",
    external_id="whatsapp:+972500000000",
)
UTM = UTMParams(source="meta", medium="cpc", campaign="spring")
FIELDS = UTM.to_airtable_fields()


class _Ledger:
    _repository = None

    def __init__(self):
        self.statuses = []

    def update_status(self, contract_id, status):
        self.statuses.append((contract_id, status))
        return True


def _gateway(ok=True, *, reason=""):
    ledger = _Ledger()
    gateway = SimpleNamespace(
        _ledger=ledger,
        propose_action=lambda **_: SimpleNamespace(
            ok=ok, contract_id="contract-1" if ok else "", reason=reason
        ),
    )
    return gateway, ledger


def test_attribution_uses_canonical_boundary_and_preserves_fields():
    gateway, ledger = _gateway()
    with patch("core.action_gateway.action_gateway", gateway), \
         patch("tools.airtable_gateway.airtable_patch", return_value=True) as writer:
        result = update_lead_fields(
            IDENTITY, "recLEAD1", FIELDS, source_module="ad_attribution"
        )

    assert result.ok
    assert result.record_id == "recLEAD1"
    assert result.evidence["mutation_executed"] is True
    assert ledger.statuses == [("contract-1", "executed")]
    writer.assert_called_once_with("Leads", "recLEAD1", FIELDS, source="ad_attribution")


def test_record_lead_source_does_not_call_legacy_airtable_writer():
    gateway, _ = _gateway()
    with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recLEAD1", "fields": {}}]), \
         patch("core.lead_service.update_lead_fields", return_value=LeadCreateResult(
             ok=True, action="updated", record_id="recLEAD1"
         )) as canonical, \
         patch("tools.airtable_tools.airtable_update", side_effect=AssertionError("legacy writer")):
        assert record_lead_source("boss_hq:test", UTM, identity=IDENTITY)

    canonical.assert_called_once_with(
        IDENTITY, "recLEAD1", FIELDS, source_module="ad_attribution"
    )


def test_attribution_uses_structured_record_id_not_rendered_text():
    with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recSTRUCTURED", "fields": {}}]), \
         patch("tools.airtable_tools.airtable_get", side_effect=AssertionError("display lookup")), \
         patch("core.lead_service.update_lead_fields", return_value=LeadCreateResult(
             ok=True, action="updated", record_id="recSTRUCTURED"
         )) as canonical:
        assert record_lead_source("boss_hq:test", UTM, identity=IDENTITY)

    assert canonical.call_args.args[1] == "recSTRUCTURED"


def test_structured_failure_stays_failure_even_with_success_looking_text():
    with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recSTRUCTURED", "fields": {}}]), \
         patch("tools.airtable_tools.airtable_get", return_value="✅ רשומה עודכנה | ID: recFAKE"), \
         patch("core.lead_service.update_lead_fields", return_value=LeadCreateResult(
             ok=False, action="write_failed", record_id="recSTRUCTURED"
         )), \
         patch("tools.airtable_tools.airtable_update", side_effect=AssertionError("legacy writer")):
        assert not record_lead_source("boss_hq:test", UTM, identity=IDENTITY)


def test_missing_structured_identity_fails_closed_without_display_fallback():
    with patch("tools.airtable_tools.airtable_get_records", return_value=[{"fields": {}}]), \
         patch("tools.airtable_tools.airtable_get", side_effect=AssertionError("display fallback")), \
         patch("core.lead_service.update_lead_fields") as canonical:
        assert not record_lead_source("boss_hq:test", UTM, identity=IDENTITY)

    canonical.assert_not_called()


def test_gateway_failure_fails_closed_without_airtable_mutation():
    gateway, _ = _gateway(ok=False, reason="gateway unavailable")
    with patch("core.action_gateway.action_gateway", gateway), \
         patch("tools.airtable_gateway.airtable_patch", side_effect=AssertionError("must not write")):
        result = update_lead_fields(
            IDENTITY, "recLEAD1", FIELDS, source_module="ad_attribution"
        )

    assert not result.ok
    assert result.action == "duplicate"
    assert result.evidence["mutation_executed"] is False


def test_canonical_writer_failure_returns_failure_without_false_success():
    gateway, _ = _gateway()
    with patch("core.action_gateway.action_gateway", gateway), \
         patch("tools.airtable_gateway.airtable_patch", return_value=False):
        result = update_lead_fields(
            IDENTITY, "recLEAD1", FIELDS, source_module="ad_attribution"
        )

    assert not result.ok
    assert result.action == "write_failed"
    assert result.evidence["mutation_executed"] is False


def test_repeated_blocked_attribution_is_safe_and_feature_off_gate_is_unchanged():
    gateway, _ = _gateway(ok=False, reason="already recorded")
    with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recLEAD1", "fields": {}}]), \
         patch("core.action_gateway.action_gateway", gateway), \
         patch("tools.airtable_gateway.airtable_patch") as writer:
        assert not record_lead_source("boss_hq:test", UTM, identity=IDENTITY)
        assert not record_lead_source("boss_hq:test", UTM, identity=IDENTITY)

    writer.assert_not_called()
