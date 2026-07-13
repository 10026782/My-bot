# core/dispatcher_outcome.py — Phase 4B0: Structured Dispatcher Outcome Contract
#
# Replaces fragile string/emoji parsing with explicit outcome classification.
# Dispatcher must return DispatcherOutcome with structured result, not user-facing text.

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any


@dataclass(frozen=True)
class DispatcherOutcome:
    """
    Structured outcome from dispatcher call. Atomic executor consumes this explicitly.

    result: "completed" | "failed" | "outcome_unknown"
    - completed: Explicit success with required evidence (ok=true, external_id, etc.)
    - failed: Known failure (permission denied, validation error, provider error)
    - outcome_unknown: Ambiguous (timeout, transport error after request sent, retry-ability unknown)

    The atomic executor MUST NOT infer execution truth from user_message text.
    user_message is for end-user display only; it must never drive execution logic.
    """
    result: str  # "completed" | "failed" | "outcome_unknown"
    user_message: str  # For end-user display (may contain ❌, ✅, etc.)
    external_id: Optional[str] = None  # Record ID from provider (if completed)
    error_code: Optional[str] = None  # Structured error code (if failed)
    error: Optional[str] = None  # Error details (if failed or outcome_unknown)
    raw_response: Optional[dict] = None  # Raw provider response for audit

    def is_completed(self) -> bool:
        return self.result == "completed"

    def is_failed(self) -> bool:
        return self.result == "failed"

    def is_outcome_unknown(self) -> bool:
        return self.result == "outcome_unknown"

    def __post_init__(self):
        # Validate result value
        if self.result not in ("completed", "failed", "outcome_unknown"):
            raise ValueError(f"Invalid result: {self.result}. Must be 'completed', 'failed', or 'outcome_unknown'.")
