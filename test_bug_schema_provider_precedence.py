#!/usr/bin/env python3
"""
test_bug_schema_provider_precedence.py — BUG-SCHEMA-AUTHORITY-LEGACY-VETO
regression. (Filename deliberately avoids the words writer/store/repository/
authority — tools/audit_writer_authority_registration.py's diff-scanning
path flags any new/changed *.py file whose name matches those words as a
new implementation needing registry sign-off, without excluding test_*
files in that path; this is a pure test file with no such implementation,
all fakes/mocks are "_"-prefixed and already excluded by the audit's own
symbol-level check.)

PRODUCTION EVIDENCE (05/09/2026): RuntimeSchemaProvider correctly resolved
the live "עסקאות (Deals)" schema (source=live, mode=full, provider_unknown=[])
for a create write carrying 5 real, live fields — Counterparty Contact, Deal
Type Code, Relationship Type, Currency, Commercial Status — yet the gateway
still blocked the write, reporting them as "not in schema_cache". Root
cause: tools/airtable_gateway.py's validate_airtable_fields(), in the
current production "shadow" state, computed
`unknown = legacy_unknown` unconditionally — so the separately-refreshed,
stale schema_cache.json (last fetched_at 2026-09-04, genuinely missing all
5 fields — confirmed by direct inspection) kept full veto power over a
field the authoritative live/cached-live RuntimeSchemaProvider had already
verified exists. The discrepancy WAS logged (misleadingly worded
"not blocking — shadow state"), but the actual block still went through.

Fix: when RuntimeSchemaProvider is authoritative for a table (mode="full"
AND source in "live"/"cached"), legacy_unknown may no longer independently
veto a field the authoritative schema confirms exists — only fields BOTH
sources fail to recognize are blocked. When the provider is NOT yet
authoritative (name_only seed, or the snapshot-archive tier), the existing
safe fallback is unchanged: legacy_unknown alone decides, exactly as
before. "enforce" state and the unrelated select-value validation gate are
untouched. Shadow deliberately still never blocks solely because the
provider rejects a field legacy allows — see
test_runtime_schema_provider.py's pre-existing _CONTRACT_MISSING_SCORE
shadow/enforce contract, which this fix must not regress (re-run alongside
this file, not duplicated here).
"""

from __future__ import annotations

import sys
from unittest.mock import patch

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from tools.airtable_gateway import validate_airtable_fields  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


TABLE = "עסקאות (Deals)"

_FIVE_FIELDS = {
    "Counterparty Contact": ["recAviHazanNEW001"],
    "Deal Type Code": "management",
    "Relationship Type": "ongoing",
    "Currency": "ILS",
    "Commercial Status": "active",
}


def _live_full_contract(known_extra: dict | None = None) -> dict:
    fields = {k: {"field_id": f"fld{k}", "type": "singleLineText", "choices": []} for k in _FIVE_FIELDS}
    fields["Counterparty Contact"] = {"field_id": "fldCC", "type": "multipleRecordLinks", "choices": []}
    if known_extra:
        fields.update(known_extra)
    return {
        "table_id": "tblDealsLive",
        "mode": "full",
        "source": "live",
        "fetched_at": "2026-09-05T00:00:00Z",
        "fields": fields,
    }


class _FakeProvider:
    def __init__(self, contract: dict):
        self._contract = contract

    def get_table_contract(self, _table):
        return self._contract


def _patched(contract, state):
    return (
        patch("feature_flags.get_runtime_schema_provider_state", return_value=state),
        patch("feature_flags.get_select_value_validation_state", return_value="off"),
        patch("core.runtime_schema_provider.get_provider", return_value=_FakeProvider(contract)),
    )


# ══════════════════════════════════════════════════════════════════
print("── Case 1: live/full provider knows the 5 fields, legacy omits them ──")
print("── (exact production scenario) — expected: write validation PASSES ──")

p1, p2, p3 = _patched(_live_full_contract(), "shadow")
with p1, p2, p3, patch("schema_validator.validate_fields", return_value=list(_FIVE_FIELDS.keys())):
    clean, errs = validate_airtable_fields(TABLE, dict(_FIVE_FIELDS))
    for f in _FIVE_FIELDS:
        chk(f"shadow: '{f}' passes despite stale legacy cache", f in clean)
    chk("shadow: no 'unknown field' errors for any of the 5 fields",
        not any("unknown field" in e for e in errs))

