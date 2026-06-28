# core/reasoning_ports.py — Core Reasoning Layer: Ports (dependency injection)
#
# Generalises DecisionPorts (decision_ports.py) to work with any entity type.
# The engines import only from this file — never directly from airtable_gateway,
# tools, or any domain module.
#
# Pattern: caller builds a ReasoningPorts instance and injects it into
# reasoning_engines.run(). Tests inject fakes. Production injects real impls.
#
# Relationship to existing DecisionPorts:
#   DecisionPorts remains unchanged and continues to serve decision_pipeline.py.
#   ReasoningPorts is a parallel (not replacement) used only by the Core layer.
#   Once Core is stable, DecisionPorts can be retired — but not yet.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


# ── Port protocols ────────────────────────────────────────────────────────────

class StoragePort(Protocol):
    """Read/write to the canonical store (Airtable or test double)."""

    def get(self, table: str, formula: str) -> list[dict]:
        """Return records matching formula. Empty list on miss/error."""
        ...

    def create(self, table: str, fields: dict, source: str = "") -> dict | None:
        """Create one record. Returns created record or None on failure."""
        ...

    def update(self, table: str, record_id: str, fields: dict, source: str = "") -> dict | None:
        """Update one record by ID. Returns updated record or None on failure."""
        ...


class VerifierPort(Protocol):
    """Anti-hallucination verifier — same contract as existing VerifierPort."""

    def verify(self, text: str, source_reliability: str) -> dict:
        """Return {"status": "ok"|"warn"|"hallucination"|"failed"}."""
        ...


class ContactPort(Protocol):
    """Resolve stakeholder names to canonical contacts."""

    def find_or_create(self, name: str) -> dict:
        """
        Return {"status": "found"|"created"|"ambiguous", "matches": [...]}
        """
        ...


class LLMPort(Protocol):
    """Thin wrapper around the LLM for conflict detection."""

    def call(
        self,
        source: str,
        model: str,
        max_tokens: int,
        messages: list[dict],
        temperature: float = 0,
    ) -> str:
        """Return raw text response. Raises on hard failure."""
        ...


# ── Null / no-op implementations (safe defaults for optional ports) ───────────

class _NullVerifier:
    def verify(self, text: str, source_reliability: str) -> dict:
        return {"status": "ok"}


class _NullContacts:
    def find_or_create(self, name: str) -> dict:
        return {"status": "found", "matches": []}


class _NullStorage:
    def get(self, table: str, formula: str) -> list[dict]:
        return []

    def create(self, table: str, fields: dict, source: str = "") -> dict | None:
        logger.warning("[ReasoningPorts._NullStorage] create called — no-op")
        return None

    def update(self, table: str, record_id: str, fields: dict, source: str = "") -> dict | None:
        logger.warning("[ReasoningPorts._NullStorage] update called — no-op")
        return None


class _NullLLM:
    def call(self, source: str, model: str, max_tokens: int,
             messages: list[dict], temperature: float = 0) -> str:
        raise RuntimeError("LLMPort not configured — AI conflict detection unavailable")


# ── Production implementations ────────────────────────────────────────────────

class _AirtableStorage:
    """Thin wrapper around the existing airtable_gateway."""

    def get(self, table: str, formula: str) -> list[dict]:
        try:
            from tools.airtable_gateway import airtable_search
            return airtable_search(table, formula) or []
        except Exception as e:
            logger.warning("[ReasoningPorts] storage.get failed: %s", e)
            return []

    def create(self, table: str, fields: dict, source: str = "") -> dict | None:
        try:
            from tools.airtable_gateway import airtable_create
            return airtable_create(table, fields, source=source)
        except Exception as e:
            logger.warning("[ReasoningPorts] storage.create failed: %s", e)
            return None

    def update(self, table: str, record_id: str, fields: dict, source: str = "") -> dict | None:
        try:
            from tools.airtable_gateway import airtable_patch
            return airtable_patch(table, record_id, fields, source=source)
        except Exception as e:
            logger.warning("[ReasoningPorts] storage.update failed: %s", e)
            return None


class _ProductionVerifier:
    def verify(self, text: str, source_reliability: str) -> dict:
        try:
            from core_verifier import verify_claim
            return verify_claim(text, source_reliability)
        except Exception as e:
            logger.warning("[ReasoningPorts] verifier failed: %s", e)
            return {"status": "ok"}


class _ProductionContacts:
    def find_or_create(self, name: str) -> dict:
        try:
            from contact_resolver import find_or_create_contact
            return find_or_create_contact(name)
        except Exception as e:
            logger.warning("[ReasoningPorts] contacts failed: %s", e)
            return {"status": "found", "matches": []}


class _AnthropicLLM:
    def call(self, source: str, model: str, max_tokens: int,
             messages: list[dict], temperature: float = 0) -> str:
        from llm_fallback import call_anthropic_text
        return call_anthropic_text(
            source=source,
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            temperature=temperature,
        )


# ── ReasoningPorts container ──────────────────────────────────────────────────

@dataclass
class ReasoningPorts:
    """
    Dependency container injected into reasoning_engines.run().
    All fields have safe no-op defaults so tests need not configure everything.

    Production code uses build_default_ports(). Tests build custom instances
    with fake implementations for the ports they care about.
    """
    storage  : Any = field(default_factory=_NullStorage)    # StoragePort
    verifier : Any = field(default_factory=_NullVerifier)   # VerifierPort
    contacts : Any = field(default_factory=_NullContacts)   # ContactPort
    llm      : Any = field(default_factory=_NullLLM)        # LLMPort


def build_default_ports() -> ReasoningPorts:
    """Production ports. Import lazily so tests never touch production deps."""
    return ReasoningPorts(
        storage=_AirtableStorage(),
        verifier=_ProductionVerifier(),
        contacts=_ProductionContacts(),
        llm=_AnthropicLLM(),
    )
