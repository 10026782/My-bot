# lead_deal_link.py — LEAD-DEAL-ASSOCIATION Model B: resolve-only helpers +
# deterministic NL/guided-flow triggers for /תקדםליד.
#
# No writes here — the only write (crm_link_lead_to_deal) happens through
# ActionGateway/tools.dispatcher.dispatch_tool(), via app.py's
# _queue_deterministic_link_lead_to_deal(). Mirrors lead_conversion.py's own
# resolve-only/writer-separation contract (see that file's module docstring)
# and reuses its shared Lead lookup helper rather than a second copy.
#
# Both regex triggers below are exact structural parses, not fuzzy/AI intent
# detection — same discipline every other deterministic parser in this
# codebase follows (see core/router/router.py's parse_deterministic_create_
# deal). Text that doesn't match either shape falls through unchanged to
# normal routing; a caller that gates on these functions therefore cannot
# regress any existing flow for non-matching text.

from __future__ import annotations

import re

from airtable_schema import DealFields

FLAG = "LEAD_DEAL_LINK"

_PROMOTE_TRIGGER_RE = re.compile(r"^\s*(?:ל)?תקדם\s+ליד\s*$")
_DIRECT_LINK_RE = re.compile(
    r"^\s*קדם\s+את\s+(?P<lead>.+?)\s+לעסק(?:ה|ת)\s+(?P<deal>.+?)\s*$"
)


def is_promote_lead_trigger(text: str) -> bool:
    """True for the bare guided-flow trigger ("תקדם ליד" / "לתקדם ליד")
    only — never for the direct one-shot form, which carries names and is
    matched by parse_direct_link_text() instead. Callers must check
    parse_direct_link_text() first so a direct-form message is never
    mistaken for the bare trigger."""
    return bool(_PROMOTE_TRIGGER_RE.match(str(text or "")))


def parse_direct_link_text(text: str) -> tuple[str, str] | None:
    """Extract (lead_query, deal_query) from the one-shot NL form
    ("קדם את <שם ליד> לעסקת <שם עסקה>"), or None if the text doesn't
    match that exact shape."""
    match = _DIRECT_LINK_RE.match(str(text or ""))
    if not match:
        return None
    lead_query = match.group("lead").strip()
    deal_query = match.group("deal").strip()
    if not lead_query or not deal_query:
        return None
    return lead_query, deal_query


def resolve_lead_by_query(query: str) -> tuple[dict | None, str]:
    """Resolve exactly one Lead by name/phone, or an error message.
    Reuses lead_conversion.py's shared lookup helper — never a second
    copy of that search logic (same reasoning resolve_lead_for_deal()
    already documents for the Origin Lead flow)."""
    from lead_conversion import _resolve_single_lead_by_query
    return _resolve_single_lead_by_query(query)


def resolve_deal_by_query(query: str, identity) -> tuple[dict | None, str]:
    """Resolve exactly one Deal by name, or an error message. Uses the
    same bounded exact-label lookup the Commercial Completion presentation
    adapter uses for every other human-typed entity reference
    (commercial_crm.lookup_human_reference) — never a raw, unscoped table
    scan."""
    if not str(query or "").strip():
        return None, "❌ חסר שם עסקה לחיפוש."
    from commercial_crm import lookup_human_reference
    matches = lookup_human_reference(
        "deal", query, scope=str(getattr(identity, "user_id", "") or ""),
        identity=identity, limit=6,
    )
    if not matches:
        return None, f"🔍 לא נמצאה עסקה התואמת '{query}'."
    if len(matches) > 1:
        names = ", ".join(
            m.get("fields", {}).get(DealFields.NAME, "?") for m in matches
        )
        return None, f"⚠️ נמצאו כמה עסקאות תואמות: {names}.\nנסה שם מדויק יותר."
    return matches[0], ""
