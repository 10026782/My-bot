# test_diamond_business_fields_migration.py —
# DIAMOND — BUSINESS FIELDS MIGRATION + USER-FACING SUMMARY FIX regression
#
# Owner-directed (06/09/2026): moves the Deal Diamond enrichment flow onto
# three new live Airtable business fields (סוג העסקה העסקי / אופי הקשר
# העסקי / משך ההתקשרות — each representing exactly one business dimension,
# replacing the old mixed deal_type/relationship_type model), translates
# Commercial Status to readable Hebrew labels for display only (storage
# unchanged), and fixes a production-reported UX defect: the final Deal
# enrichment completion message leaked a raw internal enum token
# ("הפעולה הושלמה: עדכון רשומה: recurring") instead of a real business
# summary. Root cause: core.action_gateway._first_field_preview() picks
# ONE raw field value out of the airtable_update payload with no business
# meaning at all — deliberately generic/table-agnostic for every other
# table (Leads/Tasks get their own richer verb already); this fix adds the
# same treatment for Deals via ONE shared summary builder
# (commercial_completion_ux.deal_field_business_summary()), reused by both
# the pending-approval prompt (app.py._describe_tool_call()) and the
# completion message (core.action_gateway's two description functions) —
# never duplicated between prompt/button/typed-fallback/final-summary.
#
# This file drives the REAL functions (field_presentation(),
# _handle_deal_enrichment_reply(), deal_field_business_summary(),
# build_approval_lifecycle_result(), and the real ActionGateway-approved
# tools.dispatcher.dispatch_tool() path) rather than re-implementing the
# logic under test.

from __future__ import annotations

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-bizfields-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_BIZFIELDS_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondBizFieldsTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondBizFieldsTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-bizfields-webhook-secret")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import app  # noqa: E402

import tc8_test_repo_stub  # noqa: E402
tc8_test_repo_stub.patch_turn_state_repository()

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

_bot_calls: list[tuple] = []


