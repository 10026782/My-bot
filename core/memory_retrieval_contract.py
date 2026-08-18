"""MemoryRetrievalRequest / MemorySnapshot — the Phase 2 retrieval contract.

Read-only, shadow-only (see core/memory_retrieval.py's module docstring).
Shapes a filtered, budgeted snapshot over the existing Business Memory
(Airtable) and Episodic Memory (Postgres, Phase 1) sources — it queries
them, it is not a third source of truth for anything they already own.
Not wired into context.py, memory_store.py, or any live turn path.

See docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md, sections
D (retrieval pipeline), E (budget), F (provenance).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.episodic_entry import EpisodicEntry

# Matches cmd_update.get_recent_business_context()'s existing default (limit=5).
DEFAULT_BUSINESS_MEMORY_BUDGET = 5
DEFAULT_EPISODIC_MEMORY_BUDGET = 20


class MemoryRetrievalValidationError(ValueError):
    """Raised when a MemoryRetrievalRequest violates its contract."""


@dataclass(frozen=True)
class MemoryRetrievalRequest:
    tenant_id: str
    canonical_user_id: str

    session_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    domain_id: str | None = None

    now: float = field(default_factory=time.time)

    business_memory_budget: int = DEFAULT_BUSINESS_MEMORY_BUDGET
    episodic_memory_budget: int = DEFAULT_EPISODIC_MEMORY_BUDGET

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise MemoryRetrievalValidationError("tenant_id is required")
        if not isinstance(self.canonical_user_id, str) or not self.canonical_user_id.strip():
            raise MemoryRetrievalValidationError("canonical_user_id is required")
        if self.business_memory_budget < 0 or self.episodic_memory_budget < 0:
            raise MemoryRetrievalValidationError("budgets must be non-negative")


@dataclass(frozen=True)
class BusinessMemoryItem:
    """One Business Memory record, structured — never flattened to a text blob."""

    record_id: str
    title: str
    description: str
    event_type: str | None
    domain: str | None
    occurred_at: float | None  # parsed from the Event Date field; None if unparsable
    source: str = "business_memory"


@dataclass(frozen=True)
class SnapshotMetadata:
    generated_at: float
    tenant_id: str
    canonical_user_id: str
    session_id: str | None
    entity_type: str | None
    entity_id: str | None
    domain_id: str | None

    business_memory_available: bool
    business_memory_error: str | None
    business_memory_returned: int
    business_memory_budget: int

    episodic_memory_available: bool
    episodic_memory_error: str | None
    episodic_memory_returned: int
    episodic_memory_budget: int


@dataclass(frozen=True)
class MemorySnapshot:
    business_facts: tuple[BusinessMemoryItem, ...]
    episodic_entries: tuple[EpisodicEntry, ...]
    metadata: SnapshotMetadata
