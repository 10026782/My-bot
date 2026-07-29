"""Request-local observability for deterministic approval turns.

These counters deliberately never participate in lifecycle decisions.  They
exist only to make the approval fast-path auditable without introducing a
second source of truth beside ActionContracts.
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ApprovalTurnMetrics:
    agent_call_count: int = 0
    action_contract_read_count: int = 0
    final_response_count: int = 0
    deterministic_path_used: bool = False

    def emit(self, ingress: str) -> None:
        # Do not add identity, message, payload, or response content here.
        logger.info(
            "[ApprovalTurnMetrics] ingress=%s agent_calls=%d contract_reads=%d "
            "final_responses=%d deterministic=%s",
            ingress, self.agent_call_count, self.action_contract_read_count,
            self.final_response_count, self.deterministic_path_used,
        )


_current: contextvars.ContextVar[ApprovalTurnMetrics | None] = contextvars.ContextVar(
    "approval_turn_metrics", default=None,
)


def begin() -> tuple[ApprovalTurnMetrics, contextvars.Token]:
    metrics = ApprovalTurnMetrics()
    return metrics, _current.set(metrics)


def end(token: contextvars.Token, ingress: str) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.emit(ingress)
    _current.reset(token)


def current() -> ApprovalTurnMetrics | None:
    return _current.get()


def record_action_contract_read() -> None:
    metrics = current()
    if metrics is not None:
        metrics.action_contract_read_count += 1


def record_agent_call() -> None:
    metrics = current()
    if metrics is not None:
        metrics.agent_call_count += 1


def record_final_response(*, deterministic: bool = False) -> None:
    metrics = current()
    if metrics is not None:
        metrics.final_response_count += 1
        metrics.deterministic_path_used |= deterministic
