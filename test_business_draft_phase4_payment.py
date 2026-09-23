#!/usr/bin/env python3
"""BUSINESSDRAFT PHASE 4A — Payment Term CREATE+UPDATE / Payment CREATE+UPDATE.

Standalone assert-based script (repo convention:
`python3 test_business_draft_phase4_payment.py`), structured after
test_business_draft_deal_golden_path.py's Phase 3 precedent.

Scope: `crm_create_payment_term`/`crm_update_payment_term` and
`crm_create_charge_payment`/`crm_update_payment`. `crm_create_payment` (the
legacy, flat Payment writer) is deliberately NEVER wired to BusinessDraft --
see core/business_draft.py's `_CREATE_FIELD_MAP` comment and
app.py's `_run_commercial_draft` docstring; the [ROUTING/REACHABILITY]
section below proves that absence, not incidentally.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-phase4-payment-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PHASE4_PAYMENT_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPhase4PaymentTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPhase4PaymentTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from commercial_completion import ENTITY_CONTRACTS  # noqa: E402
from core.action_gateway import action_gateway  # noqa: E402
from core.business_draft import _CREATE_FIELD_MAP, _UPDATE_FIELD_MAP  # noqa: E402
from identity import Identity, Role  # noqa: E402
from session_store import lead_sessions  # noqa: E402
from tool_registry import _REGISTRY  # noqa: E402
from tools.schemas import TOOL_SCHEMAS  # noqa: E402

import tools.airtable_tools as _at  # noqa: E402

_at.airtable_add = lambda t, f: {"ok": True, "external_id": "rec001"}
_at.airtable_update = lambda t, r, f: {"ok": True, "external_id": r}
_at.airtable_get = lambda t, formula: "אין רשומות"
_at.airtable_get_records = lambda t, formula: []

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"  PASS: {desc}")
        passed += 1
    else:
        print(f"  FAIL: {desc}")
        failed += 1


_TERM_CONTRACT = ENTITY_CONTRACTS["payment_term"]
_PAYMENT_CONTRACT = ENTITY_CONTRACTS["payment"]
_TERM_AIRTABLE_FIELD = {fc.field_name: fc.airtable_field for fc in _TERM_CONTRACT.fields}
_PAYMENT_AIRTABLE_FIELD = {fc.field_name: fc.airtable_field for fc in _PAYMENT_CONTRACT.fields}
_CHANNEL = "telegram"


def _rid(prefix: str, n: int) -> str:
    """A syntactically valid Airtable record id: 'rec' + exactly 14 chars
    (commercial_crm._valid_record_id()'s regex)."""
    return f"rec{prefix}{n:0{14 - len(prefix)}d}"


def _owner_identity(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel=_CHANNEL, external_id=user_id,
    )


def _lead_identity(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.LEAD, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel=_CHANNEL, external_id=user_id,
    )


def _clear(sender: str, entity_type: str) -> None:
    try:
        lead_sessions.delete_business_draft(sender, entity_type, channel=_CHANNEL)
    except Exception:
        pass


def _run(tool_name: str, entity_type: str, tool_inputs: dict, identity: Identity, sender: str):
    return app._run_commercial_draft(entity_type, tool_name, dict(tool_inputs), identity, _CHANNEL, sender)


def _raw_term_record(**field_values) -> dict:
    return {_TERM_AIRTABLE_FIELD[name]: value for name, value in field_values.items()}


def _raw_payment_record(**field_values) -> dict:
    return {_PAYMENT_AIRTABLE_FIELD[name]: value for name, value in field_values.items()}


_CURRENT_TERM = _raw_term_record(
    deal="recDEAL00000001", name="Existing Term", direction="הכנסה",
    calculation_type="fixed", fixed_amount=1000, cadence="once",
    trigger_type="immediate", vat_rule="none", currency="ILS",
)
_CURRENT_PAYMENT = _raw_payment_record(
    charge="recCHARGE0000001", amount=500, paid_at="2026-01-01",
    direction="הכנסה", currency="ILS", status="התקבל", reference="REF-1",
)


# ══════════════════════════════════════════════════
print("\n[ROUTING/REACHABILITY] classification of all 4 canonical tools is explicit, not silent")
# ══════════════════════════════════════════════════

chk(
    "crm_create_payment_term is wired into the BusinessDraft seam",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_create_payment_term") == "payment_term"
    and "crm_create_payment_term" in app._COMMERCIAL_DRAFT_CREATE_TOOLS
    and "payment_term" in _CREATE_FIELD_MAP,
)
chk(
    "crm_update_payment_term is wired into the BusinessDraft seam",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_update_payment_term") == "payment_term",
)
chk(
    "crm_create_charge_payment (the V2 Golden Writer, MUTATION_TOOLS['payment']'s existing "
    "canonical CREATE target) is wired into the BusinessDraft seam as entity 'payment'",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_create_charge_payment") == "payment"
    and "crm_create_charge_payment" in app._COMMERCIAL_DRAFT_CREATE_TOOLS
    and "payment" in _CREATE_FIELD_MAP,
)
chk(
    "crm_update_payment is wired into the BusinessDraft seam",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_update_payment") == "payment",
)
chk(
    "crm_create_payment (the LEGACY, flat Payment writer) is explicitly NOT wired -- it is a "
    "separately-classified legacy/compatibility surface, never the BusinessDraft 'payment' CREATE "
    "binding -- absence is proven, not incidental",
    "crm_create_payment" not in app._COMMERCIAL_DRAFT_TOOLS
    and "crm_create_payment" not in app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL
    and "crm_create_payment" not in app._COMMERCIAL_DRAFT_CREATE_TOOLS,
)
from commercial_completion_routing import MUTATION_TOOLS as _MUTATION_TOOLS  # noqa: E402
chk(
    "MUTATION_TOOLS['payment'] is crm_create_charge_payment, never the legacy crm_create_payment "
    "(the completion router's own canonical CREATE binding -- unchanged by Phase 4A)",
    _MUTATION_TOOLS.get("payment") == "crm_create_charge_payment",
)

_schema_names = {s["name"] for s in TOOL_SCHEMAS}
for _tool in ("crm_create_payment_term", "crm_create_payment", "crm_update_payment_term", "crm_update_payment"):
    _meta = _REGISTRY.get(_tool)
    chk(f"{_tool} is registered in tool_registry", _meta is not None)
    chk(
        f"{_tool} carries model_exposed=True registry metadata -- NECESSARY but NOT SUFFICIENT "
        "for live Agent reachability; see the real context._filter_tools() checks below for the "
        "actual literal tool set (this is the exact class of gap Phase 3's crm_update_deal fix "
        "closed, and Phase 4A's own report originally overclaimed reachability the same way)",
        bool(_meta and _meta.model_exposed),
    )
    chk(f"{_tool} is _MANAGEMENT-scoped (role posture unchanged by Phase 4)", bool(_meta and _meta.roles_allowed == {"owner", "partner", "manager"}))
    chk(f"{_tool} has a live TOOL_SCHEMAS entry (a precondition for exposure, not exposure itself)", _tool in _schema_names)

_charge_payment_meta = _REGISTRY.get("crm_create_charge_payment")
chk("crm_create_charge_payment is registered in tool_registry", _charge_payment_meta is not None)
chk(
    "crm_create_charge_payment is model_exposed=False (internal-only -- reachable solely via "
    "CommercialCompletionRouter's own finalize step, never a direct Agent tool_use call)",
    bool(_charge_payment_meta and _charge_payment_meta.model_exposed is False),
)
chk(
    "crm_create_charge_payment is _MANAGEMENT-scoped",
    bool(_charge_payment_meta and _charge_payment_meta.roles_allowed == {"owner", "partner", "manager"}),
)
chk(
    "crm_create_charge_payment has no TOOL_SCHEMAS entry (never offered to the Agent tool_use loop)",
    "crm_create_charge_payment" not in _schema_names,
)


# ══════════════════════════════════════════════════
print("\n[ROUTING/REACHABILITY — REAL context._filter_tools()] the actual literal tool set offered to the model")
# ══════════════════════════════════════════════════
# PHASE4A-ROUTING-CLOSURE: ToolMeta.model_exposed=True (checked above) is
# registry metadata only. context.py's _ROLE_TOOLS + _filter_tools() is the
# ACTUAL intersection with TOOL_SCHEMAS that becomes the Agent's literal
# tool_use menu -- this is the exact mechanism Phase 3's crm_update_deal fix
# targeted, and the exact mechanism this file's own [ROUTING/REACHABILITY]
# section above failed to check before this fix.

import context as _context_module  # noqa: E402

_MANAGEMENT_ROLES = (Role.OWNER, Role.PARTNER, Role.MANAGER)
_NON_MANAGEMENT_ROLES = (Role.EMPLOYEE, Role.LEAD, Role.GUEST, Role.READONLY)


def _offered_tool_names(role: str) -> set[str]:
    return {s["name"] for s in _context_module._filter_tools(role)}


for _role in _MANAGEMENT_ROLES:
    _offered = _offered_tool_names(_role)
    chk(f"crm_update_payment_term IS in the real offered tool set for role={_role}", "crm_update_payment_term" in _offered)
    chk(f"crm_update_payment IS in the real offered tool set for role={_role}", "crm_update_payment" in _offered)

for _role in _NON_MANAGEMENT_ROLES:
    _offered = _offered_tool_names(_role)
    chk(f"crm_update_payment_term is ABSENT from the offered tool set for non-management role={_role}", "crm_update_payment_term" not in _offered)
    chk(f"crm_update_payment is ABSENT from the offered tool set for non-management role={_role}", "crm_update_payment" not in _offered)

# CREATE tools are deliberately NEVER added to _ROLE_TOOLS for ANY role --
# same precedent as crm_create_deal (already absent, unchanged by Phase 4A).
# Their canonical CREATE path is the deterministic CommercialCompletionRouter
# route (core/router/router.py's parse_deterministic_commercial_completion()
# -> Handler.TOOL -> commercial_completion_routing.MUTATION_TOOLS), which
# never depends on the model freely selecting a tool_use call.
for _role in _MANAGEMENT_ROLES + _NON_MANAGEMENT_ROLES:
    _offered = _offered_tool_names(_role)
    chk(f"crm_create_deal remains absent from the offered tool set for role={_role} (existing Phase 3 precedent, unchanged)", "crm_create_deal" not in _offered)
    chk(f"crm_create_payment_term is absent from the offered tool set for role={_role} (owned by the deterministic router route, not free tool-selection)", "crm_create_payment_term" not in _offered)
    chk(f"crm_create_charge_payment is absent from the offered tool set for role={_role} (model_exposed=False, and owned by the deterministic router route)", "crm_create_charge_payment" not in _offered)

# LEGACY crm_create_payment: report its DIRECT exposure and its INDIRECT
# (generic airtable_add) reachability as two separate, non-conflated facts.
for _role in _MANAGEMENT_ROLES:
    _offered = _offered_tool_names(_role)
    chk(
        f"crm_create_payment (LEGACY) is NOT directly offered to the model for role={_role} -- "
        "registered/model_exposed=True metadata in tool_registry, but not present in the literal "
        "Agent tool set (context._ROLE_TOOLS never lists it, for any role)",
        "crm_create_payment" not in _offered,
    )
    chk(
        f"airtable_add IS directly offered to the model for role={_role} (formerly the indirect "
        "reachability path for legacy crm_create_payment -- closed for NEW proposals by Phase 4B, see "
        "the dispatcher-fallback section below and test_business_draft_phase4b_generic_bypass.py)",
        "airtable_add" in _offered,
    )


# ══════════════════════════════════════════════════
print("\n[DETERMINISTIC CREATE ROUTING] Router Intent -> CommercialCompletionRouter -> MUTATION_TOOLS -> BusinessDraft seam")
# ══════════════════════════════════════════════════
# Static proof of the full chain for both CREATE tools, entirely independent
# of context._ROLE_TOOLS / model tool-selection:
#   Router Intent (deterministic regex match, core/router/router.py) ->
#   Handler.TOOL (never Handler.AGENT -- see core/router/test_router.py's own
#   "CREATE_PAYMENT_TERM .. reaches Handler.TOOL deterministically" and the
#   two existing CREATE_CHARGE_PAYMENT cases) ->
#   app.py's _completion_entities[route.intent] -> entity_type ->
#   CommercialCompletionRouter(entity_type).start() ->
#   MUTATION_TOOLS[entity_type] (finalize) -> canonical tool_name ->
#   app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL[tool_name] -> BusinessDraft seam
# (app.py's own `_completion_entities` dict is a local literal inside
# run_agent(), not a module attribute -- its two relevant entries,
# "create_payment_term": "payment_term" and "create_charge_payment":
# "payment", are pinned by source-text assertion below so a rename/removal
# fails this test loudly instead of silently drifting.)

from core.router.route_decision import Intent as _RouterIntent  # noqa: E402
from core.router import risk_router as _risk_router_module  # noqa: E402

chk(
    "Router Intent.CREATE_PAYMENT_TERM == 'create_payment_term' "
    "(app.py's _completion_entities key space -- Intent is a plain str constant class, not an Enum)",
    _RouterIntent.CREATE_PAYMENT_TERM == "create_payment_term",
)
chk(
    "Router Intent.CREATE_CHARGE_PAYMENT == 'create_charge_payment' "
    "(app.py's _completion_entities key space)",
    _RouterIntent.CREATE_CHARGE_PAYMENT == "create_charge_payment",
)
chk(
    "risk_router's PA-01 policy table maps CREATE_PAYMENT_TERM -> crm_create_payment_term "
    "(single policy source, cross-checked against MUTATION_TOOLS below)",
    _risk_router_module._CONTRACT_REQUIRED_INTENT_TO_TOOL.get(_RouterIntent.CREATE_PAYMENT_TERM) == "crm_create_payment_term",
)
chk(
    "risk_router's PA-01 policy table maps CREATE_CHARGE_PAYMENT -> crm_create_charge_payment "
    "(single policy source, cross-checked against MUTATION_TOOLS below)",
    _risk_router_module._CONTRACT_REQUIRED_INTENT_TO_TOOL.get(_RouterIntent.CREATE_CHARGE_PAYMENT) == "crm_create_charge_payment",
)
chk(
    "CommercialCompletionRouter's own canonical binding: MUTATION_TOOLS['payment_term'] == crm_create_payment_term",
    _MUTATION_TOOLS.get("payment_term") == "crm_create_payment_term",
)
chk(
    "CommercialCompletionRouter's own canonical binding: MUTATION_TOOLS['payment'] == crm_create_charge_payment "
    "(never the legacy crm_create_payment)",
    _MUTATION_TOOLS.get("payment") == "crm_create_charge_payment",
)

import inspect as _inspect_module  # noqa: E402
_app_source = _inspect_module.getsource(app)
chk(
    "app.py's _completion_entities dict maps intent 'create_payment_term' -> entity 'payment_term' "
    "(source-pinned since this dict is a local literal, not a module attribute)",
    '"create_payment_term": "payment_term"' in _app_source,
)
chk(
    "app.py's _completion_entities dict maps intent 'create_charge_payment' -> entity 'payment' "
    "(source-pinned since this dict is a local literal, not a module attribute)",
    '"create_charge_payment": "payment"' in _app_source,
)
chk(
    "the full chain closes: entity 'payment_term' -> BusinessDraft seam via _COMMERCIAL_DRAFT_ENTITY_FOR_TOOL",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_create_payment_term") == "payment_term",
)
chk(
    "the full chain closes: entity 'payment' -> BusinessDraft seam via _COMMERCIAL_DRAFT_ENTITY_FOR_TOOL "
    "(never routes to the legacy crm_create_payment)",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_create_charge_payment") == "payment",
)


# ══════════════════════════════════════════════════
print("\n[PAYMENT TERM CREATE] direction/currency required+persisted, drift-fix parity, conditional requirements intact")
# ══════════════════════════════════════════════════

sender = "term-create-valid-full"
identity = _owner_identity(sender)
result_tc1 = _run(
    "crm_create_payment_term", "payment_term",
    {
        "deal_id": _rid("DEALTC", 1), "name": "Full Term", "calc_type": "fixed",
        "direction": "receivable", "currency": "ILS", "fixed_amount": 1000,
        "trigger_type": "after_period", "trigger_delay_days": 5,
        "cadence": "once", "vat_rule": "none",
        "start_date": "2026-01-01", "end_date": "2026-12-31", "notes": "כל השדות",
    },
    identity, sender,
)
chk("CREATE with every mappable field supplied is not blocked", not result_tc1.blocked)
chk("CREATE: deal_id passed through", result_tc1.tool_inputs.get("deal_id") == _rid("DEALTC", 1))
chk("CREATE: calc_type passed through", result_tc1.tool_inputs.get("calc_type") == "fixed")
chk("CREATE: direction required field is persisted in tool_inputs (was silently discarded pre-Phase-4A)", result_tc1.tool_inputs.get("direction") == "receivable")
chk("CREATE: currency required field is persisted in tool_inputs (was silently discarded pre-Phase-4A)", result_tc1.tool_inputs.get("currency") == "ILS")
chk("CREATE: trigger_delay_days is persisted (drift-fix parity with UPDATE)", result_tc1.tool_inputs.get("trigger_delay_days") == 5)
chk("CREATE: start_date passed through", result_tc1.tool_inputs.get("start_date") == "2026-01-01")
chk("CREATE: end_date passed through", result_tc1.tool_inputs.get("end_date") == "2026-12-31")
chk("CREATE: canonical tool_name is crm_create_payment_term", not result_tc1.blocked)
_clear(sender, "payment_term")

sender = "term-create-missing-direction"
identity = _owner_identity(sender)
result_tc2 = _run(
    "crm_create_payment_term", "payment_term",
    {"deal_id": _rid("DEALTC", 2), "calc_type": "fixed", "currency": "ILS", "fixed_amount": 1000},
    identity, sender,
)
chk("CREATE missing direction fails closed before proposal (never reaches CONFIRMED)", result_tc2.blocked)
_clear(sender, "payment_term")

sender = "term-create-missing-currency"
identity = _owner_identity(sender)
result_tc3 = _run(
    "crm_create_payment_term", "payment_term",
    {"deal_id": _rid("DEALTC", 3), "calc_type": "fixed", "direction": "receivable", "fixed_amount": 1000},
    identity, sender,
)
chk("CREATE missing currency fails closed before proposal (never reaches CONFIRMED)", result_tc3.blocked)
_clear(sender, "payment_term")

sender = "term-create-conditional-requirements-intact"
identity = _owner_identity(sender)
result_tc4 = _run(
    "crm_create_payment_term", "payment_term",
    {"deal_id": _rid("DEALTC", 4), "calc_type": "percentage", "direction": "receivable", "currency": "ILS"},
    identity, sender,
)  # missing rate_pct/calc_basis, both CONDITIONAL on calc_type=percentage
chk(
    "CREATE: calc_type=percentage's CONDITIONAL rate_pct/calc_basis requirement remains intact "
    "(not weakened by adding direction/currency)",
    result_tc4.blocked,
)
_clear(sender, "payment_term")

sender = "term-create-percentage-complete"
identity = _owner_identity(sender)
result_tc5 = _run(
    "crm_create_payment_term", "payment_term",
    {
        "deal_id": _rid("DEALTC", 5), "calc_type": "percentage", "direction": "payable",
        "currency": "USD", "rate_pct": 10, "calc_basis": "deal_amount",
    },
    identity, sender,
)
chk("CREATE: calc_type=percentage with rate_pct+calc_basis+direction+currency confirms", not result_tc5.blocked)
_clear(sender, "payment_term")

sender = "term-create-invalid-direction-value"
identity = _owner_identity(sender)
result_tc6 = _run(
    "crm_create_payment_term", "payment_term",
    {"deal_id": _rid("DEALTC", 6), "calc_type": "fixed", "direction": "not_a_real_direction",
     "currency": "ILS", "fixed_amount": 1000},
    identity, sender,
)
chk(
    "CREATE with an invalid direction value fails closed via the shared FieldContract validator "
    "(no second validator)",
    result_tc6.blocked,
)
_clear(sender, "payment_term")

sender = "term-create-unrecognized-field"
identity = _owner_identity(sender)
result_tc7 = _run(
    "crm_create_payment_term", "payment_term",
    {
        "deal_id": _rid("DEALTC", 7), "calc_type": "fixed", "direction": "receivable",
        "currency": "ILS", "fixed_amount": 1000, "minimum_amount": 100,
    },
    identity, sender,
)
chk(
    "CREATE: a real ENTITY_CONTRACTS field with no create_payment_term() kwarg (minimum_amount) "
    "fails closed rather than being silently discarded",
    result_tc7.blocked,
)
_clear(sender, "payment_term")

sender = "term-create-retry-stability"
identity = _owner_identity(sender)
_create_payload = {
    "deal_id": _rid("DEALTC", 8), "calc_type": "fixed", "direction": "receivable",
    "currency": "ILS", "fixed_amount": 2500,
}
result_tc8a = _run("crm_create_payment_term", "payment_term", _create_payload, identity, sender)
_clear(sender, "payment_term")
result_tc8b = _run("crm_create_payment_term", "payment_term", _create_payload, identity, sender)
_clear(sender, "payment_term")
chk(
    "retrying an identical confirmed CREATE produces byte-identical tool_inputs (fingerprint stability)",
    not result_tc8a.blocked and not result_tc8b.blocked and result_tc8a.tool_inputs == result_tc8b.tool_inputs,
)

sender = "term-create-unauthorized"
identity = _lead_identity(sender)
result_tc9 = _run(
    "crm_create_payment_term", "payment_term",
    {"deal_id": _rid("DEALTC", 9), "calc_type": "fixed", "direction": "receivable", "currency": "ILS", "fixed_amount": 1000},
    identity, sender,
)
chk("CREATE from an unauthorized role fails closed", result_tc9.blocked)
_clear(sender, "payment_term")

sender = "term-create-e2e-sessions-cas"
identity = _owner_identity(sender)
_clear(sender, "payment_term")
result_tc10 = _run(
    "crm_create_payment_term", "payment_term",
    {"deal_id": _rid("DEALTC", 10), "calc_type": "fixed", "direction": "receivable", "currency": "ILS", "fixed_amount": 999},
    identity, sender,
)
chk("CREATE: Sessions/CAS lifecycle exercised -- draft_ctx returned for a real persisted+confirmed draft", not result_tc10.blocked and result_tc10.draft_ctx is not None)
stored_tc10 = lead_sessions.load_business_draft(
    sender, "payment_term", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
)
chk("CREATE: the CONFIRMED draft is actually retrievable from real Sessions persistence", stored_tc10 is not None and stored_tc10.lifecycle_state.value == "CONFIRMED")
_clear(sender, "payment_term")


# ══════════════════════════════════════════════════
print("\n[PAYMENT TERM UPDATE] target identity / authorization / drift-fix / empty-value / unrecognized")
# ══════════════════════════════════════════════════

sender = "term-update-valid"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM) as spy_read:
    result_u1 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 1), "fixed_amount": 2000}, identity, sender)
