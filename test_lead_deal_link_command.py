"""בדיקות רגרסיה — /תקדםליד (LEAD-DEAL-ASSOCIATION Model B UX entry point).

מכסה: happy path, ליד/עסקה דו-משמעיים, קישור כפול (אידמפוטנטי), אי-התאמת
דומיין, ביטול אישור, כשל ביצוע, Origin Lead לא נוגע, ותגובה סופית אחת בדיוק.

pytest-native (assert, not a print/chk scaffold) — matches CI's `^def test_`
auto-detect convention (see test_lead_to_deal_origin_link.py's own docstring
for why a print-only helper would false-pass here).
"""

from __future__ import annotations

import os
import types
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-lead-deal-link-cmd-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:LEAD_DEAL_LINK_CMD_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patLeadDealLinkCmdTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appLeadDealLinkCmdTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-lead-deal-link-cmd-webhook-secret")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import app  # noqa: E402
from airtable_schema import DealFields, LeadFields, Tables  # noqa: E402
from identity import Identity, Role  # noqa: E402

import tc8_test_repo_stub  # noqa: E402
tc8_test_repo_stub.patch_turn_state_repository()

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

DEAL_ID = "recDealCCCCCCCCCC"   # 17 chars
LEAD_ID = "recLeadDDDDDDDDDD"   # 17 chars
# Distinct record-id pairs per real-ActionGateway test below — the gateway's
# own short-term duplicate-fingerprint guard would otherwise block a second
# propose_action() call for the same (tenant, user, tool, lead_id, deal_id)
# tuple across tests in this same process, unrelated to what each test
# actually wants to exercise.
DEAL_ID2, LEAD_ID2 = "recDeal2222222222", "recLead2222222222"
DEAL_ID3, LEAD_ID3 = "recDeal3333333333", "recLead3333333333"
DEAL_ID4, LEAD_ID4 = "recDeal4444444444", "recLead4444444444"
DEAL_ID5, LEAD_ID5 = "recDeal5555555555", "recLead5555555555"
DEAL_ID6, LEAD_ID6 = "recDeal6666666666", "recLead6666666666"
for _id in (DEAL_ID, LEAD_ID, DEAL_ID2, LEAD_ID2, DEAL_ID3, LEAD_ID3,
            DEAL_ID4, LEAD_ID4, DEAL_ID5, LEAD_ID5, DEAL_ID6, LEAD_ID6):
    assert len(_id) == 17, _id


def _owner_identity() -> Identity:
    return Identity(
        user_id="owner1", role=Role.OWNER, display_name="owner1",
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id="owner1",
    )


def _lead_record(rec_id: str, name: str, domain: str = "general") -> dict:
    return {"id": rec_id, "fields": {LeadFields.NAME: name, LeadFields.DOMAIN: domain}}


def _deal_record(rec_id: str, name: str, domain: str = "general") -> dict:
    return {"id": rec_id, "fields": {DealFields.NAME: name, DealFields.DOMAIN: domain}}


def _stateful_writer_mocks(lead_id=LEAD_ID, deal_id=DEAL_ID, deal_domain="general", lead_domain="general"):
    """Same stateful get_record_fields/airtable_patch pair as
    test_crm_link_lead_to_deal.py's _stateful_mocks() — a PATCH actually
    changes what the next read sees, so the writer's own read-back
    verification (and this UX layer's idempotency) is exercised for real."""
    deal_state = {"fields": {DealFields.DOMAIN: deal_domain}}
    patch_calls = []

    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS and record_id == deal_id:
            return dict(deal_state["fields"])
        if table == Tables.LEADS and record_id == lead_id:
            return {LeadFields.DOMAIN: lead_domain}
        raise RuntimeError("unexpected lookup")

    def fake_airtable_patch(table, record_id, fields, source="unknown"):
        patch_calls.append((table, record_id, dict(fields), source))
        if table == Tables.DEALS and record_id == deal_id:
            deal_state["fields"].update(fields)
            return True
        return False

    return fake_get_record_fields, fake_airtable_patch, deal_state, patch_calls


