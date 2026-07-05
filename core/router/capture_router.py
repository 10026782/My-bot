# core/router/capture_router.py — Stage 3 Capture Policy: Router-integrated
# capture classification (SPEC 1, discovery-corrected version).
#
# Thin wrapper around core.ingress_classifier.classify_ingress() — the
# existing, already-pure single entry point for input classification (C89).
# Does NOT reimplement extraction/tier logic (no duplicate regex machinery)
# and does NOT gate whether core.lead_candidate_handler.handle_lead_candidate()
# runs — it only surfaces the same classification onto RouteDecision so the
# Router's own audit trail (decision.to_log()) sees "this looked like a
# capture candidate" instead of showing nothing for messages LCH still acts
# on independently.
#
# No airtable/drive/gateway imports — classification only. Execution stays
# entirely in core/lead_candidate_handler.py, unchanged.
#
# C94 Stage ג: classify_ingress() is now wrapped in try/except. Previously an
# exception here propagated all the way up through router.route_request()
# into app.py's _safe_route(), whose blanket catch fails the ENTIRE router
# closed (Handler.APPROVAL, intent=UNKNOWN) regardless of intent/domain/risk
# — a capture-classification hiccup shouldn't force approval-gating on an
# otherwise-fine request. capture_ic is observability-only (see docstrings
# below); every existing caller already handles capture_ic=None gracefully
# (identity.is_internal=False produces exactly that today). On failure this
# now returns None instead of raising, and records an EvidenceTrace with a
# sanitized classification_error (type(exc).__name__ only — never
# str(exc)/exc_info=True, which could leak message text/PII through a log or
# traceback; same discipline as C94 Stage ב's file adapter fix).
# _safe_route()'s own blanket try/except is UNCHANGED — it still catches
# every OTHER kind of router failure exactly as before. This narrows
# fail-closed only at this one call site, not the router's general safety net.

from __future__ import annotations

import logging

from core.ingress_classifier import IngressClassification, classify_ingress, log_classification
from core.ingress_envelope import EvidenceTrace

logger = logging.getLogger(__name__)

# LCH only auto-writes / needs-review on tier 1-3; tier 4 (export/table/log)
# and tier 5 (no signal) always fall through to the agent. Collapsing those
# to None here keeps "capture_tier is not None" a meaningful signal for any
# future reader, without implying it gates LCH's own invocation.
_WRITE_WORTHY_TIERS = (1, 2, 3)


def classify_capture_ic(text: str, chat_id: str = "", envelope_id: str = "") -> IngressClassification | None:
    """
    text -> full IngressClassification, or None if classify_ingress() itself failed.

    Single classify_ingress() call for a given inbound message — used by
    classify_capture() below (observability tier) AND by router.py's Tier-4
    stop-gate AND (via RouteDecision.capture_ic) reused by
    core.lead_candidate_handler.handle_lead_candidate() instead of a second,
    independent classify_ingress() call (BUG-056 double-classification fix).

    envelope_id: C94 Stage ג — the IngressEnvelope this text belongs to, if
    the caller built one (currently only Telegram, via
    core/telegram_ingress_adapter.py). Optional/"" for any other caller —
    the exception-safety fix below applies regardless, but the EvidenceTrace
    is only recorded when an envelope_id is available to link it to.
    """
    try:
        ic = classify_ingress(text, source_type="text")
    except Exception as exc:
        logger.error(
            "[C94] classify_ingress error text_capture chat=%s envelope_id=%s error_type=%s",
            chat_id, envelope_id or "n/a", type(exc).__name__,
        )
        if envelope_id:
            trace = EvidenceTrace(envelope_id=envelope_id)
            trace.record_classification(classification_error=type(exc).__name__)
            logger.debug("[C94] row trace: envelope_id=%s status=%s", envelope_id, trace.status)
        return None

    log_classification(ic, chat_id=chat_id)
    if envelope_id:
        trace = EvidenceTrace(envelope_id=envelope_id)
        trace.record_classification(
            classification_result={"tier": ic.tier, "confidence": ic.confidence, "reason": ic.reason},
            raw_ref=ic.raw_ref,
        )
        logger.debug("[C94] row trace: envelope_id=%s tier=%s raw_ref=%s", envelope_id, ic.tier, trace.raw_ref)
    return ic


def classify_capture(text: str, chat_id: str = "", envelope_id: str = "") -> tuple[int | None, str, str]:
    """
    text -> (capture_tier, capture_reason, raw_ref).

    capture_tier is 1/2/3 only when classify_ingress() sees a write-worthy
    lead-capture candidate, else None — including when classify_capture_ic()
    itself failed (treated the same as "no signal", not an error state here).
    Pure w.r.t. side effects other than the existing log_classification() log
    line (unchanged from C89) and, when envelope_id is given, an EvidenceTrace.
    """
    ic = classify_capture_ic(text, chat_id=chat_id, envelope_id=envelope_id)
    if ic is None:
        return None, "", ""
    tier = ic.tier if ic.tier in _WRITE_WORTHY_TIERS else None
    return tier, ic.reason, ic.raw_ref
