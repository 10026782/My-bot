"""TC5 verification: bounded entity resolver framework.

Covers 0/1/many outcomes, bounded consumption, identity-scope isolation,
fail-closed behavior on missing scope, determinism, the absence of any
mutation/write or second resolver implementation, and (review follow-up on
PR #562, twice) that action_contract/session/callback structurally require
an explicit, entity-specific source-policy declaration instead of accepting
any generic lookup callable — and that the declaration itself has no
policy-granting default, so merely instantiating the wrapper class cannot
silently create a canonical/durable lookup source — across every entity kind
named in docs/architecture/turn-coordinator-full/RESOLVER_MAP.md.
"""

import ast
import inspect

import pytest

from core.router.entity_resolvers import (
    ActionContractLookupSource,
    CallbackLookupSource,
    SessionLookupSource,
    resolve_action_contract,
    resolve_callback,
    resolve_contact,
    resolve_deal,
    resolve_lead,
    resolve_session,
    resolve_task,
)
from core.router.ownership_contracts import ResolverResult

ALL_RESOLVERS = {
    "task": resolve_task,
    "lead": resolve_lead,
    "contact": resolve_contact,
    "deal": resolve_deal,
    "action_contract": resolve_action_contract,
    "session": resolve_session,
    "callback": resolve_callback,
}

# task/lead/contact/deal require RESOLVER_MAP.md's plain "durable read"
# policy, already precedented by the frozen TC3 task resolver -- they take a
# bare lookup callable directly. action_contract/session/callback carry a
# sharper, entity-specific source policy (durable-source, TTL-scoped,
# durable-AC-first) and require an explicit typed *LookupSource wrapper.
POLICY_WRAPPERS = {
    "action_contract": lambda lookup: ActionContractLookupSource(lookup, durable_source=True),
    "session": lambda lookup: SessionLookupSource(lookup, ttl_seconds=1800),
    "callback": lambda lookup: CallbackLookupSource(lookup, source_policy="durable_ac_first"),
}


def _invoke(entity_kind, resolver, query, lookup, **kwargs):
    """Call a resolver with whatever calling convention its entity kind uses."""
    wrap = POLICY_WRAPPERS.get(entity_kind)
    argument = wrap(lookup) if wrap else lookup
    return resolver(query, argument, **kwargs)


def _lookup(records, seen=None):
    def lookup(query, scope, limit):
        if seen is not None:
            seen.append((query, scope, limit))
        return records
    return lookup


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_zero_matches_returns_no_reference(entity_kind, resolver):
    result = _invoke(entity_kind, resolver, "missing", _lookup([]), scope="tenant:u1", limit=2)
    assert result.entity_kind == entity_kind
    assert result.match_count == 0
    assert result.stable_reference == ""


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_exactly_one_match_returns_stable_reference(entity_kind, resolver):
    result = _invoke(entity_kind, resolver, "call supplier", _lookup([{"id": "rec1"}]), scope="tenant:u1")
    assert result.entity_kind == entity_kind
    assert result.match_count == 1
    assert result.stable_reference == "rec1"


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_multiple_matches_never_picks_silently(entity_kind, resolver):
    result = _invoke(
        entity_kind, resolver, "call", _lookup([{"id": "rec1"}, {"id": "rec2"}]),
        scope="tenant:u1", limit=1,
    )
    assert result.match_count == 2
    assert result.stable_reference == ""


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_bounded_query_consumes_at_most_limit_plus_one(entity_kind, resolver):
    consumed = []

    def lookup(query, scope, limit):
        for number in range(100):
            consumed.append(number)
            yield {"id": f"rec{number}"}

    result = _invoke(entity_kind, resolver, "call", lookup, scope="tenant:u1", limit=3)
    assert result.match_count == 4
    assert consumed == [0, 1, 2, 3]


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_rejects_missing_query_and_invalid_limit(entity_kind, resolver):
    lookup = _lookup([])
    with pytest.raises(ValueError):
        _invoke(entity_kind, resolver, "", lookup, scope="tenant:u1", limit=5)
    with pytest.raises(ValueError):
        _invoke(entity_kind, resolver, "x", lookup, scope="tenant:u1", limit=0)


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_missing_scope_fails_closed_before_any_lookup(entity_kind, resolver):
    seen = []
    with pytest.raises(ValueError):
        _invoke(entity_kind, resolver, "x", _lookup([{"id": "rec1"}], seen), scope="")
    assert seen == [], "lookup must not run when identity scope is missing"


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_identity_scope_isolation_is_passed_through_to_lookup(entity_kind, resolver):
    seen = []
    _invoke(entity_kind, resolver, "x", _lookup([{"id": "rec1"}], seen), scope="tenant:a", limit=3)
    _invoke(entity_kind, resolver, "x", _lookup([{"id": "rec1"}], seen), scope="tenant:b", limit=3)
    scopes_seen = {call[1] for call in seen}
    assert scopes_seen == {"tenant:a", "tenant:b"}


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_deterministic_repeatable_result(entity_kind, resolver):
    lookup = _lookup([{"id": "rec1"}])
    first = _invoke(entity_kind, resolver, "call", lookup, scope="tenant:u1", limit=3)
    second = _invoke(entity_kind, resolver, "call", lookup, scope="tenant:u1", limit=3)
    assert first == second


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_result_is_the_frozen_resolver_result_contract(entity_kind, resolver):
    result = _invoke(entity_kind, resolver, "call", _lookup([{"id": "rec1"}]), scope="tenant:u1")
    assert isinstance(result, ResolverResult)