# ══════════════════════════════════════════════════════════════════
# 1. lead_deal_link.py — parser unit tests (fast, no I/O)
# ══════════════════════════════════════════════════════════════════

def test_direct_form_parses_lead_and_deal_names():
    from lead_deal_link import parse_direct_link_text
    result = parse_direct_link_text("קדם את משה כהן לעסקת גיוס עובדים לאבי")
    assert result == ("משה כהן", "גיוס עובדים לאבי")


def test_bare_trigger_recognized_and_direct_form_is_not_a_bare_trigger():
    from lead_deal_link import is_promote_lead_trigger
    assert is_promote_lead_trigger("תקדם ליד")
    assert is_promote_lead_trigger("לתקדם ליד")
    assert not is_promote_lead_trigger("קדם את משה כהן לעסקת גיוס עובדים לאבי")
    assert not is_promote_lead_trigger("שלום, מה שלומך?")


# ══════════════════════════════════════════════════════════════════
# 2. Direct NL form → _resolve_and_queue_lead_deal_link()
# ══════════════════════════════════════════════════════════════════

def test_happy_path_direct_form_links_via_real_governed_path():
    """"קדם את X לעסקת Y" resolves both, queues crm_link_lead_to_deal
    through the REAL ActionGateway (app._queue_approval_detailed(), no
    mocking of the gateway plumbing itself), and approving it executes the
    real writer — the exact path a real Telegram approval uses."""
    from guards.circuit_breaker import _airtable_breaker
    with _airtable_breaker._lock:
        _airtable_breaker._failures = 0
        _airtable_breaker._opened = 0.0

    from core.action_gateway import action_gateway as real_gw
    identity = _owner_identity()
    fake_get, fake_patch, deal_state, patch_calls = _stateful_writer_mocks()

    orig_bot = app.bot
    app.bot = types.SimpleNamespace(
        send_message=lambda *a, **k: types.SimpleNamespace(message_id=1),
        delete_message=lambda *a, **k: None,
        answer_callback_query=lambda *a, **k: None,
        edit_message_text=lambda *a, **k: None,
        process_new_updates=lambda updates: None,
    )
    orig_flag_enabled = app._flag_enabled
    prod_flags_on = {"FEATURE_ACTION_GATEWAY", "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS"}
    app._flag_enabled = lambda name: name in prod_flags_on
    import feature_flags
    orig_ff = feature_flags.is_enabled
    feature_flags.is_enabled = lambda name: name in prod_flags_on

    try:
        with patch("lead_deal_link.resolve_lead_by_query",
                   return_value=(_lead_record(LEAD_ID, "משה כהן"), "")), \
             patch("lead_deal_link.resolve_deal_by_query",
                   return_value=(_deal_record(DEAL_ID, "גיוס עובדים לאבי"), "")), \
             patch("commercial_crm.get_record_fields", side_effect=fake_get), \
             patch("commercial_crm.airtable_patch", side_effect=fake_patch), \
             patch("commercial_crm.airtable_create") as mock_create, \
             patch.object(app, "resolve_identity", return_value=identity):
            # app.resolve_identity(channel, chat_id) is what _queue_approval_
            # detailed_impl() actually uses to resolve the contract's stored
            # identity (NOT the `identity` object passed down the call chain
            # for the enforce() pre-check) — patched here so the fabricated
            # chat_id "owner1" resolves to a real owner for both proposal
            # and approval, matching how a real registered Telegram chat_id
            # would resolve in production.
            reply = app._resolve_and_queue_lead_deal_link(
                "משה כהן", "גיוס עובדים לאבי", "owner1", "telegram",
                "קדם את משה כהן לעסקת גיוס עובדים לאבי", identity,
            )
            assert isinstance(reply, str) and reply
            assert not mock_create.called

            fp = real_gw.compute_business_fingerprint(
                "boss_hq", identity.memory_key, "crm_link_lead_to_deal",
                real_gw.normalize_payload({"lead_id": LEAD_ID, "deal_id": DEAL_ID}),
            )
            contract = real_gw._ledger.find_by_fingerprint(fp)
            assert contract is not None and contract.status == "pending"

            real_gw.approve(contract.contract_id, identity.memory_key, "owner")
            contract = real_gw.find_contract(contract.contract_id)
            assert contract.status in ("completed", "executed")
    finally:
        app.bot = orig_bot
        app._flag_enabled = orig_flag_enabled
        feature_flags.is_enabled = orig_ff

    assert len(patch_calls) == 1
    assert patch_calls[0][2] == {DealFields.LINKED_LEADS: [LEAD_ID]}
    assert DealFields.ORIGIN_LEAD not in patch_calls[0][2]


