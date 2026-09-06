# test_bug_organization_create_param_mismatch.py —
# BUG-ORGANIZATION-CREATE-PARAM-MISMATCH regression (production-reported,
# 06/09/2026)
#
# Production canary: "פתח עסקה בשם מרכז גולה בתחום finance" -> "עם מי
# העסקה?" -> "ארגון" -> "Goola" -> "לא מצאתי את Goola. ליצור ארגון חדש?" ->
# "כן" -> "❌ אושר אך נכשל בביצוע ... לא הצלחתי להכין תיאור ברור לבקשה הזו."
# Server log: action_validator: ActionBlocked (presence):
# crm_find_or_create_organization missing ['organization_name'].
#
# Root cause: commercial_completion_routing.py's _primitive_inputs() sent
# {"display_name": <name>} for the nested-Organization-create tool payload,
# but commercial_crm.find_or_create_organization()'s real parameter (and
# action_validator.py's/tools/dispatcher.py's own crm_find_or_create_organization
# allowlist, both keyed on "organization_name") is organization_name — every
# confirmed nested Organization create failed closed at the presence check,
# immediately after the owner answered "כן", with no recovery short of
# retyping the whole request.
#
# crm_find_or_create_organization is approval-gated (requires_approval=True
# in tool_registry.py), so Part 2 drives the REAL
# core.action_gateway.action_gateway.propose_action() ->
# app._handle_approval_callback_impl() -> tools.dispatcher.dispatch_tool()
# path end to end — the same governed path production actually used —
# rather than hand-crafting an execution_context or bypassing the
# approval-proof gate.

from __future__ import annotations

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-org-param-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:ORG_PARAM_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patOrgParamTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appOrgParamTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-org-param-webhook-secret")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import app  # noqa: E402

import tc8_test_repo_stub  # noqa: E402
tc8_test_repo_stub.patch_turn_state_repository()

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

from commercial_completion_routing import _primitive_inputs  # noqa: E402
from airtable_schema import OrganizationFields  # noqa: E402
from identity import Identity, Role  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _reset_airtable_circuit_breaker() -> None:
    from guards.circuit_breaker import _airtable_breaker
    with _airtable_breaker._lock:
        _airtable_breaker._failures = 0
        _airtable_breaker._opened = 0.0


# ══════════════════════════════════════════════════════════════════
# Part 1 — the router's own payload translation
# ══════════════════════════════════════════════════════════════════
print("── Part 1: _primitive_inputs() produces the correct key ──")

inputs = _primitive_inputs("organization", {OrganizationFields.NAME: "Goola"})
chk("organization_name is the key sent to the writer",
    inputs == {"organization_name": "Goola"})
chk("the old buggy 'display_name' key is never produced",
    "display_name" not in inputs)


# ══════════════════════════════════════════════════════════════════
# Part 2 — real governed path: ActionGateway -> approval callback ->
# tools.dispatcher.dispatch_tool() (the exact production route)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 2: real ActionGateway approval path — the production bug scenario ──")

_bot_calls: list[tuple] = []


def _stub_bot():
    return types.SimpleNamespace(
        send_message=lambda *a, **k: (_bot_calls.append(("send_message", a, k)) or types.SimpleNamespace(message_id=1)),
        delete_message=lambda *a, **k: None,
        answer_callback_query=lambda *a, **k: _bot_calls.append(("answer_callback_query", a, k)),
        edit_message_text=lambda *a, **k: _bot_calls.append(("edit_message_text", a, k)),
        process_new_updates=lambda updates: None,
    )


_orig_bot = app.bot
app.bot = _stub_bot()

import feature_flags  # noqa: E402
_PROD_FLAGS_ON = {"FEATURE_ACTION_GATEWAY", "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS"}
_orig_flag_enabled = app._flag_enabled
_orig_ff_is_enabled = feature_flags.is_enabled
app._flag_enabled = lambda name: name in _PROD_FLAGS_ON
feature_flags.is_enabled = lambda name: name in _PROD_FLAGS_ON

from core.action_gateway import action_gateway as _real_gw  # noqa: E402

_reset_airtable_circuit_breaker()
_identity = Identity(
    user_id="org-param-test", role=Role.OWNER, display_name="org-param-test",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="org-param-test",
)

with patch("commercial_crm.list_records") as mock_list, \
     patch("commercial_crm.airtable_create") as mock_create:
    from tools.airtable_gateway import AirtableCreateOutcome
    mock_list.return_value = []
    mock_create.return_value = AirtableCreateOutcome(
        status="created",
        record={"id": "recNewOrg00000011", "fields": {OrganizationFields.NAME: "Goola"}},
    )

    propose = _real_gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=_identity.memory_key,
        tool_name="crm_find_or_create_organization",
        tool_inputs={"organization_name": "Goola"},
        origin_channel="telegram", origin_chat_id="org-param-test",
        requires_approval=True, identity=_identity, trusted_source="test_harness",
    )
    chk("setup: nested Organization-create contract proposed", propose.ok)

    with patch.object(app, "resolve_identity", return_value=_identity):
        cq = types.SimpleNamespace(
            data=f"approve:{propose.contract_id}:{propose.contract_id}",
            id="cbq-org-param-test",
            from_user=types.SimpleNamespace(id="org-param-test", first_name="T"),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id="org-param-test"), message_id=1),
        )
        app._handle_approval_callback_impl(cq)

contract = _real_gw.find_contract(propose.contract_id)
chk("the real governed approval path actually executed the create "
    "(this is the exact scenario that failed in production with "
    "'missing organization_name')",
    contract is not None and contract.status in ("completed", "executed"))
chk("the writer was actually reached (airtable_create called)", mock_create.called)

# The old, buggy payload shape must still fail closed exactly like
# production did before the fix — proving the fix is real, not a
# validator relaxation.
from tools.dispatcher import dispatch_tool  # noqa: E402
result_bad = dispatch_tool(
    "crm_find_or_create_organization", {"display_name": "Goola"}, _identity,
)
chk("the OLD buggy payload shape ('display_name') is still correctly rejected "
    "(this is the presence-check behavior the fix routes AROUND, not weakens)",
    isinstance(result_bad, dict) and result_bad.get("ok") is False)


# ══════════════════════════════════════════════════════════════════
# Restore
# ══════════════════════════════════════════════════════════════════
app.bot = _orig_bot
app._flag_enabled = _orig_flag_enabled
feature_flags.is_enabled = _orig_ff_is_enabled

print(f"\n{'='*60}\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
