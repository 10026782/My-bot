# core/leads_reasoning_projection.py
# BUG-104 — Core Reasoning Activation Program
# Phase 1 — Leads Read-Only Reasoning Projection
#
# Pure, read-only projection builder. Given a Lead snapshot that the CALLER
# already loaded (never loaded here), an already-loaded Lead-Events list, and a
# deterministic as_of timestamp, it drives the existing Core Reasoning Layer
# (F22 — core/reasoning_engines.run via core/adapters/leads_adapter.LeadsAdapter)
# and maps the ReasoningResult to a typed, JSON-serializable projection.
#
# Hard boundaries (Phase 1):
#   - READ-ONLY. No mutation, no persistence, no Airtable/repository writes.
#   - This module performs ZERO data reads. The endpoint owns all reads and
#     hands us a full snapshot (lead_record) + events. The adapter and the
#     reasoning engines run with all-null ports (ReasoningPorts()), so no
#     engine can touch Airtable or the network either.
#   - No Decision Hub, no ActionGateway, no chat/Agent, no Telegram/WhatsApp.
#   - Deterministic: same (lead_record, events, as_of) → same projection. The
#     single as_of is threaded into the reasoning engine (Attention), so no
#     internal now() can drift the result. String lists are sorted so
#     serialization is stable regardless of set/hash ordering.
#   - Honest verifier: this read path never runs the anti-hallucination
#     verifier, so it NEVER claims "verified". It reports the honest state
#     (unverified / insufficient_evidence / unavailable / error) instead.
#   - Honest lead score: the existing Lead "Score" is normalized and surfaced
#     as an input/hint with its source stated. It is never recomputed and the
#     source of truth is never replaced. Missing/invalid → an explicit
#     missing/invalid state, never an invented number.

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Contract version — bump only on a breaking projection-shape change.
PROJECTION_VERSION = 1

# ── Verifier states (honest vocabulary) ───────────────────────────────────────
# "verified" is part of the contract vocabulary but is intentionally never
# emitted by this read-only path — Phase 1 runs no affirmative verifier.
VERIFIER_VERIFIED     = "verified"
VERIFIER_UNVERIFIED   = "unverified"
VERIFIER_INSUFFICIENT = "insufficient_evidence"
VERIFIER_UNAVAILABLE  = "unavailable"
VERIFIER_ERROR        = "error"

# ── Lead-score states ─────────────────────────────────────────────────────────
SCORE_PRESENT = "present"
SCORE_MISSING = "missing"
SCORE_INVALID = "invalid"

# Sentinel: caller passes events=EVENTS_UNAVAILABLE when the Lead-Events read
# itself failed (distinct from an empty list, which means "no events exist").
EVENTS_UNAVAILABLE = None


