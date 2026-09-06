# test_diamond_d3_final_select_resolver.py —
# DIAMOND D3 FINAL: hardened core.runtime_schema_provider.resolve_live_select_value()
# as the exclusive live-select storage resolver for the Diamond Deal path.
#
# Root finding (D3 normalization audit, verified against current main before
# editing): resolve_live_select_value()'s matching only handled case and
# leading/trailing whitespace — a canonical business slug like "real_estate"
# never matched a live Airtable choice like "Real Estate" (underscore vs
# space). A sibling module (cmd_update.py, a different table) had already
# solved this exact normalization independently; this file hardens the ONE
# function the Diamond path actually shares (create_deal, the generic Deal
# update redirect, and — transitively — Deal enrichment writes, which funnel
# through that same update redirect) instead of duplicating a third fix.
#
# This file drives the REAL functions (resolve_live_select_value(),
# commercial_crm.create_deal(), the real ActionGateway-approved
# tools.dispatcher.dispatch_tool() path) rather than re-implementing the
# logic under test.

from __future__ import annotations

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-d3final-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_D3FINAL_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondD3FinalTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondD3FinalTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-d3final-webhook-secret")
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
from airtable_schema import Tables, DealFields  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
import core.runtime_schema_provider as rsp  # noqa: E402
from core.runtime_schema_provider import resolve_live_select_value, _select_match_key  # noqa: E402

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
# Part 0 — resolve_live_select_value() hardened matching (A-I), isolated
# ══════════════════════════════════════════════════════════════════
print("── Part 0: resolve_live_select_value() hardened matching (isolated) ──")

_DOMAIN_CONTRACT_NORMAL = {
    "mode": "full",
    "source": "live",
    "table_id": "tblFAKE",
    "fetched_at": "2026-09-06T00:00:00Z",
    "fields": {
        "Domain": {
            "field_id": "fldFAKE",
            "type": "singleSelect",
            "choices": ["Real Estate", "Import", "Media", "SaaS", "Finance", "Recruitment", "General"],
        },
    },
}
_DOMAIN_CONTRACT_AMBIGUOUS = {
    "mode": "full",
    "source": "live",
    "table_id": "tblFAKE",
    "fetched_at": "2026-09-06T00:00:00Z",
    "fields": {
        # A genuinely ambiguous live schema: two distinct live choices,
        # NEITHER equal to the probe value itself (so the cheap exact-match
        # fast path can't short-circuit this case), that both normalize to
        # the SAME key ("real estate") under case/whitespace/separator
        # folding — not a realistic Airtable config (duplicate options
        # would be unusual) but exactly the "fail closed, never guess"
        # edge case item I must prove.
        "Domain": {
            "field_id": "fldFAKE",
            "type": "singleSelect",
            "choices": ["Real  Estate", "Real_Estate", "Import"],
        },
    },
}


class _FakeProvider:
    def __init__(self, contract):
        self._contract = contract

    def get_table_contract(self, table):
        return self._contract


def _with_contract(contract):
    return patch.object(rsp, "get_provider", return_value=_FakeProvider(contract))


with _with_contract(_DOMAIN_CONTRACT_NORMAL):
    chk("A. real_estate -> Real Estate",
        resolve_live_select_value("Deals", "Domain", "real_estate") == "Real Estate")
    chk("B. real estate -> Real Estate",
        resolve_live_select_value("Deals", "Domain", "real estate") == "Real Estate")
    chk("C. REAL_ESTATE -> Real Estate",
        resolve_live_select_value("Deals", "Domain", "REAL_ESTATE") == "Real Estate")
    chk("D. surrounding/repeated whitespace -> Real Estate",
        resolve_live_select_value("Deals", "Domain", "  Real   Estate  ") == "Real Estate")
    chk("D2. surrounding whitespace + underscore -> Real Estate",
        resolve_live_select_value("Deals", "Domain", " real_estate ") == "Real Estate")
    chk("E. media -> Media",
        resolve_live_select_value("Deals", "Domain", "media") == "Media")
    chk("F. finance -> Finance",
        resolve_live_select_value("Deals", "Domain", "finance") == "Finance")
    chk("G. invalid value -> None",
        resolve_live_select_value("Deals", "Domain", "not_a_real_domain") is None)
    chk("H. realestate (no separator at all) -> None (not fuzzy)",
        resolve_live_select_value("Deals", "Domain", "realestate") is None)
    chk("exact match short-circuits unchanged",
        resolve_live_select_value("Deals", "Domain", "Import") == "Import")
    chk("non-select field type is an untouched no-op",
        resolve_live_select_value("Deals", "Name", "anything at all") == "anything at all")
    chk("empty value returns unchanged",
        resolve_live_select_value("Deals", "Domain", "") == "")

