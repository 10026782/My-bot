# test_diamond_remediation_d1_unified_approval_continuation.py —
# DIAMOND REMEDIATION D1 regression: unify approval continuation across the
# Telegram button-callback and typed-text confirmation ingress paths, and
# make the parked Deal enrichment offer durable.
#
# Root problem (final systemic Diamond-path audit, 06/09/2026): nested-
# parent-resume (_resolve_diamond_path_continuation) and Deal-enrichment-
# offer (_offer_deal_enrichment) behavior lived EXCLUSIVELY inside
# app.py::_handle_approval_callback_impl() (the Telegram inline-button
# handler). The parallel typed-text confirmation path
# (core.action_gateway.ActionGateway.route_confirmation_word ->
# _resolve_single_contract -> approve_with_lifecycle_result) executed the
# same underlying write but had zero knowledge of either mechanism — a
# nested Contact/Organization approved by typed "כן" never resumed the
# parent Deal, and a root Deal approved by typed "כן" never offered
# enrichment.
#
# The fix: app.py::_apply_diamond_post_approval_continuation() is now the
# ONE shared post-approval continuation hook. Both
# _handle_approval_callback_impl() and _resolve_single_contract() call it
# immediately after their own approve_with_lifecycle_result() succeeds.
#
# Separately, session_store.py's deal_enrichment_offer key was being
# written via _sync_to_db() but silently dropped (absent from that
# function's field whitelist, from _load_from_db()'s restore whitelist,
# and from _new_session()'s default shape) — RAM-only despite looking
# durable. Fixed by adding it to all three surfaces.
#
# And _apply_ingress_context_gate() didn't exempt "commercial_completion:"
# callbacks from mark_context_interrupted() — every enrichment button press
# was marking the user's OTHER live ActionContracts context-interrupted,
# the likely direct mechanism behind the reported "יש פעולה שממתינה
# לאישור..." reconfirmation spam. Fixed with a narrow exemption alongside
# the existing approve:/reject:/lead_draft_* ones.
#
# This file drives the REAL shared post-approval boundary from BOTH real
# ingress paths (app._handle_approval_callback_impl for the button,
# core.action_gateway.action_gateway.route_confirmation_word for typed
# text) against a real, in-memory ActionGateway/ExecutionLedger — never
# by calling _apply_diamond_post_approval_continuation() in isolation and
# declaring victory.

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-d1-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_D1_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondD1Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondD1Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import tc8_test_repo_stub  # noqa: E402
tc8_test_repo_stub.patch_turn_state_repository()

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

from identity import Identity, Role  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
from commercial_completion import ContinuationRef  # noqa: E402
from commercial_completion_routing import (  # noqa: E402
    CommercialCompletionRouter, serialize_completion_session,
)
import session_store  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str, role: str = Role.OWNER) -> Identity:
    return Identity(
        user_id=user_id, role=role, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


def _rec(n: int) -> str:
    """A syntactically valid Airtable record id: ^rec[A-Za-z0-9]{14}$."""
    return "rec" + str(n).zfill(14)


def _airtable_ok(tool_name: str, record_id: str, message: str = "✅ בוצע") -> dict:
    return {
        "ok": True, "tool": tool_name, "external_id": record_id,
        "evidence": {"record_id": record_id}, "user_message": message,
    }


def _airtable_fail(tool_name: str) -> dict:
    return {"ok": False, "tool": tool_name, "external_id": "", "evidence": {},
            "user_message": "❌ נכשל"}


_PROD_FLAGS_ON = {"FEATURE_ACTION_GATEWAY", "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS"}


# ══════════════════════════════════════════════════════════════════
# Part 1 — _apply_diamond_post_approval_continuation()'s own gates
# (fast, precise; NOT the sole proof — see Parts 2-4 for the real
# shared-boundary drive through both ingress paths).
# ══════════════════════════════════════════════════════════════════
print("── Part 0: core/action_gateway.py never imports app.py ──")

# Regression guard for the exact bug this design avoids: an unconditional
# (even deferred) `from app import ...` inside core/action_gateway.py would
# force app.py's full module-level startup (Flask app, bot init,
# startup_validator.validate_startup(), which calls sys.exit() on missing
# critical env vars — a SystemExit, not an Exception, so a surrounding
# try/except would NOT save the caller) onto every test that exercises
# ActionGateway without app.py's env vars set. post_approval_hook (a plain
# callable, dependency-injected by app.py's own callers) exists precisely
# so this module never needs to reach for app.py at all.
import ast as _ast  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "core", "action_gateway.py"),
          encoding="utf-8") as _f:
    _gw_source = _f.read()
