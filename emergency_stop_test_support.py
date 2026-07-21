"""
emergency_stop_test_support.py — PATCH 3B Step 6 shared test helper.

NOT itself a test_*.py file (deliberately named without that prefix) — CI's
`for f in test_*.py; do python "$f"; done` loop would otherwise try to
execute this as a standalone test script.

After the Step 6 cutover, is_enabled() for the 5 canonical EMERGENCY_STOP_*
names delegates to evaluate_emergency_stop(), which fails closed to
blocked=True when no EmergencyStopManager is configured (see
feature_flags.is_enabled()'s own docstring). Many existing tests exercise
app.py/tools/dispatcher.py code paths that incidentally call is_enabled()
for these names — e.g. the CostWatchdog gate checking EMERGENCY_STOP_AI —
without caring about emergency-stop behavior at all. Those tests need an
"all clear" manager configured so they see blocked=False, matching what
they were written against before this cutover existed.
"""

from __future__ import annotations

import feature_flags
from core.emergency_stop import EmergencyStopManager, FlagRecord, ReadResult, WriteResult


class _AllClearStore:
    """A trivial EmergencyStopStore double: every known flag reads back
    False forever, and write() is not exercised by these tests."""

    def read(self) -> ReadResult:
        return ReadResult(status="ok", flags={
            name: FlagRecord(enabled=False)
            for name in feature_flags.KNOWN_EMERGENCY_STOP_FLAG_NAMES
        })

    def write(self, *a, **kw) -> WriteResult:
        raise NotImplementedError("not exercised by emergency_stop_test_support's all-clear manager")


def configure_all_clear_emergency_stop() -> None:
    """
    Configure a fake EmergencyStopManager where all 5 canonical flags read
    durably False — restores the pre-Step-6-cutover default ("nothing is
    emergency-stopped") for tests that don't care about emergency-stop
    behavior specifically. Idempotent: safe to call even if a manager is
    already configured (feature_flags._reset_emergency_stop_manager_for_tests()
    first if a fresh one is needed).
    """
    feature_flags._reset_emergency_stop_manager_for_tests()
    manager = EmergencyStopManager(store=_AllClearStore())
    feature_flags.configure_emergency_stop_manager(manager)