def test_no_regression_to_the_already_live_tc3_task_path():
    """task_resolvers.resolve_task must remain import-compatible and behavior-identical."""
    from core.router.task_resolvers import TaskLookup, resolve_task as legacy_resolve_task

    assert legacy_resolve_task is resolve_task
    assert TaskLookup is not None

    seen = []
    result = legacy_resolve_task("call supplier", _lookup([{"id": "rec1"}], seen), scope="tenant:u1")
    assert result.match_count == 1
    assert result.stable_reference == "rec1"
    assert seen == [("call supplier", "tenant:u1", 6)]


def test_plain_resolvers_still_accept_a_bare_callable():
    """task/lead/contact/deal keep the original, simpler calling convention —
    only action_contract/session/callback require a typed source wrapper."""
    for entity_kind in ("task", "lead", "contact", "deal"):
        resolver = ALL_RESOLVERS[entity_kind]
        result = resolver("call supplier", _lookup([{"id": "rec1"}]), scope="tenant:u1")
        assert result.match_count == 1


def test_single_shared_bounded_core_backs_every_resolver():
    """No second resolver framework: every entity resolver delegates to one shared core."""
    import core.router.entity_resolvers as module

    for resolver in ALL_RESOLVERS.values():
        source = inspect.getsource(resolver)
        assert "_resolve_bounded_entity(" in source

    private_resolve_functions = [
        name for name, value in vars(module).items()
        if inspect.isfunction(value) and value.__module__ == module.__name__
        and name.startswith("_resolve")
    ]
    assert private_resolve_functions == ["_resolve_bounded_entity"]