_gw_tree = _ast.parse(_gw_source)
_gw_app_imports = [
    node for node in _ast.walk(_gw_tree)
    if (isinstance(node, _ast.Import) and any(a.name == "app" for a in node.names))
    or (isinstance(node, _ast.ImportFrom) and node.module == "app")
]
chk("core/action_gateway.py contains no real 'import app' / 'from app import' "
    "statement anywhere (AST-checked, not a naive substring match — this exact "
    "comment mentions the phrase in prose)",
    len(_gw_app_imports) == 0)

# And the functional counterpart: route_confirmation_word() with NO hook
# (the default — every pre-existing caller) must resolve a real approval
# without ever touching app.py, module unloaded or not.
_no_hook_user = "d1-no-hook-guard"
_no_hook_contract_id = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=f"boss_hq:{_no_hook_user}",
    tool_name="crm_create_deal",
    tool_inputs={"name": "עסקת ללא הוק", "domain": "import", "owner_id": _no_hook_user},
    origin_channel="telegram", origin_chat_id=_no_hook_user,
    requires_approval=True, identity=_identity(_no_hook_user), trusted_source="agent",
).contract_id
with patch("tools.dispatcher.dispatch_tool",
           side_effect=lambda *a, **k: _airtable_ok("crm_create_deal", _rec(901))), \
     patch("session_store.lead_sessions.get_last_prompted_contract", return_value=None):
    _no_hook_contract = _real_gw._ledger.find_by_id(_no_hook_contract_id)
    _no_hook_reply = _real_gw.route_confirmation_word(
        f"boss_hq:{_no_hook_user}", approver_role=Role.OWNER,
        live_contracts=[_no_hook_contract], use_session_bookmark=False,
    )
_no_hook_contract_after = _real_gw._ledger.find_by_id(_no_hook_contract_id)
chk("route_confirmation_word() with NO post_approval_hook still approves "
    "normally (the parameter is a pure additive no-op by default)",
    _no_hook_contract_after is not None
    and _no_hook_contract_after.status in ("completed", "executed")
    and bool(_no_hook_reply))


print("\n── Part 1: shared hook's own completed/verified gates ──")


def _fake_contract(status: str, tool_name: str = "crm_create_deal", continuation_ref=None):
    return SimpleNamespace(status=status, tool_name=tool_name, continuation_ref=continuation_ref)


def _fake_lifecycle(evidence_status: str | None, evidence_ref: str = ""):
    return SimpleNamespace(evidence_status=evidence_status, evidence_ref=evidence_ref)


with patch.object(app, "_resolve_diamond_path_continuation", return_value=None) as _resume_spy, \
     patch.object(app, "_offer_deal_enrichment", return_value="") as _offer_spy:
    out = app._apply_diamond_post_approval_continuation(
        _fake_contract("pending"), _fake_lifecycle("verified_write_success", _rec(1)),
        origin_chat_id="c1", origin_channel="telegram",
    )
    chk("pending contract (not yet terminal) -> no continuation at all",
        out.resume_text is None and out.enrichment_offer_text is None)
    chk("pending contract -> _resolve_diamond_path_continuation never called", not _resume_spy.called)

with patch.object(app, "_resolve_diamond_path_continuation", return_value=None) as _resume_spy, \
     patch.object(app, "_offer_deal_enrichment", return_value="offer!") as _offer_spy:
    out = app._apply_diamond_post_approval_continuation(
        _fake_contract("completed"), _fake_lifecycle("outcome_unknown"),
        origin_chat_id="c1", origin_channel="telegram",
    )
    chk("completed but NOT verified_write_success -> no enrichment offer",
        out.enrichment_offer_text is None)
    chk("completed but NOT verified_write_success -> _offer_deal_enrichment never called",
        not _offer_spy.called)
    chk("resume is still attempted with record_id='' for an unverified completion",
        _resume_spy.call_args[0][1] == "")

with patch.object(app, "_resolve_diamond_path_continuation", return_value="נמשך!") as _resume_spy, \
     patch.object(app, "_offer_deal_enrichment", return_value="בוא נשלים פרטים") as _offer_spy:
    out = app._apply_diamond_post_approval_continuation(
        _fake_contract("executed", tool_name="crm_create_deal"),
        _fake_lifecycle("verified_write_success", _rec(2)),
        origin_chat_id="c1", origin_channel="telegram",
    )
    chk("executed + verified crm_create_deal -> enrichment offer text populated",
        out.enrichment_offer_text == "בוא נשלים פרטים")
    chk("enrichment_offer_choices is the standard כן/לא pair",
        out.enrichment_offer_choices == ("כן", "לא"))
    chk("resume text is also populated (delegated unchanged)", out.resume_text == "נמשך!")
    chk("_offer_deal_enrichment called with the correct chat/channel/record_id",
        _offer_spy.call_args[0] == ("c1", "telegram", _rec(2)))

