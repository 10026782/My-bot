"""TC5 — bounded entity resolver framework.

Generalizes the bounded, side-effect-free resolution pattern TC3 proved for
tasks (`resolve_task`, still exported unchanged from
``core/router/task_resolvers.py``) to every entity kind named in
``docs/architecture/turn-coordinator-full/RESOLVER_MAP.md``: task, lead,
contact, deal, ActionContract, session, and callback.

One shared, bounded core (``_resolve_bounded_entity``) backs every entity
resolver so this module is the single resolver framework — there is no
per-entity copy of the bounded-read/0-1-many logic. Each resolver takes an
injected, caller-supplied ``lookup`` callable (identical shape to TC3's
``TaskLookup``): this module never imports a concrete data source (Airtable,
``ActionContractRepository``, ``session_store``, ``event_bus``), so it makes
no write, owns no approval/reply authority, and creates no new source of
truth. Wiring a resolver to a real, bounded, identity-scoped read (as
``core/turn_coordinator_runtime.py::airtable_task_lookup`` already does for
tasks) is an integration seam outside TC5's scope.

Every resolver returns the frozen ``ResolverResult`` contract
(``core/router/ownership_contracts.py``) and never picks among multiple
matches — 0/1/many is always explicit, never silent.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from itertools import islice

from core.router.ownership_contracts import ResolverResult

EntityLookup = Callable[[str, str, int], Iterable[Mapping[str, object]]]

TaskLookup = EntityLookup
LeadLookup = EntityLookup
ContactLookup = EntityLookup
DealLookup = EntityLookup
ActionContractLookup = EntityLookup
SessionLookup = EntityLookup
CallbackLookup = EntityLookup


def _resolve_bounded_entity(
    entity_kind: str,
    query: str,
    lookup: EntityLookup,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Resolve one entity kind to 0/1/multiple matches without choosing silently.

    Fails closed before any lookup runs when the identity/tenant scope or the
    query is missing, or when the bound is not positive. The provider
    receives a bound of ``limit + 1`` and the resolver consumes at most that
    many records — enough to distinguish one match from multiple, never a
    full-table scan.
    """
    if not scope or not str(scope).strip():
        raise ValueError("scope is required")
    query = str(query or "").strip()
    if not query:
        raise ValueError("query is required")
    if limit < 1:
        raise ValueError("limit must be positive")

    records = list(islice(lookup(query, scope, limit + 1), limit + 1))
    if not records:
        return ResolverResult(entity_kind, scope, 0, source=source, version=version, freshness=freshness)
    if len(records) != 1:
        return ResolverResult(entity_kind, scope, len(records), source=source, version=version, freshness=freshness)

    record = records[0]
    reference = str(record.get("record_id") or record.get("id") or "").strip()
    if not reference:
        return ResolverResult(
            entity_kind, scope, 1, source=source, version=version, freshness=freshness,
            error=f"unique {entity_kind} match has no stable reference",
        )
    return ResolverResult(
        entity_kind, scope, 1, stable_reference=reference, source=source,
        version=version, freshness=freshness,
    )


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
    """Bounded task reference resolution — the TC3 behavior, unchanged."""
    return _resolve_bounded_entity(
        "task", query, lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )


def resolve_lead(
    query: str,
    lookup: LeadLookup,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded lead reference resolution."""
    return _resolve_bounded_entity(
        "lead", query, lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )


def resolve_contact(
    query: str,
    lookup: ContactLookup,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded contact reference resolution.

    Distinct from ``tools/contact_resolver.py``'s fuzzy free-text name
    matcher, which is an unbounded, non-identity-scoped NLP disambiguation
    helper for a different purpose and is left untouched by TC5.
    """
    return _resolve_bounded_entity(
        "contact", query, lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )


def resolve_deal(
    query: str,
    lookup: DealLookup,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded deal reference resolution."""
    return _resolve_bounded_entity(
        "deal", query, lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )


def resolve_action_contract(
    query: str,
    lookup: ActionContractLookup,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded ActionContract reference resolution.

    Read-only reference lookup only: this never creates, infers, repairs, or
    transitions a contract. ``ActionContractRepository`` remains the sole
    lifecycle authority; TC5 does not move or duplicate it.
    """
    return _resolve_bounded_entity(
        "action_contract", query, lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )


def resolve_session(
    query: str,
    lookup: SessionLookup,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded session-reference resolution (identity/chat scope + TTL)."""
    return _resolve_bounded_entity(
        "session", query, lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )


def resolve_callback(
    query: str,
    lookup: CallbackLookup,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded callback-reference resolution.

    Resolves a callback payload to an exact ActionContract reference (or a
    stale/invalid/ambiguous outcome) — never a legacy pointer guess and never
    a silent pick among multiple candidates.
    """
    return _resolve_bounded_entity(
        "callback", query, lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )
