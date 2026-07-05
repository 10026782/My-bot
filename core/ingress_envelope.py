# core/ingress_envelope.py — C94: Unified Ingress Envelope + Evidence Trace, Stage א (schemas only)
#
# Two separate layers, never merged into one object:
#
#   IngressEnvelope — pre-classification data. Must be 7/7 valid BEFORE the
#   envelope enters classify_ingress() (C89) or the file/row pipeline (C90).
#   No field here depends on a later-stage outcome, so there is never a
#   reason to fill one with a guessed/placeholder value — a producing
#   adapter that can't fill all 7 must fail/stop instead.
#
#   EvidenceTrace — post-classification data (classification/raw-capture/
#   approval/observation), populated only after the corresponding process
#   actually ran (classify_ingress / preview / ActionGateway approval). A
#   partial trace — e.g. stopped at Tier 3/4 clarification, no write, or a
#   failed classification attempt — is a valid end state, not a failure.
#
# C94-A.1 amendment: raw_ref moved from IngressEnvelope to EvidenceTrace.
# C89's raw_ref (Decision Inbox record id / local fallback, via
# ingress_classifier._save_raw_capture()) is only produced INSIDE
# classify_ingress() itself — requiring it non-empty on the Envelope
# (pre-classification) would force every adapter to either call C89's
# raw-capture mechanism a second time (duplicate writes) or invent a
# parallel one, both forbidden by this spec. IngressEnvelope carries
# source_ref instead: a lightweight, adapter-level pointer to the original
# input (e.g. "file:<filename>:row<N>", a message id) that adapters can
# always produce before classification, with zero changes to
# core/ingress_classifier.py. EvidenceTrace.raw_ref carries C89's own
# raw_ref, copied in by the pipeline after classify_ingress() returns.
#
# C94-A.2 amendment: two more gaps closed before Stage ב wiring —
#   1. FK: EvidenceTrace.envelope_id references IngressEnvelope.envelope_id
#      (a UUID assigned once, at Envelope construction). This is a plain FK,
#      not nesting — an Envelope can exist with zero Traces (e.g.
#      classify_ingress() never got called), and the reference is
#      one-directional (Trace → Envelope) so there's no cycle.
#   2. One envelope_id can have MULTIPLE Traces over time (e.g. a retried
#      classification after a transient failure) — Traces are append-only:
#      record_classification() may be called at most once per Trace
#      instance; a retry must construct a NEW EvidenceTrace (same
#      envelope_id), never overwrite an existing one's outcome.
#   3. A classify_ingress() call that raises (not just a low-confidence
#      Tier 5 result) must still leave evidence that the attempt happened —
#      classification_error captures that, mutually exclusive with
#      classification_result. Without this, a row that errors during
#      classification would vanish with no Trace at all.
#
# C94-A.3 amendment: envelope_id alone can't distinguish MULTIPLE attempts on
# the same envelope (a retry after a transient classify_ingress() failure) —
# both attempts shared one envelope_id with no way to tell them apart or find
# "the latest one". Added:
#   - trace_id: unique per EvidenceTrace instance (per attempt).
#   - attempt_no: 1-based, strictly increasing per envelope_id — assigned by
#     next_attempt() below, not guessed by the caller.
#   - status: a read-only property (never a stored field, so it can't drift
#     from the actual data) — "empty" / "classification_error" / "classified"
#     / "complete".
#   - latest_trace()/next_attempt(): the only sanctioned way to pick "the
#     current attempt" out of a list of Traces, or construct the next one.
# Callers must sanitize classification_error before recording it — never the
# raw exception message (may embed row text / PII), only a safe summary
# (e.g. type(exc).__name__).
#
# "לעולם לא לגלות שוב ש-Telegram יודע לעשות משהו ש-WhatsApp לא" (BUG-071 pattern).
#
# This module only defines the schemas + their validation. No adapter wiring,
# no changes to classify_ingress()/C90, no channel-specific code — that is
# later stages (see the C94 ROADMAP entry).

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


# ══════════════════════════════════════════════════
# Layer 1 — IngressEnvelope (7 required fields + envelope_id, pre-classification)
# ══════════════════════════════════════════════════

# source_channel is always the LOGICAL channel, never the provider that
# implements it (see PROVIDERS below) — this is what lets a provider swap
# (e.g. WhatsApp Twilio → Meta Cloud API) happen without touching any code
# keyed on source_channel.
SOURCE_CHANNELS = frozenset({"telegram", "whatsapp", "file_upload", "voice", "text"})

# provider is always the TECHNICAL mechanism behind a source_channel.
PROVIDERS = frozenset({"telegram_bot_api", "twilio_whatsapp", "meta_cloud_api"})

# shorthand provider names that must never be written into source_channel
# (BUG-071 pattern) — distinct from PROVIDERS itself, since the mistake this
# guards against is typing the bare provider ("twilio", "meta"), not the full
# provider string.
_PROVIDER_LEAK_TOKENS = frozenset({"twilio", "meta"})


