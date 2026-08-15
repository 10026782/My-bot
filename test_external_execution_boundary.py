"""Focused architecture tests; no network, provider, or real database."""

from dataclasses import replace

from core.external_execution_boundary import (
    ExternalExecutionBoundary,
    PollResult,
    SubmitResult,
)
from core.external_execution_repository import ExternalExecutionJob
from core.external_poll_lease import PollLease


class FakeRepo:
    def __init__(self):
        self.jobs = {}
        self.events = []
        self.fail_read = False
        self.fail_write = False

    def get(self, contract_id):
        if self.fail_read:
            raise RuntimeError("airtable read failed")
        job = self.jobs.get(contract_id)
        return replace(job) if job else None

    def create(self, job):
        self.events.append("create")
        self.jobs[job.contract_id] = replace(job)

    def update(self, job):
        if self.fail_write:
            raise RuntimeError("airtable write failed")
        self.events.append("update")
        self.jobs[job.contract_id] = replace(job)

    def due_submitted(self, **_):
        return [job for job in self.jobs.values() if job.status == "submitted"]


class FakeLease:
    def __init__(self):
        self.active = None
        self.next_token = 0
        self.releases = []

    def acquire(self, job_id, poller_id, lease_seconds=120):
        if self.active:
            return None
        self.next_token += 1
        self.active = PollLease(job_id, f"token-{self.next_token}", poller_id)
        return self.active

    def release(self, lease):
        if self.active and self.active.lease_token == lease.lease_token:
            self.releases.append(lease.lease_token)
            self.active = None
            return True
        return False


class FakeAdapter:
    name = "fake"

    def __init__(self, submit_result=None, poll_result=None):
        self.submit_result = submit_result or SubmitResult("accepted", "provider-1")
        self.poll_result = poll_result or PollResult("completed", result_ref="result-1")
        self.submit_calls = []
        self.poll_calls = []

    def submit(self, request):
        self.submit_calls.append(request)
        return self.submit_result

    def poll(self, job):
        self.poll_calls.append(job.contract_id)
        return self.poll_result


def make_boundary(adapter=None, repo=None, lease=None):
    return ExternalExecutionBoundary(
        repository=repo or FakeRepo(),
        lease_repository=lease or FakeLease(),
        adapter=adapter or FakeAdapter(),
        poll_interval_seconds=0,
    )


def test_create_before_submit_and_action_completion_is_submission_only():
    repo = FakeRepo()
    adapter = FakeAdapter()
    outcome = make_boundary(adapter, repo).submit(contract_id="c1", idempotency_key="k1", payload={"x": 1})
    assert outcome.result == "completed"
    assert repo.events[:2] == ["create", "update"]
    assert repo.jobs["c1"].status == "submitted"
    assert adapter.submit_calls[0]["idempotency_key"] == "k1"
    assert repo.jobs["c1"].status != "completed"


def test_same_contract_and_idempotency_key_never_submit_twice():
    repo = FakeRepo()
    adapter = FakeAdapter()
    boundary = make_boundary(adapter, repo)
    boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    assert len(adapter.submit_calls) == 1


def test_poll_completes_job_and_terminal_outcome_unknown_is_not_resubmitted():
    repo = FakeRepo()
    adapter = FakeAdapter(poll_result=PollResult("outcome_unknown", failure_code="timeout"))
    boundary = make_boundary(adapter, repo)
    boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    assert boundary.poll_due(poller_id="a") == 1
    assert repo.jobs["c1"].status == "outcome_unknown"
    boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    assert len(adapter.submit_calls) == 1


def test_successful_poll_is_the_only_external_completion():
    repo = FakeRepo()
    adapter = FakeAdapter(poll_result=PollResult("completed", result_ref="sha256:abc"))
    boundary = make_boundary(adapter, repo)
    boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    assert boundary.completed_job("c1") is None
    assert boundary.poll_due(poller_id="restart-B") == 1
    assert repo.jobs["c1"].status == "completed"
    assert repo.jobs["c1"].result_ref == "sha256:abc"
    assert boundary.completed_job("c1").contract_id == "c1"


def test_two_pollers_and_expired_token_release_guard():
    repo = FakeRepo()
    lease = FakeLease()
    adapter = FakeAdapter()
    boundary = make_boundary(adapter, repo, lease)
    boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    first = lease.acquire("c1", "a")
    assert lease.acquire("c1", "b") is None
    lease.active = None  # test fixture simulates TTL expiry
    second = lease.acquire("c1", "b")
    assert second and second.lease_token != first.lease_token
    assert lease.release(first) is False
    assert lease.active == second


def test_terminal_and_read_failure_are_fail_closed_without_poll():
    repo = FakeRepo()
    adapter = FakeAdapter()
    lease = FakeLease()
    boundary = make_boundary(adapter, repo, lease)
    boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    repo.jobs["c1"] = replace(repo.jobs["c1"], status="completed")
    assert boundary.poll_due() == 0
    assert adapter.poll_calls == []
    repo.fail_read = True
    assert boundary.poll_due() == 0
    assert adapter.poll_calls == []
    assert lease.active is None


def test_provider_success_with_write_failure_does_not_resubmit():
    repo = FakeRepo()
    adapter = FakeAdapter()
    boundary = make_boundary(adapter, repo)
    boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    repo.fail_write = True
    assert boundary.poll_due() == 0
    assert len(adapter.poll_calls) == 1
    assert len(adapter.submit_calls) == 1
    assert repo.jobs["c1"].status == "submitted"
