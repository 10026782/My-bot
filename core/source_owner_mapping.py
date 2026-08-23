"""Shared authoritative mapping from inbound source accounts to Owner IDs.

This module resolves only canonical ``owner_user_id`` values. Profile record
resolution belongs exclusively to ``core.lead_service.create_lead()``.
"""

from __future__ import annotations

from enum import Enum


class OwnerMappingSource(str, Enum):
    WHATSAPP_DESTINATION = "whatsapp_destination"
    EMAIL_RECIPIENT = "email_recipient"
    VOICE_DESTINATION = "voice_destination"


def _normalize(source: OwnerMappingSource, identifier: str) -> str:
    value = (identifier or "").strip()
    if source is OwnerMappingSource.EMAIL_RECIPIENT:
        return value.lower()
    if source is OwnerMappingSource.WHATSAPP_DESTINATION:
        return f"whatsapp:{value.removeprefix('whatsapp:')}"
    return value.removeprefix("tel:")


def resolve_owner_user_id(
    source: OwnerMappingSource,
    identifier: str,
    *,
    mappings: dict[str, dict[str, str]] | None = None,
) -> str | None:
    """Return the configured canonical Owner user ID, or ``None``.

    Source namespaces are deliberately isolated: a WhatsApp destination
    cannot resolve through an email or voice mapping.
    """
    if not identifier:
        return None
    if mappings is None:
        from config import OWNER_USER_ID_MAPPINGS
        mappings = OWNER_USER_ID_MAPPINGS
    owner_user_id = mappings.get(source.value, {}).get(_normalize(source, identifier), "")
    return owner_user_id.strip() or None


def resolve_furniture_owner_user_id(
    whatsapp_destination: str,
    *,
    mappings: dict[str, dict[str, str]] | None = None,
) -> str | None:
    """Furniture uses the WhatsApp destination-account mapping verbatim."""
    return resolve_owner_user_id(
        OwnerMappingSource.WHATSAPP_DESTINATION,
        whatsapp_destination,
        mappings=mappings,
    )


def carried_owner_user_id(value: str) -> str | None:
    """Validate explicit LeadMemory owner context without inventing one."""
    owner_user_id = (value or "").strip()
    return owner_user_id or None
