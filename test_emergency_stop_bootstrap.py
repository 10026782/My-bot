#!/usr/bin/env python3
"""
test_emergency_stop_bootstrap.py — PATCH 3B Step 5

Tests core/emergency_stop_bootstrap.py's bootstrap_emergency_stop(): the
one explicit startup-path function app.py calls to construct+configure+
hydrate the EmergencyStopManager. Every Airtable call is mocked at the
gateway level (adapters.airtable_emergency_stop_store.at_list_by_formula)
— no network I/O, no live Airtable base.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

# ══════════════════════════════════════════════════════════════════
# 0. Importing this module does no I/O — checked before anything else in
# this file imports the adapter/gateway/feature_flags (fresh-process
# snapshot, matching CI's `for f in test_*.py; do python "$f"; done`).
# ══════════════════════════════════════════════════════════════════

_pre_import_modules = set(sys.modules)
import core.emergency_stop_bootstrap as bootstrap_mod  # noqa: E402
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
    "importing the bootstrap module does not import adapters.airtable_emergency_stop_store",
    "adapters.airtable_emergency_stop_store" not in _new_modules_from_import,
)
chk(
    "importing the bootstrap module does not import tools.airtable_gateway",
    "tools.airtable_gateway" not in _new_modules_from_import,
)
chk(
    "importing the bootstrap module does not import feature_flags",
    "feature_flags" not in _new_modules_from_import,
)

import feature_flags  # noqa: E402

ADAPTER_MOD = "adapters.airtable_emergency_stop_store"


def _rec(rec_id, name, enabled):
    return {"id": rec_id, "fields": {"Flag Name": name, "Enabled": enabled, "Operation ID": "op-1"}}


from core.emergency_stop import KNOWN_EMERGENCY_STOP_FLAG_NAMES  # noqa: E402

_ALL_FLAGS_OK = [_rec(f"rec{i}", name, False) for i, name in enumerate(sorted(KNOWN_EMERGENCY_STOP_FLAG_NAMES))]


# ══════════════════════════════════════════════════════════════════
# 1. Successful configure + hydration
# ══════════════════════════════════════════════════════════════════
print("\n── successful configure + hydration ──")

feature_flags._reset_emergency_stop_manager_for_tests()

with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    m_list.return_value = _ALL_FLAGS_OK
    result = bootstrap_mod.bootstrap_emergency_stop()

chk("successful bootstrap -> configured=True", result.configured is True)
chk("successful bootstrap -> store_status=ok", result.store_status == "ok")
chk("successful bootstrap -> flags_loaded=5", result.flags_loaded == 5)
chk("successful bootstrap -> no error", result.error == "")
chk(
    "successful bootstrap -> feature_flags reports configured",
    feature_flags.get_emergency_stop_status().configured is True,
)
chk(
    "successful bootstrap -> evaluate_emergency_stop() works through the manager",
    feature_flags.evaluate_emergency_stop("EMERGENCY_STOP_ALL").source == "durable",
)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 2. Airtable unavailable — manager stays configured, fails closed
# ══════════════════════════════════════════════════════════════════
print("\n── unavailable ────────────────────────")

from tools.airtable_gateway import AirtableLookupError  # noqa: E402

with patch(f"{ADAPTER_MOD}.at_list_by_formula", side_effect=AirtableLookupError("down")):
    result = bootstrap_mod.bootstrap_emergency_stop()

chk("unavailable -> configured=True (manager still injected)", result.configured is True)
chk("unavailable -> store_status=unavailable", result.store_status == "unavailable")
chk("unavailable -> flags_loaded=0", result.flags_loaded == 0)
chk("unavailable -> error populated", "down" in result.error)

status = feature_flags.get_emergency_stop_status()
chk("unavailable -> feature_flags still reports configured=True", status.configured is True)
ev = feature_flags.evaluate_emergency_stop("EMERGENCY_STOP_ALL")
chk("unavailable -> evaluate_emergency_stop() fails closed (blocked=True)", ev.blocked is True)
chk("unavailable -> source=unknown (never hydrated, no stale cache to fall back to)", ev.source == "unknown")

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 3. Schema/data invalid — no optimistic false defaults
# ══════════════════════════════════════════════════════════════════
print("\n── invalid ────────────────────────────")

with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [_rec("rec1", "EMERGENCY_STOP_ALL", True)]  # only 1 of 5 known flags
    result = bootstrap_mod.bootstrap_emergency_stop()

chk("invalid -> configured=True (manager still injected)", result.configured is True)
chk("invalid -> store_status=invalid", result.store_status == "invalid")
chk("invalid -> flags_loaded=0", result.flags_loaded == 0)
chk("invalid -> error names the missing flags", "EMERGENCY_STOP_WHATSAPP" in result.error)

ev = feature_flags.evaluate_emergency_stop("EMERGENCY_STOP_ALL")
chk(
    "invalid -> evaluate_emergency_stop() never optimistically defaults to False (fails closed)",
    ev.blocked is True,
)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 4. Double-startup idempotency
# ══════════════════════════════════════════════════════════════════
print("\n── double-startup idempotency ────────")

with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    m_list.return_value = _ALL_FLAGS_OK
    first = bootstrap_mod.bootstrap_emergency_stop()
    manager_after_first = feature_flags._emergency_stop_manager

    second = bootstrap_mod.bootstrap_emergency_stop()  # called again — must not construct a new manager
    manager_after_second = feature_flags._emergency_stop_manager

chk("second bootstrap call -> only one gateway read total (no re-hydration)", m_list.call_count == 1)
chk("second bootstrap call -> same manager instance (no reconfigure)", manager_after_first is manager_after_second)
chk("second bootstrap call -> reports configured=True", second.configured is True)
chk("second bootstrap call -> reports the same store_status as the first", second.store_status == first.store_status)
chk("second bootstrap call -> does not raise EmergencyStopManagerConflict", True)  # got here without an exception

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 5. Unexpected internal error during bootstrap -> never raises, never
#    silently looks like success ("app remains startable")
# ══════════════════════════════════════════════════════════════════
print("\n── unexpected internal error (app must stay startable) ")

with patch(
    f"{ADAPTER_MOD}.at_list_by_formula",
    side_effect=RuntimeError("simulated adapter bug, not a documented failure mode"),
):
    result = bootstrap_mod.bootstrap_emergency_stop()

chk("unexpected exception during hydration -> bootstrap does not raise", True)  # got here without an exception
chk("unexpected exception during hydration -> configured=True (manager still injected)", result.configured is True)
chk(
    "unexpected exception during hydration -> classified distinctly (not silently EXIT_OK-shaped)",
    result.store_status == "invalid" and "internal_error" in result.error,
)

feature_flags._reset_emergency_stop_manager_for_tests()

# configure_emergency_stop_manager() itself raising (e.g. a genuine TOCTOU
# race between the idempotency check and the configure() call — not
# reachable today with the single real caller, but the defensive try/except
# around it must still work if a future caller ever triggers it) must be
# contained, not propagated.
with patch.object(
    feature_flags,
    "configure_emergency_stop_manager",
    side_effect=feature_flags.EmergencyStopManagerConflict("simulated race"),
):
    with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
        m_list.return_value = _ALL_FLAGS_OK
        result = bootstrap_mod.bootstrap_emergency_stop()

chk("configure() raising is contained, not propagated (bootstrap does not raise)", True)
chk("configure() raising -> configured=False", result.configured is False)
chk("configure() raising -> error surfaced", "simulated race" in result.error)

feature_flags._reset_emergency_stop_manager_for_tests()


print(f"\n{'='*40}")
print(f"core/emergency_stop_bootstrap.py tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
