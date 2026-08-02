import pytest

from airtable_schema import Tables, TaskFields
from core.router import (
    build_complete_task_proposal,
    build_create_task_proposal,
    build_update_task_proposal,
)


def test_create_builder_returns_named_approval_proposal():
    proposal = build_create_task_proposal("  Call supplier  ", **{TaskFields.DOMAIN: "general"})

    assert proposal.intent == "create_task"
    assert proposal.canonical_tool == "task_create"
    assert proposal.resource == Tables.TASKS
    assert proposal.fields[TaskFields.NAME] == "Call supplier"
    assert proposal.approval_required is True


def test_update_and_complete_builders_require_resolved_record():
    update = build_update_task_proposal("rec123", **{TaskFields.DESCRIPTION: "Call today"})
    complete = build_complete_task_proposal("rec123")

    assert update.fields == {"record_id": "rec123", TaskFields.DESCRIPTION: "Call today"}
    assert complete.canonical_tool == "task_complete"
    assert complete.fields == {"record_id": "rec123", TaskFields.STATUS: "בוצע"}


@pytest.mark.parametrize(
    "builder",
    [
        lambda: build_create_task_proposal(""),
        lambda: build_create_task_proposal("x", **{TaskFields.NAME: "duplicate"}),
        lambda: build_create_task_proposal("x", not_a_task_field="bad"),
        lambda: build_update_task_proposal("rec123"),
        lambda: build_update_task_proposal("", **{TaskFields.NAME: "x"}),
        lambda: build_complete_task_proposal(""),
    ],
)
def test_task_builders_fail_closed(builder):
    with pytest.raises(ValueError):
        builder()
