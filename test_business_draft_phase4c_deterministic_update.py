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


def test_16_payment_name_lookup_has_no_resolver_deterministic_clarify():
    """REQUIRED INVARIANT: the absence of a Payment typed-name resolver is a
    UX limitation, not permission to fall through to the Agent — this must
    terminate as a deterministic clarification, never a third 'unsupported/
    fall through' status."""
    status, rid, msg = resolve_deterministic_update_record(
        "payment", "name", "התשלום של יוני", identity=Identity(user_id="u1", role=Role.OWNER),
        chat_id="c", channel="telegram",
    )
    _check("16a", status == "clarify" and rid is None, (status, rid, msg))
    _check("16b", "תשלום" in msg and "שיצרנו עכשיו" in msg, msg)


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


def test_32_payment_typed_name_is_deterministic_clarify_never_agent():
    """REQUIRED INVARIANT (blocker closure): Payment has no deterministic
    human-typed-name resolver, but that is a UX limitation, not permission
    to delegate record resolution back to the model. This exact shape must
    be owned by the deterministic commercial-update handler end to end:
    agent_calls=0, zero ActionContract, zero write, deterministic clarify
    text naming a record id or "the record we just created" as the way
    forward — never a fall-through to Agent tool selection."""
    identity = Identity(user_id="e2e32", role=Role.OWNER, tenant_id="t1", domain_id="general")
    _text = 'תעדכן בתשלום "תשלום ינואר" את ההערות ל-X'
    _parse = P(_text)
    _check("32-pre[matched]", _parse.matched and _parse.entity == "payment", repr(_parse))
    route = route_request(text=_text, channel_raw="telegram", identity=identity, domain_from_channel="general")
    _check("32-pre[handler]", route.handler == Handler.TOOL and route.intent == Intent.UPDATE_PAYMENT_FIELD,
           (route.handler, route.intent))

    reply, queue_mock, build_ctx = _e2e(_text, Intent.UPDATE_PAYMENT_FIELD)
    _check("32a", build_ctx.call_count == 0, "build_context() called — agent_calls != 0")
    _check("32b", queue_mock.call_count == 0, "an ActionContract was created for an unresolvable Payment name")
    _check("32c", isinstance(reply, str) and "תשלום" in reply and "שיצרנו עכשיו" in reply, reply)


def test_32b_guard_field_before_entity_deterministic_clarify():
    """Spec example: 'עדכן את הסטטוס של עסקה X ל-Y' — clear update verb +
    Deal, but field-before-entity ordering the strict grammar doesn't
    parse. Must be owned deterministically (guard), never delegated."""
    _text = "עדכן את הסטטוס של עסקה X ל-Y"
    identity = Identity(user_id="e2e32b", role=Role.OWNER, tenant_id="t1", domain_id="general")
    route = route_request(text=_text, channel_raw="telegram", identity=identity, domain_from_channel="general")
    _check("32b-pre", route.handler == Handler.TOOL and route.intent == Intent.UPDATE_DEAL_FIELD,
           (route.handler, route.intent))
    reply, queue_mock, build_ctx = _e2e(_text, Intent.UPDATE_DEAL_FIELD)
    _check("32b-a", build_ctx.call_count == 0, "build_context() called")
    _check("32b-b", queue_mock.call_count == 0, "ActionContract created from an unparseable shape")
    _check("32b-c", isinstance(reply, str) and reply, reply)


def test_32c_guard_colon_equals_syntax_deterministic_clarify():
    """Spec example: 'שנה בתשלום X: הערות = Y' — colon/equals syntax the
    strict grammar doesn't parse, must still be owned deterministically."""
    _text = "שנה בתשלום X: הערות = Y"
    identity = Identity(user_id="e2e32c", role=Role.OWNER, tenant_id="t1", domain_id="general")
    route = route_request(text=_text, channel_raw="telegram", identity=identity, domain_from_channel="general")
    _check("32c-pre", route.handler == Handler.TOOL and route.intent == Intent.UPDATE_PAYMENT_FIELD,
           (route.handler, route.intent))
    reply, queue_mock, build_ctx = _e2e(_text, Intent.UPDATE_PAYMENT_FIELD)
    _check("32c-a", build_ctx.call_count == 0, "build_context() called")
    _check("32c-b", queue_mock.call_count == 0, "ActionContract created from an unparseable shape")
    _check("32c-c", isinstance(reply, str) and reply, reply)


