#!/usr/bin/env python3
"""
test_bug147_dispatcher_structured_error_shape.py — Regression tests for the
PM460 Post-Merge narrow Patch A (see BUG_AUDIT_LOG.md's BUG-147 and
docs/architecture/action-gateway/PM460_POSTMERGE_MINIMAL_PATCH_GATE.md).

BUG-147, corrected root cause: tools/dispatcher.py's dispatch_tool() ran
action_validator.validate_action() BEFORE the tool-specific case block. When
it returned ActionBlocked (e.g. a presence-check failure — missing required
params like table/fields), dispatch_tool() returned the bare reason string
(no "❌" prefix — e.g. "לאיזו טבלה?"). core.anti_hallucination.verify_execution()
then misclassified that as "expected structured result dict with ok=true;
got plain string" instead of surfacing the real validation reason — exactly
what a BUG-143 malformed payload (row_data/sheet_name instead of table/
fields, missing both required airtable_add params) hits at execution time.

An earlier hypothesis (the LeadsDirectWriteBlocked/TenantScopeViolation
str(e) returns inside the airtable_add case) turned out to already be
"❌"-prefixed and therefore already correctly classified — Patch A still
converts those two to the same structured shape for consistency (harmless,
matches the "every executor returns a unified structure" principle), but
they were not the actual reported symptom's cause. This test covers both.

This is a narrow patch, NOT a full fix of BUG-147/BUG-143 — see the Impact
Matrix doc referenced above for exact scope.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug147-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG147_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug147Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug147Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import tools.dispatcher as dispatcher_module  # noqa: E402
from tools.dispatcher import dispatch_tool  # noqa: E402
from core.anti_hallucination import verify_execution  # noqa: E402
from identity import Identity, Role  # noqa: E402

# No live Airtable in this sandbox — EmergencyStopManager's flag lookup fails
# closed (blocked) without network access. Not what this test is about, so
# force it off, same as every other dispatch_tool()-level test in this repo.
_no_emergency_stop = patch.object(dispatcher_module._ff, "is_enabled", return_value=False)
_no_emergency_stop.start()

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


owner = Identity(
    user_id="owner-bug147", role=Role.OWNER, display_name="owner-bug147",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="owner-bug147",
)


# ══════════════════════════════════════════════════════════════════
# 1. The actual reported root cause: legacy Sheets-shaped payload under
# airtable_add (missing table AND fields) — action_validator's presence
# check blocks it, and the result must be a structured dict, not a bare
# question string that verify_execution() would misclassify.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: presence-check block (missing table/fields) — structured dict ──")

result1 = dispatch_tool(
    "airtable_add", {"row_data": ["a", "b"], "sheet_name": "Tasks"},
    identity=owner, trusted_source="agent",
)
chk("Test1: result is a dict, not a plain string", isinstance(result1, dict))
chk("Test1: ok=False", isinstance(result1, dict) and result1.get("ok") is False)

check1 = verify_execution("airtable_add", result1)
chk("Test1: verify_execution classifies as failed", check1.status == "failed")
chk("Test1: verify_execution surfaces the real validation reason, not the "
    "generic 'expected structured result dict' misclassification",
    "expected structured result dict" not in (check1.reason or ""))


# ══════════════════════════════════════════════════════════════════
# 2. A read-only / unregistered tool blocked by action_validator must keep
# its existing plain-string behavior — no regression for tools outside the
# structured-write set.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: unrelated tool block — unchanged plain-string behavior ────")

result2 = dispatch_tool("airtable_get", {}, identity=owner, trusted_source="agent")
chk("Test2: airtable_get block still returns a plain string (unchanged)",
    isinstance(result2, str))


# ══════════════════════════════════════════════════════════════════
# 3. LeadsDirectWriteBlocked path (direct Leads write from the agent) — was
# already "❌"-prefixed (already correctly classified), now also a
# structured dict for consistency with the rest of the airtable_add case.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: LeadsDirectWriteBlocked — structured dict, still ok=False ──")

result3 = dispatch_tool(
    "airtable_add", {"table": "Leads", "fields": {"שם": "בדיקה"}},
    identity=owner, trusted_source="agent",
)
chk("Test3: result is a dict", isinstance(result3, dict))
chk("Test3: ok=False (blocked write, never a false success)",
    isinstance(result3, dict) and result3.get("ok") is False)
check3 = verify_execution("airtable_add", result3)
chk("Test3: verify_execution classifies as failed", check3.status == "failed")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"BUG-147/Patch A regression: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
