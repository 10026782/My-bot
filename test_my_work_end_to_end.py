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
from airtable_schema import TaskFields, TaskStatus, Tables, ProfileFields, LeadFields
from tools.airtable_read_adapter import render_query


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


OWNER_RECORD_ID = "recProfileEliyahu"
OTHER_OWNER_RECORD_ID = "recProfileOther"


def create_test_task(
    record_id="rec_001",
    title="Test Task",
    owner_record_ids=(OWNER_RECORD_ID,),
    status=TaskStatus.PENDING,
    due_date=None,
    description="",
    domain="Real Estate",
):
    """Create a test task record. Owner is a multipleRecordLinks field on
    the real Airtable table -> a list of Profile record IDs, not a string."""
    return {
        "id": record_id,
        "fields": {
            TaskFields.NAME: title,
            TaskFields.OWNER: list(owner_record_ids) if owner_record_ids else [],
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
    """Verify task processing filters tasks by owner (Profile linked-record ID)."""
    from tma_api import _process_owner_tasks

    # Mixed owners in the task list
    mock_tasks = [
        create_test_task(record_id="rec_001", owner_record_ids=(OWNER_RECORD_ID,), status=TaskStatus.PENDING),
        create_test_task(record_id="rec_002", owner_record_ids=(OTHER_OWNER_RECORD_ID,), status=TaskStatus.PENDING),
        create_test_task(record_id="rec_003", owner_record_ids=(OWNER_RECORD_ID,), status=TaskStatus.PENDING),
        create_test_task(record_id="rec_004", owner_record_ids=(), status=TaskStatus.PENDING),  # Empty owner
    ]

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

    # rec_001, rec_003 (explicitly mine) + rec_004 (unowned, defaults to me).
    # rec_002 (explicitly someone else's) stays excluded.
    total = len(result["immediate"]) + len(result["upcoming"])
    assert total == 3, f"Expected 3 tasks for eliyahu, got {total}"


def test_my_work_unowned_task_defaults_to_requesting_owner():
    """A task with no Owner link at all is shown to the (sole) owner, not hidden."""
    from tma_api import _process_owner_tasks

    mock_tasks = [
        create_test_task(record_id="rec_unowned", owner_record_ids=(), status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

    total = len(result["immediate"]) + len(result["upcoming"])
    assert total == 1, "Unowned task must default to the requesting owner"


def test_my_work_multi_owner_task_visible_to_each_linked_owner():
    """A task linked to multiple Profile owners must appear for each of them."""
    from tma_api import _process_owner_tasks

    mock_tasks = [
        create_test_task(record_id="rec_shared", owner_record_ids=(OWNER_RECORD_ID, OTHER_OWNER_RECORD_ID)),
    ]

    result_a = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")
    result_b = _process_owner_tasks(mock_tasks, OTHER_OWNER_RECORD_ID, "partner")

    assert len(result_a["immediate"]) + len(result_a["upcoming"]) == 1
    assert len(result_b["immediate"]) + len(result_b["upcoming"]) == 1


def test_my_work_excludes_done_tasks():
    """Verify task processing skips DONE tasks."""
    from tma_api import _process_owner_tasks

    mock_tasks = [
        create_test_task(record_id="rec_001", status=TaskStatus.PENDING),
        create_test_task(record_id="rec_002", status=TaskStatus.DONE),
        create_test_task(record_id="rec_003", status=TaskStatus.IN_PROGRESS),
    ]

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

    total = len(result["immediate"]) + len(result["upcoming"])
    assert total == 2, "DONE task should be excluded"


def test_my_work_classifies_overdue_tasks():
    """Verify tasks with due_date < today are marked as overdue and placed in immediate."""
    from tma_api import _process_owner_tasks

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=yesterday, status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

    assert len(result["immediate"]) == 1
    assert result["immediate"][0]["overdue"] is True


def test_my_work_classifies_today_tasks():
    """Verify tasks due today are placed in immediate."""
    from tma_api import _process_owner_tasks

    today = date.today().isoformat()
    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=today, status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

    assert len(result["immediate"]) == 1
    assert result["immediate"][0]["overdue"] is False  # Today is not overdue


def test_my_work_classifies_future_tasks():
    """Verify tasks with future due dates are placed in upcoming."""
    from tma_api import _process_owner_tasks

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=tomorrow, status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

    assert len(result["upcoming"]) == 1


def test_my_work_classifies_no_due_date_tasks():
    """Verify tasks without due_date are placed in upcoming."""
    from tma_api import _process_owner_tasks

    mock_tasks = [
        create_test_task(record_id="rec_001", due_date=None, status=TaskStatus.PENDING),
    ]

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

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

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

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

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

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

    result = _process_owner_tasks(mock_tasks, OWNER_RECORD_ID, "eliyahu")

    immediate = result["immediate"]

    # Should be sorted: overdue (oldest first), then today
    assert immediate[0]["title"] == "Due two days ago"  # Oldest overdue
    assert immediate[1]["title"] == "Due yesterday"      # Newer overdue
    assert immediate[2]["title"] == "Due today"          # Not overdue


def test_my_work_empty_task_list():
    """Verify processing handles zero tasks gracefully."""
    from tma_api import _process_owner_tasks

    result = _process_owner_tasks([], OWNER_RECORD_ID, "eliyahu")

    assert len(result["immediate"]) == 0
    assert len(result["upcoming"]) == 0


# ══════════════════════════════════════════════════════════════════
# MY-WORK-1C: Owner is a multipleRecordLinks field -> Tables.PROFILE
# (verified via Airtable MCP 2026-08-19; see _resolve_profile_record_id).
# ══════════════════════════════════════════════════════════════════

def test_resolve_profile_record_id_matches_case_insensitively():
    """Live Profile.name is 'Eliyahu' (capitalized); identity.user_id is
    lowercase 'eliyahu' -- resolution must not depend on exact case."""
    from tma_api import _resolve_profile_record_id

    import core.owner_resolution as owner_resolution

    orig_list_records = owner_resolution.list_records
    captured = []

    def fake_list_records(table, formula="", max_records=50, paginate=True):
        captured.append((table, formula, max_records))
        return [{"id": OWNER_RECORD_ID, "fields": {ProfileFields.NAME: "Eliyahu"}}]

    owner_resolution.list_records = fake_list_records
    try:
        result = _resolve_profile_record_id("eliyahu")
        assert result == OWNER_RECORD_ID
        assert captured[0][0] == Tables.PROFILE
        assert "LOWER" in render_query(captured[0][1])
    finally:
        owner_resolution.list_records = orig_list_records


def test_resolve_profile_record_id_no_match_returns_none():
    from tma_api import _resolve_profile_record_id
    import core.owner_resolution as owner_resolution

    orig_list_records = owner_resolution.list_records
    owner_resolution.list_records = lambda table, formula="", max_records=50, paginate=True: []
    try:
        assert _resolve_profile_record_id("nobody") is None
    finally:
        owner_resolution.list_records = orig_list_records


def test_resolve_profile_record_id_empty_user_id_returns_none():
    from tma_api import _resolve_profile_record_id

    assert _resolve_profile_record_id("") is None


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


def _fake_at_list_for_route(profile_records, task_records, captured_calls):
    """Owner is linked-record -> the route makes two _at_list calls: one
    against Tables.PROFILE to resolve the owner, one against Tables.TASKS
    to read all tasks (filtered by Owner in Python, not by formula)."""
    def fake_at_list(table, formula="", max_records=50, strict=False):
        captured_calls.append((table, formula, max_records))
        if table == Tables.PROFILE:
            return profile_records
        if table == Tables.TASKS:
            return task_records
        return []
    return fake_at_list


def test_route_get_my_work_returns_200_and_filters_by_owner():
    """Full route: auth -> identity -> Profile resolve -> Airtable read -> owner-scoped response."""
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity
    orig_at_list = tma_api._at_list
    import core.owner_resolution as owner_resolution
    orig_list_records = owner_resolution.list_records

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="eliyahu")

    captured_calls = []
    profile_records = [{"id": OWNER_RECORD_ID, "fields": {ProfileFields.NAME: "Eliyahu"}}]
    task_records = [
        create_test_task(record_id="rec_mine", owner_record_ids=(OWNER_RECORD_ID,), status=TaskStatus.PENDING),
        create_test_task(record_id="rec_other", owner_record_ids=(OTHER_OWNER_RECORD_ID,), status=TaskStatus.PENDING),
    ]
    tma_api._at_list = _fake_at_list_for_route(profile_records, task_records, captured_calls)
    owner_resolution.list_records = lambda table, formula="", max_records=50, paginate=True: (
        captured_calls.append((table, formula, max_records)) or profile_records
    )

    try:
        r = client.get("/api/owner/my-work", headers=_HDR)
        body = r.get_json()

        assert r.status_code == 200
        tables_queried = [c[0] for c in captured_calls]
        assert tables_queried == [Tables.PROFILE, Tables.TASKS]

        stable_keys = [t["stable_key"] for t in body["immediate"] + body["upcoming"]]
        assert "rec_mine" in stable_keys
        assert "rec_other" not in stable_keys
        assert body["ok"] is True
        assert "generated_at" in body
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_list = orig_at_list
        owner_resolution.list_records = orig_list_records


def test_route_get_my_work_no_profile_record_returns_empty_not_500():
    """Owner identity with no matching Profile row must fail closed to an
    empty list, not crash or leak a mismatch as a 500."""
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity
    orig_at_list = tma_api._at_list
    import core.owner_resolution as owner_resolution
    orig_list_records = owner_resolution.list_records

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="ghost_user")
    tma_api._at_list = lambda table, formula="", max_records=50, strict=False: []
    owner_resolution.list_records = lambda table, formula="", max_records=50, paginate=True: []

    try:
        r = client.get("/api/owner/my-work", headers=_HDR)
        body = r.get_json()
        assert r.status_code == 200
        assert body["immediate"] == []
        assert body["upcoming"] == []
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_list = orig_at_list
        owner_resolution.list_records = orig_list_records


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
    import core.owner_resolution as owner_resolution
    orig_list_records = owner_resolution.list_records

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="eliyahu")

    profile_records = [{"id": OWNER_RECORD_ID, "fields": {ProfileFields.NAME: "Eliyahu"}}]

    def failing_at_list(table, formula="", max_records=50, strict=False):
        if table == Tables.PROFILE:
            return profile_records
        raise RuntimeError("Airtable timeout")

    tma_api._at_list = failing_at_list
    owner_resolution.list_records = lambda table, formula="", max_records=50, paginate=True: profile_records

    try:
        r = client.get("/api/owner/my-work", headers=_HDR)
        assert r.status_code == 500
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_list = orig_at_list
        owner_resolution.list_records = orig_list_records


# ══════════════════════════════════════════════════════════════════
# MY-WORK-1C: write-path fix -- POST /api/leads/<id>/task must give the
# created task a real Owner. Leads.Owner is never written anywhere in this
# codebase (grepped), so it's always empty; the task must default Owner to
# the creator's own Profile record, or no task would ever get one.
# ══════════════════════════════════════════════════════════════════

def _fake_owner_autoapprove_gateway(posted):
    """C05-C07 Finding #3 remediation: Owner writes now go through the same
    ActionGateway pipeline as Manager (_queue_or_owner_execute ->
    _queue_tma_write_approval -> propose_action, then, for Owner only,
    _claim_and_execute_approval). Stubs both gateway seams so these tests
    keep verifying only what they always cared about — the constructed
    Airtable payload — without needing a real ActionGateway/PostgreSQL/
    Airtable stack. Returns the (fake_queue, fake_claim_execute) pair to
    assign onto tma_api._queue_tma_write_approval / tma_api._claim_and_execute_approval."""

    def fake_queue(action, payload, identity, label):
        posted.append((payload["table"], payload["fields"]))
        return "fake_approval_1", {
            "status": "pending_approval", "approval_id": "fake_approval_1", "contract_id": "fake_contract_1",
        }, 202

    def fake_claim_execute(approval_id, identity):
        return {
            "ok": True, "status_code": 200, "new_status": "approved",
            "action_label": "test", "ctx_id": "", "bus_synced": False,
            "execution_result": {"message": "✅", "contract_status": "executed"},
        }

    return fake_queue, fake_claim_execute


def test_create_lead_task_defaults_owner_to_creator_when_lead_has_none():
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity
    orig_get_record = tma_api._at_get_record
    orig_queue = tma_api._queue_tma_write_approval
    orig_claim_execute = tma_api._claim_and_execute_approval
    orig_at_list = tma_api._at_list
    import core.owner_resolution as owner_resolution
    orig_list_records = owner_resolution.list_records

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="eliyahu", role=Role.OWNER)
    tma_api._at_get_record = lambda table, rid: {"id": rid, "fields": {}}  # lead with no Owner
    tma_api._at_list = lambda table, formula="", max_records=50, strict=False: (
        []
    )
    owner_resolution.list_records = lambda table, formula="", max_records=50, paginate=True: [
        {"id": OWNER_RECORD_ID, "fields": {ProfileFields.NAME: "Eliyahu"}}
    ]

    posted = []
    tma_api._queue_tma_write_approval, tma_api._claim_and_execute_approval = _fake_owner_autoapprove_gateway(posted)

    try:
        r = client.post("/api/leads/recLEAD001/task", json={"title": "call back"}, headers=_HDR)
        assert r.status_code == 200
        task_posts = [(t, f) for t, f in posted if t == Tables.TASKS]
        assert len(task_posts) == 1
        table, fields = task_posts[0]
        assert fields[TaskFields.OWNER] == [OWNER_RECORD_ID]
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_get_record = orig_get_record
        tma_api._queue_tma_write_approval = orig_queue
        tma_api._claim_and_execute_approval = orig_claim_execute
        tma_api._at_list = orig_at_list
        owner_resolution.list_records = orig_list_records


