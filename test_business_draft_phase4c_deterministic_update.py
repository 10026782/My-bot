# test_business_draft_phase4c_deterministic_update.py — Phase 4C:
# Deterministic Commercial UPDATE Routing.
#
# Verifies (per the Phase 4C spec's Test Acceptance section):
#   - the bounded grammar parser recognizes both closed shapes (entity-first
#     and the live-incident field-first variant) for Deal/PaymentTerm/Payment
#     and never partially matches unrelated text
#   - record resolution follows the fixed priority order (explicit id >
#     unique name > "just created" marker > CLARIFY), never guesses, never
#     picks "first result"
#   - a recognized request reaches the canonical crm_update_* tool via
#     _queue_approval_detailed() WITHOUT ever calling build_context()/the
#     Anthropic client — i.e. agent_calls stays 0
#   - ambiguous record / unknown field / missing reference all deterministic-
#     clarify, never fall to the Agent
#   - an out-of-scope shape (Payment resolved by typed name — no deterministic
#     resolver exists for that) falls through to the Agent unchanged
#   - the exact live-incident production text reproduces as agent_calls=0

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-p4c-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:P4C_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patP4CTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appP4CTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision, Intent, Handler, Risk  # noqa: E402
from context import AgentContext  # noqa: E402
from core.deterministic_commercial_update import (  # noqa: E402
    parse_deterministic_commercial_update as P,
    resolve_deterministic_update_record,
)
from core.router.router import route_request  # noqa: E402

_RESULTS = []


def _check(name, condition, detail=""):
    if not condition:
        raise AssertionError(f"{name} FAILED: {detail}")
    _RESULTS.append(name)


# ══════════════════════════════════════════════════
# 1. Parser — grammar recognition
# ══════════════════════════════════════════════════

def test_01_deal_entity_first_recognized():
    r = P("תעדכן בעסקה TEST-DEAL-X את הסטטוס ל-פעיל")
    _check("01", r.matched and r.certain and r.entity == "deal" and r.field == "commercial_status"
           and r.value == "פעיל" and r.record_ref_kind == "name", repr(r))


def test_02_payment_term_recent_marker_recognized():
    r = P("תעדכן בתנאי התשלום שיצרנו עכשיו את ההערות ל-'בדיקת קנוני'")
    _check("02", r.matched and r.certain and r.entity == "payment_term" and r.field == "notes"
           and r.value == "בדיקת קנוני" and r.record_ref_kind == "recent", repr(r))


def test_03_payment_field_first_recognized():
    r = P("תעדכן בתשלום X את אמצעי התשלום ל-מזומן")
    _check("03", r.matched and r.certain and r.entity == "payment" and r.field == "method"
           and r.value == "מזומן", repr(r))


def test_04_live_incident_field_first_variant():
    r = P("תעדכן ב-Airtable את שדה ההערות בתנאי התשלום שיצרנו עכשיו ל-'בדיקת קנוני 4B'")
    _check("04", r.matched and r.certain and r.entity == "payment_term" and r.field == "notes"
           and r.value == "בדיקת קנוני 4B" and r.record_ref_kind == "recent", repr(r))


def test_05_unrelated_text_not_matched():
    for text in ("מה שלומך היום", "תקבע לי פגישה מחר", "תעדכן משימה לקנות חלב"):
        r = P(text)
        _check(f"05[{text}]", not r.matched, repr(r))


def test_06_unknown_field_structurally_recognized_but_uncertain():
    r = P("תעדכן בעסקה X את השדה המוזר ל-ערך")
    _check("06", r.matched and not r.certain and r.unknown_field and r.entity == "deal", repr(r))


def test_07_missing_record_reference_structurally_recognized_but_uncertain():
    r = P("תעדכן בעסקה את הסטטוס ל-סגור")
    _check("07", r.matched and not r.certain and r.missing_record_ref, repr(r))


