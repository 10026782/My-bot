# core/router/router.py — CORE_02 Soft Router
# Orchestrator only. Calls 4 sub-routers → returns one RouteDecision.
# No business logic. No DB writes. No agent calls.

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from .route_decision  import RouteDecision, Intent, Handler, Risk
from .channel_router  import detect_channel, resolve_tool_for_channel
from .intent_router   import detect_intent
from .domain_router   import detect_domain
from .risk_router     import detect_risk

if TYPE_CHECKING:
    from identity import Identity

logger = logging.getLogger(__name__)

INTENT_CONFIDENCE_THRESHOLD = 0.75


def route_request(
    text:                str,
    channel_raw:         str,
    identity:            "Identity",
    domain_from_channel: str = "",
) -> RouteDecision:
    """
    text + channel + identity → RouteDecision

    domain_from_channel: comes from config.get_domain(to_number) in webhook.
    """
    # 1. Channel
    channel = detect_channel(channel_raw)

    # 2. Intent
    intent, confidence, matched_rule = detect_intent(text)
    if confidence < INTENT_CONFIDENCE_THRESHOLD:
        intent = Intent.UNKNOWN

    # 3. Domain
    domain, _ = detect_domain(
        text                 = text,
        domain_from_channel  = domain_from_channel,
        domain_from_identity = identity.domain_id,
    )

    # 4. Risk + Handler
    risk, handler, needs_approval = detect_risk(
        intent = intent,
        role   = identity.role,
        domain = domain,
    )

    # 5. Channel-specific tool override
    tool_override = resolve_tool_for_channel(intent, channel)

    # 6. Edge cases / response overrides
    if intent == Intent.UNKNOWN:
        # Safety net: unknown text always reaches the agent, never blocked
        handler           = Handler.AGENT
        response_override = ""

    elif handler == Handler.BLOCK:
        # Only explicit protected actions reach here (HIGH_RISK intents).
        # Message is informative, not a raw ⛔.
        response_override = "פעולה זו אינה זמינה עבורך. לסיוע, פנה לאליהו."

    elif risk == Risk.NEEDS_APPROVAL and confidence < 0.85:
        # Low-confidence sensitive intent → ask for clarification
        handler           = Handler.CLARIFY
        response_override = f"לא בטוח שהבנתי — כוונתך: {intent}?"

    else:
        response_override = ""

    decision = RouteDecision(
        channel           = channel,
        intent            = intent,
        domain            = domain,
        risk              = risk,
        handler           = handler,
        needs_approval    = needs_approval,
        confidence        = confidence,
        matched_rule      = matched_rule,
        llm_classified    = False,
        response_override = response_override,
    )
    if tool_override:
        decision.matched_rule = f"{matched_rule} [tool:{tool_override}]"

    logger.info(decision.to_log())
    return decision
