import ast
import io
from contextlib import redirect_stdout
from unittest.mock import patch

import diagnose_airtable as diagnose
from airtable_schema import Tables
from tools.airtable_gateway import AirtableLookupError
from tools.airtable_read_adapter import AirtableReadError


def _run():
    output = io.StringIO()
    with redirect_stdout(output):
        code = diagnose.main()
    return code, output.getvalue()


def test_whoami_success_preserves_message_and_timeout(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    with patch("diagnose_airtable.get_whoami", return_value={"email": "user@example.com"}) as whoami, \
         patch("diagnose_airtable.get_base_metadata", return_value={"tables": []}), \
         patch("diagnose_airtable.list_records", return_value=[]):
        code, output = _run()
    assert code == 0
    assert "✅ מפתח תקין — חשבון: user@example.com" in output
    whoami.assert_called_once_with(timeout=10)


def test_whoami_401_preserves_exit_code_and_message(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    error = AirtableLookupError("unauthorized", status_code=401)
    with patch("diagnose_airtable.get_whoami", side_effect=error):
        code, output = _run()
    assert code == 1
    assert "❌ 401 — המפתח לא תקין או פג תוקף" in output


def test_tables_success_preserves_payload_and_timeout(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    metadata = {"tables": [{"name": "Leads", "id": "tbl1"}]}
    with patch("diagnose_airtable.get_whoami", return_value={"id": "usr1"}), \
         patch("diagnose_airtable.get_base_metadata", return_value=metadata) as fetch, \
         patch("diagnose_airtable.list_records", return_value=[]):
        code, output = _run()
    assert code == 0
    assert "נמצאו 1 טבלאות" in output
    assert "• 'Leads' (id: tbl1)" in output
    fetch.assert_called_once_with(timeout=10)


def test_tables_403_keeps_empty_metadata_behavior(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    error = AirtableLookupError("forbidden", status_code=403)
    with patch("diagnose_airtable.get_whoami", return_value={"id": "usr1"}), \
         patch("diagnose_airtable.get_base_metadata", side_effect=error), \
         patch("diagnose_airtable.list_records", return_value=[]):
        code, output = _run()
    assert code == 0
    assert "⚠️ 403 — אין הרשאת metadata (זה בסדר, ממשיכים)" in output


def test_table_checks_preserve_read_arguments_and_output(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    calls = []

    def records(table, **kwargs):
        calls.append((table, kwargs))
        return [{"id": "rec1"}] if table == Tables.CONTACTS else []

    with patch("diagnose_airtable.get_whoami", return_value={"id": "usr1"}), \
         patch("diagnose_airtable.get_base_metadata", return_value={"tables": []}), \
         patch("diagnose_airtable.list_records", side_effect=records):
        code, output = _run()
    assert code == 0
    assert f"✅ '{Tables.CONTACTS}' — 1 רשומות" in output
    assert len(calls) == 4
    assert all(kwargs == {"max_records": 1, "paginate": False, "timeout": 10} for _, kwargs in calls)


def test_table_404_403_and_other_errors_keep_messages(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    errors = {
        Tables.CONTACTS: AirtableReadError("not found", status_code=404),
        Tables.DEALS: AirtableReadError("forbidden", status_code=403),
        Tables.PAYMENTS: AirtableReadError("bad", status_code=500, response_text="server error"),
    }

    def records(table, **_):
        if table in errors:
            raise errors[table]
        return []

    with patch("diagnose_airtable.get_whoami", return_value={"id": "usr1"}), \
         patch("diagnose_airtable.get_base_metadata", return_value={"tables": []}), \
         patch("diagnose_airtable.list_records", side_effect=records):
        code, output = _run()
    assert code == 0
    assert f"❌ '{Tables.CONTACTS}' — 404 לא נמצאה" in output
    assert f"⚠️ '{Tables.DEALS}' — 403 אין הרשאה לטבלה זו" in output
    assert "❌ 'Payments' — 500: server error" in output


def test_diagnostic_has_no_direct_http_or_transport_construction():
    source = open("diagnose_airtable.py", encoding="utf-8").read()
    tree = ast.parse(source)
    assert not [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"httpx", "requests"}
    ]
    for marker in ("api.airtable.com", "urllib.parse", "_at_url", "_at_headers"):
        assert marker not in source
