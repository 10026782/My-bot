"""Focused contract tests for TMA Airtable read-helper extraction."""

from __future__ import annotations

import ast
from unittest.mock import patch

import tma_api
from tools.airtable_read_adapter import AirtableReadError


def test_at_list_preserves_query_and_one_page_contract():
    with patch.object(tma_api, "_read_list_records", return_value=[{"id": "rec1"}]) as read:
        assert tma_api._at_list("Leads", "{Status}='Open'", 7) == [{"id": "rec1"}]
    read.assert_called_once_with(
        "Leads", "{Status}='Open'", max_records=7, paginate=False, timeout=10
    )


def test_at_list_non_strict_error_returns_empty_and_strict_error_maps_to_airtable_error():
    error = AirtableReadError("Leads list: HTTP 500", status_code=500, response_text="bad")
    with patch.object(tma_api, "_read_list_records", side_effect=error):
        assert tma_api._at_list("Leads", strict=False) == []
        try:
            tma_api._at_list("Leads", strict=True)
        except tma_api.AirtableError as exc:
            assert (exc.table, exc.http_status, exc.safe_body) == ("Leads", 500, "bad")
        else:
            raise AssertionError("strict read must raise AirtableError")


def test_at_list_transport_error_keeps_non_strict_and_strict_behavior():
    cause = TimeoutError("timed out")
    error = AirtableReadError("Leads list error", cause=cause)
    with patch.object(tma_api, "_read_list_records", side_effect=error):
        assert tma_api._at_list("Leads") == []
        try:
            tma_api._at_list("Leads", strict=True)
        except tma_api.AirtableError as exc:
            assert (exc.http_status, exc.safe_body) == (0, "timed out")
        else:
            raise AssertionError("strict transport error must raise AirtableError")


def test_at_get_record_preserves_full_record_and_timeout():
    record = {"id": "rec1", "fields": {"Name": "Dana"}, "createdTime": "now"}
    with patch.object(tma_api, "_read_get_record", return_value=record) as get:
        assert tma_api._at_get_record("Leads", "rec1") == record
    get.assert_called_once_with("Leads", "rec1", timeout=10)


def test_at_get_record_error_and_missing_return_none():
    error = AirtableReadError("Leads/rec1 get: HTTP 404", status_code=404)
    with patch.object(tma_api, "_read_get_record", side_effect=error):
        assert tma_api._at_get_record("Leads", "rec1") is None
    with patch.object(tma_api, "_read_get_record", return_value=None):
        assert tma_api._at_get_record("Leads", "rec1") is None


def test_write_helpers_still_delegate_to_gateway():
    with patch.object(tma_api, "_gw_patch", return_value=True) as patch_call, \
         patch.object(tma_api, "_shadow_record_tma"):
        assert tma_api._at_patch("Leads", "rec1", {"Name": "Dana"}) is True
    patch_call.assert_called_once_with("Leads", "rec1", {"Name": "Dana"}, source="tma")

    with patch.object(tma_api, "_gw_create", return_value={"id": "rec1"}) as create_call, \
         patch.object(tma_api, "_shadow_record_tma"):
        assert tma_api._at_post("Leads", {"Name": "Dana"}) == {"id": "rec1"}
    create_call.assert_called_once_with("Leads", {"Name": "Dana"}, source="tma")


def test_tma_read_helpers_have_no_direct_airtable_get():
    tree = ast.parse(open("tma_api.py", encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {"_at_list", "_at_get_record"}:
            source = ast.get_source_segment(open("tma_api.py", encoding="utf-8").read(), node)
            assert "httpx.get" not in source
            assert "_at_url" not in source
            assert "_at_headers" not in source


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"passed {len(tests)}")
