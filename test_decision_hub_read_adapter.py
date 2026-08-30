"""Focused regression checks for Decision Hub read extraction."""

from __future__ import annotations

import ast
from unittest.mock import patch

import cmd_decision
import decision_matching
from airtable_schema import DecisionFields, DecisionStatus, Tables
from decision_ports import _AirtableStorageAdapter
from tools.airtable_gateway import AirtableLookupError
from tools.airtable_read_adapter import AirtableReadError, get_record, render_query
from identity import Identity, Role


def test_cmd_list_and_record_preserve_read_contract():
    with patch.object(cmd_decision, "list_records", return_value=[{"id": "1"}]) as read:
        assert cmd_decision._at_list(Tables.DECISIONS, "{Status}='Open'") == [{"id": "1"}]
    read.assert_called_once_with(
        Tables.DECISIONS, "{Status}='Open'", max_records=None, paginate=False, timeout=10
    )

    record = {"id": "rec1", "fields": {DecisionFields.TITLE: "Decision"}}
    with patch.object(cmd_decision, "get_record", return_value=record) as get:
        assert cmd_decision._at_get_record(Tables.DECISIONS, "rec1") == record
    get.assert_called_once_with(Tables.DECISIONS, "rec1", timeout=10)


def test_cmd_fallbacks_and_storage_read_contract():
    error = AirtableReadError("Decisions list: HTTP 500", status_code=500)
    with patch.object(cmd_decision, "list_records", side_effect=error):
        assert cmd_decision._at_list(Tables.DECISIONS) == []
    with patch.object(cmd_decision, "get_record", side_effect=error):
        assert cmd_decision._at_get_record(Tables.DECISIONS, "rec1") is None

    with patch("tools.airtable_read_adapter.list_records", return_value=[{"id": "1"}]) as read:
        assert _AirtableStorageAdapter().get(Tables.DECISIONS, "{Status}='Open'") == [{"id": "1"}]
    read.assert_called_once_with(
        Tables.DECISIONS, "{Status}='Open'", max_records=None, paginate=False, timeout=10
    )


def test_matching_formula_is_preserved_and_limit_is_local():
    records = [{"id": str(i)} for i in range(8)]
    identity = Identity(user_id="u1", role=Role.MANAGER, tenant_id="tenant-a")
    with patch("tools.airtable_read_adapter.list_records", return_value=records) as read:
        assert decision_matching.list_open_decisions(limit=3, identity=identity) == records[:3]
    legacy_formula = "OR(" + ",".join(
        f"{{{DecisionFields.STATUS}}}='{status}'"
        for status in (DecisionStatus.OPEN, DecisionStatus.PENDING_INPUT)
    ) + ")"
    args, kwargs = read.call_args
    assert args[0] == Tables.DECISIONS
    scoped_formula = "AND(" + legacy_formula + "," + f"{{{DecisionFields.TENANT_ID}}}='tenant-a'" + ")"
    assert render_query(args[1]).replace(", ", ",") == scoped_formula
    assert kwargs == {"limit": None, "paginate": False, "timeout": 10}


def test_matching_empty_and_error_fallbacks():
    identity = Identity(user_id="u1", role=Role.MANAGER, tenant_id="tenant-a")
    with patch("tools.airtable_read_adapter.list_records", return_value=[]):
        assert decision_matching.list_open_decisions(identity=identity) == []
    with patch(
        "tools.airtable_read_adapter.list_records",
        side_effect=AirtableReadError("Decisions list: HTTP 503", status_code=503),
    ):
        assert decision_matching.list_open_decisions(identity=identity) == []


def test_matching_requires_identity_for_database_enumeration():
    with patch("tools.airtable_read_adapter.list_records") as read:
        assert decision_matching.list_open_decisions() == []
    read.assert_not_called()


def test_matching_filters_explicit_candidates_to_identity_scope():
    identity = Identity(user_id="u1", role=Role.MANAGER, tenant_id="tenant-a")
    candidates = [
        {"id": "foreign", "fields": {DecisionFields.TITLE: "Target", "tenant_id": "tenant-b", "Domain": "general"}},
        {"id": "local", "fields": {DecisionFields.TITLE: "Target", "tenant_id": "tenant-a", "Domain": "general"}},
    ]
    match, score = decision_matching.find_matching_decision("Target", candidates, identity=identity)
    assert match["id"] == "local"
    assert score == 100.0


def test_public_record_adapter_preserves_record_or_error_contract():
    record = {"id": "rec1", "fields": {"Title": "Decision"}}
    with patch("tools.airtable_read_adapter.at_get_record", return_value=record):
        assert get_record(Tables.DECISIONS, "rec1", timeout=10) == record
    with patch(
        "tools.airtable_read_adapter.at_get_record",
        side_effect=AirtableLookupError("Decisions/rec1 get error", cause=TimeoutError("network down")),
    ):
        try:
            get_record(Tables.DECISIONS, "rec1")
        except Exception as exc:
            assert isinstance(exc, Exception)
        else:
            raise AssertionError("record lookup must preserve adapter error boundary")


def test_gateway_record_primitive_preserves_full_record_and_timeout():
    from tools.airtable_gateway import at_get_record

    class Response:
        status_code = 200

        def json(self):
            return {"id": "rec1", "fields": {"Title": "Decision"}}

    with patch("tools.airtable_gateway._at_url", return_value="https://airtable/Decisions"), \
         patch("tools.airtable_gateway._at_headers", return_value={"Authorization": "Bearer key"}), \
         patch("tools.airtable_gateway.httpx.get", return_value=Response()) as http_get:
        assert at_get_record(Tables.DECISIONS, "rec1", timeout=10) == {
            "id": "rec1", "fields": {"Title": "Decision"}
        }
    http_get.assert_called_once_with(
        "https://airtable/Decisions/rec1",
        headers={"Authorization": "Bearer key"},
        timeout=10,
    )


def test_decision_read_modules_have_no_direct_airtable_transport():
    for path in ("cmd_decision.py", "decision_ports.py", "decision_matching.py"):
        tree = ast.parse(open(path, encoding="utf-8").read())
        source = open(path, encoding="utf-8").read()
        assert "httpx" not in source
        assert "_at_url" not in source
        assert "_at_headers" not in source
        assert "_safe_formula_param" not in source
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "tools.airtable_gateway":
                    assert all(not alias.name.startswith("_") for alias in node.names)


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"Decision Hub read adapter: {len(tests)}/{len(tests)} passed")
