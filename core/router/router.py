# core/router/router.py — CORE_02 Soft Router
# Orchestrator only. Calls 4 sub-routers → returns one RouteDecision.
# No business logic. No DB writes. No agent calls.

from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING

from .route_decision  import RouteDecision, Intent, Handler, Risk, RouterDomain
from .channel_router  import detect_channel, resolve_tool_for_channel
from .intent_router   import detect_intent, count_engineering_markers, detect_ambiguous_phrase
from .domain_router   import detect_domain
from .risk_router     import detect_risk

if TYPE_CHECKING:
    from identity import Identity

logger = logging.getLogger(__name__)

INTENT_CONFIDENCE_THRESHOLD = 0.75

_STRUCTURED_CREATE_TASK_RE = re.compile(
    r"^\s*(?:צור|תיצור)\s+משימה\s*:?\s*(?P<title>.+?)\s*$"
)


def deterministic_create_task_title(text: str) -> str | None:
    """מחזיר את כותרת המשימה עבור פקודת יצירה חד-משמעית ומצומצמת."""
    match = _STRUCTURED_CREATE_TASK_RE.fullmatch(text or "")
    return match.group("title").strip() if match else None


def route_request(
    text:                str,
    channel_raw:         str,
    identity:            "Identity",
    domain_from_channel: str = "",
    envelope_id:         str = "",
) -> RouteDecision:
    """
    text + channel + identity → RouteDecision

    domain_from_channel: comes from config.get_domain(to_number) in webhook.
    envelope_id: C94 Stage ג — the caller's IngressEnvelope id, if it built
    one (currently only Telegram, via app.py/core/telegram_ingress_adapter.py).
    Optional/"" for any other caller — forwarded to capture_router so a
    classify_ingress() failure's EvidenceTrace can link back to its Envelope.
    """
    # 1. Channel
    channel = detect_channel(channel_raw)

    # 2. Intent
    intent, confidence, matched_rule = detect_intent(text)
    if confidence < INTENT_CONFIDENCE_THRESHOLD:
        intent = Intent.UNKNOWN

    # 2b. Engineering / meta-safety override (SPEC-ROUTER-06).
    # Runs AFTER business-intent detection but takes priority over it: a
    # bug report from staff/owner must never be treated as a business
    # action just because it incidentally contains words like "עדכן ליד" —
    # and must not silently fall through to the general Agent via
    # intent=unknown either (BUG-NEW-11b regression: that path was observed
    # live querying Leads on an engineering message).
    marker_count = count_engineering_markers(text)
    is_staff = identity.role in (
        "owner", "partner", "manager", "employee",
    )
    if is_staff and marker_count >= 2:
        intent = Intent.ENGINEERING_NOTE

    # 3. Domain
    if intent == Intent.ENGINEERING_NOTE:
        domain = RouterDomain.INTERNAL
    else:
        domain, _ = detect_domain(
            text                 = text,
            domain_from_channel  = domain_from_channel,
            domain_from_identity = identity.domain_id,
        )

    # 4. Risk + Handler
    if intent == Intent.ENGINEERING_NOTE:
        risk, handler, needs_approval = Risk.READ_ONLY, Handler.ENGINEERING_NOTE, False
    else:
        risk, handler, needs_approval = detect_risk(
            intent = intent,
            role   = identity.role,
            domain = domain,
        )

    # פקודות משימה מובנות שלמות מספיקות ל-Coordinator כדי לבנות contract אישור.
    # ניסוחים רחבים יותר נשארים במסלול Agent; זהו שער דטרמיניסטי ומצומצם בכוונה.
    if (
        intent == Intent.CREATE_TASK
        and deterministic_create_task_title(text) is not None
        and identity.role not in ("lead", "guest", "readonly")
    ):
        risk, handler, needs_approval = Risk.NEEDS_APPROVAL, Handler.TOOL, True

    # 4b. Capture Policy (Stage 3 / C89 integration) — observability only.
    # Gate is identity.is_internal alone, with NO intent filter — this must
    # match app.py's real invocation condition for handle_lead_candidate()
    # exactly, or RouteDecision would show capture_tier=None for messages
    # LCH still independently auto-writes (e.g. an explicit "תוסיף ליד: ..."
    # that intent_router already matched as CREATE_LEAD with high confidence
    # — LCH runs on it regardless of what intent detection decided).
    capture_tier, capture_reason, raw_ref = None, "", ""
    capture_ic = None
    if identity.is_internal:
        from .capture_router import classify_capture_ic, _WRITE_WORTHY_TIERS
        capture_ic = classify_capture_ic(
            text, chat_id=getattr(identity, "memory_key", ""), envelope_id=envelope_id,
        )
        # C94 Stage ג: capture_ic can now legitimately be None (classify_ingress()
        # itself failed, already logged + traced inside classify_capture_ic) —
        # same as the identity.is_internal=False case above, handled the same way.
        if capture_ic is not None:
            capture_tier = capture_ic.tier if capture_ic.tier in _WRITE_WORTHY_TIERS else None
            capture_reason = capture_ic.reason
            raw_ref = capture_ic.raw_ref

    # 5. Channel-specific tool override
    tool_override = resolve_tool_for_channel(intent, channel)

    # 6. Restricted flow resolution
    restricted   = False
    notify_owner = False
    tool_allowed = True

    if handler == Handler.RESTRICTED:
        # Agent talks naturally; tools are silently blocked; owner gets a log.
        restricted   = True
        notify_owner = True
        tool_allowed = False
        handler      = Handler.AGENT

    if handler == Handler.BLOCK:
        # Hard block (rate-limit / extreme case) — no tools.
        tool_allowed = False

    # 7. Edge cases / response overrides
    if intent == Intent.ENGINEERING_NOTE:
        handler           = Handler.ENGINEERING_NOTE
        tool_allowed       = False
        response_override = "קיבלתי דיווח באג. לא שיניתי את המערכת. צריך שינוי קוד, בדיקות ופריסה."

    elif capture_ic is not None and capture_ic.tier == 4:
        # BUG-056 (C89 Tier 4 stop-gate): table/export/log/bot-output pasted
        # in must stop routing HERE — never reach the Agent/tools, regardless
        # of what keyword (e.g. "הוסף משימה") intent_router happened to match
        # inside the pasted text. handle_lead_candidate() already refuses to
        # auto-write for tier>=4, but only this router-level override stops
        # the message from reaching Handler.AGENT at all.
        handler            = Handler.CLARIFY
        tool_allowed       = False
        response_override  = (
            "📄 זה נראה כמו טבלה/ייצוא/פלט מודבק — לא ביצעתי שום פעולה אוטומטית. "
            "אם התכוונת לבקש משהו ספציפי, כתוב את זה במשפט רגיל."
        )

    elif intent == Intent.UNKNOWN:
        # BUG-IC-01/C89: before falling through to the general Agent (which
        # has full tool access and might decide on its own to "check" Gmail/
        # Calendar/Airtable), check whether this is a known ambiguous short
        # phrase ("סטטוס", "בדיקות מערכת", "מה המצב", "למלא משימות"). Those
        # get a clarifying question instead of silent broad-tool guessing.
        _ambiguous_q = detect_ambiguous_phrase(text)
        if _ambiguous_q:
            handler            = Handler.CLARIFY
            response_override  = _ambiguous_q
        else:
            handler            = Handler.AGENT   # safety net
            response_override  = ""

    elif risk == Risk.NEEDS_APPROVAL and confidence < 0.85 and not restricted:
        handler           = Handler.CLARIFY
        response_override = f"לא בטוח שהבנתי — כוונתך: {intent}?"

    elif handler == Handler.BLOCK:
        response_override = "פעולה זו אינה זמינה. לסיוע, פנה לאליהו."

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
        restricted        = restricted,
        notify_owner      = notify_owner,
        tool_allowed      = tool_allowed,
        capture_tier      = capture_tier,
        capture_reason    = capture_reason,
        raw_ref           = raw_ref,
        capture_ic        = capture_ic,
    )
    if tool_override:
        decision.matched_rule = f"{matched_rule} [tool:{tool_override}]"

    logger.info(decision.to_log())
    return decision
