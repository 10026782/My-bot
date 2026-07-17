# core/adapters/leads_adapter.py — CRM / Leads Adapter
#
# Maps Lead Airtable records to ReasoningEntity and renders ReasoningResult
# as a Lead card block (Telegram Markdown).
#
# Lead-specific business rules:
#   - Trust: WhatsApp + unknown source defaults to T1
#   - Confidence: score-based when no documents exist (uses lead score/tier)
#   - Readiness: HOT + score>70 = READY for followup
#   - Attention: inactive >3 days (shorter than Decision default of 14)
#
# This Adapter does NOT touch Trust/Confidence/Attention computation —
# it configures domain_rules() so the engines apply the right thresholds.
#
# Integration point: call append_reasoning_block() from the lead card
# renderer (wherever lead status cards are built today).

from __future__ import annotations

import logging

from core.reasoning_entity import (
    ENTITY_LEAD,
    PHASE_AWAITING,
    PHASE_BLOCKED,
    PHASE_COLLECTING,
    PHASE_DECIDED,
    PRIORITY_HIGH,
    ReasoningAdapter,
    ReasoningEntity,
    ReasoningResult,
)

logger = logging.getLogger(__name__)

# Lead confidence thresholds — lower than Decision (leads are pre-qualification).
CONFIDENCE_READY_THRESHOLD  = 0.45   # HOT lead with some signal = followup-ready
CONFIDENCE_DECIDE_THRESHOLD = 0.65   # enough to qualify / disqualify

# Lead-specific attention window — shorter than Decision
INACTIVE_DAYS_LEAD = 3


class LeadsAdapter(ReasoningAdapter):
    """
    Adapter for Lead / CRM entities.

    Usage
    -----
    adapter = LeadsAdapter()
    entity  = adapter.to_entity(lead_record, events=lead_events)
    result  = reasoning_engines.run(entity)
    block   = adapter.from_result(result)
    """

    entity_type = ENTITY_LEAD

    # ── to_entity ─────────────────────────────────────────────────────────────

    def to_entity(
        self,
        record: dict,
        events: list[dict] | None = None,
        **kwargs,
    ) -> ReasoningEntity:
        """
        Map one Lead Airtable record to ReasoningEntity.

        record — {"id": "rec...", "fields": {...}}
        events — list of Lead Event / conversation records (optional)
        """
        fields = record.get("fields", record)
        events = events or []

        # Raw input: last message text or lead description
        raw_input = (
            fields.get("Last Message")
            or fields.get("Notes")
            or fields.get("Source Details")
            or fields.get("Name", "")
        )

        # Domain: map lead source/product to domain
        domain = _infer_domain(fields)

        # Status normalisation → standard vocabulary for engines. BUG-104
        # Phase 2A.1: Business Outcome (when terminal) takes precedence over
        # status — see docs/architecture/bug-104/PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md.
        raw_business_outcome = fields.get("Business Outcome", "")
        status = _normalise_status(fields.get("Status", ""), raw_business_outcome)

        # Owner: assigned agent
        owner = (
            fields.get("Assigned To")
            or fields.get("Agent")
            or None
        )

        # Lead score (0–100) → used to build a synthetic confidence hint
        lead_score = fields.get("Score") or fields.get("Lead Score") or 0
        try:
            lead_score = int(lead_score)
        except (ValueError, TypeError):
            lead_score = 0

        # Channel: WhatsApp is the primary inbound channel for leads
        channel = fields.get("Source Channel") or fields.get("Channel") or "whatsapp"

        return ReasoningEntity(
            entity_type = ENTITY_LEAD,
            entity_id   = record.get("id", ""),
            domain      = domain,
            status      = status,
            raw_input   = raw_input,
            events      = events,
            evidence    = [],
            owner       = owner,
            metadata    = {
                "title":              fields.get("Name", ""),
                "lead_score":         lead_score,
                "tier":               fields.get("Tier") or fields.get("Lead Tier") or "",
                "source":             fields.get("Source") or fields.get("Lead Source") or "",
                "channel":            channel,
                "source_reliability": _source_reliability(channel),
                "phone":              fields.get("Phone") or fields.get("WhatsApp") or "",
                "last_updated":       fields.get("Last Updated") or fields.get("Updated At") or "",
                "created":            fields.get("Created") or fields.get("Created At") or "",
                # BUG-104 Phase 2A.1 — raw + normalized Business Outcome, kept
                # as an honest signal for downstream policy/observability.
                # entity.status above already applies the terminal-override
                # precedence; these are not re-derived state.
                "business_outcome":            raw_business_outcome,
                "business_outcome_normalized": _normalise_business_outcome(raw_business_outcome),
                # Preserves the "high_confidence" operational signal even
                # though it maps to the same DecisionStatus.OPEN as other
                # active statuses (Phase 2A.1 §6).
                "status_high_signal": str(fields.get("Status", "")).strip().lower() == "high_confidence",
                # Attention engine reads this field name
                "attention_fields":   {
                    "Score": lead_score,
                    "Tier":  fields.get("Tier", ""),
                },
            },
        )

    # ── from_result ───────────────────────────────────────────────────────────

    def from_result(self, result: ReasoningResult) -> str:
        """
        Render ReasoningResult as a Telegram Markdown lead card block.
        """
        phase_emoji = {
            PHASE_COLLECTING: "🔍",
            PHASE_BLOCKED:    "⛔",
            PHASE_AWAITING:   "⏳",
            PHASE_DECIDED:    "✅",
        }.get(result.phase, "🔄")

        lines = [
            f"{phase_emoji} *{_phase_label(result.phase)}*",
        ]

        if result.confidence_score > 0:
            bar = _score_bar(result.confidence_score)
            lines.append(f"📊 {bar} {int(result.confidence_score * 100)}%")

        if result.attention_priority == PRIORITY_HIGH:
            lines.append("🔴 *דורש טיפול מיידי*")

        if result.next_step:
            lines += [
                "",
                f"➡️ {result.next_step.action}",
            ]
            if result.next_step.responsible:
                lines.append(f"👤 {result.next_step.responsible}")
            if result.next_step.detail:
                lines.append(f"   {result.next_step.detail}")

        if result.blockers:
            lines.append("")
            for b in result.blockers:
                lines.append(f"⚠️ {b}")

        if result.errors:
            logger.warning("[LeadsAdapter] engine errors: %s", result.errors)

        return "\n".join(lines)

    # ── domain_rules ──────────────────────────────────────────────────────────

    def domain_rules(self) -> dict:
        return {
            "confidence_ready_threshold":  CONFIDENCE_READY_THRESHOLD,
            "confidence_decide_threshold": CONFIDENCE_DECIDE_THRESHOLD,
            "inactive_days":               INACTIVE_DAYS_LEAD,   # 3 days, not 14
            "deadline_soon_days":          2,
            "pressure_repeat_count":       2,
        }


