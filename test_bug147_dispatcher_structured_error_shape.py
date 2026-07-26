#!/usr/bin/env python3
"""
test_bug147_dispatcher_structured_error_shape.py — Narrow regression coverage
for BUG-147 Patch A only (see BUG_AUDIT_LOG.md's BUG-147).

Root cause: tools/dispatcher.py's dispatch_tool() runs
action_validator.validate_action() before the tool-specific case block. When
it returns ActionBlocked (e.g. a presence-check failure — missing required
params like table/fields, exactly what a BUG-143-shaped legacy Sheets
payload produces), dispatch_tool() used to return the bare
ActionBlocked.reason string. core.anti_hallucination.verify_execution() then
misclassified that as "expected structured result dict with ok=true; got
plain string" instead of surfacing the real validation reason — and,
critically, a bare string is not itself proof of failure, only proof of
"not the expected shape". Patch A makes dispatch_tool() return the C53-A
{ok, tool, user_message} structured dict for any tool in
core.anti_hallucination._EVIDENCE_VALIDATORS (structured write tools,
airtable_add included) on this path.

Three properties only, matching the approved narrow scope for this PR:
  1. An ActionBlocked validator result is returned as an explicit
     structured failure (dict, ok=False) for a structured write tool.
  2. The ActionGateway's own tool_executor boundary
     (core.action_gateway._make_dispatch_executor()) — the exact closure
     ActionGateway calls to run a tool — no longer receives a bare string
     either; it receives the same structured dict, unchanged.
  3. verify_execution() can never classify a validator-blocked Airtable
     write as a success — status is explicitly "failed", never "success".

No app.py or core/action_gateway.py *code* changes are involved — the
second property is verified against action_gateway.py's existing,
unmodified _make_dispatch_executor() boundary function.
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
from core.action_gateway import _make_dispatch_executor  # noqa: E402
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

# The exact reported root-cause payload: legacy Sheets-shaped input under
# airtable_add (missing both required "table" and "fields") — blocked by
# action_validator's presence check before the tool-specific case ever runs.
_blocked_sheets_payload = {"row_data": ["a", "b"], "sheet_name": "Tasks"}


# ══════════════════════════════════════════════════════════════════
# Property 1 — an ActionBlocked validator result is returned as an
# explicit structured failure, not a bare string.
# ══════════════════════════════════════════════════════════════════
print("\n── Property 1: ActionBlocked → explicit structured failure ──────────")

result1 = dispatch_tool(
    "airtable_add", _blocked_sheets_payload,
    identity=owner, trusted_source="agent",
)
chk("dispatch_tool() returns a dict, not a plain string", isinstance(result1, dict))
chk("structured result has ok=False", isinstance(result1, dict) and result1.get("ok") is False)
chk("structured result identifies the tool", isinstance(result1, dict) and result1.get("tool") == "airtable_add")
chk("structured result carries the real validation reason as user_message",
    isinstance(result1, dict) and bool(result1.get("user_message")))


# ══════════════════════════════════════════════════════════════════
# Property 2 — the ActionGateway's own tool_executor boundary
# (core.action_gateway._make_dispatch_executor(), the unmodified function
# ActionGateway actually calls in production) no longer receives a bare
# plain string for this same blocked payload.
# ══════════════════════════════════════════════════════════════════
print("\n── Property 2: ActionGateway tool_executor boundary — no bare string ─")


class _NullLedger:
    """Minimal stand-in — _make_dispatch_executor() only calls find_by_id()
    to resolve identity when identity isn't already supplied; identity is
    supplied explicitly below, so no real ledger/contract is needed."""

    def find_by_id(self, contract_id):
        return None


gateway_executor = _make_dispatch_executor(_NullLedger())
result2 = gateway_executor(
    "airtable_add", _blocked_sheets_payload, contract_id="bug147-test-contract",
    identity=owner,
)
chk("ActionGateway's tool_executor receives a dict, not a plain string",
    isinstance(result2, dict))
chk("ActionGateway's tool_executor sees ok=False",
    isinstance(result2, dict) and result2.get("ok") is False)


# ══════════════════════════════════════════════════════════════════
# Property 3 — no success classification can occur for a validator-blocked
# Airtable action: verify_execution() must never report "success" here.
# ══════════════════════════════════════════════════════════════════
print("\n── Property 3: verify_execution() never classifies this as success ──")

check1 = verify_execution("airtable_add", result1)
chk("verify_execution() status is explicitly 'failed'", check1.status == "failed")
chk("verify_execution() status is never 'success'", check1.status != "success")
chk("verify_execution() does not fall back to the generic "
    "'expected structured result dict' misclassification",
    "expected structured result dict" not in (check1.reason or ""))

check2 = verify_execution("airtable_add", result2)
chk("verify_execution() on the ActionGateway-boundary result is also 'failed', never 'success'",
    check2.status == "failed" and check2.status != "success")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"BUG-147/Patch A regression: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