with patch.object(app, "_resolve_diamond_path_continuation", return_value=None), \
     patch.object(app, "_offer_deal_enrichment", return_value="should never be called") as _offer_spy:
    out = app._apply_diamond_post_approval_continuation(
        _fake_contract("executed", tool_name="airtable_update"),
        _fake_lifecycle("verified_write_success", _rec(3)),
        origin_chat_id="c1", origin_channel="telegram",
    )
    chk("verified but NOT crm_create_deal (e.g. the enrichment write itself) "
        "-> no enrichment offer", out.enrichment_offer_text is None)
    chk("non-crm_create_deal tool -> _offer_deal_enrichment never called", not _offer_spy.called)


# ══════════════════════════════════════════════════════════════════
# Part 2 — Root Deal approval: BOTH ingress paths call the SAME shared
# hook and drive the SAME enrichment offer. (Required tests 3, 4, 8, 14)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 2: root Deal approval — button vs. typed text ──")


def _fake_cq(chat_id: str, data: str):
    return SimpleNamespace(
        id=f"cbq-{chat_id}",
        data=data,
        from_user=SimpleNamespace(id=chat_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1),
    )


def _propose_deal(user_id: str, name: str) -> str:
    r = _real_gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=f"boss_hq:{user_id}",
        tool_name="crm_create_deal",
        tool_inputs={"name": name, "domain": "import", "owner_id": user_id},
        origin_channel="telegram", origin_chat_id=user_id,
        requires_approval=True, identity=_identity(user_id), trusted_source="agent",
    )
    assert r.ok, f"propose_action failed unexpectedly: {r.user_message}"
    return r.contract_id


# 2a. Button (callback) path -------------------------------------------------
button_user = "d1-btn-deal"
button_contract_id = _propose_deal(button_user, "עסקת כפתור")
button_record_id = _rec(101)

_set_offer_calls = []


def _spy_set_offer(chat_id, state, channel=""):
    _set_offer_calls.append((chat_id, state, channel))


bot_mock = MagicMock()
with patch.object(app, "bot", bot_mock), \
     patch.object(app, "resolve_identity", return_value=_identity(button_user)), \
     patch("tools.dispatcher.dispatch_tool",
           side_effect=lambda *a, **k: _airtable_ok("crm_create_deal", button_record_id)), \
     patch.object(app, "dispatch_tool",
                  side_effect=lambda *a, **k: _airtable_ok("crm_create_deal", button_record_id)), \
     patch.object(app, "_flag_enabled", side_effect=lambda name: name in _PROD_FLAGS_ON), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name in _PROD_FLAGS_ON), \
     patch("session_store.lead_sessions.set_deal_enrichment_offer", side_effect=_spy_set_offer), \
     patch("session_store.lead_sessions.get_commercial_completion", return_value=None):
    from event_bus import bus as _real_bus
    action_id, _ = _real_bus.request_approval(
        action="crm_create_deal",
        payload={
            "tool_name": "crm_create_deal",
            "tool_inputs": {"name": "עסקת כפתור", "domain": "import", "owner_id": button_user},
            "origin_channel": "telegram", "origin_chat_id": button_user,
            "canonical_user_id": f"boss_hq:{button_user}", "user_chat_id": button_user,
            "channel": "telegram", "contract_id": button_contract_id,
        },
        chat_id=button_user, label="עסקת כפתור",
    )
    cq = _fake_cq(button_user, f"approve:{action_id}")
    app._handle_approval_callback_impl(cq)

button_contract_after = _real_gw._ledger.find_by_id(button_contract_id)
chk("button path: contract reaches a terminal success state",
    button_contract_after is not None and button_contract_after.status in ("completed", "executed"))
chk("button path: exactly one enrichment offer persisted",
    len(_set_offer_calls) == 1)
if _set_offer_calls:
    chk("button path: enrichment offer carries the verified record_id",
        _set_offer_calls[0][1].get("record_id") == button_record_id)
chk("button path: exactly one final Telegram delivery (Single-Speaker)",
    (bot_mock.edit_message_text.call_count + bot_mock.send_message.call_count) == 1)
if bot_mock.edit_message_text.call_args is not None:
    _button_final_text = bot_mock.edit_message_text.call_args[0][0]
    chk("button path: final message includes the enrichment offer text",
        "רוצה להשלים פרטים נוספים" in _button_final_text)