class EnvelopeValidationError(ValueError):
    """Raised when an IngressEnvelope is missing/invalid a required field."""


@dataclass(frozen=True)
class IngressEnvelope:
    source_channel:  str          # logical channel only — telegram/whatsapp/file_upload/voice/text
    provider:        str          # technical mechanism — telegram_bot_api/twilio_whatsapp/meta_cloud_api
    raw_event_id:    str          # original message/webhook id
    sender_identity: str          # identity.memory_key value — no parallel identity mechanism
    normalized_text: str          # the text that actually gets classified
    attachments:     tuple = ()   # media refs (file/image/voice/csv/xlsx)
    source_ref:      str = ""     # adapter-level pointer to the original input — non-empty, distinct,
                                   # produced BEFORE classification. NOT C89's raw_ref (see EvidenceTrace).
    envelope_id:     str = field(default_factory=lambda: uuid.uuid4().hex)
                                   # stable id for this envelope — the FK target for EvidenceTrace.envelope_id.
                                   # A retry of classification reuses this SAME envelope_id on a new Trace;
                                   # it does not get regenerated (this is still "the same input event").

    def validate(self) -> None:
        """
        Validation gate for entry into classify_ingress()/C90: all 7 fields
        must be non-empty and non-placeholder. Raises EnvelopeValidationError
        on the first violation — callers (adapters) must fail/stop, never
        silently substitute a default.
        """
        _require_nonempty("raw_event_id", self.raw_event_id)
        _require_nonempty("sender_identity", self.sender_identity)
        _require_nonempty("normalized_text", self.normalized_text)
        _require_nonempty("source_ref", self.source_ref)
        _require_nonempty("envelope_id", self.envelope_id)

        if self.attachments is None:
            raise EnvelopeValidationError("attachments must be a list/tuple, not None")

        _require_nonempty("provider", self.provider)
        if self.provider not in PROVIDERS:
            raise EnvelopeValidationError(
                f"provider={self.provider!r} is not a known provider "
                f"(expected one of {sorted(PROVIDERS)})"
            )

        _require_nonempty("source_channel", self.source_channel)
        if self.source_channel not in SOURCE_CHANNELS:
            # BUG-071 pattern: a provider name leaking into source_channel
            # (e.g. "twilio", "meta") breaks provider-swap independence.
            if self.source_channel in PROVIDERS or self.source_channel.lower() in _PROVIDER_LEAK_TOKENS:
                raise EnvelopeValidationError(
                    f"source_channel={self.source_channel!r} is a provider name, not a "
                    f"logical channel (BUG-071 pattern) — did you mean provider={self.source_channel!r}?"
                )
            raise EnvelopeValidationError(
                f"source_channel={self.source_channel!r} is not a known logical channel "
                f"(expected one of {sorted(SOURCE_CHANNELS)})"
            )


def _require_nonempty(field_name: str, value: str) -> None:
    if value is None or not isinstance(value, str) or not value.strip():
        raise EnvelopeValidationError(f"{field_name} is required and must be a non-empty string")


# ══════════════════════════════════════════════════
# Layer 2 — EvidenceTrace (envelope_id FK + 5 fields, populated after
# classification/preview/approval/write; append-only per instance)
# ══════════════════════════════════════════════════

class TraceValidationError(ValueError):
    """Raised when an EvidenceTrace violates its ordering invariant — a
    later-stage field populated without evidence that the stage(s) it
    depends on actually happened — or its append-only invariant (a second
    attempt to record a classification outcome on the same instance)."""