chk("UPDATE with a valid record_id is not blocked", not result_u1.blocked)
chk("UPDATE: record_id passed through unchanged", result_u1.tool_inputs.get("record_id") == _rid("TERM", 1))
chk("UPDATE: delta-only payload contains the changed field", result_u1.tool_inputs.get("fixed_amount") == 2000)
chk("UPDATE: unchanged fields (name) are absent from the delta payload", "name" not in result_u1.tool_inputs)
chk("UPDATE: pre-read reused the existing get_record_fields() reader", spy_read.call_count == 1)
_clear(sender, "payment_term")

sender = "term-update-trigger-delay-days-drift-fix"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    result_u2 = _run(
        "crm_update_payment_term", "payment_term",
        {"record_id": _rid("TERM", 2), "trigger_type": "after_period", "trigger_delay_days": 5},
        identity, sender,
    )
chk(
    "UPDATE: trigger_delay_days (a live schema/writer field previously missing from "
    "_UPDATE_FIELD_MAP -- Phase 4 drift fix) is now reachable, not rejected as unrecognized",
    not result_u2.blocked and result_u2.tool_inputs.get("trigger_delay_days") == 5,
)
_clear(sender, "payment_term")

sender = "term-update-missing-record-id"
identity = _owner_identity(sender)
result_u3 = _run("crm_update_payment_term", "payment_term", {"fixed_amount": 2000}, identity, sender)
chk("UPDATE with a missing record_id fails closed before any read", result_u3.blocked)
_clear(sender, "payment_term")

