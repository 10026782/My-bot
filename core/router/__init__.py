# core/router/__init__.py
from .router         import (
    route_request,
    deterministic_create_task_title,
    parse_deterministic_create_task,
    DeterministicTaskParse,
)
from .route_decision import RouteDecision, Intent, RouterDomain, Risk, Handler
from .channel_router import Channel
from .ownership_contracts import (
    CapabilityResolutionError,
    CanonicalActionProposal,
    ExecutionClass,
    IntentOwnershipDecision,
    IntentOwnershipRegistry,
    ResolvedCapability,
    ResolverResult,
    resolve_capability,
)
from .task_builders import (
    build_complete_task_proposal,
    build_create_task_proposal,
    build_update_task_proposal,
)
from .task_resolvers import resolve_task
from .task_integration import prepare_task_proposal
from .entity_resolvers import (
    ActionContractLookupSource,
    CallbackLookupSource,
    SessionLookupSource,
    resolve_action_contract,
    resolve_callback,
    resolve_contact,
    resolve_deal,
    resolve_lead,
    resolve_session,
)
from .lead_builders import (
    CapturePolicy,
    LeadIdentityPrecondition,
    build_create_lead_proposal,
    build_update_lead_proposal,
)
from .lead_integration import prepare_lead_proposal

__all__ = [
    "route_request",
    "deterministic_create_task_title",
    "parse_deterministic_create_task",
    "DeterministicTaskParse",
    "RouteDecision", "Intent", "RouterDomain", "Risk", "Handler",
    "Channel",
    "IntentOwnershipDecision", "CanonicalActionProposal", "ResolverResult",
    "IntentOwnershipRegistry",
    "CapabilityResolutionError", "ExecutionClass", "ResolvedCapability",
    "resolve_capability",
    "build_create_task_proposal", "build_update_task_proposal",
    "build_complete_task_proposal",
    "resolve_task",
    "resolve_lead", "resolve_contact", "resolve_deal",
    "resolve_action_contract", "resolve_session", "resolve_callback",
    "ActionContractLookupSource", "SessionLookupSource", "CallbackLookupSource",
    "prepare_task_proposal",
    "build_create_lead_proposal", "build_update_lead_proposal",
    "CapturePolicy", "LeadIdentityPrecondition",
    "prepare_lead_proposal",
]
