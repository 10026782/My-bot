# core/router/risk_router.py — CORE_02 Soft Router
#
# Rules:
#   1. UNKNOWN → agent always (never block unrecognised text)
#   2. Greeting/smalltalk/read-only → agent always
#   3. HIGH_RISK → approval (senior) | block (everyone else)
#   4. NORMAL → agent for external roles; domain-gated for internal
#   5. Fallback → agent (never block by default)

from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from .route_decision import Intent, RouterDomain, Risk, Handler
import tool_registry

if TYPE_CHECKING:
    from identity import Identity
    from context import AgentContext
    from .route_decision import RouteDecision

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Intent Buckets
# ══════════════════════════════════════════════════

_READ_ONLY_INTENTS = {
    Intent.GREETING, Intent.SMALLTALK, Intent.BOT_STATUS_CHECK,
    Intent.ASK_QUESTION, Intent.REQUEST_INFO, Intent.SUMMARIZE,
    Intent.TRANSLATE, Intent.EXPLAIN,
    Intent.LIST_TASKS, Intent.LIST_EVENTS, Intent.LIST_CONTACTS,
    Intent.FIND_CONTACT, Intent.FIND_LEAD,
    Intent.SEARCH_KNOWLEDGE, Intent.READ_DOCUMENT, Intent.RETRIEVE_MEMORY,
    Intent.SYSTEM_STATUS,
    Intent.GENERATE_REPORT, Intent.FINANCIAL_REPORT, Intent.SALES_REPORT,
    Intent.RESEARCH_TOPIC, Intent.RESEARCH_COMPANY,
}

_NORMAL_INTENTS = {
    Intent.CREATE_TASK, Intent.UPDATE_TASK, Intent.COMPLETE_TASK,
    Intent.CREATE_EVENT, Intent.UPDATE_EVENT, Intent.SCHEDULE_MEETING,
    Intent.CREATE_CONTACT, Intent.UPDATE_CONTACT,
    Intent.CREATE_LEAD, Intent.UPDATE_LEAD,
    Intent.QUALIFY_LEAD, Intent.UPDATE_DEAL_STAGE,
    Intent.DRAFT_EMAIL, Intent.DRAFT_MESSAGE,
    Intent.STORE_MEMORY,
}

# ══════════════════════════════════════════════════
# PA-01 — Canonical intent → contract-expectation policy
# docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md §3.5/§3.6
# (approved commit 81676ad). Single policy source — no duplicate list/dict
# of this mapping anywhere else, including app.py.
# ══════════════════════════════════════════════════

_CONTRACT_REQUIRED_INTENT_TO_TOOL: dict[str, str] = {
    Intent.CREATE_TASK:       "airtable_add",
    Intent.UPDATE_TASK:       "airtable_update",
    Intent.COMPLETE_TASK:     "airtable_update",
    Intent.CREATE_EVENT:      "calendar_create_event",
    Intent.SCHEDULE_MEETING:  "calendar_create_event",
    Intent.CREATE_CONTACT:    "airtable_add",
    Intent.UPDATE_CONTACT:    "airtable_update",
    Intent.CREATE_LEAD:       "airtable_add",
    Intent.UPDATE_LEAD:       "airtable_update",
    Intent.UPDATE_DEAL_STAGE: "airtable_update",
}
assert set(_CONTRACT_REQUIRED_INTENT_TO_TOOL) <= _NORMAL_INTENTS
_NON_CONTRACT_NORMAL_INTENTS = _NORMAL_INTENTS - set(_CONTRACT_REQUIRED_INTENT_TO_TOOL)


def intent_requires_contract_for_success(intent: str | None) -> bool:
    """True iff a successful fulfillment of this intent requires a real
    ActionContract — policy-only, role/domain-invariant. See §3.5."""
    return intent in _CONTRACT_REQUIRED_INTENT_TO_TOOL


def expected_tool_for_intent(intent: str | None) -> str | None:
    """The one dispatcher tool this intent's ActionContract must be created
    for. None if the intent is not contract-required."""
    return _CONTRACT_REQUIRED_INTENT_TO_TOOL.get(intent)


