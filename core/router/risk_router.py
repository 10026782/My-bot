# core/router/risk_router.py — CORE_02_ROUTER
# קביעת רמת סיכון לפי role × intent × domain.
#
# כלל ברזל: פעולה בלתי הפיכה לא רצה בלי אישור.
# כלל ברזל: ליד/אורח לעולם לא מגיע לפעולה רגישה.
# כלל ברזל: domain finance מעלה סיכון לכל פעולה.

from __future__ import annotations
import logging
from .route_decision import Intent, RouterDomain, Risk, Handler

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Intent Buckets
# ══════════════════════════════════════════════════

_READ_ONLY_INTENTS = {
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
_BLOCKED_ROLES    = {"lead", "guest", "readonly"}


# ══════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════

def detect_risk(
    intent: str,
    role:   str,
    domain: str = RouterDomain.GENERAL,
) -> tuple[str, str, bool]:
    """
    מחזיר (risk_level, handler, needs_approval).
    מטריצה: role × intent × domain
    """
    # ── חסום מוחלט ────────────────────────────────
    if role in _BLOCKED_ROLES and intent not in _READ_ONLY_INTENTS:
        logger.warning(f"[Risk] BLOCK: role={role} intent={intent} domain={domain}")
        return Risk.BLOCK, Handler.BLOCK, False

    # ── Read Only — תמיד מותר לכולם ───────────────
    if intent in _READ_ONLY_INTENTS:
        return Risk.READ_ONLY, Handler.AGENT, False

    # ── High Risk Intents ──────────────────────────
    if intent in _HIGH_RISK_INTENTS:
        if role in _SENIOR_ROLES:
            logger.info(f"[Risk] HIGH_RISK approval: role={role} intent={intent} domain={domain}")
            return Risk.NEEDS_APPROVAL, Handler.APPROVAL, True
        # manager/employee → חסום על high risk
        logger.warning(f"[Risk] BLOCK high_risk: role={role} intent={intent}")
        return Risk.BLOCK, Handler.BLOCK, False

    # ── Normal Intents — domain modifier ──────────
    if intent in _NORMAL_INTENTS:

        # finance/saas + לא senior → דורש אישור
        if domain in _SENSITIVE_DOMAINS and role not in _SENIOR_ROLES:
            logger.info(f"[Risk] SENSITIVE domain={domain} role={role} → approval")
            return Risk.NEEDS_APPROVAL, Handler.APPROVAL, True

        # employee בדומיין רגיל → אישור
        if role == "employee" and domain not in _LOW_RISK_DOMAINS:
            return Risk.NEEDS_APPROVAL, Handler.APPROVAL, True

        # employee ב-crm/general → נורמל
        if role == "employee":
            return Risk.NORMAL, Handler.AGENT, False

        # management + כל דומיין → נורמל
        if role in _MANAGEMENT_ROLES:
            return Risk.NORMAL, Handler.AGENT, False

    # ── Unknown intent ─────────────────────────────
    logger.debug(f"[Risk] Unknown intent={intent} → clarify")
    return Risk.NORMAL, Handler.CLARIFY, False
