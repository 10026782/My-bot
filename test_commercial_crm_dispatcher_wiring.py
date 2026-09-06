#!/usr/bin/env python3
"""
test_commercial_crm_dispatcher_wiring.py — regression coverage for wiring
commercial_crm.py's canonical Deal/PaymentTerm/Payment writers into
tool_registry.py + tools/dispatcher.py + tools/schemas.py (ROADMAP.md's
SCHEMA_DATA_CONTRACTS "still open" next step, closed here).

commercial_crm.py's own writer-contract logic is already covered by
test_commercial_crm.py (97 tests) — this file only covers the NEW surface:
registry policy, dispatcher case routing (inputs -> exact kwargs), tenant
scope enforcement, and schema/registry parity for the three new tool names.

No live Airtable access — commercial_crm.create_deal/create_payment_term/
create_payment are mocked. Runs as a plain script (python3 $file), matching
this repo's test_*.py convention (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-ccrmwiring-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:CCRM_WIRING_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patCcrmWiringTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCcrmWiringTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import tools.dispatcher as dispatcher_module  # noqa: E402
from tools.dispatcher import dispatch_tool  # noqa: E402
from tools.schemas import TOOL_SCHEMAS  # noqa: E402
import tool_registry  # noqa: E402
from identity import Identity, Role  # noqa: E402

# No live Airtable in this sandbox — same fail-closed-avoidance as every
# other dispatch_tool()-level test in this repo.
_no_emergency_stop = patch.object(dispatcher_module._ff, "is_enabled", return_value=False)
_no_emergency_stop.start()

# All three tools are requires_approval=True, so a direct dispatch_tool()
# call always hits _validate_execution_proof() first and is denied with a
# generic "requires an approved ActionContract" error — in production this
# gate is always satisfied by ActionGateway's _make_dispatch_executor()
# before the case block below ever runs. That gate itself is shared,
# tool-agnostic infra (identical for every requires_approval=True tool) —
# what THIS file tests is the NEW case-block logic (routing, tenant scope)
# specific to the three commercial_crm tools, so the shared upstream gate is
# bypassed here to reach it, the same boundary an already-approved
# ActionGateway execution would cross in production.
_no_execution_proof_gate = patch.object(dispatcher_module, "_validate_execution_proof", return_value=None)
_no_execution_proof_gate.start()

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
    user_id="owner-ccrmwiring", role=Role.OWNER, display_name="owner-ccrmwiring",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="owner-ccrmwiring",
)
external_no_tenant = Identity(
    user_id="ext-ccrmwiring", role=Role.LEAD, display_name="",
    tenant_id="unknown", domain_id="general", channel="whatsapp", external_id="ext-ccrmwiring",
)

_TOOL_NAMES = ("crm_create_deal", "crm_create_payment_term", "crm_create_payment")

# ══════════════════════════════════════════════════════════════════
# Property 1 — registry policy
# ══════════════════════════════════════════════════════════════════
print("\n── Property 1: tool_registry policy ───────────────────────────────")
for name in _TOOL_NAMES:
    meta = tool_registry.get(name)
    chk(f"{name}: registered", meta is not None)
    if meta is None:
        continue
    chk(f"{name}: owner/partner/manager allowed", meta.roles_allowed == {"owner", "partner", "manager"})
    chk(f"{name}: employee NOT allowed", "employee" not in meta.roles_allowed)
    chk(f"{name}: requires_approval=True", meta.requires_approval is True)
    chk(f"{name}: tenant_scoped=True", meta.tenant_scoped is True)
    chk(f"{name}: blocked_by_emergency=True", meta.blocked_by_emergency is True)

# ══════════════════════════════════════════════════════════════════
# Property 2 — schema/registry parity (mirrors SECURITY_CHECKLIST.md's
# dispatcher-case-vs-registry grep, but for schemas.py specifically)
# ══════════════════════════════════════════════════════════════════
print("\n── Property 2: schema coverage ─────────────────────────────────────")
schema_names = {s["name"] for s in TOOL_SCHEMAS}
for name in _TOOL_NAMES:
    chk(f"{name}: present in TOOL_SCHEMAS", name in schema_names)

# ══════════════════════════════════════════════════════════════════
# Property 3 — dispatcher routes inputs to the exact writer kwargs
# ══════════════════════════════════════════════════════════════════
print("\n── Property 3: dispatcher case routing ─────────────────────────────")

with patch("commercial_crm.create_deal", return_value={"ok": True, "tool": "crm_create_deal",
                                                         "external_id": "recDeal1", "evidence": {}, "user_message": "ok"}) as m:
    result = dispatch_tool(
        "crm_create_deal",
        {
            "name": "עסקה חדשה", "domain": "real_estate", "owner_id": "recOwner1",
            "estimated_value_basis": "one_off", "estimated_value_range": "100k_300k",
            "estimated_value_notes": "תלוי בהיקף",
        },
        identity=owner, trusted_source="agent",
    )
    chk("crm_create_deal: dispatch returns the writer's dict verbatim", result.get("external_id") == "recDeal1")
    chk("crm_create_deal: name passed through", m.call_args.kwargs["name"] == "עסקה חדשה")
    chk("crm_create_deal: domain passed through", m.call_args.kwargs["domain"] == "real_estate")
    chk("crm_create_deal: owner_id passed through", m.call_args.kwargs["owner_id"] == "recOwner1")
    chk("crm_create_deal: estimated_value_basis passed through", m.call_args.kwargs["estimated_value_basis"] == "one_off")
    chk("crm_create_deal: estimated_value_range passed through", m.call_args.kwargs["estimated_value_range"] == "100k_300k")
    chk("crm_create_deal: estimated_value_notes passed through", m.call_args.kwargs["estimated_value_notes"] == "תלוי בהיקף")
    chk("crm_create_deal: 'amount' no longer forwarded (BUG-DIAMOND-EXPECTED-VALUE-RANGE)", "amount" not in m.call_args.kwargs)
    chk("crm_create_deal: source is always 'agent' from this path", m.call_args.kwargs["source"] == "agent")

with patch("commercial_crm.create_payment_term", return_value={"ok": True, "tool": "crm_create_payment_term",
                                                                 "external_id": "recTerm1", "evidence": {}, "user_message": "ok"}) as m:
    dispatch_tool(
        "crm_create_payment_term",
        {"deal_id": "recDeal1", "calc_type": "percentage", "rate_pct": 5, "calc_basis": "deal_amount"},
        identity=owner, trusted_source="agent",
    )
    chk("crm_create_payment_term: deal_id passed through", m.call_args.kwargs["deal_id"] == "recDeal1")
    chk("crm_create_payment_term: calc_type passed through", m.call_args.kwargs["calc_type"] == "percentage")
    chk("crm_create_payment_term: rate_pct passed through", m.call_args.kwargs["rate_pct"] == 5)
    chk("crm_create_payment_term: calc_basis passed through", m.call_args.kwargs["calc_basis"] == "deal_amount")

with patch("commercial_crm.create_payment", return_value={"ok": True, "tool": "crm_create_payment",
                                                            "external_id": "recPay1", "evidence": {}, "user_message": "ok"}) as m:
    dispatch_tool(
        "crm_create_payment",
        {"amount": 1200, "domain": "general", "owner_id": "recOwner1", "deal_id": "recDeal1"},
        identity=owner, trusted_source="agent",
    )
    chk("crm_create_payment: amount passed through", m.call_args.kwargs["amount"] == 1200)
    chk("crm_create_payment: owner_id passed through", m.call_args.kwargs["owner_id"] == "recOwner1")
    chk("crm_create_payment: deal_id passed through", m.call_args.kwargs["deal_id"] == "recDeal1")

# ══════════════════════════════════════════════════════════════════
# Property 4 — an external/disallowed-role identity is rejected by
# tool_registry.enforce() (the capability gate) before the case block
# — and therefore before enforce_tenant_scope() or the writer — ever run.
# roles_allowed=_MANAGEMENT is all-internal, so these three tools can never
# actually reach enforce_tenant_scope()'s external/no-tenant branch (same
# as the existing crm_mark_payment_paid precedent, _SENIOR-only) — the
# real, reachable safety boundary here is the role check, tested below.
# ══════════════════════════════════════════════════════════════════
print("\n── Property 4: capability gate rejects a disallowed-role identity ──")

for name, inputs in (
    ("crm_create_deal", {"name": "x", "domain": "general", "owner_id": "recOwner1"}),
    ("crm_create_payment_term", {"deal_id": "recDeal1", "calc_type": "fixed", "fixed_amount": 100}),
    ("crm_create_payment", {"amount": 100, "domain": "general", "owner_id": "recOwner1"}),
):
    writer_name = {
        "crm_create_deal": "commercial_crm.create_deal",
        "crm_create_payment_term": "commercial_crm.create_payment_term",
        "crm_create_payment": "commercial_crm.create_payment",
    }[name]
    with patch(writer_name) as m:
        result = dispatch_tool(name, inputs, identity=external_no_tenant, trusted_source="agent")
        chk(f"{name}: rejected for a LEAD-role identity (not in roles_allowed)",
            isinstance(result, str) and "גישה נחסמה" in result)
        chk(f"{name}: writer never called once the capability gate blocks", not m.called)

print(f"\n{'='*40}")
print(f"commercial_crm dispatcher wiring: {passed} passed, {failed} failed")

if __name__ == "__main__":
    exit(0 if failed == 0 else 1)