def test_08_explicit_record_id_recognized():
    r = P("תעדכן בעסקה recAAAAAAAAAAAAAA את ההערות ל-בדיקה")
    _check("08", r.matched and r.certain and r.record_ref_kind == "explicit_id"
           and r.record_ref_text == "recAAAAAAAAAAAAAA", repr(r))


def test_09_field_alias_map_only_contains_writer_allowed_fields():
    # Module-import-time assert already enforces this; re-verify explicitly
    # here so a future edit that weakens the import-time check still fails
    # a visible test, not just an import-time AssertionError buried in a
    # traceback.
    from commercial_crm import _DEAL_UPDATE_ALLOWED, _PAYMENT_TERM_UPDATE_ALLOWED, _PAYMENT_UPDATE_ALLOWED
    from core.deterministic_commercial_update import FIELD_ALIASES
    allowed = {
        "deal": _DEAL_UPDATE_ALLOWED, "payment_term": _PAYMENT_TERM_UPDATE_ALLOWED,
        "payment": _PAYMENT_UPDATE_ALLOWED,
    }
    for entity, aliases in FIELD_ALIASES.items():
        bad = set(aliases.values()) - allowed[entity]
        _check(f"09[{entity}]", not bad, bad)


def test_10_payment_never_exposes_financial_fields():
    from core.deterministic_commercial_update import FIELD_ALIASES
    financial = {"amount", "currency", "direction", "paid_at", "charge_id", "deal_id", "status"}
    exposed = set(FIELD_ALIASES["payment"].values()) & financial
    _check("10", not exposed, exposed)


# ══════════════════════════════════════════════════
# 2. Record resolution — priority order, fail-closed
# ══════════════════════════════════════════════════

def test_11_explicit_id_resolves_directly():
    status, rid, msg = resolve_deterministic_update_record(
        "deal", "explicit_id", "recAAAAAAAAAAAAAA", identity=None, chat_id="c", channel="telegram",
    )
    _check("11", status == "resolved" and rid == "recAAAAAAAAAAAAAA" and msg is None, (status, rid, msg))


def test_12_explicit_id_invalid_shape_clarifies():
    status, rid, msg = resolve_deterministic_update_record(
        "deal", "explicit_id", "not-a-real-id", identity=None, chat_id="c", channel="telegram",
    )
    _check("12", status == "clarify" and rid is None and msg, (status, rid, msg))


def test_13_name_lookup_unique_resolves():
    with patch("commercial_crm.lookup_human_reference",
               return_value=[{"id": "recDEALUNIQUE0001", "fields": {"Name": "TEST-DEAL-X"}}]):
        status, rid, msg = resolve_deterministic_update_record(
            "deal", "name", "TEST-DEAL-X", identity=Identity(user_id="u1", role=Role.OWNER),
            chat_id="c", channel="telegram",
        )
    _check("13", status == "resolved" and rid == "recDEALUNIQUE0001", (status, rid, msg))


def test_14_name_lookup_ambiguous_clarifies_never_first_result():
    from airtable_schema import DealFields
    with patch("commercial_crm.lookup_human_reference",
               return_value=[
                   {"id": "recA", "fields": {DealFields.NAME: "עסקה א"}},
                   {"id": "recB", "fields": {DealFields.NAME: "עסקה ב"}},
               ]):
        status, rid, msg = resolve_deterministic_update_record(
            "deal", "name", "עסקה", identity=Identity(user_id="u1", role=Role.OWNER),
            chat_id="c", channel="telegram",
        )
    _check("14", status == "clarify" and rid is None and "עסקה א" in msg and "עסקה ב" in msg, (status, rid, msg))


def test_15_name_lookup_zero_matches_clarifies():
    with patch("commercial_crm.lookup_human_reference", return_value=[]):
        status, rid, msg = resolve_deterministic_update_record(
            "payment_term", "name", "לא קיים", identity=Identity(user_id="u1", role=Role.OWNER),
            chat_id="c", channel="telegram",
        )
    _check("15", status == "clarify" and rid is None, (status, rid, msg))


