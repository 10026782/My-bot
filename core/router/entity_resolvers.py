"""TC5 — bounded entity resolver framework.

Generalizes the bounded, side-effect-free resolution pattern TC3 proved for
tasks (`resolve_task`, still exported unchanged from
``core/router/task_resolvers.py``) to every entity kind named in
``docs/architecture/turn-coordinator-full/RESOLVER_MAP.md``: task, lead,
contact, deal, ActionContract, session, and callback.

One shared, bounded core (``_resolve_bounded_entity``) backs every entity
resolver so this module is the single resolver framework — there is no
per-entity copy of the bounded-read/0-1-many logic. task/lead/contact/deal
take an injected, caller-supplied ``lookup`` callable directly (identical
shape to TC3's ``TaskLookup``) since RESOLVER_MAP.md requires the same
"durable read" policy already precedented by the frozen task resolver.
action_contract/session/callback instead require an explicit, typed
``*LookupSource`` declaration (``ActionContractLookupSource``,
``SessionLookupSource``, ``CallbackLookupSource``) carrying that entity's
sharper RESOLVER_MAP.md source policy (durable-source, TTL-scoped,
durable-AC-first) — this module still never imports a concrete data source
(Airtable, ``ActionContractRepository``, ``session_store``, ``event_bus``),
so it cannot *prove* a lookup's provenance, but it structurally prevents a
resolver from being wired with an undeclared or wrongly-declared source: the
declaration is validated before any lookup runs. Wiring a resolver to a
real, bounded, identity-scoped read (as
``core/turn_coordinator_runtime.py::airtable_task_lookup`` already does for
tasks) is an integration seam outside TC5's scope.

Every resolver returns the frozen ``ResolverResult`` contract
(``core/router/ownership_contracts.py``) and never picks among multiple
matches — 0/1/many is always explicit, never silent.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ActionContractLookupSource:
    """An ActionContract lookup callable plus its required durable-source
    declaration (RESOLVER_MAP.md: "durable source").

    This does not import or couple to ``ActionContractRepository`` itself —
    that would be concrete runtime wiring outside TC5's scope. It requires
    whoever wires a resolver to make the source-policy declaration explicit
    and auditable in code, instead of any anonymous callable silently
    qualifying as canonical. ``ActionContractRepository`` remains the sole
    lifecycle authority; this is a read-only reference lookup only.
    """

    lookup: ActionContractLookup
    durable_source: bool = True

    def __post_init__(self) -> None:
        if not callable(self.lookup):
            raise TypeError("lookup must be callable")
        if not self.durable_source:
            raise ValueError(
                "ActionContract resolution requires durable_source=True — "
                "ActionContractRepository is the sole lifecycle authority; "
                "no legacy or cache source may resolve a canonical reference"
            )


@dataclass(frozen=True)
class SessionLookupSource:
    """A session lookup callable plus its required identity/chat scope + TTL
    declaration (RESOLVER_MAP.md: "identity/chat scope + TTL").

    ``ttl_seconds`` must be declared and positive. This does not enforce the
    TTL against the underlying store (no concrete ``session_store.py``
    coupling) — it forces an explicit, testable TTL declaration instead of
    an unscoped lookup.
    """

    lookup: SessionLookup
    ttl_seconds: int

    def __post_init__(self) -> None:
        if not callable(self.lookup):
            raise TypeError("lookup must be callable")
        if self.ttl_seconds <= 0:
            raise ValueError("session resolution requires a positive ttl_seconds")


@dataclass(frozen=True)
class CallbackLookupSource:
    """A callback lookup callable plus its required durable-AC-first
    declaration (RESOLVER_MAP.md: "callback payload -> exact AC ID, legacy
    pointer only as migration"; "durable AC first").

    A legacy-pointer lookup may only be used when explicitly declared as a
    migration path (``legacy_pointer_migration=True``) — it is never the
    silent default.
    """

    lookup: CallbackLookup
    ac_first: bool = True
    legacy_pointer_migration: bool = False

    def __post_init__(self) -> None:
        if not callable(self.lookup):
            raise TypeError("lookup must be callable")
        if not self.ac_first and not self.legacy_pointer_migration:
            raise ValueError(
                "callback resolution requires ac_first=True, or an explicit "
                "legacy_pointer_migration=True declaration"
            )


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
    lookup_source: ActionContractLookupSource,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded ActionContract reference resolution.

    Requires an explicit ``ActionContractLookupSource`` declaration instead
    of a bare callable, so a caller cannot silently supply a non-durable
    lookup for this entity kind. Read-only reference lookup only: this
    never creates, infers, repairs, or transitions a contract.
    ``ActionContractRepository`` remains the sole lifecycle authority; TC5
    does not move or duplicate it.
    """
    if not isinstance(lookup_source, ActionContractLookupSource):
        raise TypeError("resolve_action_contract requires an ActionContractLookupSource")
    return _resolve_bounded_entity(
        "action_contract", query, lookup_source.lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )


def resolve_session(
    query: str,
    lookup_source: SessionLookupSource,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded session-reference resolution (identity/chat scope + TTL).

    Requires an explicit ``SessionLookupSource`` declaration carrying a
    positive ``ttl_seconds`` instead of a bare callable.
    """
    if not isinstance(lookup_source, SessionLookupSource):
        raise TypeError("resolve_session requires a SessionLookupSource")
    return _resolve_bounded_entity(
        "session", query, lookup_source.lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )


def resolve_callback(
    query: str,
    lookup_source: CallbackLookupSource,
    *,
    scope: str,
    limit: int = 5,
    source: str = "",
    version: str = "",
    freshness: str = "",
) -> ResolverResult:
    """Bounded callback-reference resolution.

    Requires an explicit ``CallbackLookupSource`` declaration instead of a
    bare callable, so a caller cannot silently supply a legacy-pointer
    lookup without declaring it as a migration path. Resolves a callback
    payload to an exact ActionContract reference (or a stale/invalid/
    ambiguous outcome) — never a legacy pointer guess and never a silent
    pick among multiple candidates.
    """
    if not isinstance(lookup_source, CallbackLookupSource):
        raise TypeError("resolve_callback requires a CallbackLookupSource")
    return _resolve_bounded_entity(
        "callback", query, lookup_source.lookup, scope=scope, limit=limit,
        source=source, version=version, freshness=freshness,
    )
