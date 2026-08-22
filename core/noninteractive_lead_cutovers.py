"""Canonical bridges for non-interactive Lead writers."""

from __future__ import annotations

from core.lead_service import LeadCreateResult, LeadPayload, create_lead
from core.source_owner_mapping import (
    OwnerMappingSource,
    resolve_furniture_owner_user_id,
    resolve_owner_user_id,
)


def create_email_inbound_lead(sender: str, recipient: str, name: str, message: str, domain: str, external_id: str = "") -> LeadCreateResult:
    owner_user_id = resolve_owner_user_id(OwnerMappingSource.EMAIL_RECIPIENT, recipient)
    if not owner_user_id:
        return LeadCreateResult(ok=False, action="blocked", reason="email recipient owner mapping missing")
    from identity import resolve_identity
    identity = resolve_identity("email", sender)
    return create_lead(identity, LeadPayload(
        name=name or sender, phone=sender, domain=domain, owner_user_id=owner_user_id,
        source="email_inbound", channel="email", summary=(message or "")[:500],
        tenant_id=getattr(identity, "tenant_id", "boss_hq") or "boss_hq",
    ), source_module="email_inbound_canonical")


def create_furniture_inbound_lead(sender: str, destination: str, name: str, summary: str, answers: str) -> LeadCreateResult:
    owner_user_id = resolve_furniture_owner_user_id(destination)
    if not owner_user_id:
        return LeadCreateResult(ok=False, action="blocked", reason="furniture WhatsApp owner mapping missing")
    from identity import resolve_identity
    identity = resolve_identity("whatsapp", sender)
    return create_lead(identity, LeadPayload(
        name=name or sender, phone=sender, domain="furniture_import", owner_user_id=owner_user_id,
        source="twilio_whatsapp_furniture_funnel", channel="whatsapp",
        summary=f"{summary}\n{answers}"[:500], tenant_id=getattr(identity, "tenant_id", "boss_hq") or "boss_hq",
    ), source_module="furniture_funnel_canonical")


def create_voice_inbound_lead(session, destination: str) -> LeadCreateResult:
    owner_user_id = resolve_owner_user_id(OwnerMappingSource.VOICE_DESTINATION, destination)
    if not owner_user_id:
        return LeadCreateResult(ok=False, action="blocked", reason="voice destination owner mapping missing")
    from identity import resolve_identity
    identity = resolve_identity("voice", session.from_num)
    answers = "\n".join(f"{key}: {value}" for key, value in session.answers.items())
    return create_lead(identity, LeadPayload(
        name=session.answers.get("name", session.from_num), phone=session.from_num,
        domain=session.domain or "general", owner_user_id=owner_user_id,
        source="voice_ivr", channel="voice", summary=f"📞 ליד קולי — IVR\n{answers}"[:500],
        tenant_id=getattr(identity, "tenant_id", "boss_hq") or "boss_hq",
    ), source_module="voice_ivr_canonical")