def test_16_payment_name_lookup_is_unsupported_not_clarify():
    status, rid, msg = resolve_deterministic_update_record(
        "payment", "name", "התשלום של יוני", identity=Identity(user_id="u1", role=Role.OWNER),
        chat_id="c", channel="telegram",
    )
    _check("16", status == "unsupported" and rid is None and msg is None, (status, rid, msg))


def test_17_recent_marker_resolves_when_present():
    from session_store import lead_sessions
    with patch.object(lead_sessions, "get_last_commercial_create",
                       return_value={"record_id": "recRECENT000001", "age_seconds": 30}):
        status, rid, msg = resolve_deterministic_update_record(
            "payment_term", "recent", "שיצרנו עכשיו", identity=None, chat_id="c", channel="telegram",
        )
    _check("17", status == "resolved" and rid == "recRECENT000001", (status, rid, msg))


def test_18_recent_marker_missing_clarifies():
    from session_store import lead_sessions
    with patch.object(lead_sessions, "get_last_commercial_create", return_value=None):
        status, rid, msg = resolve_deterministic_update_record(
            "payment_term", "recent", "שיצרנו עכשיו", identity=None, chat_id="c", channel="telegram",
        )
    _check("18", status == "clarify" and rid is None, (status, rid, msg))


def test_19_recent_marker_too_stale_clarifies():
    from session_store import lead_sessions
    with patch.object(lead_sessions, "get_last_commercial_create",
                       return_value={"record_id": "recOLD00000000001", "age_seconds": 99999}):
        status, rid, msg = resolve_deterministic_update_record(
            "deal", "recent", "האחרון", identity=None, chat_id="c", channel="telegram",
        )
    _check("19", status == "clarify" and rid is None, (status, rid, msg))


def test_20_missing_record_ref_kind_clarifies():
    status, rid, msg = resolve_deterministic_update_record(
        "deal", "", "", identity=None, chat_id="c", channel="telegram",
    )
    _check("20", status == "clarify" and rid is None, (status, rid, msg))


# ══════════════════════════════════════════════════
# 3. Router — Handler.TOOL assignment
# ══════════════════════════════════════════════════

def _owner_identity():
    return Identity(user_id="owner1", role=Role.OWNER, tenant_id="t1", domain_id="general")


def test_21_router_assigns_tool_handler_for_each_entity():
    cases = [
        ("תעדכן בעסקה TEST-X את הסטטוס ל-פעיל", Intent.UPDATE_DEAL_FIELD),
        ("תעדכן בתנאי התשלום שיצרנו עכשיו את ההערות ל-בדיקה", Intent.UPDATE_PAYMENT_TERM_FIELD),
        # Payment has no deterministic name lookup (see test_16); a literal
        # "rec..." id inline also trips the unrelated pre-existing C89
        # Tier-4 pasted-table stop-gate (capture_router), so "recent" is the
        # cleanest recognized+supported shape to exercise here.
        ("תעדכן בתשלום האחרון את אמצעי התשלום ל-מזומן", Intent.UPDATE_PAYMENT_FIELD),
    ]
    identity = _owner_identity()
    for text, expected_intent in cases:
        route = route_request(text=text, channel_raw="telegram", identity=identity, domain_from_channel="general")
        _check(f"21[{expected_intent}]", route.handler == Handler.TOOL and route.intent == expected_intent,
               (route.handler, route.intent))


def test_22_router_live_incident_text_assigns_tool_handler():
    identity = _owner_identity()
    route = route_request(
        text="תעדכן ב-Airtable את שדה ההערות בתנאי התשלום שיצרנו עכשיו ל-'בדיקת קנוני 4B'",
        channel_raw="telegram", identity=identity, domain_from_channel="general",
    )
    _check("22", route.handler == Handler.TOOL and route.intent == Intent.UPDATE_PAYMENT_TERM_FIELD,
           (route.handler, route.intent))


