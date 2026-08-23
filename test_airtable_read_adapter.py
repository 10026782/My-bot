from __future__ import annotations

from unittest.mock import patch

import daily_digest
import weekly_summary
import worker
from airtable_schema import Tables
from tools.airtable_read_adapter import list_records


def test_daily_digest_query_and_pagination_are_preserved(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    with patch.object(daily_digest, "list_records", return_value=[{"id": "1"}]) as read:
        assert daily_digest._fetch("Leads", "{Status}='Open'", max_rec=0) == [{"id": "1"}]
    read.assert_called_once_with("Leads", "{Status}='Open'", max_records=0)


def test_weekly_summary_query_and_return_shape_are_preserved(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    with patch.object(
        weekly_summary,
        "list_records",
        return_value=[{"fields": {"Title": "entry"}}, {"id": "missing-fields"}],
    ) as read:
        result = weekly_summary._fetch_records_direct("IS_AFTER({Date}, 'since')")

    assert result == [{"Title": "entry"}, {}]
    read.assert_called_once_with(
        Tables.BUSINESS_MEMORY,
        "IS_AFTER({Date}, 'since')",
        max_records=50,
    )


def test_worker_query_and_requested_fields_are_preserved():
    with patch.object(worker, "list_records", return_value=[]) as read:
        assert worker._scan_airtable_deadlines(days_ahead=3) == []

    formula, kwargs = read.call_args.args[1], read.call_args.kwargs
    assert f"{{{worker.STATUS_FIELD}}} != '{worker.TaskStatus.DONE}'" in formula
    assert f"{{{worker.DEADLINE_FIELD}}}" in formula
    assert kwargs == {
        "max_records": 20,
        "fields": [worker.NAME_FIELD, worker.DEADLINE_FIELD, worker.STATUS_FIELD],
    }


def test_adapter_preserves_unbounded_pagination_and_fields():
    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    responses = iter([
        Response({"records": [{"id": "one"}], "offset": "next"}),
        Response({"records": [{"id": "two"}]}),
    ])
    seen = []

    def fake_get(*_args, **kwargs):
        seen.append(dict(kwargs["params"]))
        return next(responses)

    with patch("tools.airtable_gateway._at_base", return_value="base"), \
         patch("tools.airtable_gateway.httpx.get", side_effect=fake_get):
        assert list_records(
            "Tasks", "{Status}='Open'", max_records=0, fields=["Name"]
        ) == [{"id": "one"}, {"id": "two"}]

    assert seen == [
        {"filterByFormula": "{Status}='Open'", "fields[]": ["Name"]},
        {"filterByFormula": "{Status}='Open'", "fields[]": ["Name"], "offset": "next"},
    ]