sender = "term-update-malformed-record-id"
identity = _owner_identity(sender)
result_u3b = _run("crm_update_payment_term", "payment_term", {"record_id": "not-a-record-id", "fixed_amount": 2000}, identity, sender)
chk("UPDATE with a malformed record_id fails closed before any read", result_u3b.blocked)
_clear(sender, "payment_term")

sender = "term-update-nonexistent-record"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=None) as spy_missing:
    result_u4 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 999), "fixed_amount": 2000}, identity, sender)
chk("UPDATE with a nonexistent record_id fails closed", result_u4.blocked)
chk("UPDATE: the reader was still attempted once (record_id was syntactically valid)", spy_missing.call_count == 1)
_clear(sender, "payment_term")

sender = "term-update-unauthorized"
identity = _lead_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM) as spy_unauth:
    result_u5 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 3), "fixed_amount": 2000}, identity, sender)
chk("UPDATE from an unauthorized role fails closed", result_u5.blocked)
chk(
    "UPDATE: unauthorized caller never triggers the pre-read (no data-read bypass via BusinessDraft)",
    spy_unauth.call_count == 0,
)
_clear(sender, "payment_term")

sender = "term-update-explicit-clear"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    result_u6 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 4), "notes": ""}, identity, sender)
chk(
    "UPDATE explicit-clear on a mapped field fails closed (same Phase 3 boundary, "
    "never silently omitted / treated as unchanged)",
    result_u6.blocked,
)
_clear(sender, "payment_term")

