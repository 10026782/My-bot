"""External Capability Contract v1.

Small, stable metadata contract describing an external capability (adapter)
to the generic ExternalExecutionBoundary, plus an explicit, fail-closed
capability_id -> adapter registry.

Design invariants (see docs/architecture/EXTERNAL_CAPABILITY_CONTRACT_V1.md):
- Explicit, code-reviewed registry only. No dynamic imports of user-supplied
  names, no plugin auto-discovery, no arbitrary module loading.
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


def _moneyprinterturbo_adapter():
    from core.moneyprinterturbo_adapter import MoneyPrinterTurboAdapter
    return MoneyPrinterTurboAdapter()


_ADAPTER_FACTORIES: dict[str, Callable[[], object]] = {
    "moneyprinterturbo": _moneyprinterturbo_adapter,
}

CAPABILITY_CONTRACTS: dict[str, CapabilityContract] = {
    "moneyprinterturbo": CapabilityContract(
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
}


def resolve_adapter(capability_id: str):
    """Explicit, fail-closed capability_id -> adapter instance. Unknown id -> None."""
    factory = _ADAPTER_FACTORIES.get(capability_id)
    return factory() if factory else None


def get_contract(capability_id: str) -> CapabilityContract | None:
    return CAPABILITY_CONTRACTS.get(capability_id)
