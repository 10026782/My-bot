#!/usr/bin/env python3
"""
test_emergency_stop_contract.py — PATCH 3B Step 2.5 contract hardening.

Two things Step 1's and Step 2's own unit tests each proved in isolation but
never proved *together*:

1. AirtableEmergencyStopStore.read/write actually match the shape of
   core.emergency_stop.EmergencyStopStore's Protocol methods — not "close
   enough", but the exact same signature (param names, kinds, annotations,
   defaults) — via inspect.signature comparison.

2. A REAL EmergencyStopManager wired to a REAL AirtableEmergencyStopStore,
   driven only through the manager's public API (evaluate()/status()) —
   never calling the adapter directly — behaves correctly end-to-end. Only
   tools.airtable_gateway's own I/O calls are mocked; everything above that
   (adapter parsing/validation, manager caching/TTL/precedence) is real code
   exercising real code, not two isolated unit-test suites that happen to
   agree on paper.
"""

from __future__ import annotations

import inspect
import sys
from unittest.mock import patch

from adapters.airtable_emergency_stop_store import AirtableEmergencyStopStore
from core.emergency_stop import (
    KNOWN_EMERGENCY_STOP_FLAG_NAMES,
    EmergencyStopManager,
    EmergencyStopStore,
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


MOD = "adapters.airtable_emergency_stop_store"


class FakeClock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _rec(rec_id: str, name: str, enabled: bool, op_id: str = "op-1") -> dict:
    return {"id": rec_id, "fields": {"Flag Name": name, "Enabled": enabled, "Operation ID": op_id}}


# ══════════════════════════════════════════════════════════════════
# 1. Signature conformance — AirtableEmergencyStopStore vs the Protocol
# ══════════════════════════════════════════════════════════════════
print("\n── signature conformance ─────────────")

chk(
    "AirtableEmergencyStopStore.read() signature matches EmergencyStopStore.read() exactly",
    inspect.signature(EmergencyStopStore.read) == inspect.signature(AirtableEmergencyStopStore.read),
)
chk(
    "AirtableEmergencyStopStore.write() signature matches EmergencyStopStore.write() exactly",
    inspect.signature(EmergencyStopStore.write) == inspect.signature(AirtableEmergencyStopStore.write),
)

# EmergencyStopStore is deliberately not @runtime_checkable (see
# core/emergency_stop.py) — isinstance() against it would either raise or
# only check method presence, not signature shape, so it wouldn't add
# anything the two checks above don't already prove more precisely.
chk("EmergencyStopStore is a Protocol", getattr(EmergencyStopStore, "_is_protocol", False) is True)


# ══════════════════════════════════════════════════════════════════
# 2. End-to-end happy path: real Manager + real Adapter, gateway mocked
# ══════════════════════════════════════════════════════════════════
print("\n── manager + adapter, gateway mocked ─")

clock = FakeClock()

with patch(f"{MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [
        _rec(f"rec{i}", name, name == "EMERGENCY_STOP_ALL")
        for i, name in enumerate(sorted(KNOWN_EMERGENCY_STOP_FLAG_NAMES))
    ]
    store = AirtableEmergencyStopStore()  # real adapter, default known_flag_names
    mgr = EmergencyStopManager(store=store, clock=clock, ttl_seconds=7.0)  # real manager

    ev = mgr.evaluate("EMERGENCY_STOP_ALL")
    chk("evaluate() through the real adapter -> blocked=True (matches mocked Enabled)", ev.blocked is True)
    chk("evaluate() through the real adapter -> source=durable (fresh hydrate)", ev.source == "durable")
    chk("evaluate() through the real adapter -> store_status=ok", ev.store_status == "ok")
    chk("exactly one gateway call for the first evaluate()", m_list.call_count == 1)

    ev2 = mgr.evaluate("EMERGENCY_STOP_WHATSAPP")
    chk("a different known flag from the same hydrate -> blocked=False", ev2.blocked is False)
    chk("still only one gateway call (cache hit, not stale yet)", m_list.call_count == 1)

    st = mgr.status()
    chk(
        "status() through the real adapter -> all 5 known flags present",
        set(st.flags) == KNOWN_EMERGENCY_STOP_FLAG_NAMES,
    )
    chk("status() store_status == ok", st.store_status == "ok")

    # Advance past TTL -> next evaluate() triggers exactly one more real
    # store.read() (single-flight/staleness logic is Step 1's own code,
    # running for real here, not re-tested in depth — just proven wired up).
    clock.advance(10.0)
    m_list.return_value = [
        _rec(f"rec{i}", name, name != "EMERGENCY_STOP_ALL")  # flip every value
        for i, name in enumerate(sorted(KNOWN_EMERGENCY_STOP_FLAG_NAMES))
    ]
    ev3 = mgr.evaluate("EMERGENCY_STOP_ALL")
    chk("stale cache -> exactly one more gateway call on next evaluate()", m_list.call_count == 2)
    chk("stale cache -> refreshed value reflects the new mocked read", ev3.blocked is False)


# ══════════════════════════════════════════════════════════════════
# 3. End-to-end: adapter reports "invalid" -> manager fails closed, never
#    mistakes a data-integrity problem for a trustworthy hydrate
# ══════════════════════════════════════════════════════════════════
print("\n── manager fail-closed on adapter invalid ")

clock2 = FakeClock()
with patch(f"{MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [_rec("rec1", "EMERGENCY_STOP_ALL", True)]  # only 1 of 5 known flags
    store = AirtableEmergencyStopStore()
    mgr = EmergencyStopManager(store=store, clock=clock2, ttl_seconds=7.0)

    ev = mgr.evaluate("EMERGENCY_STOP_ALL")
    chk("adapter status=invalid -> manager never hydrates its cache", ev.source == "unknown")
    chk("adapter status=invalid -> manager fails closed (blocked=True)", ev.blocked is True)

    st = mgr.status()
    chk("adapter status=invalid -> status().store_status == invalid", st.store_status == "invalid")
    chk("adapter status=invalid -> the missing-record diagnostic reaches status()",
        "EMERGENCY_STOP_WHATSAPP" in (st.error or ""))


# ══════════════════════════════════════════════════════════════════
# 4. End-to-end: adapter's AirtableLookupError -> manager sees "unavailable"
# ══════════════════════════════════════════════════════════════════
print("\n── manager sees adapter's unavailable ")

from tools.airtable_gateway import AirtableLookupError  # noqa: E402 — grouped near use, matches repo convention

clock3 = FakeClock()
with patch(f"{MOD}.at_list_by_formula", side_effect=AirtableLookupError("down")):
    store = AirtableEmergencyStopStore()
    mgr = EmergencyStopManager(store=store, clock=clock3, ttl_seconds=7.0)
    ev = mgr.evaluate("EMERGENCY_STOP_ALL")
    chk("adapter unavailable -> manager fails closed (blocked=True)", ev.blocked is True)
    chk("adapter unavailable -> manager reports source=unknown (never hydrated)", ev.source == "unknown")
    chk("adapter unavailable -> status_store reflects it", mgr.status().store_status == "unavailable")


# ══════════════════════════════════════════════════════════════════
# 5. End-to-end: manager.write() through the real adapter -> real gateway
#    calls mocked, cache invalidation proven with a real subsequent read
# ══════════════════════════════════════════════════════════════════
print("\n── manager.write() through the real adapter ")

clock4 = FakeClock()
with patch(f"{MOD}.at_list_by_formula") as m_list, \
     patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_patch") as m_patch:
    m_list.side_effect = [
        [_rec("rec1", "EMERGENCY_STOP_ALL", False)],  # pre-write hydrate
        [_rec("rec1", "EMERGENCY_STOP_ALL", True)],   # post-write re-hydrate
    ]
    m_get.side_effect = [
        _rec("rec1", "EMERGENCY_STOP_ALL", False, op_id="op-old"),  # pre-write lookup
        _rec("rec1", "EMERGENCY_STOP_ALL", True, op_id="op-new"),   # readback
    ]
    m_patch.return_value = True

    store = AirtableEmergencyStopStore(known_flag_names={"EMERGENCY_STOP_ALL"})
    mgr = EmergencyStopManager(store=store, clock=clock4, ttl_seconds=7.0)

    ev_before = mgr.evaluate("EMERGENCY_STOP_ALL")
    chk("pre-write evaluate() through the real adapter -> blocked=False", ev_before.blocked is False)

    wr = mgr.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="test", reason="turn it on",
    )
    chk("manager.write() through the real adapter -> ok=True, verified=True", wr.ok and wr.verified)
    chk("manager.write() called the real gateway patch call", m_patch.call_count == 1)

    ev_after = mgr.evaluate("EMERGENCY_STOP_ALL")
    chk("evaluate() after write() re-reads through the real adapter", m_list.call_count == 2)
    chk("evaluate() after write() reflects the new durable value", ev_after.blocked is True)


print(f"\n{'='*40}")
print(f"emergency_stop contract tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