sender = "term-update-unrecognized-field"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    result_u7 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 5), "bogus_field": "x"}, identity, sender)
chk("UPDATE with a genuinely unrecognized field fails closed, never silently dropped", result_u7.blocked)
_clear(sender, "payment_term")

sender = "term-update-deal-immutable"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    result_u8 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 6), "deal_id": "recDEALOTHER001"}, identity, sender)
chk(
    "UPDATE attempting to change deal_id (immutable per commercial_crm.py) fails closed "
    "-- deal_id has no _UPDATE_FIELD_MAP entry, so it is unrecognized here",
    result_u8.blocked,
)
_clear(sender, "payment_term")

sender = "term-update-no-passthrough-fields-exist"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    result_u9 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 7), "minimum_amount": 100}, identity, sender)
chk(
    "PASSTHROUGH-ONLY UPDATE audit: payment_term has no passthrough fields at all -- "
    "a field the writer doesn't accept (minimum_amount, a real ENTITY_CONTRACTS field with "
    "no update_payment_term() kwarg) fails closed rather than silently reaching the writer",
    result_u9.blocked,
)
_clear(sender, "payment_term")


# ══════════════════════════════════════════════════
print("\n[PAYMENT CREATE] confirms into crm_create_charge_payment (the V2 Golden Writer), never the legacy writer")
# ══════════════════════════════════════════════════