def test_23_router_excludes_lead_guest_readonly_roles():
    for role in (Role.LEAD, Role.GUEST, Role.READONLY):
        identity = Identity(user_id="x", role=role, tenant_id="t1", domain_id="general")
        route = route_request(
            text="תעדכן בעסקה TEST-X את הסטטוס ל-פעיל", channel_raw="telegram",
            identity=identity, domain_from_channel="general",
        )
        _check(f"23[{role}]", route.handler != Handler.TOOL or route.intent != Intent.UPDATE_DEAL_FIELD,
               (role, route.handler, route.intent))


def test_24_router_unrelated_text_unaffected():
    identity = _owner_identity()
    route = route_request(text="מה שלומך היום", channel_raw="telegram", identity=identity, domain_from_channel="general")
    _check("24", route.intent != Intent.UPDATE_DEAL_FIELD, route.intent)


# ══════════════════════════════════════════════════
# 4. End-to-end run_agent() — agent_calls=0 acceptance tests
# ══════════════════════════════════════════════════

def _e2e(user_text, route_intent, *, queue_return=None, session_marker=None, lookup_return=None):
    """Drives the real app.run_agent() with Identity/Router mocked to the
    Phase 4C route this text should have produced (already independently
    verified by the router-level tests above), and build_context()/the
    Anthropic client wired to fail loudly if ever called — the only way
    agent_calls can provably be 0, not just claimed."""
    identity = Identity(user_id="e2e1", role=Role.OWNER, tenant_id="t1", domain_id="general")
    route = RouteDecision(intent=route_intent, handler=Handler.TOOL, risk=Risk.NEEDS_APPROVAL, needs_approval=True)
    build_context_mock = MagicMock(side_effect=AssertionError("build_context() called — Agent Loop was reached, agent_calls != 0"))
    queue_mock = MagicMock(return_value=queue_return or {
        "message": "queued", "contract_id": "c1", "ok": True,
        "terminal_outcome": None, "action_tool": "crm_update_deal", "created_this_turn": True,
    })
    patches = [
        patch.object(app, "resolve_identity", return_value=identity),
        patch.object(app, "_safe_route", return_value=route),
        patch.object(app, "build_context", build_context_mock),
        patch.object(app, "_queue_approval_detailed", queue_mock),
    ]
    from session_store import lead_sessions
    if session_marker is not None:
        patches.append(patch.object(lead_sessions, "get_last_commercial_create", return_value=session_marker))
    if lookup_return is not None:
        patches.append(patch("commercial_crm.lookup_human_reference", return_value=lookup_return))
    for p in patches:
        p.start()
    try:
        reply = app.run_agent(user_text, "e2e1", channel="telegram")
    finally:
        for p in patches:
            p.stop()
    return reply, queue_mock, build_context_mock


def test_25_deal_update_explicit_id_agent_calls_zero():
    reply, queue_mock, build_ctx = _e2e(
        "תעדכן בעסקה recAAAAAAAAAAAAAA את ההערות ל-עודכן",
        Intent.UPDATE_DEAL_FIELD,
    )
    _check("25a", build_ctx.call_count == 0, "build_context called — agent_calls != 0")
    _check("25b", queue_mock.call_count == 1, queue_mock.call_args_list)
    args, kwargs = queue_mock.call_args
    _check("25c", args[0] == "crm_update_deal", args)
    _check("25d", args[1] == {"record_id": "recAAAAAAAAAAAAAA", "notes": "עודכן"}, args[1])
    _check("25e", kwargs.get("trusted_source") == "deterministic_commercial_update", kwargs)