def test_create_lead_task_preserves_lead_owner_when_present():
    """Lead already has an Owner linked -> task copies it, does not override with creator."""
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity
    orig_get_record = tma_api._at_get_record
    orig_queue = tma_api._queue_tma_write_approval
    orig_claim_execute = tma_api._claim_and_execute_approval
    orig_at_list = tma_api._at_list

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="eliyahu", role=Role.OWNER)
    tma_api._at_get_record = lambda table, rid: {
        "id": rid, "fields": {LeadFields.OWNER: [OTHER_OWNER_RECORD_ID]},
    }
    tma_api._at_list = lambda table, formula="", max_records=50, strict=False: []

    posted = []
    tma_api._queue_tma_write_approval, tma_api._claim_and_execute_approval = _fake_owner_autoapprove_gateway(posted)

    try:
        r = client.post("/api/leads/recLEAD001/task", json={"title": "call back"}, headers=_HDR)
        assert r.status_code == 200
        assert posted[0][1][TaskFields.OWNER] == [OTHER_OWNER_RECORD_ID]
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_get_record = orig_get_record
        tma_api._queue_tma_write_approval = orig_queue
        tma_api._claim_and_execute_approval = orig_claim_execute
        tma_api._at_list = orig_at_list


def test_resolve_profile_display_names_resolves_ids_to_names():
    from tma_api import _resolve_profile_display_names

    orig_get_record = tma_api._at_get_record
    profiles = {
        OWNER_RECORD_ID: {"id": OWNER_RECORD_ID, "fields": {ProfileFields.NAME: "Eliyahu"}},
        OTHER_OWNER_RECORD_ID: {"id": OTHER_OWNER_RECORD_ID, "fields": {ProfileFields.NAME: "Partner"}},
    }
    tma_api._at_get_record = lambda table, rid: profiles.get(rid)

    try:
        names = _resolve_profile_display_names([OWNER_RECORD_ID, OTHER_OWNER_RECORD_ID])
        assert names == ["Eliyahu", "Partner"]
        assert _resolve_profile_display_names([]) == []
        assert _resolve_profile_display_names(["recMissing"]) == []
    finally:
        tma_api._at_get_record = orig_get_record