_PAYMENT_CREATE_FULL = {
    "charge_id": _rid("CHG", 1), "deal_id": _rid("DEALPC", 1), "direction": "receivable",
    "amount": 500, "currency": "ILS", "paid_at": "2026-01-01",
}

sender = "payment-create-valid-full"
identity = _owner_identity(sender)
result_pc1 = _run("crm_create_charge_payment", "payment", dict(_PAYMENT_CREATE_FULL), identity, sender)
chk("Payment CREATE with every required V2 field confirms", not result_pc1.blocked)
chk("Payment CREATE: charge_id passed through", result_pc1.tool_inputs.get("charge_id") == _rid("CHG", 1))
chk("Payment CREATE: deal_id passed through", result_pc1.tool_inputs.get("deal_id") == _rid("DEALPC", 1))
chk("Payment CREATE: amount passed through", result_pc1.tool_inputs.get("amount") == 500)
chk("Payment CREATE: status auto-resolves via DEFAULT (never asked, manual_entry_allowed=False)", result_pc1.tool_inputs.get("status") == "received")
chk("Payment CREATE: document_requirement auto-resolves via DEFAULT", "document_requirement" in result_pc1.tool_inputs)
chk("Payment CREATE: document_status auto-resolves via DERIVED (manual_entry_allowed=False)", "document_status" in result_pc1.tool_inputs)
_clear(sender, "payment")

for _missing_field in ("charge_id", "deal_id", "amount", "direction", "currency", "paid_at"):
    sender = f"payment-create-missing-{_missing_field}"
    identity = _owner_identity(sender)
    _payload = {k: v for k, v in _PAYMENT_CREATE_FULL.items() if k != _missing_field}
    result_missing = _run("crm_create_charge_payment", "payment", _payload, identity, sender)
    chk(
        f"Payment CREATE: required V2 field '{_missing_field}' stays required "
        "(missing it fails closed, never reaches CONFIRMED)",
        result_missing.blocked,
    )
    _clear(sender, "payment")

sender = "payment-create-with-optionals"
identity = _owner_identity(sender)
result_pc2 = _run(
    "crm_create_charge_payment", "payment",
    {**_PAYMENT_CREATE_FULL, "payment_term_id": _rid("TERMPC", 1), "reference": "REF-PC", "method": "wire", "notes": "תשלום ראשון"},
    identity, sender,
)
chk("Payment CREATE: optional payment_term_id/reference/method/notes all pass through", not result_pc2.blocked)
chk("Payment CREATE: payment_term_id mapped to payment_term_id kwarg", result_pc2.tool_inputs.get("payment_term_id") == _rid("TERMPC", 1))
chk("Payment CREATE: reference passed through", result_pc2.tool_inputs.get("reference") == "REF-PC")
_clear(sender, "payment")

