#!/usr/bin/env python3
"""BUSINESSDRAFT PHASE 4 — Payment Term / Payment UPDATE.

Standalone assert-based script (repo convention:
`python3 test_business_draft_phase4_payment.py`), structured after
test_business_draft_deal_golden_path.py's Phase 3 precedent.

Scope: `crm_update_payment_term` and `crm_update_payment` only.
`crm_create_payment_term` and `crm_create_payment` are NOT wired to
BusinessDraft in Phase 4 -- see core/business_draft.py's `_CREATE_FIELD_MAP`
comment and app.py's `_run_commercial_draft` docstring for the two
independent, pre-existing blockers this file's routing section proves are
classified, not silently missing.
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
    "crm_update_payment_term is wired into the BusinessDraft seam",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_update_payment_term") == "payment_term",
)
chk(
    "crm_update_payment is wired into the BusinessDraft seam",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_update_payment") == "payment",
)
chk(
    "crm_create_payment_term is explicitly NOT wired (classified blocker: dead required "
    "direction/currency fields would always fail closed) -- absence is proven, not incidental",
    "crm_create_payment_term" not in app._COMMERCIAL_DRAFT_TOOLS
    and "crm_create_payment_term" not in _CREATE_FIELD_MAP,
)
chk(
    "crm_create_payment is explicitly NOT wired (classified blocker: entity_type 'payment' "
    "CREATE is already canonically bound to crm_create_charge_payment)",
    "crm_create_payment" not in app._COMMERCIAL_DRAFT_TOOLS
    and "payment" not in _CREATE_FIELD_MAP,
)

_schema_names = {s["name"] for s in TOOL_SCHEMAS}
for _tool in ("crm_create_payment_term", "crm_create_payment", "crm_update_payment_term", "crm_update_payment"):
    _meta = _REGISTRY.get(_tool)
    chk(f"{_tool} is registered in tool_registry", _meta is not None)
    chk(f"{_tool} is model_exposed (agent-reachable, same posture as crm_create_deal)", bool(_meta and _meta.model_exposed))
    chk(f"{_tool} is _MANAGEMENT-scoped (role posture unchanged by Phase 4)", bool(_meta and _meta.roles_allowed == {"owner", "partner", "manager"}))
    chk(f"{_tool} has a live TOOL_SCHEMAS entry (reachable by the agent's tool_use loop)", _tool in _schema_names)


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


# ══════════════════════════════════════════════════
print("\n[GENERIC airtable_update BYPASS] classified, pre-existing gap -- same as Deal, not newly introduced")
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
    "airtable_update-on-'Payment Terms' still reaches commercial_crm.update_payment_term() directly, "
    "bypassing the Phase 4 BusinessDraft hook entirely -- this is the SAME generic-redirect gap "
    "Phase 3 documented and accepted as Deal-only out-of-scope; it is confirmed (not silently left "
    "unclassified) to also apply to Payment Term/Payment, and closing it is reported as a Phase 4 "
    "blocker (it would require touching the shared _queue_approval_detailed_impl choke point that "
    "also fronts the runtime-verified Deal path)",
    mock_update_term.call_count == 1,
)


print(f"\n{'=' * 60}")
print(f"BusinessDraft Phase 4 (Payment Term / Payment UPDATE) tests: {passed} passed, {failed} failed")
import sys  # noqa: E402
sys.exit(0 if failed == 0 else 1)