# ── Integration helper ────────────────────────────────────────────────────────

def append_reasoning_block(
    lead_record: dict,
    events: list[dict] | None = None,
    precomputed_confidence=None,
) -> str:
    """
    Build and render a reasoning block for a Lead card.
    Returns "" on failure so the card renders cleanly.
    """
    try:
        from core.reasoning_engines import run
        from core.reasoning_ports import build_default_ports

        adapter = LeadsAdapter()
        entity  = adapter.to_entity(lead_record, events=events or [])
        result  = run(
            entity,
            ports=build_default_ports(),
            precomputed_confidence=precomputed_confidence,
            require_feature_flag=False,
        )
        block = adapter.from_result(result)
        return ("\n" + block) if block else ""
    except Exception as e:
        logger.warning("[LeadsAdapter] append_reasoning_block failed: %s", e)
        return ""


# ── Private helpers ───────────────────────────────────────────────────────────

def _infer_domain(fields: dict) -> str:
    """Infer domain from lead source / product fields."""
    source = str(
        fields.get("Source") or fields.get("Lead Source") or
        fields.get("Product") or fields.get("Domain") or ""
    ).lower()

    if any(k in source for k in ("נדל", "real_estate", "דירה", "קרקע")):
        return "real_estate"
    if any(k in source for k in ("יבוא", "import", "סחר")):
        return "import"
    if any(k in source for k in ("גיוס", "recruit", "משרה", "עובד")):
        return "recruitment"
    return "general"


# BUG-104 Phase 2A.1 — Business Outcome categories (Current State Policy).
# str(raw or "").strip().lower() normalized value -> category. Anything not
# listed (including empty/missing) is "unknown" — no terminal override.
# See docs/architecture/bug-104/PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md §4.
_OUTCOME_TERMINAL_POSITIVE       = {"converted"}
_OUTCOME_TERMINAL_NEGATIVE       = {"lost", "not_relevant"}
_OUTCOME_TERMINAL_ADMINISTRATIVE = {"duplicate", "archived"}
_OUTCOME_INTERMEDIATE            = {"open", "needs_followup", "meeting_scheduled", "ליד חדש"}


