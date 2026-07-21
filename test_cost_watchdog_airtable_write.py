#!/usr/bin/env python3
"""
test_cost_watchdog_airtable_write.py — Regression tests for
core/cost_watchdog.py::_write_airtable_row() (Cost Telemetry Reliability
PR series, PR1).

Two bugs this guards against:
  1. "Success logged without checking the write result" — it used to log
     "שורה יומית נכתבה ל-Airtable" unconditionally right after calling
     airtable_create(), never inspecting its return value. airtable_create()
     returns None (not an exception) on any non-2xx HTTP response, so the
     live 422 UNKNOWN_FIELD_NAME this table hit for weeks was reported as
     success every single day.
  2. "Create-only instead of upsert" — it always called airtable_create(),
     so re-running daily_watchdog() for a date that already has a row (a
     manual retry, a scheduler double-fire) silently created a SECOND row
     for the same date. It now looks up the existing row by Date first and
     patches it if found.

Verifies:
  1. No existing row (at_get_by_field -> None) + airtable_create() -> None
     (the live 422 case) => failure, no success log.
  2. No existing row + airtable_create() -> a real record => success (create path).
  3. An existing row (at_get_by_field -> a record) => airtable_patch() is
     called with that record's id, NOT airtable_create() (no duplicate).
  4. airtable_patch() returning False => failure, no success log.
  5. at_get_by_field() raising AirtableLookupError (network/HTTP failure,
     not "genuinely not found") => refuses to blind-create, failure, no
     success log.
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


def _run_write(*, existing, create_return=None, patch_return=None, lookup_raises=None):
    from core.cost_watchdog import _write_airtable_row
    from tools.airtable_gateway import AirtableLookupError

    handler = _CaptureHandler()
    logger = logging.getLogger("core.cost_watchdog")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    lookup_side_effect = lookup_raises if lookup_raises else None
    lookup_kwargs = {"side_effect": lookup_side_effect} if lookup_side_effect else {"return_value": existing}

    try:
        with patch("tools.airtable_gateway.at_get_by_field", **lookup_kwargs), \
             patch("tools.airtable_gateway.airtable_create", return_value=create_return), \
             patch("tools.airtable_gateway.airtable_patch", return_value=patch_return) as mock_patch:
            result = _write_airtable_row("2026-07-21", {
                "claude_sonnet": 10, "claude_haiku": 20,
                "whatsapp_conversation": 0, "total_units": 30,
            })
    finally:
        logger.removeHandler(handler)
    return result, handler.records, mock_patch


print("\n── _write_airtable_row() truthfulness + upsert ────────────────")

# 1. No existing row, airtable_create() -> None (the live 422 case).
result, logs, mock_patch = _run_write(existing=None, create_return=None)
chk("no existing row + create()->None => returns False", result is False)
chk("no 'success' log line when create actually failed",
    not any("נכתבה" in l or "עודכנה" in l for l in logs))
chk("patch is never called when there's no existing row", not mock_patch.called)

# 2. No existing row, airtable_create() -> a real record => success.
fake_record = {"id": "recFAKE123", "fields": {"Date": "2026-07-21"}}
result, logs, mock_patch = _run_write(existing=None, create_return=fake_record)
chk("no existing row + create()->record => returns True", result is True)
chk("success log line present on real create", any("נכתבה" in l for l in logs))
chk("patch is never called on the create path", not mock_patch.called)

# 3. Existing row => patch() is called with that record's id, not create().
existing_record = {"id": "recEXISTING456", "fields": {"Date": "2026-07-21"}}
result, logs, mock_patch = _run_write(existing=existing_record, patch_return=True)
chk("existing row + patch()->True => returns True", result is True)
chk("success log line present on the patch/upsert path", any("עודכנה" in l for l in logs))
chk("patch() called with the existing record's id (upsert, not duplicate)",
    mock_patch.called and mock_patch.call_args[0][1] == "recEXISTING456")

# 4. Existing row, patch() returns False => failure, no success log.
result, logs, mock_patch = _run_write(existing=existing_record, patch_return=False)
chk("existing row + patch()->False => returns False", result is False)
chk("no success log line when patch actually failed",
    not any("נכתבה" in l or "עודכנה" in l for l in logs))

# 5. Lookup itself fails (network/HTTP) — must not blind-create (would risk a duplicate).
from tools.airtable_gateway import AirtableLookupError
result, logs, mock_patch = _run_write(existing=None, lookup_raises=AirtableLookupError("boom"))
chk("at_get_by_field() raising => returns False (refuses to guess)", result is False)
chk("no success log line when the lookup itself failed",
    not any("נכתבה" in l or "עודכנה" in l for l in logs))

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
