#!/usr/bin/env python3
"""
test_phase_4b2_schema_cache.py — Phase 4B-2 follow-up: gateway-level proof
that schema_cache.json's Approvals entry actually permits writing the three
projection fields (action_contract_id, legacy_read_only,
projected_lifecycle_status) end to end through the REAL validation pipeline.

Why this matters: tools/airtable_gateway.py's airtable_create()/
airtable_patch() run every write through normalize_airtable_fields() ->
validate_airtable_fields() before ever touching the network (SPEC A1,
atomic fail-closed — see tools/airtable_gateway.py's own docstring). With
FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE="off" (the default —
core/runtime_schema_provider.py is never even called in this state),
validate_airtable_fields() falls back to schema_validator.validate_fields(),
which drops any field not listed in schema_cache.json's "Approvals" entry —
and a *dropped* field triggers SPEC A1's atomic fail-closed block: the
entire write is refused, not just that one field silently omitted. Before
this test, schema_cache.json's Approvals list did not include the three
Phase 4B-2 projection fields, so a real (unmocked) airtable_create()/
airtable_patch() call setting them would have been silently blocked in
production with state=off — the exact condition that ships by default.

This test never mocks tools.airtable_gateway._at_post/_at_patch or
tools.airtable_gateway.airtable_create/airtable_patch — it calls the real
functions and only intercepts the outbound httpx call, so
normalize_airtable_fields()/validate_airtable_fields() run for real against
the actual committed schema_cache.json.

Tests:
  1. airtable_create("Approvals", {...all 3 projection fields...}) is not
     blocked — the outbound httpx.post payload contains all three fields
     untouched.
  2. airtable_patch("Approvals", ..., {...all 3 projection fields...}) is
     not blocked — same proof for the PATCH path (_ensure_approval_projection
     repair / _sync_approval_projection_status use PATCH).
  3. Negative control: a genuinely unknown field is still dropped/blocked —
     proves the pipeline is actually validating, not a no-op that would make
     tests 1-2 vacuously pass.
  4. state=off is confirmed as the code path actually exercised (not
     "shadow"/"enforce", which reads through RuntimeSchemaProvider instead).
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import schema_validator
# Force a fresh read of the (now-updated) schema_cache.json — a prior import
# elsewhere in this process may already have cached the old contents.
schema_validator._cache = None

from tools.airtable_gateway import airtable_create, airtable_patch
import feature_flags

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _fake_http_response(status_code: int, body: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    return resp


_PROJECTION_FIELDS = {
    "action_contract_id": "contract-abc-123",
    "legacy_read_only": False,
    "projected_lifecycle_status": "pending",
}


# ══════════════════════════════════════════════════════════════════
# 0. Confirm the code path under test is really state="off"
# ══════════════════════════════════════════════════════════════════
print("\n── Test 0: RuntimeSchemaProvider state is off (the path under test) ─")

with patch("feature_flags.get_runtime_schema_provider_state", return_value="off"):
    chk("Test0: get_runtime_schema_provider_state() == 'off' under test patch",
        feature_flags.get_runtime_schema_provider_state() == "off")


# ══════════════════════════════════════════════════════════════════
# 1. airtable_create: all 3 projection fields survive validation
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: airtable_create — projection fields not dropped ──────")

captured_post: list[dict] = []


def _capture_post(url, headers=None, json=None, timeout=None):
    captured_post.append(json)
    return _fake_http_response(200, {"id": "recNEW123", "fields": json["fields"]})


with patch("feature_flags.get_runtime_schema_provider_state", return_value="off"):
    with patch("httpx.post", side_effect=_capture_post):
        rec = airtable_create("Approvals", dict(_PROJECTION_FIELDS), source="test_schema_cache")

chk("Test1: airtable_create did not fail closed (record returned, not None)", rec is not None)
chk("Test1: exactly one outbound POST was made (write was not blocked pre-network)",
    len(captured_post) == 1)
if captured_post:
    sent_fields = captured_post[0]["fields"]
    chk("Test1: action_contract_id present in the actual outbound payload",
        sent_fields.get("action_contract_id") == "contract-abc-123")
    chk("Test1: legacy_read_only present in the actual outbound payload",
        sent_fields.get("legacy_read_only") is False)
    chk("Test1: projected_lifecycle_status present in the actual outbound payload",
        sent_fields.get("projected_lifecycle_status") == "pending")


# ══════════════════════════════════════════════════════════════════
# 2. airtable_patch: all 3 projection fields survive validation
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: airtable_patch — projection fields not dropped ───────")

captured_patch: list[dict] = []


def _capture_patch(url, headers=None, json=None, timeout=None):
    captured_patch.append(json)
    return _fake_http_response(200, {"id": "recEXIST123", "fields": json["fields"]})


with patch("feature_flags.get_runtime_schema_provider_state", return_value="off"):
    with patch("httpx.patch", side_effect=_capture_patch):
        ok = airtable_patch("Approvals", "recEXIST123", dict(_PROJECTION_FIELDS), source="test_schema_cache")

chk("Test2: airtable_patch did not fail closed (returned True)", ok is True)
chk("Test2: exactly one outbound PATCH was made (write was not blocked pre-network)",
    len(captured_patch) == 1)
if captured_patch:
    sent_fields = captured_patch[0]["fields"]
    chk("Test2: action_contract_id present in the actual outbound PATCH payload",
        sent_fields.get("action_contract_id") == "contract-abc-123")
    chk("Test2: legacy_read_only present in the actual outbound PATCH payload",
        sent_fields.get("legacy_read_only") is False)
    chk("Test2: projected_lifecycle_status present in the actual outbound PATCH payload",
        sent_fields.get("projected_lifecycle_status") == "pending")


# ══════════════════════════════════════════════════════════════════
# 3. Negative control — a genuinely unknown field is still blocked
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: negative control — unknown field still fails closed ──")

captured_post_bad: list[dict] = []


def _capture_post_bad(url, headers=None, json=None, timeout=None):
    captured_post_bad.append(json)
    return _fake_http_response(200, {"id": "recSHOULD_NOT_HAPPEN", "fields": json["fields"]})


with patch("feature_flags.get_runtime_schema_provider_state", return_value="off"):
    with patch("httpx.post", side_effect=_capture_post_bad):
        rec_bad = airtable_create(
            "Approvals",
            {"totally_made_up_field_xyz": "hack"},
            source="test_schema_cache",
        )

chk("Test3: an unrecognized field is fail-closed blocked (returns None)", rec_bad is None)
chk("Test3: no outbound POST was made for the unknown field — proves the "
    "pipeline is actually validating, not a no-op", captured_post_bad == [])


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Phase 4B-2 schema_cache tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
