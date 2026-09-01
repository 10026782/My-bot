"""Canonical identity-to-Profile resolution for linked Owner fields."""

from __future__ import annotations

import logging

from airtable_schema import ProfileFields, Tables
from core.query_contract import equals
from tools.airtable_read_adapter import list_records

logger = logging.getLogger(__name__)


def resolve_profile_record_id(user_id: str) -> str | None:
    """Resolve canonical ``identity.user_id`` to a Profile record ID."""
    if not user_id:
        return None
    try:
        records = list_records(
            Tables.PROFILE,
            equals(ProfileFields.NAME, user_id, case_insensitive=True),
            max_records=5,
            paginate=False,
        )
    except Exception as exc:
        logger.warning("Profile resolution failed for %r: %s", user_id, exc)
        return None
    return records[0].get("id") if records and records[0].get("id") else None
