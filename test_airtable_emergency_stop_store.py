#!/usr/bin/env python3
"""
test_airtable_emergency_stop_store.py — PATCH 3B Step 2

Pure unit tests for adapters/airtable_emergency_stop_store.py. Every
tools.airtable_gateway call is mocked (unittest.mock.patch) — no network I/O,
no live Airtable base required. Mirrors test_core_emergency_stop.py's chk()
convention.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from adapters.airtable_emergency_stop_store import AirtableEmergencyStopStore
from tools.airtable_gateway import AirtableLookupError

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

KNOWN = ("EMERGENCY_STOP_ALL", "EMERGENCY_STOP_WHATSAPP")


def _rec(rec_id: str, name: str, enabled: bool | None = None, op_id: str = "op-1"):
    fields = {"Flag Name": name, "Operation ID": op_id}
    if enabled is not None:
        fields["Enabled"] = enabled
    return {"id": rec_id, "fields": fields}


# ══════════════════════════════════════════════════════════════════
# read() — success
# ══════════════════════════════════════════════════════════════════

print("\n── read(): success ──────────────────")

with patch(f"{MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [
        _rec("rec1", "EMERGENCY_STOP_ALL", True),
        _rec("rec2", "EMERGENCY_STOP_WHATSAPP", False),
    ]
    store = AirtableEmergencyStopStore(known_flag_names=KNOWN)
    result = store.read()
    chk("status == ok", result.status == "ok")
    chk("flags populated correctly", result.flags == {
        "EMERGENCY_STOP_ALL": True, "EMERGENCY_STOP_WHATSAPP": False,
    })
    chk("no error string on success", result.error == "")

with patch(f"{MOD}.at_list_by_formula") as m_list:
    # Airtable omits an unchecked checkbox key entirely.
    m_list.return_value = [
        _rec("rec1", "EMERGENCY_STOP_ALL"),  # no "Enabled" key at all
        _rec("rec2", "EMERGENCY_STOP_WHATSAPP", False),
    ]
    store = AirtableEmergencyStopStore(known_flag_names=KNOWN)
    result = store.read()
    chk("missing checkbox key -> treated as False, not invalid", result.status == "ok")
    chk("missing checkbox key -> flags[name] is False", result.flags["EMERGENCY_STOP_ALL"] is False)

# ══════════════════════════════════════════════════════════════════
# read() — unavailable
# ══════════════════════════════════════════════════════════════════

print("\n── read(): unavailable ──────────────")

with patch(f"{MOD}.at_list_by_formula", side_effect=AirtableLookupError("boom")):
    store = AirtableEmergencyStopStore(known_flag_names=KNOWN)
    result = store.read()
    chk("AirtableLookupError -> status=unavailable", result.status == "unavailable")
    chk("unavailable -> flags is None", result.flags is None)
    chk("unavailable -> error populated", "boom" in result.error)

with patch(f"{MOD}.at_list_by_formula", side_effect=RuntimeError("unexpected")):
    store = AirtableEmergencyStopStore(known_flag_names=KNOWN)
    result = store.read()
    chk("unexpected exception -> contained, not raised, status=unavailable", result.status == "unavailable")

# ══════════════════════════════════════════════════════════════════
# read() — invalid: bad type, duplicate, missing
# ══════════════════════════════════════════════════════════════════

print("\n── read(): invalid ──────────────────")

with patch(f"{MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [_rec("rec1", "EMERGENCY_STOP_ALL", "yes")]  # not a bool
    store = AirtableEmergencyStopStore(known_flag_names=KNOWN)
    result = store.read()
    chk("non-boolean Enabled -> status=invalid", result.status == "invalid")
    chk("non-boolean Enabled -> flags is None", result.flags is None)

with patch(f"{MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [
        _rec("rec1", "EMERGENCY_STOP_ALL", True),
        _rec("rec2", "EMERGENCY_STOP_ALL", False),  # duplicate Flag Name
    ]
    store = AirtableEmergencyStopStore(known_flag_names=KNOWN)
    result = store.read()
    chk("duplicate Flag Name -> status=invalid", result.status == "invalid")
    chk("duplicate Flag Name -> error mentions it", "EMERGENCY_STOP_ALL" in result.error)

with patch(f"{MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [_rec("rec1", "EMERGENCY_STOP_ALL", True)]  # WHATSAPP missing
    store = AirtableEmergencyStopStore(known_flag_names=KNOWN)
    result = store.read()
    chk("missing known flag -> status=invalid", result.status == "invalid")
    chk("missing known flag -> error names it", "EMERGENCY_STOP_WHATSAPP" in result.error)

with patch(f"{MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [{"id": "rec1", "fields": {"Enabled": True}}]  # blank Flag Name
    store = AirtableEmergencyStopStore(known_flag_names=KNOWN)
    result = store.read()
    chk("blank/missing Flag Name -> status=invalid", result.status == "invalid")

# no known_flag_names supplied -> "missing" check is vacuous, a clean read still succeeds
with patch(f"{MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [_rec("rec1", "EMERGENCY_STOP_ALL", True)]
    store = AirtableEmergencyStopStore()  # known_flag_names=()
    result = store.read()
    chk("no known_flag_names configured -> ok (no missing-check)", result.status == "ok")

# ══════════════════════════════════════════════════════════════════
# write() — success (update path) + readback verified
# ══════════════════════════════════════════════════════════════════

print("\n── write(): success, update path ────")

with patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_patch") as m_patch, \
     patch(f"{MOD}.airtable_create") as m_create:
    m_get.side_effect = [
        _rec("rec1", "EMERGENCY_STOP_ALL", False, op_id="op-old"),  # pre-write lookup
        _rec("rec1", "EMERGENCY_STOP_ALL", True, op_id="op-new"),   # readback
    ]
    m_patch.return_value = True
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="telegram", reason="test",
    )
    chk("update path -> airtable_create NOT called", m_create.call_count == 0)
    chk("update path -> airtable_patch called on existing record", m_patch.call_count == 1)
    chk("write ok=True", result.ok is True)
    chk("write verified=True (readback matches)", result.verified is True)

# ══════════════════════════════════════════════════════════════════
# write() — success (create path, no existing record)
# ══════════════════════════════════════════════════════════════════

print("\n── write(): success, create path ────")

with patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_patch") as m_patch, \
     patch(f"{MOD}.airtable_create") as m_create:
    m_get.side_effect = [
        None,  # pre-write lookup: no existing record
        _rec("rec9", "EMERGENCY_STOP_AI", True, op_id="op-1"),  # readback
    ]
    m_create.return_value = {"id": "rec9", "fields": {}}
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_AI", True,
        operation_id="op-1", updated_by="owner", source="telegram", reason="test",
    )
    chk("create path -> airtable_create called", m_create.call_count == 1)
    chk("create path -> airtable_patch NOT called", m_patch.call_count == 0)
    chk("create + verified readback -> ok=True, verified=True", result.ok and result.verified)

# ══════════════════════════════════════════════════════════════════
# write() — readback mismatch (verified=False, ok stays True)
# ══════════════════════════════════════════════════════════════════

print("\n── write(): readback mismatch ───────")

with patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_patch") as m_patch:
    m_get.side_effect = [
        _rec("rec1", "EMERGENCY_STOP_ALL", False, op_id="op-old"),
        _rec("rec1", "EMERGENCY_STOP_ALL", False, op_id="op-old"),  # readback shows stale state
    ]
    m_patch.return_value = True
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="telegram", reason="test",
    )
    chk("readback mismatch -> ok=True (gateway call succeeded)", result.ok is True)
    chk("readback mismatch -> verified=False", result.verified is False)
    chk("readback mismatch -> error explains why", "readback mismatch" in result.error)

with patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_patch") as m_patch:
    m_get.side_effect = [
        _rec("rec1", "EMERGENCY_STOP_ALL", False, op_id="op-old"),
        None,  # readback finds nothing at all
    ]
    m_patch.return_value = True
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="telegram", reason="test",
    )
    chk("readback finds no record -> verified=False", result.verified is False)

# ══════════════════════════════════════════════════════════════════
# write() — gateway write itself fails
# ══════════════════════════════════════════════════════════════════

print("\n── write(): gateway write fails ─────")

with patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_patch") as m_patch:
    m_get.return_value = _rec("rec1", "EMERGENCY_STOP_ALL", False, op_id="op-old")
    m_patch.return_value = False
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="telegram", reason="test",
    )
    chk("gateway patch returns False -> ok=False", result.ok is False)
    chk("gateway patch returns False -> verified=False", result.verified is False)

with patch(f"{MOD}.at_get_by_field", side_effect=AirtableLookupError("down")):
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="telegram", reason="test",
    )
    chk("pre-write lookup unavailable -> ok=False, verified=False", not result.ok and not result.verified)

# ══════════════════════════════════════════════════════════════════
# write() — expected_operation_id CAS check (conflict)
# ══════════════════════════════════════════════════════════════════

print("\n── write(): expected_operation_id CAS ")

with patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_patch") as m_patch:
    m_get.return_value = _rec("rec1", "EMERGENCY_STOP_ALL", False, op_id="op-actual")
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="telegram", reason="test",
        expected_operation_id="op-stale",
    )
    chk("stale expected_operation_id -> rejected before write", m_patch.call_count == 0)
    chk("stale expected_operation_id -> conflict=True", result.conflict is True)
    chk("stale expected_operation_id -> ok=False", result.ok is False)

with patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_patch") as m_patch:
    m_get.side_effect = [
        _rec("rec1", "EMERGENCY_STOP_ALL", False, op_id="op-actual"),
        _rec("rec1", "EMERGENCY_STOP_ALL", True, op_id="op-new"),
    ]
    m_patch.return_value = True
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="telegram", reason="test",
        expected_operation_id="op-actual",
    )
    chk("matching expected_operation_id -> write proceeds", m_patch.call_count == 1)
    chk("matching expected_operation_id -> verified True", result.verified is True)

# expected_operation_id given but no existing record at all -> not a conflict,
# just proceeds as a create (nothing to have raced against).
with patch(f"{MOD}.at_get_by_field") as m_get, \
     patch(f"{MOD}.airtable_create") as m_create:
    m_get.side_effect = [None, _rec("rec1", "EMERGENCY_STOP_ALL", True, op_id="op-new")]
    m_create.return_value = {"id": "rec1", "fields": {}}
    store = AirtableEmergencyStopStore()
    result = store.write(
        "EMERGENCY_STOP_ALL", True,
        operation_id="op-new", updated_by="owner", source="telegram", reason="test",
        expected_operation_id="op-doesnt-matter",
    )
    chk("expected_operation_id with no existing record -> proceeds as create, no conflict", not result.conflict)

# ══════════════════════════════════════════════════════════════════
# Boundary checks — importability + no forbidden coupling
# ══════════════════════════════════════════════════════════════════

print("\n── boundaries ────────────────────────")

import ast as _ast
import inspect as _inspect

import core.emergency_stop as _core_mod

_core_tree = _ast.parse(_inspect.getsource(_core_mod))
_core_imported_modules = {
    alias.name
    for node in _ast.walk(_core_tree)
    if isinstance(node, _ast.Import)
    for alias in node.names
} | {
    node.module
    for node in _ast.walk(_core_tree)
    if isinstance(node, _ast.ImportFrom) and node.module
}
chk(
    "core/emergency_stop.py has no actual import of adapters.*",
    not any(m == "adapters" or m.startswith("adapters.") for m in _core_imported_modules),
)

import adapters.airtable_emergency_stop_store as _adapter_mod
chk(
    "adapter implements EmergencyStopStore Protocol shape (read/write present)",
    hasattr(_adapter_mod.AirtableEmergencyStopStore, "read")
    and hasattr(_adapter_mod.AirtableEmergencyStopStore, "write"),
)


print(f"\n{'='*40}")
print(f"adapters/airtable_emergency_stop_store.py tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
