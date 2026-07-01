# test_approval_gate_registry.py — Regression: tool_registry approval gate consistency
#
# Root cause caught: TOOLS_REQUIRING_APPROVAL frozenset listed airtable_add /
# airtable_update / gmail_draft / calendar_create_event — but their ToolMeta
# entries had requires_approval=False (default), so the gate at app.py:1426
# (if meta.requires_approval:) never fired and these tools executed immediately.
#
# Tests:
#   1. All tools in TOOLS_REQUIRING_APPROVAL have requires_approval=True in ToolMeta
#   2. airtable_add / airtable_update are also high_risk
#   3. ToolMeta.requires_approval agrees with needs_approval() helper
#   4. WhatsApp create_task scenario: airtable_add must NOT bypass approval gate

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from tool_registry import TOOLS_REQUIRING_APPROVAL, _REGISTRY, enforce, ToolMeta

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# Test 1: TOOLS_REQUIRING_APPROVAL ↔ ToolMeta consistency
# Every tool in the frozenset MUST have requires_approval=True in _REGISTRY.
# ══════════════════════════════════════════════════
print("\n── Test 1: frozenset ↔ ToolMeta consistency ────────────────")
for tool_name in sorted(TOOLS_REQUIRING_APPROVAL):
    meta = _REGISTRY.get(tool_name)
    if meta is None:
        chk(f"{tool_name}: registered in _REGISTRY", False)
        continue
    chk(
        f"{tool_name}: ToolMeta.requires_approval=True (not just in frozenset)",
        meta.requires_approval is True,
    )


# ══════════════════════════════════════════════════
# Test 2: airtable_add + airtable_update are high_risk
# (they write user data — must be marked accordingly)
# ══════════════════════════════════════════════════
print("\n── Test 2: mutating Airtable tools are high_risk ───────────")
for tool_name in ("airtable_add", "airtable_update"):
    meta = _REGISTRY.get(tool_name)
    chk(f"{tool_name}: high_risk=True", meta is not None and meta.high_risk is True)


# ══════════════════════════════════════════════════
# Test 3: needs_approval() helper agrees with ToolMeta
# ══════════════════════════════════════════════════
print("\n── Test 3: needs_approval() helper consistency ──────────────")
from tool_registry import needs_approval

for tool_name in sorted(TOOLS_REQUIRING_APPROVAL):
    chk(
        f"needs_approval({tool_name!r}) == True",
        needs_approval(tool_name) is True,
    )

# spot-check: read-only tools must NOT need approval
for read_only_tool in ("airtable_get", "calendar_get_events", "gmail_read"):
    meta = _REGISTRY.get(read_only_tool)
    if meta:
        chk(
            f"needs_approval({read_only_tool!r}) == False",
            needs_approval(read_only_tool) is False,
        )


# ══════════════════════════════════════════════════
# Test 4: WhatsApp create_task scenario
# airtable_add with Tasks table must be intercepted by approval gate,
# not executed immediately (simulated via ToolMeta flag check).
# ══════════════════════════════════════════════════
print("\n── Test 4: WhatsApp create_task approval gate ───────────────")

# Simulate what app.py:1426 does:
#   meta = enforce(tu.name, identity)
#   if meta.requires_approval:  ← this is the gate
#       result = _queue_approval(...)
#       continue   ← tool does NOT execute

from types import SimpleNamespace

_owner_identity = SimpleNamespace(
    role="owner",
    user_id="owner_1",
    tenant_id="boss_hq",
    memory_key="boss_hq:owner_1",
)

try:
    meta = enforce("airtable_add", _owner_identity)
    chk("Test4: enforce('airtable_add', owner) does not raise ToolDenied", True)
    chk("Test4: meta.requires_approval=True → approval gate fires", meta.requires_approval is True)
    # If requires_approval is True, the tool would be routed to _queue_approval(), NOT dispatched.
    # We verify that by checking the flag — no actual dispatch call is needed.
    if meta.requires_approval:
        chk("Test4: airtable_add queued, NOT dispatched immediately (gate active)", True)
    else:
        chk("Test4: airtable_add queued, NOT dispatched immediately (gate active)", False)
except Exception as e:
    chk(f"Test4: enforce() error: {e}", False)

# Simulate the "מאשר" path: after approval, contract_id must resolve back to airtable_add
from core.action_gateway import ActionGateway, ExecutionLedger

_dispatched = []

def _tracking_executor(tool_name, tool_inputs, contract_id):
    _dispatched.append({"tool": tool_name, "inputs": tool_inputs})
    # C53-A structured result with a valid Airtable record ID
    return {
        "ok": True, "tool": tool_name,
        "external_id": "recXOW7FBZQZcNdw1",
        "evidence": {"record_id": "recXOW7FBZQZcNdw1"},
        "user_message": "✅ רשומה נוספה | ID: recXOW7FBZQZcNdw1",
    }

gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_tracking_executor)

# Step 1: propose (WhatsApp turn — the 11:05 message)
r = gw.propose_action(
    tenant_id="boss_hq",
    canonical_user_id="boss_hq:owner_1",
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "לרכוש מכונת הדפסה", "Due": "היום"}},
    origin_channel="whatsapp",
    origin_chat_id="whatsapp:972501234567",
    requires_approval=True,
)
chk("Test4: propose_action creates pending contract (not executed yet)", r.ok and r.contract_id is not None)
chk("Test4: no dispatch before approval", len(_dispatched) == 0)

# Second propose same payload (simulates agent retry or WhatsApp re-send)
r2 = gw.propose_action(
    tenant_id="boss_hq",
    canonical_user_id="boss_hq:owner_1",
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "לרכוש מכונת הדפסה", "Due": "היום"}},
    origin_channel="whatsapp",
    origin_chat_id="whatsapp:972501234567",
    requires_approval=True,
)
chk("Test4: second propose blocked (pending exists)", not r2.ok)
chk("Test4: still no dispatch before approval", len(_dispatched) == 0)

# Step 2: "מאשר" (the 11:07 message) → approval route
reply = gw.route_confirmation_word("boss_hq:owner_1")
chk("Test4: route_confirmation_word dispatches exactly once", len(_dispatched) == 1)
chk("Test4: dispatched tool is airtable_add", _dispatched[0]["tool"] == "airtable_add")
chk("Test4: dispatched inputs include Tasks table", _dispatched[0]["inputs"].get("table") == "Tasks")

# Step 3: triple "מאשר" — must not execute again
gw.route_confirmation_word("boss_hq:owner_1")
gw.route_confirmation_word("boss_hq:owner_1")
chk("Test4: triple מאשר — still exactly one dispatch total", len(_dispatched) == 1)

# Step 4: contract is now executed (DoD §15 — consumed flag equivalent)
contract = gw.find_contract(r.contract_id)
chk("Test4: contract status=executed after approval", contract.status == "executed")


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Approval gate registry tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
