"""Compatibility tests for the legacy Airtable record facade."""

from __future__ import annotations

import ast
from contextlib import contextmanager
from unittest.mock import patch

import tools.airtable_gateway as gateway
import tools.airtable_tools as legacy
from tools.airtable_read_adapter import AirtableReadError


def test_gateway_page_forwards_page_size_offset_formula_and_timeout():
    class Response:
        status_code = 200
        text = ""
        url = "https://airtable.test"
        reason_phrase = "OK"

        def json(self):
            return {"records": [{"id": "rec1"}], "offset": "next"}

    with patch.object(gateway, "_at_url", return_value="https://airtable.test"), \
         patch.object(gateway, "_at_headers", return_value={}), \
         patch.object(gateway.httpx, "get", return_value=Response()) as get:
        assert gateway.at_list_page(
            "Tasks", "{Status}='Open'", page_size=100, offset="old", timeout=10
        ) == ([{"id": "rec1"}], "next")
    assert get.call_args.kwargs["params"] == {
        "filterByFormula": "{Status}='Open'",
        "pageSize": 100,
        "offset": "old",
    }
    assert get.call_args.kwargs["timeout"] == 10


def test_get_records_paginates_and_preserves_unbounded_page_size():
    calls = []

    def page(*args, **kwargs):
        calls.append((args, kwargs))
        return ([{"id": "one"}], "next") if len(calls) == 1 else ([{"id": "two"}], None)

    with patch("tools.airtable_read_adapter.list_records_page", side_effect=page):
        assert legacy.airtable_get_records("Tasks", "{Status}='Open'") == [
            {"id": "one"}, {"id": "two"}
        ]
    assert [call[1] for call in calls] == [
        {"page_size": 100, "offset": "", "timeout": 10},
        {"page_size": 100, "offset": "next", "timeout": 10},
    ]
    assert all(call[0][0] == "משימות (Tasks)" for call in calls)
    assert all(call[0][1] == "{Status}='Open'" for call in calls)


def test_get_records_uses_remaining_page_size_and_stops_at_bound():
    first = [{"id": str(i)} for i in range(100)]
    second = [{"id": str(i)} for i in range(100, 200)]
    with patch(
        "tools.airtable_read_adapter.list_records_page",
        side_effect=[(first, "next"), (second, "later")],
    ) as page:
        result = legacy.airtable_get_records("Tasks", max_records=150)
    assert len(result) == 150
    assert page.call_args_list[0].kwargs["page_size"] == 100
    assert page.call_args_list[1].kwargs == {
        "page_size": 50, "offset": "next", "timeout": 10
    }


def test_get_records_zero_negative_and_no_offset_behavior():
    with patch("tools.airtable_read_adapter.list_records_page") as page:
        assert legacy.airtable_get_records("Tasks", max_records=0) == []
        page.assert_not_called()
    with patch("tools.airtable_read_adapter.list_records_page"):
        try:
            legacy.airtable_get_records("Tasks", max_records=-1)
        except ValueError as exc:
            assert str(exc) == "max_records cannot be negative"
        else:
            raise AssertionError("negative max_records did not fail")
    with patch(
        "tools.airtable_read_adapter.list_records_page",
        return_value=([{"id": "only"}], None),
    ) as page:
        assert legacy.airtable_get_records("Tasks") == [{"id": "only"}]
        page.assert_called_once()


def test_get_records_preserves_runtime_error_contract_and_audit_breaker():
    entered = []

    @contextmanager
    def breaker():
        entered.append(True)
        yield

    error = AirtableReadError(
        "Tasks page: HTTP 422", status_code=422, response_text="bad formula"
    )
    with patch.object(legacy, "with_airtable_breaker", breaker), \
         patch("tools.airtable_read_adapter.list_records_page", side_effect=error), \
         patch.object(legacy, "_audit") as audit:
        try:
            legacy.airtable_get_records("Tasks", "bad")
        except RuntimeError as exc:
            assert str(exc) == "Airtable error 422: bad formula"
        else:
            raise AssertionError("HTTP failure did not preserve RuntimeError")
    assert entered == [True]
    audit.assert_not_called()

    with patch("tools.airtable_read_adapter.list_records_page", return_value=([{"id": "r"}], None)), \
         patch.object(legacy, "_audit") as audit:
        assert legacy.airtable_get_records("Tasks") == [{"id": "r"}]
    audit.assert_called_once()


