#!/usr/bin/env python3
"""BUSINESSDRAFT PHASE 4B — shared commercial generic-bypass closure.

Standalone assert-based script (repo convention:
`python3 test_business_draft_phase4b_generic_bypass.py`), structured after
test_business_draft_phase4_payment.py (Phase 4A) and
test_business_draft_deal_golden_path.py (Phase 3).

Proves that a NEW generic `airtable_add`/`airtable_update` proposal on a
BusinessDraft-covered commercial table (Deals / Payment Terms / Payments) is
canonicalized BEFORE BusinessDraft / fingerprinting / ActionContract into the
dedicated crm_* tool + primitive payload — through the single mapping
authority core/commercial_generic_canonicalization.py, invoked from
core.action_gateway.resolve_canonical_call() — and that:

  - the existing Phase 3 / Phase 4A seams run unchanged (Sessions CAS,
    ConfirmedSnapshot), with the canonical tool's own role policy;
  - no airtable_add/airtable_update ActionContract is minted for them;
  - generic and dedicated forms of the same business action produce the same
    canonical tool, tool_inputs, normalized payload and fingerprints;
  - a generic Payments CREATE shaped for the legacy flat writer fails closed
    before any ActionContract;
  - the dispatcher's generic redirect still executes a contract minted under
    a generic identity BEFORE Phase 4B (backward-compatible fallback only);
  - non-commercial generic behavior is unchanged.
"""

from __future__ import annotations

import copy
import json
import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-phase4b-generic-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PHASE4B_GENERIC_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPhase4bGenericTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPhase4bGenericTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
import core.action_gateway as _gateway_module  # noqa: E402
import core.commercial_generic_canonicalization as canon  # noqa: E402
import tool_registry  # noqa: E402
from airtable_schema import (  # noqa: E402
    DealFields, DealStage, PaymentFields, PaymentTermFields, PaymentTermTrigger,
    Tables, TaskFields,
)
from commercial_completion import ENTITY_CONTRACTS  # noqa: E402
from core.action_gateway import (  # noqa: E402
    CanonicalizationError, CommercialCanonicalizationError, action_gateway,
    resolve_canonical_call, resolve_canonical_tool,
)
from event_bus import executed_action_cache  # noqa: E402
from identity import Identity, Role  # noqa: E402
from session_store import lead_sessions  # noqa: E402
from tools import dispatcher as _dispatcher_module  # noqa: E402

# Sessions persistence goes through tools.airtable_tools — mocked exactly like
# the Phase 3/4A suites so real CAS/version logic runs without a live base.
import tools.airtable_tools as _at  # noqa: E402

_generic_writes: list = []


def _fake_airtable_add(table, fields):
    _generic_writes.append(("add", table))
    return {"ok": True, "external_id": "rec001"}


_at.airtable_add = _fake_airtable_add
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


_CHANNEL = "telegram"
_RESOLVED_OWNER = "recPROFILE0000001"
_TENANT = "boss_hq"
_FIXED_USER = "boss_hq:phase4b-fingerprint-basis"
_FIXED_CHAT = "phase4b-fingerprint-chat"

_resolve_owner = patch.object(
    _dispatcher_module._owner_resolution, "resolve_profile_record_id", return_value=_RESOLVED_OWNER,
)
_resolve_owner.start()


def _rid(prefix: str, n: int) -> str:
    """'rec' + exactly 14 chars — commercial_crm._valid_record_id()'s regex."""
    return f"rec{prefix}{n:0{14 - len(prefix)}d}"


def _identity(user_id: str, role: str = Role.OWNER) -> Identity:
    return Identity(
        user_id=user_id, role=role, display_name=user_id,
        tenant_id=_TENANT, domain_id="general", channel=_CHANNEL, external_id=user_id,
    )


def _airtable_record(entity: str, **field_values) -> dict:
    by_name = {fc.field_name: fc.airtable_field for fc in ENTITY_CONTRACTS[entity].fields}
    return {by_name[name]: value for name, value in field_values.items()}


_CURRENT_DEAL = _airtable_record(
    "deal", name="Existing Deal", domain="Import", owner="recOWNEREXIST01", stage=DealStage.OPPORTUNITY,
)
_CURRENT_TERM = _airtable_record(
    "payment_term", deal="recDEAL00000001", name="Existing Term", direction="receivable",
    calculation_type="fixed", fixed_amount=1000, cadence="once",
    trigger_type="immediate", vat_rule="none", currency="ILS",
)
_CURRENT_PAYMENT = _airtable_record(
    "payment", charge="recCHARGE0000001", amount=500, paid_at="2026-01-01",
    direction="receivable", currency="ILS", reference="REF-1",
)


def _clear(sender: str) -> None:
    for entity in ("deal", "payment_term", "payment"):
        try:
            lead_sessions.delete_business_draft(sender, entity, channel=_CHANNEL)
        except Exception:
            pass


