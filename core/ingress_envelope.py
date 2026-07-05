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
#   EvidenceTrace — post-classification data (classification/approval/
#   observation), populated only after the corresponding process actually
#   ran (classify_ingress / preview / ActionGateway approval). A partial
#   trace — e.g. stopped at Tier 3/4 clarification, no write — is a valid
#   end state, not a failure.
#
# "לעולם לא לגלות שוב ש-Telegram יודע לעשות משהו ש-WhatsApp לא" (BUG-071 pattern).
#
# This module only defines the schemas + their validation. No adapter wiring,
# no changes to classify_ingress()/C90, no channel-specific code — that is
# later stages (see the C94 ROADMAP entry).

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ══════════════════════════════════════════════════
# Layer 1 — IngressEnvelope (7 required fields, pre-classification)
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
    raw_ref:         str = ""    # continues C89's RAW-OBS guarantee — non-empty, never a new mechanism

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
        _require_nonempty("raw_ref", self.raw_ref)

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
# Layer 2 — EvidenceTrace (3 fields, populated after preview/approval/write)
# ══════════════════════════════════════════════════

class TraceValidationError(ValueError):
    """Raised when an EvidenceTrace violates its ordering invariant — a
    later-stage field populated without evidence that the stage(s) it
    depends on actually happened."""


@dataclass
class EvidenceTrace:
    classification_result: Optional[object] = None  # classify_ingress() result — set right after classification
    approval_contract_id:  Optional[str] = None      # ActionGateway contract id — set only if/when approval was required
    agent_observation:     Optional[str] = None      # agent's lead/task/update/action reasoning — set only after preview

    def validate(self) -> None:
        """
        A trace is a valid state at ANY point in its lifecycle — fully empty
        (nothing happened yet) and partially filled (e.g. stopped at Tier 3/4
        clarification, no write) are both valid, not errors. This only checks
        the ordering invariant: approval/observation can't exist without the
        classification that must precede them.
        """
        if self.classification_result is None:
            if self.approval_contract_id is not None:
                raise TraceValidationError(
                    "approval_contract_id is set without classification_result — "
                    "approval cannot precede classification"
                )
            if self.agent_observation is not None:
                raise TraceValidationError(
                    "agent_observation is set without classification_result — "
                    "observation cannot precede classification"
                )

    @property
    def is_complete(self) -> bool:
        """True only once all 3 fields exist — i.e. classification ran,
        preview/observation happened, AND approval (if required) resolved.
        False is not a failure state; see validate()."""
        return (
            self.classification_result is not None
            and self.approval_contract_id is not None
            and self.agent_observation is not None
        )
