#!/usr/bin/env python3
"""
test_feature_flags_emergency_stop_step3.py — PATCH 3B Step 3 (+ Step 6 cutover)

Tests feature_flags.py's EmergencyStopManager integration:
configure_emergency_stop_manager() + the parallel evaluate_emergency_stop()/
get_emergency_stop_status()/set_emergency_stop()/clear_emergency_stop() API.

Section 4 originally proved is_enabled()/set_flag() stayed byte-for-behavior
unchanged for EMERGENCY_STOP_* names (Step 3 was deliberately dual-path,
nothing wired up yet). PATCH 3B Step 6 landed the atomic cutover — is_enabled()
now delegates to evaluate_emergency_stop() for these 5 names, and set_flag()
raises EmergencyStopLegacyWriteBlocked for them — so section 4 now proves
THAT instead. See test_feature_flags_cutover.py for the fuller Step 6
end-to-end coverage (dynamic-callsite scan, cost_monitor/tma_api wiring,
non-emergency-flag regression, etc.) — this file stays focused on the
Step 3 manager-integration API plus the is_enabled()/set_flag() boundary.
"""

from __future__ import annotations

import sys

# ══════════════════════════════════════════════════════════════════
# 0. Importing feature_flags does no new I/O. Checked immediately after
# import, before this file imports anything else — each test_*.py file
# runs as its own fresh process in this repo's CI (.github/workflows/ci.yml:
# `for f in test_*.py; do python "$f"; done`), so this is a clean
# first-import snapshot, not polluted by other test files' imports.
# ══════════════════════════════════════════════════════════════════

_pre_import_modules = set(sys.modules)
import feature_flags  # noqa: E402
_new_modules_from_import = set(sys.modules) - _pre_import_modules

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


print("\n── import-time I/O boundary ──────────")

chk(
    "importing feature_flags does not import adapters.airtable_emergency_stop_store",
    "adapters.airtable_emergency_stop_store" not in _new_modules_from_import,
)
chk(
    "importing feature_flags does not import tools.airtable_gateway",
    "tools.airtable_gateway" not in _new_modules_from_import,
)
chk(
    "importing feature_flags does not auto-configure a manager",
    feature_flags._emergency_stop_manager is None,
)

import inspect  # noqa: E402

from core.emergency_stop import (  # noqa: E402
    EmergencyStopManager,
    FlagRecord,
    ReadResult,
    WriteResult,
)


class FakeClock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


class FakeStore:
    def __init__(self, read_results=(), write_results=()):
        self._read_results = list(read_results)
        self._write_results = list(write_results)

    def read(self) -> ReadResult:
        return self._read_results.pop(0)

    def write(self, flag_name, enabled, **kwargs) -> WriteResult:
        return self._write_results.pop(0)


def _fresh_manager(**overrides) -> EmergencyStopManager:
    kwargs = dict(store=None, clock=FakeClock())
    kwargs.update(overrides)
    return EmergencyStopManager(**kwargs)


# ══════════════════════════════════════════════════════════════════
# 1. New API raises NotConfigured before any configure() call
# ══════════════════════════════════════════════════════════════════
print("\n── NotConfigured before configure() ──")

feature_flags._reset_emergency_stop_manager_for_tests()

try:
    feature_flags.evaluate_emergency_stop("EMERGENCY_STOP_ALL")
    chk("evaluate_emergency_stop() raises NotConfigured pre-configure", False)
except feature_flags.EmergencyStopNotConfigured:
    chk("evaluate_emergency_stop() raises NotConfigured pre-configure", True)

try:
    feature_flags.set_emergency_stop(
        "EMERGENCY_STOP_ALL", True, operation_id="op-1", updated_by="owner",
        source="test", reason="r",
    )
    chk("set_emergency_stop() raises NotConfigured pre-configure", False)
except feature_flags.EmergencyStopNotConfigured:
    chk("set_emergency_stop() raises NotConfigured pre-configure", True)

try:
    feature_flags.clear_emergency_stop(
        "EMERGENCY_STOP_ALL", operation_id="op-1", updated_by="owner",
        source="test", reason="r",
    )
    chk("clear_emergency_stop() raises NotConfigured pre-configure", False)
except feature_flags.EmergencyStopNotConfigured:
    chk("clear_emergency_stop() raises NotConfigured pre-configure", True)

status = feature_flags.get_emergency_stop_status()
chk("get_emergency_stop_status() does NOT raise pre-configure", True)
chk("get_emergency_stop_status() -> configured=False pre-configure", status.configured is False)
chk(
    "get_emergency_stop_status() -> manager_status=None pre-configure "
    "(no 'unknown' flags dict that could be misread as an active stop)",
    status.manager_status is None,
)