def _queue(tool_name: str, tool_inputs: dict, sender: str, *, role: str = Role.OWNER, record: dict | None = None) -> dict:
    """Run one proposal through the REAL app._queue_approval_detailed() choke
    point, spying (never replacing) ActionGateway.propose_action(), the
    Sessions CREATE/CAS writes, and tool_registry.enforce()."""
    identity = _identity(sender, role)
    _clear(sender)
    obs = {"propose": [], "creates": [], "saves": [], "enforced": [], "writes_before": len(_generic_writes)}
    real_propose = action_gateway.propose_action
    real_create = lead_sessions.create_business_draft
    real_save = lead_sessions.save_business_draft
    real_enforce = tool_registry.enforce

    def spy_propose(*a, **kw):
        result = real_propose(*a, **kw)
        obs["propose"].append({
            "tool_name": kw.get("tool_name"), "tool_inputs": copy.deepcopy(kw.get("tool_inputs")),
            "fingerprint_payload": kw.get("fingerprint_payload"),
            "ok": result.ok, "contract_id": result.contract_id,
        })
        return result

    def spy_create(sender_, draft, **kw):
        obs["creates"].append({"state": draft.lifecycle_state, "entity": draft.entity_type})
        return real_create(sender_, draft, **kw)

    def spy_save(sender_, draft, **kw):
        stored = real_save(sender_, draft, **kw)
        obs["saves"].append({"state": draft.lifecycle_state, "expected_version": kw.get("expected_version"),
                             "stored_version": stored.idempotency_key})
        return stored

    def spy_enforce(tool, identity_, *a, **kw):
        obs["enforced"].append(tool)
        return real_enforce(tool, identity_, *a, **kw)

    patches = [
        patch.object(action_gateway, "propose_action", side_effect=spy_propose),
        patch.object(lead_sessions, "create_business_draft", side_effect=spy_create),
        patch.object(lead_sessions, "save_business_draft", side_effect=spy_save),
        patch.object(tool_registry, "enforce", side_effect=spy_enforce),
        patch.object(app, "resolve_identity", return_value=identity),
    ]
    if record is not None:
        patches.append(patch("tools.airtable_read_adapter.get_record_fields", return_value=record))
    for p in patches:
        p.start()
    try:
        outcome = app._queue_approval_detailed(tool_name, dict(tool_inputs), sender, _CHANNEL)
    finally:
        for p in reversed(patches):
            p.stop()
    obs["outcome"] = outcome
    obs["contract"] = (
        action_gateway._ledger.find_by_id(obs["propose"][-1]["contract_id"])
        if obs["propose"] and obs["propose"][-1]["contract_id"] else None
    )
    obs["generic_writes"] = _generic_writes[obs["writes_before"]:]
    return obs


def _fingerprints(tool_name: str, tool_inputs: dict) -> tuple[str, str]:
    """Both fingerprint bases, computed for ONE fixed user so generic-vs-
    dedicated results are comparable byte-for-byte."""
    normalized = action_gateway.normalize_payload(tool_inputs)
    return (
        action_gateway.compute_business_fingerprint(_TENANT, _FIXED_USER, tool_name, normalized),
        executed_action_cache.compute(_FIXED_CHAT, tool_name, tool_inputs),
    )


def _proposed(obs: dict) -> tuple[str | None, dict | None]:
    if not obs["propose"]:
        return None, None
    return obs["propose"][-1]["tool_name"], obs["propose"][-1]["tool_inputs"]


def _parity(label: str, generic: dict, dedicated: dict, expected_tool: str) -> None:
    g_tool, g_inputs = _proposed(generic)
    d_tool, d_inputs = _proposed(dedicated)
    chk(f"{label}: generic proposal queued successfully", generic["outcome"].get("ok") is True)
    chk(f"{label}: dedicated proposal queued successfully", dedicated["outcome"].get("ok") is True)
    chk(f"{label}: ActionGateway saw the dedicated tool {expected_tool}, never a generic tool",
        g_tool == expected_tool and all(p["tool_name"] == expected_tool for p in generic["propose"]))
    chk(f"{label}: no airtable_add/airtable_update ActionContract was minted",
        generic["contract"] is not None and generic["contract"].tool_name == expected_tool)
    chk(f"{label}: canonical tool_inputs are byte-identical to the dedicated form",
        json.dumps(g_inputs, sort_keys=True, ensure_ascii=False) == json.dumps(d_inputs, sort_keys=True, ensure_ascii=False))
    chk(f"{label}: stored normalized_payload is identical to the dedicated form",
        generic["contract"] is not None and dedicated["contract"] is not None
        and generic["contract"].normalized_payload == dedicated["contract"].normalized_payload)
    chk(f"{label}: business + dedup fingerprints match the dedicated form byte-for-byte",
        _fingerprints(g_tool, g_inputs) == _fingerprints(d_tool, d_inputs))
    chk(f"{label}: stored business_action_fingerprint recomputes from the dispatched canonical tool_inputs "
        "(no fingerprint_payload workaround)",
        generic["propose"][-1]["fingerprint_payload"] is None
        and generic["contract"].business_action_fingerprint == action_gateway.compute_business_fingerprint(
            generic["contract"].tenant_id, generic["contract"].canonical_user_id,
            generic["contract"].tool_name, generic["contract"].normalized_payload,
        ))
    chk(f"{label}: ActionGateway's second canonicalization was a no-op (contract tool/payload == what app proposed)",
        generic["contract"].tool_name == g_tool
        and generic["contract"].normalized_payload == action_gateway.normalize_payload(g_inputs))
    saves = generic["saves"]
    chk(f"{label}: BusinessDraft seam entered — Sessions CREATE (READY_FOR_REVIEW) then READY→CONFIRMED CAS save",
        len(generic["creates"]) == 1 and generic["creates"][0]["state"].value == "READY_FOR_REVIEW"
        and len(saves) == 2
        and saves[0]["state"].value == "READY_FOR_REVIEW"
        and saves[-1]["state"].value == "CONFIRMED"
        and saves[-1]["expected_version"] == saves[0]["stored_version"]
        and saves[-1]["stored_version"] == saves[-1]["expected_version"] + 1)
    chk(f"{label}: the dedicated tool's own role policy was enforced ({expected_tool}), never the generic tool's",
        expected_tool in generic["enforced"]
        and "airtable_add" not in generic["enforced"] and "airtable_update" not in generic["enforced"])
    chk(f"{label}: no generic Airtable business write happened at proposal time (only Sessions persistence)",
        all(w[1] == Tables.SESSIONS for w in generic["generic_writes"]))


# ══════════════════════════════════════════════════
print("\n[SSOT] one mapping authority — dispatcher fallback reuses the shared canonicalization module")
# ══════════════════════════════════════════════════

