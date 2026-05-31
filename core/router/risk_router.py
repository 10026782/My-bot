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
from .route_decision import Intent, RouterDomain, Risk, Handler

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
    # Only senior roles can trigger approval; everyone else is blocked.
    # External roles (lead/guest/readonly) are blocked here too —
    # this is an explicit restricted action, not casual chat.
    if intent in _HIGH_RISK_INTENTS:
        if role in _SENIOR_ROLES:
            logger.info(f"[Risk] HIGH_RISK approval: role={role} intent={intent}")
            return Risk.NEEDS_APPROVAL, Handler.APPROVAL, True
        logger.warning(f"[Risk] BLOCK explicit protected action: role={role} intent={intent}")
        return Risk.BLOCK, Handler.BLOCK, False

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