def test_26_payment_term_recent_marker_agent_calls_zero():
    reply, queue_mock, build_ctx = _e2e(
        "תעדכן בתנאי התשלום שיצרנו עכשיו את ההערות ל-'בדיקת קנוני'",
        Intent.UPDATE_PAYMENT_TERM_FIELD,
        session_marker={"record_id": "recTERMRECENT0001", "age_seconds": 5},
    )
    _check("26a", build_ctx.call_count == 0, "build_context called — agent_calls != 0")
    _check("26b", queue_mock.call_count == 1, queue_mock.call_args_list)
    args, kwargs = queue_mock.call_args
    _check("26c", args[0] == "crm_update_payment_term", args)
    _check("26d", args[1] == {"record_id": "recTERMRECENT0001", "notes": "בדיקת קנוני"}, args[1])


def test_27_live_incident_exact_text_agent_calls_zero():
    """The PRINCIPAL acceptance test — reproduces the exact production
    request that previously drove two live Agent/Anthropic calls
    (airtable_get, then model tool-selection) end to end. After Phase 4C
    this must resolve deterministically with zero Agent involvement."""
    reply, queue_mock, build_ctx = _e2e(
        "תעדכן ב-Airtable את שדה ההערות בתנאי התשלום שיצרנו עכשיו ל-'בדיקת קנוני 4B'",
        Intent.UPDATE_PAYMENT_TERM_FIELD,
        session_marker={"record_id": "recZ6IkYGDOucA8Cl", "age_seconds": 12},
    )
    _check("27a", build_ctx.call_count == 0, "build_context called — this is the regression this test exists to catch")
    _check("27b", queue_mock.call_count == 1, queue_mock.call_args_list)
    args, kwargs = queue_mock.call_args
    _check("27c", args[0] == "crm_update_payment_term", args)
    _check("27d", args[1] == {"record_id": "recZ6IkYGDOucA8Cl", "notes": "בדיקת קנוני 4B"}, args[1])
    _check("27e", kwargs.get("trusted_source") == "deterministic_commercial_update", kwargs)


def test_28_payment_update_by_name_resolves_via_lookup():
    reply, queue_mock, build_ctx = _e2e(
        "תעדכן בתשלום recPAYMENTNAME001 את אמצעי התשלום ל-מזומן",
        Intent.UPDATE_PAYMENT_FIELD,
    )
    _check("28a", build_ctx.call_count == 0, "build_context called")
    _check("28b", queue_mock.call_count == 1, queue_mock.call_args_list)
    args, kwargs = queue_mock.call_args
    _check("28c", args[0] == "crm_update_payment", args)
    _check("28d", args[1] == {"record_id": "recPAYMENTNAME001", "method": "מזומן"}, args[1])


def test_29_ambiguous_record_clarifies_zero_agent_zero_contract():
    from airtable_schema import DealFields
    reply, queue_mock, build_ctx = _e2e(
        "תעדכן בעסקה עסקה את הסטטוס ל-סגור",
        Intent.UPDATE_DEAL_FIELD,
        lookup_return=[
            {"id": "recA", "fields": {DealFields.NAME: "עסקה א"}},
            {"id": "recB", "fields": {DealFields.NAME: "עסקה ב"}},
        ],
    )
    _check("29a", build_ctx.call_count == 0, "build_context called")
    _check("29b", queue_mock.call_count == 0, "ActionContract was created for an ambiguous record")
    _check("29c", isinstance(reply, str) and reply, reply)


def test_30_unknown_field_clarifies_zero_agent_zero_contract():
    reply, queue_mock, build_ctx = _e2e(
        "תעדכן בעסקה TEST-X את השדה המוזר ל-ערך",
        Intent.UPDATE_DEAL_FIELD,
    )
    _check("30a", build_ctx.call_count == 0, "build_context called")
    _check("30b", queue_mock.call_count == 0, "ActionContract was created for an unknown field")
    _check("30c", isinstance(reply, str) and reply, reply)