chk("dispatcher's Deal/PaymentTerm/Payment/V2 field maps ARE the shared module's objects (no copy)",
    _dispatcher_module._DEAL_FIELD_MAP is canon.DEAL_FIELD_MAP
    and _dispatcher_module._PAYMENT_TERM_FIELD_MAP is canon.PAYMENT_TERM_FIELD_MAP
    and _dispatcher_module._PAYMENT_FIELD_MAP is canon.PAYMENT_FIELD_MAP
    and _dispatcher_module._PAYMENT_V2_FIELD_MAP is canon.PAYMENT_V2_FIELD_MAP)
chk("dispatcher's routing/alias/link-unwrapping helpers ARE the shared module's functions",
    _dispatcher_module._CRM_TABLE_ROUTING is canon.CRM_TABLE_ROUTING
    and _dispatcher_module._crm_create_route is canon.crm_create_route
    and _dispatcher_module._map_generic_fields_to_canonical is canon.map_generic_fields_to_canonical
    and _dispatcher_module._resolve_protected_crm_table is canon.resolve_protected_crm_table)
chk("mapping-drift closure: generic Deal map now carries the writer-supported counterparty/start_date columns",
    canon.DEAL_FIELD_MAP[DealFields.COUNTERPARTY_CONTACT] == ("counterparty_contact_id", "single")
    and canon.DEAL_FIELD_MAP[DealFields.COUNTERPARTY_ORGANIZATION] == ("counterparty_organization_id", "single")
    and canon.DEAL_FIELD_MAP[DealFields.START_DATE] == ("start_date", None))
chk("mapping-drift closure: Payments UPDATE recognizes the V2-only writer-updatable columns (method/counterparty/document)",
    canon.crm_update_field_map(Tables.PAYMENTS)[PaymentFields.METHOD] == ("method", None)
    and canon.crm_update_field_map(Tables.PAYMENTS)[PaymentFields.COUNTERPARTY_CONTACT] == ("counterparty_contact_id", "single")
    and canon.crm_update_field_map(Tables.PAYMENTS)[PaymentFields.DOCUMENT_REQUIREMENT] == ("document_requirement", None))
chk("the canonicalization module imports no Airtable I/O at module level",
    not any(name in open(canon.__file__, encoding="utf-8").read().split('"""', 2)[2].split("\ndef ", 1)[0]
            for name in ("airtable_tools", "airtable_gateway", "airtable_read_adapter", "requests", "httpx")))


# ══════════════════════════════════════════════════
print("\n[PURE] canonicalization mapping — UPDATE / CREATE / legacy / malformed / non-commercial")
# ══════════════════════════════════════════════════

_DEAL_ID = _rid("DEAL", 1)
_TERM_ID = _rid("TERM", 1)
_PAY_ID = _rid("PAY", 1)

_CASES_OK = [
    ("Deal UPDATE stage", "airtable_update",
     {"table": "Deals", "record_id": _DEAL_ID, "fields": {DealFields.STAGE: DealStage.NEGOTIATION}},
     "crm_update_deal", {"record_id": _DEAL_ID, "stage": DealStage.NEGOTIATION}),
    ("Deal UPDATE Hebrew alias + Domain free-text normalization", "airtable_update",
     {"table": "עסקאות (Deals)", "record_id": _DEAL_ID, "fields": {DealFields.DOMAIN: "import"}},
     "crm_update_deal", {"record_id": _DEAL_ID, "domain": "import"}),
    ("Deal UPDATE linked Owner list → scalar", "airtable_update",
     {"table": "Deals", "record_id": _DEAL_ID, "fields": {DealFields.OWNER: ["recOWNER00000002"]}},
     "crm_update_deal", {"record_id": _DEAL_ID, "owner_id": "recOWNER00000002"}),
    ("PaymentTerm UPDATE notes", "airtable_update",
     {"table": "Payment Terms", "record_id": _TERM_ID, "fields": {PaymentTermFields.NOTES: "n"}},
     "crm_update_payment_term", {"record_id": _TERM_ID, "notes": "n"}),
    ("Payment UPDATE notes + method", "airtable_update",
     {"table": "Payments", "record_id": _PAY_ID, "fields": {PaymentFields.NOTES: "n", PaymentFields.METHOD: "bank"}},
     "crm_update_payment", {"record_id": _PAY_ID, "notes": "n", "method": "bank"}),
    ("Deal CREATE with counterparty link", "airtable_add",
     {"table": "Deals", "fields": {DealFields.NAME: "Acme", DealFields.DOMAIN: "import",
                                   DealFields.COUNTERPARTY_CONTACT: ["recCONTACT000001"]}},
     "crm_create_deal", {"name": "Acme", "domain": "import", "counterparty_contact_id": "recCONTACT000001"}),
    ("PaymentTerm CREATE with direction/currency/delay/dates", "airtable_add",
     {"table": "Payment Terms", "fields": {
         PaymentTermFields.DEAL: [_DEAL_ID], PaymentTermFields.CALC_TYPE: "fixed",
         PaymentTermFields.DIRECTION: "receivable", PaymentTermFields.CURRENCY: "ILS",
         PaymentTermFields.FIXED_AMOUNT: 8000, PaymentTermFields.TRIGGER_TYPE: PaymentTermTrigger.AFTER_PERIOD,
         PaymentTermFields.TRIGGER_DELAY_DAYS: 30, PaymentTermFields.START_DATE: "2026-10-01",
         PaymentTermFields.END_DATE: "2027-10-01"}},
     "crm_create_payment_term", {
         "deal_id": _DEAL_ID, "calc_type": "fixed", "direction": "receivable", "currency": "ILS",
         "fixed_amount": 8000, "trigger_type": PaymentTermTrigger.AFTER_PERIOD, "trigger_delay_days": 30,
         "start_date": "2026-10-01", "end_date": "2027-10-01"}),
    ("Payment V2 CREATE (Charge-linked)", "airtable_add",
     {"table": "Payments", "fields": {
         PaymentFields.CHARGE: [_rid("CHG", 1)], PaymentFields.DEAL_LINK: [_DEAL_ID],
         PaymentFields.DIRECTION: "receivable", PaymentFields.AMOUNT: 500,
         PaymentFields.CURRENCY: "ILS", PaymentFields.PAID_AT: "2026-01-01"}},
     "crm_create_charge_payment", {
         "charge_id": _rid("CHG", 1), "deal_id": _DEAL_ID, "direction": "receivable",
         "amount": 500, "currency": "ILS", "paid_at": "2026-01-01"}),
]
for label, tool, inputs, want_tool, want_payload in _CASES_OK:
    before = copy.deepcopy(inputs)
    got_tool, got_payload = resolve_canonical_call(tool, inputs)
    chk(f"{label}: {tool} → {want_tool}", got_tool == want_tool)
    chk(f"{label}: primitive writer-space payload maps losslessly (no table/fields envelope)",
        got_payload == want_payload)
    chk(f"{label}: input payload not mutated", inputs == before)
    again = resolve_canonical_call(got_tool, got_payload)
    chk(f"{label}: idempotent — canonicalize(canonicalize(call)) == canonicalize(call), byte-for-byte",
        again == (got_tool, got_payload)
        and json.dumps(again, ensure_ascii=False) == json.dumps((got_tool, got_payload), ensure_ascii=False))
    chk(f"{label}: tool-name-only view agrees", resolve_canonical_tool(tool, inputs) == want_tool)
    chk(f"{label}: deterministic across calls", resolve_canonical_call(tool, copy.deepcopy(inputs)) == (got_tool, got_payload))


