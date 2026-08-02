# core/router/__init__.py
from .router         import route_request, deterministic_create_task_title
from .route_decision import RouteDecision, Intent, RouterDomain, Risk, Handler
from .channel_router import Channel
from .ownership_contracts import (
    CanonicalActionProposal,
    IntentOwnershipDecision,
    IntentOwnershipRegistry,
    ResolverResult,
)
from .task_builders import (
    build_complete_task_proposal,
    build_create_task_proposal,
    build_update_task_proposal,
)

__all__ = [
    "route_request",
    "deterministic_create_task_title",
    "RouteDecision", "Intent", "RouterDomain", "Risk", "Handler",
    "Channel",
    "IntentOwnershipDecision", "CanonicalActionProposal", "ResolverResult",
    "IntentOwnershipRegistry",
    "build_create_task_proposal", "build_update_task_proposal",
    "build_complete_task_proposal",
]
