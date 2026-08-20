"""External Capability Contract v1.

Small, stable metadata contract describing an external capability (adapter)
to the generic ExternalExecutionBoundary, plus an explicit, fail-closed
capability_id -> adapter registry.

Design invariants (see docs/architecture/EXTERNAL_CAPABILITY_CONTRACT_V1.md):
- Explicit, code-reviewed registry only. No dynamic imports of user-supplied
  names, no plugin auto-discovery, no arbitrary module loading.
- A capability is registered atomically as one CapabilityRegistration
  (contract + adapter factory together) — there is no way to add a contract
  without a factory, or a factory without a contract, and no way for the
  registry key to drift from the contract's own capability_id: the key is
  derived from the contract, never typed twice.
- Unknown capability_id resolves to None (fail closed) — callers must treat
  that the same as "not configured", never as a default/fallback capability.
- This module carries metadata only; it never gates ActionGateway/dispatcher
  authority, identity, permissions, or approval — those remain upstream of
  the boundary regardless of which capability was resolved here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CapabilityContract:
    capability_id: str
    adapter_name: str
    version: str
    execution_mode: str  # "sync" | "async"
    risk_class: str  # "low" | "medium" | "high"
    input_schema_ref: str = ""
    output_schema_ref: str = ""
    timeout_seconds: int | None = None
    retry_semantics: str = ""
    idempotency_semantics: str = ""
    evidence_schema_ref: str = ""
    cleanup_capability: bool = False
    healthcheck_capability: bool = False


@dataclass(frozen=True)
class CapabilityRegistration:
    contract: CapabilityContract
    adapter_factory: Callable[[], object]


class CapabilityRegistrationError(RuntimeError):
    """A capability's factory did not produce what its own contract promised."""


def _moneyprinterturbo_adapter():
    from core.moneyprinterturbo_adapter import MoneyPrinterTurboAdapter
    return MoneyPrinterTurboAdapter()


def _crawl4ai_adapter():
    from core.crawl4ai_adapter import Crawl4AIAdapter
    return Crawl4AIAdapter()


def _stirling_pdf_adapter():
    from core.stirling_pdf_adapter import StirlingPDFAdapter
    return StirlingPDFAdapter()


def _build_registry(registrations: list[CapabilityRegistration]) -> dict[str, CapabilityRegistration]:
    registry: dict[str, CapabilityRegistration] = {}
    for registration in registrations:
        capability_id = registration.contract.capability_id
        if capability_id in registry:
            raise CapabilityRegistrationError(f"duplicate capability_id registration: {capability_id!r}")
        registry[capability_id] = registration
    return registry


# The single source of truth: one registration per capability, key derived
# from the contract itself (never typed a second time), so a contract and
# its adapter factory can never drift apart or fall out of sync.
_REGISTRY: dict[str, CapabilityRegistration] = _build_registry([
    CapabilityRegistration(
        contract=CapabilityContract(
            capability_id="moneyprinterturbo",
            adapter_name="moneyprinterturbo",
            version="1.3.3",
            execution_mode="async",
            risk_class="high",
            timeout_seconds=1800,
            retry_semantics="no automatic resubmit; failed/outcome_unknown are terminal for the caller",
            idempotency_semantics="contract_id is the durable idempotency key; a submitted/completed job short-circuits resubmission",
            evidence_schema_ref="core.moneyprinterturbo_adapter",
            cleanup_capability=True,
            healthcheck_capability=False,
        ),
        adapter_factory=_moneyprinterturbo_adapter,
    ),
    CapabilityRegistration(
        contract=CapabilityContract(
            capability_id="crawl4ai",
            adapter_name="crawl4ai",
            version="0.9.2",
            execution_mode="sync",
            risk_class="medium",
            timeout_seconds=30,
            retry_semantics="no automatic resubmit; failed/outcome_unknown are terminal for the caller",
            idempotency_semantics="contract_id is the durable idempotency key; a submitted/completed job short-circuits resubmission",
            evidence_schema_ref="core.crawl4ai_adapter",
            cleanup_capability=False,
            healthcheck_capability=False,
        ),
        adapter_factory=_crawl4ai_adapter,
    ),
    CapabilityRegistration(
        contract=CapabilityContract(
            capability_id="stirling_pdf",
            adapter_name="stirling_pdf",
            version="2.14.3",
            execution_mode="sync",
            risk_class="high",
            timeout_seconds=60,
            retry_semantics="no automatic resubmit; failed/outcome_unknown are terminal for the caller",
            idempotency_semantics="contract_id is the durable idempotency key; a submitted/completed job short-circuits resubmission",
            evidence_schema_ref="core.stirling_pdf_adapter",
            cleanup_capability=False,
            healthcheck_capability=True,
        ),
        adapter_factory=_stirling_pdf_adapter,
    ),
])


def resolve_adapter(capability_id: str):
    """Explicit, fail-closed capability_id -> adapter instance.

    Unknown id -> None. A known id whose factory returns something that
    doesn't match its own contract (wrong adapter.name, or missing
    submit()/poll()) raises CapabilityRegistrationError rather than handing
    back a silently broken adapter — a misconfigured registration must never
    look like "not configured".
    """
    registration = _REGISTRY.get(capability_id)
    if registration is None:
        return None
    adapter = registration.adapter_factory()
    contract = registration.contract
    if getattr(adapter, "name", None) != contract.adapter_name:
        raise CapabilityRegistrationError(
            f"capability {capability_id!r}: factory returned adapter.name="
            f"{getattr(adapter, 'name', None)!r}, contract declares adapter_name={contract.adapter_name!r}"
        )
    if not callable(getattr(adapter, "submit", None)) or not callable(getattr(adapter, "poll", None)):
        raise CapabilityRegistrationError(
            f"capability {capability_id!r}: factory returned an adapter missing submit()/poll()"
        )
    return adapter


def get_contract(capability_id: str) -> CapabilityContract | None:
    registration = _REGISTRY.get(capability_id)
    return registration.contract if registration else None
