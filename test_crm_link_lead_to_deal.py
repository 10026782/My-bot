"""בדיקות רגרסיה — LEAD-DEAL-ASSOCIATION Model B (06/09/2026).

הרקע (audit יזום, לא production canary): המערכת תמכה רק ב-Origin Lead —
ליד יחיד, נכתב פעם אחת בזמן יצירת Deal חדש. לא היה שום מנגנון לקשר ליד
*קיים* לעסקה *קיימת* בלי ליצור עסקה חדשה ובלי "להמיר" את הליד. סעיף זה
מוסיף בדיוק את הפרימיטיב הצר הזה: `commercial_crm.link_lead_to_deal()` +
`crm_link_lead_to_deal` (registry/validator/dispatcher), כותב לשדה
מקושר-מרובה חדש (`DealFields.LINKED_LEADS`) שנפרד לגמרי מ-`ORIGIN_LEAD`.

pytest-native (assert, not a print/chk scaffold) — matches CI's `^def test_`
auto-detect convention (see test_lead_to_deal_origin_link.py's own docstring
for why a print-only helper would false-pass here).
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-lead-deal-assoc-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:LEAD_DEAL_ASSOC_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patLeadDealAssocTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appLeadDealAssocTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-lead-deal-assoc-webhook-secret")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import app  # noqa: E402
import commercial_crm  # noqa: E402
from airtable_schema import DealFields, LeadFields, Tables  # noqa: E402
from identity import Identity, Role  # noqa: E402

import tc8_test_repo_stub  # noqa: E402
tc8_test_repo_stub.patch_turn_state_repository()

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

DEAL_ID = "recDealAAAAAAAAAA"   # 17 chars — "rec" + 14 alphanumeric
LEAD_ID = "recLeadBBBBBBBBBB"   # 17 chars — "rec" + 14 alphanumeric
assert len(DEAL_ID) == 17 and len(LEAD_ID) == 17


def _owner_identity() -> Identity:
    return Identity(
        user_id="owner1", role=Role.OWNER, display_name="owner1",
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id="owner1",
    )


def _stateful_mocks(deal_fields: dict, lead_fields: dict):
    """Build a get_record_fields/airtable_patch mock pair that share one
    mutable Deal record — a PATCH actually changes what the next
    get_record_fields() read sees, so the writer's own read-back
    verification step observes a real state change (not a fixed fixture).
    Returns (fake_get_record_fields, fake_airtable_patch, deal_state,
    patch_calls)."""
    deal_state = {"fields": dict(deal_fields)}
    patch_calls = []

    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS and record_id == DEAL_ID:
            return dict(deal_state["fields"])
        if table == Tables.LEADS and record_id == LEAD_ID:
            return dict(lead_fields)
        raise RuntimeError("unexpected lookup")

    def fake_airtable_patch(table, record_id, fields, source="unknown"):
        patch_calls.append((table, record_id, dict(fields), source))
        if table == Tables.DEALS and record_id == DEAL_ID:
            deal_state["fields"].update(fields)
            return True
        return False

    return fake_get_record_fields, fake_airtable_patch, deal_state, patch_calls


# ══════════════════════════════════════════════════════════════════
# 1. commercial_crm.link_lead_to_deal() — direct unit tests
# ══════════════════════════════════════════════════════════════════

def test_invalid_lead_id_rejected():
    result = commercial_crm.link_lead_to_deal("not-a-record-id", DEAL_ID)
    assert result["ok"] is False


def test_invalid_deal_id_rejected():
    result = commercial_crm.link_lead_to_deal(LEAD_ID, "not-a-record-id")
    assert result["ok"] is False


def test_deal_not_found():
    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS:
            raise RuntimeError("404")
        return {LeadFields.DOMAIN: "general"}

    with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
         patch("commercial_crm.airtable_patch") as mock_patch:
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
    assert result["ok"] is False
    assert not mock_patch.called


def test_lead_not_found():
    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS:
            return {DealFields.DOMAIN: "general"}
        raise RuntimeError("404")

    with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
         patch("commercial_crm.airtable_patch") as mock_patch:
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
    assert result["ok"] is False
    assert not mock_patch.called


def test_domain_mismatch_blocks_link():
    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS:
            return {DealFields.DOMAIN: "finance"}
        return {LeadFields.DOMAIN: "real_estate"}

    with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
         patch("commercial_crm.airtable_patch") as mock_patch:
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
    assert result["ok"] is False
    assert not mock_patch.called


def test_matching_domain_allows_link():
    fake_get, fake_patch, _, calls = _stateful_mocks(
        {DealFields.DOMAIN: "finance"}, {LeadFields.DOMAIN: "finance"},
    )
    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch):
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
    assert result["ok"] is True
    assert len(calls) == 1


def test_empty_domain_on_either_side_does_not_block():
    """A missing/blank domain on either record is not a claim of mismatch —
    only two actually-populated, differing domains block the link."""
    fake_get, fake_patch, _, calls = _stateful_mocks(
        {DealFields.DOMAIN: ""}, {LeadFields.DOMAIN: "finance"},
    )
    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch):
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
    assert result["ok"] is True
    assert len(calls) == 1


def test_happy_path_links_and_reads_back_to_verify():
    fake_get, fake_patch, _, calls = _stateful_mocks(
        {DealFields.DOMAIN: "general"}, {LeadFields.DOMAIN: "general"},
    )
    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch):
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID, source="test_harness")

    assert result["ok"] is True
    assert result["external_id"] == DEAL_ID
    assert len(calls) == 1
    table, record_id, fields, source = calls[0]
    assert table == Tables.DEALS
    assert record_id == DEAL_ID
    assert fields == {DealFields.LINKED_LEADS: [LEAD_ID]}
    assert source == "test_harness"


def test_never_creates_a_new_deal():
    fake_get, fake_patch, _, _calls = _stateful_mocks(
        {DealFields.DOMAIN: "general"}, {LeadFields.DOMAIN: "general"},
    )
    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch), \
         patch("commercial_crm.airtable_create") as mock_create:
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
    assert result["ok"] is True
    assert not mock_create.called


def test_never_touches_origin_lead():
    fake_get, fake_patch, _, calls = _stateful_mocks(
        {DealFields.DOMAIN: "general", DealFields.ORIGIN_LEAD: ["recOtherLeadXXXXX"]},
        {LeadFields.DOMAIN: "general"},
    )
    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch):
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)

    assert result["ok"] is True
    _, _, fields, _ = calls[0]
    assert DealFields.ORIGIN_LEAD not in fields


def test_idempotent_already_linked_is_a_noop_success():
    """Calling with a Lead already present in Linked Leads must not
    duplicate-write and must not error."""
    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS:
            return {DealFields.DOMAIN: "general", DealFields.LINKED_LEADS: [LEAD_ID]}
        return {LeadFields.DOMAIN: "general"}

    with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
         patch("commercial_crm.airtable_patch") as mock_patch:
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)

    assert result["ok"] is True
    assert result["evidence"]["action"] == "already_linked"
    assert not mock_patch.called


def test_idempotent_across_two_calls_stateful():
    """Two direct calls against the SAME simulated Airtable state: the
    first actually links, the second is a verified no-op — proving
    idempotency end to end against one shared mutable record, not just
    against a pre-seeded 'already linked' fixture."""
    deal_state = {"fields": {DealFields.DOMAIN: "general"}}
    lead_state = {"fields": {LeadFields.DOMAIN: "general"}}
    patch_calls = []

    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS and record_id == DEAL_ID:
            return dict(deal_state["fields"])
        if table == Tables.LEADS and record_id == LEAD_ID:
            return dict(lead_state["fields"])
        raise RuntimeError("unexpected lookup")

    def fake_airtable_patch(table, record_id, fields, source="unknown"):
        patch_calls.append((table, record_id, dict(fields)))
        if table == Tables.DEALS and record_id == DEAL_ID:
            deal_state["fields"].update(fields)
            return True
        return False

    with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
         patch("commercial_crm.airtable_patch", side_effect=fake_airtable_patch):
        first = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
        second = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)

    assert first["ok"] is True and first["evidence"]["action"] == "linked"
    assert second["ok"] is True and second["evidence"]["action"] == "already_linked"
    assert len(patch_calls) == 1
    assert deal_state["fields"][DealFields.LINKED_LEADS] == [LEAD_ID]


def test_patch_failure_returns_not_ok():
    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS:
            return {DealFields.DOMAIN: "general"}
        return {LeadFields.DOMAIN: "general"}

    with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
         patch("commercial_crm.airtable_patch", return_value=False):
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
    assert result["ok"] is False


def test_write_not_confirmed_by_readback_returns_not_ok():
    """A 200/ok PATCH response alone must never be trusted — if the
    read-back doesn't actually show the link, this must fail closed, not
    report success on faith."""
    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS:
            # Read-back never reflects the write (simulated stale/failed
            # persistence despite a 200 response).
            return {DealFields.DOMAIN: "general"}
        return {LeadFields.DOMAIN: "general"}

    with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
         patch("commercial_crm.airtable_patch", return_value=True):
        result = commercial_crm.link_lead_to_deal(LEAD_ID, DEAL_ID)
    assert result["ok"] is False


# ══════════════════════════════════════════════════════════════════
# 2. Registry / validator / dispatcher wiring
# ══════════════════════════════════════════════════════════════════

def test_tool_registered_with_correct_policy():
    from tool_registry import _REGISTRY
    meta = _REGISTRY["crm_link_lead_to_deal"]
    assert meta.requires_approval is True
    assert meta.high_risk is True
    assert meta.tenant_scoped is True
    assert meta.blocked_by_emergency is True
    assert meta.model_exposed is False
    assert {"owner", "partner", "manager"}.issubset(meta.roles_allowed)


def test_action_validator_presence_check():
    from action_validator import ActionAllowed, ActionBlocked, validate_action
    assert isinstance(validate_action("crm_link_lead_to_deal", {}), ActionBlocked)
    assert isinstance(validate_action("crm_link_lead_to_deal", {"lead_id": LEAD_ID}), ActionBlocked)
    assert isinstance(
        validate_action("crm_link_lead_to_deal", {"lead_id": LEAD_ID, "deal_id": DEAL_ID}),
        ActionAllowed,
    )


def test_dispatch_without_execution_proof_is_denied():
    """crm_link_lead_to_deal is requires_approval=True/high_risk=True — a
    direct dispatch_tool() call with no execution_context must be refused
    by the same approval-proof gate every other high-risk tool goes
    through (tools/dispatcher.py::_validate_execution_proof)."""
    from tools.dispatcher import dispatch_tool
    result = dispatch_tool(
        "crm_link_lead_to_deal", {"lead_id": LEAD_ID, "deal_id": DEAL_ID}, _owner_identity(),
    )
    assert isinstance(result, dict) and result.get("ok") is False


# ══════════════════════════════════════════════════════════════════
# 3. Real governed path — ActionGateway -> approval callback ->
# tools.dispatcher.dispatch_tool() (the exact path a real approval uses)
# ══════════════════════════════════════════════════════════════════

def test_real_governed_path_links_lead_to_deal():
    import types

    def _stub_bot():
        return types.SimpleNamespace(
            send_message=lambda *a, **k: types.SimpleNamespace(message_id=1),
            delete_message=lambda *a, **k: None,
            answer_callback_query=lambda *a, **k: None,
            edit_message_text=lambda *a, **k: None,
            process_new_updates=lambda updates: None,
        )

    orig_bot = app.bot
    app.bot = _stub_bot()

    import feature_flags
    prod_flags_on = {"FEATURE_ACTION_GATEWAY", "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS"}
    orig_flag_enabled = app._flag_enabled
    orig_ff_is_enabled = feature_flags.is_enabled
    app._flag_enabled = lambda name: name in prod_flags_on
    feature_flags.is_enabled = lambda name: name in prod_flags_on

    try:
        from guards.circuit_breaker import _airtable_breaker
        with _airtable_breaker._lock:
            _airtable_breaker._failures = 0
            _airtable_breaker._opened = 0.0

        from core.action_gateway import action_gateway as real_gw
        identity = _owner_identity()

        fake_get_record_fields, fake_airtable_patch, _deal_state, patch_calls = _stateful_mocks(
            {DealFields.DOMAIN: "general"}, {LeadFields.DOMAIN: "general"},
        )

        with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
             patch("commercial_crm.airtable_patch", side_effect=fake_airtable_patch), \
             patch("commercial_crm.airtable_create") as mock_create:

            propose = real_gw.propose_action(
                tenant_id="boss_hq", canonical_user_id=identity.memory_key,
                tool_name="crm_link_lead_to_deal",
                tool_inputs={"lead_id": LEAD_ID, "deal_id": DEAL_ID},
                origin_channel="telegram", origin_chat_id="owner1",
                requires_approval=True, identity=identity, trusted_source="test_harness",
            )
            assert propose.ok

            with patch.object(app, "resolve_identity", return_value=identity):
                cq = types.SimpleNamespace(
                    data=f"approve:{propose.contract_id}:{propose.contract_id}",
                    id="cbq-lead-deal-link-test",
                    from_user=types.SimpleNamespace(id="owner1", first_name="T"),
                    message=types.SimpleNamespace(chat=types.SimpleNamespace(id="owner1"), message_id=1),
                )
                app._handle_approval_callback_impl(cq)

        contract = real_gw.find_contract(propose.contract_id)
        assert contract is not None and contract.status in ("completed", "executed")
        assert not mock_create.called, "must never create a new Deal"
        assert len(patch_calls) == 1
        table, record_id, fields, source = patch_calls[0]
        assert table == Tables.DEALS
        assert record_id == DEAL_ID
        assert fields == {DealFields.LINKED_LEADS: [LEAD_ID]}
        assert DealFields.ORIGIN_LEAD not in fields
    finally:
        app.bot = orig_bot
        app._flag_enabled = orig_flag_enabled
        feature_flags.is_enabled = orig_ff_is_enabled
