from core.router.task_resolvers import resolve_task


def _lookup(records, seen):
    def lookup(query, scope, limit):
        seen.append((query, scope, limit))
        return records
    return lookup


def test_task_resolver_returns_zero_without_reference():
    seen = []
    result = resolve_task("missing", _lookup([], seen), scope="tenant:u1", limit=2)
    assert result.match_count == 0
    assert result.stable_reference == ""
    assert seen == [("missing", "tenant:u1", 3)]


def test_task_resolver_returns_one_stable_reference():
    result = resolve_task(
        "call supplier", _lookup([{"id": "rec1"}], []), scope="tenant:u1"
    )
    assert result.match_count == 1
    assert result.stable_reference == "rec1"


def test_task_resolver_returns_multiple_without_picking():
    result = resolve_task(
        "call", _lookup([{"id": "rec1"}, {"id": "rec2"}], []),
        scope="tenant:u1", limit=1,
    )
    assert result.match_count == 2
    assert result.stable_reference == ""


def test_task_resolver_consumes_at_most_limit_plus_one():
    consumed = []

    def lookup(query, scope, limit):
        for number in range(100):
            consumed.append(number)
            yield {"id": f"rec{number}"}

    result = resolve_task("call", lookup, scope="tenant:u1", limit=3)
    assert result.match_count == 4
    assert consumed == [0, 1, 2, 3]


def test_task_resolver_rejects_missing_query_and_invalid_limit():
    lookup = _lookup([], [])
    for kwargs in ({"query": "", "limit": 5}, {"query": "x", "limit": 0}):
        try:
            resolve_task(kwargs["query"], lookup, scope="tenant:u1", limit=kwargs["limit"])
        except ValueError:
            pass
        else:
            raise AssertionError("invalid resolver input was accepted")
