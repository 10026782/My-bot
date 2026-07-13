#!/usr/bin/env python3
"""
test_deterministic_denial.py — Deterministic-Denial Short-Circuit regression suite.

Problem: Intent.UPDATE_LEAD (and Intent.CREATE_LEAD) are classified by the
Router, before the Agent runs, with an outcome that is already 100% knowable:
enforce_leads_write_gate() unconditionally blocks any Leads write with
source="agent" (BUG-091), and tool_registry excludes some roles from a tool's
roles_allowed entirely — neither depends on what Claude does. Previously the
system still paid for a full Claude round-trip before discovering this.

check_deterministic_denial() (core/router/deterministic_denial.py) predicts
these two outcomes using the REAL gate functions (never reimplemented) and
lets app.py return early, before build_context()/the Agent Loop.

מאמת:
1-7.  Unit-level behavior of check_deterministic_denial() directly.
8-12. End-to-end app.run_agent() proving zero Claude round-trips for a
      predicted denial, and zero behavior change for anything else.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-detdenial-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DETDENIAL_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patDetDenialTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDetDenialTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


import tool_registry  # noqa: E402
from identity import Identity, Role  # noqa: E402
from tools.airtable_security import _leads_write_blocked_message  # noqa: E402
from core.router.route_decision import Intent  # noqa: E402
from core.router.deterministic_denial import (  # noqa: E402
    check_deterministic_denial,
    INTENT_TOOL_HINTS,
)

_MANAGER  = Identity(user_id="u1", role=Role.MANAGER, tenant_id="boss_hq")
_GUEST    = Identity(user_id="u2", role=Role.GUEST, tenant_id="boss_hq")
_OWNER    = Identity(user_id="u3", role=Role.OWNER, tenant_id="boss_hq")
_EMPLOYEE = Identity(user_id="u4", role=Role.EMPLOYEE, tenant_id="boss_hq")

# ══════════════════════════════════════════════════════════════════
# 1-4. Unit tests on check_deterministic_denial() directly
# ══════════════════════════════════════════════════════════════════
print("\n── check_deterministic_denial(): Leads source-gate ────")

d1 = check_deterministic_denial(Intent.UPDATE_LEAD, _MANAGER)
chk("UPDATE_LEAD + manager (allowed role) -> denied, reason=leads_write_gate",
    d1 is not None and d1.reason == "leads_write_gate")
chk("denial message is byte-equal to _leads_write_blocked_message('airtable_update')",
    d1 is not None and d1.message == _leads_write_blocked_message("airtable_update"))

d2 = check_deterministic_denial(Intent.UPDATE_LEAD, _GUEST)
chk("UPDATE_LEAD + guest (excluded role) -> denied, reason=role_not_allowed",
    d2 is not None and d2.reason == "role_not_allowed")

d3 = check_deterministic_denial(Intent.UPDATE_LEAD, _OWNER)
chk("UPDATE_LEAD + owner -> still leads_write_gate (source-based, not role-based)",
    d3 is not None and d3.reason == "leads_write_gate")

d4 = check_deterministic_denial(Intent.CREATE_LEAD, _EMPLOYEE)
chk("CREATE_LEAD + employee (allowed role for airtable_add) -> leads_write_gate",
    d4 is not None and d4.reason == "leads_write_gate")
chk("CREATE_LEAD denial message byte-equal to _leads_write_blocked_message('airtable_add')",
    d4 is not None and d4.message == _leads_write_blocked_message("airtable_add"))

# ══════════════════════════════════════════════════════════════════
# 5. Fail-safe: intent with no hint entry -> None for any role
# ══════════════════════════════════════════════════════════════════
print("\n── fail-safe: no hint entry never over-blocks ─────────")

d5a = check_deterministic_denial(Intent.CREATE_TASK, _GUEST)
chk("CREATE_TASK (no hint) + guest -> None (proceeds to Agent as today)", d5a is None)

d5b = check_deterministic_denial(Intent.FIND_LEAD, _OWNER)
chk("FIND_LEAD (no hint) + owner -> None", d5b is None)

# ══════════════════════════════════════════════════════════════════
# 6. Structural guard: every hint references real registry/gate data
# ══════════════════════════════════════════════════════════════════
print("\n── structural guard: hint table matches real gates ────")

from tools.airtable_security import _LEADS_WRITE_OPS  # noqa: E402

_all_hints_valid = True
for _intent, _hints in INTENT_TOOL_HINTS.items():
    for _hint in _hints:
        if tool_registry.get(_hint.tool_name) is None:
            _all_hints_valid = False
        if _hint.leads_table and _hint.tool_name not in _LEADS_WRITE_OPS:
            _all_hints_valid = False
chk("every ToolHint.tool_name exists in tool_registry, leads_table hints use a real Leads write op",
    _all_hints_valid)

# ══════════════════════════════════════════════════════════════════
# 7. Non-bypass / regression guard — real gates untouched
# ══════════════════════════════════════════════════════════════════
print("\n── regression: real gates still enforce independently ─")

from tools.airtable_security import enforce_leads_write_gate, LeadsDirectWriteBlocked  # noqa: E402
from tool_registry import enforce, ToolDenied  # noqa: E402

try:
    enforce_leads_write_gate("airtable_update", {"table": "Leads"}, source="agent")
    _gate_still_raises = False
except LeadsDirectWriteBlocked:
    _gate_still_raises = True
chk("enforce_leads_write_gate() still raises on its own, unmodified by this change",
    _gate_still_raises)

try:
    enforce("airtable_update", _GUEST)
    _registry_still_raises = False
except ToolDenied:
    _registry_still_raises = True
chk("tool_registry.enforce() still raises on its own, unmodified by this change",
    _registry_still_raises)

# ══════════════════════════════════════════════════════════════════
# 8-12. End-to-end app.run_agent() — mocked Identity/Router/Anthropic
# ══════════════════════════════════════════════════════════════════
import app  # noqa: E402  (env vars above must be set before import)
from core.router.route_decision import RouteDecision, Handler  # noqa: E402
from context import AgentContext  # noqa: E402


def _fake_text_response(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def _run_agent(chat_id: str, identity: Identity, route: RouteDecision, reply_text: str = "קיבלתי."):
    fake_ctx = AgentContext(
        system_prompt="test system prompt", allowed_tools=[],
        memory_key=f"detdenial:{chat_id}", max_tokens=500,
        model="claude-haiku-test", identity_label=identity.role,
    )
    mock_create = None
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=route), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app.client.messages, "create",
                       return_value=_fake_text_response(reply_text)) as mock_create:
        reply = app.run_agent("עדכן ליד קיים — הלל זקין מעוניין שיחזרו אליו", chat_id, channel="telegram")
    return reply, mock_create


print("\n── end-to-end app.run_agent(): zero Claude round-trips ─")

route_update_lead = RouteDecision(handler=Handler.AGENT, intent=Intent.UPDATE_LEAD, tool_allowed=True)

reply8, mock8 = _run_agent("t8", Identity(user_id="t8", role=Role.MANAGER, external_id="t8", channel="telegram"),
                            route_update_lead)
chk("UPDATE_LEAD + manager -> run_agent() returns the Leads-blocked message",
    "עדכון ליד קיים דרך הצ׳אט חסום" in reply8)
chk("UPDATE_LEAD + manager -> mocked Claude client was NEVER called (zero round-trips)",
    mock8.call_count == 0)

reply9, mock9 = _run_agent("t9", Identity(user_id="t9", role=Role.GUEST, external_id="t9", channel="telegram"),
                            route_update_lead)
chk("UPDATE_LEAD + guest -> run_agent() returns the role-denial message",
    "אינה זמינה עבור התפקיד שלך" in reply9)
chk("UPDATE_LEAD + guest -> mocked Claude client was NEVER called", mock9.call_count == 0)

route_update_task = RouteDecision(handler=Handler.AGENT, intent=Intent.UPDATE_TASK, tool_allowed=True)
reply10, mock10 = _run_agent("t10", Identity(user_id="t10", role=Role.MANAGER, external_id="t10", channel="telegram"),
                              route_update_task)
chk("UPDATE_TASK (no hint entry) -> run_agent() proceeds normally (no over-blocking)",
    reply10 == "קיבלתי.")
chk("UPDATE_TASK (no hint entry) -> mocked Claude client WAS called", mock10.call_count == 1)

route_restricted = RouteDecision(handler=Handler.AGENT, intent=Intent.UPDATE_LEAD, tool_allowed=False, restricted=True)
reply11, mock11 = _run_agent("t11", Identity(user_id="t11", role=Role.MANAGER, external_id="t11", channel="telegram"),
                              route_restricted)
chk("UPDATE_LEAD + tool_allowed=False (restricted) -> short-circuit does NOT fire, existing restricted flow runs",
    "עדכון ליד קיים דרך הצ׳אט חסום" not in reply11)

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