# ══════════════════════════════════════════════════════════════════
# 2. configure_emergency_stop_manager() — success / idempotent / conflict
# ══════════════════════════════════════════════════════════════════
print("\n── configure_emergency_stop_manager() ──")

feature_flags._reset_emergency_stop_manager_for_tests()

mgr1 = _fresh_manager()
feature_flags.configure_emergency_stop_manager(mgr1)
chk("first configure() succeeds", feature_flags._emergency_stop_manager is mgr1)

feature_flags.configure_emergency_stop_manager(mgr1)  # same instance again
chk("re-configuring with the SAME instance is a no-op", feature_flags._emergency_stop_manager is mgr1)

mgr2 = _fresh_manager()
try:
    feature_flags.configure_emergency_stop_manager(mgr2)
    chk("configuring a DIFFERENT instance raises EmergencyStopManagerConflict", False)
except feature_flags.EmergencyStopManagerConflict:
    chk("configuring a DIFFERENT instance raises EmergencyStopManagerConflict", True)
chk("a rejected re-configure does not replace the manager", feature_flags._emergency_stop_manager is mgr1)

try:
    feature_flags.configure_emergency_stop_manager(None)
    chk("configure_emergency_stop_manager(None) raises TypeError", False)
except TypeError:
    chk("configure_emergency_stop_manager(None) raises TypeError", True)

feature_flags._reset_emergency_stop_manager_for_tests()
chk("reset hook (test-only) clears the configured manager", feature_flags._emergency_stop_manager is None)


# ══════════════════════════════════════════════════════════════════
# 3. New API works correctly through a configured (fake) manager
# ══════════════════════════════════════════════════════════════════
print("\n── new API through a configured manager ─")

feature_flags._reset_emergency_stop_manager_for_tests()

store = FakeStore(
    read_results=[ReadResult(status="ok", flags={
        "EMERGENCY_STOP_ALL": FlagRecord(enabled=True),
        "EMERGENCY_STOP_AI": FlagRecord(enabled=False),
    })],
    write_results=[WriteResult(ok=True, verified=True)],
)
mgr = EmergencyStopManager(store=store, clock=FakeClock(), ttl_seconds=7.0)
feature_flags.configure_emergency_stop_manager(mgr)

ev = feature_flags.evaluate_emergency_stop("EMERGENCY_STOP_ALL")
chk(
    "evaluate_emergency_stop() delegates through the configured manager",
    ev.blocked is True and ev.source == "durable",
)

status = feature_flags.get_emergency_stop_status()
chk("get_emergency_stop_status() -> configured=True once configured", status.configured is True)
chk("get_emergency_stop_status() -> manager_status populated", status.manager_status is not None)

wr = feature_flags.set_emergency_stop(
    "EMERGENCY_STOP_ALL", False, operation_id="op-2", updated_by="owner",
    source="test", reason="turn it off",
)
chk("set_emergency_stop() delegates to manager.write() and returns its result", wr.ok is True and wr.verified is True)

# clear_emergency_stop() — no force_stop_provider configured -> not still blocked
store2 = FakeStore(write_results=[WriteResult(ok=True, verified=True)])
mgr2 = EmergencyStopManager(store=store2, clock=FakeClock(), ttl_seconds=7.0)
feature_flags._reset_emergency_stop_manager_for_tests()
feature_flags.configure_emergency_stop_manager(mgr2)

clear_result = feature_flags.clear_emergency_stop(
    "EMERGENCY_STOP_WHATSAPP", operation_id="op-3", updated_by="owner",
    source="test", reason="all clear",
)
chk(
    "clear_emergency_stop() returns EmergencyStopClearResult",
    isinstance(clear_result, feature_flags.EmergencyStopClearResult),
)
chk("clear_emergency_stop() -> write.ok True", clear_result.write.ok is True)
chk(
    "clear_emergency_stop() -> not still_blocked_by_env (no force_stop_provider configured)",
    clear_result.still_blocked_by_env is False,
)

