"""TC5 verification: bounded entity resolver framework.

Covers 0/1/many outcomes, bounded consumption, identity-scope isolation,
fail-closed behavior on missing scope, determinism, and the absence of any
mutation/write or second resolver implementation, across every entity kind
named in docs/architecture/turn-coordinator-full/RESOLVER_MAP.md.
"""

import ast
import inspect

import pytest

from core.router.entity_resolvers import (
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


def _lookup(records, seen=None):
    def lookup(query, scope, limit):
        if seen is not None:
            seen.append((query, scope, limit))
        return records
    return lookup


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_zero_matches_returns_no_reference(entity_kind, resolver):
    result = resolver("missing", _lookup([]), scope="tenant:u1", limit=2)
    assert result.entity_kind == entity_kind
    assert result.match_count == 0
    assert result.stable_reference == ""


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_exactly_one_match_returns_stable_reference(entity_kind, resolver):
    result = resolver("call supplier", _lookup([{"id": "rec1"}]), scope="tenant:u1")
    assert result.entity_kind == entity_kind
    assert result.match_count == 1
    assert result.stable_reference == "rec1"


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_multiple_matches_never_picks_silently(entity_kind, resolver):
    result = resolver(
        "call", _lookup([{"id": "rec1"}, {"id": "rec2"}]), scope="tenant:u1", limit=1,
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

    result = resolver("call", lookup, scope="tenant:u1", limit=3)
    assert result.match_count == 4
    assert consumed == [0, 1, 2, 3]


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_rejects_missing_query_and_invalid_limit(entity_kind, resolver):
    lookup = _lookup([])
    with pytest.raises(ValueError):
        resolver("", lookup, scope="tenant:u1", limit=5)
    with pytest.raises(ValueError):
        resolver("x", lookup, scope="tenant:u1", limit=0)


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_missing_scope_fails_closed_before_any_lookup(entity_kind, resolver):
    seen = []
    with pytest.raises(ValueError):
        resolver("x", _lookup([{"id": "rec1"}], seen), scope="")
    assert seen == [], "lookup must not run when identity scope is missing"


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_identity_scope_isolation_is_passed_through_to_lookup(entity_kind, resolver):
    seen = []
    resolver("x", _lookup([{"id": "rec1"}], seen), scope="tenant:a", limit=3)
    resolver("x", _lookup([{"id": "rec1"}], seen), scope="tenant:b", limit=3)
    scopes_seen = {call[1] for call in seen}
    assert scopes_seen == {"tenant:a", "tenant:b"}


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_deterministic_repeatable_result(entity_kind, resolver):
    lookup = _lookup([{"id": "rec1"}])
    first = resolver("call", lookup, scope="tenant:u1", limit=3)
    second = resolver("call", lookup, scope="tenant:u1", limit=3)
    assert first == second


@pytest.mark.parametrize("entity_kind,resolver", ALL_RESOLVERS.items())
def test_result_is_the_frozen_resolver_result_contract(entity_kind, resolver):
    result = resolver("call", _lookup([{"id": "rec1"}]), scope="tenant:u1")
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