# 2b. Typed-text confirmation path -------------------------------------------
text_user = "d1-txt-deal"
text_contract_id = _propose_deal(text_user, "עסקת טקסט")
text_record_id = _rec(102)
text_contract = _real_gw._ledger.find_by_id(text_contract_id)

_set_offer_calls_text = []
with patch("session_store.lead_sessions.set_deal_enrichment_offer",
           side_effect=lambda chat_id, state, channel="": _set_offer_calls_text.append((chat_id, state, channel))), \
     patch("session_store.lead_sessions.get_commercial_completion", return_value=None), \
     patch("session_store.lead_sessions.get_last_prompted_contract", return_value=None), \
     patch("tools.dispatcher.dispatch_tool",
           side_effect=lambda *a, **k: _airtable_ok("crm_create_deal", text_record_id)):
    text_out_meta: dict = {}
    text_reply = _real_gw.route_confirmation_word(
        f"boss_hq:{text_user}", approver_role=Role.OWNER,
        live_contracts=[text_contract], use_session_bookmark=False,
        out_meta=text_out_meta, post_approval_hook=app._diamond_post_approval_hook,
    )

text_contract_after = _real_gw._ledger.find_by_id(text_contract_id)
chk("typed-text path: contract reaches a terminal success state",
    text_contract_after is not None and text_contract_after.status in ("completed", "executed"))
chk("typed-text path: exactly one enrichment offer persisted "
    "(THE FIX — this used to never fire for typed confirmation)",
    len(_set_offer_calls_text) == 1)
if _set_offer_calls_text:
    chk("typed-text path: enrichment offer carries the verified record_id",
        _set_offer_calls_text[0][1].get("record_id") == text_record_id)
chk("typed-text path: reply text includes the SAME enrichment offer text as the button path",
    "רוצה להשלים פרטים נוספים" in text_reply)
chk("typed-text path: out_meta carries the same כן/לא choices the button path's "
    "keyboard uses (so the plain-text-reply webhook path attaches real buttons too)",
    text_out_meta.get("commercial_completion_choices") == ("כן", "לא"))


# ══════════════════════════════════════════════════════════════════
# Part 3 — Nested Contact approval resumes the parent Deal, via BOTH
# ingress paths. (Required tests 1, 2, 7)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 3: nested Contact approval resumes parent Deal — button vs. typed text ──")


def _build_parked_nested_contact_state(deal_name: str, chat_id: str):
    """Drives the REAL app.run_agent() through the CREATE_CONFIRM offer +
    a phone-number answer — exactly like test_bug_diamond_parent_orphaned_
    on_nested_queue.py's turns 1-2 — to produce a genuinely parked parent
    session AND the matching continuation_hint (nested_entity/return_field/
    nonce) the router itself computed. A hand-built ContinuationRef with an
    arbitrary nonce has no counterpart in real session state and always
    fails resume_nested()'s mismatch check — this is why that approach
    doesn't work and this one does."""
    from airtable_schema import CommercialStatus, Currency, DealType, RelationshipType
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values={
        "name": deal_name, "domain": "recruitment", "owner": "recOwnerD1TestXX",
        "deal_type": DealType.SERVICE, "relationship_type": RelationshipType.ONE_OFF,
        "currency": Currency.ILS, "commercial_status": CommercialStatus.PROSPECT,
    })
    assert first.outcome == "CLARIFY"
    offer = router.answer_human(
        first.session, "איש קשר חדש", link_lookup=lambda *_: [], scope="boss_hq:eliyahu",
    )
    assert offer.outcome == "CLARIFY" and offer.choices == ("כן", "לא")
    parked_after_offer = serialize_completion_session(offer.session)

    with patch.object(app, "resolve_identity", return_value=_identity(chat_id)), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch("session_store.lead_sessions.get",
               return_value={"commercial_completion": parked_after_offer}), \
         patch("session_store.lead_sessions.clear_commercial_completion"), \
         patch("session_store.lead_sessions.set_commercial_completion") as _mock_set_1, \
         patch.object(app, "_queue_approval_detailed",
                      side_effect=AssertionError("turn 1 ('כן') must only ask for phone")), \
         patch("feature_flags.is_enabled", side_effect=lambda name: name in _PROD_FLAGS_ON):
        reply_yes = app.run_agent("כן", chat_id, "telegram")
    assert "טלפון" in reply_yes, f"unexpected turn-1 reply: {reply_yes!r}"
    state_after_yes = _mock_set_1.call_args[0][1]

    captured_hint: dict = {}

    def _queue_mock_contact(tool, payload, chat_id, channel, user_text,
                             trusted_source="agent", continuation_hint=None, **_):
        captured_hint.update(continuation_hint or {})
        return {"message": "⏳ בקשת אישור נשלחה (איש קשר)", "contract_id": "contractChildD1",
                "ok": True, "terminal_outcome": None, "action_tool": "crm_find_or_create_contact",
                "created_this_turn": True, "owner_notified": True}

    with patch.object(app, "resolve_identity", return_value=_identity(chat_id)), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch("session_store.lead_sessions.get",
               return_value={"commercial_completion": state_after_yes}), \
         patch("session_store.lead_sessions.clear_commercial_completion") as _mock_clear_2, \
         patch("session_store.lead_sessions.set_commercial_completion") as _mock_set_2, \
         patch.object(app, "_queue_approval_detailed", _queue_mock_contact), \
         patch("feature_flags.is_enabled", side_effect=lambda name: name in _PROD_FLAGS_ON):
        app.run_agent("0500000001", chat_id, "telegram")
    assert not _mock_clear_2.called, "nested queue must not clear the parked parent"
    assert _mock_set_2.called and captured_hint, "nested Contact was not actually queued"
    return _mock_set_2.call_args[0][1], captured_hint


