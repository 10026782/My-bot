"""Focused regression checks for Airtable Extraction Slice 4B."""

from __future__ import annotations

import ast
import os
from unittest.mock import patch

import profile
import project_timeline
from tools.airtable_read_adapter import AirtableReadError


def reset_profile_cache():
    profile._cache.update({"profile": None, "record_id": None, "ts": 0})


def test_profile_load_preserves_read_contract_and_merge():
    reset_profile_cache()
    with patch.object(profile, "list_records", return_value=[{
        "id": "rec-profile",
        "fields": {"ProfileData": '{"tone": "warm"}'},
    }]) as read:
        result = profile.load_profile()
    assert result["tone"] == "warm"
    assert result["name"] == profile.DEFAULT_PROFILE["name"]
    read.assert_called_once_with(
        "Profile", "{Name}='main'", max_records=1, paginate=False, timeout=10
    )
    assert profile._cache["record_id"] == "rec-profile"


def test_profile_create_update_and_failure_paths_preserve_payloads():
    reset_profile_cache()
    with patch.object(profile, "airtable_create", return_value={"id": "rec-new"}) as create:
        profile._create_profile_record()
    create.assert_called_once_with(
        "Profile",
        {"Name": "main", "ProfileData": __import__("json").dumps(profile.DEFAULT_PROFILE, ensure_ascii=False)},
        source="profile",
        timeout=10,
    )
    assert profile._cache["record_id"] == "rec-new"

    profile._cache["record_id"] = "rec-new"
    payload = {"name": "Dana"}
    with patch.object(profile, "airtable_patch", return_value=True) as patch_call:
        profile.save_profile(payload)
    patch_call.assert_called_once_with(
        "Profile", "rec-new", {"ProfileData": __import__("json").dumps(payload, ensure_ascii=False)},
        source="profile", timeout=10,
    )
    assert profile._cache["profile"] is payload

    reset_profile_cache()
    with patch.object(profile, "list_records", side_effect=AirtableReadError("Profile list error")):
        assert profile.load_profile() == profile.DEFAULT_PROFILE


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
        if args[1].startswith("OR("):
            return records
        return []

    with patch.dict(os.environ, {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
         patch.object(project_timeline, "list_records", side_effect=fake_list), \
         patch.object(project_timeline, "_count_phases_done", return_value=["A"]):
        summary = project_timeline.get_timeline_summary()

    assert summary["in_progress"] == [{"task": "T", "phase": "A", "due": "2999-01-01", "priority": "high"}]
    assert summary["done_today"] == 0
    assert calls[0] == (
        ("ProjectTimeline", "OR(Status='open', Status='in_progress')"),
        {"max_records": None, "sort": [{"field": "Due", "direction": "asc"}], "paginate": False, "timeout": 10},
    )
    assert calls[1][0][0] == "ProjectTimeline"
    assert calls[1][1] == {"max_records": None, "paginate": False, "timeout": 10}


def test_timeline_phase_count_preserves_fields_and_no_max_records():
    with patch.object(project_timeline, "list_records", return_value=[
        {"fields": {"Phase": "A", "Status": "done"}},
        {"fields": {"Phase": "A", "Status": "open"}},
    ]) as read:
        assert project_timeline._count_phases_done() == []
    read.assert_called_once_with(
        "ProjectTimeline", max_records=None, fields=["Phase", "Status"],
        paginate=False, timeout=10,
    )


def test_boundary_guard_for_profile_and_timeline():
    for filename in ("profile.py", "project_timeline.py"):
        source = open(filename, encoding="utf-8").read()
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