def test_ambiguous_lead_returns_clarification_no_contract_proposed():
    identity = _owner_identity()
    with patch("lead_deal_link.resolve_lead_by_query",
               return_value=(None, "⚠️ נמצאו כמה לידים תואמים: משה כהן, משה לוי.")), \
         patch("lead_deal_link.resolve_deal_by_query") as mock_resolve_deal, \
         patch.object(app, "_queue_deterministic_link_lead_to_deal") as mock_queue:
        reply = app._resolve_and_queue_lead_deal_link(
            "משה", "גיוס עובדים לאבי", "owner1", "telegram", "קדם את משה לעסקת גיוס עובדים לאבי",
            identity,
        )
    assert "כמה" in reply or "תואמים" in reply
    assert not mock_resolve_deal.called
    assert not mock_queue.called


def test_ambiguous_deal_returns_clarification_no_contract_proposed():
    identity = _owner_identity()
    with patch("lead_deal_link.resolve_lead_by_query",
               return_value=(_lead_record(LEAD_ID, "משה כהן"), "")), \
         patch("lead_deal_link.resolve_deal_by_query",
               return_value=(None, "⚠️ נמצאו כמה עסקאות תואמות: עסקה א, עסקה ב.")), \
         patch.object(app, "_queue_deterministic_link_lead_to_deal") as mock_queue:
        reply = app._resolve_and_queue_lead_deal_link(
            "משה כהן", "עסק", "owner1", "telegram", "קדם את משה כהן לעסקת עסק", identity,
        )
    assert "כמה" in reply or "תואמות" in reply
    assert not mock_queue.called


# ══════════════════════════════════════════════════════════════════
# 3. Guided flow → _handle_lead_deal_link_reply()
# ══════════════════════════════════════════════════════════════════

def test_guided_flow_awaiting_lead_advances_to_awaiting_deal():
    identity = _owner_identity()
    captured = {}
    with patch("lead_deal_link.resolve_lead_by_query",
               return_value=(_lead_record(LEAD_ID, "משה כהן"), "")), \
         patch("session_store.lead_sessions.set_lead_deal_link",
               side_effect=lambda *a, **k: captured.setdefault("state", a[1])):
        reply = app._handle_lead_deal_link_reply(
            {"step": "awaiting_lead"}, "owner1", "telegram", "משה כהן", identity,
        )
    assert "עסק" in reply
    assert captured["state"]["step"] == "awaiting_deal"
    assert captured["state"]["lead_id"] == LEAD_ID


def test_guided_flow_awaiting_deal_queues_link_and_clears_state():
    identity = _owner_identity()
    cleared = {"called": False}
    with patch("lead_deal_link.resolve_deal_by_query",
               return_value=(_deal_record(DEAL_ID, "גיוס עובדים לאבי"), "")), \
         patch("session_store.lead_sessions.clear_lead_deal_link",
               side_effect=lambda *a, **k: cleared.__setitem__("called", True)), \
         patch.object(app, "_queue_deterministic_link_lead_to_deal",
                      return_value="✅ הליד קושר לעסקה.") as mock_queue:
        reply = app._handle_lead_deal_link_reply(
            {"step": "awaiting_deal", "lead_id": LEAD_ID, "lead_name": "משה כהן"},
            "owner1", "telegram", "גיוס עובדים לאבי", identity,
        )
    assert cleared["called"]
    mock_queue.assert_called_once_with(
        LEAD_ID, DEAL_ID, "owner1", "telegram", "גיוס עובדים לאבי", identity, out_meta=None,
    )
    assert reply == "✅ הליד קושר לעסקה."