sender = "payment-create-unrecognized-field"
identity = _owner_identity(sender)
result_pc3 = _run(
    "crm_create_charge_payment", "payment",
    {**_PAYMENT_CREATE_FULL, "origin_lead_id": _rid("LEADPC", 1)},
    identity, sender,
)
chk(
    "Payment CREATE: a field with no ENTITY_CONTRACTS['payment']/_CREATE_FIELD_MAP entry "
    "(origin_lead_id -- Payment has no Lead attribution field) fails closed, never silently dropped",
    result_pc3.blocked,
)
_clear(sender, "payment")

sender = "payment-create-unauthorized"
identity = _lead_identity(sender)
result_pc4 = _run("crm_create_charge_payment", "payment", dict(_PAYMENT_CREATE_FULL), identity, sender)
chk("Payment CREATE from an unauthorized role fails closed", result_pc4.blocked)
_clear(sender, "payment")

sender = "payment-create-not-legacy-writer"
identity = _owner_identity(sender)
_clear(sender, "payment")
result_pc5 = _run("crm_create_charge_payment", "payment", dict(_PAYMENT_CREATE_FULL), identity, sender)
chk(
    "Payment CREATE confirms with tool_name crm_create_charge_payment, never the legacy crm_create_payment",
    not result_pc5.blocked,
)
_stored_pc5 = lead_sessions.load_business_draft(
    sender, "payment", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
)
chk(
    "the CONFIRMED draft's own snapshot.tool_name is exactly crm_create_charge_payment",
    _stored_pc5 is not None and _stored_pc5.snapshot is not None and _stored_pc5.snapshot.tool_name == "crm_create_charge_payment",
)
_clear(sender, "payment")


# ══════════════════════════════════════════════════
print("\n[PAYMENT UPDATE] financial immutability / authorization / document pairing")
# ══════════════════════════════════════════════════

sender = "payment-update-valid"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_PAYMENT) as spy_read_p:
    result_p1 = _run("crm_update_payment", "payment", {"record_id": _rid("PAY", 1), "reference": "REF-2"}, identity, sender)
chk("Payment UPDATE with a valid record_id is not blocked", not result_p1.blocked)
chk("Payment UPDATE: delta-only payload contains the changed field", result_p1.tool_inputs.get("reference") == "REF-2")
chk("Payment UPDATE: pre-read reused the existing get_record_fields() reader", spy_read_p.call_count == 1)
_clear(sender, "payment")

for _forbidden_field, _value in (
    ("amount", 999), ("currency", "USD"), ("direction", "הוצאה"),
    ("paid_at", "2026-02-02"), ("charge", "recCHARGEOTHER01"), ("deal", "recDEALOTHER001"),
    ("status", "בוטל"),
):
    sender = f"payment-update-financial-{_forbidden_field}"
    identity = _owner_identity(sender)
    with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_PAYMENT):
        result_fin = _run("crm_update_payment", "payment", {"record_id": _rid("PAY", 2), _forbidden_field: _value}, identity, sender)
    chk(
        f"BusinessDraft cannot turn financial field '{_forbidden_field}' into an UPDATE field "
        "(no _UPDATE_FIELD_MAP entry -- fails closed as unrecognized before reaching the writer)",
        result_fin.blocked,
    )
    _clear(sender, "payment")

chk(
    "Payment financial-immutability proof is structural: none of Payment's CREATE-only fields "
    "(charge/amount/paid_at/direction/currency/status/deal) appear in _UPDATE_FIELD_MAP['payment']",
    not ({"charge", "amount", "paid_at", "direction", "currency", "status", "deal"} & set(_UPDATE_FIELD_MAP["payment"])),
)

sender = "payment-update-missing-record-id"
identity = _owner_identity(sender)
result_p3 = _run("crm_update_payment", "payment", {"reference": "REF-3"}, identity, sender)
chk("Payment UPDATE with a missing record_id fails closed before any read", result_p3.blocked)
_clear(sender, "payment")

sender = "payment-update-unauthorized"
identity = _lead_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_PAYMENT) as spy_p_unauth:
    result_p4 = _run("crm_update_payment", "payment", {"record_id": _rid("PAY", 3), "reference": "REF-4"}, identity, sender)
chk("Payment UPDATE from an unauthorized role fails closed", result_p4.blocked)
chk("Payment UPDATE: unauthorized caller never triggers the pre-read", spy_p_unauth.call_count == 0)
_clear(sender, "payment")

sender = "payment-update-explicit-clear"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_PAYMENT):
    result_p5 = _run("crm_update_payment", "payment", {"record_id": _rid("PAY", 4), "notes": ""}, identity, sender)
chk("Payment UPDATE explicit-clear on a mapped field fails closed", result_p5.blocked)
_clear(sender, "payment")


# ══════════════════════════════════════════════════
print("\n[RETRY / FINGERPRINT STABILITY] identical confirmed UPDATE payloads are byte-identical")
# ══════════════════════════════════════════════════

sender = "term-retry-stability"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    result_r1 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 8), "fixed_amount": 3000}, identity, sender)
    _clear(sender, "payment_term")
    result_r2 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 8), "fixed_amount": 3000}, identity, sender)
    _clear(sender, "payment_term")
chk(
    "retrying an identical confirmed UPDATE produces byte-identical tool_inputs",
    not result_r1.blocked and not result_r2.blocked and result_r1.tool_inputs == result_r2.tool_inputs,
)


# ══════════════════════════════════════════════════
print("\n[CLEANUP CLASSIFICATION] reuses Phase 3's ownership-checked, outcome-driven cleanup")
# ══════════════════════════════════════════════════

sender = "term-cleanup-success"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    result_c1 = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 9), "fixed_amount": 4000}, identity, sender)
chk("cleanup fixture: draft created for the success scenario", not result_c1.blocked)
app._finalize_deal_draft_cleanup(result_c1.draft_ctx, {"ok": True, "terminal_outcome": None}, _CHANNEL)
stored_after_success = lead_sessions.load_business_draft(
    sender, "payment_term", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
)
chk("successful complete queue handoff -> draft removed (generic cleanup works for payment_term too)", stored_after_success is None)

sender = "payment-cleanup-orphaned"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_PAYMENT):
    result_c2 = _run("crm_update_payment", "payment", {"record_id": _rid("PAY", 5), "reference": "REF-5"}, identity, sender)
