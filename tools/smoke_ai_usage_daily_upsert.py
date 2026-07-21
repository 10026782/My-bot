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
where the real scheduler is also running.

Expected output:
  Run 1 log line: "... branch=create date=<date> record_id=rec... ..."
  Run 2 log line: "... branch=patch  date=<date> record_id=rec... ..."
    (SAME record_id as run 1)
  Final verification: exactly 1 row found for <date>.

If run 2 also says branch=create, or the final count is 2 (or 4 after
running the whole script twice), the lookup formula is broken again —
this is exactly the failure mode the DATETIME_FORMAT hotfix fixes.
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 tools/smoke_ai_usage_daily_upsert.py <YYYY-MM-DD>")
        return 2

    date_str = sys.argv[1]

    from datetime import date as _date
    try:
        _date.fromisoformat(date_str)
    except ValueError:
        print(f"❌ {date_str!r} is not a valid ISO date (YYYY-MM-DD)")
        return 2

    from core.cost_watchdog import _write_airtable_row
    from tools.airtable_gateway import at_list_by_formula, _safe_formula_param
    from airtable_schema import Tables

    table = getattr(Tables, "AI_USAGE_DAILY", "AI_Usage_Daily")

    print(f"\n=== Run 1 for {date_str} — expect branch=create ===")
    ok1 = _write_airtable_row(date_str, {
        "claude_sonnet": 11, "claude_haiku": 22,
        "whatsapp_conversation": 3, "total_units": 36,
    })
    print(f"run 1 returned: {ok1}")

    print(f"\n=== Run 2 for {date_str} (different counts) — expect branch=patch, SAME record_id as run 1 ===")
    ok2 = _write_airtable_row(date_str, {
        "claude_sonnet": 44, "claude_haiku": 55,
        "whatsapp_conversation": 6, "total_units": 105,
    })
    print(f"run 2 returned: {ok2}")

    print(f"\n=== Verifying row count for {date_str} ===")
    formula = f"DATETIME_FORMAT({{Date}}, 'YYYY-MM-DD')='{_safe_formula_param(date_str)}'"
    matches = at_list_by_formula(table, formula, max_records=10)
    print(f"rows found for {date_str}: {len(matches)}")
    for m in matches:
        print(f"  record_id={m.get('id')} fields={m.get('fields')}")

    if not (ok1 and ok2):
        print("\n❌ SMOKE FAILED — one or both writes reported failure (see logs above)")
        return 1
    if len(matches) != 1:
        print(f"\n❌ SMOKE FAILED — expected exactly 1 row for {date_str}, found {len(matches)}")
        return 1

    print("\n✅ SMOKE PASSED — create then patch, exactly one row remains")
    return 0


if __name__ == "__main__":
    sys.exit(main())
