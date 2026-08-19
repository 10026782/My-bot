"""External Capability Contract v1 — registry resolution + generic-boundary
decoupling from any single capability's name. No network, provider, or real
database."""

from dataclasses import replace

from core.external_capability_contract import (
    CapabilityContract,
    CapabilityRegistration,
    CapabilityRegistrationError,
    _build_registry,
    get_contract,
    resolve_adapter,
)
from core.external_execution_boundary import (
    ExternalExecutionBoundary,
    PollResult,
    SubmitResult,
)
from core.external_execution_repository import ExternalExecutionJob
from core.moneyprinterturbo_adapter import MoneyPrinterTurboAdapter


# ── Registry resolution ────────────────────────────────────────────────

def test_known_capability_resolves_to_the_registered_adapter():
    adapter = resolve_adapter("moneyprinterturbo")
    assert isinstance(adapter, MoneyPrinterTurboAdapter)


def test_unknown_capability_fails_closed():
    assert resolve_adapter("some_future_tool_nobody_registered") is None


def test_contract_metadata_matches_registered_capability():
    contract = get_contract("moneyprinterturbo")
    assert contract is not None
    assert contract.capability_id == "moneyprinterturbo"
    assert contract.execution_mode == "async"
    assert get_contract("unregistered_id") is None


# ── Registration-atomicity invariants ───────────────────────────────────
# CapabilityRegistration bundles a CapabilityContract with its adapter
# factory as one object with no defaults on either field — there is no
# constructor call that supplies one without the other, so these invariants
# are largely enforced by the type itself; the tests below cover the parts
# _build_registry()/resolve_adapter() still have to check at runtime.

def _contract(capability_id: str, adapter_name: str) -> CapabilityContract:
    return CapabilityContract(
        capability_id=capability_id,
        adapter_name=adapter_name,
        version="0",
        execution_mode="async",
        risk_class="low",
    )


class _StubAdapter:
    def __init__(self, name):
        self.name = name

    def submit(self, request):
        raise NotImplementedError

    def poll(self, job):
        raise NotImplementedError


def test_registration_requires_both_contract_and_factory():
    import inspect
    params = inspect.signature(CapabilityRegistration).parameters
    assert set(params) == {"contract", "adapter_factory"}
    assert all(p.default is inspect.Parameter.empty for p in params.values())


def test_duplicate_capability_id_registration_is_rejected():
    duplicate = [
        CapabilityRegistration(contract=_contract("dup", "dup"), adapter_factory=lambda: _StubAdapter("dup")),
        CapabilityRegistration(contract=_contract("dup", "dup"), adapter_factory=lambda: _StubAdapter("dup")),
    ]
    try:
        _build_registry(duplicate)
        assert False, "expected CapabilityRegistrationError"
    except CapabilityRegistrationError as exc:
        assert "dup" in str(exc)


def test_registry_key_can_never_drift_from_contract_capability_id():
    registry = _build_registry([
        CapabilityRegistration(contract=_contract("x", "x"), adapter_factory=lambda: _StubAdapter("x")),
    ])
    assert set(registry) == {"x"}
    assert registry["x"].contract.capability_id == "x"


def test_factory_adapter_name_mismatch_fails_closed_deterministically():
    registry = _build_registry([
        CapabilityRegistration(
            contract=_contract("mismatched", "expected_name"),
            adapter_factory=lambda: _StubAdapter("wrong_name"),
        ),
    ])
    from core import external_capability_contract as module
    original = module._REGISTRY
    module._REGISTRY = registry
    try:
        try:
            module.resolve_adapter("mismatched")
            assert False, "expected CapabilityRegistrationError"
        except CapabilityRegistrationError as exc:
            assert "wrong_name" in str(exc) and "expected_name" in str(exc)
    finally:
        module._REGISTRY = original


def test_factory_returning_adapter_missing_submit_or_poll_fails_closed():
    class Incomplete:
        name = "incomplete"
        # no submit()/poll()

    registry = _build_registry([
        CapabilityRegistration(contract=_contract("incomplete", "incomplete"), adapter_factory=Incomplete),
    ])
    from core import external_capability_contract as module
    original = module._REGISTRY
    module._REGISTRY = registry
    try:
        try:
            module.resolve_adapter("incomplete")
            assert False, "expected CapabilityRegistrationError"
        except CapabilityRegistrationError:
            pass
    finally:
        module._REGISTRY = original


