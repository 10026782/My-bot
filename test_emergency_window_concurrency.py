#!/usr/bin/env python3
# test_emergency_window_concurrency.py
#
# C05-C07 audit Finding #7 (UNDOCUMENTED_RECOVERY) re-audit + remediation.
#
# Original finding: core/emergency_window.py::activate_window()'s "no
# stacking" invariant was enforced via a non-atomic read-then-write
# (is_active() then airtable_create(), no lock), and _auto_expire() ignored
# its own airtable_patch()'s success/failure. Re-verified directly against
# the live file for this fix: both claims held. Note: activate_window()/
# revoke_window() currently have zero live callers anywhere in the repo
# (grep-confirmed) — the race is real in the code but not yet reachable in
# production; this test still locks in the invariant so it can't regress
# once something wires the feature up.
#
# Fix: a module-level threading.Lock() now serializes the
# check-then-create in activate_window() (same pattern event_bus.py already
# uses for its analogous pop/confirm race); _auto_expire() now checks the
# patch's return value and logs failure distinctly, while still failing
# closed (an expired window is treated as inactive either way).
#
# Run: python3 test_emergency_window_concurrency.py
# Pass condition: exit code 0, all assertions green.

from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import core.emergency_window as ew

_passed = 0
_failed = 0


def chk(label: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS: {label}")
    else:
        _failed += 1
        print(f"  FAIL: {label}")


# ── shared fakes ─────────────────────────────────────────────────────────
_orig_is_enabled = ew.feature_flags.is_enabled
_orig_fetch = ew._fetch_active_record
_orig_create = ew.airtable_create
_orig_patch = ew.airtable_patch

_log_records: list[tuple[int, str]] = []


class _CapturingHandler(logging.Handler):
    def emit(self, record):
        _log_records.append((record.levelno, record.getMessage()))


_handler = _CapturingHandler()
ew.logger.addHandler(_handler)
ew.logger.setLevel(logging.DEBUG)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── [1] activate_window(): concurrent stacking race ────────────────────────
# Simulates the real GET-then-POST race with an artificial sleep on both the
# fake fetch and the fake create, widening the window an unlocked
# implementation would fall into. The store lock below only protects the
# fake store's own bookkeeping (like a real Airtable request completing
# atomically) — it does NOT serialize the check-then-write sequence itself;
# only activate_window()'s own _activate_lock can do that.
_fake_store: dict = {"record": None}
_store_lock = threading.Lock()
_create_calls: list[str] = []


def _racy_fetch_active_record():
    time.sleep(0.02)
    with _store_lock:
        rec = _fake_store["record"]
        return dict(rec) if rec else None


def _racy_airtable_create(table, fields, source="unknown"):
    time.sleep(0.02)
    rec = {"id": f"recEW{threading.get_ident()}", "fields": dict(fields)}
    with _store_lock:
        _create_calls.append(rec["id"])
        _fake_store["record"] = rec
    return rec


ew.feature_flags.is_enabled = lambda name: True
ew._fetch_active_record = _racy_fetch_active_record
ew.airtable_create = _racy_airtable_create

print("\n[7-race] activate_window(): N concurrent callers -> exactly one activation")
_fake_store["record"] = None
_create_calls.clear()

N = 8
results: list[tuple[bool, str]] = []
results_lock = threading.Lock()


def _worker(i: int) -> None:
    try:
        rec = ew.activate_window(activated_by=f"owner{i}", reason="race test", duration_hours=24)
        with results_lock:
            results.append((True, rec["id"]))
    except ValueError as e:
        with results_lock:
            results.append((False, str(e)))


threads = [threading.Thread(target=_worker, args=(i,)) for i in range(N)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=5)

successes = [r for r in results if r[0]]
failures = [r for r in results if not r[0]]

chk("all N threads returned (no deadlock/hang)", len(results) == N)
chk("exactly one activation succeeded (no stacking)", len(successes) == 1)
chk("exactly one record was ever created in the store", len(_create_calls) == 1)
chk(f"remaining {N - 1} callers were correctly rejected as 'already active'",
    len(failures) == N - 1 and all("already active" in msg for _, msg in failures))

ew.feature_flags.is_enabled = _orig_is_enabled
ew._fetch_active_record = _orig_fetch
ew.airtable_create = _orig_create


# ── [7-expire] _auto_expire(): checks the patch outcome instead of ignoring it
print("\n[7-expire] _auto_expire(): observes airtable_patch() success/failure")

_expired_record = {
    "id": "recEWexp1",
    "fields": {ew.F.EXPIRES_AT: (_now() - timedelta(hours=1)).isoformat()},
}
_not_expired_record = {
    "id": "recEWexp2",
    "fields": {ew.F.EXPIRES_AT: (_now() + timedelta(hours=1)).isoformat()},
}

_patch_calls: list[tuple[str, dict]] = []


def _patch_ok(table, record_id, fields, source="unknown"):
    _patch_calls.append((record_id, dict(fields)))
    return True


def _patch_fail(table, record_id, fields, source="unknown"):
    _patch_calls.append((record_id, dict(fields)))
    return False


# not-yet-expired: no patch attempted at all
_patch_calls.clear()
ew.airtable_patch = _patch_ok
result = ew._auto_expire(_not_expired_record)
chk("not-yet-expired record: _auto_expire returns False", result is False)
chk("not-yet-expired record: airtable_patch never called", len(_patch_calls) == 0)

# expired + patch succeeds
_patch_calls.clear()
_log_records.clear()
ew.airtable_patch = _patch_ok
result = ew._auto_expire(_expired_record)
chk("expired + patch succeeds: _auto_expire returns True", result is True)
chk("expired + patch succeeds: airtable_patch was actually called with Status=Expired",
    len(_patch_calls) == 1 and _patch_calls[0][1].get(ew.F.STATUS) == ew.Status.EXPIRED)
chk("expired + patch succeeds: logs at WARNING, not ERROR",
    any(lvl == logging.WARNING and "auto-expired" in msg for lvl, msg in _log_records)
    and not any(lvl == logging.ERROR for lvl, msg in _log_records))

# expired + patch fails — must still fail closed, but must now be observable
_patch_calls.clear()
_log_records.clear()
ew.airtable_patch = _patch_fail
result = ew._auto_expire(_expired_record)
chk("expired + patch FAILS: _auto_expire still returns True (fails closed)", result is True)
chk("expired + patch FAILS: airtable_patch's return value was actually consulted "
    "(distinct ERROR log emitted, not silently swallowed)",
    any(lvl == logging.ERROR and "PATCH FAILED" in msg for lvl, msg in _log_records))
chk("expired + patch FAILS: no misleading 'auto-expired' success log for this call",
    not any(lvl == logging.WARNING and "auto-expired" in msg for lvl, msg in _log_records))

ew.airtable_patch = _orig_patch
ew.logger.removeHandler(_handler)


print(f"\n{'=' * 60}")
print(f"C05-C07 Finding #7 (emergency window concurrency): {_passed}/{_passed + _failed} passed")
if _failed:
    print(f"FAILED: {_failed} check(s)")
sys.exit(0 if _failed == 0 else 1)