with _with_contract(_DOMAIN_CONTRACT_AMBIGUOUS):
    chk("I. ambiguous normalized choices -> None (fail closed, never guess)",
        resolve_live_select_value("Deals", "Domain", "real_estate") is None)

chk("_select_match_key: underscore and space are equivalent",
    _select_match_key("real_estate") == _select_match_key("real estate") == _select_match_key("Real  Estate "))
chk("_select_match_key: no separator collapsing beyond whitespace/underscore",
    _select_match_key("realestate") != _select_match_key("real estate"))


# ══════════════════════════════════════════════════════════════════
# Part 1 — real Diamond paths (J-M)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 1: real Diamond create/update/enrichment paths ──")

LIVE_DEALS_FIELDS = {
    DealFields.NAME: {"field_id": "fld1", "type": "singleLineText", "choices": []},
    DealFields.DOMAIN: {"field_id": "fld2", "type": "singleSelect",
                          "choices": ["Real Estate", "Import", "Media", "SaaS", "Finance", "Recruitment", "General"]},
    DealFields.OWNER: {"field_id": "fld3", "type": "multipleRecordLinks", "choices": []},
    DealFields.STAGE: {"field_id": "fld4", "type": "singleSelect",
                         "choices": ["הזדמנות", "במשא ומתן", "סגור-ניצחון", "סגור-הפסד"]},
    DealFields.COMMERCIAL_STATUS: {"field_id": "fld5", "type": "singleSelect",
                                     "choices": ["prospect", "active", "at_risk", "completed", "cancelled", "written_off"]},
    DealFields.ESTIMATED_VALUE_BASIS: {"field_id": "fld6", "type": "singleSelect",
                                          "choices": ["monthly", "total", "one_off"]},
}


def _real_fetch_live(self, table):
    if table != Tables.DEALS:
        return None
    return {
        "table_id": "tblDealsFake",
        "fields": LIVE_DEALS_FIELDS,
        "fetched_at": "2026-09-06T00:00:00Z",
        "fetched_at_mono": __import__("time").monotonic(),
    }


_orig_fetch_live = rsp.RuntimeSchemaProvider._fetch_live
rsp.RuntimeSchemaProvider._fetch_live = _real_fetch_live
rsp._provider = None

import httpx  # noqa: E402
_orig_httpx_patch = httpx.patch
_orig_httpx_post = httpx.post
_captured_calls: list[dict] = []


def _mock_httpx_patch(url, headers=None, json=None, timeout=None):
    _captured_calls.append({"method": "PATCH", "url": url, "json": json})

    class _Resp:
        status_code = 200
        text = "{}"

        def json(self_):
            return {"id": "recD3FinalTest001", "fields": json.get("fields", {})}

    return _Resp()


def _mock_httpx_post(url, headers=None, json=None, timeout=None):
    _captured_calls.append({"method": "POST", "url": url, "json": json})

    class _Resp:
        status_code = 200
        text = "{}"

        def json(self_):
            return {"id": "recD3FinalTest001", "fields": json.get("fields", {}), "createdTime": "2026-09-06T00:00:00Z"}

    return _Resp()


httpx.patch = _mock_httpx_patch
httpx.post = _mock_httpx_post

REC_ID = "recD3FinalTest001"  # rec + 14 alnum, matches Airtable's record-id shape
_uid = [0]


def _dispatch_via_approval(tool_name, tool_inputs, flag_overrides=None):
    """Real ActionGateway.propose_action -> app._handle_approval_callback_impl
    -> tools.dispatcher.dispatch_tool(). Returns (contract, captured_calls)."""
    _uid[0] += 1
    user_id = f"d3final-{_uid[0]}"
    identity = Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )
    _captured_calls.clear()
    old_env = {}
    for k, v in (flag_overrides or {}).items():
        old_env[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        propose = _real_gw.propose_action(
            tenant_id="boss_hq", canonical_user_id=identity.memory_key,
            tool_name=tool_name, tool_inputs=tool_inputs,
            origin_channel="telegram", origin_chat_id=user_id,
            requires_approval=True, identity=identity, trusted_source="d3final_test",
        )
        assert propose.ok, f"propose_action failed: {propose}"
        with patch.object(app, "resolve_identity", return_value=identity):
            cq = types.SimpleNamespace(
                data=f"approve:{propose.contract_id}:{propose.contract_id}",
                id=f"cbq-{user_id}",
                from_user=types.SimpleNamespace(id=user_id, first_name="T"),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=user_id), message_id=1),
            )
            app._handle_approval_callback_impl(cq)
        contract = _real_gw.find_contract(propose.contract_id)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return contract, list(_captured_calls)