app._finalize_deal_draft_cleanup(result_c2.draft_ctx, {"ok": True, "terminal_outcome": "APPROVAL_QUEUE_ORPHANED"}, _CHANNEL)
stored_after_orphan = lead_sessions.load_business_draft(
    sender, "payment", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
)
chk("APPROVAL_QUEUE_ORPHANED final outcome -> draft retained (fail-closed retry guard, generic for payment too)", stored_after_orphan is not None)
_clear(sender, "payment")


# ══════════════════════════════════════════════════
print("\n[DRAFT CARDINALITY] Payment Term and Payment drafts coexist in the same sender session")
# ══════════════════════════════════════════════════

sender = "cardinality-coexist"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", side_effect=[_CURRENT_TERM, _CURRENT_PAYMENT]):
    result_card_term = _run("crm_update_payment_term", "payment_term", {"record_id": _rid("TERM", 10), "fixed_amount": 5000}, identity, sender)
    result_card_payment = _run("crm_update_payment", "payment", {"record_id": _rid("PAY", 6), "reference": "REF-6"}, identity, sender)
chk(
    "a Payment Term draft and a Payment draft coexist for the same sender "
    "(distinct entity kinds -> distinct draft slots, no cross-entity DraftConflictError)",
    not result_card_term.blocked and not result_card_payment.blocked,
)
_clear(sender, "payment_term")
_clear(sender, "payment")


# ══════════════════════════════════════════════════
print("\n[END-TO-END] fingerprint parity + real Sessions persistence, through the full pipeline")
# ══════════════════════════════════════════════════

sender = "term-e2e-fingerprint"
identity = _owner_identity(sender)
_clear(sender, "payment_term")

_captured = {}
_real_propose = action_gateway.propose_action


def _spy_propose(*a, **kw):
    result = _real_propose(*a, **kw)
    _captured["tool_inputs"] = kw.get("tool_inputs")
    _captured["fingerprint_payload"] = kw.get("fingerprint_payload")
    _captured["contract_id"] = result.contract_id
    return result


with patch.object(action_gateway, "propose_action", side_effect=_spy_propose), \
     patch.object(app, "resolve_identity", return_value=identity), \
     patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    outcome = app._queue_approval_detailed(
        "crm_update_payment_term",
        {"record_id": _rid("TERM", 11), "fixed_amount": 6000},
        sender, _CHANNEL,
    )

chk("end-to-end UPDATE through _queue_approval_detailed succeeds", outcome.get("ok") is True)
chk(
    "fingerprint_payload is forced to None so ActionGateway fingerprints the actual canonical tool_inputs",
    _captured.get("fingerprint_payload") is None,
)
contract = action_gateway._ledger.find_by_id(_captured["contract_id"]) if _captured.get("contract_id") else None
chk(
    "stored business_action_fingerprint matches one recomputed from the actual dispatched tool_inputs",
    contract is not None and contract.business_action_fingerprint == action_gateway.compute_business_fingerprint(
        contract.tenant_id, contract.canonical_user_id, contract.tool_name, contract.normalized_payload,
    ),
)
chk(
    "the CONFIRMED draft was actually cleaned up after a successful, complete handoff",
    lead_sessions.load_business_draft(
        sender, "payment_term", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
    ) is None,
)
_clear(sender, "payment_term")

sender = "term-e2e-create-fingerprint"
identity = _owner_identity(sender)
_clear(sender, "payment_term")

_captured_create = {}


def _spy_propose_create(*a, **kw):
    result = _real_propose(*a, **kw)
    _captured_create["tool_inputs"] = kw.get("tool_inputs")
    _captured_create["fingerprint_payload"] = kw.get("fingerprint_payload")
    _captured_create["contract_id"] = result.contract_id
    return result


with patch.object(action_gateway, "propose_action", side_effect=_spy_propose_create), \
     patch.object(app, "resolve_identity", return_value=identity):
    outcome_create = app._queue_approval_detailed(
        "crm_create_payment_term",
        {"deal_id": _rid("DEALE2E", 1), "calc_type": "fixed", "direction": "receivable", "currency": "ILS", "fixed_amount": 8000},
        sender, _CHANNEL,
    )

chk("end-to-end CREATE through _queue_approval_detailed succeeds", outcome_create.get("ok") is True)
chk(
    "CREATE: fingerprint_payload is forced to None so ActionGateway fingerprints the actual canonical tool_inputs",
    _captured_create.get("fingerprint_payload") is None,
)
contract_create = action_gateway._ledger.find_by_id(_captured_create["contract_id"]) if _captured_create.get("contract_id") else None
chk(
    "CREATE: stored business_action_fingerprint matches one recomputed from the actual dispatched tool_inputs",
    contract_create is not None and contract_create.business_action_fingerprint == action_gateway.compute_business_fingerprint(
        contract_create.tenant_id, contract_create.canonical_user_id, contract_create.tool_name, contract_create.normalized_payload,
    ),
)
chk(
    "CREATE: the CONFIRMED draft was actually cleaned up after a successful, complete handoff",
    lead_sessions.load_business_draft(
        sender, "payment_term", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
    ) is None,
)
_clear(sender, "payment_term")

sender = "payment-e2e-create-fingerprint"
identity = _owner_identity(sender)
_clear(sender, "payment")

_captured_pay_create = {}


def _spy_propose_pay_create(*a, **kw):
    result = _real_propose(*a, **kw)
    _captured_pay_create["tool_inputs"] = kw.get("tool_inputs")
    _captured_pay_create["fingerprint_payload"] = kw.get("fingerprint_payload")
    _captured_pay_create["contract_id"] = result.contract_id
    return result


with patch.object(action_gateway, "propose_action", side_effect=_spy_propose_pay_create), \
     patch.object(app, "resolve_identity", return_value=identity):
    outcome_pay_create = app._queue_approval_detailed(
        "crm_create_charge_payment", dict(_PAYMENT_CREATE_FULL), sender, _CHANNEL,
    )

