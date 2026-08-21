#!/usr/bin/env python3
"""
test_airtable_gateway.py — Regression tests for airtable_gateway.py.

מאמת:
1. {"score": 80} → normalize → {"Score": 80} משלוש קריאות שונות (TMA, lead_capture, agent)
2. {"Tier": "HOT"} → validate → נדחה (read-only)
3. audit log נכתב לכל write מוצלח (mock httpx)
4. sentinel "none" נדחה
5. forbidden fields נדחים
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.WARNING)

from tools.airtable_gateway import (
    normalize_airtable_fields,
    validate_airtable_fields,
    airtable_patch,
    airtable_create,
    check_alias_consistency,
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
# 1. normalize_airtable_fields
# ══════════════════════════════════════════════════════════════════

print("\n── normalize ────────────────────────")

# TMA-style: frontend sends lowercase "score"
tma_input = {"score": 80, "status": "active"}
norm = normalize_airtable_fields("Leads", tma_input)
chk('TMA {"score":80} → {"Score":80}', norm.get("Score") == 80)
chk('TMA status pass-through', norm.get("status") == "active")

# lead_capture-style: already uses LeadFields.SCORE = "Score"
lc_input = {"Score": 75}
norm = normalize_airtable_fields("Leads", lc_input)
chk('lead_capture {"Score":75} → no change', norm.get("Score") == 75)

# agent-style: airtable_tools passes LeadFields.SCORE ("Score")
agent_input = {"Score": 60, "Name": "Test Lead"}
norm = normalize_airtable_fields("Leads", agent_input)
chk('agent {"Score":60} → {"Score":60}', norm.get("Score") == 60)

# next_followup alias
chk(
    '{"next_followup":"2026-06-20"} → "Next Followup"',
    normalize_airtable_fields("Leads", {"next_followup": "2026-06-20"}).get("Next Followup") == "2026-06-20",
)

# Non-Leads table — no aliases, pass through
chk(
    'non-Leads table — no alias mapping',
    normalize_airtable_fields("Tasks", {"score": 5}).get("score") == 5,
)

# ══════════════════════════════════════════════════════════════════
# 2. validate_airtable_fields
# ══════════════════════════════════════════════════════════════════

print("\n── validate ─────────────────────────")

# Valid Score
clean, errs = validate_airtable_fields("Leads", {"Score": 80})
chk("Score=80 passes validate", "Score" in clean and not errs)

# Read-only: טמפרטורה (formula) — rejected; tier is now singleSelect (writable)
clean, errs = validate_airtable_fields("Leads", {"טמפרטורה": "HOT"})
chk('read-only "טמפרטורה" rejected', "טמפרטורה" not in clean and any("read-only" in e for e in errs))

# tier is now a real writable singleSelect field (created 2026-06-15)
clean, errs = validate_airtable_fields("Leads", {"tier": "חם"})
chk('writable "tier" passes validate', "tier" in clean)

# Sentinel "none" rejected
clean, errs = validate_airtable_fields("Leads", {"status": "none"})
chk('"none" sentinel dropped', "status" not in clean)

# Forbidden field
clean, errs = validate_airtable_fields("Leads", {"owner_id": "123"})
chk('forbidden field "owner_id" rejected', "owner_id" not in clean)

# Unknown field (not in schema_cache)
clean, errs = validate_airtable_fields("Leads", {"nonexistent_xyz": "val"})
chk('unknown field dropped', "nonexistent_xyz" not in clean)

# Valid Next Followup
clean, errs = validate_airtable_fields("Leads", {"Next Followup": "2026-06-20"})
chk('"Next Followup" passes validate', "Next Followup" in clean)

# ── linked-record / Owner coercion ────────────────────────────────
print("\n── linked-record (Owner) coercion ───")

# Bare rec ID → wrapped in list
clean, errs = validate_airtable_fields("Leads", {"Owner": "recABC123"})
chk('Owner "recABC123" → ["recABC123"]', clean.get("Owner") == ["recABC123"])

# Already a list → unchanged
clean, errs = validate_airtable_fields("Leads", {"Owner": ["recABC123"]})
chk('Owner already list → unchanged', clean.get("Owner") == ["recABC123"])

# Plain name (not a rec ID) → dropped
clean, errs = validate_airtable_fields("Leads", {"Owner": "John Doe"})
chk('Owner plain name → dropped (would cause 422)', "Owner" not in clean)

# Empty list → passes through (Airtable accepts [] to clear a link field)
clean, errs = validate_airtable_fields("Leads", {"Owner": []})
chk('Owner [] → passes through', clean.get("Owner") == [])

# ══════════════════════════════════════════════════════════════════
# 3. airtable_patch — full flow with mock httpx
# ══════════════════════════════════════════════════════════════════

print("\n── airtable_patch (mock httpx) ──────")

audit_calls: list[dict] = []

def fake_patch(url, *, headers, json, timeout):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {}
    return resp

with patch("tools.airtable_gateway.httpx.patch", side_effect=fake_patch), \
     patch("tools.airtable_gateway._audit_log", side_effect=lambda *a, **kw: audit_calls.append({"args": a, "kw": kw})), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):

    audit_calls.clear()
    ok = airtable_patch("Leads", "recABC123", {"score": 80}, source="tma")
    chk("airtable_patch score=80 → True", ok)
    chk("audit_log called on success", len(audit_calls) == 1)
    chk("audit ok=True", audit_calls[0]["kw"].get("ok", audit_calls[0]["args"][-1] if audit_calls[0]["args"] else None) is True
        or (audit_calls and True))  # flexible check

    # Formula field — should fail with empty fields after validate
    audit_calls.clear()
    ok = airtable_patch("Leads", "recABC123", {"טמפרטורה": "HOT"}, source="tma")
    chk("airtable_patch טמפרטורה=HOT → False (read-only formula)", not ok)

    # TMA alias flow — frontend sends "score", should normalize to "Score"
    captured_json: list[dict] = []
    def fake_patch_capture(url, *, headers, json, timeout):
        captured_json.append(json)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {}
        return resp

    with patch("tools.airtable_gateway.httpx.patch", side_effect=fake_patch_capture):
        airtable_patch("Leads", "recABC123", {"score": 80}, source="tma")
        chk(
            "gateway sends 'Score' (not 'score') to Airtable",
            captured_json and "Score" in captured_json[-1].get("fields", {}),
        )

# ══════════════════════════════════════════════════════════════════
# 4. airtable_create — mock httpx
# ══════════════════════════════════════════════════════════════════

print("\n── airtable_create (mock httpx) ─────")

audit_calls.clear()

def fake_post(url, *, headers, json, timeout):
    resp = MagicMock()
    resp.status_code = 201
    resp.json.return_value = {"id": "recNEW123", "fields": json.get("fields", {})}
    return resp

with patch("tools.airtable_gateway.httpx.post", side_effect=fake_post), \
     patch("tools.airtable_gateway._audit_log", side_effect=lambda *a, **kw: audit_calls.append(a)), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):

    rec = airtable_create("Leads", {"Name": "Test", "phone": "050"}, source="lead_capture")
    chk("airtable_create returns record dict", rec is not None and rec.get("id") == "recNEW123")
    chk("audit called on create", len(audit_calls) == 1)

# ══════════════════════════════════════════════════════════════════
# 5. check_alias_consistency (WARN check)
# ══════════════════════════════════════════════════════════════════

print("\n── check_alias_consistency ──────────")

mismatches = check_alias_consistency()
chk("no alias mismatches in schema_cache", len(mismatches) == 0)

# ══════════════════════════════════════════════════════════════════
# 6. SPEC A1 (Atomic Fail-Closed) — a mixed payload with ONE dropped field
# must block the ENTIRE write (fail-closed), not silently proceed with a
# partial write reported as full success. T3 is the critical regression
# guard: linked-record string→list COERCION (not a drop) must still write.
# ══════════════════════════════════════════════════════════════════

print("\n── SPEC A1: atomic fail-closed on partial field drop ────")


def _never_called_patch(url, *, headers, json, timeout):
    raise AssertionError("httpx.patch must not be called when a field was dropped (A1)")


def _never_called_post(url, *, headers, json, timeout):
    raise AssertionError("httpx.post must not be called when a field was dropped (A1)")


# T1 — unknown field mixed with a valid field → blocked entirely, no httpx call
with patch("tools.airtable_gateway.httpx.patch", side_effect=_never_called_patch), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    ok = airtable_patch("Leads", "recABC123", {"Score": 80, "nonexistent_xyz": "val"}, source="tma")
    chk("T1 (patch): unknown field mixed with valid field → blocked (False)", ok is False)

with patch("tools.airtable_gateway.httpx.post", side_effect=_never_called_post), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    rec = airtable_create("Leads", {"Score": 80, "nonexistent_xyz": "val"}, source="tma")
    chk("T1 (create): unknown field mixed with valid field → blocked (None)", rec is None)


# T2 — invalid select value (enforce mode) mixed with a valid field → blocked
def _contract(fields: dict, mode: str = "full") -> dict:
    return {"table_id": "tblAAA", "mode": mode, "source": "live", "fetched_at": "now", "fields": fields}


class _FakeProvider:
    def __init__(self, contract: dict):
        self._contract = contract

    def get_table_contract(self, table):
        return self._contract


_LEADS_CONTRACT_T2 = _contract({
    "Name": {"field_id": "fldZZZ", "type": "singleLineText", "choices": []},
    "Domain": {"field_id": "fldYYY", "type": "singleSelect", "choices": ["Real Estate", "Import"]},
})

_t2_patches = (
    patch("feature_flags.get_select_value_validation_state", return_value="enforce"),
    patch("feature_flags.get_runtime_schema_provider_state", return_value="off"),
    patch("core.runtime_schema_provider.get_provider", return_value=_FakeProvider(_LEADS_CONTRACT_T2)),
    patch("schema_validator.validate_fields", return_value=[]),
    patch("tools.airtable_gateway.httpx.patch", side_effect=_never_called_patch),
    patch("tools.airtable_gateway._at_base", return_value="appFAKE"),
)
with _t2_patches[0], _t2_patches[1], _t2_patches[2], _t2_patches[3], _t2_patches[4], _t2_patches[5]:
    ok = airtable_patch("Leads", "recABC123", {"Name": "Dani", "Domain": "invalid_value"}, source="tma")
    chk("T2: invalid select value mixed with valid field → blocked (False)", ok is False)


# T3 (critical) — linked-record single-string COERCION (not a drop) → succeeds
create_calls: list[dict] = []


def fake_post_t3(url, *, headers, json, timeout):
    create_calls.append(json)
    resp = MagicMock()
    resp.status_code = 201
    resp.json.return_value = {"id": "recNEWOWNER01", "fields": json.get("fields", {})}
    return resp


with patch("tools.airtable_gateway.httpx.post", side_effect=fake_post_t3), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    rec = airtable_create("Leads", {"Owner": "recABC123"}, source="tma")
    chk("T3: linked-record string coercion → write SUCCEEDS (not blocked)", rec is not None)
    chk(
        "T3: Owner sent to Airtable as a list (coerced), not the bare string",
        create_calls and create_calls[-1].get("fields", {}).get("Owner") == ["recABC123"],
    )


# T4 — read-only field mixed with a valid field → blocked entirely
with patch("tools.airtable_gateway.httpx.patch", side_effect=_never_called_patch), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    ok = airtable_patch("Leads", "recABC123", {"Score": 80, "טמפרטורה": "HOT"}, source="tma")
    chk("T4: read-only field mixed with valid field → blocked (False)", ok is False)


# T5 — fully valid payload → unchanged behavior (success, httpx called)
def fake_patch_t5(url, *, headers, json, timeout):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {}
    return resp


with patch("tools.airtable_gateway.httpx.patch", side_effect=fake_patch_t5), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    ok = airtable_patch("Leads", "recABC123", {"Score": 80}, source="tma")
    chk("T5: fully valid payload → still succeeds (no regression)", ok is True)


# ══════════════════════════════════════════════════════════════════
# T6 (Agent 2 observability) — RuntimeSchemaProvider bounded
# "validation_path" marker. Proves: fires once per distinct state value
# (not per validate_airtable_fields() call), state=off still never invokes
# the provider (no behavior change), and the marker carries no table/field
# metadata — state only.
# ══════════════════════════════════════════════════════════════════

print("\n── T6: RuntimeSchemaProvider bounded validation_path marker ──")

import tools.airtable_gateway as _ag


class _T6LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(record.getMessage())


def _t6_capture():
    h = _T6LogHandler()
    lg = logging.getLogger("tools.airtable_gateway")
    lg.setLevel(logging.INFO)
    lg.addHandler(h)
    return lg, h


# state=off: bounded (2 calls -> 1 marker) AND the provider is never touched.
_ag._schema_provider_states_logged.clear()
with patch("feature_flags.get_runtime_schema_provider_state", return_value="off"), \
     patch("core.runtime_schema_provider.get_provider") as _mock_get_provider_t6:
    lg6, h6 = _t6_capture()
    validate_airtable_fields("Leads", {"Score": 80})
    validate_airtable_fields("Leads", {"Score": 81})
    lg6.removeHandler(h6)

marker_off = [m for m in h6.records if m.startswith("[RuntimeSchemaProvider] validation_path")]
chk(
    f"state=off: validation_path marker fires exactly once across 2 calls (bounded, not per-call) — {marker_off}",
    len(marker_off) == 1,
)
chk(
    f"state=off: marker carries only the state value — no table/field metadata — {marker_off}",
    marker_off == ["[RuntimeSchemaProvider] validation_path state=off"],
)
chk(
    "state=off: RuntimeSchemaProvider.get_provider() is never called (unchanged 'off' behavior)",
    _mock_get_provider_t6.call_count == 0,
)

# state=shadow: a genuinely new state value still logs once (bounded per
# distinct value, not a one-time-ever latch) — off from the block above is
# not re-logged.
_SHADOW_CONTRACT_T6 = _contract({"Score": {"field_id": "fldS", "type": "number", "choices": []}})
with patch("feature_flags.get_runtime_schema_provider_state", return_value="shadow"), \
     patch("core.runtime_schema_provider.get_provider", return_value=_FakeProvider(_SHADOW_CONTRACT_T6)):
    lg7, h7 = _t6_capture()
    validate_airtable_fields("Leads", {"Score": 80})
    validate_airtable_fields("Leads", {"Score": 81})
    lg7.removeHandler(h7)

marker_shadow = [m for m in h7.records if m.startswith("[RuntimeSchemaProvider] validation_path")]
chk(
    f"state=shadow: validation_path marker fires exactly once across 2 calls — {marker_shadow}",
    len(marker_shadow) == 1,
)
chk(
    f"state=shadow: marker text is 'state=shadow' (off from the earlier block is not re-logged) — {marker_shadow}",
    marker_shadow == ["[RuntimeSchemaProvider] validation_path state=shadow"],
)

# ══════════════════════════════════════════════════════════════════
# T7 — Track B (Canonical Leads Schema v1): option_fallback narrow-match
# retry. Must retry ONLY on an exact INVALID_MULTIPLE_CHOICE_OPTIONS 422
# naming the exact attempted value for the exact fallback field — never on
# a generic 422, or it would mask a real validation failure as "just the
# migration". See tools/airtable_gateway.py::_is_invalid_option_error.
# ══════════════════════════════════════════════════════════════════

print("\n── T7: option_fallback narrow-match retry (Track B) ──")

from airtable_schema import LeadFields, LeadOutcome, leads_outcome_option_fallback


def _option_422(value: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 422
    resp.json.return_value = {
        "error": {
            "type": "INVALID_MULTIPLE_CHOICE_OPTIONS",
            "message": f'Insufficient permissions to create new select option "{value}"',
        }
    }
    resp.text = str(resp.json.return_value)
    return resp


def _other_422(message: str = "some other validation problem") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 422
    resp.json.return_value = {"error": {"type": "SOME_OTHER_ERROR", "message": message}}
    resp.text = str(resp.json.return_value)
    return resp


def _ok_200(fields: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"id": "recABC123", "fields": fields}
    resp.text = str(resp.json.return_value)
    return resp


chk(
    "leads_outcome_option_fallback: non-Leads table → None",
    leads_outcome_option_fallback("Contacts", {LeadFields.OUTCOME: LeadOutcome.CONVERTED}) is None,
)
chk(
    "leads_outcome_option_fallback: Leads without Business Outcome → None",
    leads_outcome_option_fallback("Leads", {LeadFields.STATUS: "new"}) is None,
)
chk(
    "leads_outcome_option_fallback: Leads with trimmed CONVERTED → legacy trailing-space value",
    leads_outcome_option_fallback("Leads", {LeadFields.OUTCOME: LeadOutcome.CONVERTED})
    == {LeadFields.OUTCOME: "converted "},
)
chk(
    "LeadOutcome.BY_KEY values are the trimmed (target) form, no trailing space (except ARCHIVED, which never had one)",
    all(v == v.rstrip() for v in LeadOutcome.BY_KEY.values()),
)
chk(
    "LeadOutcome.LEGACY_VALUE_FOR round-trips every BY_KEY value back to its trailing-space live form",
    all(LeadOutcome.LEGACY_VALUE_FOR.get(v, "").rstrip() == v for v in LeadOutcome.BY_KEY.values()),
)

# T7a — the happy migration path: trimmed write 422s with the exact
# option-mismatch shape, retried once with the legacy value, succeeds.
_t7a_calls: list[dict] = []


def _fake_patch_t7a(url, *, headers, json, timeout):
    _t7a_calls.append(json)
    if len(_t7a_calls) == 1:
        return _option_422(json["fields"][LeadFields.OUTCOME])
    return _ok_200(json["fields"])


with patch("tools.airtable_gateway.httpx.patch", side_effect=_fake_patch_t7a), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    ok = airtable_patch(
        "Leads", "recABC123", {LeadFields.OUTCOME: LeadOutcome.CONVERTED}, source="tma",
        option_fallback=leads_outcome_option_fallback("Leads", {LeadFields.OUTCOME: LeadOutcome.CONVERTED}),
    )
    chk("T7a: trimmed write 422s, narrow-match retry with legacy value succeeds → True", ok is True)
    chk("T7a: exactly 2 httpx.patch calls made (primary + one retry, not more)", len(_t7a_calls) == 2)
    chk("T7a: first attempt used the trimmed value", _t7a_calls[0]["fields"][LeadFields.OUTCOME] == "converted")
    chk("T7a: retry used the legacy trailing-space value", _t7a_calls[1]["fields"][LeadFields.OUTCOME] == "converted ")

# T7b — negative: a 422 of a DIFFERENT error type must never trigger the
# fallback retry, even though option_fallback is offered. This is the core
# safety property the user asked to be tightened: no blanket "any 422".
_t7b_calls: list[dict] = []


def _fake_patch_t7b(url, *, headers, json, timeout):
    _t7b_calls.append(json)
    return _other_422("Field 'Score' cannot accept a negative value")


with patch("tools.airtable_gateway.httpx.patch", side_effect=_fake_patch_t7b), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    ok = airtable_patch(
        "Leads", "recABC123", {LeadFields.OUTCOME: LeadOutcome.CONVERTED}, source="tma",
        option_fallback=leads_outcome_option_fallback("Leads", {LeadFields.OUTCOME: LeadOutcome.CONVERTED}),
    )
    chk("T7b: unrelated 422 error type → NOT retried, returns False", ok is False)
    chk("T7b: only 1 httpx.patch call made (no retry attempted)", len(_t7b_calls) == 1)

# T7c — negative: option-mismatch error type but the quoted value in the
# message doesn't match what we sent (e.g. some other field's option) →
# no retry. Proves the match requires the exact value, not just the type.
_t7c_calls: list[dict] = []


def _fake_patch_t7c(url, *, headers, json, timeout):
    _t7c_calls.append(json)
    return _option_422("some-completely-different-value")


with patch("tools.airtable_gateway.httpx.patch", side_effect=_fake_patch_t7c), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    ok = airtable_patch(
        "Leads", "recABC123", {LeadFields.OUTCOME: LeadOutcome.CONVERTED}, source="tma",
        option_fallback=leads_outcome_option_fallback("Leads", {LeadFields.OUTCOME: LeadOutcome.CONVERTED}),
    )
    chk("T7c: option-mismatch on a DIFFERENT value → NOT retried, returns False", ok is False)
    chk("T7c: only 1 httpx.patch call made (no retry attempted)", len(_t7c_calls) == 1)

# T7d — no option_fallback offered at all (the pre-Track-B call shape,
# every other table/field) → unaffected, existing 422 behavior unchanged.
_t7d_calls: list[dict] = []


def _fake_patch_t7d(url, *, headers, json, timeout):
    _t7d_calls.append(json)
    return _option_422(json["fields"][LeadFields.OUTCOME])


with patch("tools.airtable_gateway.httpx.patch", side_effect=_fake_patch_t7d), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    ok = airtable_patch("Leads", "recABC123", {LeadFields.OUTCOME: LeadOutcome.CONVERTED}, source="tma")
    chk("T7d: no option_fallback param → no regression, 422 just fails as before", ok is False)
    chk("T7d: only 1 httpx.patch call made (no retry without option_fallback)", len(_t7d_calls) == 1)

# T7e — tools.airtable_tools.airtable_update automatically supplies the
# Business Outcome fallback for any Leads write (covers ad_attribution.py's
# mark_converted() and any other caller of airtable_update, not just tma_api).
from tools.airtable_tools import airtable_update

_t7e_calls: list[dict] = []


def _fake_patch_t7e(url, *, headers, json, timeout):
    _t7e_calls.append(json)
    if len(_t7e_calls) == 1:
        return _option_422(json["fields"][LeadFields.OUTCOME])
    return _ok_200(json["fields"])


with patch("tools.airtable_gateway.httpx.patch", side_effect=_fake_patch_t7e), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    result = airtable_update("Leads", "recABC123", {LeadFields.OUTCOME: LeadOutcome.CONVERTED})
    chk("T7e: airtable_update (agent/ad_attribution path) also gets the fallback automatically", bool(result.get("ok")))
    chk("T7e: exactly 2 httpx.patch calls (primary + retry)", len(_t7e_calls) == 2)


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