_reset_airtable_circuit_breaker()

# J. Deal create real_estate reaches writer with "Real Estate"
_contract, _calls = _dispatch_via_approval(
    "crm_create_deal",
    {"name": "D3 Final Test Deal", "domain": "real_estate", "owner_id": "recOwnerD3FinalTest"},
)
_posts = [c for c in _calls if c["method"] == "POST"]
chk("J. crm_create_deal(domain=real_estate) reaches the writer",
    _contract is not None and _contract.status in ("completed", "executed") and bool(_posts))
chk("J. exact live value 'Real Estate' sent to Airtable",
    bool(_posts) and _posts[0]["json"]["fields"].get(DealFields.DOMAIN) == "Real Estate")

# K. Deal update real_estate reaches writer with "Real Estate"
_reset_airtable_circuit_breaker()
_contract, _calls = _dispatch_via_approval(
    "airtable_update",
    {"table": Tables.DEALS, "record_id": REC_ID, "fields": {DealFields.DOMAIN: "real_estate"}},
)
_patches = [c for c in _calls if c["method"] == "PATCH"]
chk("K. airtable_update(Domain=real_estate) reaches the writer",
    _contract is not None and _contract.status in ("completed", "executed") and bool(_patches))
chk("K. exact live value 'Real Estate' sent to Airtable",
    bool(_patches) and _patches[0]["json"]["fields"].get(DealFields.DOMAIN) == "Real Estate")

# L. enrichment-shaped select values (Commercial Status / Estimated Value
# Basis — the same field set Deal enrichment collects) resolve through the
# SAME shared resolver via the SAME generic airtable_update redirect the
# real enrichment flow's _queue_approval_detailed()/_finish() ultimately
# calls (see app.py's _handle_deal_enrichment_reply) — no separate wiring
# in app.py/commercial_completion.py was added or needed.
_reset_airtable_circuit_breaker()
_contract, _calls = _dispatch_via_approval(
    "airtable_update",
    {"table": Tables.DEALS, "record_id": REC_ID, "fields": {
        DealFields.COMMERCIAL_STATUS: "prospect",
        DealFields.ESTIMATED_VALUE_BASIS: "monthly",
    }},
    # FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE=off (the code default)
    # makes the SEPARATE unknown-field-NAME gate in
    # tools/airtable_gateway.py:validate_airtable_fields() consult only the
    # legacy schema_cache.json, which (per the D3/D3-A audit, unchanged
    # here — out of scope for this task) doesn't know these two field
    # names at all and would block on that gate before this test can prove
    # anything about the VALUE resolver under test. "shadow" is also the
    # state evidenced as active in production (D3 audit). This has nothing
    # to do with resolve_live_select_value() itself, which runs regardless
    # of this flag.
    flag_overrides={"FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE": "shadow"},
)
_patches = [c for c in _calls if c["method"] == "PATCH"]
chk("L. enrichment-shaped select fields reach the writer via the shared resolver",
    _contract is not None and _contract.status in ("completed", "executed") and bool(_patches)
    and _patches[0]["json"]["fields"].get(DealFields.COMMERCIAL_STATUS) == "prospect"
    and _patches[0]["json"]["fields"].get(DealFields.ESTIMATED_VALUE_BASIS) == "monthly")

# M. invalid Diamond select never reaches writer (create AND update)
_reset_airtable_circuit_breaker()
_contract, _calls = _dispatch_via_approval(
    "crm_create_deal",
    {"name": "D3 Final Bad Deal", "domain": "general", "owner_id": "recOwnerD3FinalTest",
     "commercial_status": "not_a_real_status"},
)
chk("M. crm_create_deal with an invalid select value is blocked before any write",
    _contract is not None and _contract.status == "failed" and not any(c["method"] == "POST" for c in _calls))

_reset_airtable_circuit_breaker()
_contract, _calls = _dispatch_via_approval(
    "airtable_update",
    {"table": Tables.DEALS, "record_id": REC_ID, "fields": {DealFields.DOMAIN: "not_a_real_domain"}},
)
chk("M. airtable_update with an invalid Domain value is blocked before any write",
    _contract is not None and _contract.status == "failed" and not any(c["method"] == "PATCH" for c in _calls))


# ══════════════════════════════════════════════════════════════════
# Restore
# ══════════════════════════════════════════════════════════════════
app.bot = _orig_bot
app._flag_enabled = _orig_flag_enabled
feature_flags.is_enabled = _orig_ff_is_enabled
rsp.RuntimeSchemaProvider._fetch_live = _orig_fetch_live
rsp._provider = None
httpx.patch = _orig_httpx_patch
httpx.post = _orig_httpx_post

print(f"\n{'='*60}\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