_LEGACY_PAYMENT = {"table": "Payments", "fields": {
    PaymentFields.AMOUNT: 300, PaymentFields.DOMAIN: "general", PaymentFields.OWNER: ["recOWNERLEGACY01"],
}}
_CASES_BLOCK = [
    ("legacy flat Payment CREATE shape", "airtable_add", _LEGACY_PAYMENT),
    ("legacy flat Payment CREATE (amount only)", "airtable_add", {"table": "Payments", "fields": {PaymentFields.AMOUNT: 5}}),
    ("ambiguous protected alias", "airtable_update", {"table": "Deals!", "record_id": _DEAL_ID, "fields": {DealFields.NOTES: "x"}}),
    ("absent table", "airtable_update", {"record_id": _DEAL_ID, "fields": {DealFields.NOTES: "x"}}),
    ("non-dict fields", "airtable_add", {"table": "Deals", "fields": [DealFields.NAME, "x"]}),
    ("unmapped column", "airtable_add", {"table": "Payment Terms", "fields": {"Bogus Column": 1}}),
    ("invalid link cardinality", "airtable_add",
     {"table": "Payment Terms", "fields": {PaymentTermFields.DEAL: [_DEAL_ID, _rid("DEAL", 2)]}}),
    ("non-string linked record", "airtable_update", {"table": "Deals", "record_id": _DEAL_ID, "fields": {DealFields.OWNER: 7}}),
    ("malformed UPDATE record_id", "airtable_update", {"table": "Payments", "record_id": "recSHORT", "fields": {PaymentFields.NOTES: "x"}}),
    ("missing UPDATE record_id", "airtable_update", {"table": "Payment Terms", "fields": {PaymentTermFields.NOTES: "x"}}),
    ("empty UPDATE fields", "airtable_update", {"table": "Deals", "record_id": _DEAL_ID, "fields": {}}),
    ("tenant_id-only UPDATE fields", "airtable_update", {"table": "Deals", "record_id": _DEAL_ID, "fields": {"tenant_id": "t"}}),
    ("unrecognized Deal Domain word on UPDATE", "airtable_update",
     {"table": "Deals", "record_id": _DEAL_ID, "fields": {DealFields.DOMAIN: "no-such-domain-xyz"}}),
    ("Deal AMOUNT column (writer never accepts amount)", "airtable_add", {"table": "Deals", "fields": {DealFields.AMOUNT: 5}}),
]
for label, tool, inputs in _CASES_BLOCK:
    try:
        resolve_canonical_call(tool, inputs)
        raised = None
    except Exception as exc:  # noqa: BLE001
        raised = exc
    chk(f"fail closed before proposal — {label}",
        isinstance(raised, CommercialCanonicalizationError) and isinstance(raised, CanonicalizationError)
        and str(getattr(raised, "user_message", "")).startswith("❌"))
    chk(f"fail closed — {label}: tool-name-only view never raises and never invents a canonical tool",
        resolve_canonical_tool(tool, inputs) == tool)

try:
    resolve_canonical_call("airtable_add", _LEGACY_PAYMENT)
except CommercialCanonicalizationError as exc:
    chk("legacy Payment block reason names the legacy writer (operator log) but the user message does not",
        "crm_create_payment" in str(exc) and "crm_create_payment" not in exc.user_message)


_UNCHANGED = [
    ("Task generic UPDATE", "airtable_update",
     {"table": Tables.TASKS, "record_id": _rid("TASK", 1), "fields": {TaskFields.STATUS: "done"}}),
    ("Task generic CREATE", "airtable_add", {"table": Tables.TASKS, "fields": {TaskFields.NAME: "t"}}),
    ("Contacts generic CREATE", "airtable_add", {"table": "Contacts", "fields": {"Name": "x"}}),
    ("Contacts generic UPDATE", "airtable_update", {"table": "אנשי קשר (Contacts)", "record_id": _rid("CON", 1), "fields": {"Name": "x"}}),
    ("Leads generic UPDATE", "airtable_update", {"table": "Leads", "record_id": _rid("LEAD", 1), "fields": {"x": 1}}),
    ("non-protected table CREATE", "airtable_add", {"table": "Interaction Log", "fields": {"x": 1}}),
    ("non-protected table UPDATE", "airtable_update", {"table": Tables.QUESTS, "record_id": _rid("Q", 1), "fields": {"x": 1}}),
    ("Charges generic CREATE (existing Phase state kept)", "airtable_add", {"table": "Charges", "fields": {"Amount": 1}}),
    ("Organizations generic CREATE (existing Phase state kept)", "airtable_add", {"table": "Organizations", "fields": {"Name": "x"}}),
    ("Charges generic UPDATE (existing Phase state kept)", "airtable_update", {"table": "Charges", "record_id": _rid("CHG", 9), "fields": {"x": 1}}),
    ("dedicated crm_update_deal", "crm_update_deal", {"record_id": _DEAL_ID, "stage": DealStage.NEGOTIATION}),
    ("dedicated crm_create_charge_payment", "crm_create_charge_payment", {"charge_id": _rid("CHG", 1), "amount": 5}),
    ("direct legacy crm_create_payment primitive (compatibility, untouched)", "crm_create_payment",
     {"amount": 300, "domain": "general", "owner_id": "recOWNERLEGACY01"}),
]
for label, tool, inputs in _UNCHANGED:
    chk(f"unchanged — {label}", resolve_canonical_call(tool, inputs) == (tool, inputs)
        and canon.canonicalize_generic_commercial_call(tool, inputs) is None)


