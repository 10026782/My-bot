#!/usr/bin/env python3
"""
test_health_monitor_emergency_stop.py — PATCH 3B Step 5

Tests health_monitor.py's new _check_emergency_stop_manager() and its
effect on get_health_status()'s overall status. Does not touch
_check_emergency() (the legacy is_enabled("EMERGENCY_STOP_ALL") check) —
that stays unchanged, still governs nothing new, still the only thing
production actually reads.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import feature_flags
import health_monitor
from adapters.airtable_emergency_stop_store import AirtableEmergencyStopStore
from core.emergency_stop import EmergencyStopManager, KNOWN_EMERGENCY_STOP_FLAG_NAMES

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


ADAPTER_MOD = "adapters.airtable_emergency_stop_store"


def _rec(rec_id, name, enabled):
    return {"id": rec_id, "fields": {"Flag Name": name, "Enabled": enabled, "Operation ID": "op-1"}}


_ALL_FLAGS_OK = [_rec(f"rec{i}", name, False) for i, name in enumerate(sorted(KNOWN_EMERGENCY_STOP_FLAG_NAMES))]


class _FakeClock:
    def __call__(self) -> float:
        return 1000.0


# ══════════════════════════════════════════════════════════════════
# 1. Not configured -> degraded, not silently "healthy"
# ══════════════════════════════════════════════════════════════════
print("\n── not configured ─────────────────────")

feature_flags._reset_emergency_stop_manager_for_tests()

ok, detail = health_monitor._check_emergency_stop_manager()
chk("not configured -> ok=False", ok is False)
chk("not configured -> detail says so", detail == "not configured")


# ══════════════════════════════════════════════════════════════════
# 2. Configured + durable (ok) -> healthy, names the flag count
# ══════════════════════════════════════════════════════════════════
print("\n── configured, durable ─────────────────")

with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    m_list.return_value = _ALL_FLAGS_OK
    store = AirtableEmergencyStopStore()
    manager = EmergencyStopManager(store=store, clock=_FakeClock())
    feature_flags.configure_emergency_stop_manager(manager)

    ok, detail = health_monitor._check_emergency_stop_manager()
    chk("durable -> ok=True", ok is True)
    chk("durable -> detail names the flag count", "5" in detail and "durable" in detail)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 3. Configured + unavailable -> degraded, not "healthy as usual"
# ══════════════════════════════════════════════════════════════════
print("\n── configured, unavailable ─────────────")

from tools.airtable_gateway import AirtableLookupError  # noqa: E402

with patch(f"{ADAPTER_MOD}.at_list_by_formula", side_effect=AirtableLookupError("down")):
    store = AirtableEmergencyStopStore()
    manager = EmergencyStopManager(store=store, clock=_FakeClock())
    feature_flags.configure_emergency_stop_manager(manager)

    ok, detail = health_monitor._check_emergency_stop_manager()
    chk("unavailable -> ok=False (degraded, not healthy)", ok is False)
    chk("unavailable -> detail mentions fail-closed policy", "fail-closed" in detail or "unavailable" in detail)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 4. Configured + invalid -> degraded, shows "invalid"
# ══════════════════════════════════════════════════════════════════
print("\n── configured, invalid ─────────────────")

with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [_rec("rec1", "EMERGENCY_STOP_ALL", True)]  # only 1 of 5
    store = AirtableEmergencyStopStore()
    manager = EmergencyStopManager(store=store, clock=_FakeClock())
    feature_flags.configure_emergency_stop_manager(manager)

    ok, detail = health_monitor._check_emergency_stop_manager()
    chk("invalid -> ok=False", ok is False)
    chk("invalid -> detail explicitly says invalid", "invalid" in detail)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 5. get_health_status() overall status reflects the new check —
# unavailable/invalid must flip the TOP-LEVEL status to "degraded"
# ══════════════════════════════════════════════════════════════════
print("\n── get_health_status() overall effect ──")

with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "x", "TELEGRAM_TOKEN": "x"}), \
     patch.object(health_monitor, "_check_airtable", return_value=(True, "ok")), \
     patch.object(health_monitor, "_check_scheduler", return_value=(True, "1 jobs")), \
     patch.object(health_monitor, "_check_emergency", return_value=(True, "clear")):

    with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
        m_list.return_value = _ALL_FLAGS_OK
        store = AirtableEmergencyStopStore()
        manager = EmergencyStopManager(store=store, clock=_FakeClock())
        feature_flags.configure_emergency_stop_manager(manager)
        status_ok = health_monitor.get_health_status()
    chk("all-clear including durable EmergencyStopManager -> overall status=ok", status_ok["status"] == "ok")
    chk(
        "get_health_status() exposes emergency_stop_manager_ok/detail in checks",
        "emergency_stop_manager_ok" in status_ok["checks"] and "emergency_stop_manager_detail" in status_ok["checks"],
    )

    feature_flags._reset_emergency_stop_manager_for_tests()

    with patch(f"{ADAPTER_MOD}.at_list_by_formula", side_effect=AirtableLookupError("down")):
        store2 = AirtableEmergencyStopStore()
        manager2 = EmergencyStopManager(store=store2, clock=_FakeClock())
        feature_flags.configure_emergency_stop_manager(manager2)
        status_degraded = health_monitor.get_health_status()
    chk(
        "EmergencyStopManager unavailable -> overall status flips to degraded "
        "even though every OTHER check is fine",
        status_degraded["status"] == "degraded",
    )
    chk(
        "legacy emergency_clear check is untouched by the new manager's state",
        status_degraded["checks"]["emergency_clear"] is True,
    )

feature_flags._reset_emergency_stop_manager_for_tests()


print(f"\n{'='*40}")
print(f"health_monitor.py emergency-stop tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
