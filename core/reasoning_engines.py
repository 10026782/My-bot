# core/reasoning_engines.py — Core Reasoning Layer: Engine Runner
#
# Single entry point: run(entity, ports, domain_rules) → ReasoningResult
#
# This module wires Stages 1–6 in order. It does NOT re-implement any engine —
# it delegates to the existing modules (decision_pipeline, decision_confidence,
# decision_attention, decision_orchestrator) via thin adaptor calls.
#
# Engines are called in this order:
#   1. Trust      — per-event reliability (decision_pipeline.gate_trust)
#   2. Confidence — cross-event score    (decision_confidence.calc_confidence)
#   3. Readiness  — domain readiness     (adapter.domain_rules or stub)
#   4. Attention  — priority signals     (decision_attention.calc_priority)
#   5. Ingestion  — (passive; called externally on ingest, not here)
#   6. Orchestrator — next step          (decision_orchestrator.orchestrate)
#
# Stage 5 (Ingestion) is NOT called from run() because it is triggered by
# incoming messages, not by status queries. Adapters call ingest_message()
# directly when routing new input.
#
# Read/write boundary:
#   - run() reads entity data passed in by caller
#   - Storage writes (Supersede) happen inside gate_trust via ports.storage
#   - run() itself never writes to Airtable
#   - ReasoningResult is a plain dataclass — no side effects on return

from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.reasoning_entity import (
    PHASE_COLLECTING,
    PRIORITY_NONE,
    TRUST_T2,
    NextStep,
    ReasoningEntity,
    ReasoningResult,
)
from core.reasoning_ports import ReasoningPorts, build_default_ports

logger = logging.getLogger(__name__)

FEATURE_FLAG = "FEATURE_DECISION_HUB"   # gates the whole Core layer for now


# ── Public API ────────────────────────────────────────────────────────────────

def run(
    entity: ReasoningEntity,
    ports: ReasoningPorts | None = None,
    precomputed_confidence=None,   # ConfidenceResult | None  (from Stage 2)
    require_feature_flag: bool = True,
) -> ReasoningResult:
    """
    Run all applicable reasoning engines for one entity.

    entity                 — built by the Adapter from domain records
    ports                  — dependency injection; defaults to production ports
    precomputed_confidence — pass a ConfidenceResult from Stage 2 when the
                             caller already ran AI conflict detection, so Stage
                             6 uses conflict-aware confidence. None = deterministic
                             only (no new AI calls).
    require_feature_flag   — set False in tests / when caller manages own gate
    """
    if require_feature_flag and not _feature_enabled():
        return _disabled_result(entity)

    ports = ports or build_default_ports()
    errors: list[str] = []

    # ── Stage 1: Trust ────────────────────────────────────────────────────────
    trust_level = _run_trust(entity, ports, errors)

    # ── Stage 2: Confidence ───────────────────────────────────────────────────
    confidence_score, missing_evidence, conflict_count = _run_confidence(
        entity, precomputed_confidence, errors
    )

    # ── Stage 3: Readiness ────────────────────────────────────────────────────
    # Stub — domain_rules() from the Adapter drives readiness classification.
    # Full engine implementation deferred (gate_readiness stub in pipeline).
    readiness = entity.metadata.get("readiness", "")

    # ── Stage 4: Attention ────────────────────────────────────────────────────
    attention_priority, attention_reasons = _run_attention(entity, errors)

    # ── Stage 6: Orchestrator ─────────────────────────────────────────────────
    phase, next_step, blockers, awaiting_owner, after_resolution = _run_orchestrator(
        entity,
        confidence_score,
        missing_evidence,
        readiness,
        precomputed_confidence,
        errors,
    )

    return ReasoningResult(
        entity_type        = entity.entity_type,
        entity_id          = entity.entity_id,
        phase              = phase,
        trust_level        = trust_level,
        confidence_score   = confidence_score,
        attention_priority = attention_priority,
        attention_reasons  = attention_reasons,
        missing_evidence   = missing_evidence,
        next_step          = next_step,
        blockers           = blockers,
        awaiting_owner     = awaiting_owner,
        after_resolution   = after_resolution,
        conflict_count     = conflict_count,
        errors             = errors,
    )


# ── Stage 1: Trust ────────────────────────────────────────────────────────────