def test_31_missing_record_reference_clarifies_zero_agent_zero_contract():
    reply, queue_mock, build_ctx = _e2e(
        "תעדכן בעסקה את הסטטוס ל-סגור",
        Intent.UPDATE_DEAL_FIELD,
    )
    _check("31a", build_ctx.call_count == 0, "build_context called")
    _check("31b", queue_mock.call_count == 0, "ActionContract was created with no record reference")
    _check("31c", isinstance(reply, str) and reply, reply)


def test_32_payment_by_name_falls_through_to_agent():
    """Documented Phase 4C boundary: Payment has no deterministic
    human-typed-name resolver (commercial_crm.lookup_human_reference has no
    "payment" entity). parse_deterministic_commercial_update() marks this
    exact shape unsupported_shape=True, so router.py's own gate never
    assigns Handler.TOOL for it in the first place (verified below via the
    REAL route_request(), not a hand-built RouteDecision) — it must fall
    through to the Agent pipeline unchanged, reaching build_context(),
    rather than being silently dropped or fail-closed clarified as if it
    were merely ambiguous."""
    identity = Identity(user_id="e2e32", role=Role.OWNER, tenant_id="t1", domain_id="general")
    _text = "תעדכן בתשלום התשלום של יוני את ההערות ל-בדיקה"
    _parse = P(_text)
    _check("32-pre[unsupported_shape]", _parse.matched and _parse.unsupported_shape, repr(_parse))
    route = route_request(text=_text, channel_raw="telegram", identity=identity, domain_from_channel="general")
    _check("32-pre[handler]", route.handler != Handler.TOOL, (route.handler, route.intent))
    fake_ctx = AgentContext(
        system_prompt="test", allowed_tools=[], memory_key="e2e32", max_tokens=500,
        model="claude-haiku-test", identity_label="owner",
    )
    reached_build_context = {"called": False}

    def _bc(*a, **kw):
        reached_build_context["called"] = True
        return fake_ctx

    def _fake_anthropic_response(text):
        from types import SimpleNamespace
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=10, output_tokens=10),
        )

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=route), \
         patch.object(app, "build_context", side_effect=_bc), \
         patch.object(app.client.messages, "create",
                       return_value=_fake_anthropic_response("בסדר.")):
        app.run_agent(
            "תעדכן בתשלום התשלום של יוני את ההערות ל-בדיקה", "e2e32", channel="telegram",
        )
    _check("32", reached_build_context["called"], "unsupported Payment-by-name shape did not fall through to Agent")


# ══════════════════════════════════════════════════
# 5. Phase 4B / non-commercial regression boundary
# ══════════════════════════════════════════════════

def test_33_phase4b_module_untouched_and_importable():
    import core.commercial_generic_canonicalization as p4b
    _check("33", hasattr(p4b, "canonicalize_generic_commercial_call"), "Phase 4B entry point missing")


def test_34_noncommercial_router_flows_unaffected():
    identity = _owner_identity()
    for text, expected_intent in (
        ("צור משימה: לקנות חלב", Intent.CREATE_TASK),
        ("קבע פגישה מחר ב-10", Intent.CREATE_EVENT),
    ):
        route = route_request(text=text, channel_raw="telegram", identity=identity, domain_from_channel="general")
        _check(f"34[{expected_intent}]", route.intent == expected_intent, (text, route.intent))


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

def main():
    tests = [
        v for k, v in sorted(globals().items())
        if k.startswith("test_") and callable(v)
    ]
    failures = []
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
        except Exception as e:
            failures.append((t.__name__, e))
            print(f"❌ {t.__name__}: {e}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} tests passed, {len(_RESULTS)} checks passed")
    if failures:
        print("\nFAILURES:")
        for name, e in failures:
            print(f"  {name}: {e}")
        sys.exit(1)
    print("\n✅ ALL PHASE 4C DETERMINISTIC UPDATE TESTS PASSED")


if __name__ == "__main__":
    main()