# clear_emergency_stop() — env force-stop still active after a successful
# durable clear -> still_blocked_by_env=True (never silently claim "cleared")
store3 = FakeStore(write_results=[WriteResult(ok=True, verified=True)])
mgr3 = EmergencyStopManager(
    store=store3, clock=FakeClock(), ttl_seconds=7.0,
    force_stop_provider=lambda name: name == "EMERGENCY_STOP_ALL",
)
feature_flags._reset_emergency_stop_manager_for_tests()
feature_flags.configure_emergency_stop_manager(mgr3)
clear_result2 = feature_flags.clear_emergency_stop(
    "EMERGENCY_STOP_ALL", operation_id="op-4", updated_by="owner",
    source="test", reason="all clear",
)
chk(
    "clear_emergency_stop() under an env force-stop -> still_blocked_by_env=True",
    clear_result2.still_blocked_by_env is True,
)
chk(
    "clear_emergency_stop() under an env force-stop -> the durable write itself still succeeded",
    clear_result2.write.ok is True,
)


# ══════════════════════════════════════════════════════════════════
# 4. is_enabled()/set_flag() cutover (Step 6) — EMERGENCY_STOP_* names are
# now fully intercepted; every other name is completely unaffected.
# ══════════════════════════════════════════════════════════════════
print("\n── is_enabled()/set_flag() cutover (Step 6) ")

name = "EMERGENCY_STOP_ALL"

# No manager configured at all -> is_enabled() fails closed to True (never
# falls back to the legacy env/_RUNTIME path for this name).
feature_flags._reset_emergency_stop_manager_for_tests()
chk(
    "is_enabled() with no manager configured -> True (fail-closed, not env/_RUNTIME fallback)",
    feature_flags.is_enabled(name) is True,
)

# With a configured (fake) manager, is_enabled() reflects the manager's
# evaluate() exactly.
store_true = FakeStore(read_results=[ReadResult(status="ok", flags={
    n: FlagRecord(enabled=(n == name)) for n in feature_flags.KNOWN_EMERGENCY_STOP_FLAG_NAMES
})])
mgr4 = EmergencyStopManager(store=store_true, clock=FakeClock(), ttl_seconds=7.0)
feature_flags.configure_emergency_stop_manager(mgr4)
chk("is_enabled() delegates to the durable manager -> True when durably True", feature_flags.is_enabled(name) is True)
chk(
    "is_enabled() delegates to the durable manager -> False for a durably-False sibling flag",
    feature_flags.is_enabled("EMERGENCY_STOP_AI") is False,
)

# set_flag() is hard-blocked for all 5 canonical names.
for emergency_name in feature_flags.KNOWN_EMERGENCY_STOP_FLAG_NAMES:
    try:
        feature_flags.set_flag(emergency_name, True)
        chk(f"set_flag({emergency_name!r}, ...) raises EmergencyStopLegacyWriteBlocked", False)
    except feature_flags.EmergencyStopLegacyWriteBlocked:
        chk(f"set_flag({emergency_name!r}, ...) raises EmergencyStopLegacyWriteBlocked", True)

# A non-emergency flag is completely unaffected — same _RUNTIME behavior as
# always, no coupling to the manager at all.
other_name = "SOME_UNRELATED_TEST_FLAG"
feature_flags.set_flag(other_name, True)
chk("set_flag() on a non-emergency name still works normally", feature_flags._RUNTIME.get(other_name) is True)
chk("is_enabled() on a non-emergency name still reads _RUNTIME normally", feature_flags.is_enabled(other_name) is True)
feature_flags._RUNTIME.pop(other_name, None)

feature_flags._reset_emergency_stop_manager_for_tests()

# Structural proof (not just behavioral): is_enabled()/set_flag() DO
# reference the cutover machinery now — inverted from the old Step 3
# "byte-for-behavior unchanged" claim, which is no longer true post-cutover.
_is_enabled_src = inspect.getsource(feature_flags.is_enabled)
_set_flag_src = inspect.getsource(feature_flags.set_flag)
chk(
    "is_enabled()'s source references KNOWN_EMERGENCY_STOP_FLAG_NAMES (Step 6 cutover)",
    "KNOWN_EMERGENCY_STOP_FLAG_NAMES" in _is_enabled_src,
)
chk(
    "set_flag()'s source references KNOWN_EMERGENCY_STOP_FLAG_NAMES (Step 6 cutover)",
    "KNOWN_EMERGENCY_STOP_FLAG_NAMES" in _set_flag_src,
)
chk(
    "set_flag()'s source raises EmergencyStopLegacyWriteBlocked",
    "EmergencyStopLegacyWriteBlocked" in _set_flag_src,
)


# Leave the module unconfigured for whatever runs after this file.
feature_flags._reset_emergency_stop_manager_for_tests()


print(f"\n{'='*40}")
print(f"feature_flags emergency-stop Step 3 tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
