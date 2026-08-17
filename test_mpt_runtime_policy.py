import time

from core.external_execution_boundary import ExternalExecutionBoundary, SubmitResult
from core.external_execution_repository import ExternalExecutionJob
from core.mpt_runtime_policy import MPTExecutionPolicy, classify_failure


class Repo:
    def __init__(self, jobs=()):
        self.jobs = {job.contract_id: job for job in jobs}

    def get(self, contract_id):
        return self.jobs.get(contract_id)

    def create(self, job):
        self.jobs[job.contract_id] = job

    def update(self, job):
        self.jobs[job.contract_id] = job

    def list_for_adapter(self, adapter_name):
        return [job for job in self.jobs.values() if job.adapter_name == adapter_name]


class Adapter:
    name = "moneyprinterturbo"
    submits = 0

    def submit(self, request):
        type(self).submits += 1
        return SubmitResult("accepted", "provider-1")


def test_capacity_one_blocks_second_and_releases_after_terminal():
    Adapter.submits = 0
    repo = Repo()
    policy = MPTExecutionPolicy(max_concurrent=1, max_per_day=10, max_runtime_seconds=1800)
    boundary = ExternalExecutionBoundary(repository=repo, adapter=Adapter(), policy=policy)
    assert boundary.submit(contract_id="c1", idempotency_key="k1", payload={}).result == "completed"
    assert boundary.submit(contract_id="c2", idempotency_key="k2", payload={}).result == "outcome_unknown"
    assert boundary.submit(contract_id="c2", idempotency_key="k2", payload={}).result == "outcome_unknown"
    assert Adapter.submits == 1
    repo.jobs["c1"].status = "completed"
    assert boundary.submit(contract_id="c3", idempotency_key="k3", payload={}).result == "completed"
    assert Adapter.submits == 2


def test_daily_ceiling_and_completed_jobs_do_not_consume_active_capacity():
    now = time.time()
    policy = MPTExecutionPolicy(max_concurrent=1, max_per_day=1)
    completed = ExternalExecutionJob("c1", "moneyprinterturbo", status="completed", submitted_at=now)
    assert policy.active_count([completed]) == 0
    assert policy.daily_count([completed], now=now) == 1
    assert not policy.capacity_available([completed], now=now)


def test_failure_classification_and_retry_boundaries():
    assert classify_failure(exit_code=137, failure_code="mpt_process_failed") == "RESOURCE_LIMIT"
    assert classify_failure(failure_code="mpt_timeout") == "TIMEOUT"
    assert classify_failure(failure_code="mpt_network") == "TRANSIENT_NETWORK"
    policy = MPTExecutionPolicy()
    assert policy.retry_allowed("TRANSIENT_NETWORK", 0)
    assert not policy.retry_allowed("TRANSIENT_NETWORK", 1)
    assert not policy.retry_allowed("RESOURCE_LIMIT", 0)
    assert not policy.retry_allowed("OUTCOME_UNKNOWN", 0)


def test_runtime_profile_is_fail_closed_when_explicit():
    policy = MPTExecutionPolicy(runtime_profile="starter-512mb")
    assert not policy.runtime_supported()
    assert MPTExecutionPolicy(runtime_profile="standard-2gb").runtime_supported()


def test_restart_reuses_durable_active_capacity():
    Adapter.submits = 0
    repo = Repo()
    first = ExternalExecutionJob("c1", "moneyprinterturbo", status="submitted", submitted_at=time.time())
    repo.jobs[first.contract_id] = first
    policy = MPTExecutionPolicy(max_concurrent=1, max_per_day=10)
    restarted = ExternalExecutionBoundary(repository=repo, adapter=Adapter(), policy=policy)
    result = restarted.submit(contract_id="c2", idempotency_key="k2", payload={})
    assert result.result == "outcome_unknown"
    assert Adapter.submits == 0