def test_guided_flow_cancel_word_clears_state_without_resolving_anything():
    identity = _owner_identity()
    cleared = {"called": False}
    with patch("session_store.lead_sessions.clear_lead_deal_link",
               side_effect=lambda *a, **k: cleared.__setitem__("called", True)), \
         patch("lead_deal_link.resolve_lead_by_query") as mock_resolve:
        reply = app._handle_lead_deal_link_reply(
            {"step": "awaiting_lead"}, "owner1", "telegram", "בטל", identity,
        )
    assert cleared["called"]
    assert not mock_resolve.called
    assert "בוטל" in reply


def test_guided_flow_produces_exactly_one_reply_per_turn():
    """_handle_lead_deal_link_reply() and _resolve_and_queue_lead_deal_link()
    both return a single str — never a tuple/list of multiple messages, and
    never call bot.send_message themselves (the caller sends exactly one
    reply) — Single-Speaker structural guarantee for this new entry point."""
    identity = _owner_identity()
    with patch("lead_deal_link.resolve_lead_by_query",
               return_value=(_lead_record(LEAD_ID, "משה כהן"), "")), \
         patch("session_store.lead_sessions.set_lead_deal_link"), \
         patch.object(app.bot, "send_message") as mock_send:
        reply = app._handle_lead_deal_link_reply(
            {"step": "awaiting_lead"}, "owner1", "telegram", "משה כהן", identity,
        )
    assert isinstance(reply, str)
    assert not mock_send.called  # the handler itself never sends — caller does, once


# ══════════════════════════════════════════════════════════════════
# 4. Real governed path — duplicate link, domain mismatch, approval
#    cancel, execution failure, Origin Lead untouched
# ══════════════════════════════════════════════════════════════════

def _propose_link_contract(real_gw, identity, lead_id=LEAD_ID, deal_id=DEAL_ID):
    return real_gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=identity.memory_key,
        tool_name="crm_link_lead_to_deal",
        tool_inputs={"lead_id": lead_id, "deal_id": deal_id},
        origin_channel="telegram", origin_chat_id="owner1",
        requires_approval=True, identity=identity, trusted_source="test_harness",
    )


def test_duplicate_link_is_idempotent_through_real_governed_path():
    from guards.circuit_breaker import _airtable_breaker
    with _airtable_breaker._lock:
        _airtable_breaker._failures = 0
        _airtable_breaker._opened = 0.0
    from core.action_gateway import action_gateway as real_gw
    identity = _owner_identity()
    fake_get, fake_patch, deal_state, patch_calls = _stateful_writer_mocks(
        lead_id=LEAD_ID2, deal_id=DEAL_ID2,
    )

    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch):
        first = _propose_link_contract(real_gw, identity, lead_id=LEAD_ID2, deal_id=DEAL_ID2)
        assert first.ok
        real_gw.approve(first.contract_id, identity.memory_key, "owner")
        first_contract = real_gw.find_contract(first.contract_id)
        assert first_contract.status in ("completed", "executed")

        # Second request for the SAME lead/deal pair — a fresh contract
        # (new fingerprint call), but the writer itself must be a no-op.
        second = _propose_link_contract(real_gw, identity, lead_id=LEAD_ID2, deal_id=DEAL_ID2)
        if second.ok:
            real_gw.approve(second.contract_id, identity.memory_key, "owner")
            second_contract = real_gw.find_contract(second.contract_id)
            assert second_contract.status in ("completed", "executed")

    assert len(patch_calls) == 1, "the writer must only ever patch once for the same pair"
    assert deal_state["fields"][DealFields.LINKED_LEADS] == [LEAD_ID2]


def test_domain_mismatch_surfaces_failure_not_success():
    from guards.circuit_breaker import _airtable_breaker
    with _airtable_breaker._lock:
        _airtable_breaker._failures = 0
        _airtable_breaker._opened = 0.0
    from core.action_gateway import action_gateway as real_gw
    identity = _owner_identity()
    fake_get, fake_patch, _deal_state, patch_calls = _stateful_writer_mocks(
        lead_id=LEAD_ID3, deal_id=DEAL_ID3, deal_domain="finance", lead_domain="real_estate",
    )

    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch):
        propose = _propose_link_contract(real_gw, identity, lead_id=LEAD_ID3, deal_id=DEAL_ID3)
        assert propose.ok
        approve_msg = real_gw.approve(propose.contract_id, identity.memory_key, "owner")
        contract = real_gw.find_contract(propose.contract_id)

    assert not patch_calls, "a domain mismatch must never reach the writer's PATCH"
    assert contract.status not in ("completed", "executed")
    assert "✅" not in approve_msg