def _run_nested_via_callback(user_id: str, deal_name: str, contact_record_id: str):
    parked_state, hint = _build_parked_nested_contact_state(deal_name, user_id)
    contract_id = _real_gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=f"boss_hq:{user_id}",
        tool_name="crm_find_or_create_contact",
        tool_inputs={"name": "איש קשר חדש", "phone": "0500000001"},
        origin_channel="telegram", origin_chat_id=user_id,
        requires_approval=True, identity=_identity(user_id), trusted_source="agent",
        continuation_ref=ContinuationRef.for_commercial_completion(
            session_key=user_id, channel="telegram",
            nested_entity=hint["nested_entity"], return_field=hint["return_field"],
            nonce=hint["nonce"],
        ),
    ).contract_id

    from event_bus import bus as _real_bus
    action_id, _ = _real_bus.request_approval(
        action="crm_find_or_create_contact",
        payload={
            "tool_name": "crm_find_or_create_contact",
            "tool_inputs": {"name": "איש קשר חדש", "phone": "0500000001"},
            "origin_channel": "telegram", "origin_chat_id": user_id,
            "canonical_user_id": f"boss_hq:{user_id}", "user_chat_id": user_id,
            "channel": "telegram", "contract_id": contract_id,
        },
        chat_id=user_id, label="איש קשר חדש",
    )

    deal_queue_calls = []

    def _queue_mock_deal(tool, payload, chat_id, channel, user_text,
                          trusted_source="agent", continuation_hint=None, **_):
        deal_queue_calls.append((tool, payload))
        return {
            "message": "⏳ בקשת אישור נשלחה (עסקה)", "contract_id": "contractParentD1",
            "ok": True, "terminal_outcome": None, "action_tool": "crm_create_deal",
            "created_this_turn": True, "owner_notified": True,
        }

    bot_mock = MagicMock()
    with patch.object(app, "bot", bot_mock), \
         patch.object(app, "resolve_identity", return_value=_identity(user_id)), \
         patch("tools.dispatcher.dispatch_tool",
               side_effect=lambda *a, **k: _airtable_ok("crm_find_or_create_contact", contact_record_id)), \
         patch.object(app, "dispatch_tool",
                      side_effect=lambda *a, **k: _airtable_ok("crm_find_or_create_contact", contact_record_id)), \
         patch.object(app, "_flag_enabled", side_effect=lambda name: name in _PROD_FLAGS_ON), \
         patch("feature_flags.is_enabled", side_effect=lambda name: name in _PROD_FLAGS_ON), \
         patch("session_store.lead_sessions.get_commercial_completion", return_value=parked_state), \
         patch("session_store.lead_sessions.set_commercial_completion") as _mock_set_cc, \
         patch("session_store.lead_sessions.clear_commercial_completion") as _mock_clear_cc, \
         patch.object(app, "_queue_approval_detailed", _queue_mock_deal):
        cq = _fake_cq(user_id, f"approve:{action_id}")
        app._handle_approval_callback_impl(cq)
    return deal_queue_calls, bot_mock, _mock_clear_cc


calls_btn, bot_btn, clear_btn = _run_nested_via_callback(
    "d1-btn-nested", "עסקה מקושרת-כפתור", _rec(201),
)
chk("nested via BUTTON: parent Deal is resumed and queued for its own approval",
    len(calls_btn) == 1 and calls_btn[0][0] == "crm_create_deal")
