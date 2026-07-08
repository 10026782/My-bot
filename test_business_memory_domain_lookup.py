#!/usr/bin/env python3
"""
test_business_memory_domain_lookup.py — regression tests for
cmd_update.resolve_business_memory_domain() and its integration into
normalize_business_memory_fields()/_save_to_business_memory().

Context: BUG-081 — a hardcoded _DOMAIN_TO_AIRTABLE dict repeatedly went out
of sync with the live Airtable Domain options (trailing spaces, casing,
duplicate options). This replaces the dict as the source of truth with a
live, case/whitespace-tolerant lookup through RuntimeSchemaProvider, falling
back to the static dict only when no live schema is available at all.

מאמת:
1. resolve_business_memory_domain: exact live value returned as-is (no
   normalization applied to the output), for a normalized-match lookup.
2. Rename DoD: a cosmetic live rename (extra space) is picked up automatically
   without any code change — the lookup still matches and returns the new
   exact live string.
3. Duplicate option guard: >1 live choice normalizes to the same key →
   structured {"ok": False, "error": "duplicate option name found: ... (N
   matching options)"}, never silently picks one.
4. No-match: structured error, never an arbitrary fallback value.
5. Provider unavailable (mode != full / no choices) → falls back to the
   static _DOMAIN_TO_AIRTABLE dict.
6. Provider unavailable AND no static mapping → structured error.
7. "finance" (no dedicated Airtable option) aliases to "general" lookup.
8. normalize_business_memory_fields: success sets BMF.DOMAIN to the resolved
   exact value; failure omits BMF.DOMAIN entirely (never writes "General" or
   any other arbitrary value on failure).
9. _save_to_business_memory aborts (returns None, never calls airtable_create)
   when Domain resolution failed.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import cmd_update
from airtable_schema import Tables, BusinessMemoryFields as BMF

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


class _FakeProvider:
    def __init__(self, choices, mode="full"):
        self._choices = choices
        self._mode = mode

    def get_table_contract(self, table):
        if self._mode != "full":
            return {"table_id": None, "mode": self._mode, "source": "seed", "fields": {}}
        return {
            "table_id": "tblFAKE",
            "mode": "full",
            "source": "live",
            "fields": {
                BMF.DOMAIN: {"field_id": "fldFAKE", "type": "singleSelect", "choices": self._choices},
            },
        }


def _patched(choices, mode="full"):
    return patch(
        "core.runtime_schema_provider.get_provider",
        return_value=_FakeProvider(choices, mode=mode),
    )


# ══════════════════════════════════════════════════════════════════
# 1. Exact live value returned as-is (no re-normalization of output)
# ══════════════════════════════════════════════════════════════════
print("\n── exact live value, no normalization ────")

with _patched(["Real Estate", "Import", "Media", "SaaS", "General"]):
    r = cmd_update.resolve_business_memory_domain("real_estate")
    chk("real_estate resolves ok", r["ok"] is True)
    chk("real_estate resolves to exact live string", r["value"] == "Real Estate")

    r2 = cmd_update.resolve_business_memory_domain("saas")
    chk("saas resolves to exact live casing 'SaaS'", r2 == {"ok": True, "value": "SaaS"})

# ══════════════════════════════════════════════════════════════════
# 2. Rename DoD — cosmetic live change picked up automatically
# ══════════════════════════════════════════════════════════════════
print("\n── rename DoD: no code change needed ─────")

with _patched(["Real  Estate", "Import"]):  # double space, deliberately "renamed" live
    r = cmd_update.resolve_business_memory_domain("real_estate")
    chk("rename DoD: still resolves ok", r["ok"] is True)
    chk("rename DoD: returns the new exact live string verbatim", r["value"] == "Real  Estate")

with _patched(["real estate"]):  # casing-only live rename
    r = cmd_update.resolve_business_memory_domain("real_estate")
    chk("casing-only rename still resolves", r == {"ok": True, "value": "real estate"})

# ══════════════════════════════════════════════════════════════════
# 3. Duplicate option guard
# ══════════════════════════════════════════════════════════════════
print("\n── duplicate option guard ─────────────────")

with _patched(["Real Estate", "Real Estate", "Import"]):
    r = cmd_update.resolve_business_memory_domain("real_estate")
    chk("duplicate detected, ok=False", r["ok"] is False)
    chk(
        "duplicate error message matches required format",
        r["error"] == "duplicate option name found: Real Estate (2 matching options)",
    )

# ══════════════════════════════════════════════════════════════════
# 4. No-match — structured error, not an arbitrary value
# ══════════════════════════════════════════════════════════════════
print("\n── no-match ───────────────────────────────")

with _patched(["Import", "Media"]):
    r = cmd_update.resolve_business_memory_domain("real_estate")
    chk("no-match: ok=False", r["ok"] is False)
    chk(
        "no-match: structured error message, no arbitrary value key",
        r["error"] == "no live Airtable Domain option matches domain key 'real_estate'" and "value" not in r,
    )

# ══════════════════════════════════════════════════════════════════
# 5-6. Provider unavailable → static fallback / structured error
# ══════════════════════════════════════════════════════════════════
print("\n── provider unavailable → static fallback ─")

with _patched([], mode="name_only"):
    r = cmd_update.resolve_business_memory_domain("real_estate")
    chk("provider unavailable falls back to static dict", r == {"ok": True, "value": cmd_update._DOMAIN_TO_AIRTABLE["real_estate"]})

with patch("core.runtime_schema_provider.get_provider", side_effect=Exception("boom")):
    r = cmd_update.resolve_business_memory_domain("real_estate")
    chk("provider raising also falls back to static dict (never crashes)", r["ok"] is True)

with _patched([], mode="name_only"):
    r = cmd_update.resolve_business_memory_domain("totally_unknown_key")
    chk("provider unavailable + no static mapping → structured error", r["ok"] is False)
    chk("error mentions no live schema and no static mapping", "no static mapping" in r["error"])

# ══════════════════════════════════════════════════════════════════
# 7. "finance" aliases to "general" lookup (business rule, not schema fact)
# ══════════════════════════════════════════════════════════════════
print("\n── finance → general alias ─────────────────")

with _patched(["General", "Import"]):
    r = cmd_update.resolve_business_memory_domain("finance")
    chk("finance resolves via 'general' alias to live 'General'", r == {"ok": True, "value": "General"})

# ══════════════════════════════════════════════════════════════════
# 8. normalize_business_memory_fields — success sets Domain, failure omits it
# ══════════════════════════════════════════════════════════════════
print("\n── normalize_business_memory_fields ────────")

with _patched(["Real Estate", "Import"]):
    fields = cmd_update.normalize_business_memory_fields({}, "real_estate")
    chk("normalize sets Domain to resolved exact value", fields[BMF.DOMAIN] == "Real Estate")

with _patched(["Import", "Media"]):  # real_estate has no match here
    fields = cmd_update.normalize_business_memory_fields({}, "real_estate")
    chk("normalize omits Domain entirely on resolution failure (no arbitrary value)", BMF.DOMAIN not in fields)

# ══════════════════════════════════════════════════════════════════
# 9. _save_to_business_memory aborts when Domain resolution failed
# ══════════════════════════════════════════════════════════════════
print("\n── _save_to_business_memory aborts on failure ─")

class _FakeIdentity:
    tenant_id = "t1"
    user_id = "u1"


with _patched(["Import", "Media"]), patch("tools.airtable_gateway.airtable_create") as fake_create:
    result = cmd_update._save_to_business_memory(
        identity=_FakeIdentity(), title="x", raw_text="y", domain="real_estate", entry_type="Other",
    )
    chk("_save_to_business_memory returns None on Domain resolution failure", result is None)
    chk("_save_to_business_memory never calls airtable_create when Domain resolution failed", fake_create.call_count == 0)

with _patched(["Real Estate", "Import"]), patch("tools.airtable_gateway.airtable_create") as fake_create:
    fake_create.return_value = {"id": "recFAKE"}
    result = cmd_update._save_to_business_memory(
        identity=_FakeIdentity(), title="x", raw_text="y", domain="real_estate", entry_type="Other",
    )
    chk("_save_to_business_memory proceeds and returns record when resolution succeeds", result == {"id": "recFAKE"})
    chk("airtable_create called with resolved exact Domain value", fake_create.call_args.args[1][BMF.DOMAIN] == "Real Estate")


print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
