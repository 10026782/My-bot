"""Focused regression checks for Airtable Extraction Slice 4B."""

from __future__ import annotations

import ast
import os
from unittest.mock import patch

import project_timeline
from tools.airtable_read_adapter import render_query


def test_timeline_creation_preserves_payload_and_write_contract():
    task = {"Phase": "A", "Task": "T", "Description": "D", "Owner": "O",
            "Status": "open", "Priority": "high", "Start": "2026-01-01",
            "Due": "2026-01-02", "Phase_Order": 1}
    with patch.object(project_timeline, "TIMELINE_TASKS", [task]), \
         patch.object(project_timeline, "airtable_create", return_value={"id": "rec-task"}) as create:
        assert project_timeline.create_timeline_records() == {"created": 1, "errors": 0}
    create.assert_called_once_with(
        "ProjectTimeline", task, source="project_timeline", timeout=10
    )


def test_timeline_reads_preserve_queries_and_shapes():
    records = [{"fields": {"Task": "T", "Phase": "A", "Due": "2999-01-01", "Priority": "high", "Status": "in_progress"}}]
    calls = []

    def fake_list(*args, **kwargs):
        calls.append((args, kwargs))
        if render_query(args[1]).startswith("OR("):
            return records
        return []

    with patch.dict(os.environ, {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
         patch.object(project_timeline, "list_records", side_effect=fake_list), \
         patch.object(project_timeline, "_count_phases_done", return_value=["A"]):
        summary = project_timeline.get_timeline_summary()

    assert summary["in_progress"] == [{"task": "T", "phase": "A", "due": "2999-01-01", "priority": "high"}]
    assert summary["done_today"] == 0
    assert (calls[0][0][0], render_query(calls[0][0][1])) == (
        "ProjectTimeline", "OR({Status}='open', {Status}='in_progress')"
    )
    assert calls[0][1] == {
        "limit": None,
        "sort": [{"field": "Due", "direction": "asc"}],
        "paginate": False,
        "timeout": 10,
    }
    assert calls[1][0][0] == "ProjectTimeline"
    assert calls[1][1] == {"limit": None, "paginate": False, "timeout": 10}


def test_timeline_phase_count_preserves_fields_and_no_max_records():
    with patch.object(project_timeline, "list_records", return_value=[
        {"fields": {"Phase": "A", "Status": "done"}},
        {"fields": {"Phase": "A", "Status": "open"}},
    ]) as read:
        assert project_timeline._count_phases_done() == []
    read.assert_called_once_with(
        "ProjectTimeline", limit=None, fields=["Phase", "Status"],
        paginate=False, timeout=10,
    )


def test_boundary_guard_for_profile_and_timeline():
    source = open("project_timeline.py", encoding="utf-8").read()
    ast.parse(source)
    assert not any(token in source for token in (
        "requests.", "httpx.", "api.airtable.com", "_at_url", "_at_headers",
        "_base_url", "from tools.airtable_gateway import _",
    ))


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"passed {len(tests)}")
