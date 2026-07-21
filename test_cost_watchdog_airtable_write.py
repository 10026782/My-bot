#!/usr/bin/env python3
"""
test_cost_watchdog_airtable_write.py — Regression tests for the
"success logged without checking the write result" bug (Cost Telemetry
Reliability PR, Part A).

Previously _write_airtable_row() logged "שורה יומית נכתבה ל-Airtable"
unconditionally right after calling airtable_create(), never inspecting
its return value. airtable_create() returns None (not an exception) on
any non-2xx HTTP response, so every real-world failure (the live 422
UNKNOWN_FIELD_NAME this table hit for weeks) was reported as success.

Verifies:
  1. airtable_create() -> None => _write_airtable_row() returns False,
     and the caller-facing "success" log line is never emitted.
  2. airtable_create() -> a real record dict => returns True, success
     logged.
  3. A simulated 422/unknown-field failure (airtable_create() returning
     None, mirroring what tools/airtable_gateway.py actually does for a
     non-2xx response) is never reported as success.
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


def _run_write(create_return, table="AI_Usage_Daily"):
    from core.cost_watchdog import _write_airtable_row

    handler = _CaptureHandler()
    logger = logging.getLogger("core.cost_watchdog")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with patch("tools.airtable_gateway.airtable_create", return_value=create_return):
            result = _write_airtable_row("2026-07-21", {
                "claude_sonnet": 10, "claude_haiku": 20,
                "whatsapp_conversation": 0, "total_units": 30,
            })
    finally:
        logger.removeHandler(handler)
    return result, handler.records


print("\n── _write_airtable_row() truthfulness ────────────────")

# 1. airtable_create() returns None (the live 422 case) -> failure, no success log.
result, logs = _run_write(None)
chk("airtable_create()->None => _write_airtable_row() returns False", result is False)
chk("no 'success' log line when write actually failed",
    not any("שורה יומית נכתבה" in l for l in logs))
chk("an ERROR-shaped failure message is present",
    any("FAILED" in l for l in logs))

# 2. airtable_create() returns a real record -> success.
fake_record = {"id": "recFAKE123", "fields": {"Date": "2026-07-21"}}
result, logs = _run_write(fake_record)
chk("airtable_create()->record => _write_airtable_row() returns True", result is True)
chk("success log line present when write actually succeeded",
    any("שורה יומית נכתבה" in l for l in logs))

# 3. Explicit 422/unknown-field simulation: airtable_create() itself would
#    return None for this (see tools/airtable_gateway.py:airtable_create,
#    r.status_code not in (200, 201) => return None) — same as case 1,
#    asserted again with a distinct description to pin the exact regression.
result, logs = _run_write(None)
chk("422 UNKNOWN_FIELD_NAME (airtable_create->None) is never shown as success",
    result is False and not any("נכתבה" in l for l in logs))

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