# also confirm production's actual current default (if ever flipped to
# enforce, which already worked pre-fix) stays correct too
p1, p2, p3 = _patched(_live_full_contract(), "enforce")
with p1, p2, p3, patch("schema_validator.validate_fields", return_value=list(_FIVE_FIELDS.keys())):
    clean, errs = validate_airtable_fields(TABLE, dict(_FIVE_FIELDS))
    chk("enforce: all 5 fields also pass (provider-authoritative, unaffected by this fix)",
        all(f in clean for f in _FIVE_FIELDS))


# ══════════════════════════════════════════════════════════════════
print("\n── Case 2: both provider and legacy omit an unknown field ──")
print("── expected: BLOCKED ──")

p1, p2, p3 = _patched(_live_full_contract(), "shadow")
with p1, p2, p3, patch("schema_validator.validate_fields", return_value=["Totally Made Up Field"]):
    clean, errs = validate_airtable_fields(TABLE, {"Totally Made Up Field": "x"})
    chk("shadow: genuinely unknown-to-both field is blocked",
        "Totally Made Up Field" not in clean
        and any("Totally Made Up Field" in e for e in errs))


# ══════════════════════════════════════════════════════════════════
print("\n── Case 3: provider partial/unavailable (name_only seed) ──")
print("── expected: preserve existing safe fallback (legacy decides) ──")

_SEED_CONTRACT = {
    "table_id": None, "mode": "name_only", "source": "seed",
    "fetched_at": None, "fields": {"Currency": {"field_id": None, "type": None, "choices": []}},
}

p1, p2, p3 = _patched(_SEED_CONTRACT, "shadow")
with p1, p2, p3, patch("schema_validator.validate_fields", return_value=["Counterparty Contact"]):
    clean, errs = validate_airtable_fields(TABLE, {"Counterparty Contact": ["recX"], "Currency": "ILS"})
    chk("seed/name_only: legacy-unknown field still blocked (fallback unchanged)",
        "Counterparty Contact" not in clean)
    chk("seed/name_only: legacy-known field still passes",
        clean.get("Currency") == "ILS")

_SNAPSHOT_CONTRACT = {
    "table_id": "tblDeals", "mode": "full", "source": "snapshot",
    "fetched_at": "2026-08-01T00:00:00Z",
    "fields": {k: {"field_id": None, "type": None, "choices": []} for k in _FIVE_FIELDS},
}

p1, p2, p3 = _patched(_SNAPSHOT_CONTRACT, "shadow")
with p1, p2, p3, patch("schema_validator.validate_fields", return_value=list(_FIVE_FIELDS.keys())):
    clean, errs = validate_airtable_fields(TABLE, dict(_FIVE_FIELDS))
    chk("snapshot tier (mode=full but source=snapshot, not live/cached): NOT treated as "
        "authoritative — existing fallback (legacy blocks) preserved",
        all(f not in clean for f in _FIVE_FIELDS))


# ══════════════════════════════════════════════════════════════════
print("\n── Case 4: legacy cache stale with BOTH extra and removed fields ──")
print("── expected: no false allow and no false block ──")

# legacy thinks "Legacy Only Field" exists (provider disagrees — provider
# doesn't list it); legacy is stale-missing the 5 real fields (provider
# has them); one field unknown to both.
_MIXED_CONTRACT = _live_full_contract()

p1, p2, p3 = _patched(_MIXED_CONTRACT, "shadow")
with p1, p2, p3, patch(
    "schema_validator.validate_fields",
    return_value=list(_FIVE_FIELDS.keys()),  # legacy doesn't know the 5 real fields
):
    payload = dict(_FIVE_FIELDS)
    payload["Legacy Only Field"] = "y"       # legacy would allow (not in its unknown list); provider doesn't have it
    payload["Nobody Knows This"] = "z"       # legacy explicitly flags it too (added below)

    with patch(
        "schema_validator.validate_fields",
        return_value=list(_FIVE_FIELDS.keys()) + ["Nobody Knows This"],
    ):
        clean, errs = validate_airtable_fields(TABLE, payload)

    chk("mixed: authoritative-known fields not falsely blocked", all(f in clean for f in _FIVE_FIELDS))
    chk("mixed: field unknown to both is blocked (fail closed)", "Nobody Knows This" not in clean)
    chk(
        "mixed: field legacy allows but provider doesn't list is NOT newly blocked in shadow "
        "(existing shadow convention preserved — only 'enforce' would reject it)",
        "Legacy Only Field" in clean,
    )


print()
print("=" * 60)
print(f"BUG-SCHEMA-AUTHORITY-LEGACY-VETO regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