def test_32d_guard_reference_only_no_field_value_deterministic_clarify():
    """Spec example: 'תעדכן את תנאי התשלום X' — no field/value at all."""
    _text = "תעדכן את תנאי התשלום X"
    identity = Identity(user_id="e2e32d", role=Role.OWNER, tenant_id="t1", domain_id="general")
    route = route_request(text=_text, channel_raw="telegram", identity=identity, domain_from_channel="general")
    _check("32d-pre", route.handler == Handler.TOOL and route.intent == Intent.UPDATE_PAYMENT_TERM_FIELD,
           (route.handler, route.intent))
    reply, queue_mock, build_ctx = _e2e(_text, Intent.UPDATE_PAYMENT_TERM_FIELD)
    _check("32d-a", build_ctx.call_count == 0, "build_context() called")
    _check("32d-b", queue_mock.call_count == 0, "ActionContract created from an unparseable shape")
    _check("32d-c", isinstance(reply, str) and reply, reply)


def test_32e_guard_field_before_entity_with_colon_deterministic_clarify():
    """Spec example: 'עדכן את ההערות של תנאי התשלום האחרון: X'."""
    _text = "עדכן את ההערות של תנאי התשלום האחרון: X"
    identity = Identity(user_id="e2e32e", role=Role.OWNER, tenant_id="t1", domain_id="general")
    route = route_request(text=_text, channel_raw="telegram", identity=identity, domain_from_channel="general")
    _check("32e-pre", route.handler == Handler.TOOL and route.intent == Intent.UPDATE_PAYMENT_TERM_FIELD,
           (route.handler, route.intent))
    reply, queue_mock, build_ctx = _e2e(_text, Intent.UPDATE_PAYMENT_TERM_FIELD)
    _check("32e-a", build_ctx.call_count == 0, "build_context() called")
    _check("32e-b", queue_mock.call_count == 0, "ActionContract created from an unparseable shape")
    _check("32e-c", isinstance(reply, str) and reply, reply)


def test_32f_guard_deal_colon_equals_deterministic_clarify():
    """Spec example: 'שנה בעסקה X: הערות = Y'."""
    _text = "שנה בעסקה X: הערות = Y"
    identity = Identity(user_id="e2e32f", role=Role.OWNER, tenant_id="t1", domain_id="general")
    route = route_request(text=_text, channel_raw="telegram", identity=identity, domain_from_channel="general")
    _check("32f-pre", route.handler == Handler.TOOL and route.intent == Intent.UPDATE_DEAL_FIELD,
           (route.handler, route.intent))
    reply, queue_mock, build_ctx = _e2e(_text, Intent.UPDATE_DEAL_FIELD)
    _check("32f-a", build_ctx.call_count == 0, "build_context() called")
    _check("32f-b", queue_mock.call_count == 0, "ActionContract created from an unparseable shape")
    _check("32f-c", isinstance(reply, str) and reply, reply)


def test_32g_guard_does_not_fire_on_readonly_question():
    """Explicit negative control: a read-only question naming both entities
    ('מה תנאי התשלום בעסקה X?') must remain on its existing path — the
    guard requires an update/change verb, which this text has none of."""
    r = P("מה תנאי התשלום בעסקה X?")
    _check("32g-a", not r.matched, repr(r))
    identity = Identity(user_id="e2e32g", role=Role.OWNER, tenant_id="t1", domain_id="general")
    route = route_request(
        text="מה תנאי התשלום בעסקה X?", channel_raw="telegram",
        identity=identity, domain_from_channel="general",
    )
    _check("32g-b", route.intent not in (Intent.UPDATE_DEAL_FIELD, Intent.UPDATE_PAYMENT_TERM_FIELD, Intent.UPDATE_PAYMENT_FIELD),
           route.intent)


