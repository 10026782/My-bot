# core/lead_event_writer.py — BUG-104 TMA Lead Event Bridge
#
# Best-effort Lead Events writer for TMA-originated Lead mutations
# (status/outcome/field patches). Deliberately does NOT reuse
# capture_lead_event() — that function is gated by LEAD_CAPTURE and runs
# inbound-message inference (junk filtering, event_type-from-message-text)
# meant for free-text chat, neither of which applies to a structured TMA
# field change. Must only be called after the Leads write it documents has
# already succeeded — never before, never on failure.

from __future__ import annotations

import logging

from domain_utils import normalize_business_domain

logger = logging.getLogger(__name__)

_FALLBACK_DOMAIN = "general"


def _normalize_domain(raw: str | None) -> str:
    if not raw or not isinstance(raw, str):
        return _FALLBACK_DOMAIN
    return normalize_business_domain(raw) or _FALLBACK_DOMAIN


def _resolve_domain(lead_id: str, lead_domain: str | None) -> str:
    """
    lead_domain, if given, is normalized and used directly (no extra read).
    Otherwise, read the Lead record's own `domain` field once, after the
    caller's Leads write has already succeeded.
    """
    if lead_domain is not None:
        return _normalize_domain(lead_domain)

    try:
        from airtable_schema import LeadFields
        from tools.airtable_read_adapter import list_records

        safe_id = lead_id.replace("'", "")
        records = list_records(
            "Leads", f"RECORD_ID()='{safe_id}'", max_records=1, paginate=False,
        )
        if records:
            raw = records[0].get("fields", {}).get(LeadFields.DOMAIN)
            return _normalize_domain(raw)
    except Exception as e:
        logger.warning(
            "[LeadEventWriter] domain lookup failed for lead=%s: %s", lead_id, e,
        )
    return _FALLBACK_DOMAIN


def _serialize_applied_fields(applied_fields: dict) -> str:
    """
    Deterministic text representation — sorted keys, repr'd values. Never
    claims an old->new transition: we were not given the prior value, so we
    only state what was applied, not what changed from.
    """
    if not applied_fields:
        return ""
    parts = [f"{key}={applied_fields[key]!r}" for key in sorted(applied_fields.keys())]
    return ", ".join(parts)


def write_tma_lead_event(
    lead_id: str,
    action: str,
    applied_fields: dict,
    lead_domain: str | None = None,
) -> bool:
    """
    Best-effort Lead Event for a TMA-originated Lead mutation.

    Preconditions (enforced by every call site, not by this function):
      - the Leads write this event documents has already succeeded.

    Contract:
      - never raises — any failure is logged and this returns False.
      - a False return must never turn an already-successful Lead write
        into a reported failure for the HTTP caller.
      - not gated by LEAD_CAPTURE or any feature flag.
      - performs at most one extra Airtable read (Leads domain lookup,
        only when lead_domain is not supplied) and exactly one Airtable
        write attempt — no internal retry.
    """
    try:
        from airtable_schema import LeadEventFields, LeadEventType, Tables
        from tools.airtable_gateway import airtable_create

        domain = _resolve_domain(lead_id, lead_domain)
        applied_repr = _serialize_applied_fields(applied_fields or {})
        summary = f"TMA {action}"
        message = f"{action}: {applied_repr}" if applied_repr else action

        fields = {
            LeadEventFields.NAME:       f"tma:{action}:{lead_id}",
            LeadEventFields.LEAD_LINK:  [lead_id],
            LeadEventFields.EVENT_TYPE: LeadEventType.OTHER,
            LeadEventFields.DOMAIN:     domain,
            LeadEventFields.MESSAGE:    message[:5000],
            LeadEventFields.SUMMARY:    summary[:200],
            LeadEventFields.CHANNEL:    "tma",
        }

        rec = airtable_create(Tables.LEAD_EVENTS, fields, source="tma_lead_event")
        if not rec:
            logger.warning(
                "[LeadEventWriter] create failed: lead=%s action=%s", lead_id, action,
            )
            return False

        logger.info(
            "[LeadEventWriter] created event: lead=%s event_id=%s action=%s domain=%s",
            lead_id, rec.get("id", ""), action, domain,
        )
        return True

    except Exception as e:
        logger.error(
            "[LeadEventWriter] write_tma_lead_event error for lead=%s action=%s: %s",
            lead_id, action, e,
        )
        return False
