"""Canonical identity-to-Profile resolution for linked Owner fields.

Resolution is STRICT: an identity maps to a Profile record only when exactly
one Profile row matches its ``user_id``. Zero matches, several matches, an
empty id, or a lookup failure all resolve to ``None`` — callers must treat
``None`` as "identity not resolved" and fail closed. The first of several
matches is never chosen (privacy foundation, PRIV-FCC-01 / P5).
"""

from __future__ import annotations

import logging

from airtable_schema import ProfileFields, Tables
from core.query_contract import equals
from tools.airtable_read_adapter import list_records

logger = logging.getLogger(__name__)

RESOLVED = "ok"
EMPTY_ID = "empty_id"
NOT_FOUND = "not_found"
AMBIGUOUS = "ambiguous"
LOOKUP_FAILED = "lookup_failed"

# One more than needed is enough to prove ambiguity without paging.
_AMBIGUITY_PROBE_LIMIT = 3


def resolve_profile_record_strict(user_id: str) -> tuple[str | None, str]:
    """Return ``(profile_record_id | None, reason)``; id only when reason == "ok"."""
    if not user_id or not str(user_id).strip():
        return None, EMPTY_ID
    try:
        records = list_records(
            Tables.PROFILE,
            equals(ProfileFields.NAME, user_id, case_insensitive=True),
            max_records=_AMBIGUITY_PROBE_LIMIT,
            paginate=False,
        )
    except Exception as exc:
        logger.warning("Profile resolution failed for %r: %s", user_id, exc)
        return None, LOOKUP_FAILED
    ids = [r.get("id") for r in records if r.get("id")]
    if not ids:
        return None, NOT_FOUND
    if len(ids) > 1:
        logger.warning(
            "Profile resolution ambiguous for %r: %d matching rows — failing closed",
            user_id, len(ids),
        )
        return None, AMBIGUOUS
    return ids[0], RESOLVED


def resolve_profile_record_id(user_id: str) -> str | None:
    """Resolve canonical ``identity.user_id`` to a Profile record ID (unique match only)."""
    return resolve_profile_record_strict(user_id)[0]