# ══════════════════════════════════════════════════
print("\n[E2E UPDATE] generic airtable_update → dedicated tool → BusinessDraft → ActionContract; parity with dedicated")
# ══════════════════════════════════════════════════

g = _queue("airtable_update", {"table": "Deals", "record_id": _rid("DEAL", 11), "fields": {DealFields.STAGE: DealStage.NEGOTIATION}},
           "p4b-deal-upd-generic", record=_CURRENT_DEAL)
d = _queue("crm_update_deal", {"record_id": _rid("DEAL", 11), "stage": DealStage.NEGOTIATION},
           "p4b-deal-upd-dedicated", record=_CURRENT_DEAL)
_parity("Deal UPDATE (stage)", g, d, "crm_update_deal")
chk("Deal UPDATE: CONFIRMED draft cleaned up after the complete handoff (existing Phase 3 lifecycle)",
    lead_sessions.load_business_draft(
        "p4b-deal-upd-generic", "deal", tenant_id=_TENANT, actor_user_id=_identity("p4b-deal-upd-generic").memory_key,
        source_channel=_CHANNEL, channel=_CHANNEL,
    ) is None)

g = _queue("airtable_update", {"table": "Deals", "record_id": _rid("DEAL", 12), "fields": {DealFields.DOMAIN: "finance"}},
           "p4b-deal-domain-generic", record=_CURRENT_DEAL)
d = _queue("crm_update_deal", {"record_id": _rid("DEAL", 12), "domain": "finance"},
           "p4b-deal-domain-dedicated", record=_CURRENT_DEAL)
_parity("Deal UPDATE (domain)", g, d, "crm_update_deal")

g = _queue("airtable_update", {"table": "Deals", "record_id": _rid("DEAL", 13), "fields": {DealFields.OWNER: ["recOWNERNEW00001"]}},
           "p4b-deal-owner-generic", record=_CURRENT_DEAL)
chk("Deal UPDATE (Owner link): generic linked Owner list becomes the scalar owner_id the seam resolves",
    _proposed(g)[0] == "crm_update_deal" and _proposed(g)[1].get("owner_id") == "recOWNERNEW00001")

g = _queue("airtable_update", {"table": "Payment Terms", "record_id": _rid("TERM", 11), "fields": {PaymentTermFields.NOTES: "updated notes"}},
           "p4b-term-upd-generic", record=_CURRENT_TERM)
d = _queue("crm_update_payment_term", {"record_id": _rid("TERM", 11), "notes": "updated notes"},
           "p4b-term-upd-dedicated", record=_CURRENT_TERM)
_parity("PaymentTerm UPDATE (notes)", g, d, "crm_update_payment_term")

g = _queue("airtable_update", {"table": "Payments", "record_id": _rid("PAY", 11), "fields": {PaymentFields.NOTES: "paid by wire"}},
           "p4b-pay-upd-generic", record=_CURRENT_PAYMENT)
d = _queue("crm_update_payment", {"record_id": _rid("PAY", 11), "notes": "paid by wire"},
           "p4b-pay-upd-dedicated", record=_CURRENT_PAYMENT)
_parity("Payment UPDATE (notes)", g, d, "crm_update_payment")

g = _queue("airtable_update", {"table": "Payments", "record_id": _rid("PAY", 12), "fields": {PaymentFields.AMOUNT: 999}},
           "p4b-pay-upd-immutable", record=_CURRENT_PAYMENT)
chk("Payment UPDATE financial immutability stays frozen: a generic amount edit fails closed in the seam, no contract",
    g["outcome"].get("ok") is False and not g["propose"])


# UX parity: the canonical crm_update_deal contract keeps the same
# label-aware Deal summary the generic Deals path showed (Deal enrichment).
from commercial_completion_ux import deal_field_business_summary  # noqa: E402
from core.action_gateway import _describe_contract_for_reconfirmation  # noqa: E402

_enrich_fields = {DealFields.BUSINESS_DEAL_TYPE: "שירות", DealFields.ENGAGEMENT_DURATION: "מתמשכת"}
g = _queue("airtable_update", {"table": "Deals", "record_id": _rid("DEAL", 14), "fields": dict(_enrich_fields)},
           "p4b-deal-enrich-ux", record=_CURRENT_DEAL)
_generic_summary = deal_field_business_summary(_enrich_fields)
chk("UX parity: enrichment-shaped generic Deals update is minted as crm_update_deal",
    g["contract"] is not None and g["contract"].tool_name == "crm_update_deal")
chk("UX parity: the approval prompt shows the same business summary the generic Deals path showed",
    bool(_generic_summary) and _generic_summary in app._describe_tool_call("crm_update_deal", _proposed(g)[1]))
chk("UX parity: reconfirmation/lifecycle description shows the same business summary, no raw tool name",
    g["contract"] is not None
    and _generic_summary in _describe_contract_for_reconfirmation(g["contract"])
    and "crm_update_deal" not in _describe_contract_for_reconfirmation(g["contract"]))


