# core/adapters/decision_adapter.py — Decision Hub Adapter
#
# Maps between Decision Hub's Airtable records and the Core Reasoning Layer.
# This is the ONLY place that knows about Decision-specific field names,
# status vocabulary, and output format (Telegram card block).
#
# What this Adapter owns:
#   - Field mapping (DecisionFields → ReasoningEntity)
#   - Domain rules (confidence thresholds for Decision domain)
#   - Output rendering (ReasoningResult → Telegram Markdown block)
#   - Stakeholder extraction
#
# What this Adapter does NOT own:
#   - Trust computation
#   - Confidence scoring
#   - Attention priority
#   - Orchestrator phase routing
#
# Integration point: call append_reasoning_block() from
#   cmd_decision._format_decision_card() to append Stage 6 output.
#   This replaces the current append_orchestrator_to_card() call once
#   Core is stable — both can coexist during the transition.

from __future__ import annotations

import logging

from core.reasoning_entity import (
    ENTITY_DECISION,
    PHASE_DECIDED,
    PHASE_CLOSED,
    PRIORITY_HIGH,
    ReasoningAdapter,
    ReasoningEntity,
    ReasoningResult,
)

logger = logging.getLogger(__name__)

# Decision-specific confidence thresholds (same as decision_orchestrator.py).
# Centralised here so the Adapter owns the business rule.
CONFIDENCE_READY_THRESHOLD  = 0.60
CONFIDENCE_DECIDE_THRESHOLD = 0.75


