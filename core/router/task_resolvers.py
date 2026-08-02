"""Bounded, side-effect-free task reference resolution."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from itertools import islice

from core.router.ownership_contracts import ResolverResult

TaskLookup = Callable[[str, str, int], Iterable[Mapping[str, object]]]


def resolve_task(
    query: str,
    lookup: TaskLookup,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Resolve a task to 0/1/multiple matches without choosing silently.

    The provider receives a bound and the resolver consumes at most one extra
    record, enough to distinguish one match from multiple matches.
    """
    query = str(query or "").strip()
    if not query:
        raise ValueError("query is required")
    if limit < 1:
        raise ValueError("limit must be positive")

    records = list(islice(lookup(query, scope, limit + 1), limit + 1))
    if not records:
        return ResolverResult("task", scope, 0, source=source, version=version, freshness=freshness)
    if len(records) != 1:
        return ResolverResult("task", scope, len(records), source=source, version=version, freshness=freshness)

    record = records[0]
    reference = str(record.get("record_id") or record.get("id") or "").strip()
    if not reference:
        return ResolverResult(
            "task", scope, 1, source=source, version=version, freshness=freshness,
            error="unique task match has no stable reference",
        )
    return ResolverResult(
        "task", scope, 1, stable_reference=reference, source=source,
        version=version, freshness=freshness,
    )
