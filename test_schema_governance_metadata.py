import ast
from unittest.mock import patch

import httpx

import tools.schema_governance as governance
from tools.airtable_gateway import AirtableLookupError


def test_fetch_live_schema_uses_gateway_and_preserves_payload_and_timeout():
    payload = {"tables": [{"name": "Leads", "fields": [{"name": "Name"}]}]}
    with patch("tools.airtable_gateway.get_base_metadata", return_value=payload) as fetch:
        assert governance.fetch_live_schema("base", "key") == payload
    fetch.assert_called_once_with(timeout=20)


def test_fetch_live_schema_http_failure_preserves_http_status_error():
    error = AirtableLookupError("HTTP 500", status_code=500)
    with patch("tools.airtable_gateway.get_base_metadata", side_effect=error):
        try:
            governance.fetch_live_schema("base", "key")
        except httpx.HTTPStatusError as raised:
            assert str(raised) == "HTTP 500"
        else:
            raise AssertionError("HTTP failure was not preserved")


def test_fetch_live_schema_transport_failure_preserves_original_exception():
    error = TimeoutError("timed out")
    with patch(
        "tools.airtable_gateway.get_base_metadata",
        side_effect=AirtableLookupError("transport", cause=error),
    ):
        try:
            governance.fetch_live_schema("base", "key")
        except TimeoutError as raised:
            assert raised is error
        else:
            raise AssertionError("transport failure was not preserved")


def test_main_missing_credentials_keeps_exit_code(monkeypatch, capsys):
    monkeypatch.delenv("AIRTABLE_API_KEY", raising=False)
    monkeypatch.delenv("AIRTABLE_BASE_ID", raising=False)
    assert governance.main() == 1
    assert "חסרים ב-env" in capsys.readouterr().err


def test_main_keeps_error_exit_code(monkeypatch, tmp_path):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    monkeypatch.setattr(governance, "_REPORT_PATH", tmp_path / "report.json")
    monkeypatch.setattr(governance, "fetch_live_schema", lambda *_: {"tables": []})
    monkeypatch.setattr(
        governance,
        "run_governance",
        lambda *_: {
            "generated_at": "2026-08-24",
            "tables_checked": [],
            "table_summaries": [],
            "findings": [{"severity": governance.SEVERITY_ERROR, "table": "X", "field": None, "message": "error"}],
            "field_types": {},
            "summary": {"total": 1, "errors": 1, "warnings": 0},
        },
    )
    monkeypatch.setattr(governance, "find_unregistered_field_classes", lambda: [])
    monkeypatch.setattr(governance, "print_report", lambda _: None)
    assert governance.main() == 1


def test_governance_findings_and_self_test_are_unchanged(capsys):
    governance._self_test()
    assert "6/6 assertions passed" in capsys.readouterr().out


def test_governance_module_has_no_direct_airtable_http_or_transport_construction():
    source = open("tools/schema_governance.py", encoding="utf-8").read()
    tree = ast.parse(source)
    assert not [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"httpx", "requests"}
        and node.func.attr in {"get", "post", "patch", "put", "delete"}
    ]
    assert "api.airtable.com" not in source
    assert "_at_url" not in source
    assert "_at_headers" not in source