@dataclass
class EvidenceTrace:
    envelope_id:            str = ""          # FK → IngressEnvelope.envelope_id; required once any other field is set
    trace_id:               str = field(default_factory=lambda: uuid.uuid4().hex)  # unique per attempt/instance
    attempt_no:             int = 1           # 1-based, strictly increasing per envelope_id — see next_attempt()
    classification_result:  Optional[object] = None  # classify_ingress() result — set right after a SUCCESSFUL classification
    classification_error:   Optional[str] = None      # set instead of classification_result if classify_ingress() raised.
                                                        # Must be a SAFE summary (e.g. type(exc).__name__) — never the raw
                                                        # exception message, which may embed row text / PII.
    raw_ref:                Optional[str] = None       # C89's own raw_ref (ingress_classifier._save_raw_capture) —
                                                        # copied in by the pipeline only after classify_ingress() returns successfully
    approval_contract_id:   Optional[str] = None       # ActionGateway contract id — set only if/when approval was required
    agent_observation:      Optional[str] = None       # agent's lead/task/update/action reasoning — set only after preview

    def record_classification(
        self,
        *,
        classification_result: Optional[object] = None,
        classification_error: Optional[str] = None,
        raw_ref: Optional[str] = None,
    ) -> None:
        """
        The ONLY sanctioned way to record a classify_ingress() outcome on this
        Trace. Enforces append-only: raises if this instance already recorded
        an outcome — a retry must build a NEW EvidenceTrace (same envelope_id),
        never overwrite this one's classification_result/classification_error.
        Exactly one of classification_result/classification_error must be given.
        """
        if self.classification_result is not None or self.classification_error is not None:
            raise TraceValidationError(
                "classification outcome already recorded on this trace — retries must "
                "create a new EvidenceTrace with the same envelope_id (append-only), "
                "not overwrite this one"
            )
        if (classification_result is None) == (classification_error is None):
            raise TraceValidationError(
                "exactly one of classification_result/classification_error must be set "
                "— a classification attempt either succeeded or failed, never both/neither"
            )
        if classification_result is not None and not raw_ref:
            raise TraceValidationError(
                "raw_ref is required alongside a successful classification_result — "
                "both are produced by the same classify_ingress() call"
            )
        self.classification_result = classification_result
        self.classification_error = classification_error
        self.raw_ref = raw_ref

    def validate(self) -> None:
        """
        A trace is a valid state at ANY point in its lifecycle — fully empty
        (nothing happened yet), a failed classification attempt, and a
        partially-completed trace (e.g. stopped at Tier 3/4 clarification, no
        write) are all valid, not errors. This only checks:
          - envelope_id is set once any other field is (the FK is mandatory,
            not optional bookkeeping)
          - the ordering invariant: raw_ref/approval/observation can't exist
            without a SUCCESSFUL classification_result preceding them
          - classification_result and classification_error are mutually exclusive
        """
        any_field_set = any((
            self.classification_result is not None,
            self.classification_error is not None,
            self.raw_ref is not None,
            self.approval_contract_id is not None,
            self.agent_observation is not None,
        ))
        if any_field_set and not self.envelope_id:
            raise TraceValidationError(
                "envelope_id is required once any trace field is set — a Trace must "
                "reference the Envelope it belongs to"
            )

        if self.attempt_no < 1:
            raise TraceValidationError(f"attempt_no must be >= 1, got {self.attempt_no}")

        if self.classification_result is not None and self.classification_error is not None:
            raise TraceValidationError(
                "classification_result and classification_error are mutually exclusive — "
                "a classification attempt either succeeded or failed, not both"
            )

        if self.classification_result is None:
            if self.raw_ref is not None:
                raise TraceValidationError(
                    "raw_ref is set without classification_result — "
                    "raw_ref is only produced by a successful classify_ingress() call"
                )
            if self.approval_contract_id is not None:
                raise TraceValidationError(
                    "approval_contract_id is set without classification_result — "
                    "approval cannot precede a successful classification"
                )
            if self.agent_observation is not None:
                raise TraceValidationError(
                    "agent_observation is set without classification_result — "
                    "observation cannot precede a successful classification"
                )

    @property
    def is_complete(self) -> bool:
        """True only once classification succeeded (with its raw_ref),
        preview/observation happened, AND approval (if required) resolved.
        A failed classification_error trace can never become complete — that
        is expected, not a failure; see validate()."""
        return (
            self.classification_result is not None
            and self.raw_ref is not None
            and self.approval_contract_id is not None
            and self.agent_observation is not None
        )

    @property
    def status(self) -> str:
        """
        Read-only summary of this Trace's state — computed from the actual
        fields every time, never a separately-stored value that could drift
        out of sync with them. One of: "empty" (nothing recorded yet),
        "classification_error" (a real, valid evidence state — the attempt
        happened and failed), "classified" (succeeded, not yet complete), or
        "complete" (see is_complete).
        """
        if self.classification_error is not None:
            return "classification_error"
        if self.classification_result is None:
            return "empty"
        if self.is_complete:
            return "complete"
        return "classified"


def latest_trace(traces: list[EvidenceTrace]) -> Optional[EvidenceTrace]:
    """
    Returns the Trace with the highest attempt_no — "the current attempt" —
    out of a list of Traces. Callers must pre-filter to a single envelope_id;
    this does not do that filtering itself. None if traces is empty.
    """
    if not traces:
        return None
    return max(traces, key=lambda t: t.attempt_no)


def next_attempt(envelope_id: str, prior_traces: list[EvidenceTrace]) -> EvidenceTrace:
    """
    Constructs a new EvidenceTrace for the next attempt on envelope_id —
    attempt_no = 1 + the highest attempt_no already recorded for this
    envelope_id among prior_traces (or 1 if there are none). This is the only
    sanctioned way to number attempts; never guess/hardcode attempt_no when
    building a retry Trace.
    """
    same_envelope = [t for t in prior_traces if t.envelope_id == envelope_id]
    next_no = max((t.attempt_no for t in same_envelope), default=0) + 1
    return EvidenceTrace(envelope_id=envelope_id, attempt_no=next_no)