# ── Generic boundary: no hardcoded capability name ─────────────────────

class FakeRepo:
    def __init__(self):
        self.jobs = {}

    def get(self, contract_id):
        job = self.jobs.get(contract_id)
        return replace(job) if job else None

    def create(self, job):
        self.jobs[job.contract_id] = replace(job)

    def update(self, job):
        self.jobs[job.contract_id] = replace(job)

    def list_for_adapter(self, adapter_name):
        return [j for j in self.jobs.values() if j.adapter_name == adapter_name]


class StubPolicy:
    """A capability policy that is NOT MPTExecutionPolicy and whose adapter
    is NOT named 'moneyprinterturbo' — proves capacity gating is driven by
    whatever policy the adapter declares, not a hardcoded name."""

    def __init__(self):
        self.calls = []

    def capacity_reason(self, jobs):
        self.calls.append(len(jobs))
        return "STUB_LIMIT" if jobs else ""


class GatedAdapter:
    name = "some_future_capability"

    def __init__(self, policy):
        self.policy = policy
        self.submit_calls = []

    def submit(self, request):
        self.submit_calls.append(request)
        return SubmitResult("accepted", "provider-1")


class UngatedAdapter:
    name = "another_future_capability"  # deliberately no .policy attribute

    def __init__(self):
        self.submit_calls = []

    def submit(self, request):
        self.submit_calls.append(request)
        return SubmitResult("accepted", "provider-1")

    def poll(self, job):
        return PollResult("outcome_unknown")


def test_non_mpt_adapter_capacity_policy_is_honored_by_generic_boundary():
    policy = StubPolicy()
    adapter = GatedAdapter(policy)
    boundary = ExternalExecutionBoundary(repository=FakeRepo(), adapter=adapter)
    first = boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    assert first.result == "completed"
    second = boundary.submit(contract_id="c2", idempotency_key="k2", payload={})
    assert second.result == "outcome_unknown"
    assert second.error_code == "STUB_LIMIT"
    assert len(adapter.submit_calls) == 1


def test_adapter_with_no_policy_attribute_gets_no_capacity_gating():
    adapter = UngatedAdapter()
    boundary = ExternalExecutionBoundary(repository=FakeRepo(), adapter=adapter)
    assert boundary.policy is None
    assert boundary.submit(contract_id="c1", idempotency_key="k1", payload={}).result == "completed"
    assert boundary.submit(contract_id="c2", idempotency_key="k2", payload={}).result == "completed"
    assert len(adapter.submit_calls) == 2


def test_explicit_policy_argument_overrides_adapter_declared_policy():
    override = StubPolicy()
    adapter = GatedAdapter(StubPolicy())
    boundary = ExternalExecutionBoundary(repository=FakeRepo(), adapter=adapter, policy=override)
    assert boundary.policy is override


def test_evidence_bounding_is_adapter_declared_not_hardcoded():
    adapter = UngatedAdapter()
    boundary = ExternalExecutionBoundary(repository=FakeRepo(), adapter=adapter)
    # a field only MoneyPrinterTurboAdapter declares must be stripped for an
    # adapter that never declared it.
    bounded = boundary._bounded_evidence({"provider_job_id": "x", "video_width": "1080"})
    assert bounded == {"provider_job_id": "x"}


def test_evidence_bounding_honors_mpt_extra_keys():
    boundary = ExternalExecutionBoundary(repository=FakeRepo(), adapter=MoneyPrinterTurboAdapter())
    bounded = boundary._bounded_evidence({"provider_job_id": "x", "video_width": "1080", "unlisted_field": "y"})
    assert bounded == {"provider_job_id": "x", "video_width": "1080"}


def test_adapter_submit_exception_is_outcome_unknown_not_a_crash():
    class ExplodingAdapter:
        name = "boom"

        def submit(self, request):
            raise RuntimeError("provider connection reset mid-request")

    boundary = ExternalExecutionBoundary(repository=FakeRepo(), adapter=ExplodingAdapter())
    outcome = boundary.submit(contract_id="c1", idempotency_key="k1", payload={})
    assert outcome.result == "outcome_unknown"


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