class DecisionAdapter(ReasoningAdapter):
    """
    Adapter for Decision Hub entities.

    Usage
    -----
    adapter = DecisionAdapter()
    entity  = adapter.to_entity(decision_record, events=events, stakeholders=stakeholders)
    result  = reasoning_engines.run(entity)
    block   = adapter.from_result(result)
    """

    entity_type = ENTITY_DECISION

    # ── to_entity ─────────────────────────────────────────────────────────────

    def to_entity(
        self,
        record: dict,
        events: list[dict] | None = None,
        stakeholders: list[dict] | None = None,
        **kwargs,
    ) -> ReasoningEntity:
        """
        Map one Decision Airtable record to ReasoningEntity.

        record       — {"id": "rec...", "fields": {...}}
        events       — list of Decision Event records for this decision
        stakeholders — list of Decision Stakeholder records
        """
        from airtable_schema import (
            DecisionFields as DF,
            DecisionStakeholderFields as SF,
            DecisionStakeholderRole,
        )

        fields       = record.get("fields", record)
        events       = events or []
        stakeholders = stakeholders or []

        # Owner: first stakeholder with Role=Owner
        owner = None
        for s in stakeholders:
            sf = s.get("fields", s)
            if sf.get(SF.ROLE) == DecisionStakeholderRole.OWNER:
                contact = sf.get(SF.CONTACT)
                if isinstance(contact, list) and contact:
                    owner = str(contact[0])
                else:
                    owner = sf.get(SF.POSITION_DETAILS)
                break

        # Most recent raw input: prefer last event's raw content
        raw_input = ""
        if events:
            last = events[-1].get("fields", events[-1])
            raw_input = (
                last.get("Raw Content")
                or last.get("raw_content")
                or last.get("AI Summary")
                or ""
            )
        if not raw_input:
            raw_input = fields.get(DF.DESCRIPTION, "") or fields.get(DF.TITLE, "")

        return ReasoningEntity(
            entity_type = ENTITY_DECISION,
            entity_id   = record.get("id", ""),
            domain      = fields.get(DF.DOMAIN, "general"),
            status      = fields.get(DF.STATUS, ""),
            raw_input   = raw_input,
            events      = events,
            evidence    = [],   # Decision evidence is embedded in events
            owner       = owner,
            metadata    = {
                "title":              fields.get(DF.TITLE, ""),
                "readiness":          fields.get(DF.READINESS, ""),
                "last_updated":       fields.get(DF.LAST_UPDATED, ""),
                "created":            fields.get(DF.CREATED, ""),
                "deadline":           fields.get(DF.DEADLINE, ""),
                "missing_info":       fields.get(DF.MISSING_INFO, ""),
                "source_reliability": fields.get("Source Reliability", "manual"),
                "channel":            fields.get("Channel", "manual"),
                "stakeholders":       stakeholders,
                "urgency":            fields.get(DF.URGENCY, ""),
                "estimated_exposure": fields.get(DF.ESTIMATED_EXPOSURE),
                # Pass orchestrator_fields so _run_orchestrator can enrich the
                # pseudo-record with Decision-specific display fields.
                "orchestrator_fields": {
                    "Urgency":             fields.get(DF.URGENCY, ""),
                    "Estimated Exposure":  fields.get(DF.ESTIMATED_EXPOSURE),
                },
            },
        )

    # ── from_result ───────────────────────────────────────────────────────────

    def from_result(self, result: ReasoningResult) -> str:
        """
        Render ReasoningResult as a Telegram Markdown block.
        Appended to the existing decision card by append_reasoning_block().
        """
        if result.phase in (PHASE_DECIDED, PHASE_CLOSED):
            return ""   # decided/closed cards don't need an orchestrator block

        lines = [
            "────────────────────",
            f"🔄 *מצב:* {result.phase}",
        ]

        if result.confidence_score > 0:
            bar = _confidence_bar(result.confidence_score)
            lines.append(f"📊 *Confidence:* {bar} {int(result.confidence_score * 100)}%")

        if result.attention_priority in (PRIORITY_HIGH, "MEDIUM"):
            lines.append(f"⚠️ *עדיפות:* {result.attention_priority}")

        if result.next_step:
            lines += [
                "",
                f"➡️ *צעד הבא:* {result.next_step.action}",
                f"👤 *אחראי:* {result.next_step.responsible}",
            ]
            if result.next_step.detail:
                lines.append(f"📎 {result.next_step.detail}")

        if result.blockers:
            lines.append("")
            lines.append("⛔ *חסמים:*")
            for b in result.blockers:
                lines.append(f"  • {b}")

        if result.missing_evidence:
            lines.append("")
            lines.append("📋 *ראיות חסרות:*")
            for m in result.missing_evidence:
                lines.append(f"  • {m}")

        if result.conflict_count:
            lines.append(f"⚡ *קונפליקטים:* {result.conflict_count}")

        if result.awaiting_owner:
            lines.append("")
            lines.append("⏳ _ממתין לאישור בעלים_")

        if result.after_resolution:
            lines.append("")
            lines.append(f"💡 _לאחר הפתרון: {result.after_resolution}_")

        if result.errors:
            logger.warning("[DecisionAdapter] engine errors: %s", result.errors)

        return "\n".join(lines)

    # ── domain_rules ──────────────────────────────────────────────────────────

    def domain_rules(self) -> dict:
        return {
            "confidence_ready_threshold":  CONFIDENCE_READY_THRESHOLD,
            "confidence_decide_threshold": CONFIDENCE_DECIDE_THRESHOLD,
            "inactive_days":               14,
            "deadline_soon_days":          7,
            "pressure_repeat_count":       4,
        }


# ── Integration helper ────────────────────────────────────────────────────────

def append_reasoning_block(
    decision: dict,
    events: list[dict],
    stakeholders: list[dict],
    precomputed_confidence=None,
) -> str:
    """
    Drop-in replacement for decision_orchestrator.append_orchestrator_to_card().
    Returns "" on failure so the card renders cleanly without the block.

    Migration path:
      Phase 1 (now): both this and append_orchestrator_to_card() can coexist.
      Phase 2 (after Core validated): remove append_orchestrator_to_card() call.
    """
    try:
        from core.reasoning_engines import run
        from core.reasoning_ports import build_default_ports

        adapter = DecisionAdapter()
        entity  = adapter.to_entity(decision, events=events, stakeholders=stakeholders)
        result  = run(entity, ports=build_default_ports(),
                      precomputed_confidence=precomputed_confidence,
                      require_feature_flag=False)
        block   = adapter.from_result(result)
        return ("\n" + block) if block else ""
    except Exception as e:
        logger.warning("[DecisionAdapter] append_reasoning_block failed: %s", e)
        return ""


# ── Private helpers ───────────────────────────────────────────────────────────

def _confidence_bar(score: float) -> str:
    filled = round(score * 10)
    return "█" * filled + "░" * (10 - filled)
