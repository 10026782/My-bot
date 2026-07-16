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

# ── Readiness states (honest — never derived from phase) ──────────────────────
# LeadsAdapter supplies no readiness signal and no approved Lead-readiness policy
# exists in Phase 1, so readiness is reported as an explicit honest state, never
# as a positive value and never as a copy of the lifecycle phase/state.
READINESS_UNKNOWN     = "unknown"
READINESS_UNAVAILABLE = "unavailable"
_READINESS_UNKNOWN_REASON = "leads adapter supplies no readiness signal (phase 1)"

# Deterministic cap on how many linked Lead-Event IDs feed one lookup. The
# caller (endpoint) enforces the actual read; this constant documents the
# contract the projection was designed against.
MAX_LEAD_EVENT_IDS = 50

# Live Leads schema → LeadsAdapter-expected field names. The adapter still
# reads legacy CamelCase names in places; we normalize the live snapshot into
# those names here (pure, no adapter refactor) so canonical live fields are not
# silently dropped into wrong defaults.
_LIVE_TO_ADAPTER_FIELDS = (
    ("phone",      "Phone"),
    ("status",     "Status"),
    ("tier",       "Tier"),
    ("source",     "Source"),
    ("channel",    "Channel"),
    ("domain",     "Domain"),
    ("created_at", "Created At"),
    ("updated_at", "Last Updated"),
    ("notes",      "Notes"),
    ("summary",    "Source Details"),
    ("Score",      "Score"),          # passed through, never recomputed
    ("Name",       "Name"),
)

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

    live_fields = lead_record.get("fields", lead_record)
    lead_score  = _normalize_lead_score(live_fields)

    # Normalize the live snapshot into the field names LeadsAdapter reads
    # (pure; the original record is never mutated), then drive the existing
    # Core Reasoning Layer through the adapter with all-null ports (zero I/O)
    # and a fixed reference time (determinism).
    from core.reasoning_engines import run as reasoning_run
    from core.reasoning_ports import ReasoningPorts

    entity  = build_reasoning_entity(lead_record, events_list)
    result  = reasoning_run(
        entity,
        ports=ReasoningPorts(),        # all null → no Airtable, no network, no LLM
        require_feature_flag=False,     # the endpoint owns the off/shadow/on gate
        now=as_of_dt,                   # deterministic reference time
    )

    errors = sorted(str(e) for e in (result.errors or []))
    verifier = _verifier_status(errors, events_available, events_list, result.missing_evidence)
    readiness = _readiness_state(errors)

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
        "state":              result.phase,      # lifecycle phase (distinct from readiness)
        "readiness":          readiness,          # honest state, never a copy of phase
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


def build_reasoning_entity(lead_record: dict, events_list: list):
    """
    Build the ReasoningEntity for one lead: normalize the live snapshot into the
    adapter's field names, run it through LeadsAdapter, and apply the explicit
    canonical-domain correction. Pure — the input record is never mutated.
    Exposed so the entity mapping is directly testable.
    """
    from core.adapters.leads_adapter import LeadsAdapter

    normalized = _normalize_lead_snapshot(lead_record)
    entity     = LeadsAdapter().to_entity(normalized, events=events_list)

    # Deterministic domain: honor the explicit canonical `domain` field instead
    # of the adapter's keyword inference (which can misclassify when `source`
    # holds a channel-like token). Pure correction, no adapter refactor.
    explicit_domain = _canonical_domain(lead_record.get("fields", lead_record).get("domain"))
    if explicit_domain:
        entity.domain = explicit_domain
    return entity


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
        "readiness":          {"status": READINESS_UNAVAILABLE,
                               "reason": "reasoning projection unavailable"},
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


def _readiness_state(errors: list[str]) -> dict:
    """
    Honest readiness. Phase 1 has no approved Lead-readiness policy and the
    adapter emits no readiness signal, so readiness is reported as an explicit
    state with a fixed deterministic reason — never a positive value and never
    the lifecycle phase.
    """
    if errors:
        return {"status": READINESS_UNAVAILABLE,
                "reason": "reasoning engine reported errors"}
    return {"status": READINESS_UNKNOWN, "reason": _READINESS_UNKNOWN_REASON}


def _normalize_lead_snapshot(lead_record: dict) -> dict:
    """
    Map a live Leads snapshot to the field names LeadsAdapter reads. Pure — the
    input record is never mutated; a new {"id", "fields"} dict is returned. Only
    known live fields with a non-empty value are carried across, so unknown
    fields are ignored safely and empty live fields do not shadow adapter
    fallbacks. The Score is passed through untouched (never recomputed).
    """
    live = lead_record.get("fields", lead_record)
    out: dict = {}
    for live_name, adapter_name in _LIVE_TO_ADAPTER_FIELDS:
        if live_name in live and live[live_name] not in (None, ""):
            out[adapter_name] = live[live_name]
    return {"id": lead_record.get("id", ""), "fields": out}


def _canonical_domain(value) -> str:
    """Trim a live domain value to a canonical string, or '' when absent/blank."""
    if value is None:
        return ""
    return str(value).strip()


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
