#!/usr/bin/env python3
"""
test_weekly_summary_domain_grouping.py — regression test for a stale-status-
style bug found in the FEATURE_WEEKLY_SUMMARY pre-activation check (20/07/2026).

weekly_summary.py::_group_by_domain() used to read Tags[0] as the domain.
cmd_update.py::_save_to_business_memory() never writes domain into Tags at
all (see cmd_update.py:343-349) — domain is written only to the dedicated
Domain field, as a human-readable Airtable option string ("Real Estate",
not "real_estate"). The old code silently misgrouped every entry into
"general" (Tags empty) or under an unrelated real tag as if it were a
domain. Fixed to read BusinessMemoryFields.DOMAIN and normalize it
("Real Estate" -> "real_estate") to match _DOMAIN_LABELS' internal keys.
"""

from __future__ import annotations

import logging

logging.basicConfig(level=logging.WARNING)

from airtable_schema import BusinessMemoryFields as BMF
from weekly_summary import _group_by_domain, _normalize_domain_key, _DOMAIN_LABELS

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


print("\n── _normalize_domain_key ──────────────")

chk("'Real Estate' -> 'real_estate'", _normalize_domain_key("Real Estate") == "real_estate")
chk("'SaaS' -> 'saas'", _normalize_domain_key("SaaS") == "saas")
chk("'General' -> 'general'", _normalize_domain_key("General") == "general")
chk("empty string -> 'general' (fail-safe default)", _normalize_domain_key("") == "general")
chk(
    "every _DOMAIN_TO_AIRTABLE value normalizes to a key present in _DOMAIN_LABELS "
    "(so the weekly summary never falls back to the raw-string label)",
    all(
        _normalize_domain_key(v) in _DOMAIN_LABELS
        for v in {"Real Estate", "Import", "Media", "SaaS", "General"}
    ),
)

print("\n── _group_by_domain ───────────────────")

entries = [
    {BMF.DOMAIN: "Real Estate", BMF.TAGS: ["Finance"], "id": "1"},  # real tag != domain
    {BMF.DOMAIN: "Real Estate", "id": "2"},
    {BMF.DOMAIN: "SaaS", BMF.TAGS: ["Legal", "Risk"], "id": "3"},
    {BMF.DOMAIN: "General", "id": "4"},
    {"id": "5"},  # missing Domain entirely — must not crash
]
grouped = _group_by_domain(entries)

chk("groups by Domain field, not Tags", set(grouped.keys()) == {"real_estate", "saas", "general"})
chk("real_estate bucket has both matching entries", len(grouped["real_estate"]) == 2)
chk("saas bucket unaffected by its unrelated Tags", len(grouped["saas"]) == 1)
chk("entry with a real (non-domain) tag is not grouped under that tag", "finance" not in grouped)
chk("entry with a real (non-domain) tag is not grouped under 'legal'/'risk'", "legal" not in grouped and "risk" not in grouped)
chk("missing Domain field falls back to 'general', doesn't crash", any(e["id"] == "5" for e in grouped["general"]))

print(f"\n{'='*40}")
print(f"weekly_summary domain-grouping tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