# ══════════════════════════════════════════════════
print("\n[E2E CREATE] generic airtable_add → dedicated tool → BusinessDraft; invariants enforced")
# ══════════════════════════════════════════════════

g = _queue("airtable_add", {"table": "Deals", "fields": {
    DealFields.NAME: "Acme 4B", DealFields.DOMAIN: "import", DealFields.COUNTERPARTY_CONTACT: ["recCONTACT000001"]}},
    "p4b-deal-create-generic")
d = _queue("crm_create_deal", {"name": "Acme 4B", "domain": "import", "counterparty_contact_id": "recCONTACT000001"},
           "p4b-deal-create-dedicated")
_parity("Deal CREATE", g, d, "crm_create_deal")
chk("Deal CREATE: Owner canonicalized by the existing identity-sensitive seam (not the pure canonicalizer)",
    _proposed(g)[1].get("owner_id") == _RESOLVED_OWNER)

g = _queue("airtable_add", {"table": "Deals", "fields": {DealFields.NAME: "No Counterparty", DealFields.DOMAIN: "import"}},
           "p4b-deal-create-no-counterparty")
d = _queue("crm_create_deal", {"name": "No Counterparty", "domain": "import"}, "p4b-deal-create-no-counterparty-dedicated")
chk("Deal CREATE missing the BusinessDraft counterparty invariant fails closed — not weakened for the generic origin",
    g["outcome"].get("ok") is False and not g["propose"]
    and not any(sv["state"].value == "CONFIRMED" for sv in g["saves"]))
chk("Deal CREATE missing counterparty: generic outcome is identical to the dedicated tool's own outcome",
    g["outcome"] == d["outcome"])

g = _queue("airtable_add", {"table": "Payment Terms", "fields": {
    PaymentTermFields.DEAL: [_rid("DEAL", 21)], PaymentTermFields.CALC_TYPE: "fixed",
    PaymentTermFields.DIRECTION: "receivable", PaymentTermFields.CURRENCY: "ILS",
    PaymentTermFields.FIXED_AMOUNT: 8000}}, "p4b-term-create-generic")
d = _queue("crm_create_payment_term", {"deal_id": _rid("DEAL", 21), "calc_type": "fixed", "direction": "receivable",
                                       "currency": "ILS", "fixed_amount": 8000}, "p4b-term-create-dedicated")
_parity("PaymentTerm CREATE", g, d, "crm_create_payment_term")

g = _queue("airtable_add", {"table": "Payment Terms", "fields": {
    PaymentTermFields.DEAL: [_rid("DEAL", 22)], PaymentTermFields.CALC_TYPE: "fixed",
    PaymentTermFields.FIXED_AMOUNT: 8000, PaymentTermFields.CURRENCY: "ILS"}}, "p4b-term-create-no-direction")
chk("PaymentTerm CREATE without Phase 4A-required direction fails closed, no contract",
    g["outcome"].get("ok") is False and not g["propose"])

g = _queue("airtable_add", {"table": "Payment Terms", "fields": {
    PaymentTermFields.DEAL: [_rid("DEAL", 23)], PaymentTermFields.CALC_TYPE: "fixed",
    PaymentTermFields.DIRECTION: "receivable", PaymentTermFields.CURRENCY: "ILS",
    PaymentTermFields.FIXED_AMOUNT: 8000, PaymentTermFields.TRIGGER_TYPE: PaymentTermTrigger.AFTER_PERIOD}},
    "p4b-term-create-no-delay")
chk("PaymentTerm CREATE with after_period trigger but no trigger_delay_days fails closed (Phase 4A calculation rule)",
    g["outcome"].get("ok") is False and not g["propose"])

g = _queue("airtable_add", {"table": "Payments", "fields": {
    PaymentFields.CHARGE: [_rid("CHG", 21)], PaymentFields.DEAL_LINK: [_rid("DEAL", 24)],
    PaymentFields.DIRECTION: "receivable", PaymentFields.AMOUNT: 500,
    PaymentFields.CURRENCY: "ILS", PaymentFields.PAID_AT: "2026-01-01"}}, "p4b-pay-create-generic")
d = _queue("crm_create_charge_payment", {"charge_id": _rid("CHG", 21), "deal_id": _rid("DEAL", 24),
                                         "direction": "receivable", "amount": 500, "currency": "ILS",
                                         "paid_at": "2026-01-01"}, "p4b-pay-create-dedicated")
_parity("Payment V2 CREATE", g, d, "crm_create_charge_payment")


# ══════════════════════════════════════════════════
print("\n[DUPLICATE] same user, generic then dedicated form of the SAME action → recognized as one business action")
# ══════════════════════════════════════════════════

_dup_sender = "p4b-dup-same-user"
first = _queue("airtable_update", {"table": "Payment Terms", "record_id": _rid("TERM", 31), "fields": {PaymentTermFields.NOTES: "dup"}},
               _dup_sender, record=_CURRENT_TERM)
second_patches_identity = _identity(_dup_sender)
with patch.object(app, "resolve_identity", return_value=second_patches_identity), \
     patch("tools.airtable_read_adapter.get_record_fields", return_value=_CURRENT_TERM):
    second = app._queue_approval_detailed(
        "crm_update_payment_term", {"record_id": _rid("TERM", 31), "notes": "dup"}, _dup_sender, _CHANNEL,
    )
chk("the first (generic) proposal created a crm_update_payment_term contract",
    first["outcome"].get("ok") is True and _proposed(first)[0] == "crm_update_payment_term")
chk("the dedicated re-send of the same action is suppressed as the SAME pending business action (dedup parity)",
    second.get("ok") is False and second.get("created_this_turn") is False
    and second.get("action_tool") == "crm_update_payment_term")
_clear(_dup_sender)


# ══════════════════════════════════════════════════
print("\n[LEGACY] generic Payments CREATE in the legacy flat shape fails closed BEFORE any ActionContract")
# ══════════════════════════════════════════════════

