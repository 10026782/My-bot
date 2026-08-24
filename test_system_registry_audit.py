import ast
import os
from unittest.mock import patch

import system_registry_audit as audit
from tools.airtable_gateway import AirtableLookupError


def _metadata(*tables):
    return {"tables": list(tables)}


def test_fetch_schema_preserves_table_field_mapping_and_timeout():
    payload = _metadata(
        {"name": "Leads", "fields": [{"name": "Name"}, {"name": "Status"}]},
        {"name": "Assets", "fields": [{"name": "Title"}]},
    )
    with patch.dict(os.environ, {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
         patch("tools.airtable_gateway.get_base_metadata", return_value=payload) as fetch:
        assert audit._fetch_airtable_schema() == (
            "OK",
            {"Leads": {"Name", "Status"}, "Assets": {"Title"}},
            "Airtable metadata reachable; tables=2",
        )
    fetch.assert_called_once_with(timeout=10)


def test_fetch_schema_missing_credentials_is_missing():
    with patch.dict(os.environ, {}, clear=True):
        assert audit._fetch_airtable_schema() == (
            "MISSING", {}, "AIRTABLE_API_KEY or AIRTABLE_BASE_ID missing"
        )


def test_fetch_schema_empty_metadata_is_empty():
    with patch.dict(os.environ, {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
         patch("tools.airtable_gateway.get_base_metadata", return_value={"tables": []}):
        assert audit._fetch_airtable_schema() == (
            "EMPTY", {}, "Airtable metadata returned zero tables"
        )


def test_fetch_schema_http_failure_is_broken_with_status():
    error = AirtableLookupError("bad", status_code=500)
    with patch.dict(os.environ, {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
         patch("tools.airtable_gateway.get_base_metadata", side_effect=error):
        assert audit._fetch_airtable_schema() == (
            "BROKEN", {}, "Airtable metadata returned HTTP 500"
        )


def test_fetch_schema_transport_failure_preserves_exception_type_in_detail():
    error = TimeoutError("timed out")
    wrapped = AirtableLookupError("network", cause=error)
    with patch.dict(os.environ, {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
         patch("tools.airtable_gateway.get_base_metadata", side_effect=wrapped):
        assert audit._fetch_airtable_schema() == (
            "BROKEN", {}, "Airtable metadata request failed: TimeoutError"
        )


def test_registry_audit_statuses_remain_valid():
    assert audit.VALID_STATUSES == {"OK", "EMPTY", "MISSING", "BROKEN"}


def test_registry_audit_has_no_direct_airtable_http():
    tree = ast.parse(open("system_registry_audit.py", encoding="utf-8").read())
    assert not [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"httpx", "requests"}
    ]


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"passed {len(tests)}")
