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
# 5. A bug INSIDE the adapter's own read() is still a documented outcome
#    at the bootstrap level — the adapter itself (Step 2.5 hardening)
#    already converts an unexpected exception during hydration into
#    ReadResult(status="invalid", error="internal_error: ..."), so it
#    never reaches bootstrap_emergency_stop() as a raised exception at
#    all. This is unchanged by the exception-policy fix below — it was
#    never "contained by bootstrap" to begin with, it's handled one layer
#    down, before bootstrap ever sees it.
# ══════════════════════════════════════════════════════════════════
print("\n── adapter-internal bug during hydration (documented at this layer) ")

with patch(
    f"{ADAPTER_MOD}.at_list_by_formula",
    side_effect=RuntimeError("simulated adapter bug, not a documented failure mode"),
):
    result = bootstrap_mod.bootstrap_emergency_stop()

chk("adapter-internal bug during hydration -> bootstrap does not raise", True)  # got here without an exception
chk("adapter-internal bug during hydration -> configured=True (manager still injected)", result.configured is True)
chk(
    "adapter-internal bug during hydration -> classified distinctly via the adapter's own hardening",
    result.store_status == "invalid" and "internal_error" in result.error,
)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 6. A GENUINELY unexpected failure during construction/configuration —
#    NOT a documented outcome (Airtable unavailable / invalid data) —
#    must PROPAGATE out of bootstrap_emergency_stop(), not be contained.
#    An unexpected bug here must be exposed loudly, not silently folded
#    into "just another degraded state" (see the module's exception
#    policy in its own docstring).
# ══════════════════════════════════════════════════════════════════
print("\n── unexpected construction/configuration error propagates ")

with patch.object(
    feature_flags,
    "configure_emergency_stop_manager",
    side_effect=feature_flags.EmergencyStopManagerConflict("simulated race"),
):
    with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
        m_list.return_value = _ALL_FLAGS_OK
        try:
            bootstrap_mod.bootstrap_emergency_stop()
            chk("configure() raising -> propagates out of bootstrap_emergency_stop() (does not swallow it)", False)
        except feature_flags.EmergencyStopManagerConflict as e:
            chk("configure() raising -> propagates out of bootstrap_emergency_stop() (does not swallow it)", True)
            chk("configure() raising -> the original exception reaches the caller intact", "simulated race" in str(e))

feature_flags._reset_emergency_stop_manager_for_tests()

# Same for a bug in the adapter/manager CONSTRUCTOR itself — e.g. a
# hypothetical future change that breaks known_flag_names validation.
# ValueError is EmergencyStopManager's own real documented error for
# empty known_flag_names (Step 2.5) — reused here as a stand-in for "any
# constructor bug", since it's a real exception type that construction
# can genuinely raise, not a contrived mock.
with patch(f"{ADAPTER_MOD}.AirtableEmergencyStopStore.__init__", side_effect=ValueError("simulated constructor bug")):
    try:
        bootstrap_mod.bootstrap_emergency_stop()
        chk("constructor raising -> propagates out of bootstrap_emergency_stop()", False)
    except ValueError as e:
        chk("constructor raising -> propagates out of bootstrap_emergency_stop()", True)
        chk("constructor raising -> the original exception reaches the caller intact", "simulated constructor bug" in str(e))

feature_flags._reset_emergency_stop_manager_for_tests()

feature_flags._reset_emergency_stop_manager_for_tests()


print(f"\n{'='*40}")
print(f"core/emergency_stop_bootstrap.py tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