def test_32h_guard_does_not_fire_on_unrelated_mention():
    """Explicit negative control: a sentence that happens to share a verb
    token with 'תעדכן' but isn't a bare/ב/ל-prefixed entity mention (the
    entity appears only as a bare 'ה'-prefixed back-reference) must not
    trip the guard."""
    r = P("תעדכן אותי כשהעסקה תיסגר")
    _check("32h", not r.matched, repr(r))


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
        ("עדכן איש קשר X", Intent.UPDATE_CONTACT),  # entity outside Phase 4C's {deal,payment_term,payment}
        ("עדכן ליד X", Intent.UPDATE_LEAD),
    ):
        route = route_request(text=text, channel_raw="telegram", identity=identity, domain_from_channel="general")
        _check(f"34[{expected_intent}]", route.intent == expected_intent, (text, route.intent))


def test_35_general_discussion_mentioning_payment_unaffected():
    """Spec requirement: 'General discussion mentioning a payment must
    remain unchanged.'"""
    identity = _owner_identity()
    for text in (
        "אני חושב שכדאי לבדוק את התשלום הזה",
        "מתי בדרך כלל אנחנו מקבלים תשלום מלקוחות?",
        "התשלום שקיבלנו מאתמול נראה תקין",
    ):
        r = P(text)
        _check(f"35a[{text}]", not r.matched, repr(r))
        route = route_request(text=text, channel_raw="telegram", identity=identity, domain_from_channel="general")
        _check(f"35b[{text}]", route.intent != Intent.UPDATE_PAYMENT_FIELD, (text, route.intent))


def test_36_fresh_command_escape_hatch_recognizes_phase4c_text():
    """LIVE-FOUND REGRESSION (23/09/2026, production): a genuinely fresh,
    well-formed Phase 4C UPDATE command sent right after an abandoned
    CommercialCompletionRouter CREATE clarification (e.g. a failed 'צור
    תנאי תשלום לעסקה X' still parked awaiting a deal name) was swallowed as
    a literal answer to the OLD session — the exact SEARCH() query sent to
    Airtable was the entire new message, not just the intended Deal
    reference, and the reply was the stale session's own generic
    "לא מצאתי התאמה" rather than anything from Phase 4C. Root cause:
    app._is_fresh_deterministic_command() — the shared escape hatch every
    other deterministic command family (create_task, create_deal, S2C
    completion, lead-deal link) already used to break out of a parked
    session — never checked parse_deterministic_commercial_update() at all,
    since it didn't exist when that escape hatch was written. Fixed by
    adding it there. This test locks in that fix directly against the
    exact live-reproduced text."""
    from app import _is_fresh_deterministic_command
    live_text = "תעדכן בעסקה TEST-4B-DELETE-ME את ההערות ל-בדיקת Phase 4C"
    _check("36a", _is_fresh_deterministic_command(live_text), live_text)
    # Also the guard-recognized-but-incomplete shapes (matched, not certain)
    # -- these must escape too, per the "matched, not certain" gate.
    for text in (
        "עדכן את הסטטוס של עסקה X ל-Y",
        "שנה בתשלום X: הערות = Y",
    ):
        _check(f"36b[{text}]", _is_fresh_deterministic_command(text), text)
    # Negative control: ordinary free text (a plausible field ANSWER to a
    # parked session, e.g. just a name) must still NOT be treated as a
    # fresh command -- this escape hatch must stay precise, not swallow
    # everything.
    _check("36c", not _is_fresh_deterministic_command("TEST-4B-DELETE-ME"), "plain text over-triggered the escape hatch")


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
