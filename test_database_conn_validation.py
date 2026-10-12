"""core/database.py::get_conn — dead pooled connections are discarded, never handed out.

Standalone assert-based script (`python3 test_database_conn_validation.py`), no database.
Neon M0.5: after a server-side close the first checkout must not return a dead connection;
at most one retry; still None (fail closed) if no live connection can be had.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core.database as db


class FakeCur:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql):
        assert sql == "SELECT 1"
        if self.conn.dead:
            raise RuntimeError("server closed the connection unexpectedly")


class FakeConn:
    def __init__(self, dead=False):
        self.dead, self.rolled_back = dead, 0

    def cursor(self):
        return FakeCur(self)

    def rollback(self):
        self.rolled_back += 1


class FakePool:
    def __init__(self, conns):
        self.conns, self.put = list(conns), []

    def getconn(self):
        return self.conns.pop(0)

    def putconn(self, conn, close=False):
        self.put.append((conn, close))


def with_pool(pool):
    db._pool = pool
    return db.get_conn()


good = FakeConn()
p = FakePool([good])
assert with_pool(p) is good and good.rolled_back == 1 and p.put == [], "healthy conn returned as-is"

dead, fresh = FakeConn(dead=True), FakeConn()
p = FakePool([dead, fresh])
assert with_pool(p) is fresh, "dead conn replaced by a fresh one"
assert p.put == [(dead, True)], "dead conn discarded with close=True"

d1, d2 = FakeConn(dead=True), FakeConn(dead=True)
p = FakePool([d1, d2, FakeConn()])
assert with_pool(p) is None, "two dead conns in a row -> None (fail closed), not a third try"
assert [c for c, _ in p.put] == [d1, d2] and all(close for _, close in p.put)
assert len(p.conns) == 1, "exactly two checkouts were attempted"


class BoomPool(FakePool):
    def getconn(self):
        raise RuntimeError("pool exhausted")


assert with_pool(BoomPool([])) is None, "getconn failure -> None, no retry loop"

db._pool = None
for k in ("DATABASE_URL", "DATABASE_HOST", "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD"):
    os.environ.pop(k, None)
assert db.get_conn() is None, "no PostgreSQL configured -> None"

print("test_database_conn_validation: all checks passed")
