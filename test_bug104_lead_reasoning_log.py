#!/usr/bin/env python3
# test_bug104_lead_reasoning_log.py
# BUG-104 / CR_OBS_LOG — Core Reasoning Activation Program
# Compact Lead Reasoning Observability Log
#
# Run: python3 test_bug104_lead_reasoning_log.py
# Pass condition: exit code 0, all assertions green.
#
# Covers tma_api._format_lead_reasoning_log() — a pure formatting helper, no
# I/O, no Airtable, no Flask request context. Observability only:
#   1. active + meeting_scheduled + COLLECTING + events=0
#   2. done + converted + DECIDED + events=1 + score present
#   3. events unavailable
#   4. missing status/outcome
#   5. errors count does not dump error text (PII/verbosity guard)

from __future__ import annotations

import sys

_passed = 0
_failed = 0


def check(label: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ✅ {label}")
    else:
        _failed += 1
        print(f"  ❌ {label}")


import tma_api

_format = tma_api._format_lead_reasoning_log


def _projection(state, events_available, events_count, score_value=None, score_state="missing",
                degraded=False, errors=None):
    return {
        "state": state,
        "events": {"available": events_available, "count": events_count},
        "lead_score": {"value": score_value, "state": score_state},
        "engine": {"degraded": degraded, "errors": errors or []},
    }


# ═════════════════════════════════════════════════════════════════
# 1. active + meeting_scheduled + COLLECTING + events=0
# ═════════════════════════════════════════════════════════════════
print("\n[1] active + meeting_scheduled + COLLECTING + events=0")

line1 = _format(
    "recXXX", "shadow", "active", "meeting_scheduled ",
    _projection("COLLECTING", events_available=True, events_count=0),
)
check("exact expected format",
      line1 == "[LeadReasoning] lead=recXXX mode=shadow status=active outcome=meeting_scheduled "
                "state=COLLECTING events=0 lead_score=missing degraded=false errors=0")
check("single line (no newlines)", "\n" not in line1)


# ═════════════════════════════════════════════════════════════════
# 2. done + converted + DECIDED + events=1 + score present
# ═════════════════════════════════════════════════════════════════
print("\n[2] done + converted + DECIDED + events=1 + score present")

line2 = _format(
    "recYYY", "shadow", "done", "converted ",
    _projection("DECIDED", events_available=True, events_count=1, score_value=60, score_state="present"),
)
check("exact expected format",
      line2 == "[LeadReasoning] lead=recYYY mode=shadow status=done outcome=converted "
                "state=DECIDED events=1 lead_score=60 degraded=false errors=0")

line2_on = _format(
    "recYYY", "on", "done", "converted ",
    _projection("DECIDED", events_available=True, events_count=1, score_value=60, score_state="present"),
)
check("mode=on reflected literally", "mode=on" in line2_on)


# ═════════════════════════════════════════════════════════════════
# 3. events unavailable
# ═════════════════════════════════════════════════════════════════
print("\n[3] events unavailable")

line3 = _format(
    "recZZZ", "on", "active", "",
    _projection("COLLECTING", events_available=False, events_count=0),
)
check("events=unavailable, not events=0", "events=unavailable" in line3)
check("no 'events=0' substring when unavailable", "events=0" not in line3)


# ═════════════════════════════════════════════════════════════════
# 4. missing status/outcome
# ═════════════════════════════════════════════════════════════════
print("\n[4] missing status/outcome")

for raw_status, raw_outcome in ((None, None), ("", ""), ("   ", "   ")):
    line4 = _format(
        "recMISS", "shadow", raw_status, raw_outcome,
        _projection("COLLECTING", events_available=True, events_count=0),
    )
    check(f"status/outcome={raw_status!r}/{raw_outcome!r} -> status=<missing>", "status=<missing>" in line4)
    check(f"status/outcome={raw_status!r}/{raw_outcome!r} -> outcome=<missing>", "outcome=<missing>" in line4)

# only one side missing
line4b = _format(
    "recMISS2", "shadow", "active", None,
    _projection("COLLECTING", events_available=True, events_count=0),
)
check("status present, outcome missing -> status=active outcome=<missing>",
      "status=active" in line4b and "outcome=<missing>" in line4b)

# invalid lead_score state
line4c = _format(
    "recMISS3", "shadow", "active", "open ",
    _projection("COLLECTING", events_available=True, events_count=0,
                score_value=None, score_state="invalid"),
)
check("lead_score invalid state surfaced as 'invalid'", "lead_score=invalid" in line4c)


# ═════════════════════════════════════════════════════════════════
# 5. errors count does not dump error text
# ═════════════════════════════════════════════════════════════════
print("\n[5] errors count does not dump error text")

SECRET_ERROR_TEXT = "confidence_engine: KeyError('Airtable Base app4bcgoX7t0HUVnm leaked')"
line5 = _format(
    "recERR", "shadow", "active", "open ",
    _projection("COLLECTING", events_available=True, events_count=0,
                degraded=True, errors=[SECRET_ERROR_TEXT, "orchestrator_engine: boom"]),
)
check("errors=2 (count only)", "errors=2" in line5)
check("full error text NEVER appears in the compact line", SECRET_ERROR_TEXT not in line5)
check("degraded=true reflected", "degraded=true" in line5)

line5_zero = _format(
    "recOK", "shadow", "active", "open ",
    _projection("COLLECTING", events_available=True, events_count=0, degraded=False, errors=[]),
)
check("errors=0 when engine clean", "errors=0" in line5_zero)
check("degraded=false when engine clean", "degraded=false" in line5_zero)


# ═════════════════════════════════════════════════════════════════
# PII guard — no phone/name/notes/message keys ever touched by the helper
# ═════════════════════════════════════════════════════════════════
print("\n[PII guard] helper never reflects unrelated projection/lead fields")

proj_with_pii_shaped_extra_keys = _projection("COLLECTING", events_available=True, events_count=0)
proj_with_pii_shaped_extra_keys["notes"] = "0501234567 בטלפון של הלקוח"   # not a real field on the
proj_with_pii_shaped_extra_keys["raw_input"] = "השם שלי דני, תתקשרו אליי"  # projection dict, but if the
                                                                            # helper ever did **projection
                                                                            # or similar it would leak here
line_pii = _format("recPII", "shadow", "active", "open ", proj_with_pii_shaped_extra_keys)
check("no phone-shaped digits leaked", "0501234567" not in line_pii)
check("no free-text note content leaked", "בטלפון" not in line_pii and "תתקשרו" not in line_pii)


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print(f"BUG-104 / CR_OBS_LOG compact lead reasoning log: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
