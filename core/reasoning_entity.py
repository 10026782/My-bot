# core/reasoning_entity.py — Core Reasoning Layer: Entity Contract
#
# Pure dataclasses. Zero logic. Zero imports from the rest of the system.
# This is the only interface the Core Reasoning Layer knows about.
#
# Read/write boundary: none — this file defines data shapes only.
#
# Usage:
#   Every Adapter constructs a ReasoningEntity from its domain data and
#   passes it to reasoning_engines.run(). It receives back a ReasoningResult
#   and translates it to its own output format.
#
# Adding a new entity type:
#   1. Add entity_type string constant below (ENTITY_*)
#   2. Implement an Adapter in core/adapters/<name>_adapter.py
#   3. No changes to this file or to the engines.

from __future__ import annotations

from dataclasses import dataclass, field

# ── Entity type constants ─────────────────────────────────────────────────────

ENTITY_DECISION   = "decision"
ENTITY_LEAD       = "lead"
ENTITY_PROJECT    = "project"
ENTITY_CONTRACT   = "contract"
ENTITY_CANDIDATE  = "candidate"
ENTITY_FINANCE    = "financial_commitment"
ENTITY_BUSINESS   = "business_update"

# ── Phase constants (Orchestrator output) ────────────────────────────────────

PHASE_COLLECTING = "COLLECTING"
PHASE_BLOCKED    = "BLOCKED"
PHASE_REVIEW     = "REVIEW"
PHASE_AWAITING   = "AWAITING"
PHASE_DECIDED    = "DECIDED"
PHASE_CLOSED     = "CLOSED"

# ── Priority constants (Attention output) ────────────────────────────────────

PRIORITY_HIGH   = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW    = "LOW"
PRIORITY_NONE   = "NONE"

# ── Trust level constants ─────────────────────────────────────────────────────

TRUST_T0 = "T0"
TRUST_T1 = "T1"
TRUST_T2 = "T2"
TRUST_T3 = "T3"


# ── Input contract ────────────────────────────────────────────────────────────

@dataclass
class ReasoningEntity:
    """
    Unified input contract for all Core Reasoning engines.
    Constructed by an Adapter from domain-specific Airtable records.

    Fields
    ------
    entity_type : str
        One of the ENTITY_* constants. Used by engines for domain-aware
        defaults (e.g. confidence thresholds per entity type).
    entity_id : str
        Unique identifier — Airtable record ID or equivalent.
    domain : str
        Business domain (e.g. "real_estate", "import", "recruitment",
        "general"). Drives REQUIRED_EVIDENCE lookup and Readiness rules.
    status : str
        Current lifecycle status in the Adapter's terms. Each Adapter maps
        its own status vocabulary into ReasoningResult.phase.
    owner : str | None
        Owner identifier (Airtable contact ID or display name). Used by
        Orchestrator for next_step.responsible.
    raw_input : str
        Most recent raw text input for this entity. Used by Trust engine
        and Ingestion engine.
    events : list[dict]
        Domain event records (Decision Events, Lead Events, …). Each dict
        is an Airtable record with {"id": ..., "fields": {...}}.
    evidence : list[dict]
        Attached evidence records (files, documents, approvals). Same
        Airtable record shape as events.
    metadata : dict
        Adapter-specific extras (source_reliability, channel, tenant_id,
        attachment_url, …). Engines access via metadata.get(key).
    """
    entity_type : str
    entity_id   : str
    domain      : str
    status      : str
    raw_input   : str
    events      : list[dict]          = field(default_factory=list)
    evidence    : list[dict]          = field(default_factory=list)
    owner       : str | None          = None
    metadata    : dict                = field(default_factory=dict)


# ── Next step ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NextStep:
    """One actionable step — what to do, who does it, optional detail."""
    action      : str
    responsible : str
    detail      : str = ""


# ── Output contract ───────────────────────────────────────────────────────────

@dataclass
class ReasoningResult:
    """
    Unified output from Core Reasoning engines.
    Returned to the Adapter, which translates it to its own output format
    (Telegram card, API response, digest line, …).

    The Adapter is responsible for display. The Core is responsible for
    computing these values. Never mix the two.
    """
    entity_type        : str
    entity_id          : str
    phase              : str                   # PHASE_* constant
    trust_level        : str                   # TRUST_T* constant
    confidence_score   : float                 # 0.0–1.0
    attention_priority : str                   # PRIORITY_* constant
    attention_reasons  : list[str]             = field(default_factory=list)
    missing_evidence   : list[str]             = field(default_factory=list)
    next_step          : NextStep | None       = None
    blockers           : list[str]             = field(default_factory=list)
    awaiting_owner     : bool                  = False
    after_resolution   : str                   = ""
    conflict_count     : int                   = 0    # from Confidence engine
    errors             : list[str]             = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "entity_type":        self.entity_type,
            "entity_id":          self.entity_id,
            "phase":              self.phase,
            "trust_level":        self.trust_level,
            "confidence_score":   self.confidence_score,
            "attention_priority": self.attention_priority,
            "attention_reasons":  self.attention_reasons,
            "missing_evidence":   self.missing_evidence,
            "next_step": {
                "action":      self.next_step.action,
                "responsible": self.next_step.responsible,
                "detail":      self.next_step.detail,
            } if self.next_step else None,
            "blockers":         self.blockers,
            "awaiting_owner":   self.awaiting_owner,
            "after_resolution": self.after_resolution,
            "conflict_count":   self.conflict_count,
            "errors":           self.errors,
        }


# ── Adapter interface (protocol) ──────────────────────────────────────────────

class ReasoningAdapter:
    """
    Base class for all domain Adapters. Adapters subclass this and implement
    the three methods below. The engines call nothing on this class directly —
    it exists for documentation and isinstance() checks.

    Adapter responsibilities:
      1. to_entity()    — map domain records → ReasoningEntity
      2. from_result()  — map ReasoningResult → domain output (str / dict)
      3. domain_rules() — return domain-specific config overrides

    Adapter non-responsibilities (handled by engines):
      - Trust computation
      - Confidence scoring
      - Attention priority
      - Orchestrator phase routing
    """

    entity_type: str = ""   # must be set by subclass

    def to_entity(self, record: dict, **kwargs) -> ReasoningEntity:
        """Map a domain record to ReasoningEntity. Implemented by subclass."""
        raise NotImplementedError

    def from_result(self, result: ReasoningResult) -> str:
        """Render ReasoningResult as domain output. Implemented by subclass."""
        raise NotImplementedError

    def domain_rules(self) -> dict:
        """
        Return domain config overrides for the engines. Keys recognised:
          confidence_ready_threshold  : float  (default 0.60)
          confidence_decide_threshold : float  (default 0.75)
          inactive_days               : int    (default 14)
          deadline_soon_days          : int    (default 7)
          pressure_repeat_count       : int    (default 4)
        """
        return {}
