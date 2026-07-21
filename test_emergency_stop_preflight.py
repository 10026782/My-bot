#!/usr/bin/env python3
"""
test_emergency_stop_preflight.py — PATCH 3B Step 4

Tests core/emergency_stop_preflight.py's run_preflight(). Every Airtable
call is mocked (tools.airtable_gateway.get_table_schema for the schema
check, adapters.airtable_emergency_stop_store.at_list_by_formula for the
data check via the REAL adapter) — no network I/O, no live Airtable base.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

# ══════════════════════════════════════════════════════════════════
# 0. Importing this module does no I/O — checked before anything else in
# this file imports the adapter/gateway (fresh-process snapshot, matching
# CI's `for f in test_*.py; do python "$f"; done`).
# ══════════════════════════════════════════════════════════════════

_pre_import_modules = set(sys.modules)
import core.emergency_stop_preflight as preflight  # noqa: E402
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
    "importing the preflight does not import adapters.airtable_emergency_stop_store",
    "adapters.airtable_emergency_stop_store" not in _new_modules_from_import,
)
chk(
    "importing the preflight does not import tools.airtable_gateway",
    "tools.airtable_gateway" not in _new_modules_from_import,
)
chk(
    "importing the preflight does not import feature_flags",
    "feature_flags" not in _new_modules_from_import,
)

GATEWAY_MOD = "tools.airtable_gateway"
ADAPTER_MOD = "adapters.airtable_emergency_stop_store"


def _valid_schema(fields_override=None):
    fields = fields_override if fields_override is not None else [
        {"name": "Flag Name", "type": "singleLineText"},
        {"name": "Enabled", "type": "checkbox"},
        {"name": "Operation ID", "type": "singleLineText"},
        {"name": "Updated At", "type": "dateTime"},
        {"name": "Updated By", "type": "singleLineText"},
        {"name": "Source", "type": "singleLineText"},
        {"name": "Reason", "type": "multilineText"},
    ]
    return {"id": "tblXXX", "name": "Emergency Stop Flags", "fields": fields}


def _rec(rec_id, name, enabled=None, op_id="op-1"):
    fields = {"Flag Name": name, "Operation ID": op_id}
    if enabled is not None:
        fields["Enabled"] = enabled
    return {"id": rec_id, "fields": fields}


from core.emergency_stop import KNOWN_EMERGENCY_STOP_FLAG_NAMES  # noqa: E402

CANONICAL_FLAGS = sorted(KNOWN_EMERGENCY_STOP_FLAG_NAMES)


# ══════════════════════════════════════════════════════════════════
# 1. success — valid schema, all 5 flags present, no duplicates
# ══════════════════════════════════════════════════════════════════
print("\n── success ───────────────────────────")

with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=_valid_schema()) as m_schema, \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [_rec(f"rec{i}", name, True) for i, name in enumerate(CANONICAL_FLAGS)]
    code = preflight.run_preflight()
    chk("valid schema + valid data -> EXIT_OK", code == preflight.EXIT_OK)
    chk("schema was checked exactly once", m_schema.call_count == 1)
    chk("data was read exactly once", m_list.call_count == 1)


# ══════════════════════════════════════════════════════════════════
# 2. table missing -> EXIT_INVALID, adapter.read() never even attempted
# ══════════════════════════════════════════════════════════════════
print("\n── table missing ─────────────────────")

with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=None), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    code = preflight.run_preflight()
    chk("table missing -> EXIT_INVALID", code == preflight.EXIT_INVALID)
    chk("table missing -> adapter.read() is never reached", m_list.call_count == 0)


# ══════════════════════════════════════════════════════════════════
# 3. required field missing -> EXIT_INVALID
# ══════════════════════════════════════════════════════════════════
print("\n── required field missing ────────────")

_missing_reason = _valid_schema([f for f in _valid_schema()["fields"] if f["name"] != "Reason"])
with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=_missing_reason), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    code = preflight.run_preflight()
    chk("missing required field (Reason) -> EXIT_INVALID", code == preflight.EXIT_INVALID)
    chk("missing required field -> adapter.read() is never reached", m_list.call_count == 0)


# ══════════════════════════════════════════════════════════════════
# 4. invalid field type -> EXIT_INVALID
# ══════════════════════════════════════════════════════════════════
print("\n── invalid field type ────────────────")

_bad_enabled_type = _valid_schema([
    {"name": "Flag Name", "type": "singleLineText"},
    {"name": "Enabled", "type": "singleSelect"},  # should be checkbox
    {"name": "Operation ID", "type": "singleLineText"},
    {"name": "Updated At", "type": "dateTime"},
    {"name": "Updated By", "type": "singleLineText"},
    {"name": "Source", "type": "singleLineText"},
    {"name": "Reason", "type": "multilineText"},
])
with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=_bad_enabled_type), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    code = preflight.run_preflight()
    chk("Enabled field wrong type (singleSelect, not checkbox) -> EXIT_INVALID", code == preflight.EXIT_INVALID)
    chk("invalid field type -> adapter.read() is never reached", m_list.call_count == 0)


# ══════════════════════════════════════════════════════════════════
# 5. one flag missing -> EXIT_INVALID (schema valid, data incomplete)
# ══════════════════════════════════════════════════════════════════
print("\n── one flag missing ──────────────────")

with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=_valid_schema()), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    m_list.return_value = [_rec(f"rec{i}", name, True) for i, name in enumerate(CANONICAL_FLAGS[:-1])]
    code = preflight.run_preflight()
    chk("one of 5 canonical flags missing -> EXIT_INVALID", code == preflight.EXIT_INVALID)


# ══════════════════════════════════════════════════════════════════
# 6. duplicate flag -> EXIT_INVALID
# ══════════════════════════════════════════════════════════════════
print("\n── duplicate flag ────────────────────")

with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=_valid_schema()), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    recs = [_rec(f"rec{i}", name, True) for i, name in enumerate(CANONICAL_FLAGS)]
    recs.append(_rec("recDUP", CANONICAL_FLAGS[0], False))  # duplicate
    m_list.return_value = recs
    code = preflight.run_preflight()
    chk("duplicate Flag Name record -> EXIT_INVALID", code == preflight.EXIT_INVALID)


# ══════════════════════════════════════════════════════════════════
# 7. invalid Enabled value -> EXIT_INVALID
# ══════════════════════════════════════════════════════════════════
print("\n── invalid Enabled value ─────────────")

with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=_valid_schema()), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    recs = [_rec(f"rec{i}", name, True) for i, name in enumerate(CANONICAL_FLAGS)]
    recs[0]["fields"]["Enabled"] = "yes"  # not a bool
    m_list.return_value = recs
    code = preflight.run_preflight()
    chk("non-boolean Enabled value -> EXIT_INVALID", code == preflight.EXIT_INVALID)


# ══════════════════════════════════════════════════════════════════
# 8. Airtable unavailable — both failure points
# ══════════════════════════════════════════════════════════════════
print("\n── Airtable unavailable ──────────────")

from tools.airtable_gateway import AirtableLookupError  # noqa: E402

with patch(f"{GATEWAY_MOD}.get_table_schema", side_effect=AirtableLookupError("down")), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    code = preflight.run_preflight()
    chk("schema check unavailable -> EXIT_UNAVAILABLE", code == preflight.EXIT_UNAVAILABLE)
    chk("schema unavailable -> adapter.read() never reached", m_list.call_count == 0)

with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=_valid_schema()), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula", side_effect=AirtableLookupError("down")):
    code = preflight.run_preflight()
    chk("data read unavailable (schema was fine) -> EXIT_UNAVAILABLE", code == preflight.EXIT_UNAVAILABLE)


# ══════════════════════════════════════════════════════════════════
# 9. unexpected internal error -> clear failure, NEVER success
# ══════════════════════════════════════════════════════════════════
print("\n── unexpected internal error ─────────")

with patch(f"{GATEWAY_MOD}.get_table_schema", side_effect=RuntimeError("bug, not a network error")), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list:
    code = preflight.run_preflight()
    chk("unexpected exception in schema check -> EXIT_INTERNAL_ERROR (never EXIT_OK)", code == preflight.EXIT_INTERNAL_ERROR)
    chk("EXIT_INTERNAL_ERROR is distinct from EXIT_OK", preflight.EXIT_INTERNAL_ERROR != preflight.EXIT_OK)

with patch(f"{GATEWAY_MOD}.get_table_schema", return_value=_valid_schema()), \
     patch(f"{ADAPTER_MOD}.at_list_by_formula", side_effect=TypeError("a real bug")):
    code = preflight.run_preflight()
    chk(
        "unexpected exception surfacing through the adapter -> a clear non-OK exit "
        "(EXIT_INTERNAL_ERROR or EXIT_INVALID, both non-zero and non-success)",
        code in (preflight.EXIT_INTERNAL_ERROR, preflight.EXIT_INVALID) and code != preflight.EXIT_OK,
    )


# ══════════════════════════════════════════════════════════════════
# 10. exit-code sanity — every non-OK code is genuinely non-zero
# ══════════════════════════════════════════════════════════════════
print("\n── exit code sanity ──────────────────")

chk("EXIT_OK == 0", preflight.EXIT_OK == 0)
chk("EXIT_INTERNAL_ERROR, EXIT_UNAVAILABLE, EXIT_INVALID are all non-zero and distinct", len({
    preflight.EXIT_INTERNAL_ERROR, preflight.EXIT_UNAVAILABLE, preflight.EXIT_INVALID,
}) == 3 and 0 not in {preflight.EXIT_INTERNAL_ERROR, preflight.EXIT_UNAVAILABLE, preflight.EXIT_INVALID})


print(f"\n{'='*40}")
print(f"core/emergency_stop_preflight.py tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