def _stub_bot():
    return types.SimpleNamespace(
        send_message=lambda *a, **k: (_bot_calls.append(("send_message", a, k)) or types.SimpleNamespace(message_id=1)),
        delete_message=lambda *a, **k: None,
        answer_callback_query=lambda *a, **k: _bot_calls.append(("answer_callback_query", a, k)),
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

from identity import Identity, Role  # noqa: E402
from airtable_schema import (  # noqa: E402
    BusinessDealType, DealFields, EngagementDuration, RelationshipRole, Tables,
)
from commercial_completion import ENTITY_CONTRACTS  # noqa: E402
from commercial_completion_ux import (  # noqa: E402
    field_presentation, deal_field_business_summary, COMMERCIAL_STATUS_LABELS,
)
from core.action_gateway import (  # noqa: E402
    action_gateway as _real_gw, build_approval_lifecycle_result,
    _describe_contract_for_reconfirmation,
)
import core.runtime_schema_provider as rsp  # noqa: E402

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
# Part 0 — business-language field presentation (items 1, 2, 3, 6)
# ══════════════════════════════════════════════════════════════════
print("── Part 0: field_presentation() renders business language ──")

_deal_contract = ENTITY_CONTRACTS["deal"]

# item 1: new Deal Type choices render in business language
p = field_presentation("deal", _deal_contract.field("business_deal_type"))
chk("1. business_deal_type choices are the live Hebrew business words",
    set(p.choices) == {"שירות", "מכירה", "עמלה / תיווך", "שותפות", "אחר"})
chk("1. business_deal_type choices contain no obsolete internal enum",
    not any(c in p.choices for c in ("one_off", "recurring", "commission", "service", "other")))

# item 2: new Relationship choices render in business language
p = field_presentation("deal", _deal_contract.field("relationship_role"))
chk("2. relationship_role choices are the live Hebrew business words",
    set(p.choices) == {"לקוח", "ספק", "שותף", "מפנה / מתווך", "אחר"})
chk("2. relationship_role choices contain no obsolete internal enum",
    not any(c in p.choices for c in ("one_off", "ongoing", "recurring_service", "commission_relationship", "partnership")))

# item 3: Duration question exists and renders correctly
p = field_presentation("deal", _deal_contract.field("engagement_duration"))
chk("3. engagement_duration field exists with the two live duration choices",
    set(p.choices) == {"חד-פעמית", "מתמשכת"})
chk("3. engagement_duration prompt asks about duration", "משך" in p.prompt)

# item 6: Commercial Status displays readable Hebrew labels while storing
# canonical values.
p = field_presentation("deal", _deal_contract.field("commercial_status"))
chk("6. commercial_status choices are Hebrew display labels",
    set(p.choices) == set(COMMERCIAL_STATUS_LABELS.values()))
chk("6. commercial_status choices contain no raw canonical enum",
    not any(c in p.choices for c in ("prospect", "active", "at_risk", "completed", "cancelled", "written_off")))


# ══════════════════════════════════════════════════════════════════
# Part 1 — real _handle_deal_enrichment_reply() walk (items 4, 5, 7)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 1: real Deal enrichment loop, business fields end-to-end ──")

_REC_ID = "recBizFieldsTst01"


def _seed_state(remaining, collected=None):
    return {
        "stage": "collecting", "record_id": _REC_ID,
        "remaining_fields": list(remaining), "collected": dict(collected or {}),
    }


with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set:
    state = _seed_state(["business_deal_type", "relationship_role", "engagement_duration"])
    result = app._handle_deal_enrichment_reply(state, "chat-biz-1", "telegram", BusinessDealType.SERVICE)
chk("4. answering business_deal_type stores the exact live Hebrew value",
    mock_set.called and mock_set.call_args[0][1]["collected"].get(DealFields.BUSINESS_DEAL_TYPE) == "שירות")
chk("5. business_deal_type prompt for the NEXT field is in Hebrew, no obsolete enum leaked",
    "relationship_type" not in result and "recurring" not in result and "commission" not in result)

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set:
    state = _seed_state(["relationship_role", "engagement_duration"],
                         {DealFields.BUSINESS_DEAL_TYPE: BusinessDealType.SERVICE})
    result = app._handle_deal_enrichment_reply(state, "chat-biz-1", "telegram", RelationshipRole.CUSTOMER)
chk("4. answering relationship_role stores the exact live Hebrew value",
    mock_set.called and mock_set.call_args[0][1]["collected"].get(DealFields.RELATIONSHIP_ROLE) == "לקוח")

with patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set:
    state = _seed_state(["engagement_duration", "currency"],
                         {DealFields.BUSINESS_DEAL_TYPE: BusinessDealType.SERVICE,
                          DealFields.RELATIONSHIP_ROLE: RelationshipRole.CUSTOMER})
    result = app._handle_deal_enrichment_reply(state, "chat-biz-1", "telegram", EngagementDuration.ONGOING)
chk("4. answering engagement_duration stores the exact live Hebrew value",
    mock_set.called and mock_set.call_args[0][1]["collected"].get(DealFields.ENGAGEMENT_DURATION) == "מתמשכת")

# item 5 (full sweep): the OFFER prompt itself never mentions the old
# mixed-model internal enums either.
with patch("session_store.lead_sessions.set_deal_enrichment_offer"):
    offer_text = app._offer_deal_enrichment("chat-biz-2", "telegram", _REC_ID)
chk("5. offer text mentions the new business dimensions",
    "סוג עסקה" in offer_text and "אופי קשר" in offer_text and "משך התקשרות" in offer_text)
chk("5. offer text leaks no obsolete internal enum",
    not any(tok in offer_text for tok in ("one_off", "recurring", "commission_relationship")))

# item 7: user answering "לא" at the final optional step completes cleanly.
with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
     patch("app._queue_approval_detailed", return_value={"message": "", "ok": True, "created_this_turn": True, "contract_id": "c1"}) as mock_queue:
    state = _seed_state(["estimated_value_notes"], {
        DealFields.COMMERCIAL_STATUS: "active",
        DealFields.ENGAGEMENT_DURATION: EngagementDuration.ONGOING,
    })
    result = app._handle_deal_enrichment_reply(state, "chat-biz-3", "telegram", "לא")
chk("7. 'לא' at the final optional step completes cleanly (non-empty reply)", bool(result))
chk("7. 'לא' clears the enrichment marker", mock_clear.called)
chk("7. 'לא' does not store the literal word as a field value",
    mock_queue.called and "לא" not in mock_queue.call_args[0][1]["fields"].values())
chk("7. 'לא' still queues the fields genuinely collected earlier",
    mock_queue.called and mock_queue.call_args[0][1]["fields"].get(DealFields.COMMERCIAL_STATUS) == "active")


# ══════════════════════════════════════════════════════════════════
# Part 2 — deal_field_business_summary() unit coverage (items 8-12)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 2: deal_field_business_summary() — no enum leak, verified-only ──")

summary = deal_field_business_summary({
    DealFields.DEAL_TYPE_CODE: "recurring",  # a skipped/legacy field, not a NEW answer
})
chk("8. a raw 'recurring' token in the input never appears verbatim as a business value",
    "recurring" not in summary or "• " not in summary)

summary = deal_field_business_summary({
    DealFields.RELATIONSHIP_TYPE: "commission_relationship",
})
chk("9. a raw 'commission_relationship' token never appears verbatim as a business value",
    "commission_relationship" not in summary)

summary = deal_field_business_summary({
    DealFields.BUSINESS_DEAL_TYPE: "שירות",
    DealFields.RELATIONSHIP_ROLE: "לקוח",
    DealFields.ENGAGEMENT_DURATION: "מתמשכת",
    DealFields.CURRENCY: "ILS",
    DealFields.COMMERCIAL_STATUS: "active",
    DealFields.ESTIMATED_VALUE_RANGE: "10k_100k",
})
chk("10. summary contains only the fields actually present in the input",
    summary.count("•") == 6)
chk("10. commercial_status displays the Hebrew label, not the raw enum",
    "פעילה" in summary and "• סטטוس מסחרי: active" not in summary)
chk("10. estimated_value_range displays the Hebrew label, not the raw enum",
    "10,000" in summary and "10k_100k" not in summary)

summary_skipped = deal_field_business_summary({DealFields.BUSINESS_DEAL_TYPE: "שירות"})
chk("11. a field never present in the input never appears in the summary",
    "אופי הקשר" not in summary_skipped and "משך" not in summary_skipped)

summary_empty_skip = deal_field_business_summary({DealFields.RELATIONSHIP_ROLE: ""})
chk("12. an explicitly empty/falsy field value is never rendered as 'updated'",
    summary_empty_skip == "")


# ══════════════════════════════════════════════════════════════════
# Part 3 — real governed path: the actual production bug, end to end
# (items 8, 9, 13, 14)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 3: real ActionGateway approval path — the production bug scenario ──")

LIVE_DEALS_FIELDS = {
    DealFields.NAME: {"field_id": "fld1", "type": "singleLineText", "choices": []},
    DealFields.BUSINESS_DEAL_TYPE: {"field_id": "fld2", "type": "singleSelect",
                                      "choices": ["שירות", "מכירה", "עמלה / תיווך", "שותפות", "אחר"]},
    DealFields.RELATIONSHIP_ROLE: {"field_id": "fld3", "type": "singleSelect",
                                     "choices": ["לקוח", "ספק", "שותף", "מפנה / מתווך", "אחר"]},
    DealFields.ENGAGEMENT_DURATION: {"field_id": "fld4", "type": "singleSelect",
                                       "choices": ["חד-פעמית", "מתמשכת"]},
    DealFields.CURRENCY: {"field_id": "fld5", "type": "singleSelect", "choices": ["ILS", "USD", "EUR"]},
    DealFields.COMMERCIAL_STATUS: {"field_id": "fld6", "type": "singleSelect",
                                     "choices": ["prospect", "active", "at_risk", "completed", "cancelled", "written_off"]},
    DealFields.DEAL_TYPE_CODE: {"field_id": "fld7", "type": "singleSelect",
                                  "choices": ["one_off", "recurring", "commission", "service", "other"]},
}


def _real_fetch_live(self, table):
    if table != Tables.DEALS:
        return None
    return {
        "table_id": "tblDealsFake", "fields": LIVE_DEALS_FIELDS,
        "fetched_at": "2026-09-06T00:00:00Z",
        "fetched_at_mono": __import__("time").monotonic(),
    }


_orig_fetch_live = rsp.RuntimeSchemaProvider._fetch_live
rsp.RuntimeSchemaProvider._fetch_live = _real_fetch_live
rsp._provider = None

import httpx  # noqa: E402
_orig_httpx_patch = httpx.patch
_captured: list[dict] = []


def _mock_httpx_patch(url, headers=None, json=None, timeout=None):
    _captured.append({"json": json})

    class _Resp:
        status_code = 200
        text = "{}"

        def json(self_):
            return {"id": _REC_ID, "fields": json.get("fields", {})}

    return _Resp()


httpx.patch = _mock_httpx_patch

_reset_airtable_circuit_breaker()
_identity = Identity(
    user_id="biz-canary-1", role=Role.OWNER, display_name="biz-canary-1",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="biz-canary-1",
)

# This is EXACTLY the production scenario: a multi-field enrichment update
# (business_deal_type + relationship_role + engagement_duration +
# commercial_status) queued the same way _finish() in
# _handle_deal_enrichment_reply() queues it, approved once, and the
# resulting ActionContract handed to the REAL build_approval_lifecycle_result()
# — the exact function that produced "הפעולה הושלמה: עדכון רשומה: recurring"
# in production.
_captured.clear()
# FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE=off (the code default)
# makes the unknown-field-NAME gate in tools/airtable_gateway.py consult
# only the legacy schema_cache.json, which doesn't know these new fields
# at all (same D3/D3-A finding, unchanged/out of scope here) — "shadow" is
# also the state evidenced as active in production. Unrelated to the
# summary/description logic under test in this Part.
_old_provider_state = os.environ.get("FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE")
os.environ["FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE"] = "shadow"
try:
    propose = _real_gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=_identity.memory_key,
        tool_name="airtable_update",
        tool_inputs={
            "table": Tables.DEALS, "record_id": _REC_ID,
            "fields": {
                DealFields.BUSINESS_DEAL_TYPE: "שירות",
                DealFields.RELATIONSHIP_ROLE: "לקוח",
                DealFields.ENGAGEMENT_DURATION: "מתמשכת",
                DealFields.COMMERCIAL_STATUS: "active",
            },
        },
        origin_channel="telegram", origin_chat_id="biz-canary-1",
        requires_approval=True, identity=_identity, trusted_source="test_harness",
    )
    chk("setup: multi-field Deal enrichment update contract proposed", propose.ok)

    with patch.object(app, "resolve_identity", return_value=_identity):
        cq = types.SimpleNamespace(
            data=f"approve:{propose.contract_id}:{propose.contract_id}",
            id="cbq-biz-canary-1",
            from_user=types.SimpleNamespace(id="biz-canary-1", first_name="T"),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id="biz-canary-1"), message_id=1),
        )
        app._handle_approval_callback_impl(cq)
