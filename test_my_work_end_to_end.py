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

import os
from datetime import date, timedelta

import identity as identity_module
import tma_api
from identity import Identity, Role, Domain
from airtable_schema import TaskFields, TaskStatus, Tables


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


# ══════════════════════════════════════════════════════════════════
# MY-WORK-1C: real resolve_identity() proof (not a hand-built Identity)
# ══════════════════════════════════════════════════════════════════

def test_resolve_identity_real_owner_mapping():
    """Prove the actual resolve_identity() maps a Telegram owner chat ID
    to user_id='eliyahu'/role=OWNER via the real registry-loading path,
    not a hand-constructed Identity object."""
    orig_registry = identity_module._REGISTRY
    orig_env = os.environ.get("ELIYAHU_CHAT_ID")
    test_chat_id = "999999"
    try:
        os.environ["ELIYAHU_CHAT_ID"] = test_chat_id
        identity_module._REGISTRY = identity_module._load_registry()

        resolved = identity_module.resolve_identity("telegram", test_chat_id)

        assert resolved.user_id == "eliyahu"
        assert resolved.role == Role.OWNER
        assert resolved.is_owner is True
        assert resolved.tenant_id == "boss_hq"
    finally:
        if orig_env is None:
            os.environ.pop("ELIYAHU_CHAT_ID", None)
        else:
            os.environ["ELIYAHU_CHAT_ID"] = orig_env
        identity_module._REGISTRY = orig_registry


def test_resolve_identity_unknown_telegram_id_is_not_owner():
    """A Telegram ID absent from the registry must never resolve to owner."""
    orig_registry = identity_module._REGISTRY
    orig_env = os.environ.get("ELIYAHU_CHAT_ID")
    try:
        os.environ["ELIYAHU_CHAT_ID"] = "999999"
        identity_module._REGISTRY = identity_module._load_registry()

        resolved = identity_module.resolve_identity("telegram", "000000_unknown")

        assert resolved.user_id != "eliyahu"
        assert resolved.is_owner is False
    finally:
        if orig_env is None:
            os.environ.pop("ELIYAHU_CHAT_ID", None)
        else:
            os.environ["ELIYAHU_CHAT_ID"] = orig_env
        identity_module._REGISTRY = orig_registry


# ══════════════════════════════════════════════════════════════════
# MY-WORK-1C: real Flask route tests for GET /api/owner/my-work
# (established pattern: see test_tma_projects_read_path_optimization.py)
# ══════════════════════════════════════════════════════════════════

def _make_client():
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    return app.test_client()


_HDR = {"X-Telegram-Init-Data": "x"}


def test_route_get_my_work_returns_200_and_filters_by_owner():
    """Full route: auth -> identity -> Airtable read -> owner-scoped response."""
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity
    orig_at_list = tma_api._at_list

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="eliyahu")

    captured_calls = []

    def fake_at_list(table, formula="", max_records=50, strict=False):
        captured_calls.append((table, formula, max_records))
        # Airtable would already filter server-side, but mixing owners here
        # also proves the route's own safety-check excludes non-matching rows.
        return [
            create_test_task(record_id="rec_mine", owner="eliyahu", status=TaskStatus.PENDING),
            create_test_task(record_id="rec_other", owner="other_owner", status=TaskStatus.PENDING),
        ]

    tma_api._at_list = fake_at_list

    try:
        r = client.get("/api/owner/my-work", headers=_HDR)
        body = r.get_json()

        assert r.status_code == 200
        assert len(captured_calls) == 1
        table, formula, max_records = captured_calls[0]
        assert table == Tables.TASKS
        assert "eliyahu" in formula

        stable_keys = [t["stable_key"] for t in body["immediate"] + body["upcoming"]]
        assert "rec_mine" in stable_keys
        assert "rec_other" not in stable_keys
        assert body["ok"] is True
        assert "generated_at" in body
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_list = orig_at_list


def test_route_get_my_work_non_owner_returns_403():
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "222222"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="partner", role=Role.PARTNER)

    try:
        r = client.get("/api/owner/my-work", headers=_HDR)
        assert r.status_code == 403
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve


def test_route_get_my_work_airtable_failure_returns_500():
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity
    orig_at_list = tma_api._at_list

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="eliyahu")

    def failing_at_list(*a, **kw):
        raise RuntimeError("Airtable timeout")

    tma_api._at_list = failing_at_list

    try:
        r = client.get("/api/owner/my-work", headers=_HDR)
        assert r.status_code == 500
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_list = orig_at_list


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python3", "-m", "pytest", __file__, "-v"], check=True)
