"""Focused regression checks for Airtable Extraction Slice 4A."""

from __future__ import annotations

import ast
import os
from unittest.mock import patch

import core.emergency_window as emergency_window
import core.lead_events as lead_events
import tools.dispatcher as dispatcher
import tools.airtable_gateway as gateway
import tools.airtable_read_adapter as read_adapter
from tools.airtable_read_adapter import AirtableReadError, render_query
from core.query_contract import equals


def test_lead_event_store_preserves_formula_options_and_mapping():
    lead_events._AT_KEY = "key"
    lead_events._AT_BASE = "base"
    records = [{"id": "rec1", "fields": {"type": "note", "summary": "hello", "keywords": "[\"x\"]"}}]
    with patch.object(lead_events, "list_records", return_value=records) as read:
        assert lead_events.LeadEventStore().get_all("real_estate") == [{
            "type": "note", "domain": "real_estate", "memory_key": "rec1", "content": "hello", "keywords": ["x"]
        }]
    read.assert_called_once()
    call = read.call_args
    assert call.args[0] == "Business Memory"
    assert render_query(call.args[1]) == "FIND('real_estate', ARRAYJOIN({keywords}))"
    assert call.kwargs == {"limit": 500, "paginate": False, "timeout": 10}


def test_lead_event_store_preserves_empty_and_error_behavior():
    lead_events._AT_KEY = "key"
    lead_events._AT_BASE = "base"
    with patch.object(lead_events, "list_records", return_value=[]):
        assert lead_events.LeadEventStore().get_all() == []
    with patch.object(
        lead_events,
        "list_records",
        side_effect=AirtableReadError("Business Memory list: HTTP 500", status_code=500, response_text="bad"),
    ):
        assert lead_events.LeadEventStore().get_all() == []


def test_emergency_lookup_preserves_formula_sort_limit_and_timeout():
    emergency_window._at_key = lambda: "key"
    emergency_window._at_base = lambda: "base"
    record = {"id": "rec-ew", "fields": {"Status": "Active"}}
    with patch.object(emergency_window, "list_records", return_value=[record]) as read:
        assert emergency_window._fetch_active_record() == record
    read.assert_called_once_with(
        emergency_window.Tables.EMERGENCY_WINDOW,
        equals(emergency_window.F.STATUS, emergency_window.Status.ACTIVE),
        limit=1,
        sort=[{"field": emergency_window.F.ACTIVATED_AT, "direction": "desc"}],
        paginate=False,
        timeout=10,
    )


def test_emergency_lookup_preserves_empty_and_error_behavior():
    emergency_window._at_key = lambda: "key"
    emergency_window._at_base = lambda: "base"
    with patch.object(emergency_window, "list_records", return_value=[]):
        assert emergency_window._fetch_active_record() is None
    with patch.object(
        emergency_window,
        "list_records",
        side_effect=AirtableReadError("Emergency Window list: HTTP 503", status_code=503),
    ):
        assert emergency_window._fetch_active_record() is None


def test_dispatcher_duplicate_lookup_preserves_sanitization_and_options():
    with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "base", "AIRTABLE_API_KEY": "key"}), \
         patch.object(dispatcher, "list_records", return_value=[{"id": "rec1"}]) as read:
        assert dispatcher._check_duplicate("Leads", "phone", "050'123") == {"id": "rec1"}
    read.assert_called_once_with(
        "Leads", "{phone}='050123'", max_records=1, paginate=False, timeout=5
    )


def test_dispatcher_duplicate_lookup_preserves_empty_and_error_behavior():
    with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "base", "AIRTABLE_API_KEY": "key"}), \
         patch.object(dispatcher, "list_records", return_value=[]):
        assert dispatcher._check_duplicate("Leads", "phone", "050123") is None
    with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "base", "AIRTABLE_API_KEY": "key"}), \
         patch.object(
             dispatcher,
             "list_records",
             side_effect=AirtableReadError("Leads list: HTTP 500", status_code=500),
         ):
        assert dispatcher._check_duplicate("Leads", "phone", "050123") is None


def test_boundary_guard_for_three_migrated_paths():
    for filename, function_name in (
        ("core/lead_events.py", "get_all"),
        ("core/emergency_window.py", "_fetch_active_record"),
        ("tools/dispatcher.py", "_check_duplicate"),
    ):
        source = open(filename, encoding="utf-8").read()
        tree = ast.parse(source)
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function_name)
        body = ast.get_source_segment(source, node)
        assert not any(token in body for token in (
            "httpx.get", "requests.get", "api.airtable.com", "_at_url", "_at_headers",
        ))


def test_read_adapter_forwards_sort_without_changing_defaults():
    with patch.object(read_adapter, "at_list_by_formula", return_value=[]) as list_by_formula:
        assert read_adapter.list_records(
            "Emergency Window",
            equals(emergency_window.F.STATUS, emergency_window.Status.ACTIVE),
            limit=1,
            sort=[{"field": "Activated At", "direction": "desc"}],
            paginate=False,
            timeout=10,
        ) == []
    list_by_formula.assert_called_once_with(
        "Emergency Window",
        "{Status}='Active'",
        1,
        fields=None,
        sort=[{"field": "Activated At", "direction": "desc"}],
        paginate=False,
        timeout=10,
    )


def test_gateway_encodes_sort_params():
    class Response:
        status_code = 200
        text = ""
        url = "https://airtable.test"
        reason_phrase = "OK"

        def json(self):
            return {"records": [{"id": "rec1"}]}

    with patch.object(gateway, "_at_url", return_value="https://airtable.test"), \
         patch.object(gateway, "_at_headers", return_value={"Authorization": "Bearer key"}), \
         patch.object(gateway.httpx, "get", return_value=Response()) as http_get:
        assert gateway.at_list_by_formula(
            "Emergency Window",
            "{Status}='Active'",
            1,
            sort=[{"field": "Activated At", "direction": "desc"}],
            paginate=False,
            timeout=10,
        ) == [{"id": "rec1"}]
    assert http_get.call_args.kwargs["params"] == {
        "filterByFormula": "{Status}='Active'",
        "maxRecords": 1,
        "sort[0][field]": "Activated At",
        "sort[0][direction]": "desc",
    }


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"passed {len(tests)}")