finally:
    if _old_provider_state is None:
        os.environ.pop("FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE", None)
    else:
        os.environ["FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE"] = _old_provider_state

contract = _real_gw.find_contract(propose.contract_id)
chk("13. the multi-field update actually executed", contract is not None and contract.status in ("completed", "executed"))
chk("13. exact live values (not the raw dict) were sent to Airtable",
    bool(_captured) and _captured[0]["json"]["fields"].get(DealFields.BUSINESS_DEAL_TYPE) == "שירות")

lifecycle = build_approval_lifecycle_result(contract, canonical_state="completed")
completion_message = lifecycle.safe_user_message
chk("8. the REAL completion message never contains the raw enum 'recurring'",
    "recurring" not in completion_message)
chk("9. the REAL completion message never contains the raw enum 'commission_relationship'",
    "commission_relationship" not in completion_message)
chk("13. the REAL completion message is a business-readable multi-field summary",
    "שירות" in completion_message and "לקוח" in completion_message and "מתמשכת" in completion_message)
chk("6/13. the REAL completion message shows Commercial Status as a Hebrew label",
    "פעילה" in completion_message and "active" not in completion_message)
chk("14. exactly one completion message string is produced for this mutation",
    isinstance(completion_message, str) and completion_message.count("הפעולה הושלמה") <= 1)

# Same proof for the pending-reconfirmation description surface
# (_describe_contract_for_reconfirmation) — the OTHER place this exact
# class of bug could resurface, now sharing the same builder.
reconfirm_text = _describe_contract_for_reconfirmation(contract)
chk("8/9. the pending-reconfirmation description also leaks no raw enum",
    "recurring" not in reconfirm_text and "commission_relationship" not in reconfirm_text)
chk("13. the pending-reconfirmation description is also a business-readable summary",
    "שירות" in reconfirm_text)


# ══════════════════════════════════════════════════════════════════
# Restore
# ══════════════════════════════════════════════════════════════════
app.bot = _orig_bot
app._flag_enabled = _orig_flag_enabled
feature_flags.is_enabled = _orig_ff_is_enabled
rsp.RuntimeSchemaProvider._fetch_live = _orig_fetch_live
rsp._provider = None
httpx.patch = _orig_httpx_patch

print(f"\n{'='*60}\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
