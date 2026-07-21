#!/usr/bin/env python3
"""
test_cost_watchdog_airtable_write.py — Regression tests for
core/cost_watchdog.py::_write_airtable_row() (Cost Telemetry Reliability
PR series, PR1 + hotfix).

Three bugs this guards against:
  1. "Success logged without checking the write result" — it used to log
     "שורה יומית נכתבה ל-Airtable" unconditionally right after calling
     airtable_create(), never inspecting its return value. airtable_create()
     returns None (not an exception) on any non-2xx HTTP response, so the
     live 422 UNKNOWN_FIELD_NAME this table hit for weeks was reported as
     success every single day.
  2. "Create-only instead of upsert" — it always called airtable_create(),
     so re-running daily_watchdog() for a date that already has a row (a
     manual retry, a scheduler double-fire) silently created a SECOND row
     for the same date.
  3. HOTFIX — the upsert lookup used at_get_by_field(table, "Date",
     date_str), building {Date}='YYYY-MM-DD': plain text equality against
     an Airtable DATE field, which never matches. Every call took the
     create branch — production smoke showed 2 runs producing 2 rows, then
     4 rows on a repeat. Fixed to at_list_by_formula() with
     DATETIME_FORMAT({Date}, 'YYYY-MM-DD')='<date_str>' and max_records=2,
     so an existing row is actually found, and an already-existing
     duplicate is detected (2+ matches) rather than patched arbitrarily.

Verifies:
  1. The lookup formula sent to at_list_by_formula() uses DATETIME_FORMAT,
     not a bare {Date}='...' text-equality formula.
  2. 0 matches => airtable_create() is called, airtable_patch() is not.
  3. 1 match => airtable_patch() is called with that record's id,
     airtable_create() is not.
  4. 2+ matches => neither create nor patch is called; returns False (a
     data-integrity problem, not a normal upsert case).
  5. A lookup failure (AirtableLookupError — network/HTTP, not "genuinely
     not found") refuses to touch Airtable further; returns False.
  6. A malformed date_str never reaches Airtable at all (no lookup, no
     create, no patch).
  7. airtable_create() -> None and airtable_patch() -> False both remain
     truthful failures (no success log, returns False).
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import patch

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(record.getMessage())


def _run_write(*, date_str="2026-07-21", matches=None, create_return=None,
                patch_return=None, lookup_raises=None):
    from core.cost_watchdog import _write_airtable_row
    from tools.airtable_gateway import AirtableLookupError

    handler = _CaptureHandler()
    logger = logging.getLogger("core.cost_watchdog")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    lookup_kwargs = (
        {"side_effect": lookup_raises} if lookup_raises
        else {"return_value": matches if matches is not None else []}
    )

    try:
        with patch("tools.airtable_gateway.at_list_by_formula", **lookup_kwargs) as mock_lookup, \
             patch("tools.airtable_gateway.airtable_create", return_value=create_return) as mock_create, \
             patch("tools.airtable_gateway.airtable_patch", return_value=patch_return) as mock_patch:
            result = _write_airtable_row(date_str, {
                "claude_sonnet": 10, "claude_haiku": 20,
                "whatsapp_conversation": 0, "total_units": 30,
            })
    finally:
        logger.removeHandler(handler)
    return result, handler.records, mock_lookup, mock_create, mock_patch


print("\n── _write_airtable_row() date-aware lookup + upsert branching ────────────────")

# 1. The lookup formula must use DATETIME_FORMAT, not bare {Date}='...'.
result, logs, mock_lookup, mock_create, mock_patch = _run_write(matches=[])
formula_used = mock_lookup.call_args[0][1]
chk("lookup uses DATETIME_FORMAT({Date}, 'YYYY-MM-DD') formula",
    "DATETIME_FORMAT({Date}, 'YYYY-MM-DD')" in formula_used)
chk("lookup does NOT use bare text-equality {Date}='...' formula",
    "{Date}='2026-07-21'" not in formula_used)
chk("lookup requests max_records=2 (to detect duplicates, not just find one)",
    mock_lookup.call_args.kwargs.get("max_records") == 2 or
    (len(mock_lookup.call_args[0]) > 2 and mock_lookup.call_args[0][2] == 2))

# 2. 0 matches => create only.
fake_record = {"id": "recFAKE123", "fields": {"Date": "2026-07-21"}}
result, logs, mock_lookup, mock_create, mock_patch = _run_write(matches=[], create_return=fake_record)
chk("0 matches + create()->record => returns True", result is True)
chk("0 matches => airtable_create() called", mock_create.called)
chk("0 matches => airtable_patch() NOT called", not mock_patch.called)
chk("success log includes branch=create", any("branch=create" in l for l in logs))
chk("success log includes the record id", any("recFAKE123" in l for l in logs))

# 3. 1 match => patch only, with that record's id.
existing_record = {"id": "recEXISTING456", "fields": {"Date": "2026-07-21"}}
result, logs, mock_lookup, mock_create, mock_patch = _run_write(matches=[existing_record], patch_return=True)
chk("1 match + patch()->True => returns True", result is True)
chk("1 match => airtable_patch() called with that record's id",
    mock_patch.called and mock_patch.call_args[0][1] == "recEXISTING456")
chk("1 match => airtable_create() NOT called", not mock_create.called)
chk("success log includes branch=patch", any("branch=patch" in l for l in logs))
chk("success log includes the matched record id", any("recEXISTING456" in l for l in logs))

# 4. 2+ matches => refuse entirely (duplicate-row integrity error).
dup_a = {"id": "recDUP1", "fields": {"Date": "2026-07-21"}}
dup_b = {"id": "recDUP2", "fields": {"Date": "2026-07-21"}}
result, logs, mock_lookup, mock_create, mock_patch = _run_write(matches=[dup_a, dup_b])
chk("2 matches => returns False", result is False)
chk("2 matches => airtable_create() NOT called", not mock_create.called)
chk("2 matches => airtable_patch() NOT called", not mock_patch.called)
chk("2 matches => a duplicate-row integrity error is logged",
    any("DUPLICATE-ROW" in l or "duplicate" in l.lower() for l in logs))
chk("2 matches => no success log", not any("branch=create" in l or "branch=patch" in l for l in logs))

# 5. Lookup itself fails (network/HTTP) — must not touch create/patch.
from tools.airtable_gateway import AirtableLookupError
result, logs, mock_lookup, mock_create, mock_patch = _run_write(lookup_raises=AirtableLookupError("boom"))
chk("lookup raising => returns False", result is False)
chk("lookup raising => airtable_create() NOT called", not mock_create.called)
chk("lookup raising => airtable_patch() NOT called", not mock_patch.called)
chk("no success log when the lookup itself failed",
    not any("branch=create" in l or "branch=patch" in l for l in logs))

# 6. Malformed date_str => no Airtable call at all.
result, logs, mock_lookup, mock_create, mock_patch = _run_write(date_str="not-a-date", matches=[])
chk("malformed date_str => returns False", result is False)
chk("malformed date_str => lookup NOT called", not mock_lookup.called)
chk("malformed date_str => airtable_create() NOT called", not mock_create.called)
chk("malformed date_str => airtable_patch() NOT called", not mock_patch.called)

# 7. Truthful failures remain truthful.
result, logs, mock_lookup, mock_create, mock_patch = _run_write(matches=[], create_return=None)
chk("0 matches + create()->None => returns False", result is False)
chk("no success log when create actually failed",
    not any("branch=create" in l or "branch=patch" in l for l in logs))

result, logs, mock_lookup, mock_create, mock_patch = _run_write(matches=[existing_record], patch_return=False)
chk("1 match + patch()->False => returns False", result is False)
chk("no success log when patch actually failed",
    not any("branch=create" in l or "branch=patch" in l for l in logs))

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