def test_no_mutation_or_write_or_dispatch_import():
    """The resolver framework performs no write/execution: it must not import
    any dispatcher, gateway, or Airtable write path — only the frozen
    ResolverResult contract and stdlib."""
    import core.router.entity_resolvers as module

    tree = ast.parse(inspect.getsource(module))
    forbidden_substrings = (
        "dispatcher", "airtable_tools", "airtable_gateway", "action_gateway",
        "action_contract_repository", "event_bus", "session_store", "app",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not any(bad in module_name for bad in forbidden_substrings), (
                f"unexpected import touching a write/execution path: {module_name}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(bad in alias.name for bad in forbidden_substrings), (
                    f"unexpected import touching a write/execution path: {alias.name}"
                )


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_no_agent_call_where_tc5_owns_resolution(entity_kind, resolver):
    """The resolver never invents/guesses a match — it either resolves exactly
    one stable reference or reports 0/many, with no code path that could call
    out to an Agent/LLM. Inspects the shared bounded-resolve core too, not
    just the thin per-entity wrapper, since every resolver executes it."""
    import core.router.entity_resolvers as module

    source = "\n".join((
        inspect.getsource(resolver),
        inspect.getsource(module._resolve_bounded_entity),
    ))
    for banned in ("agent", "anthropic", "claude", "llm"):
        assert banned not in source.lower()


# --- Review follow-up (PR #562): entity-specific source-policy enforcement ---


def test_action_contract_resolver_rejects_a_bare_callable():
    """A caller cannot supply a raw lookup for ActionContract resolution —
    the durable-source declaration is required, not optional."""
    with pytest.raises(TypeError):
        resolve_action_contract("x", _lookup([{"id": "rec1"}]), scope="tenant:u1")


def test_action_contract_lookup_source_requires_the_declaration_be_explicit():
    """Omitting durable_source entirely must fail closed at construction —
    merely instantiating the wrapper class must not silently grant the
    canonical/durable policy."""
    with pytest.raises(TypeError):
        ActionContractLookupSource(_lookup([{"id": "rec1"}]))


def test_action_contract_resolver_requires_durable_source_true():
    """An explicit-but-false declaration must also fail closed at
    construction time, before it can ever reach the resolver."""
    with pytest.raises(ValueError):
        ActionContractLookupSource(_lookup([{"id": "rec1"}]), durable_source=False)


def test_action_contract_resolver_accepts_a_valid_durable_declaration():
    seen = []
    result = resolve_action_contract(
        "AC-1", ActionContractLookupSource(_lookup([{"id": "rec1"}], seen), durable_source=True),
        scope="tenant:u1",
    )
    assert result.match_count == 1
    assert result.stable_reference == "rec1"
    assert seen  # the underlying lookup did run once correctly declared


def test_session_resolver_rejects_a_bare_callable():
    with pytest.raises(TypeError):
        resolve_session("x", _lookup([{"id": "rec1"}]), scope="tenant:u1")


def test_session_lookup_source_requires_ttl_be_explicit():
    """Omitting ttl_seconds entirely must fail closed at construction."""
    with pytest.raises(TypeError):
        SessionLookupSource(_lookup([{"id": "rec1"}]))


@pytest.mark.parametrize("bad_ttl", [0, -1, -3600])
def test_session_resolver_requires_positive_ttl(bad_ttl):
    """An explicit-but-non-positive TTL must fail closed at construction time."""
    with pytest.raises(ValueError):
        SessionLookupSource(_lookup([{"id": "rec1"}]), ttl_seconds=bad_ttl)


def test_session_resolver_accepts_a_valid_ttl_declaration():
    result = resolve_session(
        "sess-1", SessionLookupSource(_lookup([{"id": "rec1"}]), ttl_seconds=1800),
        scope="chat:c1",
    )
    assert result.match_count == 1
    assert result.stable_reference == "rec1"


def test_callback_resolver_rejects_a_bare_callable():
    with pytest.raises(TypeError):
        resolve_callback("x", _lookup([{"id": "rec1"}]), scope="tenant:u1")


def test_callback_lookup_source_requires_the_declaration_be_explicit():
    """Omitting source_policy entirely must fail closed at construction —
    merely instantiating the wrapper class must not silently grant the
    canonical durable-AC-first policy."""
    with pytest.raises(TypeError):
        CallbackLookupSource(_lookup([{"id": "rec1"}]))


@pytest.mark.parametrize("bad_policy", ["", "ac_first", "cache", "legacy"])
def test_callback_resolver_rejects_an_unrecognized_source_policy(bad_policy):
    """An explicit-but-invalid source_policy value must fail closed at
    construction time -- only the two RESOLVER_MAP.md-recognized policies
    are accepted."""
    with pytest.raises(ValueError):
        CallbackLookupSource(_lookup([{"id": "rec1"}]), source_policy=bad_policy)


def test_callback_resolver_accepts_durable_ac_first_declaration():
    result = resolve_callback(
        "cb-1",
        CallbackLookupSource(_lookup([{"id": "rec1"}]), source_policy="durable_ac_first"),
        scope="tenant:u1",
    )
    assert result.match_count == 1
    assert result.stable_reference == "rec1"


def test_callback_resolver_accepts_explicit_legacy_pointer_migration_declaration():
    """A legacy-pointer lookup is only accepted when explicitly opted into as
    a migration path -- never as a silent default."""
    result = resolve_callback(
        "cb-legacy-1",
        CallbackLookupSource(_lookup([{"id": "rec1"}]), source_policy="legacy_pointer_migration"),
        scope="tenant:u1",
    )
    assert result.match_count == 1
    assert result.stable_reference == "rec1"


@pytest.mark.parametrize(
    "wrapper_cls,kwargs",
    [
        (ActionContractLookupSource, {"durable_source": True}),
        (SessionLookupSource, {"ttl_seconds": 1800}),
        (CallbackLookupSource, {"source_policy": "durable_ac_first"}),
    ],
)
def test_policy_wrappers_reject_a_non_callable_lookup(wrapper_cls, kwargs):
    """The lookup field itself must be callable -- a structural guard against
    wiring mistakes, independent of the source-policy declaration."""
    with pytest.raises(TypeError):
        wrapper_cls("not-a-callable", **kwargs)