def _run_trust(entity: ReasoningEntity, ports: ReasoningPorts, errors: list[str]) -> str:
    """
    Compute trust for the most recent event (or raw_input if no events).
    Returns TrustLevel string (T0–T3).
    Full per-event pipeline runs via gate_trust for Decision entities;
    for other entity types we use compute_trust directly.
    """
    try:
        from decision_pipeline import compute_trust, SRC, CH

        source_reliability = entity.metadata.get("source_reliability", SRC.MANUAL)
        channel            = entity.metadata.get("channel", CH.MANUAL)

        verify_result = ports.verifier.verify(entity.raw_input, source_reliability)
        verify_status = verify_result.get("status", "ok")

        level, _ = compute_trust(source_reliability, channel, verify_status)
        return level
    except Exception as e:
        errors.append(f"trust_engine: {e}")
        return TRUST_T2   # safe default — neither blocks nor blindly trusts


# ── Stage 2: Confidence ───────────────────────────────────────────────────────

def _run_confidence(
    entity: ReasoningEntity,
    precomputed_confidence,
    errors: list[str],
) -> tuple[float, list[str], int]:
    """Returns (score, missing_evidence, conflict_count)."""
    try:
        from decision_confidence import calc_confidence

        if precomputed_confidence is not None:
            result = precomputed_confidence
        else:
            result = calc_confidence(
                entity.events,
                conflicts=[],          # no AI calls from run()
                domain=entity.domain,
            )

        conflict_count = len(result.conflicting) if result.conflicting else 0
        return result.score, result.missing, conflict_count

    except Exception as e:
        errors.append(f"confidence_engine: {e}")
        return 0.0, [], 0


# ── Stage 4: Attention ────────────────────────────────────────────────────────

def _run_attention(
    entity: ReasoningEntity,
    errors: list[str],
) -> tuple[str, list[str]]:
    """Returns (priority, reasons)."""
    try:
        from decision_attention import calc_priority

        # Build a minimal decision-shaped record so calc_priority can read it.
        # Attention engine only reads fields it knows — unknown fields are ignored.
        pseudo_record = {
            "id": entity.entity_id,
            "fields": {
                "Status":       entity.status,
                "Readiness":    entity.metadata.get("readiness", ""),
                "Last Updated": entity.metadata.get("last_updated", ""),
                "Created":      entity.metadata.get("created", ""),
                "Deadline":     entity.metadata.get("deadline", ""),
                "Missing Info": entity.metadata.get("missing_info", ""),
                **entity.metadata.get("attention_fields", {}),
            },
        }

        item = calc_priority(
            pseudo_record,
            entity.events,
            now=datetime.now(timezone.utc),
            require_feature_flag=False,
        )
        return item.priority, list(item.reasons)

    except Exception as e:
        errors.append(f"attention_engine: {e}")
        return PRIORITY_NONE, []


# ── Stage 6: Orchestrator ─────────────────────────────────────────────────────

def _run_orchestrator(
    entity: ReasoningEntity,
    confidence_score: float,
    missing_evidence: list[str],
    readiness: str,
    precomputed_confidence,
    errors: list[str],
) -> tuple[str, NextStep | None, list[str], bool, str]:
    """Returns (phase, next_step, blockers, awaiting_owner, after_resolution)."""
    try:
        from decision_orchestrator import orchestrate

        # Build a minimal decision-shaped record for the orchestrator.
        pseudo_record = {
            "id": entity.entity_id,
            "fields": {
                "Title":     entity.metadata.get("title", entity.entity_id),
                "Status":    entity.status,
                "Readiness": readiness,
                "Domain":    entity.domain,
                **entity.metadata.get("orchestrator_fields", {}),
            },
        }

        stakeholders = entity.metadata.get("stakeholders", [])

        orch = orchestrate(
            pseudo_record,
            entity.events,
            stakeholders,
            precomputed_confidence=precomputed_confidence,
            require_feature_flag=False,
        )

        next_step = NextStep(
            action      = orch.next_step.action,
            responsible = orch.next_step.responsible,
            detail      = orch.next_step.detail,
        ) if orch.next_step else None

        return (
            orch.phase,
            next_step,
            orch.blockers,
            orch.awaiting_owner,
            orch.after_resolution,
        )

    except Exception as e:
        errors.append(f"orchestrator_engine: {e}")
        return PHASE_COLLECTING, None, [], False, ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _feature_enabled() -> bool:
    try:
        from feature_flags import is_enabled
        return bool(is_enabled(FEATURE_FLAG))
    except Exception:
        return False


def _disabled_result(entity: ReasoningEntity) -> ReasoningResult:
    return ReasoningResult(
        entity_type        = entity.entity_type,
        entity_id          = entity.entity_id,
        phase              = PHASE_COLLECTING,
        trust_level        = TRUST_T2,
        confidence_score   = 0.0,
        attention_priority = PRIORITY_NONE,
        next_step          = NextStep("הפעל FEATURE_DECISION_HUB", "system"),
        errors             = ["feature_flag_off"],
    )
