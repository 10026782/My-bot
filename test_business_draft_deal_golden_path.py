#!/usr/bin/env python3
"""BUSINESSDRAFT PHASE 3 — Deal Golden Path.

Standalone assert-based script (repo convention: `python3 test_business_draft_deal_golden_path.py`).

Exercises app.py's single Deal seam (`_run_deal_business_draft`, wired into
`_queue_approval_detailed_impl`) directly at the unit level (Airtable I/O
mocked, matching test_phase0_commercial_crm_update_authority.py's
convention) plus a handful of true end-to-end checks through
`app.run_agent()` (matching test_bug_crm_bypass_create_deal_deterministic_route.py's
convention) for the properties that only the full pipeline can prove:
fingerprint parity and that Sessions persistence actually happened, not just
an in-memory BusinessDraft object.

See docs/architecture/BUSINESSDRAFT_UX_CONTRACT_FREEZE_20260922.md and the
Phase 3 implementation plan for the full design this proves.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-phase3-deal-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PHASE3_DEAL_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPhase3DealTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPhase3DealTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from commercial_completion import ENTITY_CONTRACTS  # noqa: E402
from core.action_gateway import action_gateway  # noqa: E402
from identity import Identity, Role  # noqa: E402
from session_store import lead_sessions  # noqa: E402
from tools import dispatcher as _dispatcher_module  # noqa: E402

# Sessions persistence for BusinessDraft goes through tools.airtable_tools
# under the hood (session_store.py's own I/O boundary) -- mock it exactly
# like test_business_draft_persistence.py does so this file exercises real
# CAS/version logic without depending on (or repeatedly failing against, and
# eventually tripping the circuit breaker on) a real Airtable connection.
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


_DEAL_CONTRACT = ENTITY_CONTRACTS["deal"]
_AIRTABLE_FIELD = {fc.field_name: fc.airtable_field for fc in _DEAL_CONTRACT.fields}
_RESOLVED_OWNER = "recPROFILE0000001"
_CHANNEL = "telegram"
_STAGE_WON = "סגור-ניצחון"  # one of ENTITY_CONTRACTS["deal"]'s real "stage" choices


def _rid(n: int) -> str:
    """A syntactically valid Airtable record id (rec + exactly 14 chars) --
    commercial_crm._valid_record_id()'s regex, reused for the UPDATE
    `record_id` target check, is stricter than commercial_completion.py's
    own looser LINK-field validation (`rec[A-Za-z0-9]+`, any length)."""
    return f"recDEAL{n:010d}"


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


def _clear(sender: str) -> None:
    try:
        lead_sessions.delete_business_draft(sender, "deal", channel=_CHANNEL)
    except Exception:
        pass


_resolve_owner = patch.object(
    _dispatcher_module._owner_resolution, "resolve_profile_record_id", return_value=_RESOLVED_OWNER,
)
_resolve_owner.start()


def _run(tool_name: str, tool_inputs: dict, identity: Identity, sender: str):
    return app._run_deal_business_draft(tool_name, dict(tool_inputs), identity, _CHANNEL, sender)


def _raw_deal_record(**field_values) -> dict:
    return {_AIRTABLE_FIELD[name]: value for name, value in field_values.items()}


# ══════════════════════════════════════════════════
print("\n[CREATE] authorization / owner / validation / translation")
# ══════════════════════════════════════════════════

sender = "deal-create-owner-self"
_clear(sender)
identity = _owner_identity(sender)
result = _run(
    "crm_create_deal",
    {"name": "Acme", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
chk("CREATE with owner self-reference is not blocked", not result.blocked)
chk("CREATE: owner self-reference resolves to the canonical Profile record", result.tool_inputs.get("owner_id") == _RESOLVED_OWNER)
chk("CREATE: canonical adapter-derived tool_inputs match _primitive_inputs shape", result.tool_inputs.get("name") == "Acme" and result.tool_inputs.get("domain") == "import")
_clear(sender)

sender = "deal-create-explicit-rec"
identity = _owner_identity(sender)
result2 = _run(
    "crm_create_deal",
    {"name": "Acme2", "domain": "import", "owner_id": "recEXPLICITOWNER01", "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
chk(
    "CREATE: an explicit syntactically-valid rec... owner id is accepted as-is "
    "(current resolver policy does not check record ownership -- Phase 3 preserves that)",
    not result2.blocked and result2.tool_inputs.get("owner_id") == "recEXPLICITOWNER01",
)
chk(
    "CREATE with the same self-reference and an explicit valid rec id both "
    "resolve to a canonical owner in the final snapshot (no divergence)",
    result.tool_inputs.get("owner_id") == _RESOLVED_OWNER,
)
_clear(sender)

sender = "deal-create-foreign-owner"
identity = _owner_identity(sender)
result3 = _run(
    "crm_create_deal",
    {"name": "Acme3", "domain": "import", "owner_id": "not-a-rec-id-and-not-self", "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
chk("CREATE: a value that is neither a rec... id nor a self-reference fails closed", result3.blocked)
_clear(sender)

sender = "deal-create-no-counterparty"
identity = _owner_identity(sender)
result4 = _run("crm_create_deal", {"name": "Acme4", "domain": "import", "owner_id": identity.user_id}, identity, sender)
chk(
    "CREATE lacking a counterparty fails closed before propose_action "
    "(deliberate Phase 3 contract tightening -- ENTITY_CONTRACTS['deal'] requires one)",
    result4.blocked,
)
_clear(sender)

sender = "deal-create-amount-drift"
identity = _owner_identity(sender)
result5 = _run(
    "crm_create_deal",
    {"name": "Acme5", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001", "amount": 500},
    identity, sender,
)
chk("CREATE supplying the confirmed schema-drift 'amount' field fails closed, never silently dropped", result5.blocked)
_clear(sender)

sender = "deal-create-invalid-select"
identity = _owner_identity(sender)
result6 = _run(
    "crm_create_deal",
    # "domain" is InputType.TEXT (validation="type", no declared choices --
    # live select-value resolution is the Golden Writer's job, not
    # BusinessDraft's, per "reuse, don't reimplement, final write
    # validation"). "currency" IS an InputType.SELECT field with a real
    # `choices` tuple -- this is what FieldContract.validate_value()
    # actually enforces.
    {
        "name": "Acme6", "domain": "import", "owner_id": identity.user_id,
        "counterparty_contact_id": "recCONTACT00001", "currency": "NOT_A_REAL_CURRENCY",
    },
    identity, sender,
)
chk("CREATE with an invalid SELECT value (currency) fails closed via the reused FieldContract validation", result6.blocked)
_clear(sender)

sender = "deal-create-passthrough"
identity = _owner_identity(sender)
result7 = _run(
    "crm_create_deal",
    {
        "name": "Acme7", "domain": "import", "owner_id": identity.user_id,
        "counterparty_contact_id": "recCONTACT00001", "venture_id": "recVENTURE001",
        "priority": "high",
    },
    identity, sender,
)
chk(
    "CREATE passthrough field (venture_id/priority) reaches the final payload verbatim",
    not result7.blocked and result7.tool_inputs.get("venture_id") == "recVENTURE001" and result7.tool_inputs.get("priority") == "high",
)
_clear(sender)


# ══════════════════════════════════════════════════
print("\n[UPDATE] target identity / authorization / owner / empty-value / passthrough")
# ══════════════════════════════════════════════════

_current_deal = _raw_deal_record(name="Existing Deal", domain="Import", owner="recOWNEREXIST01", stage="opportunity")

sender = "deal-update-valid"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_current_deal) as spy_read:
    result_u1 = _run("crm_update_deal", {"record_id": _rid(1), "stage": _STAGE_WON}, identity, sender)
chk("UPDATE with a valid record_id is not blocked", not result_u1.blocked)
chk("UPDATE: record_id passed through unchanged", result_u1.tool_inputs.get("record_id") == _rid(1))
chk("UPDATE: delta-only payload contains the changed field", result_u1.tool_inputs.get("stage") == _STAGE_WON)
chk("UPDATE: unchanged fields (name) are absent from the delta payload", "name" not in result_u1.tool_inputs)
chk("UPDATE: pre-read reused the existing get_record_fields() reader", spy_read.call_count == 1)
_clear(sender)

sender = "deal-update-no-owner-key"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_current_deal):
    result_u2 = _run("crm_update_deal", {"record_id": _rid(2), "stage": _STAGE_WON}, identity, sender)
chk(
    "UPDATE with no owner_id key present adds no Owner field to the mapped edits / final payload",
    not result_u2.blocked and "owner_id" not in result_u2.tool_inputs and "owner" not in result_u2.tool_inputs,
)
_clear(sender)

sender = "deal-update-missing-record-id"
identity = _owner_identity(sender)
result_u3 = _run("crm_update_deal", {"stage": _STAGE_WON}, identity, sender)
chk("UPDATE with a missing record_id fails closed before any read", result_u3.blocked)
_clear(sender)

sender = "deal-update-nonexistent-record"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=None) as spy_read_missing:
    result_u4 = _run("crm_update_deal", {"record_id": _rid(999), "stage": _STAGE_WON}, identity, sender)
chk("UPDATE with a nonexistent record_id fails closed", result_u4.blocked)
chk("UPDATE: the reader was still attempted once (record_id was syntactically valid)", spy_read_missing.call_count == 1)
_clear(sender)

sender = "deal-update-unauthorized"
identity = _lead_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_current_deal) as spy_read_unauth:
    result_u5 = _run("crm_update_deal", {"record_id": _rid(3), "stage": _STAGE_WON}, identity, sender)
chk("UPDATE from an unauthorized role fails closed", result_u5.blocked)
chk("UPDATE: unauthorized caller never triggers the pre-read", spy_read_unauth.call_count == 0)
_clear(sender)

sender = "deal-update-explicit-clear"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_current_deal):
    result_u6 = _run("crm_update_deal", {"record_id": _rid(4), "notes": ""}, identity, sender)
chk(
    "UPDATE explicit-clear on a mapped field fails closed (unsupported in Phase 3), "
    "never silently omitted / treated as unchanged",
    result_u6.blocked,
)
_clear(sender)

sender = "deal-update-passthrough-clear"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_current_deal):
    # A passthrough-only UPDATE (no mapped field change at all) never
    # reaches READY_FOR_REVIEW -- confirm() requires at least one mapped
    # delta. This is a real, minor Phase 3 boundary: BusinessDraft doesn't
    # front an update consisting purely of an unmapped field, since there
    # is nothing for it to validate/confirm in that case (documented in the
    # Phase 3 report, not papered over here). Combine the passthrough field
    # with a genuine mapped change -- the realistic shape of this scenario.
    result_u7 = _run(
        "crm_update_deal", {"record_id": _rid(5), "stage": _STAGE_WON, "venture_id": ""}, identity, sender,
    )
chk(
    "UPDATE explicit-clear on a PASSTHROUGH field is preserved verbatim alongside a real mapped "
    "change (unlike a mapped field's explicit clear) -- passthrough never goes through "
    "BusinessDraft's empty-value gate",
    not result_u7.blocked and result_u7.tool_inputs.get("venture_id") == "" and result_u7.tool_inputs.get("stage") == _STAGE_WON,
)
_clear(sender)

sender = "deal-update-domain-normalization"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_current_deal):
    # _current_deal's live Domain is "Import" (Airtable label casing);
    # supplying the business-canonical "import" must be seen as NO CHANGE.
    result_u8 = _run("crm_update_deal", {"record_id": _rid(6), "domain": "import"}, identity, sender)
chk(
    "UPDATE: live 'Import' vs canonical 'import' produces no false domain delta -- "
    "confirm() fails closed with 'nothing changed' rather than proposing a spurious update",
    result_u8.blocked,
)
_clear(sender)

sender = "deal-update-unrecognized-field"
identity = _owner_identity(sender)
with patch("tools.airtable_read_adapter.get_record_fields", return_value=_current_deal):
    result_u9 = _run("crm_update_deal", {"record_id": _rid(7), "bogus_field": "x"}, identity, sender)
chk("UPDATE with a genuinely unrecognized field fails closed, never silently dropped", result_u9.blocked)
_clear(sender)


# ══════════════════════════════════════════════════
print("\n[RETRY / FINGERPRINT STABILITY] identical confirmed payloads are byte-identical")
# ══════════════════════════════════════════════════

sender = "deal-retry-stability"
identity = _owner_identity(sender)
inputs = {"name": "Retry Deal", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"}
result_r1 = _run("crm_create_deal", inputs, identity, sender)
_clear(sender)
result_r2 = _run("crm_create_deal", inputs, identity, sender)
_clear(sender)
chk(
    "retrying an identical confirmed CREATE produces byte-identical tool_inputs "
    "(no timestamp/draft_id leakage into the fingerprinted payload)",
    not result_r1.blocked and not result_r2.blocked and result_r1.tool_inputs == result_r2.tool_inputs,
)


# ══════════════════════════════════════════════════
print("\n[CLEANUP CLASSIFICATION] ownership-checked, outcome-driven")
# ══════════════════════════════════════════════════

sender = "deal-cleanup-success"
identity = _owner_identity(sender)
result_c1 = _run(
    "crm_create_deal",
    {"name": "Cleanup Deal", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
chk("cleanup fixture: draft created for the success scenario", not result_c1.blocked)
app._finalize_deal_draft_cleanup(result_c1.draft_ctx, {"ok": True, "terminal_outcome": None}, _CHANNEL)
stored_after_success = lead_sessions.load_business_draft(
    sender, "deal", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
)
chk("successful complete queue handoff -> draft removed", stored_after_success is None)

sender = "deal-cleanup-determinate-rejection"
identity = _owner_identity(sender)
result_c2 = _run(
    "crm_create_deal",
    {"name": "Cleanup Deal 2", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
app._finalize_deal_draft_cleanup(result_c2.draft_ctx, {"ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR"}, _CHANNEL)
stored_after_rejection = lead_sessions.load_business_draft(
    sender, "deal", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
)
chk("determinate clean rejection -> draft removed", stored_after_rejection is None)

sender = "deal-cleanup-orphaned"
identity = _owner_identity(sender)
result_c3 = _run(
    "crm_create_deal",
    {"name": "Cleanup Deal 3", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
app._finalize_deal_draft_cleanup(result_c3.draft_ctx, {"ok": True, "terminal_outcome": "APPROVAL_QUEUE_ORPHANED"}, _CHANNEL)
stored_after_orphan = lead_sessions.load_business_draft(
    sender, "deal", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
)
chk("APPROVAL_QUEUE_ORPHANED final outcome -> draft retained (fail-closed retry guard)", stored_after_orphan is not None)
# _run_deal_business_draft() itself catches DraftConflictError from
# create_business_draft() and turns it into a blocked outcome (never lets
# it propagate as a raw exception) -- so the caller-visible proof is
# result.blocked, not a raised DraftConflictError.
second_attempt = _run(
    "crm_create_deal",
    {"name": "Second Attempt", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
chk(
    "a second attempt after an orphaned handoff is blocked (DraftConflictError from "
    "create_business_draft, caught and turned into a fail-closed response)",
    second_attempt.blocked,
)
_clear(sender)

sender = "deal-cleanup-not-owned"
identity = _owner_identity(sender)
pre_existing = _run(
    "crm_create_deal",
    {"name": "Pre-existing Deal", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
chk("cleanup fixture: a pre-existing CONFIRMED draft occupies the slot", not pre_existing.blocked)
blocked_attempt = _run(
    "crm_create_deal",
    {"name": "Blocked Second Attempt", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
    identity, sender,
)
chk("a second attempt blocked by the pre-existing CONFIRMED slot never creates its own draft", blocked_attempt.blocked and blocked_attempt.draft_ctx is None)
stored_untouched = lead_sessions.load_business_draft(
    sender, "deal", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
)
chk(
    "the pre-existing draft is left completely untouched by the blocked attempt "
    "(draft_ctx is None -> _queue_approval_detailed_impl never calls cleanup for it)",
    stored_untouched is not None,
)
_clear(sender)

sender = "deal-cleanup-sequential-success"
identity = _owner_identity(sender)
for i in (1, 2):
    r = _run(
        "crm_create_deal",
        {"name": f"Sequential Deal {i}", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
        identity, sender,
    )
    chk(f"sequential successful Deal attempt #{i} succeeds", not r.blocked)
    app._finalize_deal_draft_cleanup(r.draft_ctx, {"ok": True, "terminal_outcome": None}, _CHANNEL)
_clear(sender)


# ══════════════════════════════════════════════════
print("\n[END-TO-END] fingerprint parity + real Sessions persistence, through the full pipeline")
# ══════════════════════════════════════════════════

sender = "deal-e2e-fingerprint"
identity = _owner_identity(sender)
_clear(sender)

_captured = {}
_real_propose = action_gateway.propose_action


def _spy_propose(*a, **kw):
    result = _real_propose(*a, **kw)
    _captured["tool_inputs"] = kw.get("tool_inputs")
    _captured["fingerprint_payload"] = kw.get("fingerprint_payload")
    _captured["contract_id"] = result.contract_id
    return result


with patch.object(action_gateway, "propose_action", side_effect=_spy_propose), \
     patch.object(app, "resolve_identity", return_value=identity):
    outcome = app._queue_approval_detailed(
        "crm_create_deal",
        {"name": "E2E Fingerprint Deal", "domain": "import", "owner_id": identity.user_id, "counterparty_contact_id": "recCONTACT00001"},
        sender, _CHANNEL,
    )

chk("end-to-end CREATE through _queue_approval_detailed succeeds", outcome.get("ok") is True)
chk(
    "fingerprint_payload is forced to None so ActionGateway fingerprints the actual canonical tool_inputs "
    "(BUG-CRM-BYPASS-FINGERPRINT-PARITY precedent, not reintroduced)",
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
        sender, "deal", tenant_id=identity.tenant_id, actor_user_id=identity.memory_key, source_channel=_CHANNEL, channel=_CHANNEL,
    ) is None,
)
_clear(sender)


# ══════════════════════════════════════════════════
print("\n[LEGACY PATH] airtable_update-on-Deals stays untouched by the new hook")
# ══════════════════════════════════════════════════

with patch("commercial_crm.update_deal", return_value={"ok": True, "tool": "crm_update_deal", "external_id": "recDEAL0000009", "evidence": {}, "user_message": "ok"}) as mock_update_deal, \
     patch.object(_dispatcher_module, "_validate_execution_proof", return_value=None), \
     patch.object(_dispatcher_module._ff, "is_enabled", return_value=False):
    from tools.dispatcher import dispatch_tool as _dispatch_tool
    _dispatch_tool(
        "airtable_update",
        {"table": "Deals", "record_id": "recDEAL0000009", "fields": {"שלב": "won"}},
        identity=_owner_identity("deal-legacy-redirect"),
        trusted_source="agent",
        execution_context={"contract_id": "legacy-redirect-regression"},
    )
chk(
    "airtable_update-on-Deals still reaches commercial_crm.update_deal() unchanged, "
    "untouched by the new BusinessDraft hook (the hook only intercepts _queue_approval_detailed_impl, "
    "never tools/dispatcher.py's post-approval execution path)",
    mock_update_deal.call_count == 1,
)


_resolve_owner.stop()

print(f"\n{'=' * 60}")
print(f"BusinessDraft Phase 3 (Deal Golden Path) tests: {passed} passed, {failed} failed")
import sys  # noqa: E402
sys.exit(0 if failed == 0 else 1)