with patch("commercial_crm.create_payment") as mock_legacy_writer, \
     patch("commercial_crm.create_charge_payment") as mock_v2_writer:
    legacy = _queue("airtable_add", copy.deepcopy(_LEGACY_PAYMENT), "p4b-legacy-payment")
chk("legacy generic Payment CREATE: outcome is a verified never-attempted failure",
    legacy["outcome"].get("ok") is False
    and legacy["outcome"].get("terminal_outcome") == "APPROVAL_QUEUE_NEVER_ATTEMPTED"
    and legacy["outcome"].get("contract_id") is None)
chk("legacy generic Payment CREATE: ActionGateway.propose_action was never called (no ActionContract)",
    not legacy["propose"])
chk("legacy generic Payment CREATE: no BusinessDraft was created or saved", not legacy["creates"] and not legacy["saves"])
chk("legacy generic Payment CREATE: no Airtable mutation (no writer, no generic write)",
    mock_legacy_writer.call_count == 0 and mock_v2_writer.call_count == 0 and not legacy["generic_writes"])
chk("legacy generic Payment CREATE: not reinterpreted as V2 and not continued as airtable_add",
    legacy["outcome"].get("action_tool") in ("airtable_add",) and "crm_create_charge_payment" not in json.dumps(legacy["outcome"]))
chk("legacy generic Payment CREATE: the user gets the specific legacy-shape reason",
    "חיוב" in legacy["outcome"].get("message", ""))
chk("ENTITY_CONTRACTS['payment'] still binds to the V2 writer, untouched",
    app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL.get("crm_create_charge_payment") == "payment"
    and "crm_create_payment" not in app._COMMERCIAL_DRAFT_ENTITY_FOR_TOOL)

with patch("commercial_crm.create_payment", return_value={"ok": True, "tool": "crm_create_payment", "external_id": "recPAYLEGACY0001", "evidence": {}, "user_message": "ok"}) as mock_direct, \
     patch.object(_dispatcher_module, "_validate_execution_proof", return_value=None), \
     patch.object(_dispatcher_module._ff, "is_enabled", return_value=False):
    _dispatcher_module.dispatch_tool(
        "crm_create_payment", {"amount": 300, "domain": "general", "owner_id": "recOWNERLEGACY01"},
        identity=_identity("p4b-direct-legacy"), trusted_source="agent",
        execution_context={"contract_id": "p4b-direct-legacy-primitive"},
    )
chk("the direct legacy crm_create_payment dispatcher primitive remains unchanged (compatibility)",
    mock_direct.call_count == 1 and mock_direct.call_args.kwargs.get("amount") == 300)


# ══════════════════════════════════════════════════
print("\n[AUTH] generic tool possession never authorizes the narrower commercial mutation")
# ══════════════════════════════════════════════════

_employee = _identity("p4b-employee", Role.EMPLOYEE)
chk("precondition: employee DOES possess the generic airtable_add tool",
    tool_registry.enforce("airtable_add", _employee) is not None)
for label, tool, inputs, canonical_tool, record in [
    ("Deal CREATE", "airtable_add", {"table": "Deals", "fields": {
        DealFields.NAME: "E", DealFields.DOMAIN: "import", DealFields.COUNTERPARTY_CONTACT: ["recCONTACT000001"]}},
     "crm_create_deal", None),
    ("PaymentTerm CREATE", "airtable_add", {"table": "Payment Terms", "fields": {
        PaymentTermFields.DEAL: [_DEAL_ID], PaymentTermFields.CALC_TYPE: "fixed", PaymentTermFields.DIRECTION: "receivable",
        PaymentTermFields.CURRENCY: "ILS", PaymentTermFields.FIXED_AMOUNT: 1}}, "crm_create_payment_term", None),
    ("Payment V2 CREATE", "airtable_add", {"table": "Payments", "fields": {
        PaymentFields.CHARGE: [_rid("CHG", 41)], PaymentFields.DEAL_LINK: [_DEAL_ID], PaymentFields.DIRECTION: "receivable",
        PaymentFields.AMOUNT: 1, PaymentFields.CURRENCY: "ILS", PaymentFields.PAID_AT: "2026-01-01"}},
     "crm_create_charge_payment", None),
    ("Deal UPDATE", "airtable_update", {"table": "Deals", "record_id": _DEAL_ID, "fields": {DealFields.NOTES: "x"}},
     "crm_update_deal", _CURRENT_DEAL),
    ("PaymentTerm UPDATE", "airtable_update", {"table": "Payment Terms", "record_id": _TERM_ID, "fields": {PaymentTermFields.NOTES: "x"}},
     "crm_update_payment_term", _CURRENT_TERM),
    ("Payment UPDATE", "airtable_update", {"table": "Payments", "record_id": _PAY_ID, "fields": {PaymentFields.NOTES: "x"}},
     "crm_update_payment", _CURRENT_PAYMENT),
]:
    for role in (Role.EMPLOYEE, Role.LEAD):
        obs = _queue(tool, inputs, f"p4b-auth-{role}-{canonical_tool}", role=role, record=record)
        chk(f"{label} as {role} via generic {tool}: denied under {canonical_tool}'s own policy, no contract, no draft",
            obs["outcome"].get("ok") is False and not obs["propose"] and not obs["creates"]
            and canonical_tool in obs["enforced"] and tool not in obs["enforced"])


# ══════════════════════════════════════════════════
print("\n[FALLBACK] a pre-Phase-4B generic commercial contract still executes via the dispatcher redirect")
# ══════════════════════════════════════════════════

