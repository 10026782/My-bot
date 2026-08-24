"""Focused linked-relation portability checks for Cluster #2."""

import inspect

import tma_api
from tools.airtable_read_adapter import render_query


def test_relation_refs_preserve_empty_single_multiple_and_opaque_values():
    assert tma_api.relation_refs(None) == ()
    assert tma_api.relation_refs([]) == ()
    assert tma_api.relation_refs("provider-1") == ("provider-1",)
    assert tma_api.relation_refs(["provider-1", "provider-2"]) == (
        "provider-1", "provider-2"
    )
    assert tma_api.relation_refs(["provider-1", 7, ""]) == ("provider-1",)
    assert tma_api.relation_payload(("provider-1", "provider-2")) == [
        "provider-1", "provider-2"
    ]


def test_lead_event_linkage_keeps_missing_and_malformed_shapes_fail_closed():
    event = {"fields": {tma_api.LeadEventFields.LEAD_LINK: ["provider-lead"]}}
    assert tma_api._event_linked_to_lead(event, "provider-lead") is True
    assert tma_api._event_linked_to_lead(event, "other") is False
    assert tma_api._event_linked_to_lead({"fields": {}}, "provider-lead") is False
    assert tma_api._event_linked_to_lead(
        {"fields": {tma_api.LeadEventFields.LEAD_LINK: "provider-lead"}},
        "provider-lead",
    ) is False


def test_read_lead_events_uses_opaque_relation_refs_without_rec_validation(monkeypatch):
    calls = []

    def fake_list(table, formula="", max_records=50, strict=False, **kwargs):
        calls.append(formula)
        return [{
            "id": "event-1",
            "fields": {tma_api.LeadEventFields.LEAD_LINK: ["lead-1"]},
        }]

    monkeypatch.setattr(tma_api, "_at_list", fake_list)
    lead = {
        "id": "lead-1",
        "fields": {"Lead Events": ["event-1"]},
    }
    assert tma_api._read_lead_events(lead)
    assert "event-1" in render_query(calls[0])
    assert "RECORD_ID()" in render_query(calls[0])


def test_linked_relation_validation_is_not_reintroduced():
    source = inspect.getsource(tma_api)
    assert "_REC_ID_RE" not in source
    assert "def _linked_record_ids" not in source
