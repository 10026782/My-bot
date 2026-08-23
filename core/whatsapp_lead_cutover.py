"""WhatsApp-only bridge into the canonical Lead creation service."""

from __future__ import annotations

from core.lead_service import (
    CANONICAL_LEAD_DOMAINS,
    LeadCreateResult,
    LeadPayload,
    create_lead,
)
from core.source_owner_mapping import OwnerMappingSource, resolve_owner_user_id


def create_whatsapp_inbound_lead(
    identity,
    message: str,
    destination: str,
    domain: str,
) -> LeadCreateResult:
    """Resolve account ownership and delegate the write exactly once.

    Missing account ownership or unsupported domains fail closed before the
    canonical service is called. This function has no legacy fallback.
    """
    owner_user_id = resolve_owner_user_id(
        OwnerMappingSource.WHATSAPP_DESTINATION,
        destination,
    )
    if not owner_user_id:
        return LeadCreateResult(
            ok=False,
            action="blocked",
            reason="whatsapp destination owner mapping missing",
        )
    if domain not in CANONICAL_LEAD_DOMAINS:
        return LeadCreateResult(
            ok=False,
            action="invalid",
            reason=f"unsupported WhatsApp Lead domain: {domain!r}",
        )

    sender = getattr(identity, "external_id", "") or ""
    payload = LeadPayload(
        name=getattr(identity, "display_name", "") or sender,
        phone=sender,
        domain=domain,
        owner_user_id=owner_user_id,
        source="whatsapp_inbound",
        channel="whatsapp",
        summary=(message or "")[:500],
        tenant_id=getattr(identity, "tenant_id", "boss_hq") or "boss_hq",
    )
    return create_lead(
        identity,
        payload,
        source_module="whatsapp_ingress_canonical",
    )