def contract_capable_this_turn(
    route: "RouteDecision", identity: "Identity", ctx: "AgentContext",
) -> bool:
    """
    Runtime-dependent — can *this* identity's *this* turn actually reach a
    contract for the intent's expected tool at all? Combines three already-
    existing, independently-maintained signals (§3.6): the role-filtered
    tool list actually offered to Claude this turn, the tool_registry's own
    role-tool policy, and the router's own tool_allowed flag. Table-
    granularity gaps (e.g. Leads-specific preflight) are NOT covered here —
    see PREFLIGHT_BLOCKED in §3.6's terminal-outcome table.
    """
    expected_tool = expected_tool_for_intent(getattr(route, "intent", None))
    if expected_tool is None:
        return False
    return (
        any(t.get("name") == expected_tool for t in (getattr(ctx, "allowed_tools", None) or []))
        and tool_registry.check_allowed(expected_tool, identity)
        and bool(getattr(route, "tool_allowed", True))
    )


# Explicit protected actions — block for anyone below senior
_HIGH_RISK_INTENTS = {
    Intent.DELETE_TASK, Intent.CANCEL_EVENT,
    Intent.SEND_EMAIL, Intent.SEND_MESSAGE,
    Intent.CLOSE_DEAL, Intent.ADMIN_ACTION,
}

# ══════════════════════════════════════════════════
# Domain Risk Modifiers
# ══════════════════════════════════════════════════

_SENSITIVE_DOMAINS = {RouterDomain.FINANCE, RouterDomain.SAAS}
_LOW_RISK_DOMAINS  = {RouterDomain.CRM, RouterDomain.GENERAL}


# ══════════════════════════════════════════════════
# Role Groups
# ══════════════════════════════════════════════════

_SENIOR_ROLES     = {"owner", "partner"}
_MANAGEMENT_ROLES = {"owner", "partner", "manager"}
_EXTERNAL_ROLES   = {"lead", "guest", "readonly"}


# ══════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════

def detect_risk(
    intent: str,
    role:   str,
    domain: str = RouterDomain.GENERAL,
) -> tuple[str, str, bool]:
    """
    Returns (risk_level, handler, needs_approval).
    Soft router: only explicit HIGH_RISK intents are blocked.
    Unknown / casual conversation always reaches the agent.
    """
    # ── Rule 1 & 7: UNKNOWN → Agent for everyone ──────
    if intent == Intent.UNKNOWN:
        return Risk.NORMAL, Handler.AGENT, False

    # ── Rule 3: Read-only intents → Agent always ───────
    if intent in _READ_ONLY_INTENTS:
        return Risk.READ_ONLY, Handler.AGENT, False

    # ── Rule 4 & 5: Explicit protected actions ─────────
    # Senior roles → approval flow.
    # Everyone else → RESTRICTED: agent talks, tools silently blocked,
    # owner gets a log notification. No ⛔ to the user.
    if intent in _HIGH_RISK_INTENTS:
        if role in _SENIOR_ROLES:
            logger.info(f"[Risk] HIGH_RISK approval: role={role} intent={intent}")
            return Risk.NEEDS_APPROVAL, Handler.APPROVAL, True
        logger.warning(f"[Risk] RESTRICTED explicit protected action: role={role} intent={intent}")
        return Risk.NEEDS_APPROVAL, Handler.RESTRICTED, False

    # ── Normal Intents ─────────────────────────────────
    if intent in _NORMAL_INTENTS:
        # Rule 2 & 6: external roles → Agent handles gracefully
        if role in _EXTERNAL_ROLES:
            return Risk.NORMAL, Handler.AGENT, False

        # finance/saas + non-senior → approval
        if domain in _SENSITIVE_DOMAINS and role not in _SENIOR_ROLES:
            logger.info(f"[Risk] SENSITIVE domain={domain} role={role} → approval")
            return Risk.NEEDS_APPROVAL, Handler.APPROVAL, True

        # employee in non-standard domain → approval
        if role == "employee" and domain not in _LOW_RISK_DOMAINS:
            return Risk.NEEDS_APPROVAL, Handler.APPROVAL, True

        # employee in crm/general or any management role → normal
        return Risk.NORMAL, Handler.AGENT, False

    # ── Rule 1 & 7: Fallback → Agent (never block by default) ─
    logger.debug(f"[Risk] Unclassified intent={intent} → agent")
    return Risk.NORMAL, Handler.AGENT, False