def _normalise_business_outcome(raw_business_outcome) -> str:
    """str(raw or '').strip().lower() — Phase 2A.1 §3, exact spec normalization."""
    return str(raw_business_outcome or "").strip().lower()


def _normalise_status(raw_status: str, raw_business_outcome: str = "") -> str:
    """
    Normalise Lead status (+ Business Outcome) to the literal vocabulary the
    shared Attention/Orchestrator engines actually compare against (BUG-104
    Phase 1.1 status-literal fix, extended by Phase 2A.1 Current State Policy).

    Attention's closed_statuses (decision_attention_policy.py) and
    Orchestrator's DECIDED_YES/DECIDED_NO/CANCELLED branches
    (decision_orchestrator.py) compare entity.status literally against
    DecisionStatus's own string values ("Open"/"Decided Yes"/"Decided No"/
    "Cancelled") — the same values decision_adapter.py passes through
    untouched for native Decision records (fields.get(DF.STATUS, "")).

    Phase 2A.1 precedence (PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md §7):
      A. A terminal Business Outcome (positive/negative/administrative)
         overrides status entirely.
      B. An intermediate Business Outcome does not close the lead.
      C. If Business Outcome is not terminal (intermediate/unknown/missing),
         status alone drives the operational DecisionStatus, below.
    """
    from airtable_schema import DecisionStatus

    normalized_outcome = _normalise_business_outcome(raw_business_outcome)
    if normalized_outcome in _OUTCOME_TERMINAL_POSITIVE:
        return DecisionStatus.DECIDED_YES
    if normalized_outcome in _OUTCOME_TERMINAL_NEGATIVE:
        return DecisionStatus.DECIDED_NO
    if normalized_outcome in _OUTCOME_TERMINAL_ADMINISTRATIVE:
        return DecisionStatus.CANCELLED

    # No terminal Business Outcome (intermediate/unknown/missing) — status
    # drives the operational bucket (Phase 2A.1 §6). Legacy free-text
    # synonyms predate Phase 2A.1 and are kept for backward compatibility;
    # the live Leads.status values are the ones actually written today.
    normalized_status = str(raw_status or "").strip().lower()
    status_map = {
        # legacy free-text synonyms (pre-Phase-2A.1)
        "new":       DecisionStatus.OPEN,
        "חדש":       DecisionStatus.OPEN,
        "hot":       DecisionStatus.OPEN,
        "חם":        DecisionStatus.OPEN,
        "warm":      DecisionStatus.OPEN,
        "פושר":      DecisionStatus.OPEN,
        "cold":      DecisionStatus.OPEN,
        "קר":        DecisionStatus.OPEN,
        "converted": DecisionStatus.DECIDED_YES,
        "הומר":      DecisionStatus.DECIDED_YES,
        "lost":      DecisionStatus.DECIDED_NO,
        "אבוד":      DecisionStatus.DECIDED_NO,
        "cancelled": DecisionStatus.CANCELLED,
        "בוטל":      DecisionStatus.CANCELLED,
        # live Leads.status values (Phase 2A.1 §6 — operational bucket)
        "ליד חדש":          DecisionStatus.OPEN,
        "active":           DecisionStatus.OPEN,
        "waiting_call":     DecisionStatus.OPEN,
        "waiting_response": DecisionStatus.OPEN,
        "high_confidence":  DecisionStatus.OPEN,
        "done":             DecisionStatus.DECIDED_YES,
        "not_relevant":     DecisionStatus.DECIDED_NO,
        "archived":         DecisionStatus.CANCELLED,
        "duplicate":        DecisionStatus.CANCELLED,
    }
    return status_map.get(normalized_status, DecisionStatus.OPEN)


def _source_reliability(channel: str) -> str:
    """Map inbound channel to source reliability constant."""
    channel = channel.lower()
    if "whatsapp" in channel:
        return "client"    # SRC.CLIENT — T1 by default
    if "email" in channel:
        return "client"
    if "manual" in channel or "form" in channel:
        return "manual"    # SRC.MANUAL
    return "unknown"       # SRC.UNKNOWN — T0/T1


def _phase_label(phase: str) -> str:
    return {
        PHASE_COLLECTING: "בתהליך איסוף",
        PHASE_BLOCKED:    "חסום",
        PHASE_AWAITING:   "ממתין לטיפול",
        PHASE_DECIDED:    "טופל",
        "CLOSED":         "סגור",
        "REVIEW":         "בבדיקה",
    }.get(phase, phase)


def _score_bar(score: float) -> str:
    filled = round(score * 10)
    return "█" * filled + "░" * (10 - filled)
