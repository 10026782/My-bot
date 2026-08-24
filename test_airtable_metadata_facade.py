import ast
import inspect
import os
from unittest.mock import Mock, patch

import tools.airtable_tools as legacy
from tools.airtable_gateway import get_base_metadata


def _response(status=200, *, payload=None, text=""):
    response = Mock(status_code=status, text=text, url="https://api.airtable.com/meta")
    response.reason_phrase = "Bad Request" if status != 200 else "OK"
    response.json.return_value = payload
    return response


def test_schema_formats_all_tables_and_fields_with_timeout_10():
    payload = {
        "tables": [
            {"name": "Leads", "fields": [{"name": "Name"}, {"name": "Status"}]},
            {"name": "Assets", "fields": [{"name": "Title"}]},
        ]
    }
    with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTest", "AIRTABLE_API_KEY": "patTest"}), \
         patch("tools.airtable_gateway.httpx.get", return_value=_response(payload=payload)) as get:
        assert legacy.airtable_get_schema() == (
            "📊 נמצאו 2 טבלאות:\n\n"
            "• Leads\n  שדות: Name, Status\n\n"
            "• Assets\n  שדות: Title"
        )
    get.assert_called_once()
    assert get.call_args.kwargs["timeout"] == 10


def test_gateway_returns_full_metadata_payload():
    payload = {"tables": [{"id": "tbl1", "name": "Leads", "fields": []}], "extra": "kept"}
    with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTest", "AIRTABLE_API_KEY": "patTest"}), \
         patch("tools.airtable_gateway.httpx.get", return_value=_response(payload=payload)):
        assert get_base_metadata(timeout=10) == payload


def test_schema_public_signature_is_unchanged():
    assert str(inspect.signature(legacy.airtable_get_schema)) == "() -> str"


def test_schema_empty_metadata_message():
    with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTest", "AIRTABLE_API_KEY": "patTest"}), \
         patch("tools.airtable_gateway.httpx.get", return_value=_response(payload={"tables": []})):
        assert legacy.airtable_get_schema() == "📭 לא נמצאו טבלאות בבסיס הנתונים."


def test_schema_http_error_compatibility():
    with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTest", "AIRTABLE_API_KEY": "patTest"}), \
         patch(
        "tools.airtable_gateway.httpx.get",
        return_value=_response(422, text="invalid metadata"),
    ):
        assert legacy.airtable_get_schema() == "❌ Meta API error 422: invalid metadata"


def test_schema_transport_error_is_preserved():
    error = TimeoutError("timed out")
    with patch.dict(os.environ, {"AIRTABLE_BASE_ID": "appTest", "AIRTABLE_API_KEY": "patTest"}), \
         patch("tools.airtable_gateway.httpx.get", side_effect=error):
        try:
            legacy.airtable_get_schema()
        except TimeoutError as actual:
            assert actual is error
        else:
            raise AssertionError("transport error was swallowed")


def test_schema_missing_base_error_is_preserved():
    with patch.dict(os.environ, {}, clear=True):
        try:
            legacy.airtable_get_schema()
        except RuntimeError as actual:
            assert str(actual) == "AIRTABLE_BASE_ID לא מוגדר"
        else:
            raise AssertionError("missing base error was swallowed")


def test_schema_facade_contains_no_direct_http():
    tree = ast.parse(open("tools/airtable_tools.py", encoding="utf-8").read())
    direct = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"httpx", "requests"}
    ]
    assert direct == []


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for test in tests:
        test()
    print(f"passed {len(tests)}")
