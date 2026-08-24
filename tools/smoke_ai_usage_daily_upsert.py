#!/usr/bin/env python3
"""
tools/smoke_ai_usage_daily_upsert.py — Production smoke test for
core/cost_watchdog.py::_write_airtable_row()'s upsert path.

WHY THIS EXISTS: the PR1 hotfix (DATETIME_FORMAT lookup formula) fixes a
bug that a mocked unit test cannot catch by construction — the mock always
returns whatever the test tells it to, so a test can assert "the code
calls at_list_by_formula with the right formula" but can't independently
prove Airtable actually matches on that formula the way we assume. The
original bug (at_get_by_field's plain {Date}='YYYY-MM-DD' never matching a
DATE-typed field) only ever showed up against the real API. This script is
that real-API check, meant to be run by hand against the live base before
trusting the fix.

Usage:
    python3 tools/smoke_ai_usage_daily_upsert.py <YYYY-MM-DD>

WARNING — this WRITES to the live AI_Usage_Daily table (AIRTABLE_API_KEY /
AIRTABLE_BASE_ID from the environment). Pass a throwaway date that will
never collide with a real daily_watchdog() run (e.g. a date far in the
future) — do not point this at today's date on a production environment
where the real scheduler is also running. The script requires the date to
be empty (0 existing rows) before it will write anything, precisely so it
can't silently corrupt a real day's data.

This is a full assertion-based verification, not just a log inspection:
  0. Pre-check: the date must have ZERO existing rows. If it already has
     one (or more), abort — pick a different date rather than writing
     into who-knows-what state.
  1. Write #1 (claude_sonnet=11, claude_haiku=22, whatsapp_conversation=3).
     Look up afterward: require EXACTLY one row, capture its record id.
  2. Write #2, same date, DIFFERENT counts (claude_sonnet=44,
     claude_haiku=55, whatsapp_conversation=6). Look up afterward: require
     EXACTLY one row, capture its record id.
  3. Assert the two record ids are identical — write #2 patched the same
     row write #1 created, it did not create a second one.
  4. Assert the row's final field values match write #2's counts exactly
     (claude_sonnet=44, claude_haiku=55, whatsapp_conversation=6,
     total_units=105) — proving the patch actually applied write #2's
     values, not some stale mix of the two writes.

Deliberately does NOT include "total_units" in the counts dict passed to
_write_airtable_row() — that function computes total_units itself as
sum(counts.values()), so including it in the input would double-count
(an earlier draft of this script did exactly that: sending total_units=36
in a counts dict that also had claude_sonnet/claude_haiku/
whatsapp_conversation summing to 36 produced a stored total_units of 72).
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def _lookup(table: str, date_str: str) -> list[dict]:
    from tools.airtable_gateway import at_list_by_formula, escape_formula_value
    formula = f"DATETIME_FORMAT({{Date}}, 'YYYY-MM-DD')='{escape_formula_value(date_str)}'"
    return at_list_by_formula(table, formula, max_records=10)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 tools/smoke_ai_usage_daily_upsert.py <YYYY-MM-DD>")
        return 2

    date_str = sys.argv[1]

    from datetime import date as _date
    try:
        parsed = _date.fromisoformat(date_str)
    except ValueError:
        print(f"❌ {date_str!r} is not a valid ISO date (YYYY-MM-DD)")
        return 2
    if parsed.isoformat() != date_str:
        print(
            f"❌ {date_str!r} parsed but is not canonical YYYY-MM-DD "
            f"(fromisoformat() accepts other formats too — got {parsed.isoformat()!r} "
            f"back). Pass the date exactly as YYYY-MM-DD."
        )
        return 2

    from core.cost_watchdog import _write_airtable_row
    from airtable_schema import Tables

    table = getattr(Tables, "AI_USAGE_DAILY", "AI_Usage_Daily")

    print(f"\n=== Pre-check for {date_str}: must be ZERO existing rows ===")
    pre_matches = _lookup(table, date_str)
    if pre_matches:
        print(
            f"❌ ABORTING — {len(pre_matches)} row(s) already exist for {date_str} "
            f"(record ids: {[m.get('id') for m in pre_matches]}). This script refuses "
            f"to write into a date that isn't empty. Pick a different throwaway date."
        )
        return 1
    print("OK — no existing rows.")

    print(f"\n=== Write #1 for {date_str} — expect branch=create ===")
    ok1 = _write_airtable_row(date_str, {
        "claude_sonnet": 11, "claude_haiku": 22, "whatsapp_conversation": 3,
    })
    print(f"write #1 returned: {ok1}")
    if not ok1:
        print("❌ SMOKE FAILED — write #1 reported failure (see logs above)")
        return 1

    post1_matches = _lookup(table, date_str)
    if len(post1_matches) != 1:
        print(
            f"❌ SMOKE FAILED — after write #1, expected exactly 1 row for {date_str}, "
            f"found {len(post1_matches)} (record ids: {[m.get('id') for m in post1_matches]})"
        )
        return 1
    id1 = post1_matches[0]["id"]
    print(f"OK — exactly 1 row, record_id={id1}")

    print(f"\n=== Write #2 for {date_str} (different counts) — expect branch=patch, SAME record_id ===")
    ok2 = _write_airtable_row(date_str, {
        "claude_sonnet": 44, "claude_haiku": 55, "whatsapp_conversation": 6,
    })
    print(f"write #2 returned: {ok2}")
    if not ok2:
        print("❌ SMOKE FAILED — write #2 reported failure (see logs above)")
        return 1

    post2_matches = _lookup(table, date_str)
    if len(post2_matches) != 1:
        print(
            f"❌ SMOKE FAILED — after write #2, expected exactly 1 row for {date_str}, "
            f"found {len(post2_matches)} (record ids: {[m.get('id') for m in post2_matches]})"
        )
        return 1
    id2 = post2_matches[0]["id"]
    print(f"OK — exactly 1 row, record_id={id2}")

    print(f"\n=== Verifying record identity and final field values ===")
    if id1 != id2:
        print(f"❌ SMOKE FAILED — write #2 created a DIFFERENT row (id1={id1}, id2={id2}) instead of patching id1")
        return 1
    print(f"OK — write #2 patched the same row as write #1 (record_id={id1})")

    final_fields = post2_matches[0].get("fields", {})
    expected = {
        "claude_sonnet": 44,
        "claude_haiku": 55,
        "whatsapp_conversation": 6,
        "total_units": 105,
    }
    mismatches = {
        k: (final_fields.get(k), v) for k, v in expected.items() if final_fields.get(k) != v
    }
    if mismatches:
        print(f"❌ SMOKE FAILED — final field values don't match write #2's counts: {mismatches}")
        print(f"   full record fields: {final_fields}")
        return 1
    print(f"OK — final fields match write #2 exactly: {expected}")

    print("\n✅ SMOKE PASSED — create then patch, same record, exactly one row, correct final values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
