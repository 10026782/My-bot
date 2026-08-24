import ast
import inspect
from unittest.mock import Mock, patch

from providers.airtable_shim import AirtableStorageProvider
from tools.airtable_read_adapter import AirtableReadError


def test_get_preserves_query_shape_timeout_and_one_page_behavior():
    page = ([{"id": "rec1"}, {"id": "rec2"}], "offset-next")
    with patch("providers.airtable_shim.list_records_page", return_value=page) as read:
        result = AirtableStorageProvider().get(
            "Tasks", "{Status}='Open'", max_records=150, fields=["Name"]
        )
    assert result == page[0]
    read.assert_called_once_with(
        "משימות (Tasks)", "{Status}='Open'", page_size=100, fields=["Name"], timeout=10
    )


def test_get_applies_max_records_without_pagination():
    with patch(
        "providers.airtable_shim.list_records_page",
        return_value=([{"id": f"rec{i}"} for i in range(5)], "next"),
    ) as read:
        assert AirtableStorageProvider().get("Tasks", max_records=2) == [
            {"id": "rec0"}, {"id": "rec1"}
        ]
    assert read.call_count == 1
    assert read.call_args.kwargs["page_size"] == 2


def test_get_empty_and_http_error_return_empty_list():
    with patch("providers.airtable_shim.list_records_page", return_value=([], None)):
        assert AirtableStorageProvider().get("Tasks") == []
    error = AirtableReadError("HTTP 500", status_code=500, response_text="bad")
    with patch("providers.airtable_shim.list_records_page", side_effect=error):
        assert AirtableStorageProvider().get("Tasks") == []


def test_get_transport_error_is_preserved():
    error = TimeoutError("timed out")
    wrapped = AirtableReadError("transport", cause=error)
    with patch("providers.airtable_shim.list_records_page", side_effect=wrapped):
        try:
            AirtableStorageProvider().get("Tasks")
        except TimeoutError as actual:
            assert actual is error
        else:
            raise AssertionError("transport error was swallowed")


def test_writes_still_use_gateway_and_public_api_is_unchanged():
    provider = AirtableStorageProvider()
    with patch("providers.airtable_shim.airtable_create", return_value={"id": "rec1"}) as create:
        assert provider.add("Tasks", {"Name": "x"}) == {"id": "rec1"}
    create.assert_called_once_with("משימות (Tasks)", {"Name": "x"}, source="provider:airtable_shim")
    with patch("providers.airtable_shim.airtable_patch", return_value=True) as patch_write:
        assert provider.update("Tasks", "rec1", {"Name": "y"}) == {"id": "rec1", "ok": True}
    patch_write.assert_called_once_with(
        "משימות (Tasks)", "rec1", {"Name": "y"}, source="provider:airtable_shim"
    )
    assert str(inspect.signature(provider.get)) == (
        "(table: 'str', formula: 'str' = '', max_records: 'int' = 100, "
        "fields: 'list[str] | None' = None) -> 'list[dict[str, Any]]'"
    )


def test_shim_has_no_direct_airtable_http():
    source = open("providers/airtable_shim.py", encoding="utf-8").read()
    tree = ast.parse(source)
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
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"passed {len(tests)}")