chk("nested via BUTTON: parked parent completion is cleared once safely queued",
    clear_btn.called)
if bot_btn.edit_message_text.call_args is not None:
    chk("nested via BUTTON: final message reports the resumed parent Deal",
        "בקשת אישור נשלחה" in bot_btn.edit_message_text.call_args[0][0])


def _run_nested_via_text(user_id: str, deal_name: str, contact_record_id: str):
    parked_state, hint = _build_parked_nested_contact_state(deal_name, user_id)
    contract = _real_gw._ledger.find_by_id(
        _real_gw.propose_action(
            tenant_id="boss_hq", canonical_user_id=f"boss_hq:{user_id}",
            tool_name="crm_find_or_create_contact",
            tool_inputs={"name": "איש קשר חדש 2", "phone": "0500000002"},
            origin_channel="telegram", origin_chat_id=user_id,
            requires_approval=True, identity=_identity(user_id), trusted_source="agent",
            continuation_ref=ContinuationRef.for_commercial_completion(
                session_key=user_id, channel="telegram",
                nested_entity=hint["nested_entity"], return_field=hint["return_field"],
                nonce=hint["nonce"],
            ),
        ).contract_id
    )

    deal_queue_calls = []

    def _queue_mock_deal(tool, payload, chat_id, channel, user_text,
                          trusted_source="agent", continuation_hint=None, **_):
        deal_queue_calls.append((tool, payload))
        return {
            "message": "⏳ בקשת אישור נשלחה (עסקה)", "contract_id": "contractParentD1Text",
            "ok": True, "terminal_outcome": None, "action_tool": "crm_create_deal",
            "created_this_turn": True, "owner_notified": True,
        }

    with patch("tools.dispatcher.dispatch_tool",
               side_effect=lambda *a, **k: _airtable_ok("crm_find_or_create_contact", contact_record_id)), \
         patch("session_store.lead_sessions.get_commercial_completion", return_value=parked_state), \
         patch("session_store.lead_sessions.set_commercial_completion"), \
         patch("session_store.lead_sessions.clear_commercial_completion") as _mock_clear_cc, \
         patch("session_store.lead_sessions.get_last_prompted_contract", return_value=None), \
         patch.object(app, "_queue_approval_detailed", _queue_mock_deal):
        reply = _real_gw.route_confirmation_word(
            f"boss_hq:{user_id}", approver_role=Role.OWNER,
            live_contracts=[contract], use_session_bookmark=False,
            post_approval_hook=app._diamond_post_approval_hook,
        )
    return deal_queue_calls, reply, _mock_clear_cc


calls_txt, reply_txt, clear_txt = _run_nested_via_text(
    "d1-txt-nested", "עסקה מקושרת-טקסט", _rec(202),
)
chk("nested via TYPED TEXT: parent Deal is resumed and queued for its own approval "
    "(THE FIX — this used to silently never happen)",
    len(calls_txt) == 1 and calls_txt[0][0] == "crm_create_deal")
chk("nested via TYPED TEXT: parked parent completion is cleared once safely queued",
    clear_txt.called)
chk("nested via TYPED TEXT: reply reports the resumed parent Deal",
    "בקשת אישור נשלחה" in reply_txt)


# ══════════════════════════════════════════════════════════════════
# Part 4 — Rejected / failed approvals never continue. Exactly-once.
# (Required tests 5, 6, 7 second half)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 4: rejected/failed approvals never continue; exactly-once ──")

reject_user = "d1-reject-deal"
reject_contract_id = _propose_deal(reject_user, "עסקה נדחית")
with patch.object(app, "_apply_diamond_post_approval_continuation") as _hook_spy_reject:
    rejection_reply = _real_gw.reject(reject_contract_id, rejected_by=f"boss_hq:{reject_user}")
chk("a rejected contract never reaches the shared continuation hook at all",
    not _hook_spy_reject.called)
chk("reject() itself still reports cancellation", "בוטלה" in rejection_reply)

fail_user = "d1-fail-deal"
fail_contract_id = _propose_deal(fail_user, "עסקה שנכשלת")
fail_contract = _real_gw._ledger.find_by_id(fail_contract_id)
_offer_calls_fail = []
with patch("tools.dispatcher.dispatch_tool",
           side_effect=lambda *a, **k: _airtable_fail("crm_create_deal")), \
     patch("session_store.lead_sessions.get_last_prompted_contract", return_value=None), \
     patch("session_store.lead_sessions.set_deal_enrichment_offer",
           side_effect=lambda *a, **k: _offer_calls_fail.append(1)):
    _real_gw.route_confirmation_word(
        f"boss_hq:{fail_user}", approver_role=Role.OWNER,
        live_contracts=[fail_contract], use_session_bookmark=False,
        post_approval_hook=app._diamond_post_approval_hook,
    )