def test_presentation_and_search_wrappers_are_unchanged():
    with patch.object(legacy, "airtable_get_records", return_value=[]):
        assert legacy.airtable_get("Tasks") == "📭 אין רשומות בטבלה 'Tasks'."
    with patch.object(legacy, "airtable_get_records", side_effect=RuntimeError("boom")):
        assert legacy.airtable_get("Tasks") == "❌ boom"
    with patch.object(legacy, "airtable_get_records", return_value=[{"id": "r", "fields": {"Name": "Dana"}}]):
        assert legacy.airtable_get("Tasks") == "📊 Tasks — 1 רשומות:\n• [r] Name: Dana\n"
    with patch.object(legacy, "airtable_get") as get:
        legacy.search_lead("O'Brien")
    get.assert_called_once_with("Leads", "SEARCH('O\\'Brien', {Name})")


def test_linked_lookup_uses_one_page_adapter_compatibility_call():
    with patch(
        "tools.airtable_read_adapter.list_records_page",
        return_value=([{"id": "rec1"}], None),
    ) as page:
        assert legacy._lookup_record_id("Worlds", "O'Brien") == "rec1"
    page.assert_called_once_with(
        "Worlds", "{Name}='O\\'Brien'", max_records=1, timeout=10
    )


def test_gateway_page_preserves_legacy_max_records_for_linked_lookup():
    class Response:
        status_code = 200
        text = ""
        url = "https://airtable.test"
        reason_phrase = "OK"

        def json(self):
            return {"records": [], "offset": "ignored"}

    with patch.object(gateway, "_at_url", return_value="https://airtable.test"), \
         patch.object(gateway, "_at_headers", return_value={}), \
         patch.object(gateway.httpx, "get", return_value=Response()) as get:
        gateway.at_list_page("Worlds", "{Name}='x'", max_records=1, timeout=10)
    assert get.call_args.kwargs["params"] == {
        "filterByFormula": "{Name}='x'",
        "maxRecords": 1,
    }


def test_linked_lookup_failure_stays_non_fatal():
    with patch(
        "tools.airtable_read_adapter.list_records_page",
        side_effect=AirtableReadError("Worlds page: HTTP 503", status_code=503),
    ), patch.object(legacy.logger, "warning") as warning:
        assert legacy._lookup_record_id("Worlds", "x") is None
    warning.assert_called_once_with("airtable: lookup failed [Worlds] 503")


def test_add_and_update_still_use_gateway_writes():
    record = {"id": "rec1", "fields": {}}
    with patch("tools.airtable_gateway.airtable_create", return_value=record) as create:
        assert legacy.airtable_add("Leads", {"Name": "Dana"})["ok"] is True
    create.assert_called_once_with("Leads", {"Name": "Dana"}, source="agent")

    with patch("tools.airtable_gateway.airtable_patch", return_value=True) as patch_write:
        assert legacy.airtable_update("Leads", "rec1", {"Name": "Dana"})["ok"] is True
    patch_write.assert_called_once_with("Leads", "rec1", {"Name": "Dana"}, source="agent")


def test_record_level_http_is_absent_from_legacy_module():
    source = open("tools/airtable_tools.py", encoding="utf-8").read()
    tree = ast.parse(source)
    direct_get_functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            body = ast.get_source_segment(source, node) or ""
            if "httpx.get(" in body:
                direct_get_functions.append(node.name)
    assert direct_get_functions == ["airtable_get_schema"]
    assert "list_records_page" in source


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"passed {len(tests)}")
