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

from __future__ import annotations

from core.ingress_classifier import IngressClassification, classify_ingress, log_classification

# LCH only auto-writes / needs-review on tier 1-3; tier 4 (export/table/log)
# and tier 5 (no signal) always fall through to the agent. Collapsing those
# to None here keeps "capture_tier is not None" a meaningful signal for any
# future reader, without implying it gates LCH's own invocation.
_WRITE_WORTHY_TIERS = (1, 2, 3)


def classify_capture_ic(text: str, chat_id: str = "") -> IngressClassification:
    """
    text -> full IngressClassification.

    Single classify_ingress() call for a given inbound message — used by
    classify_capture() below (observability tier) AND by router.py's Tier-4
    stop-gate AND (via RouteDecision.capture_ic) reused by
    core.lead_candidate_handler.handle_lead_candidate() instead of a second,
    independent classify_ingress() call (BUG-056 double-classification fix).
    """
    ic = classify_ingress(text, source_type="text")
    log_classification(ic, chat_id=chat_id)
    return ic


def classify_capture(text: str, chat_id: str = "") -> tuple[int | None, str, str]:
    """
    text -> (capture_tier, capture_reason, raw_ref).

    capture_tier is 1/2/3 only when classify_ingress() sees a write-worthy
    lead-capture candidate, else None. Pure w.r.t. side effects other than
    the existing log_classification() log line (unchanged from C89).
    """
    ic = classify_capture_ic(text, chat_id=chat_id)
    tier = ic.tier if ic.tier in _WRITE_WORTHY_TIERS else None
    return tier, ic.reason, ic.raw_ref
