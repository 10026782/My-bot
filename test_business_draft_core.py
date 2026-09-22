"""BUSINESSDRAFT PHASE 1 — core/business_draft.py coverage.

Standalone assert-based script (repo convention: `python3 test_business_draft_core.py`).
Covers the BusinessDraft envelope + CommercialEntityAdapter added by Phase 1;
regression for the primitives it wraps (commercial_completion.py,
commercial_completion_routing.py, core/draft_flow.py, core/draft_fields.py,
Phase 0's crm_update_* writers) is run separately — this file is additive,
not a replacement for those suites.
"""

from __future__ import annotations

from commercial_completion import CommercialCompletionWriter, InvalidValueError, UnknownFieldError
from core.business_draft import (
    BusinessDraftError,
    CommercialEntityAdapter,
    DraftOperation,
    DraftState,
    UnsupportedOperationError,
    create_draft,
)

_ADAPTER = CommercialEntityAdapter()


def chk(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(f"FAILED: {label}")
    print(f"  PASS: {label}")


def _fresh_deal_create():
    return create_draft(
        entity_type="deal", operation=DraftOperation.CREATE, tenant_id="t1",
        actor_role="owner", actor_user_id="recOWNER0000001", source_channel="telegram",
        sender="chat1",
    )


def _complete_deal(draft):
    draft = draft.set_field("name", "Acme deal")
    draft = draft.set_field("domain", "import")
    draft = draft.set_field("owner", "recOWNER0000001")
    draft = draft.set_field("counterparty_contact", "recCONTACT00001")
    return draft


# ══════════════════════════════════════════════════
# BUSINESS DRAFT
# ══════════════════════════════════════════════════

print("\n[BUSINESS DRAFT] create CREATE draft")
draft = _fresh_deal_create()
chk(draft.operation is DraftOperation.CREATE, "operation is CREATE")
chk(draft.lifecycle_state is DraftState.CAPTURED, "fresh empty draft starts CAPTURED")
chk(draft.draft_id == "t1:telegram:chat1:deal", "draft_id matches tenant:channel:sender:entity scoping")

print("\n[BUSINESS DRAFT] create UPDATE draft")
update_draft = create_draft(
    entity_type="deal", operation=DraftOperation.UPDATE, tenant_id="t1",
    actor_role="owner", actor_user_id="recOWNER0000001", source_channel="telegram",
    sender="chat1", original_fields={"stage": "Opportunity"},
)
chk(update_draft.operation is DraftOperation.UPDATE, "operation is UPDATE")
chk(update_draft.original_fields == {"stage": "Opportunity"}, "original_fields stored verbatim")
try:
    create_draft(
        entity_type="deal", operation=DraftOperation.UPDATE, tenant_id="t1",
        actor_role="owner", actor_user_id="u1", source_channel="telegram", sender="chat1",
    )
    raise AssertionError("FAILED: UPDATE draft without original_fields should be rejected")
except BusinessDraftError:
    print("  PASS: UPDATE draft requires original_fields")

print("\n[BUSINESS DRAFT] required-field detection")
missing_names = {f.field_name for f in draft.missing_fields()}
chk({"name", "domain", "owner", "counterparty_contact"} <= missing_names, "missing_fields lists Deal's required set")
chk(update_draft.missing_fields() == (), "UPDATE drafts report no CREATE-style missing fields")

print("\n[BUSINESS DRAFT] valid field set")
complete_draft = _complete_deal(draft)
chk(complete_draft.lifecycle_state is DraftState.READY_FOR_REVIEW, "fully-fielded Deal draft reaches READY_FOR_REVIEW")
chk(complete_draft.fields["name"] == "Acme deal", "set_field persisted the value")

print("\n[BUSINESS DRAFT] invalid field rejection")
try:
    draft.set_field("stage", "not-a-real-stage-choice-xyz")
    raise AssertionError("FAILED: invalid SELECT value should be rejected")
except InvalidValueError:
    print("  PASS: invalid field value raises InvalidValueError")
try:
    draft.set_field("no_such_field", "x")
    raise AssertionError("FAILED: unknown field should be rejected")
except UnknownFieldError:
    print("  PASS: unknown field raises UnknownFieldError")

print("\n[BUSINESS DRAFT] clear field")
cleared = complete_draft.clear_field("counterparty_contact")
chk("counterparty_contact" not in cleared.fields, "clear_field removes the value")
chk(cleared.lifecycle_state is DraftState.CAPTURED, "clearing a required field drops back to CAPTURED")

print("\n[BUSINESS DRAFT] move compatible fields (name -> notes, both TEXT)")
moved = complete_draft.move_field("name", "notes")
chk(moved.fields.get("notes") == "Acme deal", "move_field copies the value to the target")
chk("name" not in moved.fields, "move_field clears the source")

print("\n[BUSINESS DRAFT] reject incompatible move (LINK field)")
try:
    complete_draft.move_field("owner", "name")
    raise AssertionError("FAILED: moving a LINK field should be rejected")
except BusinessDraftError:
    print("  PASS: moving a LINK-typed field is rejected")
try:
    complete_draft.move_field("name", "owner")
    raise AssertionError("FAILED: moving into a LINK field should be rejected")
except BusinessDraftError:
    print("  PASS: moving a TEXT value into a LINK-typed target is rejected (type mismatch)")

print("\n[BUSINESS DRAFT] swap compatible fields (name <-> notes)")
with_notes = complete_draft.set_field("notes", "existing note")
swapped = with_notes.swap_fields("name", "notes")
chk(swapped.fields.get("name") == "existing note", "swap_fields: target value landed in name")
chk(swapped.fields.get("notes") == "Acme deal", "swap_fields: source value landed in notes")

print("\n[BUSINESS DRAFT] confirm valid draft")
confirmed, snapshot = complete_draft.confirm()
chk(confirmed.lifecycle_state is DraftState.CONFIRMED, "confirm() transitions to CONFIRMED")
chk(snapshot.tool_name == "crm_create_deal", "snapshot carries the canonical CREATE tool")
chk(snapshot.tool_inputs["name"] == "Acme deal", "snapshot tool_inputs carries the confirmed fields")
chk(snapshot.tool_inputs["owner_id"] == "recOWNER0000001", "snapshot maps completion field name to writer kwarg name")

print("\n[BUSINESS DRAFT] reject confirm when invalid/incomplete")
try:
    draft.confirm()
    raise AssertionError("FAILED: confirming an incomplete CAPTURED draft should be rejected")
except BusinessDraftError:
    print("  PASS: confirm() on an incomplete draft (not READY_FOR_REVIEW) is rejected")

print("\n[BUSINESS DRAFT] confirmed snapshot cannot be mutated through BusinessDraft API")
for attempt, label in (
    (lambda: confirmed.set_field("name", "x"), "set_field"),
    (lambda: confirmed.clear_field("name"), "clear_field"),
    (lambda: confirmed.move_field("name", "notes"), "move_field"),
    (lambda: confirmed.cancel(), "cancel"),
):
    try:
        attempt()
        raise AssertionError(f"FAILED: {label} on a CONFIRMED draft should be rejected")
    except BusinessDraftError:
        print(f"  PASS: {label} on a CONFIRMED draft is rejected")
try:
    snapshot.tool_inputs["name"] = "tampered"
    raise AssertionError("FAILED: snapshot.tool_inputs should be immutable")
except TypeError:
    print("  PASS: snapshot.tool_inputs rejects direct mutation")

print("\n[BUSINESS DRAFT] cancel")
cancelled = draft.cancel()
chk(cancelled.lifecycle_state is DraftState.CANCELLED, "cancel() transitions to CANCELLED")
try:
    cancelled.cancel()
    raise AssertionError("FAILED: cancelling an already-terminal draft should be rejected")
except BusinessDraftError:
    print("  PASS: cancelling a terminal draft again is rejected")

print("\n[BUSINESS DRAFT] expiry")
chk(draft.is_expired(now=draft.expires_at + 1) is True, "is_expired() true once past expires_at")
chk(draft.is_expired(now=draft.expires_at - 1) is False, "is_expired() false before expires_at")
expired = draft.expire()
chk(expired.lifecycle_state is DraftState.EXPIRED, "expire() transitions to EXPIRED")
try:
    expired.expire()
    raise AssertionError("FAILED: expiring an already-terminal draft should be rejected")
except BusinessDraftError:
    print("  PASS: expiring a terminal draft again is rejected")

print("\n[BUSINESS DRAFT] UPDATE draft: confirm + writer-boundary enforcement")
upd = update_draft.set_field("stage", "במשא ומתן")
chk(upd.lifecycle_state is DraftState.READY_FOR_REVIEW, "a real UPDATE change reaches READY_FOR_REVIEW")
upd_confirmed, upd_snapshot = upd.confirm()
chk(upd_snapshot.tool_name == "crm_update_deal", "UPDATE snapshot carries the canonical UPDATE tool")
chk(upd_snapshot.tool_inputs == {"stage": "במשא ומתן"}, "UPDATE snapshot is a minimal patch, not the full record")
try:
    update_draft.set_field("origin_lead", "recLEAD000000001")
    raise AssertionError("FAILED: a field outside the UPDATE writer's allowlist should be rejected")
except UnsupportedOperationError:
    print("  PASS: setting a field outside the entity's canonical UPDATE boundary is rejected")
try:
    update_draft.confirm()
    raise AssertionError("FAILED: an UPDATE draft with nothing changed should not be confirmable")
except BusinessDraftError:
    print("  PASS: an UPDATE draft with no changes is not READY_FOR_REVIEW / not confirmable")


# ══════════════════════════════════════════════════
# ENTITY ADAPTER
# ══════════════════════════════════════════════════

print("\n[ENTITY ADAPTER] validation delegates to existing contracts")
try:
    _ADAPTER.validate_field("deal", "stage", "not-a-real-stage-choice-xyz")
    raise AssertionError("FAILED: adapter.validate_field should delegate to commercial_completion.validate_value")
except InvalidValueError:
    print("  PASS: adapter.validate_field raises the same InvalidValueError as the underlying contract")
chk(
    set(_ADAPTER.get_required_fields("deal", {})) >= {"name", "domain", "owner"},
    "adapter.get_required_fields reflects EntityContract.is_required()",
)

print("\n[ENTITY ADAPTER] create payload mapping")
writer = complete_draft._writer()
from commercial_completion_routing import _primitive_inputs as _reference_primitive_inputs
chk(
    _ADAPTER.build_create_payload(writer) == _reference_primitive_inputs("deal", writer.complete_payload()),
    "adapter.build_create_payload matches commercial_completion_routing._primitive_inputs exactly",
)

print("\n[ENTITY ADAPTER] update payload mapping")
term_original = {"cadence": "Once"}
term_draft = create_draft(
    entity_type="payment_term", operation=DraftOperation.UPDATE, tenant_id="t1",
    actor_role="owner", actor_user_id="u1", source_channel="telegram", sender="chat2",
    original_fields=term_original,
)
term_draft = term_draft.set_field("notes", "renegotiated")
payload = _ADAPTER.build_update_payload(term_draft._writer(), term_original)
chk(payload == {"notes": "renegotiated"}, "update payload contains only the changed, allow-listed field")

print("\n[ENTITY ADAPTER] canonical tool selection")
chk(_ADAPTER.get_canonical_create_tool("deal") == "crm_create_deal", "CREATE tool for deal")
chk(_ADAPTER.get_canonical_update_tool("deal") == "crm_update_deal", "UPDATE tool for deal")
chk(_ADAPTER.get_canonical_update_tool("organization") is None, "organization has no canonical UPDATE tool (Phase 0 scope)")
try:
    _ADAPTER.build_update_payload(CommercialCompletionWriter("organization"), {})
    raise AssertionError("FAILED: organization has no update field mapping and should fail closed")
except UnsupportedOperationError:
    print("  PASS: build_update_payload fails closed for an entity with no canonical UPDATE writer")


# ══════════════════════════════════════════════════
# PHASE 3 — Deal primitive <-> completion-field-name translation helpers
# ══════════════════════════════════════════════════

from commercial_completion import ENTITY_CONTRACTS  # noqa: E402
from core.business_draft import (  # noqa: E402
    _CREATE_FIELD_MAP,
    _UPDATE_FIELD_MAP,
    fields_from_airtable_record,
    fields_from_primitive_create,
    fields_from_primitive_update,
)

print("\n[PHASE 3] fields_from_primitive_create / fields_from_primitive_update round-trips")
for field_name, primitive in _UPDATE_FIELD_MAP["deal"].items():
    chk(
        _CREATE_FIELD_MAP["deal"][field_name] == primitive,
        f"CREATE map agrees with UPDATE map for shared field {field_name!r}",
    )

_create_probe = {
    "name": "Acme", "domain": "import", "owner_id": "recOWNER0000001",
    "origin_lead_id": "recLEAD0000001", "stage": "opportunity",
    "venture_id": "recVENTURE001", "contact_ids": ["recC1"], "priority": "high",
    "risk_level": "low", "amount": 500,
}
mapped, unrecognized, passthrough = fields_from_primitive_create("deal", _create_probe)
chk(mapped.get("name") == "Acme" and mapped.get("domain") == "import", "CREATE: business fields mapped")
chk(mapped.get("origin_lead") == "recLEAD0000001", "CREATE: origin_lead_id -> origin_lead (CREATE-only field)")
chk("owner_id" not in mapped and "owner" not in mapped, "CREATE: owner key excluded (caller handles separately)")
chk(unrecognized == frozenset({"amount"}), "CREATE: confirmed tools/schemas.py 'amount' drift is unrecognized, not silently dropped")
chk(
    passthrough == {"venture_id": "recVENTURE001", "contact_ids": ["recC1"], "priority": "high", "risk_level": "low"},
    "CREATE: exactly the 4 independently-verified passthrough kwargs pass through raw",
)

_update_probe = {
    "record_id": "recDEAL0000001", "stage": "won", "owner_id": "recOWNER0000002",
    "venture_id": "recVENTURE002", "priority": "low",
}
mapped_u, unrecognized_u, passthrough_u = fields_from_primitive_update("deal", _update_probe)
chk(mapped_u == {"stage": "won"}, "UPDATE: only the mapped business field is returned")
chk(unrecognized_u == frozenset(), "UPDATE: no unrecognized keys for a legal payload")
chk(
    passthrough_u == {"record_id": "recDEAL0000001", "venture_id": "recVENTURE002", "priority": "low"},
    "UPDATE: record_id + the 2 supplied passthrough kwargs pass through raw, owner_id excluded",
)

mapped_bad, unrecognized_bad, _ = fields_from_primitive_update("deal", {"record_id": "r1", "bogus_field": 1})
chk(unrecognized_bad == frozenset({"bogus_field"}), "UPDATE: a genuinely unmapped key is reported, never silently dropped")

print("\n[PHASE 3] fields_from_airtable_record")
_raw_record = {
    "Deal Name": "Acme", "Domain": "Import", "Owner": ["recOWNER0000001"],
    "Counterparty (Contact)": ["recCONTACT00001"], "Stage": "opportunity",
}
_deal_contract = ENTITY_CONTRACTS["deal"]
_airtable_field_by_name = {fc.field_name: fc.airtable_field for fc in _deal_contract.fields}
_raw_by_airtable_field = {
    _airtable_field_by_name["name"]: "Acme",
    _airtable_field_by_name["domain"]: "Import",
    _airtable_field_by_name["owner"]: ["recOWNER0000001"],
    _airtable_field_by_name["counterparty_contact"]: ["recCONTACT00001"],
    _airtable_field_by_name["stage"]: "opportunity",
}
result = fields_from_airtable_record("deal", _raw_by_airtable_field)
chk(result["name"] == "Acme", "airtable record: scalar field passes through")
chk(result["owner"] == "recOWNER0000001", "airtable record: LINK field unwrapped from Airtable's [id] list to a bare scalar")
chk(result["counterparty_contact"] == "recCONTACT00001", "airtable record: second LINK field also unwrapped generically by input_type, not a hardcoded list")


def test_business_draft_core_completed() -> None:
    """pytest entry point — this module's body already ran and asserted everything above."""


print("\n" + "=" * 60)
print("BusinessDraft Phase 1 core: all checks passed")
