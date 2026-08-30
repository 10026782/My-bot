#!/usr/bin/env python3
"""Shared deterministic Decision Hub title matching.

The public matcher accepts explicit candidates for channel-independent use. The
default Airtable loader is kept behind a separate function so a future storage
adapter can replace it without changing the scoring logic.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from airtable_schema import DecisionFields, DecisionStatus, Tables
from core.query_contract import all_of, any_of, equals
from tma_api import record_fields

logger = logging.getLogger(__name__)

OPEN_STATUSES = (DecisionStatus.OPEN, DecisionStatus.PENDING_INPUT)
DECISION_ALLOWED_ROLES = ("owner", "manager", "partner")


def has_decision_capability(identity) -> bool:
    return bool(identity and (getattr(identity, "is_owner", False) or getattr(identity, "role", None) in DECISION_ALLOWED_ROLES))


def decision_in_scope(decision: dict | None, identity) -> bool:
    if not has_decision_capability(identity) or not decision:
        return False
    fields = record_fields(decision) or {}
    return fields.get(DecisionFields.TENANT_ID) == getattr(identity, "tenant_id", None) and identity.can_access_domain(fields.get(DecisionFields.DOMAIN, ""))


def _scoped_open_query(identity):
    if not has_decision_capability(identity):
        return None
    query = all_of(
        any_of(*(equals(DecisionFields.STATUS, status) for status in OPEN_STATUSES)),
        equals(DecisionFields.TENANT_ID, identity.tenant_id),
    )
    if getattr(identity, "role", None) == "partner":
        domains = tuple(getattr(identity, "allowed_domains", ()) or ())
        if not domains:
            return None
        query = all_of(query, any_of(*(equals(DecisionFields.DOMAIN, domain) for domain in domains)))
    return query


def normalize_text(text: str) -> str:
    """Normalize text for deterministic title matching."""
    return re.sub(r"[^\w\s]", "", text or "").strip().lower()


def find_matching_decision(
    text: str,
    decisions: Iterable[dict] | None = None,
    identity=None,
) -> tuple[dict | None, float]:
    """Return the best title match and score, loading open decisions if omitted."""
    candidates = list(decisions) if decisions is not None else list_open_decisions(identity=identity)
    if identity is not None:
        candidates = [candidate for candidate in candidates if decision_in_scope(candidate, identity)]
    if not candidates or not text:
        return None, 0.0

    normalized_text = normalize_text(text)
    text_words = set(normalized_text.split())
    best, best_score = None, 0.0
    for decision in candidates:
        title = record_fields(decision).get(DecisionFields.TITLE, "")
        normalized_title = normalize_text(title)
        if not normalized_title:
            continue
        if normalized_title in normalized_text:
            return decision, 100.0
        title_words = set(normalized_title.split())
        overlap = len(text_words & title_words) / len(title_words) * 100
        if overlap > best_score:
            best, best_score = decision, overlap

    return best, best_score


def list_open_decisions(limit: int = 5, identity=None) -> list[dict]:
    """Load open matching candidates through the current Airtable read boundary."""
    query = _scoped_open_query(identity)
    if query is None:
        return []
    try:
        from tools.airtable_read_adapter import AirtableReadError, list_records
        return list_records(
            Tables.DECISIONS,
            query,
            limit=None,
            paginate=False,
            timeout=10,
        )[:limit]
    except AirtableReadError as exc:
        if exc.status_code is not None:
            logger.warning("[DecisionMatching] list_open_decisions -> %s", exc.status_code)
        else:
            logger.warning("[DecisionMatching] list_open_decisions error: %s", exc.cause or exc)
    except Exception as exc:
        logger.warning("[DecisionMatching] list_open_decisions error: %s", exc)
    return []