# Simulate a contract minted BEFORE Phase 4B (frozen generic tool identity)
# by bypassing the pre-proposal canonicalization for exactly this proposal.
_pre4b_owner = _identity("p4b-pre4b-contract")
with patch.object(_gateway_module, "resolve_canonical_call", side_effect=lambda t, p, u="": (t, dict(p or {}))):
    pre4b = action_gateway.propose_action(
        tenant_id=_TENANT, canonical_user_id=_pre4b_owner.memory_key,
        tool_name="airtable_update",
        tool_inputs={"table": "Deals", "record_id": _rid("DEAL", 51), "fields": {DealFields.STAGE: DealStage.NEGOTIATION}},
        origin_channel=_CHANNEL, origin_chat_id=_pre4b_owner.user_id,
        requires_approval=True, identity=_pre4b_owner, trusted_source="agent",
    )
pre4b_contract = action_gateway._ledger.find_by_id(pre4b.contract_id) if pre4b.ok else None
chk("setup: a generic-identity (airtable_update) contract exists, as one minted before Phase 4B would",
    pre4b_contract is not None and pre4b_contract.tool_name == "airtable_update")

with patch("commercial_crm.update_deal", return_value={
        "ok": True, "tool": "crm_update_deal", "external_id": _rid("DEAL", 51),
        "evidence": {"record_id": _rid("DEAL", 51)}, "user_message": "ok"}) as mock_update_deal, \
     patch.object(_dispatcher_module, "airtable_update") as mock_raw_update, \
     patch.object(_dispatcher_module._ff, "is_enabled", return_value=False):
    approve_reply = action_gateway.approve(
        pre4b.contract_id, approver=_pre4b_owner.memory_key, approver_role=_pre4b_owner.role,
    ) if pre4b_contract else ""
chk("the approved pre-4B generic contract executed through the existing dispatcher redirect into the Golden Writer",
    mock_update_deal.call_count == 1
    and mock_update_deal.call_args.args[0] == _rid("DEAL", 51)
    and mock_update_deal.call_args.args[1] == {"stage": DealStage.NEGOTIATION})
chk("the fallback never degraded to a raw generic Airtable write", mock_raw_update.call_count == 0)
chk("the fallback contract kept its frozen generic identity (not re-canonicalized at execution)",
    action_gateway._ledger.find_by_id(pre4b.contract_id).tool_name == "airtable_update")

with patch("commercial_crm.update_payment", return_value={"ok": True, "tool": "crm_update_payment", "external_id": _PAY_ID, "evidence": {}, "user_message": "ok"}) as mock_upd_pay, \
     patch("commercial_crm.create_payment_term", return_value={"ok": True, "tool": "crm_create_payment_term", "external_id": _TERM_ID, "evidence": {}, "user_message": "ok"}) as mock_new_term, \
     patch.object(_dispatcher_module, "_validate_execution_proof", return_value=None), \
     patch.object(_dispatcher_module._ff, "is_enabled", return_value=False):
    _dispatcher_module.dispatch_tool(
        "airtable_update", {"table": "Payments", "record_id": _PAY_ID, "fields": {PaymentFields.METHOD: "bank"}},
        identity=_identity("p4b-fallback-pay"), trusted_source="agent",
        execution_context={"contract_id": "p4b-fallback-payment-update"},
    )
    _dispatcher_module.dispatch_tool(
        "airtable_add", {"table": "Payment Terms", "fields": {
            PaymentTermFields.DEAL: [_DEAL_ID], PaymentTermFields.CALC_TYPE: "fixed",
            PaymentTermFields.DIRECTION: "receivable", PaymentTermFields.CURRENCY: "ILS",
            PaymentTermFields.FIXED_AMOUNT: 10}},
        identity=_identity("p4b-fallback-term"), trusted_source="agent",
        execution_context={"contract_id": "p4b-fallback-term-create"},
    )
chk("dispatcher fallback (Payments UPDATE) reaches update_payment via the SAME shared map",
    mock_upd_pay.call_count == 1 and mock_upd_pay.call_args.args[1] == {"method": "bank"})
chk("dispatcher fallback (Payment Terms CREATE) reaches create_payment_term via the SAME shared map",
    mock_new_term.call_count == 1 and mock_new_term.call_args.kwargs.get("direction") == "receivable")


# ══════════════════════════════════════════════════
print("\n[NONCOMMERCIAL] generic Airtable behavior outside Deal/PaymentTerm/Payment is unchanged")
# ══════════════════════════════════════════════════

_task_inputs = {"table": Tables.TASKS, "record_id": _rid("TASK", 61), "fields": {TaskFields.STATUS: "done"}}
t = _queue("airtable_update", copy.deepcopy(_task_inputs), "p4b-task-update")
chk("Task generic UPDATE still proposes airtable_update with its original table/record/fields envelope",
    _proposed(t)[0] == "airtable_update" and _proposed(t)[1] == _task_inputs and not t["creates"])

_other_inputs = {"table": "Interaction Log", "fields": {"Summary": "x"}}
o = _queue("airtable_add", copy.deepcopy(_other_inputs), "p4b-other-add")
chk("non-protected generic airtable_add still proposes airtable_add unchanged",
    _proposed(o)[0] == "airtable_add" and _proposed(o)[1] == _other_inputs and not o["creates"])

_contact_inputs = {"table": "Contacts", "fields": {"Name": "Dana"}}
c = _queue("airtable_add", copy.deepcopy(_contact_inputs), "p4b-contact-add")
chk("Contacts generic airtable_add still proposes airtable_add unchanged (Contacts redirect stays in the dispatcher)",
    _proposed(c)[0] == "airtable_add" and _proposed(c)[1] == _contact_inputs and not c["creates"])

_charge_inputs = {"table": "Charges", "fields": {"Amount": 1}}
ch = _queue("airtable_add", copy.deepcopy(_charge_inputs), "p4b-charge-add")
chk("Charges generic airtable_add keeps its existing (pre-4B) Phase state — not migrated to BusinessDraft",
    _proposed(ch)[0] == "airtable_add" and _proposed(ch)[1] == _charge_inputs and not ch["creates"])


print(f"\n{'=' * 60}")
print(f"BusinessDraft Phase 4B (generic commercial bypass closure) tests: {passed} passed, {failed} failed")
import sys  # noqa: E402
sys.exit(0 if failed == 0 else 1)
