#!/usr/bin/env python3
"""
test_core_emergency_stop.py — pure unit tests for core/emergency_stop.py
(PATCH 3B Step 1).

No network, no file I/O, no Airtable, no feature_flags. Every test injects
a fake clock and a fake EmergencyStopStore double.
"""

from __future__ import annotations

import threading
import time

from core.emergency_stop import (
    EmergencyStopManager,
    EmergencyStopStore,
    FlagEvaluation,
    ReadResult,
    WriteResult,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
# Test doubles
# ══════════════════════════════════════════════════════════════════

class FakeClock:
    """Deterministic monotonic-compatible clock — advances only when told."""
    def __init__(self, start: float = 1000.0):
        self._t = start

    def advance(self, seconds: float) -> None:
        self._t += seconds

    def __call__(self) -> float:
        return self._t


class QueueStore:
    """Returns ReadResult from a pre-seeded queue, one per call(); raises
    IndexError (a test bug, not part of the contract) if exhausted."""
    def __init__(self, results: list[ReadResult]):
        self._results = list(results)
        self.call_count = 0

    def read(self) -> ReadResult:
        self.call_count += 1
        return self._results.pop(0)

    def write(self, *a, **kw) -> WriteResult:
        raise NotImplementedError("not exercised in Step 1 tests")


class RaisingStore:
    def read(self) -> ReadResult:
        raise RuntimeError("simulated adapter bug — Protocol says this must never happen")

    def write(self, *a, **kw) -> WriteResult:
        raise NotImplementedError


class BlockingStore:
    """First call() blocks on an Event until released — used to prove
    single-flight dedup under concurrent callers."""
    def __init__(self, result: ReadResult):
        self._result = result
        self.call_count = 0
        self.started = threading.Event()
        self._release = threading.Event()

    def read(self) -> ReadResult:
        self.call_count += 1
        self.started.set()
        self._release.wait(timeout=5)
        return self._result

    def release(self) -> None:
        self._release.set()

    def write(self, *a, **kw) -> WriteResult:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════
# 1. Never hydrated, no store configured -> unknown, fail-closed
# ══════════════════════════════════════════════════════════════════
print("\n── no store configured ──────────────────")

mgr = EmergencyStopManager(store=None, clock=FakeClock())
ev = mgr.evaluate("EMERGENCY_STOP_ALL")
chk("no store -> source=unknown", ev.source == "unknown")
chk("no store -> blocked=True (fail-closed)", ev.blocked is True)
chk("no store -> store_status is None", ev.store_status is None)
chk("no store -> cache_age_seconds is None", ev.cache_age_seconds is None)


# ══════════════════════════════════════════════════════════════════
# 2. Successful hydrate -> source=durable, correct value
# ══════════════════════════════════════════════════════════════════
print("\n── successful hydrate ───────────────────")

clock = FakeClock()
store = QueueStore([ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": True, "EMERGENCY_STOP_AI": False})])
mgr = EmergencyStopManager(store=store, clock=clock, ttl_seconds=7.0)

ev_all = mgr.evaluate("EMERGENCY_STOP_ALL")
chk("hydrated ALL -> blocked=True", ev_all.blocked is True)
chk("hydrated ALL -> source=durable", ev_all.source == "durable")
chk("hydrated ALL -> store_status=ok", ev_all.store_status == "ok")
chk("hydrated ALL -> cache_age_seconds == 0 right after hydrate", ev_all.cache_age_seconds == 0.0)

ev_ai = mgr.evaluate("EMERGENCY_STOP_AI")
chk("hydrated AI -> blocked=False (real configured false, not fail-closed)", ev_ai.blocked is False)
chk("hydrated AI -> source=durable", ev_ai.source == "durable")
chk("second evaluate() within TTL did not re-read the store", store.call_count == 1)


# ══════════════════════════════════════════════════════════════════
# 3. TTL: fresh within window, stale after
# ══════════════════════════════════════════════════════════════════
print("\n── TTL staleness ────────────────────────")

clock = FakeClock()
store = QueueStore([
    ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": False}),
    ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": True}),
])
mgr = EmergencyStopManager(store=store, clock=clock, ttl_seconds=7.0)

mgr.evaluate("EMERGENCY_STOP_ALL")
chk("first evaluate() triggers exactly one read", store.call_count == 1)

clock.advance(3.0)
ev = mgr.evaluate("EMERGENCY_STOP_ALL")
chk("within TTL (3s < 7s) -> no second read", store.call_count == 1)
chk("within TTL -> still source=durable", ev.source == "durable")

clock.advance(5.0)  # total 8s since hydrate > 7s ttl
ev = mgr.evaluate("EMERGENCY_STOP_ALL")
chk("past TTL -> triggers a second read", store.call_count == 2)
chk("past TTL, second read succeeded -> new value reflected", ev.blocked is True)
chk("past TTL, second read succeeded -> source=durable again", ev.source == "durable")


# ══════════════════════════════════════════════════════════════════
# 4. Stale-cache fallback: refresh fails, old value still served
# ══════════════════════════════════════════════════════════════════
print("\n── stale-cache fallback on refresh failure ──")

clock = FakeClock()
store = QueueStore([
    ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": True}),
    ReadResult(status="unavailable", error="simulated network timeout"),
])
mgr = EmergencyStopManager(store=store, clock=clock, ttl_seconds=7.0)

mgr.evaluate("EMERGENCY_STOP_ALL")
clock.advance(10.0)  # now stale
ev = mgr.evaluate("EMERGENCY_STOP_ALL")
chk("refresh attempted after staleness", store.call_count == 2)
chk("refresh failed -> old cached value still returned", ev.blocked is True)
chk("refresh failed -> source flips to cache (fallback, not durable)", ev.source == "cache")
chk("refresh failed -> store_status reflects the failure", ev.store_status == "unavailable")
chk("refresh failed -> error message surfaced", "timeout" in ev.error)
chk("last_hydrated_at NOT bumped by the failed attempt",
    mgr.evaluate("EMERGENCY_STOP_ALL").cache_age_seconds >= 10.0)


# ══════════════════════════════════════════════════════════════════
# 5. Never successfully hydrated + refresh keeps failing -> stays unknown
# ══════════════════════════════════════════════════════════════════
print("\n── perpetually unavailable store -> stays unknown ──")

clock = FakeClock()
store = QueueStore([ReadResult(status="unavailable", error="down")])
mgr = EmergencyStopManager(store=store, clock=clock, ttl_seconds=7.0)
ev = mgr.evaluate("EMERGENCY_STOP_ALL")
chk("store down from the start -> source=unknown", ev.source == "unknown")
chk("store down from the start -> blocked=True (fail-closed)", ev.blocked is True)


# ══════════════════════════════════════════════════════════════════
# 6. Full-cache replacement (not merge) on a successful read
# ══════════════════════════════════════════════════════════════════
print("\n── full-cache replacement, not merge ────")

clock = FakeClock()
store = QueueStore([
    ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": True, "EMERGENCY_STOP_AI": True}),
    ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": False}),  # AI dropped
])
mgr = EmergencyStopManager(store=store, clock=clock, ttl_seconds=7.0)

mgr.evaluate("EMERGENCY_STOP_ALL")
chk("AI present after first hydrate", mgr.evaluate("EMERGENCY_STOP_AI").source == "durable")

clock.advance(8.0)
mgr.evaluate("EMERGENCY_STOP_ALL")  # triggers the second (replacing) read
ev_ai = mgr.evaluate("EMERGENCY_STOP_AI")
chk("AI absent from second read -> now unknown, not stale-True",
    ev_ai.source == "unknown" and ev_ai.blocked is True)


# ══════════════════════════════════════════════════════════════════
# 7. env force-stop precedence — always wins, never consults cache
# ══════════════════════════════════════════════════════════════════
print("\n── env force-stop precedence ────────────")

clock = FakeClock()
store = QueueStore([ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": False})])
mgr = EmergencyStopManager(
    store=store, clock=clock, ttl_seconds=7.0,
    force_stop_provider=lambda name: name == "EMERGENCY_STOP_ALL",
)
ev = mgr.evaluate("EMERGENCY_STOP_ALL")
chk("env force-stop -> blocked=True even though durable says False", ev.blocked is True)
chk("env force-stop -> source=env", ev.source == "env")

ev_other = mgr.evaluate("EMERGENCY_STOP_AI")
chk("force_stop_provider returning False for a different flag -> not env-forced",
    ev_other.source != "env")

mgr_no_store = EmergencyStopManager(
    store=None, clock=FakeClock(),
    force_stop_provider=lambda name: True,
)
chk("env force-stop wins even with no store configured at all",
    mgr_no_store.evaluate("EMERGENCY_STOP_ALL").source == "env")


# ══════════════════════════════════════════════════════════════════
# 8. Defensive: store.read() raising is caught, not propagated
# ══════════════════════════════════════════════════════════════════
print("\n── adapter raising is contained ─────────")

mgr = EmergencyStopManager(store=RaisingStore(), clock=FakeClock())
try:
    ev = mgr.evaluate("EMERGENCY_STOP_ALL")
    chk("store.read() raising does not propagate out of evaluate()", True)
    chk("raised exception treated as unavailable", ev.store_status == "unavailable")
    chk("raised exception -> still fail-closed (unknown)", ev.source == "unknown" and ev.blocked is True)
except Exception as e:
    chk(f"store.read() raising does not propagate out of evaluate() (got {e})", False)


# ══════════════════════════════════════════════════════════════════
# 9. status() — observability snapshot
# ══════════════════════════════════════════════════════════════════
print("\n── status() observability ───────────────")

clock = FakeClock()
store = QueueStore([ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": True, "EMERGENCY_STOP_AI": False})])
mgr = EmergencyStopManager(
    store=store, clock=clock, ttl_seconds=7.0,
    known_flag_names=["EMERGENCY_STOP_ALL", "EMERGENCY_STOP_AI", "EMERGENCY_STOP_EMAIL"],
)
st = mgr.status()
chk("status().store_configured", st.store_configured is True)
chk("status().store_status == ok", st.store_status == "ok")
chk("status().flags has all known flags, including one never in a read", set(st.flags) == {
    "EMERGENCY_STOP_ALL", "EMERGENCY_STOP_AI", "EMERGENCY_STOP_EMAIL",
})
chk("status().flags['EMERGENCY_STOP_EMAIL'] is unknown (never appeared in a read)",
    st.flags["EMERGENCY_STOP_EMAIL"].source == "unknown")
chk("status() never renders unknown as blocked=false", st.flags["EMERGENCY_STOP_EMAIL"].blocked is True)

st_unconfigured = EmergencyStopManager(store=None, clock=FakeClock()).status()
chk("status() with no store -> store_configured=False", st_unconfigured.store_configured is False)


# ══════════════════════════════════════════════════════════════════
# 10. Single-flight: concurrent evaluate() calls dedupe to one read
# ══════════════════════════════════════════════════════════════════
print("\n── single-flight under concurrency ──────")

clock = FakeClock()
store = BlockingStore(ReadResult(status="ok", flags={"EMERGENCY_STOP_ALL": True}))
mgr = EmergencyStopManager(store=store, clock=clock, ttl_seconds=7.0)

results: list[FlagEvaluation] = []
results_lock = threading.Lock()

def _worker():
    ev = mgr.evaluate("EMERGENCY_STOP_ALL")
    with results_lock:
        results.append(ev)

threads = [threading.Thread(target=_worker) for _ in range(8)]
for t in threads:
    t.start()

store.started.wait(timeout=5)  # at least one thread is inside store.read()
time.sleep(0.2)  # let the other 7 threads pile up on the manager's lock
store.release()
for t in threads:
    t.join(timeout=5)

chk("8 concurrent evaluate() calls -> exactly 1 store.read() call", store.call_count == 1)
chk("all 8 threads got a result", len(results) == 8)
chk("all 8 threads agree on the value", all(r.blocked is True for r in results))


print(f"\n{'='*40}")
print(f"core/emergency_stop.py tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