def test_route_get_lead_detail_resolves_owner_to_display_name():
    """GET /api/leads/<id>: Owner is a linked-record field -> the response
    must carry a resolved name, never a raw 'recXXX' id (see PR #766)."""
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity
    orig_get_record = tma_api._at_get_record
    orig_at_list = tma_api._at_list

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="eliyahu", role=Role.OWNER)
    tma_api._at_list = lambda table, formula="", max_records=50, strict=False: []

    records = {
        "recLEAD001": {"id": "recLEAD001", "fields": {LeadFields.NAME: "Test Lead", LeadFields.OWNER: [OWNER_RECORD_ID]}},
        OWNER_RECORD_ID: {"id": OWNER_RECORD_ID, "fields": {ProfileFields.NAME: "Eliyahu"}},
    }
    tma_api._at_get_record = lambda table, rid: records.get(rid)

    try:
        r = client.get("/api/leads/recLEAD001", headers=_HDR)
        body = r.get_json()
        assert r.status_code == 200
        assert body["owner"] == "Eliyahu", f"expected resolved name, got {body['owner']!r}"
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_get_record = orig_get_record
        tma_api._at_list = orig_at_list


def test_route_get_lead_detail_no_owner_returns_empty_string():
    """A lead with no Owner link at all -> owner is "", not None/[]."""
    orig_validate = tma_api._validate_initdata
    orig_resolve = tma_api.resolve_identity
    orig_get_record = tma_api._at_get_record
    orig_at_list = tma_api._at_list

    client = _make_client()
    tma_api._validate_initdata = lambda s: {"id": "999999"}
    tma_api.resolve_identity = lambda ch, tid: create_test_identity(user_id="eliyahu", role=Role.OWNER)
    tma_api._at_list = lambda table, formula="", max_records=50, strict=False: []
    tma_api._at_get_record = lambda table, rid: {"id": "recLEAD002", "fields": {LeadFields.NAME: "Unowned Lead"}}

    try:
        r = client.get("/api/leads/recLEAD002", headers=_HDR)
        body = r.get_json()
        assert r.status_code == 200
        assert body["owner"] == ""
    finally:
        tma_api._validate_initdata = orig_validate
        tma_api.resolve_identity = orig_resolve
        tma_api._at_get_record = orig_get_record
        tma_api._at_list = orig_at_list


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python3", "-m", "pytest", __file__, "-v"], check=True)
