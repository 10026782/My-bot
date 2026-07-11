#!/usr/bin/env python3
"""
test_bug099a_name_stop_extension.py — BUG-099a regression suite.

_extract_name_from_window() (core/ingress_classifier.py) accepted a
property-description phrase ("קומה"/"חדרים"/floor-ordinals/etc.) as a
lead's name whenever it happened to be the first 2+-word Hebrew sequence
inside the +-80-char window around the phone number, and the real name
sat outside that window. Confirmed against a real record written to
production Leads (recRvK6hFTNgyj8ag, Name="חדרים קומה ראשונה").

Fix: extend _NAME_STOP with property-description vocabulary — the
existing rejection check in _extract_name_from_window() (`if any(w in
_NAME_STOP for w in name.split()): continue`) already handles this
correctly once the vocabulary is present. No new extraction logic.

Scope: single set (_NAME_STOP) in core/ingress_classifier.py only —
confirmed NOT shared with lead_candidate_handler.py's separate (dead)
_NAME_STOP copy.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from core.ingress_classifier import (  # noqa: E402
    classify_ingress,
    _extract_lead_candidates,
    _NAME_STOP,
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


# ══════════════════════════════════════════════════════════════════
# T1 — exact production repro (recRvK6hFTNgyj8ag's original text, via
# its own summary field, retrieved live through the Airtable MCP)
# ══════════════════════════════════════════════════════════════════
print("\n── T1: production repro — recRvK6hFTNgyj8ag ──")

_T1_TEXT = "צור ליד חדש יעל רייס  מעוניינת בדירת 2 חדרים קומה ראשונה   065726763"
cands = _extract_lead_candidates(_T1_TEXT)
names = [c["name"] for c in cands]

chk("T1: garbage name 'חדרים קומה ראשונה' no longer produced", "חדרים קומה ראשונה" not in names)
chk("T1: falls through to no-candidates (safer than garbage) rather than writing bad data", cands == [])

ic = classify_ingress(_T1_TEXT)
chk("T1: classify_ingress degrades to Tier 5 (no_lead_candidates), not a false Tier 1", ic.tier == 5)


# ══════════════════════════════════════════════════════════════════
# T2 — second reproduction case (description before phone, comma variant)
# ══════════════════════════════════════════════════════════════════
print("\n── T2: description-before-phone repro ──")

_T2_TEXT = "יוסי יהלום מעוניין בדירת 4 חדרים בקומה חמישית, טלפון 0736637363"
cands = _extract_lead_candidates(_T2_TEXT)
names = [c["name"] for c in cands]

chk("T2: garbage name 'חדרים בקומה חמישית' no longer produced", not any("קומה" in n for n in names))
chk("T2: falls through to no-candidates", cands == [])


# ══════════════════════════════════════════════════════════════════
# Control — description AFTER the phone still extracts the real name
# (this direction was never broken; must stay working)
# ══════════════════════════════════════════════════════════════════
print("\n── Control: description-after-phone still works ──")

_CTRL1_TEXT = "יוסי יהלום טלפון 0736637363, מעוניין בדירת 4 חדרים בקומה חמישית"
cands = _extract_lead_candidates(_CTRL1_TEXT)
chk("Control 1: real name still extracted when description is after the phone",
    any(c["name"] == "יוסי יהלום" for c in cands))

_CTRL2_TEXT = "צור ליד: ישראל כהן, טלפון 0521234567, מעוניין בדירת 3 חדרים"
cands = _extract_lead_candidates(_CTRL2_TEXT)
chk("Control 2: plain control case (no property-description collision) unaffected",
    any(c["name"] == "ישראל כהן" for c in cands))


# ══════════════════════════════════════════════════════════════════
# Isolation — confirm _NAME_STOP is NOT shared with lead_candidate_handler.py
# ══════════════════════════════════════════════════════════════════
print("\n── Isolation: ingress_classifier._NAME_STOP is not shared ──")

import core.lead_candidate_handler as lch  # noqa: E402

chk("Isolation: lead_candidate_handler.py has its own separate _NAME_STOP object",
    lch._NAME_STOP is not _NAME_STOP)
chk("Isolation: new property-description words were NOT added to the dead-code copy",
    "קומה" not in lch._NAME_STOP)


# ══════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