fail_contract_after = _real_gw._ledger.find_by_id(fail_contract_id)
chk("a failed dispatch never leaves the contract completed/executed",
    fail_contract_after.status not in ("completed", "executed"))
chk("a failed/unverified write never triggers an enrichment offer",
    len(_offer_calls_fail) == 0)

# Exactly-once: re-resolve the SAME (now-terminal) contract a second time —
# the shared hook must not fire again (find_live_contracts() no longer
# returns it, so route_confirmation_word() falls through to "no pending").
once_user = "d1-once-deal"
once_contract_id = _propose_deal(once_user, "עסקה פעם אחת")
once_record_id = _rec(301)
_offer_calls_once = []
with patch("tools.dispatcher.dispatch_tool",
           side_effect=lambda *a, **k: _airtable_ok("crm_create_deal", once_record_id)), \
     patch("session_store.lead_sessions.get_last_prompted_contract", return_value=None), \
     patch("session_store.lead_sessions.get_commercial_completion", return_value=None), \
     patch("session_store.lead_sessions.set_deal_enrichment_offer",
           side_effect=lambda *a, **k: _offer_calls_once.append(1)):
    once_contract = _real_gw._ledger.find_by_id(once_contract_id)
    _real_gw.route_confirmation_word(
        f"boss_hq:{once_user}", approver_role=Role.OWNER,
        live_contracts=[once_contract], use_session_bookmark=False,
        post_approval_hook=app._diamond_post_approval_hook,
    )
    # Second resolution attempt: find_live_contracts() no longer returns a
    # terminal contract, so the caller passes an empty live list here,
    # exactly like production's find_live_contracts() would.
    second_reply = _real_gw.route_confirmation_word(
        f"boss_hq:{once_user}", approver_role=Role.OWNER,
        live_contracts=[], use_session_bookmark=False,
        post_approval_hook=app._diamond_post_approval_hook,
    )
chk("the enrichment offer fires exactly once across two resolution attempts "
    "on the same contract", len(_offer_calls_once) == 1)
chk("a second confirm with no live contract left gets the canonical no-pending reply",
    bool(second_reply))


# ══════════════════════════════════════════════════════════════════
# Part 5 — durable deal_enrichment_offer: persist -> simulated restart ->
# restore -> next answer continues. (Required tests 9, 10)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 5: deal_enrichment_offer survives a simulated restart ──")

import sys as _sys
import types as _types
import json as _json


def _fake_airtable_module():
    """Full-module replacement — the same technique session_store.py's own
    self-test (_run_tests()) uses, so every deferred `from tools.
    airtable_tools import X` call inside session_store.py's methods (there
    are several distinct call sites: _sync_to_db, _find_best_session_in_db,
    _load_from_db) resolves consistently, instead of risking missing one
    with a narrower per-function patch."""
    mod = _types.ModuleType("tools.airtable_tools")
    saves = []
    mod.airtable_add = lambda t, f: (saves.append(dict(f)), {"ok": True, "external_id": "recD1RestartSeed01"})[1]
    mod.airtable_update = lambda t, r, f: (saves.append(dict(f)), {"ok": True, "external_id": r})[1]
    mod.airtable_get = lambda t, formula: "אין רשומות"
    mod.airtable_get_records = lambda t, formula: []
    return mod, saves


restart_sender = "d1-restart-user"
restart_record_id = _rec(401)
restart_offer_state = {
    "stage": "collecting", "record_id": restart_record_id,
    "remaining_fields": ["currency"],
    "collected": {"Deal Type Code": "one_off"},
}

fake_at_write, at_saves = _fake_airtable_module()
with patch.dict(_sys.modules, {"tools.airtable_tools": fake_at_write}):
    store_before = session_store.PersistentSessionStore(maxsize=5)
    store_before.set_deal_enrichment_offer(restart_sender, restart_offer_state, channel="telegram")
    # Confirm it is at least readable from the SAME (still-warm) process —
    # sanity check before the actual restart simulation below.
    chk("same-process read-back before restart: offer present",
        store_before.get_deal_enrichment_offer(restart_sender, channel="telegram") is not None)

chk("writing the offer round-trips through _sync_to_db (a write was captured)",
    len(at_saves) >= 1)
_persisted_fields = at_saves[-1]
_persisted_state_json = _json.loads(_persisted_fields[session_store.SF.STATE_JSON])
chk("THE FIX: the persisted State JSON blob actually contains "
    "deal_enrichment_offer (previously silently dropped by _sync_to_db's whitelist)",
    _persisted_state_json.get("deal_enrichment_offer", {}).get("record_id") == restart_record_id)