def test_approval_cancel_no_write_happens():
    from guards.circuit_breaker import _airtable_breaker
    with _airtable_breaker._lock:
        _airtable_breaker._failures = 0
        _airtable_breaker._opened = 0.0
    from core.action_gateway import action_gateway as real_gw
    identity = _owner_identity()
    fake_get, fake_patch, _deal_state, patch_calls = _stateful_writer_mocks(
        lead_id=LEAD_ID4, deal_id=DEAL_ID4,
    )

    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch):
        propose = _propose_link_contract(real_gw, identity, lead_id=LEAD_ID4, deal_id=DEAL_ID4)
        assert propose.ok
        real_gw.reject(propose.contract_id, identity.memory_key)
        contract = real_gw.find_contract(propose.contract_id)

    assert contract.status == "rejected"
    assert not patch_calls, "a rejected approval must never reach the writer"


def test_execution_failure_never_claims_success():
    from guards.circuit_breaker import _airtable_breaker
    with _airtable_breaker._lock:
        _airtable_breaker._failures = 0
        _airtable_breaker._opened = 0.0
    from core.action_gateway import action_gateway as real_gw
    identity = _owner_identity()

    def fake_get_record_fields(table, record_id):
        if table == Tables.DEALS:
            return {DealFields.DOMAIN: "general"}
        return {LeadFields.DOMAIN: "general"}

    with patch("commercial_crm.get_record_fields", side_effect=fake_get_record_fields), \
         patch("commercial_crm.airtable_patch", return_value=False):
        propose = _propose_link_contract(real_gw, identity, lead_id=LEAD_ID5, deal_id=DEAL_ID5)
        assert propose.ok
        approve_msg = real_gw.approve(propose.contract_id, identity.memory_key, "owner")
        contract = real_gw.find_contract(propose.contract_id)

    assert contract.status not in ("completed", "executed")
    assert "✅" not in approve_msg


def test_origin_lead_never_touched_across_full_flow():
    from guards.circuit_breaker import _airtable_breaker
    with _airtable_breaker._lock:
        _airtable_breaker._failures = 0
        _airtable_breaker._opened = 0.0
    from core.action_gateway import action_gateway as real_gw
    identity = _owner_identity()
    deal_state = {"fields": {DealFields.DOMAIN: "general",
                              DealFields.ORIGIN_LEAD: ["recOtherLeadXXXXX"]}}
    patch_calls = []

    def fake_get(table, record_id):
        if table == Tables.DEALS and record_id == DEAL_ID6:
            return dict(deal_state["fields"])
        if table == Tables.LEADS and record_id == LEAD_ID6:
            return {LeadFields.DOMAIN: "general"}
        raise RuntimeError("unexpected lookup")

    def fake_patch(table, record_id, fields, source="unknown"):
        patch_calls.append((table, record_id, dict(fields), source))
        deal_state["fields"].update(fields)
        return True

    with patch("commercial_crm.get_record_fields", side_effect=fake_get), \
         patch("commercial_crm.airtable_patch", side_effect=fake_patch), \
         patch("commercial_crm.airtable_create") as mock_create:
        propose = _propose_link_contract(real_gw, identity, lead_id=LEAD_ID6, deal_id=DEAL_ID6)
        assert propose.ok
        real_gw.approve(propose.contract_id, identity.memory_key, "owner")
        contract = real_gw.find_contract(propose.contract_id)

    assert contract.status in ("completed", "executed")
    assert not mock_create.called
    assert len(patch_calls) == 1
    assert DealFields.ORIGIN_LEAD not in patch_calls[0][2]
    assert deal_state["fields"][DealFields.ORIGIN_LEAD] == ["recOtherLeadXXXXX"]
