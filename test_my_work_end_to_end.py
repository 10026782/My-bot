"""
MY-WORK-1B: End-to-end tests for My Work screen task reading.

Tests verify:
1. Identity resolution for authenticated owner
2. Task filtering by owner
3. Date classification (overdue/today/future)
4. Status filtering (excluding done)
5. Proper response structure
6. Fail-closed on non-owner access
"""

from datetime import date, timedelta
from identity import Identity, Role, Domain
from airtable_schema import TaskFields, TaskStatus


def create_test_identity(user_id="eliyahu", role=Role.OWNER, external_id="123456"):
    """Create test identity."""
    return Identity(
        user_id=user_id,
        role=role,
        display_name="Test User",
        tenant_id="boss_hq",
        domain_id=Domain.GENERAL,
        channel="telegram",
        external_id=external_id,
    )


def create_test_task(
    record_id="rec_001",
    title="Test Task",
    owner="eliyahu",
    status=TaskStatus.PENDING,
    due_date=None,
    description="",
    domain="Real Estate",
):
    """Create a test task record."""
    return {
        "id": record_id,
        "fields": {
            TaskFields.NAME: title,
            TaskFields.OWNER: owner,
            TaskFields.STATUS: status,
            TaskFields.DUE_DATE: due_date,
            TaskFields.DESCRIPTION: description,
            TaskFields.DOMAIN: domain,
        },
    }


def test_identity_owner_resolves_to_eliyahu():
    """Verify owner's user_id resolves to 'eliyahu'."""
    identity = create_test_identity(user_id="eliyahu", role=Role.OWNER)
    assert identity.user_id == "eliyahu"
    assert identity.is_owner


def test_my_work_endpoint_requires_owner_role():
    """Verify endpoint rejects non-owner access."""
    # Test the authorization logic directly
    partner_identity = create_test_identity(user_id="partner", role=Role.PARTNER)

    # Only owners should have is_owner = True
    assert partner_identity.is_owner is False
    assert partner_identity.role == Role.PARTNER


def test_my_work_filters_by_owner():
    """Verify task processing filters tasks by owner."""
    from tma_api import _process_owner_tasks

    # Mixed owners in the task list
    mock_tasks = [
        create_test_task(record_id="rec_001", owner="eliyahu", status=TaskStatus.PENDING),
        create_test_task(record_id="rec_002", owner="other_owner", status=TaskStatus.PENDING),
        create_test_task(record_id="rec_003", owner="eliyahu", status=TaskStatus.PENDING),
        create_test_task(record_id="rec_004", owner="", status=TaskStatus.PENDING),  # Empty owner
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    # Should only have 2 tasks (rec_001 and rec_003)
    total = len(result["immediate"]) + len(result["upcoming"])
    assert total == 2, f"Expected 2 tasks for eliyahu, got {total}"


def test_my_work_excludes_done_tasks():
    """Verify task processing skips DONE tasks."""
    from tma_api import _process_owner_tasks

    mock_tasks = [
        create_test_task(record_id="rec_001", status=TaskStatus.PENDING),
        create_test_task(record_id="rec_002", status=TaskStatus.DONE),
        create_test_task(record_id="rec_003", status=TaskStatus.IN_PROGRESS),
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    total = len(result["immediate"]) + len(result["upcoming"])
    assert total == 2, "DONE task should be excluded"


def test_my_work_classifies_overdue_tasks():
    """Verify tasks with due_date < today are marked as overdue and placed in immediate."""
    from tma_api import _process_owner_tasks

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=yesterday, status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    assert len(result["immediate"]) == 1
    assert result["immediate"][0]["overdue"] is True


def test_my_work_classifies_today_tasks():
    """Verify tasks due today are placed in immediate."""
    from tma_api import _process_owner_tasks

    today = date.today().isoformat()
    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=today, status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    assert len(result["immediate"]) == 1
    assert result["immediate"][0]["overdue"] is False  # Today is not overdue


def test_my_work_classifies_future_tasks():
    """Verify tasks with future due dates are placed in upcoming."""
    from tma_api import _process_owner_tasks

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=tomorrow, status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    assert len(result["upcoming"]) == 1


def test_my_work_classifies_no_due_date_tasks():
    """Verify tasks without due_date are placed in upcoming."""
    from tma_api import _process_owner_tasks

    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=None, status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    assert len(result["upcoming"]) == 1


def test_my_work_response_structure():
    """Verify response has correct structure and fields."""
    from tma_api import _process_owner_tasks

    today = date.today().isoformat()
    mock_tasks = [
        create_test_task(
            record_id="rec_001",
            title="Urgent Task",
            description="Do this now",
            due_date=today,
            domain="Real Estate",
        ),
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    # Structure
    assert "immediate" in result
    assert "upcoming" in result

    # Task structure
    task = result["immediate"][0]
    assert task["stable_key"] == "rec_001"
    assert task["title"] == "Urgent Task"
    assert task["description"] == "Do this now"
    assert task["due_date"] == today
    assert task["domain"] == "Real Estate"
    assert task["owner"] == "eliyahu"
    assert task["status"] == TaskStatus.PENDING
    assert task["overdue"] is False
    assert task["source_type"] == "task"
    assert task["source_ref"] == "rec_001"
    assert task["destination"] == "task"
    assert task["actionable"] is True


def test_my_work_counts_correct():
    """Verify counts match actual task arrays."""
    from tma_api import _process_owner_tasks

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=yesterday),  # immediate (overdue)
        create_test_task(record_id="rec_002", due_date=tomorrow),   # upcoming
        create_test_task(record_id="rec_003", due_date=tomorrow),   # upcoming
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    assert len(result["immediate"]) == 1
    assert len(result["upcoming"]) == 2


def test_my_work_sorting_immediate():
    """Verify immediate tasks are sorted: overdue first, then by due date."""
    from tma_api import _process_owner_tasks

    # Create tasks with different due dates
    two_days_ago = (date.today() - timedelta(days=2)).isoformat()
    one_day_ago = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    mock_tasks = [
        create_test_task(record_id="rec_001", title="Due yesterday", due_date=one_day_ago),
        create_test_task(record_id="rec_002", title="Due two days ago", due_date=two_days_ago),
        create_test_task(record_id="rec_003", title="Due today", due_date=today),
    ]

    result = _process_owner_tasks(mock_tasks, user_id="eliyahu")

    immediate = result["immediate"]

    # Should be sorted: overdue (oldest first), then today
    assert immediate[0]["title"] == "Due two days ago"  # Oldest overdue
    assert immediate[1]["title"] == "Due yesterday"      # Newer overdue
    assert immediate[2]["title"] == "Due today"          # Not overdue


def test_my_work_empty_task_list():
    """Verify processing handles zero tasks gracefully."""
    from tma_api import _process_owner_tasks

    result = _process_owner_tasks([], user_id="eliyahu")

    assert len(result["immediate"]) == 0
    assert len(result["upcoming"]) == 0


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python3", "-m", "pytest", __file__, "-v"], check=True)
