# core/turn_result.py — N18 Phase 2: terminal-turn-result primitive.
#
# Formalizes the "did this call end the turn" signal Lead's draft-card
# confirm/cancel path already returns today as a bare Optional[str] — every
# caller does `if reply is not None: return reply`, duplicated ad hoc at
# each call site (app.py's confirm-word branch, cancel-word branch, and
# _resolve_lead_draft's own cancel/confirm outcomes). TurnResult makes that
# an explicit, named type instead of relying on "some string" vs. None,
# and carries an optional machine-readable status alongside the rendered
# message.
#
# This is deliberately NOT the full Phase 4 UX Contract (structured
# entity/operation/status/display_name/domain/owner/external_id result,
# a separate UX-rendering layer, internal-ID hiding) — that remains
# Phase 4's job, sequenced last because it touches single-speaker/UX more
# broadly. Only the narrow draft-confirm/cancel path (the truly generic,
# entity-agnostic piece already extracted into core/draft_flow.py) uses
# this here; handle_lead_candidate()'s own broader Optional[str] contract
# (spanning Tier 1-5 Lead-business-specific paths) is untouched.

from dataclasses import dataclass
from typing import Optional

STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"
STATUS_INCOMPLETE = "incomplete"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class TurnResult:
    """A terminal reply for the current turn. message is what the user
    sees; status is an optional machine-readable outcome for callers that
    care (e.g. bulk-processing summaries) — absent when there's nothing
    more specific than "this ended the turn"."""
    message: str
    status: Optional[str] = None