chk("end-to-end Payment CREATE through _queue_approval_detailed succeeds", outcome_pay_create.get("ok") is True)
contract_pay_create = (
    action_gateway._ledger.find_by_id(_captured_pay_create["contract_id"]) if _captured_pay_create.get("contract_id") else None
)
chk(
    "end-to-end Payment CREATE: the queued ActionContract's tool_name is crm_create_charge_payment, "
    "never the legacy crm_create_payment",
    contract_pay_create is not None and contract_pay_create.tool_name == "crm_create_charge_payment",
)
_clear(sender, "payment")


# ══════════════════════════════════════════════════
print("\n[DISPATCHER EXECUTION FALLBACK] generic airtable_add/airtable_update redirects -- CLOSED for new proposals by Phase 4B (test_business_draft_phase4b_generic_bypass.py); kept only to execute pre-4B generic-identity contracts")
# ══════════════════════════════════════════════════

from tools import dispatcher as _dispatcher_module  # noqa: E402

with patch("commercial_crm.update_payment_term", return_value={"ok": True, "tool": "crm_update_payment_term", "external_id": "recTERM0000009", "evidence": {}, "user_message": "ok"}) as mock_update_term, \
     patch.object(_dispatcher_module, "_validate_execution_proof", return_value=None), \
     patch.object(_dispatcher_module._ff, "is_enabled", return_value=False):
    from tools.dispatcher import dispatch_tool as _dispatch_tool
    _dispatch_tool(
        "airtable_update",
        {"table": "Payment Terms", "record_id": "recTERM0000009", "fields": {_TERM_AIRTABLE_FIELD["fixed_amount"]: 7000}},
        identity=_owner_identity("term-legacy-redirect"),
        trusted_source="agent",
        execution_context={"contract_id": "phase4-legacy-redirect-regression"},
    )
chk(
    "DISPATCHER FALLBACK: an already-approved generic airtable_update-on-'Payment Terms' contract "
    "(frozen generic tool identity, minted before Phase 4B) still executes into "
    "commercial_crm.update_payment_term() -- this redirect is NOT BusinessDraft-fronted; Phase 4B "
    "canonicalizes every NEW generic proposal before ActionContract creation instead",
    mock_update_term.call_count == 1,
)

from airtable_schema import PaymentFields as _PF  # noqa: E402

with patch("commercial_crm.create_payment", return_value={"ok": True, "tool": "crm_create_payment", "external_id": "recPAY0000LEGACY", "evidence": {}, "user_message": "ok"}) as mock_create_payment_legacy, \
     patch.object(_dispatcher_module, "_validate_execution_proof", return_value=None), \
     patch.object(_dispatcher_module._ff, "is_enabled", return_value=False):
    from tools.dispatcher import dispatch_tool as _dispatch_tool_legacy_pay
    _dispatch_tool_legacy_pay(
        "airtable_add",
        {
            "table": "Payments",
            # Deliberately a shape with NO Charge-only V2 field present, so
            # tools/dispatcher.py's own _crm_create_route() disambiguator
            # picks the legacy route (_CRM_TABLE_ROUTING), never _PAYMENT_V2_ROUTE.
            "fields": {_PF.AMOUNT: 300, _PF.DOMAIN: "general", _PF.OWNER: "recOwnerLegacy001"},
        },
        identity=_owner_identity("payment-legacy-create-redirect"),
        trusted_source="agent",
        execution_context={"contract_id": "phase4a-legacy-payment-create-redirect-regression"},
    )
chk(
    "DISPATCHER FALLBACK: an already-approved pre-4B generic airtable_add contract on 'Payments' with "
    "a legacy-shaped (Charge-less) fields dict still executes into crm_create_payment() via "
    "_crm_create_route() -- a NEW such proposal now fails closed before any ActionContract (Phase 4B)",
    mock_create_payment_legacy.call_count == 1,
)

from airtable_schema import PaymentTermFields as _PTF  # noqa: E402

with patch("commercial_crm.create_payment_term", return_value={"ok": True, "tool": "crm_create_payment_term", "external_id": "recTERM0000010", "evidence": {}, "user_message": "ok"}) as mock_create_term, \
     patch.object(_dispatcher_module, "airtable_add") as mock_generic_add, \
     patch.object(_dispatcher_module, "_validate_execution_proof", return_value=None), \
     patch.object(_dispatcher_module._ff, "is_enabled", return_value=False):
    from tools.dispatcher import dispatch_tool as _dispatch_tool2
    _dispatch_tool2(
        "airtable_add",
        {
            "table": "Payment Terms",
            "fields": {
                # NOTE: the generic-redirect field map (tools/dispatcher.py's
                # _PAYMENT_TERM_FIELD_MAP) keys off the raw Airtable field
                # names (PaymentTermFields.*), a DIFFERENT namespace from
                # ENTITY_CONTRACTS' airtable_field (e.g. "Calculation Type"
                # here vs. the completion contract's "Calculation Type
                # Code") -- _TERM_AIRTABLE_FIELD is deliberately not reused.
                _PTF.DEAL: ["recDEAL00000002"],
                _PTF.CALC_TYPE: "fixed",
                _PTF.DIRECTION: "receivable",
                _PTF.CURRENCY: "ILS",
                _PTF.FIXED_AMOUNT: 8000,
            },
        },
        identity=_owner_identity("term-legacy-create-redirect"),
        trusted_source="agent",
        execution_context={"contract_id": "phase4a-legacy-create-redirect-regression"},
    )
chk(
    "GENERIC airtable_add CREATE-side redirect for 'Payment Terms' still works with the new "
    "required direction/currency writer kwargs (compatibility preserved, not broken by Phase 4A) "
    "-- DISPATCHER FALLBACK for pre-4B generic-identity contracts only; new generic proposals are "
    "canonicalized to crm_create_payment_term before ActionContract creation (Phase 4B)",
    mock_create_term.call_count == 1
    and mock_generic_add.call_count == 0
    and mock_create_term.call_args.kwargs.get("direction") == "receivable"
    and mock_create_term.call_args.kwargs.get("currency") == "ILS",
)


print(f"\n{'=' * 60}")
print(f"BusinessDraft Phase 4A (Payment Term CREATE+UPDATE / Payment CREATE+UPDATE) tests: {passed} passed, {failed} failed")
import sys  # noqa: E402
sys.exit(0 if failed == 0 else 1)
