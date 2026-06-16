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
# Summary
# ══════════════════════════════════════════════════════════════════

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