# ── Simulate a process restart: a BRAND-NEW store instance (empty RAM),
# restoring purely from the persisted Airtable row captured above. ──
fake_at_read, _ = _fake_airtable_module()
fake_at_read.airtable_get_records = lambda t, formula: [{
    "id": "recD1RestartSeed01",
    "fields": {
        session_store.SF.SENDER_ID: restart_sender,
        session_store.SF.CONTEXT_TYPE: "lead",
        session_store.SF.CHANNEL: "telegram",
        session_store.SF.STATE_JSON: _json.dumps(_persisted_state_json, ensure_ascii=False),
    },
}]

with patch.dict(_sys.modules, {"tools.airtable_tools": fake_at_read}):
    store_after_restart = session_store.PersistentSessionStore(maxsize=5)
    restored_offer = store_after_restart.get_deal_enrichment_offer(restart_sender, channel="telegram")

chk("THE FIX: a fresh process (empty RAM) restores the SAME enrichment "
    "offer from the persisted Airtable row", restored_offer is not None)
if restored_offer:
    chk("restored offer carries the same record_id",
        restored_offer.get("record_id") == restart_record_id)
    chk("restored offer carries the same remaining_fields/collected",
        restored_offer.get("remaining_fields") == ["currency"]
        and restored_offer.get("collected") == {"Deal Type Code": "one_off"})

# The restored state is directly usable by the real handler for the NEXT
# local answer — proves the restart didn't just restore inert data, but a
# genuinely continuable enrichment loop.
_restart_queue_calls = []


def _restart_queue_mock(tool, payload, chat_id, channel, user_text, trusted_source="agent", **_):
    _restart_queue_calls.append((tool, payload))
    return {"message": "⏳ בקשת אישור נשלחה", "contract_id": "contractRestartD1",
            "ok": True, "terminal_outcome": None, "action_tool": tool,
            "created_this_turn": True, "owner_notified": True}


with patch("session_store.lead_sessions.clear_deal_enrichment_offer") as _restart_clear, \
     patch.object(app, "_queue_approval_detailed", _restart_queue_mock):
    restart_reply = app._handle_deal_enrichment_reply(
        restored_offer, restart_sender, "telegram", "USD",
    )
chk("restored enrichment state accepts the next local answer via the REAL "
    "handler (not a reimplementation)", bool(restart_reply))
chk("restored enrichment: currency answer is accepted and the (now-empty) "
    "remaining fields queue the accumulated update",
    len(_restart_queue_calls) == 1 and _restart_queue_calls[0][0] == "airtable_update")
if _restart_queue_calls:
    chk("restored enrichment: the queued fields include both the pre-restart "
        "and post-restart answers", _restart_queue_calls[0][1]["fields"].get("Deal Type Code") == "one_off"
        and _restart_queue_calls[0][1]["fields"].get("Currency") == "USD")
chk("restored enrichment: the offer is cleared once the loop finishes",
    _restart_clear.called)


# ══════════════════════════════════════════════════════════════════
# Part 6 — commercial_completion: callback ingress exemption from
# mark_context_interrupted(). (Required tests 11, 12)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 6: commercial_completion: callbacks don't mark context interrupted ──")

with patch("core.action_gateway.action_gateway.mark_context_interrupted") as _mark_spy:
    app._apply_ingress_context_gate(
        _identity("d1-gate-user"),
        app._IngressEvent(channel="telegram", kind="callback", data="commercial_completion:כן"),
    )
chk("THE FIX: a commercial_completion: callback does NOT mark context interrupted",
    not _mark_spy.called)

with patch("core.action_gateway.action_gateway.mark_context_interrupted") as _mark_spy2:
    app._apply_ingress_context_gate(
        _identity("d1-gate-user2"),
        app._IngressEvent(channel="telegram", kind="callback", data="some_other_unrelated_callback:xyz"),
    )
chk("regression: an UNRELATED callback still marks context interrupted "
    "(the exemption is narrow, not blanket)", _mark_spy2.called)

with patch("core.action_gateway.action_gateway.mark_context_interrupted") as _mark_spy3:
    app._apply_ingress_context_gate(
        _identity("d1-gate-user3"),
        app._IngressEvent(channel="telegram", kind="callback", data="approve:abc123"),
    )
chk("regression: approve:/reject: callbacks remain exempt (unchanged)", not _mark_spy3.called)


# ══════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(f"DIAMOND-REMEDIATION-D1 regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