def build_reasoning_projection(
    lead_record: dict,
    events,
    as_of: datetime,
) -> dict:
    """
    Build the read-only "reasoning" projection for one Lead.

    lead_record — {"id": "rec...", "fields": {...}} already loaded by the caller.
    events      — list of already-loaded Lead-Event records, or EVENTS_UNAVAILABLE
                  (None) when the Lead-Events read failed. This function performs
                  no reads of its own.
    as_of       — the single request-scoped reference time. Threaded into the
                  reasoning engine so the projection is deterministic.

    Returns a typed, JSON-serializable dict. Never raises for ordinary data
    problems (missing/partial fields, empty/unavailable events) — those map to
    honest states inside the projection.
    """
    as_of_dt  = _as_utc(as_of)
    as_of_iso = as_of_dt.isoformat()

    events_available = events is not EVENTS_UNAVAILABLE
    events_list      = list(events) if events_available else []

    lead_score = _normalize_lead_score(lead_record.get("fields", lead_record))

    # Drive the existing Core Reasoning Layer through the Leads adapter, with
    # all-null ports (zero I/O) and a fixed reference time (determinism).
    from core.adapters.leads_adapter import LeadsAdapter
    from core.reasoning_engines import run as reasoning_run
    from core.reasoning_ports import ReasoningPorts

    adapter = LeadsAdapter()
    entity  = adapter.to_entity(lead_record, events=events_list)
    result  = reasoning_run(
        entity,
        ports=ReasoningPorts(),        # all null → no Airtable, no network, no LLM
        require_feature_flag=False,     # the endpoint owns the off/shadow/on gate
        now=as_of_dt,                   # deterministic reference time
    )

    errors = sorted(str(e) for e in (result.errors or []))
    verifier = _verifier_status(errors, events_available, events_list, result.missing_evidence)

    next_step = None
    if result.next_step is not None:
        next_step = {
            "action":      result.next_step.action,
            "responsible": result.next_step.responsible,
            "detail":      result.next_step.detail,
        }

    return {
        "version":            PROJECTION_VERSION,
        "as_of":              as_of_iso,
        "state":              result.phase,
        "readiness":          result.phase,   # readiness == lifecycle phase for leads
        "confidence": {
            "score": round(float(result.confidence_score), 4),
            "basis": "reasoning_engine",       # Core Reasoning confidence over lead events
        },
        "missing_evidence":   sorted(str(m) for m in (result.missing_evidence or [])),
        "verifier":           verifier,
        "next_step":          next_step,
        "attention_priority": result.attention_priority,
        "lead_score":         lead_score,
        "events": {
            "available": events_available,
            "count":     len(events_list),
        },
        "engine": {
            "degraded": bool(errors),
            "errors":   errors,
        },
    }


def degraded_projection(as_of: datetime, reason: str) -> dict:
    """
    Honest degraded projection for the "on" state when the projection build
    itself fails. Never hides the failure as success; never claims "verified".
    Keeps GET /api/leads/<id> from failing because of a reasoning error.
    """
    as_of_iso = _as_utc(as_of).isoformat()
    return {
        "version":            PROJECTION_VERSION,
        "as_of":              as_of_iso,
        "state":              "UNKNOWN",
        "readiness":          "UNKNOWN",
        "confidence":         {"score": 0.0, "basis": "unavailable"},
        "missing_evidence":   [],
        "verifier":           {"status": VERIFIER_ERROR, "reason": str(reason)},
        "next_step":          None,
        "attention_priority": "NONE",
        "lead_score":         {"value": None, "state": SCORE_MISSING, "source": None, "recomputed": False},
        "events":             {"available": False, "count": 0},
        "engine":             {"degraded": True, "errors": [str(reason)]},
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verifier_status(
    errors: list[str],
    events_available: bool,
    events_list: list,
    missing_evidence,
) -> dict:
    """
    Deterministic, honest verifier status. Never returns "verified": the
    read-only projection runs no affirmative anti-hallucination verifier, so an
    absence of errors is not proof of correctness.
    """
    if errors:
        return {"status": VERIFIER_ERROR,
                "reason": "reasoning engine reported errors"}
    if not events_available:
        return {"status": VERIFIER_UNAVAILABLE,
                "reason": "lead events could not be read"}
    if not events_list:
        return {"status": VERIFIER_INSUFFICIENT,
                "reason": "no lead events to reason over"}
    return {"status": VERIFIER_UNVERIFIED,
            "reason": "reasoning computed; no affirmative verification in read-only projection"}


def _normalize_lead_score(fields: dict) -> dict:
    """
    Normalize the existing Lead score as an honest input/hint. Never recomputes
    it, never invents a value, and states its source. Mirrors the field-name
    fallbacks used by LeadsAdapter (Score / Lead Score).
    """
    raw, source_field = None, None
    for name in ("Score", "Lead Score"):
        if name in fields and fields.get(name) not in (None, ""):
            raw, source_field = fields.get(name), name
            break

    if raw is None:
        return {"value": None, "state": SCORE_MISSING, "source": None, "recomputed": False}

    try:
        value = int(raw)
    except (ValueError, TypeError):
        return {"value": None, "state": SCORE_INVALID,
                "source": f"lead_record.{source_field}", "recomputed": False}

    return {"value": value, "state": SCORE_PRESENT,
            "source": f"lead_record.{source_field}", "recomputed": False}


def _as_utc(dt: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC. Naive input is assumed UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
